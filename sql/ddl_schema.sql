CREATE SCHEMA IF NOT EXISTS track_stocks;
SET search_path TO track_stocks, public;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'bloco_indicador_enum' AND n.nspname = 'track_stocks'
    ) THEN
        CREATE TYPE track_stocks.bloco_indicador_enum AS ENUM ('BP', 'DRE', 'DFC', 'CMB', 'HST', 'MKT', 'OUTRO');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'unidade_valor_enum' AND n.nspname = 'track_stocks'
    ) THEN
        CREATE TYPE track_stocks.unidade_valor_enum AS ENUM ('MOEDA', 'PERCENTUAL', 'RATIO', 'PONTOS', 'INDICE', 'OUTRO');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'etl_status_enum' AND n.nspname = 'track_stocks'
    ) THEN
        CREATE TYPE track_stocks.etl_status_enum AS ENUM ('STARTED', 'SUCCESS', 'FAILED', 'PARTIAL');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS track_stocks.empresas (
    empresa_id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    razao_social             TEXT NOT NULL,
    cnpj_original            TEXT NOT NULL,
    cnpj_normalizado         VARCHAR(14) NOT NULL,
    codigo_cvm               INTEGER,
    ticker                   TEXT,
    ativo                    BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em                TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_empresas_cnpj_normalizado CHECK (cnpj_normalizado ~ '^[0-9]{14}$')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_empresas_cnpj_normalizado
    ON track_stocks.empresas (cnpj_normalizado);

CREATE UNIQUE INDEX IF NOT EXISTS uq_empresas_codigo_cvm
    ON track_stocks.empresas (codigo_cvm)
    WHERE codigo_cvm IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_empresas_razao_social
    ON track_stocks.empresas (razao_social);

CREATE INDEX IF NOT EXISTS ix_empresas_ticker
    ON track_stocks.empresas (ticker)
    WHERE ticker IS NOT NULL;

CREATE TABLE IF NOT EXISTS track_stocks.periodos (
    periodo_id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    freq                     track_stocks.freq_enum NOT NULL,
    ano                      SMALLINT NOT NULL,
    trimestre                SMALLINT,
    mes                      SMALLINT,
    dt_referencia            DATE NOT NULL,
    competencia_label        TEXT GENERATED ALWAYS AS (
                                CASE
                                    WHEN freq = 'A' THEN ano::TEXT
                                    WHEN freq = 'T' THEN ano::TEXT || '-T' || trimestre::TEXT
                                    WHEN freq = 'M' THEN ano::TEXT || '-' || LPAD(mes::TEXT, 2, '0')
                                END
                             ) STORED,
    criado_em                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_periodos_ano CHECK (ano BETWEEN 1900 AND 2200),
    CONSTRAINT ck_periodos_dt_ref_ano CHECK (EXTRACT(YEAR FROM dt_referencia) = ano),
    CONSTRAINT ck_periodos_trimestre_por_freq CHECK (
        (freq = 'A' AND trimestre IS NULL) OR
        (freq = 'T' AND trimestre BETWEEN 1 AND 4) OR
        (freq = 'M' AND trimestre IS NULL)
    ),
    CONSTRAINT ck_periodos_mes_por_freq CHECK (
        (freq = 'M' AND mes BETWEEN 1 AND 12) OR
        (freq != 'M' AND mes IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_periodos_anual
    ON track_stocks.periodos (ano)
    WHERE freq = 'A';

CREATE UNIQUE INDEX IF NOT EXISTS uq_periodos_trimestral
    ON track_stocks.periodos (ano, trimestre)
    WHERE freq = 'T';

-- Índice único para períodos mensais
CREATE UNIQUE INDEX IF NOT EXISTS uq_periodos_mensal
    ON track_stocks.periodos (ano, mes)
    WHERE freq = 'M';

CREATE UNIQUE INDEX IF NOT EXISTS uq_periodos_freq_data
    ON track_stocks.periodos (freq, dt_referencia);

CREATE UNIQUE INDEX IF NOT EXISTS uq_periodos_competencia_label
    ON track_stocks.periodos (freq, competencia_label);

CREATE INDEX IF NOT EXISTS ix_periodos_filtro
    ON track_stocks.periodos (freq, ano, trimestre, mes, dt_referencia);

CREATE TABLE IF NOT EXISTS track_stocks.indicadores (
    indicador_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo                   TEXT NOT NULL,
    nome                     TEXT NOT NULL,
    bloco                    track_stocks.bloco_indicador_enum NOT NULL,
    camada                   SMALLINT NOT NULL,
    descricao                TEXT,
    formula                  TEXT,
    contas_utilizadas        JSONB NOT NULL DEFAULT '[]'::jsonb,
    unidade                  track_stocks.unidade_valor_enum NOT NULL DEFAULT 'OUTRO',
    ativo                    BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em                TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_indicadores_codigo UNIQUE (codigo),
    CONSTRAINT ck_indicadores_camada CHECK (camada IN (1, 2, 3)),
    CONSTRAINT ck_indicadores_codigo_formato CHECK (codigo ~ '^[a-z0-9_]+$')
);

CREATE INDEX IF NOT EXISTS ix_indicadores_bloco_camada
    ON track_stocks.indicadores (bloco, camada, codigo);

CREATE INDEX IF NOT EXISTS ix_indicadores_ativo
    ON track_stocks.indicadores (ativo)
    WHERE ativo = TRUE;

CREATE TABLE IF NOT EXISTS track_stocks.etl_execucoes (
    etl_execucao_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_nome            TEXT NOT NULL DEFAULT 'indicadores_pipeline',
    versao_pipeline          TEXT,
    origem_dados             TEXT,
    iniciado_em              TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizado_em            TIMESTAMPTZ,
    status                   track_stocks.etl_status_enum NOT NULL DEFAULT 'STARTED',
    total_empresas           INTEGER,
    total_periodos           INTEGER,
    total_registros_fato     BIGINT,
    observacao               TEXT,
    CONSTRAINT ck_etl_datas CHECK (finalizado_em IS NULL OR finalizado_em >= iniciado_em),
    CONSTRAINT ck_etl_contagens CHECK (
        (total_empresas IS NULL OR total_empresas >= 0)
        AND (total_periodos IS NULL OR total_periodos >= 0)
        AND (total_registros_fato IS NULL OR total_registros_fato >= 0)
    )
);

CREATE INDEX IF NOT EXISTS ix_etl_execucoes_status_data
    ON track_stocks.etl_execucoes (status, iniciado_em DESC);

CREATE TABLE IF NOT EXISTS track_stocks.fato_indicadores (
    empresa_id               BIGINT NOT NULL,
    periodo_id               BIGINT NOT NULL,
    indicador_id             BIGINT NOT NULL,
    valor                    NUMERIC(28,10) NOT NULL,
    etl_execucao_id          BIGINT,
    calculado_em             TIMESTAMPTZ NOT NULL DEFAULT now(),
    observacao               TEXT,

    CONSTRAINT pk_fato_indicadores PRIMARY KEY (empresa_id, periodo_id, indicador_id),

    CONSTRAINT fk_fato_empresa
        FOREIGN KEY (empresa_id)
        REFERENCES track_stocks.empresas (empresa_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_fato_periodo
        FOREIGN KEY (periodo_id)
        REFERENCES track_stocks.periodos (periodo_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_fato_indicador
        FOREIGN KEY (indicador_id)
        REFERENCES track_stocks.indicadores (indicador_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_fato_etl
        FOREIGN KEY (etl_execucao_id)
        REFERENCES track_stocks.etl_execucoes (etl_execucao_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_fato_empresa_indicador_periodo
    ON track_stocks.fato_indicadores (empresa_id, indicador_id, periodo_id);

CREATE INDEX IF NOT EXISTS ix_fato_indicador_periodo_empresa
    ON track_stocks.fato_indicadores (indicador_id, periodo_id, empresa_id);

CREATE INDEX IF NOT EXISTS ix_fato_periodo
    ON track_stocks.fato_indicadores (periodo_id);

CREATE INDEX IF NOT EXISTS ix_fato_etl
    ON track_stocks.fato_indicadores (etl_execucao_id);

DROP VIEW IF EXISTS track_stocks.vw_indicadores_historicos;
CREATE VIEW track_stocks.vw_indicadores_historicos AS
SELECT
    e.empresa_id,
    e.razao_social AS empresa,
    e.cnpj_original,
    e.cnpj_normalizado,
    e.codigo_cvm,
    e.ticker,
    p.freq,
    p.ano,
    p.trimestre,
    p.mes,
    p.dt_referencia,
    i.codigo AS indicador_codigo,
    i.nome   AS indicador_nome,
    i.bloco,
    i.camada,
    i.unidade,
    f.valor,
    f.etl_execucao_id,
    f.calculado_em
FROM track_stocks.fato_indicadores f
JOIN track_stocks.empresas e ON e.empresa_id = f.empresa_id
JOIN track_stocks.periodos p ON p.periodo_id = f.periodo_id
JOIN track_stocks.indicadores i ON i.indicador_id = f.indicador_id;
