"""
Pipeline: Valuation — Graham Number e Preço Teto Bazin
=======================================================
Calcula e persiste, por empresa × período trimestral:

  val_lpa          — Lucro Por Ação TTM (R$)          = preço / P/L TTM
  val_vpa          — Valor Patrimonial Por Ação (R$)   = preço / P/VP
  val_dpa_ttm      — Dividendos Por Ação TTM (R$)      = DY × preço
  val_graham       — Graham Number (R$)                = √(22,5 × LPA × VPA)
  val_margem_graham  — Margem vs Graham                = (Graham − Preço) / Preço
  val_bazin_6      — Preço teto Bazin DY 6% (R$)       = DPA / 0,06
  val_bazin_10     — Preço teto Bazin DY 10% (R$)      = DPA / 0,10
  val_margem_bazin_6  — Margem vs Bazin 6%             = (Bazin6 − Preço) / Preço
  val_margem_bazin_10 — Margem vs Bazin 10%            = (Bazin10 − Preço) / Preço
  val_status       — Status: +1 subavaliado, 0 justo, -1 sobrevalorizado

Fontes dos dados (todas já em fato_indicadores):
  mkt_preco_fechamento   → preço de referência do período
  mkt_pl_ttm             → P/L TTM (LPA = preço / PL)
  mkt_pvp                → P/VP    (VPA = preço / PVP)
  mkt_dividend_yield_ttm → DY TTM  (DPA = DY × preço)

Critérios de status (composto Graham + Bazin):
  subavaliado     : margem_graham > 20% E preço < bazin_6
  sobrevalorizado : margem_graham < -20% E preço > bazin_6
  justo           : demais casos (ou falta de dados)

Sem look-ahead bias: usa apenas indicadores calculados na mesma data de referência.
"""

from __future__ import annotations

import argparse
import logging
import math
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from pipeline.config import get_database_url

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

GRAHAM_MULTIPLIER   = 22.5
BAZIN_DY_CLASSICO   = 0.06
BAZIN_DY_CONSERVADOR = 0.10

# Thresholds para sinalização de status
MARGEM_SUBAVALIADO   = 0.20   # +20% acima do preço → subavaliado
MARGEM_SOBREVALORIZADO = -0.20  # −20% abaixo do preço → sobrevalorizado

# ─────────────────────────────────────────────────────────────────────────────
# SQL
# ─────────────────────────────────────────────────────────────────────────────

_SQL_INSUMOS = """
-- Carrega indicadores MKT por empresa × período para computar valuation
SELECT
    f.empresa_id,
    f.periodo_id,
    MAX(CASE WHEN i.codigo = 'mkt_preco_fechamento'    THEN f.valor END) AS preco,
    MAX(CASE WHEN i.codigo = 'mkt_pl_ttm'              THEN f.valor END) AS pl_ttm,
    MAX(CASE WHEN i.codigo = 'mkt_pvp'                 THEN f.valor END) AS pvp,
    MAX(CASE WHEN i.codigo = 'mkt_dividend_yield_ttm'  THEN f.valor END) AS dy_ttm
FROM track_stocks.fato_indicadores f
JOIN track_stocks.indicadores i USING (indicador_id)
WHERE i.codigo IN (
    'mkt_preco_fechamento',
    'mkt_pl_ttm',
    'mkt_pvp',
    'mkt_dividend_yield_ttm'
)
GROUP BY f.empresa_id, f.periodo_id
HAVING
    MAX(CASE WHEN i.codigo = 'mkt_preco_fechamento' THEN f.valor END) IS NOT NULL
    AND MAX(CASE WHEN i.codigo = 'mkt_preco_fechamento' THEN f.valor END) > 0
ORDER BY f.empresa_id, f.periodo_id
"""

_SQL_INDICADOR_IDS = """
SELECT codigo, indicador_id
FROM track_stocks.indicadores
WHERE codigo = ANY(%(codes)s)
"""

_SQL_UPSERT = """
INSERT INTO track_stocks.fato_indicadores (empresa_id, periodo_id, indicador_id, valor)
VALUES (%(empresa_id)s, %(periodo_id)s, %(indicador_id)s, %(valor)s)
ON CONFLICT (empresa_id, periodo_id, indicador_id)
DO UPDATE SET valor = EXCLUDED.valor
"""

_SQL_DONE_EMPRESAS = """
SELECT empresa_id
FROM track_stocks.fato_indicadores fi
JOIN track_stocks.indicadores i USING (indicador_id)
WHERE i.codigo = 'val_graham'
GROUP BY empresa_id
HAVING COUNT(*) >= 50
"""


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de valuation para um único (empresa_id, periodo_id)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_row(
    preco: float,
    pl_ttm: Optional[float],
    pvp:    Optional[float],
    dy_ttm: Optional[float],
) -> dict[str, Optional[float]]:
    """
    Retorna dict {codigo_val: valor | None} para uma linha de insumos.
    None = valor não computável (falta de dado ou resultado inválido).
    """
    result: dict[str, Optional[float]] = {}

    # ── LPA, VPA, DPA ────────────────────────────────────────────────────────
    lpa: Optional[float] = None
    vpa: Optional[float] = None
    dpa: Optional[float] = None

    if pl_ttm and pl_ttm > 0:
        lpa = preco / pl_ttm
        result["val_lpa"] = round(lpa, 6)

    if pvp and pvp > 0:
        vpa = preco / pvp
        result["val_vpa"] = round(vpa, 6)

    if dy_ttm is not None and dy_ttm >= 0:
        dpa = dy_ttm * preco
        result["val_dpa_ttm"] = round(dpa, 6)

    # ── Graham Number ─────────────────────────────────────────────────────────
    # Válido apenas quando LPA > 0 E VPA > 0 (empresa lucrativa e solvente).
    # Filtro de sanidade: descarta casos onde LPA ou VPA > 50× o preço,
    # que indicam distorção por capital muito concentrado (ex.: ultra-low float).
    graham: Optional[float] = None
    if (
        lpa and vpa
        and lpa > 0 and vpa > 0
        and lpa <= 50 * preco      # LPA não pode ser maior que 50× preço
        and vpa <= 200 * preco     # VPA não pode ser maior que 200× preço
    ):
        graham = math.sqrt(GRAHAM_MULTIPLIER * lpa * vpa)
        result["val_graham"] = round(graham, 4)
        result["val_margem_graham"] = round((graham - preco) / preco, 6)

    # ── Bazin ────────────────────────────────────────────────────────────────
    # Válido apenas quando há dividendos positivos
    if dpa and dpa > 0:
        bazin_6  = dpa / BAZIN_DY_CLASSICO
        bazin_10 = dpa / BAZIN_DY_CONSERVADOR
        result["val_bazin_6"]  = round(bazin_6,  4)
        result["val_bazin_10"] = round(bazin_10, 4)
        result["val_margem_bazin_6"]  = round((bazin_6  - preco) / preco, 6)
        result["val_margem_bazin_10"] = round((bazin_10 - preco) / preco, 6)

    # ── Status composto ───────────────────────────────────────────────────────
    # Combina sinal Graham E Bazin para produzir sinalização robusta.
    # Requer ambos para emitir +1 ou -1; caso contrário usa apenas Graham.
    margem_g = result.get("val_margem_graham")
    bazin6   = result.get("val_bazin_6")

    if margem_g is not None:
        if bazin6 is not None:
            if margem_g > MARGEM_SUBAVALIADO and preco < bazin6:
                result["val_status"] = 1.0     # subavaliado pelos dois critérios
            elif margem_g < MARGEM_SOBREVALORIZADO and preco > bazin6:
                result["val_status"] = -1.0    # sobrevalorizado pelos dois
            elif margem_g > MARGEM_SUBAVALIADO or preco < bazin6:
                result["val_status"] = 0.5     # subavaliado por apenas um critério
            elif margem_g < MARGEM_SOBREVALORIZADO or preco > bazin6:
                result["val_status"] = -0.5    # sobrevalorizado por apenas um
            else:
                result["val_status"] = 0.0     # zona de justo por ambos
        else:
            # Sem Bazin (empresa sem dividendos): usa só Graham
            if margem_g > MARGEM_SUBAVALIADO:
                result["val_status"] = 0.5
            elif margem_g < MARGEM_SOBREVALORIZADO:
                result["val_status"] = -0.5
            else:
                result["val_status"] = 0.0

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    full: bool = False,
    tickers_filter: Optional[list[str]] = None,
    batch_size: int = 500,
) -> None:
    conn = psycopg.connect(get_database_url(), row_factory=dict_row)
    try:
        # 1. Aplicar DDL de enum e sincronizar catálogo
        _ensure_catalog(conn)

        # 2. Carregar IDs dos indicadores VAL
        from sql.catalog import VALUATION_CODES
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_SQL_INDICADOR_IDS, {"codes": VALUATION_CODES})
            ind_ids = {r["codigo"]: r["indicador_id"] for r in cur.fetchall()}

        missing = [c for c in VALUATION_CODES if c not in ind_ids]
        if missing:
            log.error("Códigos não encontrados no catálogo: %s. Rode schema.py --sync.", missing)
            return

        # 3. Empresas já calculadas (incremental)
        done_ids: set[int] = set()
        if not full:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(_SQL_DONE_EMPRESAS)
                done_ids = {r["empresa_id"] for r in cur.fetchall()}
            log.info("Empresas já calculadas (skip): %d", len(done_ids))

        # 4. Filtro por ticker
        empresa_filter_sql = ""
        params: dict = {}
        if tickers_filter:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT empresa_id FROM track_stocks.empresas WHERE ticker = ANY(%s)",
                    (tickers_filter,),
                )
                filter_ids = [r["empresa_id"] for r in cur.fetchall()]
            if not filter_ids:
                log.warning("Nenhum empresa_id para tickers: %s", tickers_filter)
                return
            empresa_filter_sql = f" AND f.empresa_id = ANY(ARRAY{filter_ids})"

        # 5. Carregar insumos
        log.info("Carregando insumos MKT do banco...")
        sql_insumos = _SQL_INSUMOS
        if empresa_filter_sql:
            sql_insumos = sql_insumos.replace(
                "ORDER BY f.empresa_id", empresa_filter_sql + "\nORDER BY f.empresa_id"
            )
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql_insumos)
            rows = cur.fetchall()

        log.info("Linhas de insumos carregadas: %d", len(rows))

        # 6. Calcular e persistir em lotes
        total_rows = 0
        batch: list[dict] = []

        def _flush(b: list[dict]) -> int:
            if not b:
                return 0
            with conn.cursor() as cur:
                cur.executemany(_SQL_UPSERT, b)
            conn.commit()
            return len(b)

        for row in rows:
            empresa_id = row["empresa_id"]
            periodo_id = row["periodo_id"]

            if not full and empresa_id in done_ids:
                continue

            preco  = float(row["preco"])  if row["preco"]  else None
            pl_ttm = float(row["pl_ttm"]) if row["pl_ttm"] else None
            pvp    = float(row["pvp"])    if row["pvp"]    else None
            dy_ttm = float(row["dy_ttm"]) if row["dy_ttm"] is not None else None

            if not preco or preco <= 0:
                continue

            computed = _compute_row(preco, pl_ttm, pvp, dy_ttm)

            for codigo, valor in computed.items():
                if valor is None or (isinstance(valor, float) and not math.isfinite(valor)):
                    continue
                ind_id = ind_ids.get(codigo)
                if ind_id is None:
                    continue
                batch.append({
                    "empresa_id":   empresa_id,
                    "periodo_id":   periodo_id,
                    "indicador_id": ind_id,
                    "valor":        valor,
                })

            if len(batch) >= batch_size:
                total_rows += _flush(batch)
                batch = []
                log.debug("Flushed batch — total até agora: %d", total_rows)

        total_rows += _flush(batch)
        log.info("Valuation concluído. Total de registros: %d", total_rows)

    finally:
        conn.close()


def _ensure_catalog(conn: psycopg.Connection) -> None:
    """Sincroniza enum VAL e catálogo sem re-aplicar todo o schema."""
    # Enum precisa de autocommit separado
    from sql.schema import DDL_ENUM_MIGRATION
    with psycopg.connect(get_database_url(), autocommit=True) as aconn:
        with aconn.cursor() as cur:
            cur.execute(DDL_ENUM_MIGRATION)

    from sql.catalog import build_indicator_rows
    rows = build_indicator_rows()
    with conn.cursor() as cur:
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
            ON CONFLICT (codigo) DO UPDATE
            SET nome = EXCLUDED.nome, bloco = EXCLUDED.bloco,
                camada = EXCLUDED.camada, unidade = EXCLUDED.unidade;
            """,
            rows,
        )
    conn.commit()
    log.info("Catálogo sincronizado.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL de valuation: Graham Number e Bazin.")
    p.add_argument("--full", action="store_true",
                   help="Recalcular tudo (ignora cache incremental).")
    p.add_argument("--tickers", nargs="*",
                   help="Limitar a uma lista de tickers.")
    p.add_argument("--batch-size", type=int, default=2000)
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()
    run_pipeline(
        full=args.full,
        tickers_filter=[t.upper() for t in args.tickers] if args.tickers else None,
        batch_size=args.batch_size,
    )
