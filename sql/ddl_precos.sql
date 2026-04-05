-- =============================================================================
-- DDL: tabelas de mercado diário e classificação setorial
--
-- DECISÃO DE DESIGN: NÃO usamos fato_indicadores para OHLCV porque:
--   1. periodos só tem freq A/T/M, não diária
--   2. fato_indicadores é EAV: 5 linhas por pregão = joins caros para séries
--   3. OHLCV é dado bruto, não indicador derivado
--
-- precos_diarios → wide format, PK (ticker, data_pregao)
-- ticker_setor   → classificação setorial por ticker
--
-- Esses dados alimentarão no futuro cálculos de:
--   P/L, P/VP, EV/EBITDA, dividend yield e similares,
--   que serão salvos em fato_indicadores com freq T ou A.
-- =============================================================================

-- ── 1. Tabela de preços diários ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS track_stocks.precos_diarios (
    ticker          TEXT        NOT NULL,
    data_pregao     DATE        NOT NULL,
    open            NUMERIC(18, 6),
    high            NUMERIC(18, 6),
    low             NUMERIC(18, 6),
    close           NUMERIC(18, 6) NOT NULL,
    volume          NUMERIC(28, 2),
    fonte           TEXT        NOT NULL DEFAULT 'b3',
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_precos_diarios PRIMARY KEY (ticker, data_pregao),

    CONSTRAINT ck_precos_ohlc CHECK (
        (open  IS NULL OR open  > 0) AND
        (high  IS NULL OR high  > 0) AND
        (low   IS NULL OR low   > 0) AND
        close > 0
    ),
    CONSTRAINT ck_precos_high_low CHECK (
        high IS NULL OR low IS NULL OR high >= low
    ),
    CONSTRAINT ck_precos_volume CHECK (
        volume IS NULL OR volume >= 0
    )
);

-- Consultas de série temporal por ativo (mais comum)
CREATE INDEX IF NOT EXISTS ix_precos_ticker_data
    ON track_stocks.precos_diarios (ticker, data_pregao DESC);

-- Consultas de snapshot cross-sectional por data (ranking, correlação)
CREATE INDEX IF NOT EXISTS ix_precos_data_ticker
    ON track_stocks.precos_diarios (data_pregao DESC, ticker);

-- ── 2. Tabela de classificação setorial ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS track_stocks.ticker_setor (
    ticker          TEXT        NOT NULL,
    setor           TEXT,
    subsetor        TEXT,
    industria       TEXT,
    fonte           TEXT        NOT NULL DEFAULT 'yfinance',
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_ticker_setor PRIMARY KEY (ticker)
);

CREATE INDEX IF NOT EXISTS ix_ticker_setor_setor
    ON track_stocks.ticker_setor (setor)
    WHERE setor IS NOT NULL;
