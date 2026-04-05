from __future__ import annotations

import logging
from pathlib import Path

import psycopg

from pipeline.config import get_database_url
from sql.catalog import build_indicator_rows

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent

DDL_ENUM_MIGRATION   = _HERE.joinpath("ddl_enum_migration.sql").read_text(encoding="utf-8")
DDL                  = _HERE.joinpath("ddl_schema.sql").read_text(encoding="utf-8")
DDL_PRECOS           = _HERE.joinpath("ddl_precos.sql").read_text(encoding="utf-8")
DDL_DEMONSTRATIVOS   = _HERE.joinpath("ddl_demonstrativos.sql").read_text(encoding="utf-8")
DDL_ACOES_SHARES     = _HERE.joinpath("ddl_acoes_shares.sql").read_text(encoding="utf-8")


def create_schema_and_catalog() -> None:
    """Aplica todas as migrações DDL e sincroniza o catálogo de indicadores."""
    dsn = get_database_url()

    # Enums precisam de autocommit (ALTER TYPE ADD VALUE não pode rodar em transação)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL_ENUM_MIGRATION)
    logger.info("Enums aplicados.")

    # Schema principal + catálogo de indicadores + tabelas de mercado
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            logger.info("DDL principal aplicado.")

            cur.execute(DDL_PRECOS)
            logger.info("DDL de preços e setores aplicado.")

            cur.execute(DDL_DEMONSTRATIVOS)
            logger.info("DDL de demonstrativos (BP/DRE/DFC) aplicado.")

            cur.execute(DDL_ACOES_SHARES)
            logger.info("DDL de ações (shares outstanding) aplicado.")

            rows = build_indicator_rows()
            cur.executemany(
                """
                INSERT INTO track_stocks.indicadores
                    (codigo, nome, bloco, camada, unidade, contas_utilizadas)
                VALUES (
                    %s, %s,
                    %s::track_stocks.bloco_indicador_enum,
                    %s,
                    %s::track_stocks.unidade_valor_enum,
                    %s
                )
                ON CONFLICT (codigo) DO UPDATE
                SET nome              = EXCLUDED.nome,
                    bloco             = EXCLUDED.bloco,
                    camada            = EXCLUDED.camada,
                    unidade           = EXCLUDED.unidade,
                    contas_utilizadas = EXCLUDED.contas_utilizadas,
                    atualizado_em     = now();
                """,
                rows,
            )
            logger.info("Catálogo de indicadores sincronizado: %d indicadores.", len(rows))
        conn.commit()
