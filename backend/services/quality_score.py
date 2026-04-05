"""
Recency-Weighted Quality Score Engine.

Filosofia: o presente vale mais que o passado.
Usa EWA (exponentially weighted average) com duas meia-vidas
(curta para score recente, longa para score estrutural) e
detecta tendências de melhora/deterioração.

Score final:
    α · score_recente + (1-α) · score_estrutural
    - penalidade_deterioração
    + bônus_melhoria
    + ajuste_consistência
"""

from __future__ import annotations

import math
import time
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta
from typing import Any

# ── Indicador config ────────────────────────────────────────────────────────

INDICATOR_CONFIG: dict[str, dict[str, Any]] = {
    # Rentabilidade e Eficiência (35%)
    "cmb_roe":                {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "ROE"},
    "cmb_roa":                {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "ROA"},
    "cmb_roic":               {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "ROIC"},
    "cmb_giro_ativo":         {"block": "rentabilidade", "hb": True,  "unit": "ratio", "label": "Giro do Ativo"},
    "dre_margem_bruta":       {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "Margem Bruta"},
    "dre_margem_ebit":        {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "Margem EBIT"},
    "dre_margem_ebitda":      {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "Margem EBITDA"},
    "dre_margem_liquida":     {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "Margem Líquida"},
    "dre_margem_operacional": {"block": "rentabilidade", "hb": True,  "unit": "pct",   "label": "Margem Operacional"},
    "dre_custo_sobre_receita":{"block": "rentabilidade", "hb": False, "unit": "ratio", "label": "Custo/Receita"},

    # Solidez Financeira (25%)
    "bp_liquidez_corrente":           {"block": "solidez", "hb": True,  "unit": "ratio", "label": "Liquidez Corrente"},
    "bp_liquidez_seca":               {"block": "solidez", "hb": True,  "unit": "ratio", "label": "Liquidez Seca"},
    "bp_liquidez_imediata":           {"block": "solidez", "hb": True,  "unit": "ratio", "label": "Liquidez Imediata"},
    "bp_passivo_sobre_ativo":         {"block": "solidez", "hb": False, "unit": "ratio", "label": "Passivo/Ativo"},
    "bp_pl_sobre_ativo":              {"block": "solidez", "hb": True,  "unit": "ratio", "label": "PL/Ativo"},
    "bp_equity_multiplier":           {"block": "solidez", "hb": False, "unit": "ratio", "label": "Equity Multiplier"},
    "bp_grau_alavancagem_patrimonial":{"block": "solidez", "hb": False, "unit": "ratio", "label": "Alavancagem"},

    # Geração de Caixa e Qualidade Contábil (20%)
    "dfc_cfo_sobre_receita":      {"block": "caixa", "hb": True,  "unit": "ratio", "label": "CFO/Receita"},
    "dfc_accrual_ratio":          {"block": "caixa", "hb": False, "unit": "ratio", "label": "Accrual Ratio"},
    "bp_capital_giro_sobre_ativo":{"block": "caixa", "hb": True,  "unit": "ratio", "label": "Cap Giro/Ativo"},
    "bp_caixa_sobre_ativo":       {"block": "caixa", "hb": True,  "unit": "ratio", "label": "Caixa/Ativo"},
    "bp_estoques_sobre_ativo":    {"block": "caixa", "hb": False, "unit": "ratio", "label": "Estoques/Ativo"},
    "bp_imobilizado_sobre_ativo": {"block": "caixa", "hb": False, "unit": "ratio", "label": "Imobilizado/Ativo"},

    # Consistência Quantitativa (20%)
    "mkt_sharpe_252d":            {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Sharpe 252d"},
    "mkt_sharpe_126d":            {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Sharpe 126d"},
    "mkt_sharpe_63d":             {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Sharpe 63d"},
    "mkt_sharpe_21d":             {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Sharpe 21d"},
    "mkt_sortino_252d":           {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Sortino 252d"},
    "mkt_beta_252d":              {"block": "quantitativo", "hb": False, "unit": "ratio", "label": "Beta 252d"},
    "mkt_max_drawdown_252d":      {"block": "quantitativo", "hb": False, "unit": "pct",   "label": "Max DD 252d"},
    "mkt_volatility_252d":        {"block": "quantitativo", "hb": False, "unit": "pct",   "label": "Volatilidade"},
    "mkt_jensen_alpha_252d":      {"block": "quantitativo", "hb": True,  "unit": "pct",   "label": "Alpha Jensen"},
    "mkt_calmar_ratio_252d":      {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Calmar Ratio"},
    "mkt_omega_ratio_252d":       {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Omega Ratio"},
    "mkt_var_252d":               {"block": "quantitativo", "hb": False, "unit": "ratio", "label": "VaR 252d"},
    "mkt_information_ratio_252d": {"block": "quantitativo", "hb": True,  "unit": "ratio", "label": "Info Ratio"},
    "mkt_tracking_error_252d":    {"block": "quantitativo", "hb": False, "unit": "pct",   "label": "Tracking Error"},
}

BLOCK_WEIGHTS = {
    "rentabilidade": 0.35,
    "solidez": 0.25,
    "caixa": 0.20,
    "quantitativo": 0.20,
}

ALL_CODES = list(INDICATOR_CONFIG.keys())

# ── Parâmetros de recência ──────────────────────────────────────────────────

RECENT_HL_FUND = 182     # meia-vida curta: 2 trimestres (dias)
STRUCTURAL_HL_FUND = 548  # meia-vida longa: 6 trimestres
RECENT_HL_QUANT = 122    # meia-vida curta: 4 meses
STRUCTURAL_HL_QUANT = 365 # meia-vida longa: 12 meses

LOOKBACK_DAYS = 4 * 365   # janela de 4 anos

ALPHA = 0.70               # 70% recente, 30% estrutural
DETERIORATION_THR = 0.08   # 8% de piora relativa → penalidade
IMPROVEMENT_THR = 0.08     # 8% de melhora relativa → bônus
MAX_DET_PENALTY = 8.0
MAX_IMP_BONUS = 5.0

MIN_TOTAL_COVERAGE = 0.35
MIN_BLOCKS = 3
MIN_SERIES_LEN = 2         # mínimo de observações por indicador

# ── SQL ─────────────────────────────────────────────────────────────────────

FETCH_SQL = """
SELECT
    ticker, empresa, indicador_codigo, valor, dt_referencia
FROM track_stocks.vw_indicadores_historicos
WHERE indicador_codigo = ANY(%s)
  AND valor IS NOT NULL
  AND ticker IS NOT NULL AND ticker != ''
  AND (
      (indicador_codigo LIKE 'mkt_%%' AND freq = 'M')
      OR (indicador_codigo NOT LIKE 'mkt_%%' AND freq IN ('T', 'A'))
  )
  AND dt_referencia >= %s
ORDER BY ticker, indicador_codigo, dt_referencia ASC
"""

# ── Cache ───────────────────────────────────────────────────────────────────

_cache: dict[str, Any] = {}
_CACHE_TTL = 300


# ── Funções auxiliares ──────────────────────────────────────────────────────

def _parse_date(val: Any) -> date:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val[:10])
    return date.today()


def _ewa(
    series: list[tuple[date, float]],
    half_life_days: float,
    ref_date: date,
) -> float | None:
    """Exponentially weighted average com meia-vida em dias."""
    if not series:
        return None
    lam = math.log(2) / half_life_days
    tw = 0.0
    twv = 0.0
    for dt, val in series:
        age = max(0, (ref_date - dt).days)
        w = math.exp(-lam * age)
        tw += w
        twv += w * val
    return twv / tw if tw > 1e-12 else None


def _percentile_rank(sorted_vals: list[float], value: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 50.0
    left = bisect_left(sorted_vals, value)
    right = bisect_right(sorted_vals, value)
    return ((left + right) / (2 * n)) * 100


def _format_value(value: float, unit: str) -> str:
    if unit == "pct":
        return f"{value * 100:.1f}%"
    return f"{value:.2f}"


def _half_lives(code: str) -> tuple[float, float]:
    """Retorna (recent_hl, structural_hl) em dias conforme tipo do indicador."""
    if code.startswith("mkt_"):
        return RECENT_HL_QUANT, STRUCTURAL_HL_QUANT
    return RECENT_HL_FUND, STRUCTURAL_HL_FUND


def _consistency_adj(block_scores: dict[str, float | None]) -> float:
    vals = [v for v in block_scores.values() if v is not None]
    if len(vals) < 2:
        return 0.0
    mn = min(vals)
    mean = sum(vals) / len(vals)
    if mn < 20:
        return -8.0
    if mn < 30:
        return -4.0
    if mn >= 60 and mean >= 75:
        return 5.0
    if mn >= 50 and mean >= 65:
        return 3.0
    return 0.0


# ── Pipeline principal ──────────────────────────────────────────────────────

def compute_rankings(cursor) -> list[dict]:
    now = time.time()
    if "rankings" in _cache and now - _cache["rankings"]["ts"] < _CACHE_TTL:
        return _cache["rankings"]["data"]

    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)
    cursor.execute(FETCH_SQL, (ALL_CODES, cutoff))
    rows = cursor.fetchall()

    series, empresa_map = _ingest(rows)
    if not series:
        return []

    ref_date = _global_ref_date(series)
    ewa_recent, ewa_struct = _compute_ewas(series, ref_date)

    qualified = _filter(ewa_recent)
    if not qualified:
        return []

    pct_recent = _cross_sectional_rank(ewa_recent, qualified)
    pct_struct = _cross_sectional_rank(ewa_struct, qualified)

    trends = _compute_trends(ewa_recent, ewa_struct)

    results = _assemble(
        qualified, pct_recent, pct_struct, trends,
        ewa_recent, empresa_map, ref_date,
    )

    results.sort(key=lambda x: x["quality_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    _cache["rankings"] = {"data": results, "ts": time.time()}
    return results


# ── Etapas ──────────────────────────────────────────────────────────────────

SeriesMap = dict[str, dict[str, list[tuple[date, float]]]]


def _ingest(rows: list[dict]) -> tuple[SeriesMap, dict[str, str]]:
    series: SeriesMap = {}
    empresa: dict[str, str] = {}
    for r in rows:
        tk = r["ticker"]
        code = r["indicador_codigo"]
        val = r["valor"]
        if val is None or code not in INDICATOR_CONFIG:
            continue
        dt = _parse_date(r["dt_referencia"])
        series.setdefault(tk, {}).setdefault(code, []).append((dt, float(val)))
        if tk not in empresa:
            empresa[tk] = r.get("empresa") or tk
    return series, empresa


def _global_ref_date(series: SeriesMap) -> date:
    max_dt = date(2000, 1, 1)
    for inds in series.values():
        for pts in inds.values():
            if pts:
                max_dt = max(max_dt, pts[-1][0])
    return max_dt


def _compute_ewas(
    series: SeriesMap, ref: date,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    recent: dict[str, dict[str, float]] = {}
    struct: dict[str, dict[str, float]] = {}
    for tk, inds in series.items():
        for code, pts in inds.items():
            if len(pts) < MIN_SERIES_LEN:
                continue
            hl_r, hl_s = _half_lives(code)
            val_r = _ewa(pts, hl_r, ref)
            val_s = _ewa(pts, hl_s, ref)
            if val_r is not None:
                recent.setdefault(tk, {})[code] = val_r
            if val_s is not None:
                struct.setdefault(tk, {})[code] = val_s
    return recent, struct


def _filter(ewa_recent: dict[str, dict[str, float]]) -> set[str]:
    total = len(ALL_CODES)
    qualified: set[str] = set()
    for tk, inds in ewa_recent.items():
        if len(inds) / total < MIN_TOTAL_COVERAGE:
            continue
        blocks_present = {INDICATOR_CONFIG[c]["block"] for c in inds}
        if len(blocks_present) < MIN_BLOCKS:
            continue
        qualified.add(tk)
    return qualified


def _cross_sectional_rank(
    ewa_map: dict[str, dict[str, float]],
    qualified: set[str],
) -> dict[str, dict[str, float]]:
    """Percentile rank cross-sectional de cada indicador."""
    ind_vals: dict[str, list[float]] = {}
    for tk in qualified:
        for code, val in ewa_map.get(tk, {}).items():
            ind_vals.setdefault(code, []).append(val)
    for code in ind_vals:
        ind_vals[code].sort()

    result: dict[str, dict[str, float]] = {}
    for tk in qualified:
        result[tk] = {}
        for code, val in ewa_map.get(tk, {}).items():
            if code not in ind_vals:
                continue
            pct = _percentile_rank(ind_vals[code], val)
            if not INDICATOR_CONFIG[code]["hb"]:
                pct = 100.0 - pct
            result[tk][code] = pct
    return result


def _compute_trends(
    recent: dict[str, dict[str, float]],
    struct: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Trend = (ewa_short - ewa_long) / |ewa_long|, ajustado por direção."""
    trends: dict[str, dict[str, float]] = {}
    for tk in recent:
        trends[tk] = {}
        for code, val_r in recent[tk].items():
            val_s = struct.get(tk, {}).get(code)
            if val_s is None or abs(val_s) < 1e-10:
                trends[tk][code] = 0.0
                continue
            raw = (val_r - val_s) / abs(val_s)
            hb = INDICATOR_CONFIG[code]["hb"]
            trends[tk][code] = raw if hb else -raw
    return trends


def _assemble(
    qualified: set[str],
    pct_recent: dict[str, dict[str, float]],
    pct_struct: dict[str, dict[str, float]],
    trends: dict[str, dict[str, float]],
    ewa_recent: dict[str, dict[str, float]],
    empresa_map: dict[str, str],
    ref_date: date,
) -> list[dict]:
    results = []

    for tk in qualified:
        pr = pct_recent.get(tk, {})
        ps = pct_struct.get(tk, {})
        tr = trends.get(tk, {})
        raw = ewa_recent.get(tk, {})

        block_recent = _block_avg(pr)
        block_struct = _block_avg(ps)

        score_r = sum(
            (block_recent.get(b) or 0) * w
            for b, w in BLOCK_WEIGHTS.items()
        ) / sum(BLOCK_WEIGHTS.values())

        score_s = sum(
            (block_struct.get(b) or 0) * w
            for b, w in BLOCK_WEIGHTS.items()
        ) / sum(BLOCK_WEIGHTS.values())

        det_pen, imp_bon, trend_label = _trend_adjustments(tr)
        consist = _consistency_adj(block_recent)

        final = ALPHA * score_r + (1 - ALPHA) * score_s - det_pen + imp_bon + consist
        final = min(100, max(0, round(final)))

        drivers, red_flags = _extract_drivers(pr, raw)

        bloco_scores = {}
        for b in BLOCK_WEIGHTS:
            r_val = block_recent.get(b)
            s_val = block_struct.get(b)
            if r_val is not None and s_val is not None:
                bloco_scores[b] = round(ALPHA * r_val + (1 - ALPHA) * s_val)
            elif r_val is not None:
                bloco_scores[b] = round(r_val)
            else:
                bloco_scores[b] = 0

        results.append({
            "ticker": tk,
            "empresa": empresa_map.get(tk, tk),
            "setor": "",
            "rank": 0,
            "quality_score": final,
            "score_recent": round(score_r),
            "score_structural": round(score_s),
            "deterioration_penalty": round(det_pen, 1),
            "improvement_bonus": round(imp_bon, 1),
            "trend": trend_label,
            "bloco_scores": bloco_scores,
            "drivers": drivers,
            "red_flags": red_flags,
            "data_coverage": round(len(raw) / len(ALL_CODES), 2),
        })

    return results


def _block_avg(pcts: dict[str, float]) -> dict[str, float | None]:
    buckets: dict[str, list[float]] = {b: [] for b in BLOCK_WEIGHTS}
    for code, val in pcts.items():
        block = INDICATOR_CONFIG[code]["block"]
        buckets[block].append(val)
    return {
        b: (sum(v) / len(v) if v else None)
        for b, v in buckets.items()
    }


def _trend_adjustments(
    trend_map: dict[str, float],
) -> tuple[float, float, str]:
    if not trend_map:
        return 0.0, 0.0, "stable"

    vals = list(trend_map.values())
    avg_trend = sum(vals) / len(vals)
    neg_count = sum(1 for v in vals if v < -DETERIORATION_THR)
    pos_count = sum(1 for v in vals if v > IMPROVEMENT_THR)
    neg_frac = neg_count / len(vals)
    pos_frac = pos_count / len(vals)

    det_pen = 0.0
    if neg_frac > 0.3:
        det_pen = min(MAX_DET_PENALTY, neg_frac * MAX_DET_PENALTY * 1.5)
    elif avg_trend < -DETERIORATION_THR:
        det_pen = min(MAX_DET_PENALTY, abs(avg_trend) * MAX_DET_PENALTY * 2)

    imp_bon = 0.0
    if pos_frac > 0.3:
        imp_bon = min(MAX_IMP_BONUS, pos_frac * MAX_IMP_BONUS * 1.2)
    elif avg_trend > IMPROVEMENT_THR:
        imp_bon = min(MAX_IMP_BONUS, avg_trend * MAX_IMP_BONUS * 1.5)

    if det_pen > 2:
        label = "deteriorating"
    elif imp_bon > 1:
        label = "improving"
    else:
        label = "stable"

    return det_pen, imp_bon, label


def _extract_drivers(
    pcts: dict[str, float],
    raw_values: dict[str, float],
) -> tuple[list[dict], list[dict]]:
    sorted_inds = sorted(pcts.items(), key=lambda x: x[1], reverse=True)

    drivers = []
    for code, pct in sorted_inds[:4]:
        cfg = INDICATOR_CONFIG[code]
        val = raw_values.get(code, 0)
        drivers.append({
            "indicator": code,
            "name": cfg["label"],
            "value": _format_value(val, cfg["unit"]),
            "percentile": round(pct, 1),
            "good": True,
        })

    red_flags = []
    for code, pct in reversed(sorted_inds):
        if pct >= 25 or len(red_flags) >= 2:
            break
        cfg = INDICATOR_CONFIG[code]
        val = raw_values.get(code, 0)
        red_flags.append({
            "indicator": code,
            "name": cfg["label"],
            "value": _format_value(val, cfg["unit"]),
            "percentile": round(pct, 1),
            "good": False,
        })

    return drivers, red_flags
