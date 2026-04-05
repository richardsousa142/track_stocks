"""
Repositório: preços diários e classificação setorial.

Estratégia de upsert em bulk:
    1. COPY para tabela temporária (máxima velocidade de ingestão)
    2. INSERT ... ON CONFLICT DO UPDATE da temp para a tabela definitiva
    3. DROP da tabela temporária

Isso evita o custo de UPDATE linha a linha e aproveita o protocolo
binário do PostgreSQL, que é ~10x mais rápido que executemany.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

import pandas as pd
import psycopg

logger = logging.getLogger(__name__)


# ── DTOs ─────────────────────────────────────────────────────────────────────

@dataclass
class UpsertStats:
    linhas_input: int = 0
    linhas_validas: int = 0
    erros_validacao: int = 0
    tickers_distintos: int = 0
    datas_min: date | None = None
    datas_max: date | None = None
    setores_upserted: int = 0
    precos_upserted: int = 0
    warnings: list[str] = field(default_factory=list)


# ── Validação ─────────────────────────────────────────────────────────────────

_REQUIRED_COLS = {"ticker", "data_pregao", "close"}
_OHLCV_COLS   = {"open", "high", "low", "close", "volume"}


def validate_precos_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Valida e limpa o DataFrame de preços.
    Retorna (df_limpo, lista_de_warnings).
    """
    warnings: list[str] = []
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    n_raw = len(df)

    df = df.copy()
    df["data_pregao"] = pd.to_datetime(df["data_pregao"]).dt.date
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()

    # remove tickers vazios
    mask_ticker = df["ticker"].str.len() > 0
    n_bad_ticker = (~mask_ticker).sum()
    if n_bad_ticker:
        warnings.append(f"{n_bad_ticker} linhas com ticker vazio removidas.")
    df = df[mask_ticker]

    # remove close inválido
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    mask_close = df["close"].notna() & (df["close"] > 0)
    n_bad_close = (~mask_close).sum()
    if n_bad_close:
        warnings.append(f"{n_bad_close} linhas com close inválido (≤0 ou nulo) removidas.")
    df = df[mask_close]

    # converte colunas OHLCV numéricas e satura negativos
    for col in _OHLCV_COLS - {"close"}:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            mask_neg = df[col].notna() & (df[col] < 0)
            if mask_neg.any():
                warnings.append(f"{mask_neg.sum()} valores negativos em '{col}' convertidos para NULL.")
                df.loc[mask_neg, col] = None

    # verifica high >= low quando ambos presentes
    if "high" in df.columns and "low" in df.columns:
        mask_hl = df["high"].notna() & df["low"].notna() & (df["high"] < df["low"])
        if mask_hl.any():
            warnings.append(f"{mask_hl.sum()} linhas com high < low: valores trocados.")
            df.loc[mask_hl, ["high", "low"]] = df.loc[mask_hl, ["low", "high"]].values

    # duplicatas (ticker, data_pregao): mantém última ocorrência
    dupes = df.duplicated(subset=["ticker", "data_pregao"], keep="last")
    if dupes.any():
        warnings.append(f"{dupes.sum()} duplicatas (ticker, data_pregao) removidas (manteve última).")
    df = df[~dupes]

    logger.info(
        "Validação concluída: %d → %d linhas (%d descartadas).",
        n_raw, len(df), n_raw - len(df),
    )
    return df, warnings


# ── Preços diários ────────────────────────────────────────────────────────────

_TEMP_PRECOS = "tmp_precos_ingest"

_SQL_CREATE_TEMP = f"""
CREATE TEMPORARY TABLE {_TEMP_PRECOS} (
    ticker      TEXT        NOT NULL,
    data_pregao DATE        NOT NULL,
    open        NUMERIC(18,6),
    high        NUMERIC(18,6),
    low         NUMERIC(18,6),
    close       NUMERIC(18,6) NOT NULL,
    volume      NUMERIC(28,2),
    fonte       TEXT        NOT NULL DEFAULT 'b3'
) ON COMMIT DROP;
"""

_SQL_UPSERT_FROM_TEMP = f"""
INSERT INTO track_stocks.precos_diarios
    (ticker, data_pregao, open, high, low, close, volume, fonte, atualizado_em)
SELECT
    ticker, data_pregao, open, high, low, close, volume, fonte, now()
FROM {_TEMP_PRECOS}
ON CONFLICT (ticker, data_pregao) DO UPDATE SET
    open          = EXCLUDED.open,
    high          = EXCLUDED.high,
    low           = EXCLUDED.low,
    close         = EXCLUDED.close,
    volume        = EXCLUDED.volume,
    fonte         = EXCLUDED.fonte,
    atualizado_em = now();
"""


def _df_to_tsv_buffer(df: pd.DataFrame, cols: list[str]) -> io.BytesIO:
    """Serializa o DataFrame para TSV em memória (formato para COPY)."""
    buf = io.StringIO()
    df[cols].to_csv(buf, sep="\t", index=False, header=False, na_rep="\\N")
    return io.BytesIO(buf.getvalue().encode("utf-8"))


def upsert_precos_diarios(
    conn: psycopg.Connection,
    df: pd.DataFrame,
    fonte: str = "b3",
    batch_size: int = 50_000,
) -> int:
    """
    Faz upsert em bulk de preços diários via COPY → temp → INSERT ON CONFLICT.

    Retorna o número de linhas processadas.
    """
    cols = ["ticker", "data_pregao", "open", "high", "low", "close", "volume", "fonte"]

    # garante coluna fonte
    df = df.copy()
    df["fonte"] = fonte

    # garante colunas opcionais ausentes
    for col in ["open", "high", "low", "volume"]:
        if col not in df.columns:
            df[col] = None

    df = df[cols].copy()
    df["data_pregao"] = df["data_pregao"].astype(str)  # psycopg precisa de str para COPY text

    total = 0
    with conn.cursor() as cur:
        cur.execute(_SQL_CREATE_TEMP)

        for start in range(0, len(df), batch_size):
            chunk = df.iloc[start : start + batch_size]
            buf = _df_to_tsv_buffer(chunk, cols)

            with cur.copy(
                f"COPY {_TEMP_PRECOS} ({', '.join(cols)}) FROM STDIN WITH (FORMAT TEXT, NULL '\\N')"
            ) as copy:
                copy.write(buf.read())

            total += len(chunk)
            logger.debug("COPY: %d/%d linhas carregadas.", total, len(df))

        cur.execute(_SQL_UPSERT_FROM_TEMP)
        upserted = cur.rowcount if cur.rowcount >= 0 else total
        logger.info("Upsert precos_diarios: %d linhas processadas.", upserted)

    return total


# ── Setor ─────────────────────────────────────────────────────────────────────

_SQL_UPSERT_SETOR = """
INSERT INTO track_stocks.ticker_setor
    (ticker, setor, subsetor, industria, fonte, atualizado_em)
VALUES (%s, %s, %s, %s, %s, now())
ON CONFLICT (ticker) DO UPDATE SET
    setor         = COALESCE(EXCLUDED.setor,    track_stocks.ticker_setor.setor),
    subsetor      = COALESCE(EXCLUDED.subsetor, track_stocks.ticker_setor.subsetor),
    industria     = COALESCE(EXCLUDED.industria,track_stocks.ticker_setor.industria),
    fonte         = EXCLUDED.fonte,
    atualizado_em = now();
"""


def upsert_setores(
    conn: psycopg.Connection,
    registros: Iterable[dict],
    fonte: str = "yfinance",
) -> int:
    """
    Upsert de classificações setoriais.

    Cada registro deve ter: ticker, setor (e opcionalmente subsetor, industria).
    Estratégia COALESCE: não sobrescreve valores existentes com NULL.
    """
    rows = [
        (
            str(r["ticker"]).strip().upper(),
            r.get("setor") or None,
            r.get("subsetor") or None,
            r.get("industria") or None,
            fonte,
        )
        for r in registros
        if r.get("ticker")
    ]
    if not rows:
        return 0

    with conn.cursor() as cur:
        cur.executemany(_SQL_UPSERT_SETOR, rows)
    logger.info("Upsert ticker_setor: %d registros.", len(rows))
    return len(rows)


def upsert_setores_from_df(
    conn: psycopg.Connection,
    df: pd.DataFrame,
    ticker_col: str = "ticker",
    setor_col: str = "setor",
    fonte: str = "yfinance",
) -> int:
    registros = df.rename(columns={ticker_col: "ticker", setor_col: "setor"}).to_dict("records")
    return upsert_setores(conn, registros, fonte=fonte)


# ── Consultas auxiliares ──────────────────────────────────────────────────────

def fetch_precos_ticker(
    conn: psycopg.Connection,
    ticker: str,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> pd.DataFrame:
    """Retorna série histórica diária de um ticker como DataFrame."""
    sql = """
        SELECT data_pregao, open, high, low, close, volume
        FROM track_stocks.precos_diarios
        WHERE ticker = %s
          AND (%s IS NULL OR data_pregao >= %s)
          AND (%s IS NULL OR data_pregao <= %s)
        ORDER BY data_pregao ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (ticker, data_inicio, data_inicio, data_fim, data_fim))
        rows = cur.fetchall()
        cols = [d.name for d in cur.description]
    return pd.DataFrame(rows, columns=cols)


def fetch_close_pivot(
    conn: psycopg.Connection,
    tickers: list[str],
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> pd.DataFrame:
    """
    Retorna tabela pivot de fechamentos (linhas=datas, colunas=tickers).
    Útil para calcular correlações, retornos, métricas quantitativas.
    """
    sql = """
        SELECT data_pregao, ticker, close
        FROM track_stocks.precos_diarios
        WHERE ticker = ANY(%s)
          AND (%s IS NULL OR data_pregao >= %s)
          AND (%s IS NULL OR data_pregao <= %s)
        ORDER BY data_pregao ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (tickers, data_inicio, data_inicio, data_fim, data_fim))
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["data_pregao", "ticker", "close"])
    return df.pivot(index="data_pregao", columns="ticker", values="close")
