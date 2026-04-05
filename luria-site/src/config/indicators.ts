import type { IndicatorConfig, Bloco, Freq } from '../types';

export const INDICATORS: Record<string, IndicatorConfig> = {
  bp_liquidez_corrente:       { name: 'Liquidez Corrente',       bloco: 'BP',  unit: 'RATIO',      threshold: 1.5,   higherBetter: true  },
  bp_liquidez_seca:           { name: 'Liquidez Seca',           bloco: 'BP',  unit: 'RATIO',      threshold: 1.0,   higherBetter: true  },
  bp_liquidez_imediata:       { name: 'Liquidez Imediata',       bloco: 'BP',  unit: 'RATIO',                        higherBetter: true  },
  bp_passivo_sobre_ativo:     { name: 'Passivo / Ativo',         bloco: 'BP',  unit: 'RATIO',      threshold: 0.65,  higherBetter: false },
  bp_pl_sobre_ativo:          { name: 'PL / Ativo',              bloco: 'BP',  unit: 'RATIO',      threshold: 0.35,  higherBetter: true  },
  bp_equity_multiplier:       { name: 'Equity Multiplier',       bloco: 'BP',  unit: 'RATIO',      threshold: 2.5,   higherBetter: false },
  bp_capital_giro_sobre_ativo:{ name: 'Capital de Giro / Ativo', bloco: 'BP',  unit: 'RATIO',      threshold: 0.15,  higherBetter: true  },
  bp_capital_giro_liquido:    { name: 'Capital de Giro Líquido', bloco: 'BP',  unit: 'MOEDA',                        higherBetter: true  },
  bp_caixa_sobre_ativo:       { name: 'Caixa / Ativo',           bloco: 'BP',  unit: 'RATIO',                        higherBetter: true  },
  bp_estoques_sobre_ativo:    { name: 'Estoques / Ativo',        bloco: 'BP',  unit: 'RATIO',                        higherBetter: false },
  bp_imobilizado_sobre_ativo: { name: 'Imobilizado / Ativo',     bloco: 'BP',  unit: 'RATIO',                        higherBetter: false },
  bp_grau_alavancagem_patrimonial: { name: 'Alavancagem Patrimonial', bloco: 'BP', unit: 'RATIO',                    higherBetter: false },

  dre_margem_bruta:           { name: 'Margem Bruta',            bloco: 'DRE', unit: 'PERCENTUAL', threshold: 0.25,  higherBetter: true  },
  dre_margem_ebit:            { name: 'Margem EBIT',             bloco: 'DRE', unit: 'PERCENTUAL', threshold: 0.10,  higherBetter: true  },
  dre_margem_ebitda:          { name: 'Margem EBITDA',           bloco: 'DRE', unit: 'PERCENTUAL',                   higherBetter: true  },
  dre_margem_liquida:         { name: 'Margem Líquida',          bloco: 'DRE', unit: 'PERCENTUAL', threshold: 0.08,  higherBetter: true  },
  dre_margem_operacional:     { name: 'Margem Operacional',      bloco: 'DRE', unit: 'PERCENTUAL',                   higherBetter: true  },
  dre_cobertura_juros:        { name: 'Cobertura de Juros',      bloco: 'DRE', unit: 'RATIO',      threshold: 3.0,   higherBetter: true  },
  dre_custo_sobre_receita:    { name: 'Custo / Receita',         bloco: 'DRE', unit: 'RATIO',                        higherBetter: false },

  dfc_cfo_sobre_receita:      { name: 'CFO / Receita',           bloco: 'DFC', unit: 'RATIO',      threshold: 0.10,  higherBetter: true  },
  dfc_accrual_ratio:          { name: 'Accrual Ratio',           bloco: 'DFC', unit: 'RATIO',      threshold: 0.05,  higherBetter: false },
  dfc_fcf_bruto:              { name: 'FCF Bruto',               bloco: 'DFC', unit: 'MOEDA',                        higherBetter: true  },
  dfc_fcf_liquido:            { name: 'FCF Líquido',             bloco: 'DFC', unit: 'MOEDA',                        higherBetter: true  },

  cmb_roe:                    { name: 'ROE',                     bloco: 'CMB', unit: 'PERCENTUAL', threshold: 0.15,  higherBetter: true  },
  cmb_roa:                    { name: 'ROA',                     bloco: 'CMB', unit: 'PERCENTUAL', threshold: 0.08,  higherBetter: true  },
  cmb_roic:                   { name: 'ROIC',                    bloco: 'CMB', unit: 'PERCENTUAL', threshold: 0.12,  higherBetter: true  },
  cmb_giro_ativo:             { name: 'Giro do Ativo',           bloco: 'CMB', unit: 'RATIO',      threshold: 0.5,   higherBetter: true  },

  mkt_sharpe_252d:            { name: 'Sharpe 252d',             bloco: 'MKT', unit: 'RATIO',      threshold: 0.5,   higherBetter: true,  freq: 'M' },
  mkt_sharpe_126d:            { name: 'Sharpe 126d',             bloco: 'MKT', unit: 'RATIO',      threshold: 0.5,   higherBetter: true,  freq: 'M' },
  mkt_sharpe_63d:             { name: 'Sharpe 63d',              bloco: 'MKT', unit: 'RATIO',      threshold: 0.5,   higherBetter: true,  freq: 'M' },
  mkt_sharpe_21d:             { name: 'Sharpe 21d',              bloco: 'MKT', unit: 'RATIO',      threshold: 0.5,   higherBetter: true,  freq: 'M' },
  mkt_sortino_252d:           { name: 'Sortino 252d',            bloco: 'MKT', unit: 'RATIO',      threshold: 0.8,   higherBetter: true,  freq: 'M' },
  mkt_beta_252d:              { name: 'Beta 252d',               bloco: 'MKT', unit: 'RATIO',      threshold: 1.0,   higherBetter: false, freq: 'M' },
  mkt_max_drawdown_252d:      { name: 'Max Drawdown 252d',       bloco: 'MKT', unit: 'PERCENTUAL', threshold: 0.20,  higherBetter: false, freq: 'M' },
  mkt_volatility_252d:        { name: 'Volatilidade 252d',       bloco: 'MKT', unit: 'PERCENTUAL', threshold: 0.30,  higherBetter: false, freq: 'M' },
  mkt_jensen_alpha_252d:      { name: 'Alpha Jensen 252d',       bloco: 'MKT', unit: 'PERCENTUAL', threshold: 0.0,   higherBetter: true,  freq: 'M' },
  mkt_calmar_ratio_252d:      { name: 'Calmar Ratio 252d',       bloco: 'MKT', unit: 'RATIO',      threshold: 1.0,   higherBetter: true,  freq: 'M' },
  mkt_omega_ratio_252d:       { name: 'Omega Ratio 252d',        bloco: 'MKT', unit: 'RATIO',      threshold: 1.0,   higherBetter: true,  freq: 'M' },
  mkt_var_252d:               { name: 'VaR 252d',                bloco: 'MKT', unit: 'RATIO',      threshold: 0.025, higherBetter: false, freq: 'M' },
  mkt_information_ratio_252d: { name: 'Information Ratio 252d',  bloco: 'MKT', unit: 'RATIO',      threshold: 0.3,   higherBetter: true,  freq: 'M' },
  mkt_tracking_error_252d:    { name: 'Tracking Error 252d',     bloco: 'MKT', unit: 'PERCENTUAL', threshold: 0.20,  higherBetter: false, freq: 'M' },

  // Múltiplos fundamentalistas (calculados no ETL multiplos_mercado)
  mkt_pl_ttm:                 { name: 'P/L TTM',                 bloco: 'MKT', unit: 'RATIO',      threshold: 15,    higherBetter: false, freq: 'T' },
  mkt_pvp:                    { name: 'P/VP',                    bloco: 'MKT', unit: 'RATIO',      threshold: 2.0,   higherBetter: false, freq: 'T' },
  mkt_ps_ttm:                 { name: 'P/Receita TTM',           bloco: 'MKT', unit: 'RATIO',      threshold: 3.0,   higherBetter: false, freq: 'T' },
  mkt_pfcf_ttm:               { name: 'P/FCF TTM',               bloco: 'MKT', unit: 'RATIO',      threshold: 20,    higherBetter: false, freq: 'T' },
  mkt_pcfo_ttm:               { name: 'P/CFO TTM',               bloco: 'MKT', unit: 'RATIO',      threshold: 15,    higherBetter: false, freq: 'T' },
  mkt_ev_ebitda_ttm:          { name: 'EV/EBITDA TTM',           bloco: 'MKT', unit: 'RATIO',      threshold: 12,    higherBetter: false, freq: 'T' },
  mkt_ev_ebit_ttm:            { name: 'EV/EBIT TTM',             bloco: 'MKT', unit: 'RATIO',      threshold: 15,    higherBetter: false, freq: 'T' },
  mkt_ev_receita_ttm:         { name: 'EV/Receita TTM',          bloco: 'MKT', unit: 'RATIO',      threshold: 3.0,   higherBetter: false, freq: 'T' },
  mkt_dividend_yield_ttm:     { name: 'Dividend Yield TTM',      bloco: 'MKT', unit: 'PERCENTUAL', threshold: 0.06,  higherBetter: true,  freq: 'T' },
  mkt_divida_liquida_ebitda_ttm: { name: 'Dív. Líq. / EBITDA',  bloco: 'MKT', unit: 'RATIO',      threshold: 3.0,   higherBetter: false, freq: 'T' },
  mkt_divida_liquida_pl:      { name: 'Dív. Líq. / PL',          bloco: 'MKT', unit: 'RATIO',      threshold: 1.5,   higherBetter: false, freq: 'T' },

  // Valuation (Graham & Bazin)
  val_lpa:                    { name: 'LPA (Lucro/Ação)',         bloco: 'VAL', unit: 'MOEDA',                        higherBetter: true,  freq: 'T' },
  val_vpa:                    { name: 'VPA (Patrimônio/Ação)',    bloco: 'VAL', unit: 'MOEDA',                        higherBetter: true,  freq: 'T' },
  val_dpa_ttm:                { name: 'DPA TTM (Dividendo/Ação)', bloco: 'VAL', unit: 'MOEDA',                        higherBetter: true,  freq: 'T' },
  val_graham:                 { name: 'Valor Justo Graham',       bloco: 'VAL', unit: 'MOEDA',                        higherBetter: true,  freq: 'T' },
  val_bazin_6:                { name: 'Preço Teto Bazin 6%',      bloco: 'VAL', unit: 'MOEDA',                        higherBetter: true,  freq: 'T' },
  val_bazin_10:               { name: 'Preço Teto Bazin 10%',     bloco: 'VAL', unit: 'MOEDA',                        higherBetter: true,  freq: 'T' },
  val_margem_graham:          { name: 'Margem de Segurança Graham', bloco: 'VAL', unit: 'PERCENTUAL',                 higherBetter: true,  freq: 'T' },
  val_margem_bazin_6:         { name: 'Margem Bazin 6%',          bloco: 'VAL', unit: 'PERCENTUAL',                   higherBetter: true,  freq: 'T' },
  val_margem_bazin_10:        { name: 'Margem Bazin 10%',         bloco: 'VAL', unit: 'PERCENTUAL',                   higherBetter: true,  freq: 'T' },
};

export const BLOCOS: Bloco[] = ['BP', 'DRE', 'DFC', 'CMB', 'MKT', 'VAL'];

export const BLOCO_LABEL: Record<string, string> = {
  BP:  'Balanço Patrimonial',
  DRE: 'Demonstração de Resultados',
  DFC: 'Fluxo de Caixa',
  CMB: 'Retorno & Eficiência',
  MKT: 'Mercado & Múltiplos',
  VAL: 'Valuation (Graham & Bazin)',
  HST: 'Histórico',
};

export const BLOCO_COLORS: Record<Bloco, string> = {
  BP:  '#2563eb',
  DRE: '#7c3aed',
  DFC: '#d97706',
  CMB: '#059669',
  MKT: '#e11d48',
  HST: '#64748b',
  VAL: '#0891b2',
};

export const BLOCO_BG: Record<string, string> = {
  BP:  'bg-blue-50 text-blue-700 border-blue-200',
  DRE: 'bg-violet-50 text-violet-700 border-violet-200',
  DFC: 'bg-amber-50 text-amber-700 border-amber-200',
  CMB: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  MKT: 'bg-rose-50 text-rose-700 border-rose-200',
  HST: 'bg-slate-50 text-slate-600 border-slate-200',
  VAL: 'bg-cyan-50 text-cyan-700 border-cyan-200',
};

export const DEFAULT_MINI_INDICATORS = [
  'dre_margem_liquida',
  'cmb_roe',
  'bp_passivo_sobre_ativo',
  'dre_cobertura_juros',
  'mkt_pl_ttm',
  'mkt_dividend_yield_ttm',
];

export const SCORE_WEIGHTS: Record<string, number> = {
  BP: 0.25,
  DRE: 0.30,
  DFC: 0.20,
  CMB: 0.15,
  MKT: 0.10,
};

export function formatValue(code: string, value: number): string {
  const ind = INDICATORS[code];
  if (!ind) return value.toFixed(3);

  switch (ind.unit) {
    case 'PERCENTUAL':
      return `${(value * 100).toFixed(1)}%`;
    case 'MOEDA': {
      const abs = Math.abs(value);
      if (abs >= 1e9) return `R$ ${(value / 1e9).toFixed(1)}B`;
      if (abs >= 1e6) return `R$ ${(value / 1e6).toFixed(1)}M`;
      if (abs >= 1e3) return `R$ ${(value / 1e3).toFixed(1)}K`;
      return `R$ ${value.toFixed(2)}`;
    }
    case 'INDICE':
      return value.toFixed(3);
    default:
      return value.toFixed(2);
  }
}

export function resolveFreq(code: string): Freq {
  return INDICATORS[code]?.freq ?? 'T';
}

export function isGood(code: string, value: number): boolean | null {
  const ind = INDICATORS[code];
  if (!ind || ind.threshold === undefined) return null;
  return ind.higherBetter ? value >= ind.threshold : value <= ind.threshold;
}

export function getStatusColor(code: string, value: number): string {
  const good = isGood(code, value);
  if (good === null) return '#2563eb';
  return good ? '#059669' : '#dc2626';
}

export function formatLabel(freq: string, ano: number, trimestre?: number, mes?: number): string {
  if (freq === 'M' && mes) return `${String(mes).padStart(2, '0')}/${ano}`;
  if (freq === 'T' && trimestre) return `T${trimestre}/${String(ano).slice(2)}`;
  return String(ano);
}
