"""
Persistência de métricas quantitativas rolling em ``fato_indicadores``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import psycopg

from pipeline.config import (
    BATCH_SIZE,
    empresas_ticker_csv_for,
    get_database_url,
    result_df_parquet_for,
)
from sql.repos.empresas import resolve_empresa_id_by_ticker, update_tickers_from_csv
from sql.repos.fatos import fetch_indicador_ids_by_codigos, flush_batch, row_value_ok_for_quant
from sql.repos.periodos import upsert_periodo
from sql.schema import create_schema_and_catalog

log = logging.getLogger(__name__)


def persist_quant_metrics(
    result_df: pd.DataFrame,
    batch_size: int | None = None,
    skip_missing_tickers: bool = True,
) -> dict:
    bs = batch_size if batch_size is not None else BATCH_SIZE
    id_cols = {"codneg", "year_month", "window_end"}
    value_cols = [c for c in result_df.columns if c not in id_cols]
    col_to_codigo = {col: f"mkt_{col}" for col in value_cols}

    stats = {
        "tickers_ok": 0,
        "tickers_skip": 0,
        "periodos_criados": 0,
        "fatos_inseridos": 0,
    }

    with psycopg.connect(get_database_url(), autocommit=False) as conn:
        with conn.cursor() as cur:
            codigos = list(col_to_codigo.values())
            indicador_cache = fetch_indicador_ids_by_codigos(cur, codigos)

            missing_ind = set(codigos) - set(indicador_cache)
            if missing_ind:
                raise LookupError(
                    f"Indicadores não encontrados no catálogo: {missing_ind}\n"
                    "Execute create_schema_and_catalog() primeiro."
                )

            for ticker, grp in result_df.groupby("codneg"):
                empresa_id = resolve_empresa_id_by_ticker(cur, ticker)

                if empresa_id is None:
                    if skip_missing_tickers:
                        stats["tickers_skip"] += 1
                        continue
                    raise LookupError(
                        f"Ticker '{ticker}' não encontrado em track_stocks.empresas."
                    )

                stats["tickers_ok"] += 1
                batch = []

                for _, row in grp.iterrows():
                    ym = row["year_month"]
                    if hasattr(ym, "year"):
                        ano, mes = int(ym.year), int(ym.month)
                    else:
                        ano, mes = int(str(ym)[:4]), int(str(ym)[5:7])

                    periodo_id = upsert_periodo(cur, freq="M", ano=ano, mes=mes)
                    stats["periodos_criados"] += 1

                    for col in value_cols:
                        valor = row[col]
                        if not row_value_ok_for_quant(valor):
                            continue
                        indicador_id = indicador_cache[col_to_codigo[col]]
                        batch.append((empresa_id, periodo_id, indicador_id, float(valor)))

                    if len(batch) >= bs:
                        flush_batch(cur, batch)
                        stats["fatos_inseridos"] += len(batch)
                        batch.clear()

                if batch:
                    flush_batch(cur, batch)
                    stats["fatos_inseridos"] += len(batch)
                    batch.clear()

        conn.commit()

    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(description="Persiste métricas quantitativas no PostgreSQL.")
    p.add_argument("--base-dir", type=str, default=".", help="Raiz do projeto.")
    p.add_argument(
        "--result-df",
        type=str,
        default=None,
        help="Parquet com result_df (default: data/processed/indicadores/result_df.parquet).",
    )
    p.add_argument(
        "--tickers-csv",
        type=str,
        default=None,
        help="CSV empresa→ticker (default: empresas_com_ticker.csv na raiz).",
    )
    p.add_argument("--schema-only", action="store_true", help="Só cria schema/catálogo e atualiza tickers.")
    args = p.parse_args()

    root = Path(args.base_dir).resolve()
    result_path = Path(args.result_df) if args.result_df else result_df_parquet_for(root)
    csv_path = Path(args.tickers_csv) if args.tickers_csv else empresas_ticker_csv_for(root)

    create_schema_and_catalog()
    log.info("Schema e catálogo OK.")
    st = update_tickers_from_csv(csv_path)
    print(f"Tickers: {st}")

    if args.schema_only:
        return

    df = pd.read_parquet(result_path)
    out = persist_quant_metrics(df)
    print(f"Persistência: {out}")


if __name__ == "__main__":
    main()
