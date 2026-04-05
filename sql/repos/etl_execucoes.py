"""Repositório: registro de execuções ETL."""

from __future__ import annotations

from typing import Optional


def iniciar_execucao(cur, origem: str) -> int:
    cur.execute(
        """
        INSERT INTO track_stocks.etl_execucoes
            (pipeline_nome, versao_pipeline, origem_dados, status)
        VALUES ('etl_indicadores', '1.0', %s, 'STARTED')
        RETURNING etl_execucao_id;
        """,
        (origem,),
    )
    return cur.fetchone()[0]


def finalizar_execucao(
    cur,
    etl_id: int,
    status: str,
    n_empresas: int,
    n_periodos: int,
    n_fatos: int,
    obs: Optional[str] = None,
) -> None:
    cur.execute(
        """
        UPDATE track_stocks.etl_execucoes SET
            finalizado_em        = now(),
            status               = %s::track_stocks.etl_status_enum,
            total_empresas       = %s,
            total_periodos       = %s,
            total_registros_fato = %s,
            observacao           = %s
        WHERE etl_execucao_id = %s;
        """,
        (status, n_empresas, n_periodos, n_fatos, obs, etl_id),
    )
