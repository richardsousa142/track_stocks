"""Fluxo demo: schema, tickers CSV, persistência de métricas quant."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.config import empresas_ticker_csv_for, result_df_parquet_for
from sql.repos.empresas import update_tickers_from_csv
from sql.schema import create_schema_and_catalog


def run_as_script(base_dir=None) -> None:
    root = Path(base_dir).resolve() if base_dir else Path(".").resolve()
    csv_path = empresas_ticker_csv_for(root)
    result_path = result_df_parquet_for(root)

    create_schema_and_catalog()
    print("Schema e catálogo atualizados com sucesso.")

    ticker_stats = update_tickers_from_csv(csv_path)
    print(
        f"Tickers atualizados: {ticker_stats['atualizados']} | "
        f"Sem ticker no CSV: {ticker_stats['sem_ticker_no_csv']} | "
        f"Não encontrados no banco: {ticker_stats['nao_encontrados_no_banco']}"
    )

    from pipeline.etl.quantitativos import persist_quant_metrics

    result_df = pd.read_parquet(result_path)
    stats = persist_quant_metrics(result_df)
    print(f"Persistência concluída: {stats}")
