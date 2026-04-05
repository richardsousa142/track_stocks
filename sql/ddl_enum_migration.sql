-- 0. Adiciona 'VAL' ao bloco_indicador_enum (valuation: Graham, Bazin, etc.)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'bloco_indicador_enum'
          AND n.nspname = 'track_stocks'
          AND e.enumlabel = 'VAL'
    ) THEN
        ALTER TYPE track_stocks.bloco_indicador_enum ADD VALUE 'VAL';
    END IF;
END$$;

-- 1. Cria ou adiciona 'M' ao freq_enum
--    ALTER TYPE ADD VALUE exige autocommit — não pode rodar em transação
--    junto com comandos que já usem o novo valor.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'freq_enum' AND n.nspname = 'track_stocks'
    ) THEN
        CREATE TYPE track_stocks.freq_enum AS ENUM ('A', 'T', 'M');
    ELSIF NOT EXISTS (
        SELECT 1 FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'freq_enum'
          AND n.nspname = 'track_stocks'
          AND e.enumlabel = 'M'
    ) THEN
        ALTER TYPE track_stocks.freq_enum ADD VALUE 'M';
    END IF;
END$$;

-- 2. Adiciona a coluna 'mes' em periodos caso a tabela já exista sem ela.
--    CREATE TABLE IF NOT EXISTS não altera tabelas existentes, então
--    precisamos garantir a coluna e constraints via ALTER TABLE aqui.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'track_stocks' AND table_name = 'periodos'
    ) THEN
        -- Adiciona coluna mes se não existir
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'track_stocks'
              AND table_name   = 'periodos'
              AND column_name  = 'mes'
        ) THEN
            ALTER TABLE track_stocks.periodos ADD COLUMN mes SMALLINT;
        END IF;

        -- Recria ck_periodos_trimestre_por_freq incluindo o caso freq='M'.
        -- A constraint original só tinha 'A' e 'T', então freq='M' a viola.
        IF EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema      = 'track_stocks'
              AND table_name        = 'periodos'
              AND constraint_name   = 'ck_periodos_trimestre_por_freq'
        ) THEN
            ALTER TABLE track_stocks.periodos
                DROP CONSTRAINT ck_periodos_trimestre_por_freq;
        END IF;

        ALTER TABLE track_stocks.periodos
            ADD CONSTRAINT ck_periodos_trimestre_por_freq CHECK (
                (freq = 'A' AND trimestre IS NULL) OR
                (freq = 'T' AND trimestre BETWEEN 1 AND 4) OR
                (freq = 'M' AND trimestre IS NULL)
            );

        -- Adiciona ck_periodos_mes_por_freq se ainda não existir
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema    = 'track_stocks'
              AND table_name      = 'periodos'
              AND constraint_name = 'ck_periodos_mes_por_freq'
        ) THEN
            ALTER TABLE track_stocks.periodos
                ADD CONSTRAINT ck_periodos_mes_por_freq CHECK (
                    (freq = 'M' AND mes BETWEEN 1 AND 12) OR
                    (freq != 'M' AND mes IS NULL)
                );
        END IF;
    END IF;
END$$;
