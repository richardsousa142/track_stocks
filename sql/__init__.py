"""
Pacote de acesso ao PostgreSQL (schema ``track_stocks``, catálogo, repositórios).

Uso::

    python -m sql
"""

from __future__ import annotations

from sql.catalog import (
    INDICATOR_CODES,
    QUANT_INDICATOR_CODES,
    INDEX_HINTS,
    MOEDA_CODES,
    PERCENTUAL_HINTS,
    RATIO_HINTS,
    build_indicator_rows,
    humanize,
    humanize_codigo,
    infer_bloco,
    infer_camada,
    infer_unidade,
)
from sql.connection import DATABASE_URL, get_connection, get_database_url
from sql.facade import run_as_script
from sql.repos.empresas import (
    normalize_cnpj,
    resolve_empresa_id,
    resolve_empresa_id_by_ticker,
    update_tickers_from_csv,
    upsert_empresa,
    upsert_empresa_completa,
)
from sql.repos.fatos import resolve_indicador_id
from sql.repos.periodos import (
    infer_dt_referencia,
    quarter_end_date,
    resolve_periodo_id,
    upsert_periodo,
)
from sql.schema import DDL, DDL_ENUM_MIGRATION, create_schema_and_catalog

__all__ = [
    "DATABASE_URL",
    "DDL",
    "DDL_ENUM_MIGRATION",
    "INDICATOR_CODES",
    "INDEX_HINTS",
    "MOEDA_CODES",
    "PERCENTUAL_HINTS",
    "QUANT_INDICATOR_CODES",
    "RATIO_HINTS",
    "build_indicator_rows",
    "create_schema_and_catalog",
    "get_connection",
    "get_database_url",
    "humanize",
    "humanize_codigo",
    "infer_bloco",
    "infer_camada",
    "infer_dt_referencia",
    "infer_unidade",
    "normalize_cnpj",
    "persist_quant_metrics",
    "quarter_end_date",
    "resolve_empresa_id",
    "resolve_empresa_id_by_ticker",
    "resolve_indicador_id",
    "resolve_periodo_id",
    "run_as_script",
    "update_tickers_from_csv",
    "upsert_empresa",
    "upsert_empresa_completa",
    "upsert_periodo",
]


def __getattr__(name: str):
    if name == "persist_quant_metrics":
        from pipeline.etl.quantitativos import persist_quant_metrics

        return persist_quant_metrics
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
