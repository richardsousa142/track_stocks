"""
Pipeline: FII DY Anual — Dividend Yield rolling 12 meses
=========================================================

Deriva o DY anual de cada FII a partir da série mensal já persistida
(fii_dy_mes), usando uma janela rolling de 12 meses.

Metodologia
-----------
  fii_dy_anual[t] = Σ fii_dy_mes[t-11 : t]

Requisitos para calcular:
  • Exatamente 12 meses consecutivos com dados válidos na janela.
  • Cada mês deve ter DY mensal no intervalo [0, MAX_DY_MES] (filtro anti-outlier).
  • O resultado anual deve estar em (0, MAX_DY_ANUAL].

Sem look-ahead bias: o DY anual do período T usa apenas meses ≤ T.

Granularidade
-------------
  freq = 'M'  (mesmo nível do fii_dy_mes — um ponto por mês por fundo)

Notas sobre qualidade dos dados
---------------------------------
  • Alguns fii_dy_mes têm valores absurdamente altos (>10% ao mês) por
    erros de ingestão do parquet CVM. O filtro MAX_DY_MES remove esses outliers
    antes da soma, garantindo resultados auditáveis.
  • O threshold conservador de 10% mensal é generoso para FIIs brasileiros
    (fundos com DY > 10% ao mês são sistematicamente suspeitos).
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from pipeline.config import get_database_url

log = logging.getLogger(__name__)

# ── Thresholds auditáveis ──────────────────────────────────────────────────

MAX_DY_MES    = 0.10   # 10% ao mês — acima disso é outlier
MAX_DY_ANUAL  = 1.50   # 150% ao ano — acima disso é erro de ingestão
ROLLING_WINDOW = 12    # meses

# ── SQL ───────────────────────────────────────────────────────────────────

SQL_FETCH_MENSAL = """
SELECT
    f.empresa_id,
    p.periodo_id,
    p.dt_referencia,
    f.valor           AS dy_mes
FROM track_stocks.fato_indicadores f
JOIN track_stocks.periodos    p ON p.periodo_id   = f.periodo_id
JOIN track_stocks.indicadores i ON i.indicador_id = f.indicador_id
WHERE i.codigo = 'fii_dy_mes'
  AND p.freq   = 'M'
  AND f.valor  IS NOT NULL
ORDER BY f.empresa_id, p.dt_referencia
"""

SQL_GET_INDICADOR_ID = """
SELECT indicador_id
FROM track_stocks.indicadores
WHERE codigo = 'fii_dy_anual'
"""

SQL_UPSERT = """
INSERT INTO track_stocks.fato_indicadores
    (empresa_id, periodo_id, indicador_id, valor, calculado_em)
VALUES
    (%s, %s, %s, %s, now())
ON CONFLICT (empresa_id, periodo_id, indicador_id)
    DO UPDATE SET valor = EXCLUDED.valor, calculado_em = now()
"""


# ── Cálculo ───────────────────────────────────────────────────────────────

def compute_dy_anual(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe DataFrame com colunas [empresa_id, periodo_id, dt_referencia, dy_mes].
    Retorna DataFrame com [empresa_id, periodo_id, dy_anual] para os períodos
    em que há exatamente 12 meses válidos na janela rolling.
    """
    # 1. Filtrar outliers mensais
    before = len(df)
    df = df[(df["dy_mes"] >= 0) & (df["dy_mes"] <= MAX_DY_MES)].copy()
    n_outliers = before - len(df)
    if n_outliers:
        log.info("Descartados %d registros com dy_mes > %.0f%% (outliers)", n_outliers, MAX_DY_MES * 100)

    # 2. Reindexar em calendário mensal regular por empresa
    #    para garantir que meses faltantes sejam tratados como NaN
    df["dt_referencia"] = pd.to_datetime(df["dt_referencia"])
    df["ym"] = df["dt_referencia"].dt.to_period("M")

    # Pivot: empresa_id × mês → dy_mes
    pivot = (
        df.pivot_table(index="ym", columns="empresa_id", values="dy_mes", aggfunc="last")
        .sort_index()
    )

    # 3. Rolling 12 meses — soma exata (min_periods=12 descarta janelas incompletas)
    dy_anual = pivot.rolling(window=ROLLING_WINDOW, min_periods=ROLLING_WINDOW).sum()

    # 4. Filtrar resultado
    dy_anual = dy_anual[(dy_anual > 0) & (dy_anual <= MAX_DY_ANUAL)]

    # 5. Reconstruir tabela longa
    dy_long = (
        dy_anual.stack(future_stack=True)
        .reset_index()
        .rename(columns={"ym": "ym", "empresa_id": "empresa_id", 0: "dy_anual"})
    )

    # 6. Recuperar periodo_id da última observação de cada mês por empresa
    periodo_map = (
        df.groupby(["empresa_id", "ym"])["periodo_id"]
        .last()
        .reset_index()
    )
    result = dy_long.merge(periodo_map, on=["empresa_id", "ym"], how="left")
    result = result.dropna(subset=["periodo_id", "dy_anual"])

    return result[["empresa_id", "periodo_id", "dy_anual"]]


# ── Pipeline ──────────────────────────────────────────────────────────────

def run(full: bool = False) -> None:
    dsn = get_database_url()

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # Indicador ID
            cur.execute(SQL_GET_INDICADOR_ID)
            row = cur.fetchone()
            if not row:
                raise RuntimeError("fii_dy_anual não encontrado no catálogo. Execute schema.py primeiro.")
            indicador_id = row["indicador_id"]
            log.info("indicador_id para fii_dy_anual: %d", indicador_id)

            # Lê todos os DYs mensais
            log.info("Lendo fii_dy_mes do banco...")
            cur.execute(SQL_FETCH_MENSAL)
            rows = cur.fetchall()

    if not rows:
        log.warning("Nenhum registro de fii_dy_mes encontrado.")
        return

    df = pd.DataFrame(rows)
    log.info("Total de registros fii_dy_mes: %d / %d fundos", len(df), df["empresa_id"].nunique())

    # Calcula DY anual
    result = compute_dy_anual(df)
    log.info("DY anual calculado: %d registros / %d fundos", len(result), result["empresa_id"].nunique())

    if result.empty:
        log.warning("Nenhum DY anual calculado.")
        return

    # Persiste
    records = [
        (int(r["empresa_id"]), int(r["periodo_id"]), indicador_id, float(r["dy_anual"]))
        for _, r in result.iterrows()
    ]

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.executemany(SQL_UPSERT, records)
        conn.commit()

    log.info("Upsert concluído: %d registros de fii_dy_anual persistidos.", len(records))

    # Validação final
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(DISTINCT empresa_id) AS fundos,
                       COUNT(*)                   AS registros,
                       ROUND(AVG(valor)::numeric, 4) AS media_dy_anual,
                       ROUND(MIN(valor)::numeric, 4) AS min_dy,
                       ROUND(MAX(valor)::numeric, 4) AS max_dy
                FROM track_stocks.fato_indicadores f
                JOIN track_stocks.indicadores i USING (indicador_id)
                WHERE i.codigo = 'fii_dy_anual'
            """)
            v = cur.fetchone()
            log.info(
                "Validação: %d fundos, %d períodos | DY anual médio=%.2f%% min=%.2f%% max=%.2f%%",
                v["fundos"], v["registros"],
                float(v["media_dy_anual"]) * 100,
                float(v["min_dy"]) * 100,
                float(v["max_dy"]) * 100,
            )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Calcula e persiste fii_dy_anual")
    parser.add_argument("--full", action="store_true", help="Re-processa tudo (padrão: incremental)")
    args = parser.parse_args()
    run(full=args.full)
