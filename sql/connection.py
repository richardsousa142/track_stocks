"""Conexão PostgreSQL — URL em ``pipeline.config``."""

from __future__ import annotations

import psycopg

from pipeline.config import DATABASE_URL, get_database_url


def get_connection(*, autocommit: bool = False):
    return psycopg.connect(get_database_url(), autocommit=autocommit)
