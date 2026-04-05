"""
ETL: ingestão de BP, DRE e DFC da CVM para o PostgreSQL.

Estrutura de entrada:
    data/processed/dem_acoes/
        <RAZAO_SOCIAL>/
            bpa_YYYY.parquet   ← Balanço Patrimonial (Ativo + Passivo via GRUPO_DFP)
            dre_YYYY.parquet   ← Demonstração do Resultado do Exercício
            dfc_YYYY.parquet   ← Demonstração dos Fluxos de Caixa

Cada arquivo pode conter múltiplos períodos (trimestres do ano fiscal).
Cada linha representa uma conta (CD_CONTA) em um período (DT_FIM_EXERC).

Estratégia:
    1. Para cada empresa, para cada arquivo:
       a. Lê o parquet
       b. Normaliza colunas e tipos
       c. Resolve empresa_id por CNPJ_CIA (upsert se necessário)
       d. Para cada DT_FIM_EXERC único → resolve periodo_id (upsert se necessário)
       e. Flush em batch para fato_demonstrativos com ON CONFLICT DO UPDATE

    2. Registra execução ETL (etl_execucoes) com contagens e status.

Idempotente: re-executar não duplica dados.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import psycopg

from pipeline.config import get_database_url
from sql.repos.demonstrativos import (
    TIPO_DEMO_MAP,
    build_demo_rows,
    flush_demo_batch,
    normalize_demo_df,
    resolve_empresa_id,
    resolve_periodo_id,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 2_000
DEM_ACOES_SUBDIR = Path("data") / "processed" / "dem_acoes"


# ── Stats ─────────────────────────────────────────────────────────────────────

@dataclass
class DemoStats:
    empresas_processadas: int = 0
    empresas_com_erro: int = 0
    arquivos_processados: int = 0
    arquivos_com_erro: int = 0
    periodos_criados: int = 0
    linhas_totais: int = 0
    linhas_inseridas: int = 0
    erros: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"empresas={self.empresas_processadas} (erros={self.empresas_com_erro}) | "
            f"arquivos={self.arquivos_processados} (erros={self.arquivos_com_erro}) | "
            f"linhas={self.linhas_inseridas:,} | erros_detalhe={len(self.erros)}"
        )


# ── ETL principal ─────────────────────────────────────────────────────────────

def persist_demonstrativos(
    base_dir: Path | None = None,
    empresa_filter: str | None = None,
    dry_run: bool = False,
    batch_size: int = BATCH_SIZE,
) -> DemoStats:
    """
    Percorre data/processed/dem_acoes/ e persiste todos os demonstrativos.

    Args:
        base_dir:       raiz do projeto (padrão: cwd)
        empresa_filter: se informado, processa apenas empresas cujo nome contiver este substring
        dry_run:        valida sem persistir
    """
    root = (Path(base_dir).resolve() if base_dir else Path(".").resolve())
    dem_dir = root / DEM_ACOES_SUBDIR

    if not dem_dir.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {dem_dir}")

    stats = DemoStats()
    t0 = time.perf_counter()
    dsn = get_database_url()

    # Registra execução ETL
    etl_id = _start_etl(dsn)

    empresa_dirs = sorted(d for d in dem_dir.iterdir() if d.is_dir())
    if empresa_filter:
        empresa_dirs = [d for d in empresa_dirs if empresa_filter.lower() in d.name.lower()]

    logger.info("Iniciando ETL: %d empresas | dry_run=%s", len(empresa_dirs), dry_run)

    with psycopg.connect(dsn, autocommit=False) as conn:
        empresa_cache: dict[str, int] = {}
        periodo_cache: dict[object, int] = {}

        for empresa_dir in empresa_dirs:
            try:
                _process_empresa(
                    conn=conn,
                    dsn=dsn,
                    empresa_dir=empresa_dir,
                    etl_id=etl_id,
                    stats=stats,
                    empresa_cache=empresa_cache,
                    periodo_cache=periodo_cache,
                    dry_run=dry_run,
                    batch_size=batch_size,
                )
                stats.empresas_processadas += 1
            except Exception as exc:
                stats.empresas_com_erro += 1
                msg = f"[EMPRESA] {empresa_dir.name}: {exc}"
                stats.erros.append(msg)
                logger.error(msg)
                conn.rollback()

    elapsed = time.perf_counter() - t0
    _finish_etl(dsn, etl_id, stats)
    logger.info("ETL concluído em %.1fs | %s", elapsed, stats)
    return stats


def _process_empresa(
    conn: psycopg.Connection,
    dsn: str,
    empresa_dir: Path,
    etl_id: int | None,
    stats: DemoStats,
    empresa_cache: dict,
    periodo_cache: dict,
    dry_run: bool,
    batch_size: int,
) -> None:
    demo_files = _discover_files(empresa_dir)
    if not demo_files:
        logger.debug("Sem arquivos em %s — pulando.", empresa_dir.name)
        return

    for filepath, tipo_demo in demo_files:
        try:
            _process_file(
                conn=conn,
                dsn=dsn,
                filepath=filepath,
                tipo_demo=tipo_demo,
                etl_id=etl_id,
                stats=stats,
                empresa_cache=empresa_cache,
                periodo_cache=periodo_cache,
                dry_run=dry_run,
                batch_size=batch_size,
            )
        except Exception as exc:
            stats.arquivos_com_erro += 1
            msg = f"[ARQUIVO] {filepath.name} ({empresa_dir.name}): {exc}"
            stats.erros.append(msg)
            logger.warning(msg)
            conn.rollback()


def _process_file(
    conn: psycopg.Connection,
    dsn: str,
    filepath: Path,
    tipo_demo: str,
    etl_id: int | None,
    stats: DemoStats,
    empresa_cache: dict,
    periodo_cache: dict,
    dry_run: bool,
    batch_size: int,
) -> None:
    # 1. Lê e normaliza
    raw = pd.read_parquet(filepath)
    df = normalize_demo_df(raw)
    stats.linhas_totais += len(df)

    if df.empty:
        logger.debug("Arquivo vazio após normalização: %s", filepath.name)
        return

    # 2. Meta da empresa (única por arquivo) — autocommit independente
    cnpj_raw = df["CNPJ_CIA"].iloc[0]
    razao_social = df["DENOM_CIA"].iloc[0] if "DENOM_CIA" in df.columns else filepath.parent.name
    cd_cvm = df["CD_CVM"].iloc[0] if "CD_CVM" in df.columns else None

    empresa_id = resolve_empresa_id(dsn, cnpj_raw, razao_social, cd_cvm, empresa_cache)

    with conn.cursor() as cur:
        # 3. Agrupa por DT_FIM_EXERC e processa cada período
        for dt_fim, grp in df.groupby("DT_FIM_EXERC", sort=True):
            periodo_id, dt_ref = resolve_periodo_id(cur, dt_fim, periodo_cache)

            if dry_run:
                stats.linhas_inseridas += len(grp)
                continue

            rows = build_demo_rows(grp, tipo_demo, empresa_id, periodo_id, dt_fim, etl_id)

            for start in range(0, len(rows), batch_size):
                flush_demo_batch(cur, rows[start : start + batch_size])

            stats.linhas_inseridas += len(rows)

        conn.commit()

    stats.arquivos_processados += 1


def _discover_files(empresa_dir: Path) -> list[tuple[Path, str]]:
    """Retorna lista de (filepath, tipo_demo) para todos os parquets válidos."""
    result = []
    for f in sorted(empresa_dir.iterdir()):
        if f.suffix != ".parquet":
            continue
        prefix = f.stem.split("_")[0].lower()
        tipo = TIPO_DEMO_MAP.get(prefix)
        if tipo is None:
            logger.debug("Arquivo ignorado (prefixo desconhecido): %s", f.name)
            continue
        result.append((f, tipo))
    return result


# ── ETL execução audit ────────────────────────────────────────────────────────

def _start_etl(dsn: str) -> int | None:
    try:
        with psycopg.connect(dsn, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO track_stocks.etl_execucoes
                        (pipeline_nome, versao_pipeline, origem_dados, status)
                    VALUES ('demonstrativos_b3', '1.0', 'dem_acoes/', 'STARTED')
                    RETURNING etl_execucao_id
                """)
                eid = cur.fetchone()[0]
            conn.commit()
        return eid
    except Exception as exc:
        logger.warning("Não foi possível registrar etl_execucao: %s", exc)
        return None


def _finish_etl(dsn: str, etl_id: int | None, stats: DemoStats) -> None:
    if etl_id is None:
        return
    status = "SUCCESS" if stats.empresas_com_erro == 0 else "PARTIAL"
    try:
        with psycopg.connect(dsn, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE track_stocks.etl_execucoes SET
                        finalizado_em        = now(),
                        status               = %s,
                        total_empresas       = %s,
                        total_registros_fato = %s,
                        observacao           = %s
                    WHERE etl_execucao_id = %s
                """, (
                    status,
                    stats.empresas_processadas,
                    stats.linhas_inseridas,
                    f"{stats.arquivos_com_erro} arquivos com erro." if stats.arquivos_com_erro else None,
                    etl_id,
                ))
            conn.commit()
    except Exception as exc:
        logger.warning("Não foi possível atualizar etl_execucao %s: %s", etl_id, exc)


# ── Entrada via script ────────────────────────────────────────────────────────

def run(
    base_dir: Path | None = None,
    empresa_filter: str | None = None,
    dry_run: bool = False,
) -> DemoStats:
    return persist_demonstrativos(base_dir, empresa_filter, dry_run)
