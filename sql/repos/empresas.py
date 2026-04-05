"""Repositório: empresas."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg

from pipeline.config import get_database_url


def normalize_cnpj(cnpj: str) -> str:
    digits = re.sub(r"\D", "", cnpj or "")
    if len(digits) != 14:
        raise ValueError(f"CNPJ inválido: {cnpj}")
    return digits


def cnpj_placeholder(razao_social: str) -> str:
    h = int(hashlib.md5(razao_social.upper().strip().encode("utf-8")).hexdigest(), 16)
    return str(h % (10**14)).zfill(14)


def upsert_empresa(cur, razao_social: str) -> int:
    """ETL fundamentalista: pasta = razão social; CNPJ sintético (MD5)."""
    cnpj_norm = cnpj_placeholder(razao_social)
    cur.execute(
        """
        INSERT INTO track_stocks.empresas
            (razao_social, cnpj_original, cnpj_normalizado)
        VALUES (%s, %s, %s)
        ON CONFLICT (cnpj_normalizado)
        DO UPDATE SET
            razao_social  = EXCLUDED.razao_social,
            atualizado_em = now()
        RETURNING empresa_id;
        """,
        (razao_social, razao_social, cnpj_norm),
    )
    return cur.fetchone()[0]


def upsert_empresa_completa(
    cur,
    razao_social,
    cnpj,
    codigo_cvm=None,
    ticker=None,
    ativo=True,
):
    """Upsert por CNPJ normalizado (dados reais)."""
    cnpj_original = cnpj
    cnpj_normalizado = normalize_cnpj(cnpj)
    cur.execute(
        """
        INSERT INTO track_stocks.empresas
            (razao_social, cnpj_original, cnpj_normalizado, codigo_cvm, ticker, ativo)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (cnpj_normalizado)
        DO UPDATE SET
            razao_social  = EXCLUDED.razao_social,
            cnpj_original = EXCLUDED.cnpj_original,
            codigo_cvm    = COALESCE(EXCLUDED.codigo_cvm, track_stocks.empresas.codigo_cvm),
            ticker        = COALESCE(EXCLUDED.ticker,     track_stocks.empresas.ticker),
            ativo         = EXCLUDED.ativo,
            atualizado_em = now()
        RETURNING empresa_id;
        """,
        (razao_social, cnpj_original, cnpj_normalizado, codigo_cvm, ticker, ativo),
    )
    return cur.fetchone()[0]


def resolve_empresa_id(cur, cnpj: str) -> int:
    cnpj_normalizado = normalize_cnpj(cnpj)
    cur.execute(
        "SELECT empresa_id FROM track_stocks.empresas WHERE cnpj_normalizado = %s",
        (cnpj_normalizado,),
    )
    row = cur.fetchone()
    if row is None:
        raise LookupError(f"Empresa não encontrada para CNPJ {cnpj}")
    return row[0]


def resolve_empresa_id_by_ticker(cur, ticker: str) -> Optional[int]:
    cur.execute(
        "SELECT empresa_id FROM track_stocks.empresas WHERE ticker = %s LIMIT 1",
        (ticker,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def update_tickers_from_csv(
    csv_path: str | Path,
    empresa_col: str = "Empresa",
    ticker_col: str = "ticker",
    skip_empty: bool = True,
) -> dict:
    df_map = pd.read_csv(csv_path)
    df_map.columns = df_map.columns.str.strip()
    df_map[empresa_col] = df_map[empresa_col].str.strip()
    df_map[ticker_col] = df_map[ticker_col].str.strip()

    stats = {"atualizados": 0, "sem_ticker_no_csv": 0, "nao_encontrados_no_banco": 0}

    with psycopg.connect(get_database_url(), autocommit=False) as conn:
        with conn.cursor() as cur:
            for _, row in df_map.iterrows():
                razao = row[empresa_col]
                ticker = row[ticker_col]

                if not ticker or pd.isna(ticker) or ticker == "":
                    stats["sem_ticker_no_csv"] += 1
                    if skip_empty:
                        continue

                cur.execute(
                    """
                    SELECT empresa_id
                    FROM track_stocks.empresas
                    WHERE UPPER(razao_social) = UPPER(%s)
                    LIMIT 1
                    """,
                    (razao,),
                )
                empresa_row = cur.fetchone()

                if empresa_row is None:
                    stats["nao_encontrados_no_banco"] += 1
                    continue

                empresa_id = empresa_row[0]

                cur.execute(
                    """
                    UPDATE track_stocks.empresas
                    SET ticker        = %s,
                        atualizado_em = now()
                    WHERE empresa_id = %s
                    """,
                    (ticker, empresa_id),
                )
                stats["atualizados"] += 1

        conn.commit()

    return stats
