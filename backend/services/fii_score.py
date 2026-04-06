"""
Recency-Weighted Quality Score Engine — FIIs.

Mesma filosofia do quality_score.py para ações:
  score_final = α·score_recente + (1-α)·score_estrutural
                - penalidade_deterioração
                + bônus_melhoria
                + ajuste_consistência

Diferenças:
  - Indicadores FII (fii_*), todos com freq='M'
  - 4 blocos: solidez, portfolio, distribuicao, eficiencia
  - Meia-vida curta ~3 meses (90d), longa ~12 meses (365d)

Sanidade:
  Antes do score, um filtro remove fundos com dados inválidos:
  cotistas <= 0, VPC <= 0, PL <= 0, dados desatualizados, etc.
"""

from __future__ import annotations

import logging
import math
import time
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── Indicadores FII ──────────────────────────────────────────────────────────

FII_INDICATOR_CONFIG: dict[str, dict[str, Any]] = {
    # Solidez Patrimonial (30%)
    "fii_passivo_sobre_ativo":          {"block": "solidez",      "hb": False, "unit": "ratio", "label": "Passivo/Ativo"},
    "fii_passivo_sobre_pl":             {"block": "solidez",      "hb": False, "unit": "ratio", "label": "Passivo/PL"},
    "fii_disponibilidades_sobre_ativo": {"block": "solidez",      "hb": True,  "unit": "ratio", "label": "Disponib./Ativo"},

    # Portfólio / Composição (30%)
    "fii_pct_total_investido":          {"block": "portfolio",    "hb": True,  "unit": "pct",   "label": "Total Investido"},
    "fii_pct_caixa":                    {"block": "portfolio",    "hb": True,  "unit": "pct",   "label": "% Caixa"},
    "fii_pct_liquidez":                 {"block": "portfolio",    "hb": True,  "unit": "pct",   "label": "% Liquidez"},
    "fii_pct_imoveis":                  {"block": "portfolio",    "hb": True,  "unit": "pct",   "label": "% Imóveis"},
    "fii_pct_cri_cra":                  {"block": "portfolio",    "hb": True,  "unit": "pct",   "label": "% CRI/CRA"},

    # Distribuição / Proventos (25%)
    "fii_dy_mes":                       {"block": "distribuicao", "hb": True,  "unit": "pct",   "label": "DY Mensal"},
    "fii_dy_anual":                     {"block": "distribuicao", "hb": True,  "unit": "pct",   "label": "DY Anual (12M)"},
    "fii_rendimentos_sobre_pl":         {"block": "distribuicao", "hb": True,  "unit": "pct",   "label": "Rend./PL"},

    # Eficiência de Custos (15%)
    "fii_pct_despesas_adm":             {"block": "eficiencia",   "hb": False, "unit": "pct",   "label": "Despesas ADM"},
    "fii_taxa_adm_pagar_sobre_pl":      {"block": "eficiencia",   "hb": False, "unit": "ratio", "label": "Taxa ADM/PL"},
}

FII_BLOCK_WEIGHTS = {
    "solidez":      0.30,
    "portfolio":    0.30,
    "distribuicao": 0.25,
    "eficiencia":   0.15,
}

ALL_FII_CODES = list(FII_INDICATOR_CONFIG.keys())

# ── Parâmetros de recência (mensais → meia-vida em dias) ────────────────────

RECENT_HL  = 90    # ~3 meses
STRUCT_HL  = 365   # ~12 meses
LOOKBACK   = 3 * 365
ALPHA      = 0.70

DETERIORATION_THR = 0.08
IMPROVEMENT_THR   = 0.08
MAX_DET_PENALTY   = 8.0
MAX_IMP_BONUS     = 5.0

MIN_COVERAGE  = 0.30   # pelo menos 30% dos indicadores presentes
MIN_BLOCKS    = 2       # pelo menos 2 blocos presentes
MIN_SERIES    = 2       # pelo menos 2 observações por indicador

# ── Filtro de sanidade ────────────────────────────────────────────────────────
# Indicadores críticos para validação (fora do set de scoring)


# Indicadores críticos para sanidade (devem existir no banco com valores > 0)
SANITY_CODES = [
    "fii_total_cotistas",
    "fii_vpc",
    "fii_patrimonio_liquido",
]

# Threshold mínimo aceitável (busca o mais recente valor POSITIVO)
SANITY_THRESHOLDS: dict[str, dict] = {
    "fii_total_cotistas":    {"min": 2,    "reason": "cotista único (fundo patrimonial privado)"},
    "fii_vpc":               {"min": 0.01, "reason": "VPC nulo ou negativo"},
    "fii_patrimonio_liquido":{"min": 1.0,  "reason": "Patrimônio Líquido nulo"},
}

# Fundo deve ter ao menos 1 registro recente válido dentro dos últimos N dias
MAX_STALENESS_DAYS = 18 * 30   # ~18 meses

# Mínimo de meses de histórico para entrar no ranking
MIN_MONTHS_HISTORY = 3

# ── SQL ──────────────────────────────────────────────────────────────────────

FETCH_FII_SQL = """
SELECT
    e.cnpj_normalizado,
    e.razao_social                         AS nome_fundo,
    COALESCE(m.segmento_atuacao, 'Outros') AS segmento,
    i.codigo                               AS indicador_codigo,
    f.valor,
    p.dt_referencia
FROM track_stocks.fato_indicadores f
JOIN track_stocks.empresas    e ON e.empresa_id   = f.empresa_id
JOIN track_stocks.periodos    p ON p.periodo_id   = f.periodo_id
JOIN track_stocks.indicadores i ON i.indicador_id = f.indicador_id
LEFT JOIN track_stocks.tb_fiis_meta m ON m.empresa_id = e.empresa_id
WHERE i.codigo = ANY(%s)
  AND f.valor IS NOT NULL
  AND p.freq = 'M'
  AND p.dt_referencia >= %s
ORDER BY e.cnpj_normalizado, i.codigo, p.dt_referencia ASC
"""

# Busca o valor POSITIVO mais recente de cada indicador de sanidade por fundo.
# Usar valor > 0 garante que períodos com 0 (ex.: último mês sem cotistas)
# não desclassifiquem fundos que historicamente têm dados válidos.
FETCH_SANITY_SQL = """
SELECT DISTINCT ON (e.cnpj_normalizado, i.codigo)
    e.cnpj_normalizado,
    i.codigo  AS indicador_codigo,
    f.valor,
    p.dt_referencia
FROM track_stocks.fato_indicadores f
JOIN track_stocks.empresas    e ON e.empresa_id   = f.empresa_id
JOIN track_stocks.periodos    p ON p.periodo_id   = f.periodo_id
JOIN track_stocks.indicadores i ON i.indicador_id = f.indicador_id
WHERE i.codigo = ANY(%s)
  AND f.valor  > 0
  AND p.freq   = 'M'
  AND p.dt_referencia >= %s
ORDER BY e.cnpj_normalizado, i.codigo, p.dt_referencia DESC
"""

# ── Cache ─────────────────────────────────────────────────────────────────────

_cache: dict[str, Any] = {}
_CACHE_TTL = 300


# ── Helpers (idênticos ao quality_score.py) ──────────────────────────────────

def _parse_date(val: Any) -> date:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val[:10])
    return date.today()


def _ewa(series: list[tuple[date, float]], half_life: float, ref: date) -> float | None:
    if not series:
        return None
    lam = math.log(2) / half_life
    tw = twv = 0.0
    for dt, val in series:
        age = max(0, (ref - dt).days)
        w = math.exp(-lam * age)
        tw += w
        twv += w * val
    return twv / tw if tw > 1e-12 else None


def _percentile_rank(sorted_vals: list[float], value: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 50.0
    left  = bisect_left(sorted_vals, value)
    right = bisect_right(sorted_vals, value)
    return ((left + right) / (2 * n)) * 100


def _format_value(value: float, unit: str) -> str:
    if unit == "pct":
        return f"{value * 100:.1f}%"
    return f"{value:.2f}"


def _consistency_adj(block_scores: dict[str, float | None]) -> float:
    vals = [v for v in block_scores.values() if v is not None]
    if len(vals) < 2:
        return 0.0
    mn   = min(vals)
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


# ── Filtro de sanidade ────────────────────────────────────────────────────────

SanityResult = dict[str, list[str]]   # cnpj → lista de motivos de exclusão


def _sanity_filter(cursor, ref_date: date) -> tuple[set[str], SanityResult]:
    """
    Valida os FIIs com base em indicadores críticos e remove os inválidos.

    Estratégia:
    - Busca o valor POSITIVO mais recente de cada indicador de sanidade.
    - "sem dados" só exclui quando o indicador é absolutamente crítico
      (VPC e PL); para cotistas, tolera ausência.
    - Verifica staleness: dado mais recente positivo deve ser recente.
    - Verifica consistência VPC × PL/cotistas (ordem de grandeza).

    Retorna (cnpjs_validos, cnpjs_excluidos_com_motivos).
    """
    cutoff = date.today() - timedelta(days=LOOKBACK)
    cursor.execute(FETCH_SANITY_SQL, (SANITY_CODES, cutoff))
    rows = cursor.fetchall()

    # cnpj → código → (valor_positivo_mais_recente, dt)
    latest: dict[str, dict[str, tuple[float, date]]] = {}
    for r in rows:
        cnpj = r["cnpj_normalizado"]
        code = r["indicador_codigo"]
        val  = float(r["valor"])
        dt   = _parse_date(r["dt_referencia"])
        # val > 0 garantido pelo SQL, mas protege na tipagem
        if val > 0:
            latest.setdefault(cnpj, {})[code] = (val, dt)

    excluded: SanityResult = {}

    for cnpj, ind_map in latest.items():
        reasons: list[str] = []

        # ── 1. Thresholds mínimos ──────────────────────────────────────────
        for code, cfg in SANITY_THRESHOLDS.items():
            entry = ind_map.get(code)
            if entry is None:
                # Ausência de cotistas: warning, não exclusão automática
                if code == "fii_total_cotistas":
                    continue
                # Ausência de VPC ou PL: exclusão por falta de dado crítico
                reasons.append(f"sem valor positivo para {code} ({cfg['reason']})")
                continue
            val, _ = entry
            if val < cfg["min"]:
                reasons.append(
                    f"{code}={val:.4g} < mín {cfg['min']} ({cfg['reason']})"
                )

        # ── 2. Staleness — dado positivo deve ser recente ─────────────────
        if ind_map:
            most_recent = max(dt for _, dt in ind_map.values())
            staleness = (ref_date - most_recent).days
            if staleness > MAX_STALENESS_DAYS:
                reasons.append(
                    f"dado mais recente há {staleness // 30} meses "
                    f"(máx {MAX_STALENESS_DAYS // 30} meses)"
                )

        # ── 3. Sanidade de escala do VPC ─────────────────────────────────
        # Intervalo plausível para VPC de FIIs brasileiros: R$ 0,01 – R$ 10.000.000
        # Valores fora disso indicam erro de ingestão (ex.: coluna errada).
        vpc_e = ind_map.get("fii_vpc")
        if vpc_e:
            vpc = vpc_e[0]
            if not (0.01 <= vpc <= 10_000_000):
                reasons.append(
                    f"VPC={vpc:.4g} fora do intervalo plausível [0.01, 10M]"
                )

        if reasons:
            excluded[cnpj] = reasons

    valid = set(latest.keys()) - set(excluded.keys())

    n_total   = len(latest)
    n_excluded = len(excluded)
    n_valid   = len(valid)

    logger.info(
        "Sanidade FII: %d válidos / %d excluídos / %d candidatos",
        n_valid, n_excluded, n_total,
    )
    if n_excluded:
        for cnpj, reasons in list(excluded.items())[:5]:
            logger.debug("  EXCLUÍDO %s: %s", cnpj, "; ".join(reasons))

    return valid, excluded


# ── Pipeline principal ────────────────────────────────────────────────────────

SeriesMap = dict[str, dict[str, list[tuple[date, float]]]]


def compute_fii_rankings(cursor) -> list[dict]:
    now = time.time()
    if "fii_rankings" in _cache and now - _cache["fii_rankings"]["ts"] < _CACHE_TTL:
        return _cache["fii_rankings"]["data"]

    cutoff = date.today() - timedelta(days=LOOKBACK)
    cursor.execute(FETCH_FII_SQL, (ALL_FII_CODES, cutoff))
    rows = cursor.fetchall()

    series, meta_map = _ingest(rows)
    if not series:
        return []

    ref_date = _global_ref_date(series)

    # ── Filtro de sanidade (antes do score) ──────────────────────────────────
    valid_cnpjs, excluded = _sanity_filter(cursor, ref_date)
    _cache["fii_excluded"] = excluded  # salva para auditoria independente do resultado

    # Remove fundos inválidos das séries
    series   = {k: v for k, v in series.items()   if k in valid_cnpjs}
    meta_map = {k: v for k, v in meta_map.items() if k in valid_cnpjs}

    if not series:
        logger.warning("Nenhum FII passou o filtro de sanidade.")
        return []

    ewa_recent, ewa_struct = _compute_ewas(series, ref_date)
    qualified = _filter(ewa_recent)

    if not qualified:
        return []

    pct_recent = _cross_rank(ewa_recent, qualified)
    pct_struct = _cross_rank(ewa_struct, qualified)
    trends     = _compute_trends(ewa_recent, ewa_struct)

    results = _assemble(qualified, pct_recent, pct_struct, trends, ewa_recent, meta_map, ref_date)
    results.sort(key=lambda x: x["quality_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    _cache["fii_rankings"] = {"data": results, "ts": time.time()}
    _cache["fii_excluded"]  = excluded   # auditoria disponível via endpoint
    return results


def get_excluded_fiis() -> dict[str, list[str]]:
    """Retorna os FIIs excluídos na última execução do ranking (para auditoria)."""
    return _cache.get("fii_excluded", {})


def _ingest(rows: list) -> tuple[SeriesMap, dict[str, dict]]:
    series: SeriesMap = {}
    meta: dict[str, dict] = {}
    month_counts: dict[str, set[date]] = {}

    for r in rows:
        cnpj = r["cnpj_normalizado"]
        code = r["indicador_codigo"]
        val  = r["valor"]
        if val is None or code not in FII_INDICATOR_CONFIG:
            continue
        dt = _parse_date(r["dt_referencia"])
        series.setdefault(cnpj, {}).setdefault(code, []).append((dt, float(val)))
        month_counts.setdefault(cnpj, set()).add(dt)
        if cnpj not in meta:
            meta[cnpj] = {
                "nome_fundo": r.get("nome_fundo") or cnpj,
                "segmento":   r.get("segmento") or "Outros",
            }

    # Remove fundos com histórico insuficiente (< MIN_MONTHS_HISTORY meses distintos)
    short_history = {
        cnpj for cnpj, months in month_counts.items()
        if len(months) < MIN_MONTHS_HISTORY
    }
    if short_history:
        logger.debug(
            "Descartados %d FIIs por histórico < %d meses",
            len(short_history), MIN_MONTHS_HISTORY,
        )
    for cnpj in short_history:
        series.pop(cnpj, None)
        meta.pop(cnpj, None)

    return series, meta


def _global_ref_date(series: SeriesMap) -> date:
    mx = date(2000, 1, 1)
    for inds in series.values():
        for pts in inds.values():
            if pts:
                mx = max(mx, pts[-1][0])
    return mx


def _compute_ewas(series: SeriesMap, ref: date):
    recent: dict[str, dict[str, float]] = {}
    struct: dict[str, dict[str, float]] = {}
    for cnpj, inds in series.items():
        for code, pts in inds.items():
            if len(pts) < MIN_SERIES:
                continue
            val_r = _ewa(pts, RECENT_HL, ref)
            val_s = _ewa(pts, STRUCT_HL, ref)
            if val_r is not None:
                recent.setdefault(cnpj, {})[code] = val_r
            if val_s is not None:
                struct.setdefault(cnpj, {})[code] = val_s
    return recent, struct


def _filter(ewa_recent: dict[str, dict[str, float]]) -> set[str]:
    total = len(ALL_FII_CODES)
    qualified: set[str] = set()
    for cnpj, inds in ewa_recent.items():
        if len(inds) / total < MIN_COVERAGE:
            continue
        blocks = {FII_INDICATOR_CONFIG[c]["block"] for c in inds}
        if len(blocks) < MIN_BLOCKS:
            continue
        qualified.add(cnpj)
    return qualified


def _cross_rank(ewa_map: dict[str, dict[str, float]], qualified: set[str]):
    ind_vals: dict[str, list[float]] = {}
    for cnpj in qualified:
        for code, val in ewa_map.get(cnpj, {}).items():
            ind_vals.setdefault(code, []).append(val)
    for code in ind_vals:
        ind_vals[code].sort()

    result: dict[str, dict[str, float]] = {}
    for cnpj in qualified:
        result[cnpj] = {}
        for code, val in ewa_map.get(cnpj, {}).items():
            if code not in ind_vals:
                continue
            pct = _percentile_rank(ind_vals[code], val)
            if not FII_INDICATOR_CONFIG[code]["hb"]:
                pct = 100.0 - pct
            result[cnpj][code] = pct
    return result


def _compute_trends(recent: dict, struct: dict) -> dict[str, dict[str, float]]:
    trends: dict[str, dict[str, float]] = {}
    for cnpj in recent:
        trends[cnpj] = {}
        for code, val_r in recent[cnpj].items():
            val_s = struct.get(cnpj, {}).get(code)
            if val_s is None or abs(val_s) < 1e-10:
                trends[cnpj][code] = 0.0
                continue
            raw = (val_r - val_s) / abs(val_s)
            hb  = FII_INDICATOR_CONFIG[code]["hb"]
            trends[cnpj][code] = raw if hb else -raw
    return trends


def _block_avg(pcts: dict[str, float]) -> dict[str, float | None]:
    buckets: dict[str, list[float]] = {b: [] for b in FII_BLOCK_WEIGHTS}
    for code, val in pcts.items():
        block = FII_INDICATOR_CONFIG[code]["block"]
        buckets[block].append(val)
    return {b: (sum(v) / len(v) if v else None) for b, v in buckets.items()}


def _trend_adjustments(trend_map: dict[str, float]) -> tuple[float, float, str]:
    if not trend_map:
        return 0.0, 0.0, "stable"
    vals      = list(trend_map.values())
    avg_trend = sum(vals) / len(vals)
    neg_frac  = sum(1 for v in vals if v < -DETERIORATION_THR) / len(vals)
    pos_frac  = sum(1 for v in vals if v > IMPROVEMENT_THR)    / len(vals)

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


def _extract_drivers(pcts: dict[str, float], raw: dict[str, float]):
    sorted_inds = sorted(pcts.items(), key=lambda x: x[1], reverse=True)
    drivers = []
    for code, pct in sorted_inds[:4]:
        cfg = FII_INDICATOR_CONFIG[code]
        drivers.append({
            "indicator":  code,
            "name":       cfg["label"],
            "value":      _format_value(raw.get(code, 0), cfg["unit"]),
            "percentile": round(pct, 1),
            "good":       True,
        })
    red_flags = []
    for code, pct in reversed(sorted_inds):
        if pct >= 25 or len(red_flags) >= 2:
            break
        cfg = FII_INDICATOR_CONFIG[code]
        red_flags.append({
            "indicator":  code,
            "name":       cfg["label"],
            "value":      _format_value(raw.get(code, 0), cfg["unit"]),
            "percentile": round(pct, 1),
            "good":       False,
        })
    return drivers, red_flags


def _assemble(
    qualified: set[str],
    pct_recent: dict,
    pct_struct: dict,
    trends: dict,
    ewa_recent: dict,
    meta_map: dict[str, dict],
    ref_date: date,
) -> list[dict]:
    results = []
    for cnpj in qualified:
        pr  = pct_recent.get(cnpj, {})
        ps  = pct_struct.get(cnpj, {})
        tr  = trends.get(cnpj, {})
        raw = ewa_recent.get(cnpj, {})

        block_r = _block_avg(pr)
        block_s = _block_avg(ps)

        score_r = sum((block_r.get(b) or 0) * w for b, w in FII_BLOCK_WEIGHTS.items()) / sum(FII_BLOCK_WEIGHTS.values())
        score_s = sum((block_s.get(b) or 0) * w for b, w in FII_BLOCK_WEIGHTS.items()) / sum(FII_BLOCK_WEIGHTS.values())

        det_pen, imp_bon, trend_label = _trend_adjustments(tr)
        consist = _consistency_adj(block_r)

        final = ALPHA * score_r + (1 - ALPHA) * score_s - det_pen + imp_bon + consist
        final = int(min(100, max(0, round(final))))

        drivers, red_flags = _extract_drivers(pr, raw)

        bloco_scores = {}
        for b in FII_BLOCK_WEIGHTS:
            r_val = block_r.get(b)
            s_val = block_s.get(b)
            if r_val is not None and s_val is not None:
                bloco_scores[b] = round(ALPHA * r_val + (1 - ALPHA) * s_val)
            elif r_val is not None:
                bloco_scores[b] = round(r_val)
            else:
                bloco_scores[b] = 0

        meta = meta_map.get(cnpj, {})
        results.append({
            "cnpj":                  cnpj,
            "nome_fundo":            meta.get("nome_fundo", cnpj),
            "segmento":              meta.get("segmento", "Outros"),
            "rank":                  0,
            "quality_score":         final,
            "score_recent":          round(score_r),
            "score_structural":      round(score_s),
            "deterioration_penalty": round(det_pen, 1),
            "improvement_bonus":     round(imp_bon, 1),
            "trend":                 trend_label,
            "bloco_scores":          bloco_scores,
            "drivers":               drivers,
            "red_flags":             red_flags,
            "data_coverage":         round(len(raw) / len(ALL_FII_CODES), 2),
        })
    return results
