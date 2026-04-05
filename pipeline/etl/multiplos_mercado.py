"""
Pipeline: Múltiplos de Mercado Fundamentalistas
================================================
Calcula e persiste P/L, P/VP, P/FCF, EV/EBITDA, DY, Dívida Líquida/EBITDA,
etc., cruzando dados do banco (fato_demonstrativos + precos_diarios) com o
número de ações obtido via yfinance.

Lógica de corte temporal (sem look-ahead bias):
  - Cada trimestre usa o PREÇO NA DATA DE REFERÊNCIA do período (último pregão
    disponível até dt_referencia).
  - Dados de demonstrativos são os já presentes em fato_demonstrativos para o
    mesmo periodo_id → publicados até a data de referência.
  - TTM = soma dos últimos 4 trimestres de valores periódicos (fluxo).

Unidades:
  - Valores contábeis em fato_demonstrativos: R$ MIL (escala_moeda='MIL')
  - Preço: R$ por ação
  - Market Cap: R$ MIL  (= price × shares / 1000)
  - Todos os múltiplos ficam na mesma escala → adimensionais.

Execução incremental:
  - Calcula apenas períodos sem valor mkt_pl_ttm (ou --full para refazer tudo).
"""

from __future__ import annotations

import argparse
import logging
import unicodedata
import re
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False
    logging.warning("yfinance não instalado — shares não serão atualizados.")

from pipeline.config import get_database_url

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SQL: dados fundamentais por empresa × período (direto do banco)
# ─────────────────────────────────────────────────────────────────────────────

_SQL_BP_ITEMS = """
-- Itens do balanço patrimonial por empresa × período.
-- Estratégia: prefere Consolidado; se não existir, aceita Individual.
WITH ranked AS (
    SELECT
        d.empresa_id,
        d.periodo_id,
        d.cd_conta,
        d.vl_conta,
        CASE WHEN d.grupo_dfp LIKE '%%Consolidado%%' THEN 1 ELSE 2 END AS pref
    FROM track_stocks.fato_demonstrativos d
    WHERE d.tipo_demo = 'BP'
      AND d.empresa_id = ANY(%(empresa_ids)s)
),
best_pref AS (
    SELECT empresa_id, periodo_id, MIN(pref) AS best_pref
    FROM ranked
    GROUP BY empresa_id, periodo_id
)
SELECT
    r.empresa_id,
    r.periodo_id,
    MAX(CASE WHEN r.cd_conta = '1.01.01' THEN r.vl_conta END) AS cash_eq,
    MAX(CASE WHEN r.cd_conta = '1.01.02' THEN r.vl_conta END) AS fin_apps,
    MAX(CASE WHEN r.cd_conta = '1'       THEN r.vl_conta END) AS asset_total,
    MAX(CASE WHEN r.cd_conta = '2'       THEN r.vl_conta END) AS liab_total,
    MAX(CASE WHEN r.cd_conta = '2.01'    THEN r.vl_conta END) AS liab_current,
    MAX(CASE WHEN r.cd_conta = '2.02'    THEN r.vl_conta END) AS liab_non_current,
    MAX(CASE WHEN r.cd_conta = '2.03'    THEN r.vl_conta END) AS equity
FROM ranked r
JOIN best_pref bp USING (empresa_id, periodo_id)
WHERE r.pref = bp.best_pref
GROUP BY r.empresa_id, r.periodo_id
"""

_SQL_DRE_ITEMS = """
WITH ranked AS (
    SELECT
        d.empresa_id, d.periodo_id, d.cd_conta, d.vl_conta,
        CASE WHEN d.grupo_dfp LIKE '%%Consolidado%%' THEN 1 ELSE 2 END AS pref
    FROM track_stocks.fato_demonstrativos d
    WHERE d.tipo_demo = 'DRE'
      AND d.empresa_id = ANY(%(empresa_ids)s)
),
best_pref AS (
    SELECT empresa_id, periodo_id, MIN(pref) AS best_pref FROM ranked GROUP BY 1,2
)
SELECT
    r.empresa_id, r.periodo_id,
    MAX(CASE WHEN r.cd_conta = '3.01'    THEN r.vl_conta END) AS revenue_ytd,
    MAX(CASE WHEN r.cd_conta = '3.03'    THEN r.vl_conta END) AS gross_profit_ytd,
    MAX(CASE WHEN r.cd_conta = '3.05'    THEN r.vl_conta END) AS ebit_ytd,
    MAX(CASE WHEN r.cd_conta = '3.11'    THEN r.vl_conta END) AS net_income_ytd,
    MAX(CASE WHEN r.cd_conta = '3.06.02' THEN r.vl_conta END) AS financial_exp_ytd
FROM ranked r
JOIN best_pref bp USING (empresa_id, periodo_id)
WHERE r.pref = bp.best_pref
GROUP BY r.empresa_id, r.periodo_id
"""

_SQL_DFC_ITEMS = """
WITH ranked AS (
    SELECT
        d.empresa_id, d.periodo_id, d.cd_conta, d.vl_conta,
        CASE WHEN d.grupo_dfp LIKE '%%Consolidado%%' THEN 1 ELSE 2 END AS pref
    FROM track_stocks.fato_demonstrativos d
    WHERE d.tipo_demo = 'DFC'
      AND d.empresa_id = ANY(%(empresa_ids)s)
),
best_pref AS (
    SELECT empresa_id, periodo_id, MIN(pref) AS best_pref FROM ranked GROUP BY 1,2
)
SELECT
    r.empresa_id, r.periodo_id,
    MAX(CASE WHEN r.cd_conta = '6.01'       THEN r.vl_conta END) AS cfo_ytd,
    MAX(CASE WHEN r.cd_conta = '6.01.01.02' THEN r.vl_conta END) AS da_ytd,
    MAX(CASE WHEN r.cd_conta = '6.02.16'    THEN r.vl_conta END) AS acq_ppe_ytd,
    MAX(CASE WHEN r.cd_conta = '6.02.15'    THEN r.vl_conta END) AS acq_intang_ytd,
    MAX(CASE WHEN r.cd_conta = '6.02.14'    THEN r.vl_conta END) AS acq_concession_ytd,
    MAX(CASE WHEN r.cd_conta = '6.03.05'    THEN r.vl_conta END) AS dividends_paid_ytd,
    MAX(CASE WHEN r.cd_conta = '6.03'       THEN r.vl_conta END) AS cff_ytd
FROM ranked r
JOIN best_pref bp USING (empresa_id, periodo_id)
WHERE r.pref = bp.best_pref
GROUP BY r.empresa_id, r.periodo_id
"""

_SQL_PERIODOS = """
SELECT p.periodo_id, p.ano, p.trimestre, p.dt_referencia, p.freq
FROM track_stocks.periodos p
WHERE p.freq = 'T'
ORDER BY p.dt_referencia
"""

_SQL_EMPRESAS = """
-- Para cada ticker, selecionar empresa_id com mais dados em fato_demonstrativos
WITH ranked_emp AS (
    SELECT
        e.empresa_id,
        e.ticker,
        COUNT(fd.empresa_id) AS n_rows,
        ROW_NUMBER() OVER (
            PARTITION BY e.ticker
            ORDER BY COUNT(fd.empresa_id) DESC, e.empresa_id DESC
        ) AS rn
    FROM track_stocks.empresas e
    LEFT JOIN track_stocks.fato_demonstrativos fd USING (empresa_id)
    WHERE e.ticker IS NOT NULL
      AND e.ticker NOT LIKE '%%11'
    GROUP BY e.empresa_id, e.ticker
)
SELECT empresa_id, ticker
FROM ranked_emp
WHERE rn = 1
ORDER BY ticker
"""

_SQL_LAST_PRICE_AT_DATE = """
SELECT DISTINCT ON (ticker)
    ticker,
    close AS preco,
    data_pregao
FROM track_stocks.precos_diarios
WHERE ticker = ANY(%(tickers)s)
  AND data_pregao <= %(dt_ref)s
ORDER BY ticker, data_pregao DESC
"""

_SQL_SHARES = """
SELECT ticker, shares_outstanding, data_referencia
FROM track_stocks.tb_acoes_shares
WHERE ticker = ANY(%(tickers)s)
ORDER BY ticker, data_referencia DESC
"""

_SQL_INDICADOR_ID = """
SELECT indicador_id, codigo FROM track_stocks.indicadores
WHERE codigo = ANY(%(codes)s)
"""

_SQL_EMPRESA_DONE = """
-- Retorna empresa_ids que já têm mkt_pl_ttm calculado para TODOS os períodos
-- (usamos como proxy: empresa com >=50 períodos de mkt_pl_ttm está completa)
SELECT fi.empresa_id
FROM track_stocks.fato_indicadores fi
JOIN track_stocks.indicadores i USING (indicador_id)
WHERE i.codigo = 'mkt_pl_ttm'
  AND fi.empresa_id = ANY(%(empresa_ids)s)
GROUP BY fi.empresa_id
HAVING COUNT(*) >= 50
"""

_SQL_UPSERT = """
INSERT INTO track_stocks.fato_indicadores (empresa_id, periodo_id, indicador_id, valor)
VALUES (%(empresa_id)s, %(periodo_id)s, %(indicador_id)s, %(valor)s)
ON CONFLICT (empresa_id, periodo_id, indicador_id)
DO UPDATE SET valor = EXCLUDED.valor
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_div(a, b):
    """Divisão segura, retorna NaN se denominador for 0 ou NaN."""
    if b is None or b == 0 or np.isnan(b):
        return np.nan
    if a is None or np.isnan(a):
        return np.nan
    result = a / b
    if np.isinf(result):
        return np.nan
    return float(result)


def _flow_from_ytd(s: pd.Series) -> pd.Series:
    """Converte série YTD para valor periódico (Q1=YTD, Q2=YTD-Q1, ...)."""
    if s.empty:
        return s
    grp = s.groupby(s.index.get_level_values("ano"))
    diff = grp.diff()
    first_mask = grp.cumcount() == 0
    diff[first_mask] = s[first_mask]
    return diff


def _ttm(s: pd.Series, n: int = 4) -> pd.Series:
    """Rolling sum de n períodos (TTM quando n=4)."""
    return s.rolling(n, min_periods=n).sum()


def _fetch_yf_shares(tickers_sa: list[str]) -> dict[str, int]:
    """Busca shares outstanding via yfinance. Retorna {ticker_sa: shares}."""
    if not HAS_YF:
        return {}
    result: dict[str, int] = {}
    for t in tickers_sa:
        try:
            info = yf.Ticker(t).info
            shares = (
                info.get("sharesOutstanding")
                or info.get("impliedSharesOutstanding")
                or info.get("sharesOutstandingCommon")
            )
            if shares and isinstance(shares, (int, float)) and shares > 0:
                result[t] = int(shares)
                log.debug("shares %s = %d", t, shares)
        except Exception as exc:
            log.warning("yfinance erro %s: %s", t, exc)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Upsert de shares na tabela de infra
# ─────────────────────────────────────────────────────────────────────────────

_SQL_UPSERT_SHARES = """
INSERT INTO track_stocks.tb_acoes_shares (ticker, data_referencia, shares_outstanding, fonte)
VALUES (%(ticker)s, %(data_referencia)s, %(shares)s, 'yfinance')
ON CONFLICT (ticker, data_referencia) DO UPDATE
    SET shares_outstanding = EXCLUDED.shares_outstanding,
        atualizado_em = now()
"""


def refresh_shares(conn: psycopg.Connection, tickers: list[str]) -> dict[str, int]:
    """Atualiza tb_acoes_shares via yfinance e retorna {ticker: shares}."""
    tickers_sa = [t + ".SA" for t in tickers]
    log.info("Buscando shares via yfinance para %d tickers...", len(tickers_sa))
    raw = _fetch_yf_shares(tickers_sa)

    today = date.today()
    rows = []
    result: dict[str, int] = {}
    for t_sa, shares in raw.items():
        t = t_sa.replace(".SA", "")
        result[t] = shares
        rows.append({"ticker": t, "data_referencia": today, "shares": shares})

    if rows:
        with conn.cursor() as cur:
            cur.executemany(_SQL_UPSERT_SHARES, rows)
        conn.commit()
        log.info("Shares persistidos: %d tickers", len(rows))

    return result


def load_shares_from_db(conn: psycopg.Connection, tickers: list[str]) -> dict[str, int]:
    """Carrega shares mais recentes do banco (já salvos)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SQL_SHARES, {"tickers": tickers})
        rows = cur.fetchall()
    seen: set[str] = set()
    result: dict[str, int] = {}
    for r in rows:
        if r["ticker"] not in seen:
            result[r["ticker"]] = int(r["shares_outstanding"])
            seen.add(r["ticker"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Leitura de dados fundamentais do banco
# ─────────────────────────────────────────────────────────────────────────────

def load_fundamentos(
    conn: psycopg.Connection,
    empresa_ids: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Retorna (periodos_df, bp_df, dre_df, dfc_df).
    Todas com colunas empresa_id + periodo_id como chave.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SQL_PERIODOS)
        periodos_df = pd.DataFrame(cur.fetchall())

        cur.execute(_SQL_BP_ITEMS, {"empresa_ids": empresa_ids})
        bp_df = pd.DataFrame(cur.fetchall())

        cur.execute(_SQL_DRE_ITEMS, {"empresa_ids": empresa_ids})
        dre_df = pd.DataFrame(cur.fetchall())

        cur.execute(_SQL_DFC_ITEMS, {"empresa_ids": empresa_ids})
        dfc_df = pd.DataFrame(cur.fetchall())

    for df in [bp_df, dre_df, dfc_df]:
        for col in df.columns:
            if col not in ("empresa_id", "periodo_id"):
                df[col] = pd.to_numeric(df[col], errors="coerce")

    return periodos_df, bp_df, dre_df, dfc_df


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo dos múltiplos para UM ativo
# ─────────────────────────────────────────────────────────────────────────────

def _filter_by_empresa(df: pd.DataFrame, empresa_id: int, periodos: pd.DataFrame) -> pd.DataFrame:
    """Filtra df por empresa_id e faz merge com periodos. Retorna vazio seguro se sem dados."""
    if df.empty or "empresa_id" not in df.columns:
        return pd.DataFrame(columns=["ano", "trimestre"])
    sub = df[df["empresa_id"] == empresa_id]
    if sub.empty:
        return pd.DataFrame(columns=["ano", "trimestre"])
    return (
        sub.merge(periodos[["periodo_id", "ano", "trimestre"]], on="periodo_id")
        .set_index("periodo_id")
        .sort_values(["ano", "trimestre"])
    )


def _ytd_to_quarterly(df: pd.DataFrame, ytd_cols: list[str]) -> pd.DataFrame:
    """
    Dado um DataFrame com index=periodo_id e colunas 'ano', 'trimestre' + ytd_cols,
    converte cada coluna YTD para valor periódico (Q1=YTD, Q2=Q2ytd-Q1ytd, etc.).
    """
    df = df.reset_index()
    for col in ytd_cols:
        if col not in df.columns:
            continue
        base = col.replace("_ytd", "")
        grp = df.groupby("ano")[col]
        diff = grp.diff()
        first_mask = grp.cumcount() == 0
        diff.loc[first_mask] = df.loc[first_mask, col].values
        df[f"{base}_q"] = diff
    return df.set_index("periodo_id")


def _build_company_series(
    empresa_id: int,
    periodos: pd.DataFrame,
    bp_all: pd.DataFrame,
    dre_all: pd.DataFrame,
    dfc_all: pd.DataFrame,
    prices: dict[int, float],     # {periodo_id: close}
    shares: int,                  # shares outstanding (constante)
) -> pd.DataFrame:
    """
    Constrói séries temporais de múltiplos para um único ativo.
    Retorna DataFrame com colunas = indicadores e índice = periodo_id.
    """
    bp  = _filter_by_empresa(bp_all,  empresa_id, periodos)
    dre = _filter_by_empresa(dre_all, empresa_id, periodos)
    dfc = _filter_by_empresa(dfc_all, empresa_id, periodos)

    if bp.empty and dre.empty:
        return pd.DataFrame()

    # ── Índice mestre de períodos (apenas trimestrais) ───────────────────────
    # periodos já vem filtrado por freq='T' → garantia de sem look-ahead bias
    per_lookup = periodos.set_index("periodo_id")[["ano", "trimestre"]]
    all_pids_raw = sorted(
        set(bp.index.tolist()) | set(dre.index.tolist()) | set(dfc.index.tolist())
    )
    # Interseção: só usa períodos trimestrais conhecidos
    all_pids = sorted(set(all_pids_raw) & set(per_lookup.index))
    if not all_pids:
        return pd.DataFrame()

    s = per_lookup.reindex(all_pids)
    s.index.name = "periodo_id"

    # ── BP (posição — não precisa de conversão YTD→Q) ────────────────────────
    for col in ["cash_eq", "fin_apps", "asset_total", "liab_total",
                "liab_current", "liab_non_current", "equity"]:
        if not bp.empty and col in bp.columns:
            s[col] = bp[col].reindex(s.index)

    # ── DRE: reindex YTD, depois converter para periódico ───────────────────
    dre_ytd_cols = ["revenue_ytd", "gross_profit_ytd", "ebit_ytd",
                    "net_income_ytd", "financial_exp_ytd"]
    for col in dre_ytd_cols:
        if not dre.empty and col in dre.columns:
            s[col] = dre[col].reindex(s.index)

    s = _ytd_to_quarterly(s, dre_ytd_cols)

    # ── DFC: reindex YTD, depois converter para periódico ───────────────────
    dfc_ytd_cols = ["cfo_ytd", "da_ytd", "acq_ppe_ytd", "acq_intang_ytd",
                    "acq_concession_ytd", "dividends_paid_ytd", "cff_ytd"]
    for col in dfc_ytd_cols:
        if not dfc.empty and col in dfc.columns:
            s[col] = dfc[col].reindex(s.index)

    s = _ytd_to_quarterly(s, dfc_ytd_cols)

    # ── TTM (rolling 4 quarters) ─────────────────────────────────────────────
    for base in ["revenue", "ebit", "net_income", "cfo", "da",
                 "dividends_paid", "financial_exp"]:
        q_col = f"{base}_q"
        if q_col in s.columns:
            s[f"{base}_ttm"] = s[q_col].rolling(4, min_periods=4).sum()

    # Capex TTM
    capex_q_cols = [c for c in ["acq_ppe_q", "acq_intang_q", "acq_concession_q"] if c in s.columns]
    if capex_q_cols:
        capex_q = s[capex_q_cols].fillna(0).sum(axis=1)
        s["capex_ttm"] = -(capex_q.rolling(4, min_periods=4).sum())

    # EBITDA TTM = EBIT TTM + D&A TTM
    if "ebit_ttm" in s.columns:
        da_ttm = s.get("da_ttm", pd.Series(0, index=s.index)).fillna(0)
        s["ebitda_ttm"] = s["ebit_ttm"] + da_ttm

    # FCF TTM = CFO TTM - Capex TTM
    if "cfo_ttm" in s.columns and "capex_ttm" in s.columns:
        s["fcf_ttm"] = s["cfo_ttm"] - s["capex_ttm"]

    # ── Preço e Market Cap ───────────────────────────────────────────────────
    s["preco"] = pd.Series(prices, dtype=float).reindex(s.index)
    # Market cap em R$ MIL (escala dos demonstrativos): price(R$/ação) × shares / 1000
    s["market_cap"] = s["preco"] * shares / 1_000.0

    # ── Dívida Líquida ───────────────────────────────────────────────────────
    cash_total = (
        s.get("cash_eq",  pd.Series(0, index=s.index)).fillna(0)
        + s.get("fin_apps", pd.Series(0, index=s.index)).fillna(0)
    )
    liab = s.get("liab_total", pd.Series(np.nan, index=s.index))
    s["divida_liquida"]   = liab - cash_total
    s["enterprise_value"] = s["market_cap"] + s["divida_liquida"]

    # ── Múltiplos ─────────────────────────────────────────────────────────────
    out = pd.DataFrame(index=s.index)

    out["mkt_preco_fechamento"]     = s["preco"]
    out["mkt_shares_outstanding"]   = float(shares)
    out["mkt_market_cap"]           = s["market_cap"]
    out["mkt_enterprise_value"]     = s["enterprise_value"]
    out["mkt_divida_liquida"]       = s["divida_liquida"]
    out["mkt_dividendos_pagos_ttm"] = s.get(
        "dividends_paid_ttm", pd.Series(np.nan, index=s.index)
    ).abs()

    mc = s["market_cap"]
    ev = s["enterprise_value"]

    if "net_income_ttm" in s.columns:
        out["mkt_pl_ttm"]   = _col_div(mc, s["net_income_ttm"])
    if "equity" in s.columns:
        out["mkt_pvp"]      = _col_div(mc, s["equity"])
    if "revenue_ttm" in s.columns:
        out["mkt_ps_ttm"]   = _col_div(mc, s["revenue_ttm"])
    if "fcf_ttm" in s.columns:
        out["mkt_pfcf_ttm"] = _col_div(mc, s["fcf_ttm"])
    if "cfo_ttm" in s.columns:
        out["mkt_pcfo_ttm"] = _col_div(mc, s["cfo_ttm"])
    if "ebitda_ttm" in s.columns:
        out["mkt_ev_ebitda_ttm"]         = _col_div(ev, s["ebitda_ttm"])
        out["mkt_divida_liquida_ebitda_ttm"] = _col_div(s["divida_liquida"], s["ebitda_ttm"])
        out["mkt_divida_bruta_ebitda_ttm"]   = _col_div(liab, s["ebitda_ttm"])
    if "ebit_ttm" in s.columns:
        out["mkt_ev_ebit_ttm"]  = _col_div(ev, s["ebit_ttm"])
    if "revenue_ttm" in s.columns:
        out["mkt_ev_receita_ttm"] = _col_div(ev, s["revenue_ttm"])
    if "equity" in s.columns:
        out["mkt_divida_liquida_pl"] = _col_div(s["divida_liquida"], s["equity"])

    # Dividend Yield
    if "mkt_dividendos_pagos_ttm" in out.columns:
        out["mkt_dividend_yield_ttm"] = _col_div(
            out["mkt_dividendos_pagos_ttm"].abs(), mc
        )

    # Limpar infinitos e outliers extremos
    out = out.replace([np.inf, -np.inf], np.nan)
    ratio_cols = [c for c in out.columns if c.startswith("mkt_p") or c.startswith("mkt_ev")]
    for col in ratio_cols:
        out.loc[out[col].abs() > 500, col] = np.nan

    return out


def _col_div(a: pd.Series, b: pd.Series) -> pd.Series:
    """Divisão elemento a elemento com tratamento de zeros e infinitos."""
    b_safe = b.replace(0, np.nan)
    result = a / b_safe
    return result.replace([np.inf, -np.inf], np.nan)


# ─────────────────────────────────────────────────────────────────────────────
# Preços na data de referência de cada período
# ─────────────────────────────────────────────────────────────────────────────

def get_prices_by_period(
    conn: psycopg.Connection,
    tickers: list[str],
    periodos: pd.DataFrame,
) -> dict[str, dict[int, float]]:
    """
    Retorna {ticker: {periodo_id: close_price}} para todos os tickers e períodos.
    Usa o último pregão disponível até dt_referencia de cada período.
    """
    result: dict[str, dict[int, float]] = {t: {} for t in tickers}

    with conn.cursor(row_factory=dict_row) as cur:
        for _, per in periodos.iterrows():
            dt_ref = per["dt_referencia"]
            cur.execute(_SQL_LAST_PRICE_AT_DATE, {
                "tickers": tickers,
                "dt_ref": dt_ref,
            })
            rows = cur.fetchall()
            for r in rows:
                result[r["ticker"]][int(per["periodo_id"])] = float(r["preco"])

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Persistência em fato_indicadores
# ─────────────────────────────────────────────────────────────────────────────

def _load_indicador_ids(conn: psycopg.Connection, codes: list[str]) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SQL_INDICADOR_ID, {"codes": codes})
        return {r["codigo"]: r["indicador_id"] for r in cur.fetchall()}


def _flush_multiplos(
    conn: psycopg.Connection,
    empresa_id: int,
    multiplos: pd.DataFrame,
    indicador_ids: dict[str, int],
) -> int:
    """Faz upsert dos múltiplos calculados em fato_indicadores."""
    rows = []
    for periodo_id, row in multiplos.iterrows():
        for col, val in row.items():
            if col not in indicador_ids:
                continue
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            rows.append({
                "empresa_id": empresa_id,
                "periodo_id": int(periodo_id),
                "indicador_id": indicador_ids[col],
                "valor": float(val),
            })

    if rows:
        with conn.cursor() as cur:
            cur.executemany(_SQL_UPSERT, rows)
        conn.commit()

    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    full: bool = False,
    tickers_filter: Optional[list[str]] = None,
    fetch_shares: bool = True,
    batch_size: int = 20,
) -> None:
    conn = psycopg.connect(get_database_url(), row_factory=dict_row)
    try:
        # 1. Aplicar DDL se necessário
        _ensure_ddl(conn)

        # 2. Carregar empresas e períodos
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_SQL_EMPRESAS)
            empresas = [dict(r) for r in cur.fetchall()]

        if tickers_filter:
            tickers_filter = [t.upper() for t in tickers_filter]
            empresas = [e for e in empresas if e["ticker"] in tickers_filter]

        if not empresas:
            log.warning("Nenhuma empresa encontrada.")
            return

        # Deduplicar: cada ticker aponta para apenas um empresa_id
        empresa_map: dict[str, int] = {}
        for e in empresas:
            empresa_map[e["ticker"]] = e["empresa_id"]
        tickers = list(empresa_map.keys())
        log.info("Empresas carregadas: %d", len(empresas))

        # 3. Atualizar shares
        shares_map: dict[str, int] = {}
        if fetch_shares:
            shares_map = refresh_shares(conn, tickers)
        # Complementar com dados do banco (caso yfinance falhe para alguns)
        db_shares = load_shares_from_db(conn, tickers)
        for t, s in db_shares.items():
            if t not in shares_map:
                shares_map[t] = s

        tickers_with_shares = [t for t in tickers if t in shares_map]
        if not tickers_with_shares:
            log.error("Nenhum ticker com shares disponíveis.")
            return
        log.info("Tickers com shares: %d / %d", len(tickers_with_shares), len(tickers))

        # 4. Carregar indicador IDs do catálogo
        from sql.catalog import MULTIPLOS_MKT_CODES
        indicador_ids = _load_indicador_ids(conn, MULTIPLOS_MKT_CODES)
        missing = [c for c in MULTIPLOS_MKT_CODES if c not in indicador_ids]
        if missing:
            log.warning("Códigos não encontrados no catálogo: %s", missing)
            log.warning("Execute sql/schema.py --sync-catalog para registrar.")

        # 5. Carregar períodos
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_SQL_PERIODOS)
            periodos_all = pd.DataFrame(cur.fetchall())
        periodos_all["dt_referencia"] = pd.to_datetime(periodos_all["dt_referencia"])

        # 6. Descobrir empresas já completamente calculadas (incremental por empresa)
        empresa_ids_all = [empresa_map[t] for t in tickers_with_shares]
        done_empresa_ids: set[int] = set()
        if not full:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(_SQL_EMPRESA_DONE, {"empresa_ids": empresa_ids_all})
                done_empresa_ids = {r["empresa_id"] for r in cur.fetchall()}
            log.info("Empresas já calculadas (incremental): %d", len(done_empresa_ids))

        # 7. Processar em lotes de tickers para não sobrecarregar memória
        total_rows = 0
        for batch_start in range(0, len(tickers_with_shares), batch_size):
            batch_tickers = tickers_with_shares[batch_start: batch_start + batch_size]
            batch_ids = [empresa_map[t] for t in batch_tickers]

            log.info(
                "Lote %d-%d / %d: %s ...",
                batch_start + 1,
                min(batch_start + batch_size, len(tickers_with_shares)),
                len(tickers_with_shares),
                batch_tickers[:3],
            )

            # Carregar dados fundamentais do banco para o lote
            periodos_df, bp_df, dre_df, dfc_df = load_fundamentos(conn, batch_ids)

            # Filtrar períodos disponíveis para este lote (interseção com periodos_all)
            pids_with_data: set[int] = set()
            for _df in [bp_df, dre_df, dfc_df]:
                if not _df.empty and "periodo_id" in _df.columns:
                    pids_with_data.update(_df["periodo_id"].tolist())
            periodos_lote = periodos_all[periodos_all["periodo_id"].isin(pids_with_data)]

            if periodos_lote.empty:
                log.debug("Sem dados de demonstrativos para lote: %s", batch_tickers)
                continue

            # Obter preços por período para cada ticker do lote
            prices_by_ticker = get_prices_by_period(conn, batch_tickers, periodos_lote)

            for ticker in batch_tickers:
                empresa_id = empresa_map[ticker]
                # Skip se empresa já foi completamente calculada (incremental)
                if not full and empresa_id in done_empresa_ids:
                    log.debug("  %s: já calculado, skip", ticker)
                    continue
                shares = shares_map[ticker]
                prices_for_ticker = prices_by_ticker.get(ticker, {})

                if not prices_for_ticker:
                    log.debug("Sem preços: %s", ticker)
                    continue

                try:
                    multiplos = _build_company_series(
                        empresa_id=empresa_id,
                        periodos=periodos_lote,
                        bp_all=bp_df,
                        dre_all=dre_df,
                        dfc_all=dfc_df,
                        prices=prices_for_ticker,
                        shares=shares,
                    )
                except Exception as exc:
                    log.error("Erro ao calcular múltiplos %s: %s", ticker, exc, exc_info=True)
                    continue

                if multiplos.empty:
                    continue

                n = _flush_multiplos(conn, empresa_id, multiplos, indicador_ids)
                total_rows += n
                log.debug("  %s: %d registros persistidos", ticker, n)

        log.info("Pipeline concluído. Total de registros: %d", total_rows)

    finally:
        conn.close()


def _ensure_ddl(conn: psycopg.Connection) -> None:
    """Aplica DDL de tb_acoes_shares se a tabela não existir."""
    ddl_path = __file__.replace("pipeline/etl/multiplos_mercado.py", "sql/ddl_acoes_shares.sql")
    ddl_path = ddl_path.replace("\\pipeline\\etl\\multiplos_mercado.py", "\\sql\\ddl_acoes_shares.sql")
    import os
    from pathlib import Path
    # Localizar DDL de forma robusta
    base = Path(__file__).parent.parent.parent
    ddl = base / "sql" / "ddl_acoes_shares.sql"
    if ddl.exists():
        sql = ddl.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL de múltiplos de mercado fundamentalistas.")
    p.add_argument("--full", action="store_true", help="Recalcular tudo (ignora cache).")
    p.add_argument("--no-fetch-shares", dest="fetch_shares", action="store_false",
                   help="Não buscar shares via yfinance (usa apenas o banco).")
    p.add_argument("--tickers", nargs="*", help="Lista de tickers para processar.")
    p.add_argument("--batch-size", type=int, default=20, help="Tickers por lote.")
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()
    run_pipeline(
        full=args.full,
        tickers_filter=args.tickers,
        fetch_shares=args.fetch_shares,
        batch_size=args.batch_size,
    )
