"""Endpoints da API de FIIs."""

from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from ..services.db import get_cursor
from ..services.fii_score import compute_fii_rankings  # usado em listar_fiis

router = APIRouter(prefix="/api/fiis")


@router.get("")
def listar_fiis(
    limit:  int = Query(20, ge=1, le=200),
    offset: int = Query(0,  ge=0),
):
    """Ranking paginado de FIIs por Quality Score (apenas fundos válidos)."""
    with get_cursor() as cur:
        rankings = compute_fii_rankings(cur)
    return rankings[offset: offset + limit]



@router.get("/busca")
def buscar_fiis(q: str = Query(..., min_length=1)):
    """Busca FIIs por nome, CNPJ ou segmento."""
    pattern = f"%{q.upper()}%"
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                e.cnpj_normalizado,
                e.razao_social          AS nome_fundo,
                COALESCE(m.segmento_atuacao, 'Outros') AS segmento
            FROM track_stocks.empresas e
            LEFT JOIN track_stocks.tb_fiis_meta m ON m.empresa_id = e.empresa_id
            WHERE e.ticker IS NULL
              AND (
                  UPPER(e.razao_social)      LIKE %s
                  OR e.cnpj_normalizado      LIKE %s
                  OR UPPER(m.segmento_atuacao) LIKE %s
                  OR UPPER(m.nome_administrador) LIKE %s
              )
            ORDER BY e.razao_social
            LIMIT 15
        """, (pattern, pattern, pattern, pattern))
        return [
            {
                "cnpj":      r["cnpj_normalizado"],
                "nome_fundo": r["nome_fundo"],
                "segmento":   r["segmento"],
                "tipo":       "fii",
            }
            for r in cur.fetchall()
        ]


@router.get("/{cnpj}")
def get_fii(cnpj: str):
    """
    Metadados de um FII específico.
    Retorna imediatamente os dados descritivos (nome, segmento, administrador).
    O score é obtido via cache do ranking — incluso apenas quando já calculado.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                e.cnpj_normalizado,
                e.razao_social              AS nome_fundo,
                m.segmento_atuacao          AS segmento,
                m.tipo_gestao,
                m.nome_administrador,
                m.cnpj_administrador
            FROM track_stocks.empresas e
            LEFT JOIN track_stocks.tb_fiis_meta m ON m.empresa_id = e.empresa_id
            WHERE e.cnpj_normalizado = %s
        """, (cnpj,))
        row = cur.fetchone()

    if not row:
        raise HTTPException(404, "FII não encontrado")

    meta = {
        "cnpj":               row["cnpj_normalizado"],
        "nome_fundo":         row["nome_fundo"] or cnpj,
        "segmento":           row["segmento"] or "Outros",
        "tipo_gestao":        row["tipo_gestao"] or "",
        "nome_administrador": row["nome_administrador"] or "",
        "cnpj_administrador": row["cnpj_administrador"] or "",
    }

    # Inclui score apenas se o ranking já foi calculado e está em cache.
    # Não dispara novo cálculo para não bloquear a resposta.
    from ..services.fii_score import _cache
    cached_rankings: list = _cache.get("fii_rankings", {}).get("data", [])
    score_entry = next((r for r in cached_rankings if r["cnpj"] == cnpj), None)
    if score_entry:
        for k, v in score_entry.items():
            if k not in meta:
                meta[k] = v

    return meta


@router.get("/{cnpj}/indicadores")
def indicador_serie_fii(
    cnpj:      str,
    indicador: str = Query(...),
    freq:      str = Query("M", pattern="^(M|T|A)$"),
):
    """Série histórica de um indicador para um FII."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                p.dt_referencia,
                i.codigo  AS indicador_codigo,
                i.nome    AS indicador_nome,
                i.bloco,
                i.unidade,
                f.valor,
                p.freq,
                p.ano,
                p.mes
            FROM track_stocks.fato_indicadores f
            JOIN track_stocks.empresas    e ON e.empresa_id   = f.empresa_id
            JOIN track_stocks.periodos    p ON p.periodo_id   = f.periodo_id
            JOIN track_stocks.indicadores i ON i.indicador_id = f.indicador_id
            WHERE e.cnpj_normalizado = %s
              AND i.codigo           = %s
              AND p.freq             = %s
              AND f.valor IS NOT NULL
            ORDER BY p.dt_referencia ASC
        """, (cnpj, indicador, freq))
        rows = cur.fetchall()

    return [
        {
            "dt_referencia":    str(r["dt_referencia"]),
            "indicador_codigo": r["indicador_codigo"],
            "indicador_nome":   r["indicador_nome"],
            "bloco":            r["bloco"],
            "unidade":          r["unidade"],
            "valor":            float(r["valor"]) if r["valor"] is not None else 0,
            "freq":             r["freq"],
            "ano":              r["ano"],
            "mes":              r.get("mes"),
        }
        for r in rows
    ]


@router.get("/{cnpj}/todos-indicadores")
def todos_indicadores_fii(cnpj: str):
    """Todos os indicadores FII mais recentes de um fundo (freq='M')."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (i.codigo)
                i.codigo  AS indicador_codigo,
                i.nome    AS indicador_nome,
                i.bloco,
                i.unidade,
                f.valor,
                p.dt_referencia
            FROM track_stocks.fato_indicadores f
            JOIN track_stocks.empresas    e ON e.empresa_id   = f.empresa_id
            JOIN track_stocks.periodos    p ON p.periodo_id   = f.periodo_id
            JOIN track_stocks.indicadores i ON i.indicador_id = f.indicador_id
            WHERE e.cnpj_normalizado = %s
              AND p.freq             = 'M'
              AND f.valor IS NOT NULL
              AND i.bloco            = 'FII'
            ORDER BY i.codigo, p.dt_referencia DESC
        """, (cnpj,))
        rows = cur.fetchall()

    return [
        {
            "indicador_codigo": r["indicador_codigo"],
            "indicador_nome":   r["indicador_nome"],
            "bloco":            r["bloco"],
            "unidade":          r["unidade"],
            "valor":            float(r["valor"]) if r["valor"] is not None else 0,
            "dt_referencia":    str(r["dt_referencia"]),
        }
        for r in rows
    ]
