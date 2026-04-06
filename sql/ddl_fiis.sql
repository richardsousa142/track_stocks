-- ============================================================
-- DDL: camada de FIIs
-- Complementa a arquitetura existente (empresas / periodos /
-- fato_indicadores) com uma tabela de metadados específica
-- de fundos imobiliários.
-- ============================================================

-- Metadados descritivos do fundo (não dependem de período)
CREATE TABLE IF NOT EXISTS track_stocks.tb_fiis_meta (
    empresa_id              BIGINT        NOT NULL,
    cnpj_fundo              VARCHAR(14)   NOT NULL,
    nome_fundo              TEXT,
    segmento_atuacao        TEXT,
    tipo_gestao             TEXT,
    publico_alvo            TEXT,
    nome_administrador      TEXT,
    cnpj_administrador      VARCHAR(14),
    atualizado_em           TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT pk_fiis_meta PRIMARY KEY (empresa_id),

    CONSTRAINT fk_fiis_meta_empresa
        FOREIGN KEY (empresa_id)
        REFERENCES track_stocks.empresas (empresa_id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fiis_meta_cnpj
    ON track_stocks.tb_fiis_meta (cnpj_fundo);

CREATE INDEX IF NOT EXISTS ix_fiis_meta_segmento
    ON track_stocks.tb_fiis_meta (segmento_atuacao);

COMMENT ON TABLE track_stocks.tb_fiis_meta IS
    'Metadados descritivos de fundos imobiliários (CVM). '
    'Referencia empresas.empresa_id; um fundo = um CNPJ.';
