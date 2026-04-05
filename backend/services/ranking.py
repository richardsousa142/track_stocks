"""Cálculo de score composto para ranking de ativos."""

from __future__ import annotations

SCORE_INDICATORS = {
    "BP": {
        "weight": 0.25,
        "indicators": {
            "bp_liquidez_corrente": {"threshold": 1.5, "higher_better": True},
            "bp_liquidez_seca": {"threshold": 1.0, "higher_better": True},
            "bp_passivo_sobre_ativo": {"threshold": 0.65, "higher_better": False},
            "bp_pl_sobre_ativo": {"threshold": 0.35, "higher_better": True},
            "bp_equity_multiplier": {"threshold": 2.5, "higher_better": False},
        },
    },
    "DRE": {
        "weight": 0.30,
        "indicators": {
            "dre_margem_bruta": {"threshold": 0.25, "higher_better": True},
            "dre_margem_ebit": {"threshold": 0.10, "higher_better": True},
            "dre_margem_liquida": {"threshold": 0.08, "higher_better": True},
            "dre_cobertura_juros": {"threshold": 3.0, "higher_better": True},
        },
    },
    "DFC": {
        "weight": 0.20,
        "indicators": {
            "dfc_cfo_sobre_receita": {"threshold": 0.10, "higher_better": True},
            "dfc_accrual_ratio": {"threshold": 0.05, "higher_better": False},
        },
    },
    "CMB": {
        "weight": 0.15,
        "indicators": {
            "cmb_roe": {"threshold": 0.15, "higher_better": True},
            "cmb_roa": {"threshold": 0.08, "higher_better": True},
            "cmb_roic": {"threshold": 0.12, "higher_better": True},
        },
    },
    "MKT": {
        "weight": 0.10,
        "indicators": {
            "mkt_sharpe_252d": {"threshold": 0.5, "higher_better": True},
            "mkt_sortino_252d": {"threshold": 0.8, "higher_better": True},
            "mkt_beta_252d": {"threshold": 1.0, "higher_better": False},
        },
    },
}


def compute_score(indicator_values: dict[str, float]) -> int:
    """Calcula score composto 0-100 baseado nos indicadores fornecidos."""
    total_score = 0.0
    total_weight = 0.0

    for bloco, config in SCORE_INDICATORS.items():
        bloco_score = 0.0
        bloco_count = 0

        for code, meta in config["indicators"].items():
            val = indicator_values.get(code)
            if val is None:
                continue

            thr = meta["threshold"]
            hb = meta["higher_better"]

            if hb:
                ratio = val / thr if thr != 0 else 1.0
            else:
                ratio = thr / val if val != 0 else 1.0

            normalized = min(max(ratio * 50, 0), 100)
            bloco_score += normalized
            bloco_count += 1

        if bloco_count > 0:
            avg = bloco_score / bloco_count
            total_score += avg * config["weight"]
            total_weight += config["weight"]

    if total_weight == 0:
        return 50

    return int(round(total_score / total_weight))
