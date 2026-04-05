"""
Metricas quantitativas rolling (mensal por ticker).
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from tqdm import tqdm

from pipeline.config import (
    BENCHMARK_TICKER,
    MIN_OBS_FRACTION,
    MIN_ROLLING_OBS_FLOOR,
    RISK_FREE_ANNUAL,
    ROLLING_WINDOWS,
    THRESHOLD,
    TRADING_DAYS,
    VAR_CONFIDENCE,
    bvsp_parquet_for,
    historico_acoes_parquet_for,
    result_df_parquet_for,
)

log = logging.getLogger(__name__)


def load_price_data(base_dir: Path | None = None) -> pd.DataFrame:
    root = base_dir.resolve() if base_dir is not None else Path(".").resolve()
    df_acoes = pd.read_parquet(historico_acoes_parquet_for(root))
    df_bvsp = pd.read_parquet(bvsp_parquet_for(root))
    df_bvsp["data_pregao"] = pd.to_datetime(df_bvsp["data_pregao"]).dt.date
    df_g = pd.concat([df_acoes, df_bvsp], axis=0)
    df_filt = df_g[["data_pregao", "codneg", "premin", "premax", "preult", "voltot"]].copy()
    df_filt.dropna(inplace=True)
    return df_filt


def _max_drawdown(r: np.ndarray) -> float:
    if len(r) == 0:
        return np.nan
    equity      = np.cumprod(1.0 + r)
    running_max = np.maximum.accumulate(equity)
    mdd         = -np.min(equity / running_max - 1.0)
    return float(mdd) if np.isfinite(mdd) else np.nan

def _average_drawdown(r: np.ndarray) -> float:
    if len(r) == 0:
        return np.nan
    equity      = np.cumprod(1.0 + r)
    running_max = np.maximum.accumulate(equity)
    drawdown    = equity / running_max - 1.0
    neg_dd      = drawdown[drawdown < 0]
    return float(-neg_dd.mean()) if len(neg_dd) > 0 else 0.0

def _annualized_return(r: np.ndarray) -> float:
    n = len(r)
    if n == 0:
        return np.nan
    return float(np.prod(1.0 + r) ** (TRADING_DAYS / n) - 1.0)

def _compute_metrics(
    r:               np.ndarray,
    bm:              np.ndarray = None,
    risk_free_annual: float     = RISK_FREE_ANNUAL,
    var_confidence:   float     = VAR_CONFIDENCE,
    min_obs:          int       = MIN_ROLLING_OBS_FLOOR,
    threshold:        float     = THRESHOLD,
    ) -> dict:
    """
    Recebe arrays numpy de retornos diários (já fatiados) e devolve
    dicionário com todos os indicadores.
    Opera em numpy puro — sem criação de Series/DataFrame dentro do cálculo.
    """
    base = {
        "mean_return":       np.nan,
        "volatility":        np.nan,
        "sharpe":            np.nan,
        "adj_sharpe":        np.nan,
        "sortino":           np.nan,
        "var":               np.nan,
        "es":                np.nan,
        "max_drawdown":      np.nan,
        "avg_drawdown":      np.nan,
        "calmar_ratio":      np.nan,
        "sterling_ratio":    np.nan,
        "omega_ratio":       np.nan,
        "upside_potential":  np.nan,
        "beta":              np.nan,
        "jensen_alpha":      np.nan,
        "treynor_ratio":     np.nan,
        "information_ratio": np.nan,
        "tracking_error":    np.nan,
        "n_obs":             0,
    }

    n = len(r)
    base["n_obs"] = n

    if n < min_obs:
        return base

    rf_daily = (1.0 + risk_free_annual) ** (1.0 / TRADING_DAYS) - 1.0

    # ── Retorno e volatilidade ────────────────────────────────────────────────
    ann_ret = _annualized_return(r)
    std_d   = r.std(ddof=1)

    if not np.isfinite(std_d) or std_d <= 0 or not np.isfinite(ann_ret):
        base["mean_return"] = ann_ret
        return base

    ann_vol = std_d * np.sqrt(TRADING_DAYS)
    base["mean_return"] = ann_ret
    base["volatility"]  = ann_vol

    if ann_vol <= 0:
        return base

    # ── Sharpe ────────────────────────────────────────────────────────────────
    sharpe = (ann_ret - risk_free_annual) / ann_vol
    base["sharpe"] = sharpe

    # ── Adjusted Sharpe (Pézier & White, 2006) ────────────────────────────────
    if n >= 4:
        sk = float(np.clip(stats.skew(r, bias=False),                  -10.0, 10.0))
        ku = float(np.clip(stats.kurtosis(r, fisher=True, bias=False),  -10.0, 10.0))
        sr = float(np.clip(sharpe,                                       -10.0, 10.0))
        with np.errstate(over="ignore", invalid="ignore"):
            raw = sr * (1.0 + (sk / 6.0) * sr - (ku / 24.0) * sr ** 2)
        base["adj_sharpe"] = float(raw) if np.isfinite(raw) else np.nan

    # ── Sortino ───────────────────────────────────────────────────────────────
    excess   = r - rf_daily
    downside = excess[excess < 0]
    if len(downside) > 0:
        dd_std_ann = np.sqrt((downside ** 2).mean()) * np.sqrt(TRADING_DAYS)
        if np.isfinite(dd_std_ann) and dd_std_ann > 0:
            base["sortino"] = (ann_ret - risk_free_annual) / dd_std_ann

    # ── VaR / ES ──────────────────────────────────────────────────────────────
    var_threshold = np.percentile(r, (1.0 - var_confidence) * 100.0)
    base["var"]   = float(var_threshold)
    tail          = r[r <= var_threshold]
    base["es"]    = float(tail.mean()) if len(tail) > 0 else np.nan

    # ── Drawdowns ─────────────────────────────────────────────────────────────
    max_dd = _max_drawdown(r)
    avg_dd = _average_drawdown(r)
    base["max_drawdown"] = max_dd
    base["avg_drawdown"] = avg_dd

    if np.isfinite(max_dd) and max_dd > 0:
        base["calmar_ratio"]   = ann_ret / max_dd
    if np.isfinite(avg_dd) and avg_dd > 0:
        base["sterling_ratio"] = ann_ret / avg_dd

    # ── Omega Ratio ───────────────────────────────────────────────────────────
    exc_r = r - threshold
    pos_r = exc_r[exc_r > 0]
    neg_r = exc_r[exc_r <= 0]
    denom = np.abs(neg_r).sum()
    if denom > 0:
        base["omega_ratio"] = float(pos_r.sum() / denom)

    # ── Upside Potential Ratio ────────────────────────────────────────────────
    up_r  = r[r > threshold]
    bel_r = r[r <= threshold] - threshold
    if len(up_r) > 0 and len(bel_r) > 0:
        semi_var = np.sqrt((bel_r ** 2).mean())
        if np.isfinite(semi_var) and semi_var > 0:
            base["upside_potential"] = float(up_r.mean() / semi_var)

    # ── Benchmark-based ───────────────────────────────────────────────────────
    if bm is not None and len(bm) >= min_obs:
        var_m = bm.var(ddof=1)
        if np.isfinite(var_m) and var_m > 0:
            cov_pm      = np.cov(r, bm, ddof=1)[0, 1]
            beta        = cov_pm / var_m
            base["beta"] = float(beta)

            ann_mkt_ret = _annualized_return(bm)
            exp_ret     = risk_free_annual + beta * (ann_mkt_ret - risk_free_annual)
            base["jensen_alpha"] = float(ann_ret - exp_ret)

            if np.isfinite(beta) and beta != 0:
                base["treynor_ratio"] = float((ann_ret - risk_free_annual) / beta)

            active_r = r - bm
            te_d     = active_r.std(ddof=1)
            if np.isfinite(te_d) and te_d > 0:
                te_ann = te_d * np.sqrt(TRADING_DAYS)
                base["tracking_error"]    = float(te_ann)
                base["information_ratio"] = float((ann_ret - ann_mkt_ret) / te_ann)

    return base

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                          PIPELINE PRINCIPAL                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def compute_rolling_monthly_metrics(
    df:               pd.DataFrame,
    rolling_windows:  dict  = None,
    risk_free_annual: float = RISK_FREE_ANNUAL,
    var_confidence:   float = VAR_CONFIDENCE,
    threshold:        float = THRESHOLD,
    benchmark_ticker: str   = None,
    ) -> pd.DataFrame:
    """
    Calcula indicadores mensais com múltiplas janelas rolantes por ticker.

    Parâmetros
    ──────────
    df               : DataFrame com colunas ['data_pregao', 'codneg', 'preult'].
    rolling_windows  : dict {sufixo: n_pregões}. Default: ROLLING_WINDOWS global.
    risk_free_annual : Taxa livre de risco anual.
    var_confidence   : Nível de confiança do VaR/ES.
    threshold        : Threshold para Omega Ratio e Upside Potential.
    benchmark_ticker : Ticker do benchmark no mesmo DataFrame (ex.: '^BVSP').
                       Se None, métricas vs benchmark ficam NaN.

    Retorna
    ───────
    DataFrame com uma linha por (codneg × year_month).
    Colunas sufixadas por janela: sharpe_21d | sharpe_63d | sharpe_126d | ...
    """
    if rolling_windows is None:
        rolling_windows = ROLLING_WINDOWS

    if benchmark_ticker is None:
        benchmark_ticker = BENCHMARK_TICKER

    required_cols = {"data_pregao", "codneg", "preult"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    data = df[["data_pregao", "codneg", "preult"]].copy()
    data["data_pregao"] = pd.to_datetime(data["data_pregao"])
    data = data.sort_values(["codneg", "data_pregao"]).reset_index(drop=True)

    # Retorno diário por ticker — groupby garante isolamento total entre ativos.
    data["ret"] = data.groupby("codneg")["preult"].pct_change()

    # ── Pré-processa benchmark uma única vez ──────────────────────────────────
    # Resultado: array numpy de datas e retornos para busca via searchsorted.
    bm_dates   = None
    bm_returns = None
    if benchmark_ticker is not None:
        bm_df = data[data["codneg"] == benchmark_ticker].dropna(subset=["ret"])
        if len(bm_df) > 0:
            bm_dates   = bm_df["data_pregao"].values          # numpy datetime64
            bm_returns = bm_df["ret"].values.astype(float)
        else:
            log.warning(f"⚠️  benchmark_ticker '{benchmark_ticker}' não encontrado.")

    _metric_keys = [
        "mean_return", "volatility", "sharpe", "adj_sharpe", "sortino",
        "var", "es", "max_drawdown", "avg_drawdown", "calmar_ratio",
        "sterling_ratio", "omega_ratio", "upside_potential",
        "beta", "jensen_alpha", "treynor_ratio", "information_ratio",
        "tracking_error", "n_obs",
    ]

    results  = []
    tickers  = sorted(data["codneg"].unique())
    max_win  = max(rolling_windows.values())

    for ticker in tqdm(tickers, desc="Calculando métricas", unit="ticker"):
        tdf = data[data["codneg"] == ticker].dropna(subset=["ret"]).sort_values("data_pregao")

        # Arrays numpy — fatiamento O(1) via índice, sem varredura booleana
        t_dates   = tdf["data_pregao"].values          # datetime64
        t_returns = tdf["ret"].values.astype(float)

        # Último pregão de cada mês via resample — rápido e sem FutureWarning
        month_end_dates = (
            tdf.set_index("data_pregao")["ret"]
            .resample("ME")
            .apply(lambda x: x.index[-1] if len(x) > 0 else pd.NaT)
            .dropna()
            .values  # numpy datetime64
        )

        use_benchmark = (bm_dates is not None and ticker != benchmark_ticker)

        for end_date in month_end_dates:
            # searchsorted: encontra a posição de end_date em O(log n)
            # "right" retorna o índice após end_date → slice [:pos] inclui end_date
            pos = int(np.searchsorted(t_dates, end_date, side="right"))

            row = {
                "codneg":     ticker,
                "year_month": pd.Timestamp(end_date).to_period("M"),
                "window_end": pd.Timestamp(end_date),
            }

            for label, n_days in rolling_windows.items():
                min_obs = max(MIN_ROLLING_OBS_FLOOR, int(n_days * MIN_OBS_FRACTION))

                # Fatia direto por posição — O(1), sem varredura
                start  = max(0, pos - n_days)
                r_arr  = t_returns[start:pos]
                r_arr  = r_arr[np.isfinite(r_arr)]

                # Benchmark: mesmo período, alinhado por data via searchsorted
                bm_arr = None
                if use_benchmark:
                    bm_pos   = int(np.searchsorted(bm_dates, end_date, side="right"))
                    bm_start = max(0, bm_pos - n_days)
                    bm_raw   = bm_returns[bm_start:bm_pos]
                    bm_raw   = bm_raw[np.isfinite(bm_raw)]

                    # Alinhamento por tamanho: usa os N mais recentes de cada um
                    # (datas coincidem pois ambos são pregões B3 do mesmo período)
                    n_common = min(len(r_arr), len(bm_raw))
                    if n_common >= min_obs:
                        r_arr  = r_arr[-n_common:]
                        bm_arr = bm_raw[-n_common:]
                    else:
                        bm_arr = None

                metrics = _compute_metrics(
                    r=r_arr,
                    bm=bm_arr,
                    risk_free_annual=risk_free_annual,
                    var_confidence=var_confidence,
                    min_obs=min_obs,
                    threshold=threshold,
                )

                for key in _metric_keys:
                    row[f"{key}_{label}"] = metrics.get(key, np.nan)

            results.append(row)

    result_df = pd.DataFrame(results)

    id_cols   = ["codneg", "year_month", "window_end"]
    met_cols  = [
        f"{metric}_{label}"
        for metric in _metric_keys
        for label in rolling_windows.keys()
    ]
    col_order = [c for c in id_cols + met_cols if c in result_df.columns]

    return (
        result_df[col_order]
        .sort_values(["codneg", "window_end"])
        .reset_index(drop=True)
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Metricas quant rolling.")
    p.add_argument("--base-dir", type=str, default=".")
    p.add_argument("--historico", type=str, default=None)
    p.add_argument("--benchmark", type=str, default=None)
    p.add_argument("--output", type=str, default=None)
    args = p.parse_args()
    base = Path(args.base_dir).resolve()
    h = Path(args.historico) if args.historico else historico_acoes_parquet_for(base)
    b = Path(args.benchmark) if args.benchmark else bvsp_parquet_for(base)
    outp = Path(args.output) if args.output else result_df_parquet_for(base)
    df_acoes = pd.read_parquet(h)
    df_bvsp = pd.read_parquet(b)
    df_bvsp["data_pregao"] = pd.to_datetime(df_bvsp["data_pregao"]).dt.date
    df_g = pd.concat([df_acoes, df_bvsp], axis=0)
    df_filt = df_g[["data_pregao", "codneg", "premin", "premax", "preult", "voltot"]].copy()
    df_filt.dropna(inplace=True)
    out = compute_rolling_monthly_metrics(
        df_filt,
        rolling_windows=ROLLING_WINDOWS,
        risk_free_annual=RISK_FREE_ANNUAL,
        var_confidence=VAR_CONFIDENCE,
        threshold=THRESHOLD,
        benchmark_ticker=BENCHMARK_TICKER,
    )
    outp.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(outp, index=False)
    print(f"Salvo: {outp}")


if __name__ == "__main__":
    main()
