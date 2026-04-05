"""
Metadados do catálogo de indicadores — única fonte de verdade.
"""

from __future__ import annotations

from psycopg.types.json import Jsonb

INDICATOR_CODES = [
    "bp_liquidez_corrente", "bp_liquidez_seca", "bp_liquidez_imediata",
    "bp_capital_giro_liquido", "bp_capital_giro_sobre_ativo",
    "bp_cobertura_pc_por_caixa", "bp_passivo_sobre_ativo", "bp_pl_sobre_ativo",
    # ...
    "hst_receita_var_acumulada", "hst_lucro_var_acumulada",
]

# Múltiplos de mercado fundamentalistas (bloco MKT, camada 3)
MULTIPLOS_MKT_CODES = [
    # Preço e estrutura de capital
    "mkt_preco_fechamento",         # Close price na data de referência
    "mkt_shares_outstanding",       # Número de ações em circulação
    "mkt_market_cap",               # Market Cap (R$ mil)
    "mkt_enterprise_value",         # EV = Market Cap + Dívida Líquida (R$ mil)
    "mkt_divida_liquida",           # Dívida Líquida = Liab Total - Caixa - Aplic (R$ mil)
    # Múltiplos de preço
    "mkt_pl_ttm",                   # P/L TTM
    "mkt_pvp",                      # P/VP (Price to Book)
    "mkt_ps_ttm",                   # P/Receita TTM
    "mkt_pfcf_ttm",                 # P/FCF TTM
    "mkt_pcfo_ttm",                 # P/CFO TTM
    # Múltiplos EV
    "mkt_ev_ebitda_ttm",            # EV / EBITDA TTM
    "mkt_ev_ebit_ttm",              # EV / EBIT TTM
    "mkt_ev_receita_ttm",           # EV / Receita TTM
    # Dividendos
    "mkt_dividendos_pagos_ttm",     # Total dividendos + JCP pagos TTM (R$ mil)
    "mkt_dividend_yield_ttm",       # DY = Dividendos TTM / Market Cap
    # Dívida (sem preço)
    "mkt_divida_liquida_ebitda_ttm", # Dívida Líquida / EBITDA TTM
    "mkt_divida_liquida_pl",        # Dívida Líquida / Patrimônio Líquido
    "mkt_divida_bruta_ebitda_ttm",  # Dívida Bruta / EBITDA TTM
]

_QUANT_METRICS = [
    "mean_return", "volatility", "sharpe", "adj_sharpe", "sortino",
    "var", "es", "max_drawdown", "avg_drawdown", "calmar_ratio",
    "sterling_ratio", "omega_ratio", "upside_potential",
    "beta", "jensen_alpha", "treynor_ratio", "information_ratio",
    "tracking_error", "n_obs",
]
_QUANT_WINDOWS = ["21d", "63d", "126d", "252d"]

QUANT_INDICATOR_CODES = [
    f"mkt_{metric}_{window}"
    for metric in _QUANT_METRICS
    for window in _QUANT_WINDOWS
]

MOEDA_CODES = {
    # VAL — valores em R$
    "val_lpa", "val_vpa", "val_dpa_ttm",
    "val_graham", "val_bazin_6", "val_bazin_10",
    # MKT
    "mkt_preco_fechamento",
    "mkt_market_cap",
    "mkt_enterprise_value",
    "mkt_divida_liquida",
    "mkt_dividendos_pagos_ttm",
    "mkt_shares_outstanding",
    "bp_capital_giro_liquido",
    "dre_receita",
    "dre_mm_receita_4p",
    "dfc_cfo",
    "dfc_cfi",
    "dfc_cff",
    "dfc_capex_bruto",
    "dfc_investimento_liquido",
    "dfc_fcf_bruto",
    "dfc_fcf_liquido",
    "dfc_captacao_divida",
    "dfc_amortizacao_divida",
    "dfc_captacao_liquida_divida",
    "dfc_dividendos_pagos",
    "dfc_jscp_pagos",
    "dfc_proventos_totais_pagos",
    "dfc_aumento_capital",
    "dfc_custo_captacao",
    "dfc_pagamentos_arrendamento",
    "dfc_variacao_liquida_caixa",
    "dfc_saldo_inicial_caixa",
    "dfc_saldo_final_caixa",
    "dfc_queima_caixa",
    "dfc_reserva_liquidez",
    "cmb_diferenca_lucro_caixa",
}

PERCENTUAL_HINTS = (
    "_yoy", "_cagr_3a", "_drawdown", "_sazonalidade",
    "_margem_", "_aliquota_", "_tax_burden", "_crescimento_", "_pct",
    "mean_return", "volatility", "var", "es",
    "tracking_error",
    "dividend_yield",
    # VAL margens
    "val_margem_",
)

INDEX_HINTS = (
    "_volatilidade_", "_persistencia_", "_estabilidade_",
    "_tendencia_", "_reversao_",
)

RATIO_HINTS = (
    "_sobre_", "liquidez", "alavancagem", "equity_multiplier",
    "giro_", "intensidade", "conc_", "cobertura_juros",
    "cobertura_caixa_pc", "dependencia", "payout_ratio", "capex_ratio",
    "cash_conversion_ratio", "accrual_ratio", "cfo_sobre_", "fcf_sobre_",
    "roa", "roe", "roic",
    "sharpe", "adj_sharpe", "sortino", "calmar_ratio", "sterling_ratio",
    "omega_ratio", "upside_potential", "beta", "jensen_alpha",
    "treynor_ratio", "information_ratio", "n_obs",
    # Múltiplos de mercado fundamentalistas
    "mkt_pl_", "mkt_pvp", "mkt_ps_", "mkt_pfcf_", "mkt_pcfo_",
    "mkt_ev_", "mkt_divida_liquida_ebitda", "mkt_divida_liquida_pl",
    "mkt_divida_bruta_ebitda",
)


def infer_bloco(codigo: str) -> str:
    if codigo.startswith("bp_"):
        return "BP"
    if codigo.startswith("dre_"):
        return "DRE"
    if codigo.startswith("dfc_"):
        return "DFC"
    if codigo.startswith("cmb_"):
        return "CMB"
    if codigo.startswith("hst_"):
        return "HST"
    if codigo.startswith("mkt_"):
        return "MKT"
    if codigo.startswith("val_"):
        return "VAL"
    return "OUTRO"


def infer_camada(codigo: str) -> int:
    if codigo.startswith("mkt_") or codigo.startswith("val_"):
        return 3
    if codigo.startswith("hst_"):
        return 2
    return 1


def infer_unidade(codigo: str) -> str:
    if codigo in MOEDA_CODES or codigo.startswith("dfc_var_"):
        return "MOEDA"
    if any(hint in codigo for hint in PERCENTUAL_HINTS):
        return "PERCENTUAL"
    if any(hint in codigo for hint in INDEX_HINTS):
        return "INDICE"
    if any(hint in codigo for hint in RATIO_HINTS):
        return "RATIO"
    return "OUTRO"


def humanize_codigo(codigo: str) -> str:
    return codigo.replace("_", " ").title()


humanize = humanize_codigo


# Indicadores de valuation: Graham Number, Bazin e margens de segurança (bloco VAL)
VALUATION_CODES = [
    # Métricas por ação
    "val_lpa",              # Lucro Por Ação TTM (R$) = preço / P/L
    "val_vpa",              # Valor Patrimonial Por Ação (R$) = preço / P/VP
    "val_dpa_ttm",          # Dividendos Por Ação TTM (R$) = DY × preço

    # Valor justo — Graham
    "val_graham",           # Graham Number = √(22.5 × LPA × VPA)
    "val_margem_graham",    # Margem de segurança Graham = (Graham − Preço) / Preço

    # Preço teto — Bazin
    "val_bazin_6",          # Preço teto Bazin DY 6% = DPA / 0.06
    "val_bazin_10",         # Preço teto Bazin DY 10% = DPA / 0.10
    "val_margem_bazin_6",   # Margem vs Bazin 6%  = (Bazin6 − Preço) / Preço
    "val_margem_bazin_10",  # Margem vs Bazin 10% = (Bazin10 − Preço) / Preço

    # Sinalização composta
    "val_status",           # +1 subavaliado, 0 justo, -1 sobrevalorizado (codif. numérica)
]


def build_indicator_rows():
    rows = []
    all_codes = [c for c in INDICATOR_CODES if c not in {"freq", "empresa", "ano"}]
    all_codes += QUANT_INDICATOR_CODES
    all_codes += MULTIPLOS_MKT_CODES
    all_codes += VALUATION_CODES

    for cod in all_codes:
        rows.append((
            cod,
            humanize_codigo(cod),
            infer_bloco(cod),
            infer_camada(cod),
            infer_unidade(cod),
            Jsonb([]),
        ))
    return rows
