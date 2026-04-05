"""
ETL de indicadores fundamentalistas (parquets → PostgreSQL).
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg

from pipeline.config import (
    ARQUIVO_ANUAL,
    ARQUIVO_TRIMESTRAL,
    BATCH_SIZE,
    NON_INDICATOR_COLS,
    acoes_indicadores_dir_for,
    get_database_url,
)
from sql.repos.empresas import upsert_empresa
from sql.repos.etl_execucoes import finalizar_execucao, iniciar_execucao
from sql.repos.fatos import ensure_indicadores, flush_batch, is_valid_value
from sql.repos.periodos import quarter_end, upsert_periodo

log = logging.getLogger(__name__)


def carregar_parquet(
    path: Path,
    freq: str,
    empresa_id: int,
    conn,
    etl_id: int,
    indicador_map: dict[str, int],
    periodos_cache: dict,
    batch_size: int,
) -> int:
    df = pd.read_parquet(path)
    ind_cols = [c for c in df.columns if c not in NON_INDICATOR_COLS]

    lote: list[tuple] = []
    n_fatos = 0

    def flush() -> None:
        nonlocal n_fatos
        if not lote:
            return
        with conn.cursor() as cur:
            flush_batch(cur, lote)
        n_fatos += len(lote)
        lote.clear()
        conn.commit()

    with conn.cursor() as cur:
        for idx, row in df.iterrows():
            ano = int(row["ano"])
            row_freq = str(row.get("freq", freq))

            trimestre: Optional[int] = None
            if "trimestre" in row and pd.notna(row.get("trimestre")):
                trimestre = int(row["trimestre"])

            if hasattr(idx, "date"):
                dt_ref = idx.date()
            elif trimestre:
                dt_ref = quarter_end(ano, trimestre)
            else:
                dt_ref = date(ano, 12, 31)

            periodo_key = (row_freq, ano, trimestre, dt_ref)
            if periodo_key not in periodos_cache:
                periodos_cache[periodo_key] = upsert_periodo(
                    cur,
                    row_freq,
                    ano,
                    trimestre=trimestre,
                    mes=None,
                    dt_referencia=dt_ref,
                )
            periodo_id = periodos_cache[periodo_key]

            for col in ind_cols:
                val = row[col]
                if not is_valid_value(val):
                    continue
                ind_id = indicador_map.get(col)
                if ind_id is None:
                    continue
                lote.append((empresa_id, periodo_id, ind_id, float(val), etl_id))
                if len(lote) >= batch_size:
                    flush()

    flush()
    return n_fatos


def run_etl(base_dir: Path) -> None:
    ind_dir = acoes_indicadores_dir_for(base_dir)

    if not ind_dir.exists():
        log.error("Pasta não encontrada: %s", ind_dir)
        return

    empresas_dirs = sorted([
        p for p in ind_dir.iterdir()
        if p.is_dir() and (
            (p / ARQUIVO_ANUAL).exists() or
            (p / ARQUIVO_TRIMESTRAL).exists()
        )
    ])

    if not empresas_dirs:
        log.error("Nenhuma subpasta com parquets em %s", ind_dir)
        return

    log.info("Empresas encontradas: %d", len(empresas_dirs))
    for d in empresas_dirs:
        log.info("  · %s", d.name)

    erros: list[str] = []
    total_fatos = 0
    periodos_cache: dict = {}
    batch_size = BATCH_SIZE

    with psycopg.connect(get_database_url(), autocommit=False) as conn:
        with conn.cursor() as cur:
            etl_id = iniciar_execucao(cur, str(ind_dir))
        conn.commit()
        log.info("ETL execução iniciada → id=%d", etl_id)

        todos_codigos: set[str] = set()
        for emp_dir in empresas_dirs:
            for arquivo in [ARQUIVO_ANUAL, ARQUIVO_TRIMESTRAL]:
                p = emp_dir / arquivo
                if p.exists():
                    cols = pd.read_parquet(p, columns=None).columns.tolist()
                    todos_codigos.update(c for c in cols if c not in NON_INDICATOR_COLS)

        with conn.cursor() as cur:
            indicador_map = ensure_indicadores(cur, list(todos_codigos))
        conn.commit()
        log.info("Catálogo: %d indicadores.", len(indicador_map))

        for emp_dir in empresas_dirs:
            empresa_nome = emp_dir.name
            log.info("──── %s", empresa_nome)

            with conn.cursor() as cur:
                empresa_id = upsert_empresa(cur, empresa_nome)
            conn.commit()

            p_anual = emp_dir / ARQUIVO_ANUAL
            if p_anual.exists():
                t0 = time.time()
                try:
                    nf = carregar_parquet(
                        p_anual, "A", empresa_id,
                        conn, etl_id, indicador_map, periodos_cache, batch_size,
                    )
                    total_fatos += nf
                    log.info("  [A] %d fatos (%.1fs)", nf, time.time() - t0)
                except Exception as exc:
                    conn.rollback()
                    log.exception("  [A] ERRO: %s", exc)
                    erros.append(f"{p_anual}: {exc}")
            else:
                log.warning("  [A] %s ausente.", ARQUIVO_ANUAL)

            p_tri = emp_dir / ARQUIVO_TRIMESTRAL
            if p_tri.exists():
                t0 = time.time()
                try:
                    nf = carregar_parquet(
                        p_tri, "T", empresa_id,
                        conn, etl_id, indicador_map, periodos_cache, batch_size,
                    )
                    total_fatos += nf
                    log.info("  [T] %d fatos (%.1fs)", nf, time.time() - t0)
                except Exception as exc:
                    conn.rollback()
                    log.exception("  [T] ERRO: %s", exc)
                    erros.append(f"{p_tri}: {exc}")
            else:
                log.warning("  [T] %s ausente.", ARQUIVO_TRIMESTRAL)

        status = "SUCCESS" if not erros else ("PARTIAL" if total_fatos > 0 else "FAILED")
        obs = "; ".join(erros) if erros else None
        with conn.cursor() as cur:
            finalizar_execucao(
                cur, etl_id, status,
                len(empresas_dirs), len(periodos_cache), total_fatos, obs,
            )
        conn.commit()

    log.info("ETL concluído status=%s empresas=%d periodos=%d fatos=%d",
             status, len(empresas_dirs), len(periodos_cache), total_fatos)
    if erros:
        for e in erros:
            log.warning("erro: %s", e)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL indicadores fundamentalistas para PostgreSQL.")
    p.add_argument("--base-dir", type=str, default=".", help="Raiz do projeto.")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()
    run_etl(Path(args.base_dir).resolve())


if __name__ == "__main__":
    main()
