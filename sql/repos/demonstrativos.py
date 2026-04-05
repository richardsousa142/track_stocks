"""
Repositório: demonstrativos financeiros (BP, DRE, DFC).

Estratégia de upsert:
    executemany com ON CONFLICT DO UPDATE em batches.
    COPY seria mais rápido mas complica o ON CONFLICT com a PK composta de 5 colunas.
    Para ~1.4M linhas totais, executemany em batches de 2000 é adequado.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

import pandas as pd
import psycopg

logger = logging.getLogger(__name__)

# ── Mapeamento de arquivo → tipo_demo ────────────────────────────────────────

TIPO_DEMO_MAP = {
    "bpa": "BP",
    "bpp": "BP",
    "dre": "DRE",
    "dfc": "DFC",
}

# ── Mapeamento de trimestre por último dia do mês ─────────────────────────────

_QUARTER_BY_MONTH = {3: 1, 6: 2, 9: 3, 12: 4}

# Para meses não-padrão (ex: Camil fiscal year fev/28), mapeamos para o
# trimestre do calendário civil que CONTÉM o mês.
_MONTH_TO_QUARTER = {
    1: 1, 2: 1, 3: 1,    # Q1: jan-mar
    4: 2, 5: 2, 6: 2,    # Q2: abr-jun
    7: 3, 8: 3, 9: 3,    # Q3: jul-set
    10: 4, 11: 4, 12: 4, # Q4: out-dez
}

_QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


def infer_quarter(dt: date) -> tuple[int, date]:
    """
    Infere (trimestre, dt_referencia_padrao) a partir da data de fim de exercício.
    Para datas não-padrão (ex: fev/28), usa o fim do trimestre civil contendo o mês
    e emite um log de aviso (sem raise).
    """
    q = _QUARTER_BY_MONTH.get(dt.month)
    if q is not None:
        return q, dt  # data já é fim de trimestre padrão

    # data não-padrão → mapeia para trimestre civil
    q = _MONTH_TO_QUARTER[dt.month]
    m, d = _QUARTER_END[q]
    import calendar
    # ajusta dia para o último dia do mês correto
    last_day = calendar.monthrange(dt.year, m)[1]
    ref = date(dt.year, m, min(d, last_day))
    logger.debug(
        "Ano fiscal não-padrão: DT_FIM_EXERC=%s mapeado para período %s (Q%d)",
        dt, ref, q,
    )
    return q, ref


# ── Normalização do CNPJ ──────────────────────────────────────────────────────

def _normalize_cnpj(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw) or "")
    if len(digits) != 14:
        raise ValueError(f"CNPJ inválido: {raw!r}")
    return digits


# ── SQL ───────────────────────────────────────────────────────────────────────

_SQL_UPSERT = """
INSERT INTO track_stocks.fato_demonstrativos
    (empresa_id, periodo_id, tipo_demo, grupo_dfp, cd_conta,
     ds_conta, vl_conta, escala_moeda, moeda, st_conta_fixa,
     versao, dt_fim_exerc, etl_execucao_id, calculado_em)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (empresa_id, periodo_id, tipo_demo, grupo_dfp, cd_conta)
DO UPDATE SET
    ds_conta        = EXCLUDED.ds_conta,
    vl_conta        = EXCLUDED.vl_conta,
    escala_moeda    = EXCLUDED.escala_moeda,
    moeda           = EXCLUDED.moeda,
    st_conta_fixa   = EXCLUDED.st_conta_fixa,
    versao          = EXCLUDED.versao,
    dt_fim_exerc    = EXCLUDED.dt_fim_exerc,
    etl_execucao_id = EXCLUDED.etl_execucao_id,
    calculado_em    = now();
"""

_SQL_RESOLVE_EMPRESA = """
SELECT empresa_id FROM track_stocks.empresas
WHERE cnpj_normalizado = %s
LIMIT 1;
"""

_SQL_UPSERT_EMPRESA = """
INSERT INTO track_stocks.empresas
    (razao_social, cnpj_original, cnpj_normalizado, codigo_cvm)
VALUES (%s, %s, %s, %s)
ON CONFLICT (cnpj_normalizado) DO UPDATE SET
    razao_social  = COALESCE(EXCLUDED.razao_social, track_stocks.empresas.razao_social),
    codigo_cvm    = COALESCE(EXCLUDED.codigo_cvm,   track_stocks.empresas.codigo_cvm),
    atualizado_em = now()
RETURNING empresa_id;
"""

_SQL_GET_OR_CREATE_EMPRESA = """
WITH upserted AS (
    INSERT INTO track_stocks.empresas
        (razao_social, cnpj_original, cnpj_normalizado, codigo_cvm)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (cnpj_normalizado) DO UPDATE SET
        codigo_cvm    = COALESCE(EXCLUDED.codigo_cvm, track_stocks.empresas.codigo_cvm),
        atualizado_em = now()
    RETURNING empresa_id
)
SELECT empresa_id FROM upserted
UNION ALL
SELECT empresa_id FROM track_stocks.empresas WHERE cnpj_normalizado = %s
LIMIT 1;
"""

_SQL_UPSERT_PERIODO = """
INSERT INTO track_stocks.periodos (freq, ano, trimestre, mes, dt_referencia)
VALUES ('T', %s, %s, NULL, %s)
ON CONFLICT DO NOTHING
RETURNING periodo_id;
"""

_SQL_GET_PERIODO = """
SELECT periodo_id FROM track_stocks.periodos
WHERE freq = 'T' AND ano = %s AND trimestre = %s
LIMIT 1;
"""


# ── Lookup caches (dentro de uma execução ETL) ────────────────────────────────

def resolve_empresa_id(
    dsn: str,
    cnpj_raw: str,
    razao_social: str,
    cd_cvm: str | None,
    _cache: dict[str, int],
) -> int:
    """
    Resolve (ou cria) empresa em transação AUTOCOMMIT independente.

    Usar autocommit evita que rollbacks do processamento de arquivos
    desfaçam a criação da empresa no banco, corrompendo o cache com
    IDs que não existem mais.
    """
    cnpj_norm = _normalize_cnpj(cnpj_raw)
    if cnpj_norm in _cache:
        return _cache[cnpj_norm]

    cd_cvm_int = None
    if cd_cvm and str(cd_cvm).strip():
        try:
            cd_cvm_int = int(str(cd_cvm).strip())
        except ValueError:
            pass

    with psycopg.connect(dsn, autocommit=True) as conn_ac:
        with conn_ac.cursor() as cur:
            cur.execute(
                _SQL_GET_OR_CREATE_EMPRESA,
                (razao_social, cnpj_raw, cnpj_norm, cd_cvm_int, cnpj_norm),
            )
            row = cur.fetchone()

    if row is None:
        raise LookupError(f"Não foi possível resolver empresa_id para CNPJ {cnpj_raw}")

    eid = row[0]
    _cache[cnpj_norm] = eid
    return eid


def resolve_periodo_id(
    cur: psycopg.Cursor,
    dt_fim: date,
    _cache: dict[date, int],
) -> tuple[int, date]:
    """
    Retorna (periodo_id, dt_referencia_padrao).
    Para datas não-padrão, dt_referencia_padrao é o fim do trimestre civil.
    A data original é preservada em fato_demonstrativos.dt_fim_exerc.
    """
    if dt_fim in _cache:
        return _cache[dt_fim]

    trimestre, dt_ref = infer_quarter(dt_fim)
    ano = dt_ref.year  # usa o ano da data de referência padrão

    cur.execute(_SQL_UPSERT_PERIODO, (ano, trimestre, dt_ref))
    row = cur.fetchone()
    if row is None:
        cur.execute(_SQL_GET_PERIODO, (ano, trimestre))
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"Não foi possível resolver periodo_id para {dt_fim}")

    pid = row[0]
    _cache[dt_fim] = (pid, dt_ref)
    return pid, dt_ref


# ── Normalização do DataFrame ─────────────────────────────────────────────────

def normalize_demo_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpa e padroniza o DataFrame de um arquivo de demonstrativo CVM.
    Retorna df limpo com dtypes corretos.
    """
    df = df.copy()

    # Renomear colunas para lowercase
    df.columns = [c.strip().upper() for c in df.columns]

    required = {"CNPJ_CIA", "DT_FIM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA", "GRUPO_DFP"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    # Datas
    df["DT_FIM_EXERC"] = pd.to_datetime(df["DT_FIM_EXERC"], errors="coerce").dt.date
    df = df.dropna(subset=["DT_FIM_EXERC"])

    # Valor numérico
    df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")

    # CD_CONTA e DS_CONTA como string
    df["CD_CONTA"] = df["CD_CONTA"].astype(str).str.strip()
    df["DS_CONTA"] = df["DS_CONTA"].astype(str).str.strip()

    # GRUPO_DFP — normaliza encoding
    df["GRUPO_DFP"] = df["GRUPO_DFP"].astype(str).str.strip()

    # CNPJ_CIA
    df["CNPJ_CIA"] = df["CNPJ_CIA"].astype(str).str.strip()

    # ST_CONTA_FIXA → bool
    if "ST_CONTA_FIXA" in df.columns:
        df["ST_CONTA_FIXA"] = df["ST_CONTA_FIXA"].astype(str).str.upper().map(
            {"S": True, "N": False}
        )

    # VERSAO → int
    if "VERSAO" in df.columns:
        df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce")

    # ESCALA_MOEDA e MOEDA
    for col in ["ESCALA_MOEDA", "MOEDA"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
        else:
            df[col] = None

    # Remove linhas sem CD_CONTA ou CNPJ_CIA
    df = df[df["CD_CONTA"].str.len() > 0]
    df = df[df["CNPJ_CIA"].str.len() >= 14]

    return df


# ── Flush de batch ────────────────────────────────────────────────────────────

def flush_demo_batch(cur: psycopg.Cursor, batch: list[tuple]) -> None:
    if not batch:
        return
    cur.executemany(_SQL_UPSERT, batch)


def build_demo_rows(
    df: pd.DataFrame,
    tipo_demo: str,
    empresa_id: int,
    periodo_id: int,
    dt_fim_exerc: date,
    etl_id: int | None,
) -> list[tuple]:
    """
    Converte as linhas do DataFrame em tuplas prontas para insert.
    Uma tupla por (grupo_dfp, cd_conta).
    dt_fim_exerc é a data REAL do fim do exercício (preserva fiscal year não-padrão).
    """
    rows: list[tuple] = []
    for _, r in df.iterrows():
        rows.append((
            empresa_id,
            periodo_id,
            tipo_demo,
            r["GRUPO_DFP"],
            r["CD_CONTA"],
            r["DS_CONTA"],
            None if pd.isna(r.get("VL_CONTA", None)) else float(r["VL_CONTA"]),
            r.get("ESCALA_MOEDA") or None,
            r.get("MOEDA") or None,
            r.get("ST_CONTA_FIXA", None),
            int(r["VERSAO"]) if pd.notna(r.get("VERSAO")) else None,
            dt_fim_exerc,
            etl_id,
        ))
    return rows
