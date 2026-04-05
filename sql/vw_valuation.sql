-- =============================================================================
-- VIEW: vw_valuation
-- Retorna o valuation mais recente por ticker com Graham Number, Bazin e status.
-- Otimizada para consumo direto pelo backend (endpoint /api/valuation).
-- =============================================================================

CREATE OR REPLACE VIEW track_stocks.vw_valuation AS

WITH

-- Período mais recente com val_graham calculado para cada empresa
latest_periodo AS (
    SELECT DISTINCT ON (fi.empresa_id)
        fi.empresa_id,
        fi.periodo_id,
        p.ano,
        p.trimestre,
        p.dt_referencia
    FROM track_stocks.fato_indicadores fi
    JOIN track_stocks.indicadores      i  USING (indicador_id)
    JOIN track_stocks.periodos         p  USING (periodo_id)
    WHERE i.codigo = 'val_graham'
    ORDER BY fi.empresa_id, p.ano DESC, p.trimestre DESC
),

-- Pivot de todos os indicadores VAL + MKT necessários no período mais recente
vals AS (
    SELECT
        lp.empresa_id,
        lp.periodo_id,
        lp.ano,
        lp.trimestre,
        lp.dt_referencia,

        -- Preço
        MAX(CASE WHEN i.codigo = 'mkt_preco_fechamento'     THEN fi.valor END) AS preco,

        -- Por ação
        MAX(CASE WHEN i.codigo = 'val_lpa'                  THEN fi.valor END) AS lpa,
        MAX(CASE WHEN i.codigo = 'val_vpa'                  THEN fi.valor END) AS vpa,
        MAX(CASE WHEN i.codigo = 'val_dpa_ttm'              THEN fi.valor END) AS dpa_ttm,

        -- Graham
        MAX(CASE WHEN i.codigo = 'val_graham'               THEN fi.valor END) AS graham,
        MAX(CASE WHEN i.codigo = 'val_margem_graham'        THEN fi.valor END) AS margem_graham,

        -- Bazin
        MAX(CASE WHEN i.codigo = 'val_bazin_6'              THEN fi.valor END) AS bazin_6,
        MAX(CASE WHEN i.codigo = 'val_bazin_10'             THEN fi.valor END) AS bazin_10,
        MAX(CASE WHEN i.codigo = 'val_margem_bazin_6'       THEN fi.valor END) AS margem_bazin_6,
        MAX(CASE WHEN i.codigo = 'val_margem_bazin_10'      THEN fi.valor END) AS margem_bazin_10,

        -- Status numérico
        MAX(CASE WHEN i.codigo = 'val_status'               THEN fi.valor END) AS status_num,

        -- Complementares para contexto
        MAX(CASE WHEN i.codigo = 'mkt_pl_ttm'               THEN fi.valor END) AS pl_ttm,
        MAX(CASE WHEN i.codigo = 'mkt_pvp'                  THEN fi.valor END) AS pvp,
        MAX(CASE WHEN i.codigo = 'mkt_dividend_yield_ttm'   THEN fi.valor END) AS dy_ttm,
        MAX(CASE WHEN i.codigo = 'mkt_market_cap'           THEN fi.valor END) AS market_cap_mil,
        MAX(CASE WHEN i.codigo = 'mkt_ev_ebitda_ttm'        THEN fi.valor END) AS ev_ebitda,
        MAX(CASE WHEN i.codigo = 'mkt_divida_liquida_ebitda_ttm' THEN fi.valor END) AS dl_ebitda

    FROM latest_periodo    lp
    JOIN track_stocks.fato_indicadores fi USING (empresa_id)
    JOIN track_stocks.indicadores       i USING (indicador_id)
    -- Garante que buscamos apenas o período mais recente de cada empresa
    WHERE fi.periodo_id = lp.periodo_id
      AND i.codigo IN (
          'mkt_preco_fechamento', 'val_lpa', 'val_vpa', 'val_dpa_ttm',
          'val_graham', 'val_margem_graham',
          'val_bazin_6', 'val_bazin_10',
          'val_margem_bazin_6', 'val_margem_bazin_10',
          'val_status',
          'mkt_pl_ttm', 'mkt_pvp', 'mkt_dividend_yield_ttm',
          'mkt_market_cap', 'mkt_ev_ebitda_ttm', 'mkt_divida_liquida_ebitda_ttm'
      )
    GROUP BY lp.empresa_id, lp.periodo_id, lp.ano, lp.trimestre, lp.dt_referencia
)

SELECT
    e.ticker,
    e.razao_social,
    ts.setor,
    v.ano,
    v.trimestre,
    v.dt_referencia,

    -- Preço
    ROUND(v.preco::numeric,       2)        AS preco,

    -- Métricas por ação
    ROUND(v.lpa::numeric,         4)        AS lpa,
    ROUND(v.vpa::numeric,         4)        AS vpa,
    ROUND(v.dpa_ttm::numeric,     4)        AS dpa_ttm,

    -- Valuation — Graham
    ROUND(v.graham::numeric,      2)        AS valor_justo_graham,
    ROUND((v.margem_graham * 100)::numeric, 1) AS margem_graham_pct,

    -- Valuation — Bazin
    ROUND(v.bazin_6::numeric,     2)        AS preco_teto_bazin_6,
    ROUND(v.bazin_10::numeric,    2)        AS preco_teto_bazin_10,
    ROUND((v.margem_bazin_6  * 100)::numeric, 1) AS margem_bazin_6_pct,
    ROUND((v.margem_bazin_10 * 100)::numeric, 1) AS margem_bazin_10_pct,

    -- Status legível
    CASE
        WHEN v.status_num =  1.0 THEN 'subavaliado'
        WHEN v.status_num =  0.5 THEN 'possivel_oportunidade'
        WHEN v.status_num =  0.0 THEN 'proximo_do_valor_justo'
        WHEN v.status_num = -0.5 THEN 'levemente_sobrevalorizado'
        WHEN v.status_num = -1.0 THEN 'sobrevalorizado'
        ELSE                          'sem_dados_suficientes'
    END                                     AS status_graham_bazin,

    -- Status simplificado para UI (3 estados)
    CASE
        WHEN v.status_num >= 0.5  THEN 'abaixo_do_valor_justo'
        WHEN v.status_num <= -0.5 THEN 'acima_do_valor_justo'
        ELSE                           'proximo_do_valor_justo'
    END                                     AS status_simples,

    -- Contexto adicional
    ROUND(v.pl_ttm::numeric,      2)        AS pl_ttm,
    ROUND(v.pvp::numeric,         4)        AS pvp,
    ROUND((v.dy_ttm * 100)::numeric, 2)     AS dy_ttm_pct,
    ROUND((v.market_cap_mil / 1e6)::numeric, 2) AS market_cap_bilhoes,
    ROUND(v.ev_ebitda::numeric,   2)        AS ev_ebitda,
    ROUND(v.dl_ebitda::numeric,   2)        AS dl_ebitda

FROM vals             v
JOIN track_stocks.empresas   e  USING (empresa_id)
LEFT JOIN track_stocks.ticker_setor ts ON ts.ticker = e.ticker
WHERE e.ticker IS NOT NULL;
