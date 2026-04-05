"""
Endpoints de valuation: Graham Number, Bazin, margens de segurança.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ..services.db import get_cursor

router = APIRouter(prefix="/api/valuation", tags=["valuation"])


# ─────────────────────────────────────────────────────────────────────────────
# Schema de resposta
# ─────────────────────────────────────────────────────────────────────────────

class ValuationItem(BaseModel):
    ticker: str
    razao_social: Optional[str] = None
    setor: Optional[str] = None
    ano: Optional[int] = None
    trimestre: Optional[int] = None
    dt_referencia: Optional[str] = None

    preco: Optional[float] = None

    # Por ação
    lpa: Optional[float] = None
    vpa: Optional[float] = None
    dpa_ttm: Optional[float] = None

    # Graham
    valor_justo_graham: Optional[float] = None
    margem_graham_pct: Optional[float] = None

    # Bazin
    preco_teto_bazin_6: Optional[float] = None
    preco_teto_bazin_10: Optional[float] = None
    margem_bazin_6_pct: Optional[float] = None
    margem_bazin_10_pct: Optional[float] = None

    # Status
    status_graham_bazin: Optional[str] = None
    status_simples: Optional[str] = None

    # Contexto
    pl_ttm: Optional[float] = None
    pvp: Optional[float] = None
    dy_ttm_pct: Optional[float] = None
    market_cap_bilhoes: Optional[float] = None
    ev_ebitda: Optional[float] = None
    dl_ebitda: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_SELECT_ALL = """
    SELECT
        ticker, razao_social, setor,
        ano, trimestre, dt_referencia::text AS dt_referencia,
        preco, lpa, vpa, dpa_ttm,
        valor_justo_graham, margem_graham_pct,
        preco_teto_bazin_6, preco_teto_bazin_10,
        margem_bazin_6_pct, margem_bazin_10_pct,
        status_graham_bazin, status_simples,
        pl_ttm, pvp, dy_ttm_pct, market_cap_bilhoes, ev_ebitda, dl_ebitda
    FROM track_stocks.vw_valuation
"""


def _row_to_item(r: dict) -> ValuationItem:
    def _f(v) -> Optional[float]:
        return float(v) if v is not None else None

    return ValuationItem(
        ticker=r["ticker"],
        razao_social=r.get("razao_social") or r.get("empresa"),
        setor=r.get("setor"),
        ano=r.get("ano"),
        trimestre=r.get("trimestre"),
        dt_referencia=r.get("dt_referencia"),
        preco=_f(r.get("preco")),
        lpa=_f(r.get("lpa")),
        vpa=_f(r.get("vpa")),
        dpa_ttm=_f(r.get("dpa_ttm")),
        valor_justo_graham=_f(r.get("valor_justo_graham")),
        margem_graham_pct=_f(r.get("margem_graham_pct")),
        preco_teto_bazin_6=_f(r.get("preco_teto_bazin_6")),
        preco_teto_bazin_10=_f(r.get("preco_teto_bazin_10")),
        margem_bazin_6_pct=_f(r.get("margem_bazin_6_pct")),
        margem_bazin_10_pct=_f(r.get("margem_bazin_10_pct")),
        status_graham_bazin=r.get("status_graham_bazin"),
        status_simples=r.get("status_simples"),
        pl_ttm=_f(r.get("pl_ttm")),
        pvp=_f(r.get("pvp")),
        dy_ttm_pct=_f(r.get("dy_ttm_pct")),
        market_cap_bilhoes=_f(r.get("market_cap_bilhoes")),
        ev_ebitda=_f(r.get("ev_ebitda")),
        dl_ebitda=_f(r.get("dl_ebitda")),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ValuationItem], summary="Lista de valuation (todos os ativos)")
def listar_valuation(
    status: Optional[str] = Query(
        None,
        description="Filtrar por status: abaixo_do_valor_justo | proximo_do_valor_justo | acima_do_valor_justo",
    ),
    setor: Optional[str] = Query(None, description="Filtrar por setor"),
    min_graham_margem: Optional[float] = Query(None, description="Margem Graham mínima (ex.: 20 para +20%)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Retorna o valuation mais recente de todos os ativos, com Graham Number,
    preço teto Bazin (6% e 10%) e status de subavaliação.
    Ordenado por margem de segurança Graham decrescente.
    """
    conditions: list[str] = []
    params: list = []

    if status:
        conditions.append("status_simples = %s")
        params.append(status)
    if setor:
        conditions.append("setor ILIKE %s")
        params.append(f"%{setor}%")
    if min_graham_margem is not None:
        conditions.append("margem_graham_pct >= %s")
        params.append(min_graham_margem)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        {_SELECT_ALL}
        {where}
        ORDER BY margem_graham_pct DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    params += [limit, offset]

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [_row_to_item(r) for r in rows]


@router.get(
    "/ranking",
    response_model=list[ValuationItem],
    summary="Top ativos por margem de segurança Graham",
)
def ranking_valuation(
    limit: int = Query(20, ge=1, le=100),
    apenas_subavaliados: bool = Query(True, description="Filtrar apenas status abaixo_do_valor_justo"),
    min_dpa: Optional[float] = Query(None, description="DPA mínimo (ex.: 0.50 para R$0.50/ação)"),
):
    """
    Ranking de ativos com maior margem de segurança (Graham Number acima do preço).
    Ideal para triagem de stock picking fundamentalista.
    """
    conditions = ["valor_justo_graham IS NOT NULL", "preco IS NOT NULL", "preco > 0"]
    params: list = []

    if apenas_subavaliados:
        conditions.append("margem_graham_pct > 0")
    if min_dpa is not None:
        conditions.append("dpa_ttm >= %s")
        params.append(min_dpa)

    sql = f"""
        {_SELECT_ALL}
        WHERE {' AND '.join(conditions)}
        ORDER BY margem_graham_pct DESC NULLS LAST
        LIMIT %s OFFSET 0
    """
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [_row_to_item(r) for r in rows]


@router.get(
    "/{ticker}",
    response_model=ValuationItem,
    summary="Valuation de um ativo específico",
)
def valuation_ticker(ticker: str):
    """
    Retorna o valuation mais recente do ativo: Graham Number, Bazin,
    margens de segurança e status.
    """
    with get_cursor() as cur:
        cur.execute(
            _SELECT_ALL + " WHERE ticker = %s",
            (ticker.upper(),),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' não encontrado ou sem valuation calculado.")

    return _row_to_item(row)


@router.get(
    "/{ticker}/historico",
    response_model=list[dict],
    summary="Série histórica de valuation do ativo",
)
def historico_valuation(
    ticker: str,
    limit: int = Query(20, ge=1, le=60),
):
    """
    Série histórica de Graham Number, Bazin e preço para análise temporal.
    Útil para ver evolução do valor justo ao longo dos trimestres.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                p.ano,
                p.trimestre,
                p.dt_referencia::text AS dt_referencia,
                MAX(CASE WHEN i.codigo = 'mkt_preco_fechamento' THEN fi.valor END) AS preco,
                MAX(CASE WHEN i.codigo = 'val_graham'           THEN fi.valor END) AS graham,
                MAX(CASE WHEN i.codigo = 'val_bazin_6'          THEN fi.valor END) AS bazin_6,
                MAX(CASE WHEN i.codigo = 'val_bazin_10'         THEN fi.valor END) AS bazin_10,
                MAX(CASE WHEN i.codigo = 'val_lpa'              THEN fi.valor END) AS lpa,
                MAX(CASE WHEN i.codigo = 'val_vpa'              THEN fi.valor END) AS vpa,
                MAX(CASE WHEN i.codigo = 'val_dpa_ttm'          THEN fi.valor END) AS dpa_ttm,
                MAX(CASE WHEN i.codigo = 'val_margem_graham'    THEN fi.valor END) AS margem_graham,
                MAX(CASE WHEN i.codigo = 'val_status'           THEN fi.valor END) AS status_num
            FROM track_stocks.fato_indicadores fi
            JOIN track_stocks.indicadores      i  USING (indicador_id)
            JOIN track_stocks.empresas         e  USING (empresa_id)
            JOIN track_stocks.periodos         p  USING (periodo_id)
            WHERE e.ticker = %s
              AND i.codigo IN (
                  'mkt_preco_fechamento','val_graham','val_bazin_6','val_bazin_10',
                  'val_lpa','val_vpa','val_dpa_ttm','val_margem_graham','val_status'
              )
            GROUP BY p.ano, p.trimestre, p.dt_referencia
            ORDER BY p.ano DESC, p.trimestre DESC
            LIMIT %s
        """, (ticker.upper(), limit))
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Sem histórico de valuation para '{ticker}'.")

    def _s(status_num) -> str:
        m = {1.0: "subavaliado", 0.5: "possivel_oportunidade",
             0.0: "proximo_do_valor_justo", -0.5: "levemente_sobrevalorizado",
             -1.0: "sobrevalorizado"}
        return m.get(float(status_num), "sem_dados") if status_num is not None else "sem_dados"

    return [
        {
            "ano": r["ano"],
            "trimestre": r["trimestre"],
            "dt_referencia": r["dt_referencia"],
            "preco": float(r["preco"]) if r["preco"] else None,
            "graham": float(r["graham"]) if r["graham"] else None,
            "bazin_6": float(r["bazin_6"]) if r["bazin_6"] else None,
            "bazin_10": float(r["bazin_10"]) if r["bazin_10"] else None,
            "lpa": float(r["lpa"]) if r["lpa"] else None,
            "vpa": float(r["vpa"]) if r["vpa"] else None,
            "dpa_ttm": float(r["dpa_ttm"]) if r["dpa_ttm"] else None,
            "margem_graham_pct": round(float(r["margem_graham"]) * 100, 1) if r["margem_graham"] else None,
            "status": _s(r["status_num"]),
        }
        for r in rows
    ]
