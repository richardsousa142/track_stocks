-- ============================================================
-- View de indicadores históricos dos FIIs
-- Análoga à vw_indicadores_historicos, mas identificada por
-- cnpj_normalizado em vez de ticker.
-- ============================================================

CREATE OR REPLACE VIEW track_stocks.vw_fii_indicadores AS
SELECT
    e.empresa_id,
    e.cnpj_normalizado,
    e.razao_social                              AS nome_fundo,
    COALESCE(m.segmento_atuacao, 'Outros')      AS segmento,
    COALESCE(m.tipo_gestao, '')                 AS tipo_gestao,
    COALESCE(m.nome_administrador, '')          AS nome_administrador,
    p.freq,
    p.ano,
    p.mes,
    p.dt_referencia,
    i.codigo                                    AS indicador_codigo,
    i.nome                                      AS indicador_nome,
    i.bloco,
    i.unidade,
    f.valor,
    f.calculado_em
FROM track_stocks.fato_indicadores f
JOIN track_stocks.empresas    e ON e.empresa_id    = f.empresa_id
JOIN track_stocks.periodos    p ON p.periodo_id    = f.periodo_id
JOIN track_stocks.indicadores i ON i.indicador_id  = f.indicador_id
LEFT JOIN track_stocks.tb_fiis_meta m ON m.empresa_id = e.empresa_id
WHERE i.bloco = 'FII'
  AND f.valor IS NOT NULL;

-- Índice auxiliar para consultas por empresa (cobre FIIs)
CREATE INDEX IF NOT EXISTS ix_fato_empresa_id ON track_stocks.fato_indicadores (empresa_id);
