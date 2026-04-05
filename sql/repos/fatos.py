"""Repositório: catálogo de indicadores e fatos."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from psycopg.types.json import Jsonb

from pipeline.config import QUANT_VALUE_ABS_MAX
from sql.catalog import humanize_codigo, infer_bloco, infer_camada, infer_unidade

_SQL_UPSERT_COM_ETL = """
INSERT INTO track_stocks.fato_indicadores
    (empresa_id, periodo_id, indicador_id, valor, etl_execucao_id)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (empresa_id, periodo_id, indicador_id)
DO UPDATE SET
    valor           = EXCLUDED.valor,
    etl_execucao_id = EXCLUDED.etl_execucao_id,
    calculado_em    = now();
"""

_SQL_UPSERT_SEM_ETL = """
INSERT INTO track_stocks.fato_indicadores
    (empresa_id, periodo_id, indicador_id, valor)
VALUES (%s, %s, %s, %s)
ON CONFLICT (empresa_id, periodo_id, indicador_id)
DO UPDATE SET
    valor        = EXCLUDED.valor,
    calculado_em = now();
"""


def is_valid_value(v: Any) -> bool:
    if v is None:
        return False
    try:
        x = float(v)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(x):
        return False
    return abs(x) < QUANT_VALUE_ABS_MAX


def flush_batch(cur, batch: list[tuple]) -> None:
    if not batch:
        return
    n = len(batch[0])
    if n == 5:
        cur.executemany(_SQL_UPSERT_COM_ETL, batch)
    elif n == 4:
        cur.executemany(_SQL_UPSERT_SEM_ETL, batch)
    else:
        raise ValueError(f"Tupla de fatos deve ter 4 ou 5 elementos, obteve {n}")


def resolve_indicador_id(cur, codigo: str) -> int:
    cur.execute(
        "SELECT indicador_id FROM track_stocks.indicadores WHERE codigo = %s",
        (codigo,),
    )
    row = cur.fetchone()
    if row is None:
        raise LookupError(f"Indicador não encontrado: {codigo}")
    return row[0]


def ensure_indicadores(cur, codigos: list[str]) -> dict[str, int]:
    rows = [
        (
            cod,
            humanize_codigo(cod),
            infer_bloco(cod),
            infer_camada(cod),
            infer_unidade(cod),
            Jsonb([]),
        )
        for cod in codigos
    ]
    cur.executemany(
        """
        INSERT INTO track_stocks.indicadores
            (codigo, nome, bloco, camada, unidade, contas_utilizadas)
        VALUES (
            %s, %s,
            %s::track_stocks.bloco_indicador_enum,
            %s,
            %s::track_stocks.unidade_valor_enum,
            %s
        )
        ON CONFLICT (codigo) DO NOTHING;
        """,
        rows,
    )
    cur.execute(
        "SELECT codigo, indicador_id FROM track_stocks.indicadores WHERE codigo = ANY(%s)",
        (codigos,),
    )
    return {r[0]: r[1] for r in cur.fetchall()}


def fetch_indicador_ids_by_codigos(cur, codigos: list[str]) -> dict[str, int]:
    cur.execute(
        "SELECT codigo, indicador_id FROM track_stocks.indicadores WHERE codigo = ANY(%s)",
        (codigos,),
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def row_value_ok_for_quant(val: Any) -> bool:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return False
    try:
        x = float(val)
    except (TypeError, ValueError):
        return False
    return np.isfinite(x) and abs(x) < QUANT_VALUE_ABS_MAX
