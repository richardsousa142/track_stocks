"""
ETL: persistência de preços diários (OHLCV) e setor no PostgreSQL.

Fonte de entrada: df_b3_setor.parquet
Schema esperado do parquet:
    data_pregao  DATE    — data do pregão
    ticker       TEXT    — código de negociação (ex: VALE3)
    open         FLOAT   — preço de abertura
    high         FLOAT   — preço máximo
    low          FLOAT   — preço mínimo
    close        FLOAT   — preço de fechamento
    volume       FLOAT   — volume financeiro total
    setor        TEXT    — classificação setorial (pode ser NULL)

Estratégia:
    1. Valida e limpa o DataFrame
    2. Upsert de setores (ticker_setor) — tabela pequena, executemany
    3. Upsert de preços (precos_diarios) — bulk via COPY + INSERT ON CONFLICT

Idempotente: pode ser re-executado sem duplicar dados.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from pipeline.config import get_database_url
from sql.repos.precos import (
    UpsertStats,
    upsert_precos_diarios,
    upsert_setores_from_df,
    validate_precos_df,
)

logger = logging.getLogger(__name__)


# ── Ponto de entrada principal ────────────────────────────────────────────────

def persist_precos_b3(
    parquet_path: str | Path,
    fonte: str = "b3",
    batch_size: int = 50_000,
    dry_run: bool = False,
) -> UpsertStats:
    """
    Carrega o parquet df_b3_setor e persiste no PostgreSQL.

    Args:
        parquet_path: caminho para o arquivo .parquet
        fonte:        identificador da origem dos dados (metadado)
        batch_size:   linhas por lote no COPY (padrão: 50k)
        dry_run:      se True, valida mas não persiste (útil para CI)

    Returns:
        UpsertStats com contagens e warnings.
    """
    t0 = time.perf_counter()
    stats = UpsertStats()

    # ── 1. Carregar parquet ───────────────────────────────────────────────────
    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet não encontrado: {parquet_path}")

    logger.info("Carregando %s …", parquet_path)
    df = pd.read_parquet(parquet_path)
    stats.linhas_input = len(df)
    logger.info("Linhas carregadas: %d", stats.linhas_input)

    # ── 2. Validar e limpar ───────────────────────────────────────────────────
    df_clean, warnings = validate_precos_df(df)
    stats.warnings.extend(warnings)
    stats.linhas_validas = len(df_clean)
    stats.erros_validacao = stats.linhas_input - stats.linhas_validas
    stats.tickers_distintos = df_clean["ticker"].nunique()
    stats.datas_min = df_clean["data_pregao"].min()
    stats.datas_max = df_clean["data_pregao"].max()

    for w in warnings:
        logger.warning(w)

    logger.info(
        "Dados válidos: %d linhas | %d tickers | %s → %s",
        stats.linhas_validas,
        stats.tickers_distintos,
        stats.datas_min,
        stats.datas_max,
    )

    if dry_run:
        logger.info("dry_run=True — abortando antes da persistência.")
        return stats

    if stats.linhas_validas == 0:
        logger.warning("Nenhuma linha válida para persistir.")
        return stats

    # ── 3. Persistir ─────────────────────────────────────────────────────────
    dsn = get_database_url()

    # Setores (tabela pequena — commit separado e rápido)
    if "setor" in df_clean.columns:
        df_setor = (
            df_clean[["ticker", "setor"]]
            .drop_duplicates(subset="ticker")
            .dropna(subset=["setor"])
        )
        if not df_setor.empty:
            with psycopg.connect(dsn, autocommit=False) as conn:
                stats.setores_upserted = upsert_setores_from_df(conn, df_setor)
                conn.commit()
            logger.info("Setores persistidos: %d tickers.", stats.setores_upserted)
    else:
        logger.info("Coluna 'setor' ausente — ticker_setor não atualizado.")

    # Preços diários (bulk via COPY)
    with psycopg.connect(dsn, autocommit=False) as conn:
        stats.precos_upserted = upsert_precos_diarios(
            conn,
            df_clean,
            fonte=fonte,
            batch_size=batch_size,
        )
        conn.commit()

    elapsed = time.perf_counter() - t0
    logger.info(
        "ETL concluído em %.1fs | preços: %d | setores: %d | warnings: %d",
        elapsed,
        stats.precos_upserted,
        stats.setores_upserted,
        len(stats.warnings),
    )
    return stats


# ── Entrada via __main__ ──────────────────────────────────────────────────────

def run(base_dir: Path | None = None, dry_run: bool = False) -> UpsertStats:
    from pipeline.config import with_base

    root = with_base(base_dir)
    parquet_path = root / "df_b3_setor.parquet"
    return persist_precos_b3(parquet_path, dry_run=dry_run)
