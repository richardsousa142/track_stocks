"""Endpoints da API de ativos."""

from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from ..services.db import get_cursor
from ..services.quality_score import compute_rankings

router = APIRouter(prefix="/api")


@router.get("/ativos")
def listar_ativos(
    tipo: str = Query("acoes", pattern="^(acoes|fiis)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Lista paginada de ativos ordenados por Quality Score."""
    with get_cursor() as cur:
        rankings = compute_rankings(cur)

    return rankings[offset : offset + limit]


@router.get("/ativos/busca")
def buscar_ativos(q: str = Query(..., min_length=1)):
    """Busca por ticker ou razão social."""
    pattern = f"%{q.upper()}%"
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ticker, empresa
            FROM track_stocks.vw_indicadores_historicos
            WHERE (UPPER(ticker) LIKE %s OR UPPER(empresa) LIKE %s)
              AND ticker IS NOT NULL AND ticker != ''
            ORDER BY ticker
            LIMIT 15
        """, (pattern, pattern))
        return [{"ticker": r["ticker"], "empresa": r["empresa"]} for r in cur.fetchall()]


@router.get("/ativos/{ticker}/indicadores")
def indicador_serie(
    ticker: str,
    indicador: str = Query(...),
    freq: str = Query("T", pattern="^(A|T|M)$"),
):
    """Série histórica de um indicador para um ativo."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                dt_referencia, indicador_codigo, indicador_nome,
                bloco, unidade, valor, freq, ano, trimestre, mes
            FROM track_stocks.vw_indicadores_historicos
            WHERE ticker = %s
              AND indicador_codigo = %s
              AND freq = %s
            ORDER BY dt_referencia ASC
        """, (ticker, indicador, freq))
        rows = cur.fetchall()

    return [
        {
            "dt_referencia": str(r["dt_referencia"]),
            "indicador_codigo": r["indicador_codigo"],
            "indicador_nome": r["indicador_nome"],
            "bloco": r["bloco"],
            "unidade": r["unidade"],
            "valor": float(r["valor"]) if r["valor"] is not None else 0,
            "freq": r["freq"],
            "ano": r["ano"],
            "trimestre": r.get("trimestre"),
            "mes": r.get("mes"),
        }
        for r in rows
    ]


@router.get("/ativos/{ticker}/todos-indicadores")
def todos_indicadores(
    ticker: str,
    freq: str = Query("T", pattern="^(A|T|M)$"),
):
    """Todos os indicadores mais recentes do ativo."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (indicador_codigo)
                indicador_codigo, indicador_nome, bloco, unidade, valor, dt_referencia
            FROM track_stocks.vw_indicadores_historicos
            WHERE ticker = %s AND freq = %s
            ORDER BY indicador_codigo, dt_referencia DESC
        """, (ticker, freq))
        rows = cur.fetchall()

    return [
        {
            "indicador_codigo": r["indicador_codigo"],
            "indicador_nome": r["indicador_nome"],
            "bloco": r["bloco"],
            "unidade": r["unidade"],
            "valor": float(r["valor"]) if r["valor"] is not None else 0,
            "dt_referencia": str(r["dt_referencia"]),
        }
        for r in rows
    ]


@router.get("/ativos/{ticker}/analise")
def analise(ticker: str):
    """Análise textual do ativo baseada nos indicadores."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (indicador_codigo)
                indicador_codigo, valor
            FROM track_stocks.vw_indicadores_historicos
            WHERE ticker = %s AND freq IN ('T', 'A')
            ORDER BY indicador_codigo, dt_referencia DESC
        """, (ticker,))
        latest = {
            r["indicador_codigo"]: float(r["valor"])
            for r in cur.fetchall()
            if r["valor"] is not None
        }

    if not latest:
        raise HTTPException(404, "Ativo não encontrado")

    highlights = {
        "bp_liquidez_corrente": ("Liquidez corrente", 1.5, True, "×"),
        "cmb_roe": ("ROE", 0.15, True, "%"),
        "dre_margem_liquida": ("Margem líquida", 0.08, True, "%"),
        "bp_passivo_sobre_ativo": ("Passivo/Ativo", 0.65, False, ""),
        "mkt_sharpe_252d": ("Sharpe 252d", 0.5, True, ""),
        "mkt_sortino_252d": ("Sortino 252d", 0.8, True, ""),
    }

    parts = [f"<strong>{ticker}</strong> apresenta os seguintes destaques recentes:"]
    for code, (name, thr, hb, suffix) in highlights.items():
        val = latest.get(code)
        if val is None:
            continue
        is_good = (val >= thr) if hb else (val <= thr)
        color = "#059669" if is_good else "#dc2626"
        if suffix == "%":
            formatted = f"{val*100:.1f}%"
        elif suffix == "×":
            formatted = f"{val:.2f}×"
        else:
            formatted = f"{val:.2f}"
        status = "acima" if is_good else "abaixo"
        parts.append(
            f' <span style="color:{color};font-weight:600">{name} de {formatted}</span>'
            f" ({status} do limiar de {thr})."
        )

    return {
        "ticker": ticker,
        "texto": " ".join(parts),
        "gerado_em": "2026-03-30T00:00:00Z",
    }
