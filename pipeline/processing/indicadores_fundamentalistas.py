from __future__ import annotations

import argparse
import logging
import re
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pipeline.config import acoes_indicadores_dir_for, dem_acoes_dir_for

warnings.simplefilter("ignore", pd.errors.PerformanceWarning)

log = logging.getLogger(__name__)


def _norm_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def _safe_div(numer: pd.Series, denom: pd.Series) -> pd.Series:
    out = numer / denom.replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
    def _fit(y: np.ndarray) -> float:
        if np.all(np.isnan(y)):
            return np.nan
        x = np.arange(len(y), dtype=float)
        mask = ~np.isnan(y)
        if mask.sum() < 2:
            return np.nan
        xx = x[mask]
        yy = y[mask]
        return float(np.polyfit(xx, yy, 1)[0])

    return series.rolling(window=window, min_periods=max(2, window // 2)).apply(_fit, raw=True)


def _rolling_autocorr(series: pd.Series, window: int, lag: int = 1) -> pd.Series:
    return series.rolling(window=window, min_periods=max(lag + 2, window // 2)).apply(
        lambda x: pd.Series(x).autocorr(lag=lag),
        raw=False,
    )


@dataclass(frozen=True)
class IndicatorMeta:
    indicador: str
    bloco: str
    camada: int
    formula: str
    contas: str
    observacao: str = ""


# Contas-base por CD_CONTA; fallback textual cobre variações em DS_CONTA.
ACCOUNT_RULES: dict[str, dict[str, Any]] = {
    # BP
    "asset_total": {"codes": ["1"], "contains": ["ativo total"]},
    "asset_current": {"codes": ["1.01"], "contains": ["ativo circulante"]},
    "cash_eq": {"codes": ["1.01.01"], "contains": ["caixa e equivalentes de caixa"]},
    "fin_apps": {"codes": ["1.01.02"], "contains": ["aplicacoes financeiras"]},
    "inventory": {"codes": ["1.01.04"], "contains": ["estoques"]},
    "asset_non_current": {"codes": ["1.02"], "contains": ["ativo nao circulante"]},
    "asset_ltp": {"codes": ["1.02.01"], "contains": ["ativo realizavel a longo prazo"]},
    "investments": {"codes": ["1.02.02"], "contains": ["investimentos"]},
    "ppe": {"codes": ["1.02.03"], "contains": ["imobilizado"]},
    "intangibles": {"codes": ["1.02.04"], "contains": ["intangivel"]},
    "liab_total": {"codes": ["2"], "contains": ["passivo total"]},
    "liab_current": {"codes": ["2.01"], "contains": ["passivo circulante"]},
    "liab_non_current": {"codes": ["2.02"], "contains": ["passivo nao circulante"]},
    "equity": {"codes": ["2.03"], "contains": ["patrimonio liquido consolidado"]},
    "suppliers": {"codes": ["2.01.02"], "contains": ["fornecedores"]},
    # DRE
    "revenue": {"codes": ["3.01"], "contains": ["receita de venda de bens e ou servicos"]},
    "cogs": {"codes": ["3.02"], "contains": ["custo dos bens e ou servicos vendidos"]},
    "gross_profit": {"codes": ["3.03"], "contains": ["resultado bruto"]},
    "opex_total": {"codes": ["3.04"], "contains": ["despesas receitas operacionais"]},
    "sell_exp": {"codes": ["3.04.01"], "contains": ["despesas com vendas"]},
    "ga_exp": {"codes": ["3.04.02"], "contains": ["despesas gerais e administrativas"]},
    "sgna_exp": {"codes": ["3.04.01", "3.04.02"], "contains": ["despesas de vendas administrativas e gerais"], "sum_codes": True},
    "rnd_exp": {"codes": [], "contains": ["despesas com pesquisas e desenvolvimento"]},
    "impairment": {"codes": ["3.04.03"], "contains": ["nao recuperabilidade de ativos", "impairment"]},
    "other_op_rev": {"codes": ["3.04.04"], "contains": ["outras receitas operacionais"]},
    "other_op_exp": {"codes": ["3.04.05"], "contains": ["outras despesas operacionais"]},
    "equity_result": {"codes": ["3.04.06"], "contains": ["resultado de equivalencia patrimonial"]},
    "ebit": {
        "codes": ["3.05"],
        "contains": ["resultado antes do resultado financeiro e dos tributos"],
    },
    "financial_result": {"codes": ["3.06"], "contains": ["resultado financeiro"]},
    "financial_rev": {"codes": ["3.06.01"], "contains": ["receitas financeiras"]},
    "financial_exp": {"codes": ["3.06.02"], "contains": ["despesas financeiras"]},
    "pretax_income": {"codes": ["3.07"], "contains": ["resultado antes dos tributos sobre o lucro"]},
    "tax_total": {"codes": ["3.08"], "contains": ["imposto de renda e contribuicao social sobre o lucro"]},
    "tax_current": {"codes": ["3.08.01"], "contains": ["corrente"]},
    "tax_deferred": {"codes": ["3.08.02"], "contains": ["diferido"]},
    "income_cont_ops": {"codes": ["3.09"], "contains": ["resultado liquido das operacoes continuadas"]},
    "income_discont_ops": {"codes": ["3.10"], "contains": ["resultado liquido de operacoes descontinuadas"]},
    "net_income": {"codes": ["3.11"], "contains": ["lucro prejuizo consolidado do periodo"]},
    "net_income_ctrl": {"codes": ["3.11.01"], "contains": ["atribuido a socios da empresa controladora"]},
    "net_income_nci": {"codes": ["3.11.02"], "contains": ["atribuido a socios nao controladores"]},
    # DFC
    "cfo": {"codes": ["6.01"], "contains": ["caixa liquido atividades operacionais"]},
    "cash_generated_ops": {"codes": ["6.01.01"], "contains": ["caixa gerado nas operacoes"]},
    "da_dfc": {"codes": ["6.01.01.02"], "contains": ["amortizacao e depreciacao"]},
    "wc_var_total": {"codes": ["6.01.02"], "contains": ["variacoes nos ativos e passivos"]},
    "wc_ar": {"codes": ["6.01.02.01"], "contains": ["contas a receber de clientes"]},
    "wc_inventory": {"codes": ["6.01.02.02"], "contains": ["estoques"]},
    "wc_tax_rec": {"codes": ["6.01.02.03"], "contains": ["tributos a recuperar"]},
    "wc_prepaid": {"codes": ["6.01.02.04"], "contains": ["despesas antecipadas"]},
    "wc_adv_suppliers": {"codes": ["6.01.02.05"], "contains": ["adiantamento a fornecedores"]},
    "wc_judicial_dep": {"codes": ["6.01.02.06"], "contains": ["depositos judiciais"]},
    "wc_other_credits": {"codes": ["6.01.02.07"], "contains": ["outros creditos"]},
    "wc_dividends_rec": {"codes": ["6.01.02.08"], "contains": ["dividendos a receber"]},
    "wc_contract_fin_assets": {"codes": ["6.01.02.09"], "contains": ["ativos financeiros contratuais"]},
    "wc_suppliers": {"codes": ["6.01.02.12", "6.01.02.11"], "contains": ["fornecedores e empreiteiros", "fornecedores"]},
    "wc_labor": {"codes": ["6.01.02.13"], "contains": ["obrigacoes trabalhistas e sociais", "obrigacoes trabalhistas"]},
    "wc_tax": {"codes": ["6.01.02.14"], "contains": ["obrigacoes fiscais"]},
    "wc_installment_taxes": {"codes": ["6.01.02.15"], "contains": ["parcelamento de tributos"]},
    "wc_other_def_taxes": {"codes": ["6.01.02.17"], "contains": ["outros tributos diferidos"]},
    "wc_other_payables": {"codes": ["6.01.02.18"], "contains": ["outras contas a pagar", "outras obrigacoes"]},
    "dividends_payable_var": {"codes": ["6.01.02.19"], "contains": ["dividendos a pagar"]},
    "interest_paid": {"codes": ["6.01.03.01"], "contains": ["juros pagos"]},
    "tax_paid_cash": {"codes": ["6.01.03.02"], "contains": ["imposto de renda e contribuicao social pagos"]},
    "cfi": {"codes": ["6.02"], "contains": ["caixa liquido atividades de investimento"]},
    "invest_fin_apps_net": {"codes": ["6.02.01"], "contains": ["aplicacoes financeiras", "debentures privadas"]},
    "interest_received_invest": {"codes": ["6.02.02"], "contains": ["juros recebidos"]},
    "afac_invest": {"codes": ["6.02.03"], "contains": ["adiantamento para futuro aumento de capital"]},
    "div_jscp_received": {"codes": ["6.02.04"], "contains": ["dividendos e juros sobre capital proprio recebidos"]},
    "acq_subsidiaries": {"codes": ["6.02.05"], "contains": ["aquisicao da controlada", "aquisicao de controladas"]},
    "loan_related_invest": {"codes": ["6.02.06"], "contains": ["mutuo com partes relacionadas"]},
    "acq_fin_asset": {"codes": ["6.02.07"], "contains": ["aquisicao do ativo financeiro"]},
    "capital_contrib_subs": {"codes": ["6.02.10"], "contains": ["aporte de capital em controladas"]},
    "capital_contrib_colig": {"codes": ["6.02.11"], "contains": ["aporte de capital em coligadas"]},
    "net_related_current_invest": {"codes": ["6.02.12"], "contains": ["conta corrente liquida partes relacionadas"]},
    "reserve_tax_incentive": {"codes": ["6.02.13"], "contains": ["reserva de incentivo fiscal"]},
    "acq_concession_asset": {"codes": ["6.02.14"], "contains": ["aquisicao de ativo de contrato da concessao"]},
    "acq_intangibles": {"codes": ["6.02.15"], "contains": ["aquisicao de intangivel"]},
    "acq_ppe": {"codes": ["6.02.16"], "contains": ["aquisicao de imobilizado"]},
    "future_invest_fund": {"codes": ["6.02.17"], "contains": ["aplicacao em fundo para futuros investimentos"]},
    "cff": {"codes": ["6.03"], "contains": ["caixa liquido atividades de financiamento"]},
    "debt_raised": {"codes": ["6.03.01"], "contains": ["emprestimos financiamentos e debentures captadas"]},
    "capital_increase": {"codes": ["6.03.02"], "contains": ["aumento de capital social"]},
    "debt_issuance_cost": {"codes": ["6.03.03"], "contains": ["custo na captacao de emprestimos financiamentos e debentures"]},
    "debt_paid": {"codes": ["6.03.04"], "contains": ["emprestimos financiamentos e debentures pagas"]},
    "dividends_paid": {"codes": ["6.03.05"], "exact": ["dividendos pagos"], "contains": ["dividendos pagos"]},
    "dividends_jscp_paid_total": {
        "codes": [],
        "exact": ["dividendos e juros sobre capital proprios pagos"],
        "contains": ["dividendos e juros sobre capital proprios pagos"],
    },
    "loan_related_paid": {"codes": ["6.03.06"], "contains": ["mutuo pago para partes relacionadas"]},
    "derivatives_received": {"codes": ["6.03.07"], "contains": ["instrumentos financeiros derivativos recebidos"]},
    "derivatives_paid": {"codes": ["6.03.08"], "contains": ["instrumentos financeiros derivativos pagos"]},
    "equity_issuance_cost": {"codes": ["6.03.09"], "contains": ["custo de emissao de novas acoes"]},
    "capital_contrib_received": {"codes": ["6.03.10"], "contains": ["recursos provenientes de aporte de capital"]},
    "capital_reserve": {"codes": ["6.03.11"], "contains": ["reserva de capital"]},
    "net_related_current_fin": {"codes": ["6.03.12"], "contains": ["conta corrente liquida partes relacionadas"]},
    "dilution_loss": {"codes": ["6.03.13"], "contains": ["perda na diluicao na participacao societaria", "ganho de diluicao"]},
    "afac_fin": {"codes": ["6.03.14"], "contains": ["adiantamento para futuro aumento de capital"]},
    "lease_payments": {"codes": ["6.03.15"], "contains": ["pagamentos de arrendamentos", "pagamento de passivos de arrendamento"]},
    "fx_cash": {"codes": ["6.04"], "contains": ["variacao cambial s caixa e equivalentes"]},
    "net_cash_change": {"codes": ["6.05"], "contains": ["aumento reducao de caixa e equivalentes"]},
    "cash_begin": {"codes": ["6.05.01"], "contains": ["saldo inicial de caixa e equivalentes"]},
    "cash_end": {"codes": ["6.05.02"], "contains": ["saldo final de caixa e equivalentes"]},
}


def _select_series(
    pivot_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    key: str,
    prefer_single: bool = False,
) -> pd.Series:
    rules = ACCOUNT_RULES[key]
    parts: list[tuple[str, pd.Series]] = []

    for code in rules.get("codes", []):
        if code in pivot_df.columns:
            parts.append((code, pivot_df[code]))

    if parts:
        if prefer_single and not rules.get("sum_codes", False):
            candidates = []
            for code, s in parts:
                depth = str(code).count(".")
                nn = int(s.notna().sum())
                candidates.append((nn, depth, s))
            _, _, best = sorted(candidates, key=lambda x: (x[0], x[1]), reverse=True)[0]
            return best

        s = pd.concat([s for _, s in parts], axis=1).sum(axis=1, min_count=1)
        return s

    # fallback por DS_CONTA normalizado
    df = raw_df[["DT_FIM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA"]].copy()
    df["ds_norm"] = df["DS_CONTA"].map(_norm_text)
    mask = False
    exact_tokens = rules.get("exact", [])
    if exact_tokens:
        exact_mask = False
        for token in exact_tokens:
            exact_mask = exact_mask | (df["ds_norm"] == token)
        mask = exact_mask

    if not np.any(mask):
        for token in rules.get("contains", []):
            mask = mask | df["ds_norm"].str.contains(token, na=False)

    if not np.any(mask):
        return pd.Series(index=pivot_df.index, dtype=float)

    filtered = df.loc[mask].copy()
    filtered["VL_CONTA"] = pd.to_numeric(filtered["VL_CONTA"], errors="coerce")

    if prefer_single and not rules.get("sum_codes", False):
        filtered["cd_depth"] = filtered["CD_CONTA"].astype(str).str.count(r"\.")
        filtered = filtered.sort_values(["DT_FIM_EXERC", "cd_depth"], ascending=[True, False])
        filtered = filtered.drop_duplicates(["DT_FIM_EXERC"], keep="first")
        grouped = filtered.groupby("DT_FIM_EXERC")["VL_CONTA"].sum(min_count=1)
    else:
        grouped = filtered.groupby("DT_FIM_EXERC")["VL_CONTA"].sum(min_count=1)

    grouped.index = pd.to_datetime(grouped.index)
    grouped = grouped.sort_index()
    return grouped.reindex(pivot_df.index)


def _read_statement(company_dir: Path, prefix: str) -> pd.DataFrame:
    files = sorted(company_dir.glob(f"{prefix}_*.parquet"))
    if not files:
        return pd.DataFrame(columns=["DT_FIM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA"])

    all_parts: list[pd.DataFrame] = []
    use_cols = ["DT_FIM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA"]
    for file in files:
        df = pd.read_parquet(file, columns=use_cols)
        df["DT_FIM_EXERC"] = pd.to_datetime(df["DT_FIM_EXERC"])
        df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
        all_parts.append(df)

    out = pd.concat(all_parts, ignore_index=True)
    out = (
        out.sort_values(["DT_FIM_EXERC", "CD_CONTA", "DS_CONTA"])
        .drop_duplicates(["DT_FIM_EXERC", "CD_CONTA", "DS_CONTA"], keep="last")
        .reset_index(drop=True)
    )
    return out


def _build_pivot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    pivot = df.pivot_table(
        index="DT_FIM_EXERC",
        columns="CD_CONTA",
        values="VL_CONTA",
        aggfunc="last",
    ).sort_index()
    return pivot


def _flow_from_ytd(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    grp = series.groupby(series.index.year)
    q = grp.diff()
    first_mask = grp.cumcount() == 0
    q[first_mask] = series[first_mask]
    return q


def _to_ttm(series: pd.Series, freq: str) -> pd.Series:
    if freq == "T":
        return series.rolling(4, min_periods=4).sum()
    return series


def _build_base_timeseries(company_dir: Path) -> pd.DataFrame:
    bpa = _read_statement(company_dir, "bpa")
    dre = _read_statement(company_dir, "dre")
    dfc = _read_statement(company_dir, "dfc")

    all_dates = sorted(
        set(pd.to_datetime(bpa["DT_FIM_EXERC"], errors="coerce").dropna().tolist())
        | set(pd.to_datetime(dre["DT_FIM_EXERC"], errors="coerce").dropna().tolist())
        | set(pd.to_datetime(dfc["DT_FIM_EXERC"], errors="coerce").dropna().tolist())
    )
    if not all_dates:
        return pd.DataFrame()

    base = pd.DataFrame(index=pd.DatetimeIndex(all_dates))
    piv_bpa = _build_pivot(bpa).reindex(base.index)
    piv_dre = _build_pivot(dre).reindex(base.index)
    piv_dfc = _build_pivot(dfc).reindex(base.index)

    # BP
    for key in [
        "asset_total",
        "asset_current",
        "cash_eq",
        "fin_apps",
        "inventory",
        "asset_non_current",
        "asset_ltp",
        "investments",
        "ppe",
        "intangibles",
        "liab_total",
        "liab_current",
        "liab_non_current",
        "equity",
        "suppliers",
    ]:
        base[key] = _select_series(piv_bpa, bpa, key)

    # DRE (acumulado no ano)
    dre_keys = [
        "revenue",
        "cogs",
        "gross_profit",
        "opex_total",
        "sell_exp",
        "ga_exp",
        "sgna_exp",
        "rnd_exp",
        "impairment",
        "other_op_rev",
        "other_op_exp",
        "equity_result",
        "ebit",
        "financial_result",
        "financial_rev",
        "financial_exp",
        "pretax_income",
        "tax_total",
        "tax_current",
        "tax_deferred",
        "income_cont_ops",
        "income_discont_ops",
        "net_income",
        "net_income_ctrl",
        "net_income_nci",
    ]
    for key in dre_keys:
        base[f"{key}_ytd"] = _select_series(piv_dre, dre, key)
        base[f"{key}_q"] = _flow_from_ytd(base[f"{key}_ytd"])

    # DFC (acumulado no ano)
    dfc_keys = [
        "cfo",
        "cash_generated_ops",
        "da_dfc",
        "wc_var_total",
        "wc_ar",
        "wc_inventory",
        "wc_tax_rec",
        "wc_prepaid",
        "wc_adv_suppliers",
        "wc_judicial_dep",
        "wc_other_credits",
        "wc_dividends_rec",
        "wc_contract_fin_assets",
        "wc_suppliers",
        "wc_labor",
        "wc_tax",
        "wc_installment_taxes",
        "wc_other_def_taxes",
        "wc_other_payables",
        "dividends_payable_var",
        "interest_paid",
        "tax_paid_cash",
        "cfi",
        "invest_fin_apps_net",
        "interest_received_invest",
        "afac_invest",
        "div_jscp_received",
        "acq_subsidiaries",
        "loan_related_invest",
        "acq_fin_asset",
        "capital_contrib_subs",
        "capital_contrib_colig",
        "net_related_current_invest",
        "reserve_tax_incentive",
        "acq_concession_asset",
        "acq_intangibles",
        "acq_ppe",
        "future_invest_fund",
        "cff",
        "debt_raised",
        "capital_increase",
        "debt_issuance_cost",
        "debt_paid",
        "dividends_paid",
        "dividends_jscp_paid_total",
        "loan_related_paid",
        "derivatives_received",
        "derivatives_paid",
        "equity_issuance_cost",
        "capital_contrib_received",
        "capital_reserve",
        "net_related_current_fin",
        "dilution_loss",
        "afac_fin",
        "lease_payments",
        "fx_cash",
        "net_cash_change",
        "cash_begin",
        "cash_end",
    ]
    for key in dfc_keys:
        base[f"{key}_ytd"] = _select_series(piv_dfc, dfc, key, prefer_single=True)
        base[f"{key}_q"] = _flow_from_ytd(base[f"{key}_ytd"])

    base["year"] = base.index.year
    base["quarter"] = base.index.quarter
    return base.sort_index()


def _compute_indicators_from_base(base: pd.DataFrame, freq: str) -> pd.DataFrame:
    if base.empty:
        return pd.DataFrame()

    df = base.copy()
    out = pd.DataFrame(index=df.index)

    revenue = df["revenue_q"] if freq == "T" else df["revenue_ytd"]
    cogs = df["cogs_q"] if freq == "T" else df["cogs_ytd"]
    gross_profit = df["gross_profit_q"] if freq == "T" else df["gross_profit_ytd"]
    ebit = df["ebit_q"] if freq == "T" else df["ebit_ytd"]
    financial_result = df["financial_result_q"] if freq == "T" else df["financial_result_ytd"]
    financial_rev = df["financial_rev_q"] if freq == "T" else df["financial_rev_ytd"]
    financial_exp = df["financial_exp_q"] if freq == "T" else df["financial_exp_ytd"]
    pretax = df["pretax_income_q"] if freq == "T" else df["pretax_income_ytd"]
    tax_total = df["tax_total_q"] if freq == "T" else df["tax_total_ytd"]
    tax_current = df["tax_current_q"] if freq == "T" else df["tax_current_ytd"]
    tax_deferred = df["tax_deferred_q"] if freq == "T" else df["tax_deferred_ytd"]
    ni = df["net_income_q"] if freq == "T" else df["net_income_ytd"]
    ni_ctrl = df["net_income_ctrl_q"] if freq == "T" else df["net_income_ctrl_ytd"]
    ni_nci = df["net_income_nci_q"] if freq == "T" else df["net_income_nci_ytd"]
    ni_cont = df["income_cont_ops_q"] if freq == "T" else df["income_cont_ops_ytd"]
    ni_discont = df["income_discont_ops_q"] if freq == "T" else df["income_discont_ops_ytd"]

    cfo = df["cfo_q"] if freq == "T" else df["cfo_ytd"]
    cfi = df["cfi_q"] if freq == "T" else df["cfi_ytd"]
    cff = df["cff_q"] if freq == "T" else df["cff_ytd"]
    da = df["da_dfc_q"] if freq == "T" else df["da_dfc_ytd"]

    dividends_paid = df["dividends_paid_q"] if freq == "T" else df["dividends_paid_ytd"]
    dividends_jscp_paid_total = (
        df["dividends_jscp_paid_total_q"] if freq == "T" else df["dividends_jscp_paid_total_ytd"]
    )
    jscp_paid = dividends_jscp_paid_total - dividends_paid
    proventos_totais_pagos = dividends_jscp_paid_total.combine_first(dividends_paid)
    debt_raised = df["debt_raised_q"] if freq == "T" else df["debt_raised_ytd"]
    debt_paid = df["debt_paid_q"] if freq == "T" else df["debt_paid_ytd"]
    lease_paid = df["lease_payments_q"] if freq == "T" else df["lease_payments_ytd"]

    capex = -(
        (df["acq_ppe_q"] if freq == "T" else df["acq_ppe_ytd"]).fillna(0)
        + (df["acq_intangibles_q"] if freq == "T" else df["acq_intangibles_ytd"]).fillna(0)
        + (df["acq_concession_asset_q"] if freq == "T" else df["acq_concession_asset_ytd"]).fillna(0)
    )

    cash_eq = df["cash_eq"]
    fin_apps = df["fin_apps"]
    cash_reserve = cash_eq.fillna(0) + fin_apps.fillna(0)
    nwc = df["asset_current"] - df["liab_current"]
    avg_assets = (df["asset_total"] + df["asset_total"].shift(1)) / 2
    avg_equity = (df["equity"] + df["equity"].shift(1)) / 2
    avg_nwc = (nwc + nwc.shift(1)) / 2
    capital_invested = df["equity"] + df["liab_non_current"] - cash_reserve
    avg_capital_invested = (capital_invested + capital_invested.shift(1)) / 2

    tax_rate = _safe_div(tax_total, pretax)
    ebit_after_tax = ebit * (1 - tax_rate.clip(lower=-2, upper=2))
    ebitda = ebit + da
    fcf_bruto = cfo - capex
    other_invest = -(
        (df["acq_subsidiaries_q"] if freq == "T" else df["acq_subsidiaries_ytd"]).fillna(0)
        + (df["acq_fin_asset_q"] if freq == "T" else df["acq_fin_asset_ytd"]).fillna(0)
    )
    fcf_liquido = fcf_bruto - other_invest
    accruals = ni - cfo

    ni_ttm = _to_ttm(ni, freq)
    rev_ttm = _to_ttm(revenue, freq)
    cfo_ttm = _to_ttm(cfo, freq)
    ebit_ttm = _to_ttm(ebit, freq)
    ebitda_ttm = _to_ttm(ebitda, freq)
    fcf_ttm = _to_ttm(fcf_bruto, freq)

    # ---- BP
    out["bp_liquidez_corrente"] = _safe_div(df["asset_current"], df["liab_current"])
    out["bp_liquidez_seca"] = _safe_div(df["asset_current"] - df["inventory"], df["liab_current"])
    out["bp_liquidez_imediata"] = _safe_div(cash_eq, df["liab_current"])
    out["bp_capital_giro_liquido"] = nwc
    out["bp_capital_giro_sobre_ativo"] = _safe_div(nwc, df["asset_total"])
    out["bp_cobertura_pc_por_caixa"] = _safe_div(cash_eq, df["liab_current"])
    out["bp_passivo_sobre_ativo"] = _safe_div(df["liab_total"], df["asset_total"])
    out["bp_pl_sobre_ativo"] = _safe_div(df["equity"], df["asset_total"])
    out["bp_passivo_sobre_pl"] = _safe_div(df["liab_total"], df["equity"])
    out["bp_grau_alavancagem_patrimonial"] = _safe_div(df["liab_total"], df["equity"])
    out["bp_equity_multiplier"] = _safe_div(df["asset_total"], df["equity"])
    out["bp_caixa_sobre_ativo"] = _safe_div(cash_eq, df["asset_total"])
    out["bp_aplic_fin_sobre_ativo"] = _safe_div(fin_apps, df["asset_total"])
    out["bp_estoques_sobre_ativo"] = _safe_div(df["inventory"], df["asset_total"])
    out["bp_imobilizado_sobre_ativo"] = _safe_div(df["ppe"], df["asset_total"])
    out["bp_intangivel_sobre_ativo"] = _safe_div(df["intangibles"], df["asset_total"])
    out["bp_investimentos_sobre_ativo"] = _safe_div(df["investments"], df["asset_total"])
    out["bp_ativo_nc_sobre_ativo"] = _safe_div(df["asset_non_current"], df["asset_total"])
    out["bp_ativo_c_sobre_ativo"] = _safe_div(df["asset_current"], df["asset_total"])
    out["bp_arlp_sobre_ativo"] = _safe_div(df["asset_ltp"], df["asset_total"])
    out["bp_ativos_liquidos_operacionais_pct"] = _safe_div((df["asset_total"] - cash_reserve) - (df["liab_total"] - df["liab_current"]), df["asset_total"])
    out["bp_intensidade_capital"] = _safe_div(df["ppe"], revenue.abs())
    out["bp_intensidade_intangivel"] = _safe_div(df["intangibles"], revenue.abs())
    out["bp_intensidade_caixa"] = _safe_div(cash_eq, df["asset_total"])
    out["bp_conc_caixa_apps"] = _safe_div(cash_reserve, df["asset_total"])
    out["bp_conc_operacional"] = _safe_div(df["asset_current"] - cash_reserve, df["asset_total"])
    out["bp_conc_longo_prazo"] = _safe_div(df["asset_non_current"], df["asset_total"])

    # ---- DRE
    out["dre_receita"] = revenue
    out["dre_receita_yoy"] = revenue.pct_change(4 if freq == "T" else 1, fill_method=None)
    out["dre_receita_cagr_3a"] = (revenue / revenue.shift(12 if freq == "T" else 3)) ** (1 / 3) - 1
    out["dre_receita_sazonalidade"] = _safe_div(revenue, revenue.rolling(4 if freq == "T" else 3, min_periods=2).mean())
    out["dre_margem_bruta"] = _safe_div(gross_profit, revenue)
    out["dre_margem_operacional"] = _safe_div(ebit, revenue)
    out["dre_margem_ebit"] = _safe_div(ebit, revenue)
    out["dre_margem_ebitda"] = _safe_div(ebitda, revenue)
    out["dre_margem_financeira"] = _safe_div(financial_result, revenue)
    out["dre_margem_pre_tax"] = _safe_div(pretax, revenue)
    out["dre_margem_liquida"] = _safe_div(ni, revenue)
    out["dre_custo_sobre_receita"] = _safe_div(cogs.abs(), revenue.abs())
    out["dre_desp_vendas_sobre_receita"] = _safe_div((df["sell_exp_q"] if freq == "T" else df["sell_exp_ytd"]).abs(), revenue.abs())
    out["dre_desp_ga_sobre_receita"] = _safe_div((df["ga_exp_q"] if freq == "T" else df["ga_exp_ytd"]).abs(), revenue.abs())
    out["dre_pd_sobre_receita"] = _safe_div((df["rnd_exp_q"] if freq == "T" else df["rnd_exp_ytd"]).abs(), revenue.abs())
    out["dre_impairment_sobre_receita"] = _safe_div((df["impairment_q"] if freq == "T" else df["impairment_ytd"]).abs(), revenue.abs())
    out["dre_outras_receitas_op_sobre_receita"] = _safe_div((df["other_op_rev_q"] if freq == "T" else df["other_op_rev_ytd"]), revenue)
    out["dre_outras_desp_op_sobre_receita"] = _safe_div((df["other_op_exp_q"] if freq == "T" else df["other_op_exp_ytd"]).abs(), revenue.abs())
    out["dre_equiv_patrimonial_sobre_receita"] = _safe_div((df["equity_result_q"] if freq == "T" else df["equity_result_ytd"]), revenue)
    out["dre_rec_fin_sobre_receita"] = _safe_div(financial_rev, revenue)
    out["dre_desp_fin_sobre_receita"] = _safe_div(financial_exp.abs(), revenue.abs())
    out["dre_cobertura_juros"] = _safe_div(ebit, financial_exp.abs())
    out["dre_peso_resultado_fin_no_lucro"] = _safe_div(financial_result, ni)
    out["dre_dependencia_resultado_financeiro"] = _safe_div(financial_result.abs(), pretax.abs())
    out["dre_aliquota_efetiva"] = _safe_div(tax_total, pretax)
    out["dre_peso_imposto_corrente"] = _safe_div(tax_current, tax_total)
    out["dre_peso_imposto_diferido"] = _safe_div(tax_deferred, tax_total)
    out["dre_tax_burden"] = _safe_div(ni, pretax)
    out["dre_lucro_continuadas_sobre_consolidado"] = _safe_div(ni_cont, ni)
    out["dre_peso_descontinuadas"] = _safe_div(ni_discont, ni)
    out["dre_participacao_minoritaria"] = _safe_div(ni_nci, ni)
    out["dre_lucro_controladora_sobre_consolidado"] = _safe_div(ni_ctrl, ni)
    out["dre_persistencia_lucro"] = _rolling_autocorr(ni, window=8 if freq == "T" else 5)
    out["dre_volatilidade_lucro"] = ni.rolling(8 if freq == "T" else 5, min_periods=3).std()
    out["dre_crescimento_lucro_yoy"] = ni.pct_change(4 if freq == "T" else 1, fill_method=None)
    out["dre_cagr_lucro_3a"] = (ni / ni.shift(12 if freq == "T" else 3)) ** (1 / 3) - 1
    out["dre_mm_receita_4p"] = revenue.rolling(4 if freq == "T" else 3, min_periods=2).mean()
    out["dre_vol_margem_ebit"] = out["dre_margem_ebit"].rolling(8 if freq == "T" else 5, min_periods=3).std()
    out["dre_compressao_expansao_margem"] = out["dre_margem_ebit"] - out["dre_margem_ebit"].shift(4 if freq == "T" else 1)
    out["dre_estabilidade_lucro"] = _safe_div(ni.rolling(8 if freq == "T" else 5, min_periods=3).mean().abs(), ni.rolling(8 if freq == "T" else 5, min_periods=3).std())
    out["dre_reversao_lucro"] = -ni.diff(4 if freq == "T" else 1)
    out["dre_tendencia_eficiencia"] = _rolling_slope(out["dre_margem_ebit"], window=8 if freq == "T" else 5)

    # ---- DFC
    out["dfc_cfo"] = cfo
    out["dfc_cfo_sobre_receita"] = _safe_div(cfo, revenue)
    out["dfc_cfo_sobre_lucro"] = _safe_div(cfo, ni)
    out["dfc_cfo_sobre_ebit"] = _safe_div(cfo, ebit)
    out["dfc_cfo_sobre_ebitda"] = _safe_div(cfo, ebitda)
    out["dfc_taxa_conversao_lucro_caixa"] = _safe_div(cfo, ni)
    out["dfc_accruals"] = accruals
    out["dfc_accrual_ratio"] = _safe_div(accruals, avg_assets)
    out["dfc_cash_conversion_ratio"] = _safe_div(cfo, ni)
    out["dfc_cash_earnings_quality"] = _safe_div(cfo_ttm, ni_ttm)
    out["dfc_persistencia_cfo"] = _rolling_autocorr(cfo, window=8 if freq == "T" else 5)
    out["dfc_var_contas_receber"] = df["wc_ar_q"] if freq == "T" else df["wc_ar_ytd"]
    out["dfc_var_estoques"] = df["wc_inventory_q"] if freq == "T" else df["wc_inventory_ytd"]
    out["dfc_var_fornecedores"] = df["wc_suppliers_q"] if freq == "T" else df["wc_suppliers_ytd"]
    out["dfc_var_obrig_fiscais"] = df["wc_tax_q"] if freq == "T" else df["wc_tax_ytd"]
    out["dfc_var_passivos_trabalhistas"] = df["wc_labor_q"] if freq == "T" else df["wc_labor_ytd"]
    out["dfc_var_outros_creditos"] = df["wc_other_credits_q"] if freq == "T" else df["wc_other_credits_ytd"]
    out["dfc_var_outros_passivos"] = df["wc_other_payables_q"] if freq == "T" else df["wc_other_payables_ytd"]
    out["dfc_pressao_capital_giro"] = -(df["wc_var_total_q"] if freq == "T" else df["wc_var_total_ytd"])
    out["dfc_liberacao_consumo_cx_cg"] = df["wc_var_total_q"] if freq == "T" else df["wc_var_total_ytd"]
    out["dfc_cfi"] = cfi
    out["dfc_capex_bruto"] = capex
    out["dfc_capex_sobre_receita"] = _safe_div(capex, revenue.abs())
    out["dfc_capex_sobre_cfo"] = _safe_div(capex, cfo.abs())
    out["dfc_capex_sobre_da"] = _safe_div(capex, da.abs())
    out["dfc_investimento_liquido"] = cfi
    out["dfc_fcf_bruto"] = fcf_bruto
    out["dfc_fcf_liquido"] = fcf_liquido
    out["dfc_cff"] = cff
    out["dfc_captacao_divida"] = debt_raised
    out["dfc_amortizacao_divida"] = debt_paid
    out["dfc_captacao_liquida_divida"] = debt_raised + debt_paid
    out["dfc_dividendos_pagos"] = dividends_paid
    out["dfc_jscp_pagos"] = jscp_paid
    out["dfc_proventos_totais_pagos"] = proventos_totais_pagos
    out["dfc_aumento_capital"] = df["capital_increase_q"] if freq == "T" else df["capital_increase_ytd"]
    out["dfc_custo_captacao"] = df["debt_issuance_cost_q"] if freq == "T" else df["debt_issuance_cost_ytd"]
    out["dfc_pagamentos_arrendamento"] = lease_paid
    out["dfc_dependencia_financiamento_externo"] = _safe_div((-(cff)).clip(lower=0), cfo.abs())
    out["dfc_politica_distribuicao_acionista"] = _safe_div(proventos_totais_pagos.abs(), ni.abs())
    out["dfc_variacao_liquida_caixa"] = df["net_cash_change_q"] if freq == "T" else df["net_cash_change_ytd"]
    out["dfc_saldo_inicial_caixa"] = df["cash_begin_q"] if freq == "T" else df["cash_begin_ytd"]
    out["dfc_saldo_final_caixa"] = df["cash_end_q"] if freq == "T" else df["cash_end_ytd"]
    out["dfc_crescimento_caixa"] = out["dfc_saldo_final_caixa"].pct_change(4 if freq == "T" else 1, fill_method=None)
    out["dfc_queima_caixa"] = np.where(cfo < 0, cfo, 0.0)
    out["dfc_reserva_liquidez"] = cash_reserve
    out["dfc_cobertura_caixa_pc"] = _safe_div(cash_reserve, df["liab_current"])

    # ---- Combinados
    out["cmb_roa"] = _safe_div(ni_ttm, avg_assets)
    out["cmb_roe"] = _safe_div(ni_ttm, avg_equity)
    out["cmb_roic_aprox"] = _safe_div(_to_ttm(ebit_after_tax, freq), avg_capital_invested)
    out["cmb_margem_ebitda"] = _safe_div(ebitda_ttm, rev_ttm)
    out["cmb_margem_ebit"] = _safe_div(ebit_ttm, rev_ttm)
    out["cmb_margem_liquida"] = _safe_div(ni_ttm, rev_ttm)
    out["cmb_retorno_sobre_caixa"] = _safe_div(ni_ttm, cash_reserve)
    out["cmb_giro_ativo"] = _safe_div(rev_ttm, avg_assets)
    out["cmb_giro_patrimonio"] = _safe_div(rev_ttm, avg_equity)
    out["cmb_giro_capital_giro"] = _safe_div(rev_ttm, avg_nwc)
    out["cmb_produtividade_capital_receita"] = _safe_div(rev_ttm, df["ppe"])
    out["cmb_produtividade_capital_ebit"] = _safe_div(ebit_ttm, df["ppe"])
    out["cmb_eficiencia_capital_investido"] = _safe_div(ebit_ttm, avg_capital_invested)
    out["cmb_cfo_sobre_lucro"] = _safe_div(cfo_ttm, ni_ttm)
    out["cmb_fcf_sobre_lucro"] = _safe_div(fcf_ttm, ni_ttm)
    out["cmb_cfo_sobre_ativo"] = _safe_div(cfo_ttm, avg_assets)
    out["cmb_fcf_sobre_ativo"] = _safe_div(fcf_ttm, avg_assets)
    out["cmb_accrual_ratio"] = _safe_div(_to_ttm(accruals, freq), avg_assets)
    out["cmb_diferenca_lucro_caixa"] = ni_ttm - cfo_ttm
    out["cmb_estabilidade_caixa"] = _safe_div(cfo.rolling(8 if freq == "T" else 5, min_periods=3).mean().abs(), cfo.rolling(8 if freq == "T" else 5, min_periods=3).std())
    out["cmb_volatilidade_cfo"] = cfo.rolling(8 if freq == "T" else 5, min_periods=3).std()
    out["cmb_liabilities_to_assets"] = _safe_div(df["liab_total"], df["asset_total"])
    out["cmb_equity_ratio"] = _safe_div(df["equity"], df["asset_total"])
    out["cmb_cobertura_juros"] = _safe_div(ebit_ttm, financial_exp.abs().rolling(4 if freq == "T" else 1, min_periods=1).sum())
    out["cmb_cobertura_encargos_financeiros"] = _safe_div(cfo_ttm, (df["interest_paid_q"] if freq == "T" else df["interest_paid_ytd"]).abs().rolling(4 if freq == "T" else 1, min_periods=1).sum())
    out["cmb_dependencia_financiamento"] = _safe_div((-(cff)).clip(lower=0), cfo.abs())
    out["cmb_payout_ratio"] = _safe_div(proventos_totais_pagos.abs(), ni.abs())
    out["cmb_dividendos_sobre_lucro"] = _safe_div(dividends_paid.abs(), ni.abs())
    out["cmb_dividendos_sobre_cfo"] = _safe_div(dividends_paid.abs(), cfo.abs())
    out["cmb_fcf_payout"] = _safe_div(proventos_totais_pagos.abs(), fcf_bruto.abs())
    out["cmb_reinvestimento_lucro"] = _safe_div(capex, ni.abs())
    out["cmb_capex_ratio"] = _safe_div(capex, cfo.abs())

    # ---- Séries históricas transversais
    out["hst_bp_liquidez_corrente_yoy"] = out["bp_liquidez_corrente"].pct_change(4 if freq == "T" else 1, fill_method=None)
    out["hst_bp_liquidez_corrente_drawdown"] = out["bp_liquidez_corrente"] / out["bp_liquidez_corrente"].cummax() - 1
    out["hst_bp_alavancagem_tendencia"] = _rolling_slope(out["bp_passivo_sobre_pl"], window=8 if freq == "T" else 5)
    out["hst_bp_capitalizacao_tendencia"] = _rolling_slope(out["bp_pl_sobre_ativo"], window=8 if freq == "T" else 5)
    out["hst_receita_volatilidade"] = out["dre_receita_yoy"].rolling(8 if freq == "T" else 5, min_periods=3).std()
    out["hst_lucro_volatilidade"] = out["dre_crescimento_lucro_yoy"].rolling(8 if freq == "T" else 5, min_periods=3).std()
    out["hst_cfo_volatilidade"] = out["cmb_volatilidade_cfo"]
    out["hst_receita_var_acumulada"] = (1 + out["dre_receita_yoy"].fillna(0)).cumprod() - 1
    out["hst_lucro_var_acumulada"] = (1 + out["dre_crescimento_lucro_yoy"].fillna(0)).cumprod() - 1

    out["freq"] = freq
    return out


def _build_catalog() -> pd.DataFrame:
    metas: list[IndicatorMeta] = [
        IndicatorMeta("bp_liquidez_corrente", "BP", 1, "Ativo Circulante / Passivo Circulante", "1.01; 2.01"),
        IndicatorMeta("bp_liquidez_seca", "BP", 1, "(Ativo Circulante - Estoques) / Passivo Circulante", "1.01; 1.01.04; 2.01"),
        IndicatorMeta("bp_liquidez_imediata", "BP", 1, "Caixa e Equivalentes / Passivo Circulante", "1.01.01; 2.01"),
        IndicatorMeta("bp_capital_giro_liquido", "BP", 1, "Ativo Circulante - Passivo Circulante", "1.01; 2.01"),
        IndicatorMeta("bp_capital_giro_sobre_ativo", "BP", 1, "NWC / Ativo Total", "1.01; 2.01; 1"),
        IndicatorMeta("bp_cobertura_pc_por_caixa", "BP", 1, "Caixa / Passivo Circulante", "1.01.01; 2.01"),
        IndicatorMeta("bp_passivo_sobre_ativo", "BP", 1, "Passivo Total / Ativo Total", "2; 1"),
        IndicatorMeta("bp_pl_sobre_ativo", "BP", 1, "Patrimônio Líquido / Ativo Total", "2.03; 1"),
        IndicatorMeta("bp_passivo_sobre_pl", "BP", 1, "Passivo Total / Patrimônio Líquido", "2; 2.03"),
        IndicatorMeta("bp_equity_multiplier", "BP", 1, "Ativo Total / Patrimônio Líquido", "1; 2.03"),
        IndicatorMeta("bp_intensidade_capital", "BP", 1, "Imobilizado / Receita", "1.02.03; 3.01"),
        IndicatorMeta("dre_margem_bruta", "DRE", 1, "Resultado Bruto / Receita", "3.03; 3.01"),
        IndicatorMeta("dre_margem_ebit", "DRE", 1, "EBIT / Receita", "3.05; 3.01"),
        IndicatorMeta("dre_margem_ebitda", "DRE", 1, "(EBIT + D&A) / Receita", "3.05; DFC D&A; 3.01"),
        IndicatorMeta("dre_margem_liquida", "DRE", 1, "Lucro Líquido / Receita", "3.11; 3.01"),
        IndicatorMeta("dre_cobertura_juros", "DRE", 1, "EBIT / Despesa Financeira", "3.05; 3.06.02"),
        IndicatorMeta("dre_aliquota_efetiva", "DRE", 1, "IR/CSLL Total / Lucro Antes dos Tributos", "3.08; 3.07"),
        IndicatorMeta("dfc_cfo", "DFC", 1, "Caixa Líquido Atividades Operacionais", "6.01"),
        IndicatorMeta("dfc_capex_bruto", "DFC", 1, "-(Aquisição de Imobilizado + Intangível + Ativo de Concessão)", "6.02.16; 6.02.15; 6.02.14"),
        IndicatorMeta("dfc_fcf_bruto", "DFC", 1, "CFO - Capex", "6.01; 6.02.16; 6.02.15; 6.02.14"),
        IndicatorMeta("dfc_accrual_ratio", "DFC", 1, "(Lucro Líquido - CFO) / Ativo Médio", "3.11; 6.01; 1"),
        IndicatorMeta("dfc_dependencia_financiamento_externo", "DFC", 1, "max(-CFF,0) / |CFO|", "6.03; 6.01"),
        IndicatorMeta("cmb_roa", "COMBINADO", 1, "Lucro Líquido TTM / Ativo Médio", "3.11; 1"),
        IndicatorMeta("cmb_roe", "COMBINADO", 1, "Lucro Líquido TTM / PL Médio", "3.11; 2.03"),
        IndicatorMeta("cmb_roic_aprox", "COMBINADO", 1, "EBIT pós imposto / Capital Investido Médio", "3.05; 3.08; 2.03; 2.02; 1.01.01; 1.01.02"),
        IndicatorMeta("cmb_giro_ativo", "COMBINADO", 1, "Receita TTM / Ativo Médio", "3.01; 1"),
        IndicatorMeta("cmb_cfo_sobre_lucro", "COMBINADO", 1, "CFO TTM / Lucro Líquido TTM", "6.01; 3.11"),
        IndicatorMeta("cmb_payout_ratio", "COMBINADO", 1, "|Dividendos + JCP pagos| / |Lucro|", "DS: Dividendos e Juros Sobre Capital Próprios Pagos; DS: Dividendos Pagos; 3.11"),
        IndicatorMeta("dre_receita_bruta_sobre_operacional", "DRE", 2, "Receita Bruta / Receita Líquida", "conta de receita bruta explícita", "Necessita linha de receita bruta não agregada"),
        IndicatorMeta("dre_margem_ebitda_ajustada", "DRE", 2, "EBITDA Ajustado / Receita", "D&A e ajustes não recorrentes detalhados", "Necessita abertura adicional de ajustes"),
        IndicatorMeta("dfc_jscp_pagos", "DFC", 1, "('Dividendos e Juros Sobre Capital Próprios Pagos' - 'Dividendos Pagos')", "DS_CONTA explícitas no DFC"),
        IndicatorMeta("mkt_preco_lucro", "MERCADO", 3, "Preço por ação / LPA", "preço + nº ações"),
        IndicatorMeta("mkt_ev_ebitda", "MERCADO", 3, "(Valor Firma) / EBITDA", "market cap + dívida líquida + EBITDA"),
        IndicatorMeta("mkt_dividend_yield", "MERCADO", 3, "Dividendos por ação / Preço por ação", "preço + nº ações + dividendos por ação"),
    ]
    return pd.DataFrame([m.__dict__ for m in metas])


def _annual_cut(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # Última data disponível de cada ano fiscal (respeita empresas com fechamento diferente de dez/31)
    idx = df.groupby(df.index.year).tail(1).index
    return df.loc[idx].sort_index()


def process_company(company_dir: Path, out_root: Path) -> tuple[str, int]:
    base = _build_base_timeseries(company_dir)
    if base.empty:
        return company_dir.name, 0

    tri = _compute_indicators_from_base(base, freq="T")
    anu = _compute_indicators_from_base(_annual_cut(base), freq="A")

    out_dir = out_root / company_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    tri = tri.sort_index()
    tri.index.name = "dt_fim_exerc"
    tri["empresa"] = company_dir.name
    tri["ano"] = tri.index.year
    tri["trimestre"] = tri.index.quarter
    tri.to_parquet(out_dir / "indicadores_trimestrais.parquet", index=True)

    anu = anu.sort_index()
    anu.index.name = "dt_fim_exerc"
    anu["empresa"] = company_dir.name
    anu["ano"] = anu.index.year
    anu.to_parquet(out_dir / "indicadores_anuais.parquet", index=True)

    return company_dir.name, tri.shape[0] + anu.shape[0]


def run_pipeline(base_dir: Path) -> None:
    dem_dir = dem_acoes_dir_for(base_dir)
    out_root = acoes_indicadores_dir_for(base_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    companies = sorted([p for p in dem_dir.iterdir() if p.is_dir()])
    results: list[tuple[str, int]] = []
    for company in companies:
        name, n_rows = process_company(company, out_root)
        results.append((name, n_rows))

    catalog = _build_catalog()
    catalog.to_parquet(out_root / "_catalogo_indicadores.parquet", index=False)
    catalog.to_csv(out_root / "_catalogo_indicadores.csv", index=False, encoding="utf-8-sig")

    status = pd.DataFrame(results, columns=["empresa", "linhas_indicadores"])
    status.to_parquet(out_root / "_status_processamento.parquet", index=False)
    log.info(
        "Empresas processadas: %d | com indicadores: %d | saída: %s",
        len(status),
        int((status["linhas_indicadores"] > 0).sum()),
        out_root,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline de indicadores fundamentalistas (CVM).")
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Pasta raiz do projeto TRACK_STOCKS.",
    )
    return parser.parse_args()

 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    base = Path(args.base_dir).resolve()
    run_pipeline(base)
    out = acoes_indicadores_dir_for(base)
    print(f"Concluído. Saída: {out}")
