-- =============================================================================
-- DDL: número de ações por ticker
--
-- DECISÃO DE DESIGN: tabela separada (não em 'empresas') porque:
--   1. Shares outstanding muda ao longo do tempo (splits, follow-ons)
--   2. Pode ter série histórica anual
--   3. Não é atributo fixo da empresa
-- =============================================================================

CREATE TABLE IF NOT EXISTS track_stocks.tb_acoes_shares (
    ticker              TEXT        NOT NULL,
    data_referencia     DATE        NOT NULL,  -- data de corte (aproximada)
    shares_outstanding  BIGINT      NOT NULL,  -- número de ações
    market_cap_ref      NUMERIC(28,2),         -- market cap na data (informativo)
    fonte               TEXT        NOT NULL DEFAULT 'yfinance',
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_acoes_shares PRIMARY KEY (ticker, data_referencia)
);

CREATE INDEX IF NOT EXISTS ix_acoes_shares_ticker
    ON track_stocks.tb_acoes_shares (ticker, data_referencia DESC);
