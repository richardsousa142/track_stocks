"""Repositório: períodos."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Optional


def quarter_end_date(ano: int, trimestre: int) -> date:
    mapping = {
        1: date(ano, 3, 31),
        2: date(ano, 6, 30),
        3: date(ano, 9, 30),
        4: date(ano, 12, 31),
    }
    if trimestre not in mapping:
        raise ValueError("Trimestre deve estar entre 1 e 4.")
    return mapping[trimestre]


quarter_end = quarter_end_date


def infer_dt_referencia(
    freq: str,
    ano: int,
    trimestre: Optional[int] = None,
    mes: Optional[int] = None,
) -> date:
    if freq == "A":
        return date(ano, 12, 31)
    if freq == "T":
        if trimestre is None:
            raise ValueError("Para frequência trimestral, informe o trimestre.")
        return quarter_end_date(ano, trimestre)
    if freq == "M":
        if mes is None:
            raise ValueError("Para frequência mensal, informe o mês.")
        last_day = calendar.monthrange(ano, mes)[1]
        return date(ano, mes, last_day)
    raise ValueError("freq deve ser 'A', 'T' ou 'M'.")


def load_periodo_row(cur, freq: str, ano: int, trimestre, mes) -> Optional[tuple]:
    cur.execute(
        """
        SELECT periodo_id FROM track_stocks.periodos
        WHERE freq = %s AND ano = %s
          AND (trimestre IS NOT DISTINCT FROM %s)
          AND (mes       IS NOT DISTINCT FROM %s)
        """,
        (freq, ano, trimestre, mes),
    )
    return cur.fetchone()


def upsert_periodo(
    cur,
    freq: str,
    ano: int,
    trimestre: Optional[int] = None,
    mes: Optional[int] = None,
    dt_referencia: Optional[date] = None,
):
    if dt_referencia is None:
        dt_referencia = infer_dt_referencia(freq, ano, trimestre, mes)

    if freq == "A":
        trimestre = None
        mes = None
    elif freq == "T":
        mes = None
    elif freq == "M":
        trimestre = None

    cur.execute(
        """
        INSERT INTO track_stocks.periodos (freq, ano, trimestre, mes, dt_referencia)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING periodo_id;
        """,
        (freq, ano, trimestre, mes, dt_referencia),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    row = load_periodo_row(cur, freq, ano, trimestre, mes)
    if row is None:
        raise LookupError(
            f"Período não encontrado: freq={freq} ano={ano} tri={trimestre} mes={mes}"
        )
    return row[0]


def resolve_periodo_id(
    cur, freq: str, ano: int,
    trimestre: Optional[int] = None,
    mes: Optional[int] = None,
) -> int:
    row = load_periodo_row(cur, freq, ano, trimestre, mes)
    if row is None:
        raise LookupError(
            f"Período não encontrado: freq={freq} ano={ano} tri={trimestre} mes={mes}"
        )
    return row[0]
