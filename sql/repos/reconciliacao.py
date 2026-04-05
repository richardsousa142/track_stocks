"""
Reconciliação de empresa_id após ingestão de demonstrativos.

Problema: o pipeline fundamentalista criou empresas com CNPJs sintéticos (MD5)
que têm ticker. O ETL de demonstrativos criou empresas com CNPJs reais (CVM)
sem ticker. São entidades duplicadas que precisam ser unificadas.

Estratégia:
    1. Para cada empresa com CNPJ real (sem ticker) em fato_demonstrativos,
       encontrar a empresa com ticker pelo CNPJ real (quando disponível via CD_CVM
       / código CVM) ou por correspondência de razão social normalizada.
    2. Copiar o ticker para a empresa com CNPJ real.
    3. (Opcional, mais invasivo) Consolidar fato_demonstrativos para apontar
       para o empresa_id canônico — desnecessário enquanto mantemos ambos.

Essa reconciliação é idempotente.
"""

from __future__ import annotations

import logging
import re

import psycopg

logger = logging.getLogger(__name__)


def _normalize_nome(s: str) -> str:
    """Normaliza razão social para comparação fuzzy simples."""
    s = s.upper().strip()
    # remove sufixos jurídicos comuns
    suffixes = [
        r"\bS\.?A\.?\b", r"\bLTDA\.?\b", r"\bSA\b", r"\bS/A\b",
        r"\bEIRELI\b", r"\bME\b", r"\bEPP\b", r"\bS\.A\b",
    ]
    for pat in suffixes:
        s = re.sub(pat, "", s)
    # remove pontuação e espaços extras
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def link_tickers_por_razao_social(conn: psycopg.Connection) -> dict[str, int]:
    """
    Para empresas com CNPJ real (sem ticker), encontra o ticker pela razão social.
    Retorna {'atualizadas': N, 'nao_encontradas': M}.
    """
    with conn.cursor() as cur:
        # Empresas com ticker (fonte: pipeline fundamentalista)
        cur.execute("""
            SELECT empresa_id, razao_social, ticker
            FROM track_stocks.empresas
            WHERE ticker IS NOT NULL
        """)
        com_ticker = cur.fetchall()

        # Mapa: razão social normalizada → ticker
        ticker_map: dict[str, str] = {
            _normalize_nome(r[1]): r[2] for r in com_ticker
        }

        # Empresas sem ticker que têm dados em fato_demonstrativos
        cur.execute("""
            SELECT DISTINCT e.empresa_id, e.razao_social, e.cnpj_normalizado
            FROM track_stocks.empresas e
            JOIN track_stocks.fato_demonstrativos d USING (empresa_id)
            WHERE e.ticker IS NULL
        """)
        sem_ticker = cur.fetchall()

    stats = {"atualizadas": 0, "nao_encontradas": 0}
    updates: list[tuple[str, int]] = []

    for emp_id, razao, cnpj in sem_ticker:
        norm = _normalize_nome(razao)
        ticker = ticker_map.get(norm)
        if ticker:
            updates.append((ticker, emp_id))
        else:
            stats["nao_encontradas"] += 1
            logger.debug("Sem match de ticker para: %s (norm: %s)", razao, norm)

    if updates:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE track_stocks.empresas SET ticker = %s WHERE empresa_id = %s",
                updates,
            )
        conn.commit()
        stats["atualizadas"] = len(updates)
        logger.info(
            "Tickers vinculados por razão social: %d | sem match: %d",
            stats["atualizadas"], stats["nao_encontradas"],
        )

    return stats


def link_tickers_por_codigo_cvm(conn: psycopg.Connection) -> dict[str, int]:
    """
    Alternativa mais precisa quando CD_CVM está disponível em ambos os lados.
    Atualiza ticker usando o código CVM como chave de join.
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE track_stocks.empresas e_real
            SET ticker = e_old.ticker,
                atualizado_em = now()
            FROM track_stocks.empresas e_old
            WHERE e_real.ticker IS NULL
              AND e_old.ticker IS NOT NULL
              AND e_real.codigo_cvm IS NOT NULL
              AND e_old.codigo_cvm IS NOT NULL
              AND e_real.codigo_cvm = e_old.codigo_cvm
              AND e_real.empresa_id != e_old.empresa_id
        """)
        n = cur.rowcount
    conn.commit()
    logger.info("Tickers vinculados por código CVM: %d", n)
    return {"atualizadas_cvm": n}


def run_reconciliacao(dsn: str) -> dict:
    """Executa todas as estratégias de reconciliação de empresa_id."""
    with psycopg.connect(dsn, autocommit=False) as conn:
        r1 = link_tickers_por_codigo_cvm(conn)
        r2 = link_tickers_por_razao_social(conn)
    return {**r1, **r2}
