-- =============================================================================
-- DDL: demonstrativos financeiros brutos (BP, DRE, DFC)
--
-- DECISÃO DE DESIGN: NÃO usamos fato_indicadores para os demonstrativos porque:
--   1. fato_indicadores é para indicadores DERIVADOS (ROE, ROA etc.)
--      Os demonstrativos são dados BRUTOS com hierarquia de contas CVM.
--   2. O catálogo de indicadores não modela CD_CONTA hierárquico (1.01.02.03).
--   3. Forçar ~800 contas por empresa por período no EAV existente criaria
--      milhões de linhas com joins caros e sem semântica correta.
--   4. A granularidade dos demonstrativos é conta/período, não indicador/período.
--
-- fato_demonstrativos → formato wide-row, PK (empresa_id, periodo_id, tipo_demo, grupo_dfp, cd_conta)
--
-- tipo_demo: 'BP' (Balanço Patrimonial), 'DRE', 'DFC'
-- grupo_dfp: string CVM completa (ex: "DF Consolidado - Balanço Patrimonial Ativo")
--            distingue: Consolidado vs Individual, e Ativo vs Passivo no BP
--
-- Frequência dos períodos: sempre quarterly (freq='T')
--   DT_FIM_EXERC 31/03 → Q1, 30/06 → Q2, 30/09 → Q3, 31/12 → Q4
--   Dados anuais (DFP) são Q4 do respectivo ano.
-- =============================================================================

CREATE TABLE IF NOT EXISTS track_stocks.fato_demonstrativos (
    empresa_id      BIGINT      NOT NULL,
    periodo_id      BIGINT      NOT NULL,
    tipo_demo       TEXT        NOT NULL,  -- 'BP', 'DRE', 'DFC'
    grupo_dfp       TEXT        NOT NULL,  -- GRUPO_DFP original da CVM
    cd_conta        TEXT        NOT NULL,  -- código da conta, ex: "1.01.02"
    ds_conta        TEXT        NOT NULL,  -- descrição da conta
    vl_conta        NUMERIC(28, 10),       -- valor na escala original (MIL ou UNIDADE)
    escala_moeda    TEXT,                  -- 'MIL' ou 'UNIDADE'
    moeda           TEXT,                  -- 'REAL'
    st_conta_fixa   BOOLEAN,              -- conta fixa da estrutura CVM (S→true)
    versao          SMALLINT,             -- versão do documento CVM
    dt_fim_exerc    DATE,                  -- data real do fim do exercício (preserva fiscal year não-padrão)
    etl_execucao_id BIGINT,
    calculado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_fato_demonstrativos
        PRIMARY KEY (empresa_id, periodo_id, tipo_demo, grupo_dfp, cd_conta),

    CONSTRAINT fk_demo_empresa
        FOREIGN KEY (empresa_id)
        REFERENCES track_stocks.empresas (empresa_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_demo_periodo
        FOREIGN KEY (periodo_id)
        REFERENCES track_stocks.periodos (periodo_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_demo_etl
        FOREIGN KEY (etl_execucao_id)
        REFERENCES track_stocks.etl_execucoes (etl_execucao_id)
        ON DELETE SET NULL,

    CONSTRAINT ck_demo_tipo
        CHECK (tipo_demo IN ('BP', 'DRE', 'DFC')),

    CONSTRAINT ck_demo_escala
        CHECK (escala_moeda IS NULL OR escala_moeda IN ('MIL', 'UNIDADE', 'BILHAO'))
);

-- Consultas por empresa + período (análise histórica por ativo)
CREATE INDEX IF NOT EXISTS ix_demo_empresa_periodo
    ON track_stocks.fato_demonstrativos (empresa_id, periodo_id, tipo_demo);

-- Consultas cross-sectional por conta (comparação entre empresas)
CREATE INDEX IF NOT EXISTS ix_demo_conta_periodo
    ON track_stocks.fato_demonstrativos (cd_conta, periodo_id, empresa_id);

-- Consultas por tipo de demonstrativo
CREATE INDEX IF NOT EXISTS ix_demo_tipo_empresa
    ON track_stocks.fato_demonstrativos (tipo_demo, empresa_id, periodo_id);

-- ETL audit
CREATE INDEX IF NOT EXISTS ix_demo_etl
    ON track_stocks.fato_demonstrativos (etl_execucao_id)
    WHERE etl_execucao_id IS NOT NULL;
