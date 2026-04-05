"""Conexão PostgreSQL com pool de conexões."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/track_stocks",
)


def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@contextmanager
def get_cursor() -> Generator[psycopg.Cursor, None, None]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    finally:
        conn.close()
