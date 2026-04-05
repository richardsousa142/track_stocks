export interface IndicatorConfig {
  name: string;
  bloco: Bloco;
  unit: Unit;
  threshold?: number;
  higherBetter: boolean;
  description?: string;
  freq?: Freq;
}

export type Bloco = 'BP' | 'DRE' | 'DFC' | 'CMB' | 'HST' | 'MKT' | 'VAL';
export type Unit = 'RATIO' | 'PERCENTUAL' | 'MOEDA' | 'INDICE' | 'OUTRO';
export type AssetType = 'acoes' | 'fiis';
export type ChartType = 'line' | 'bar';
export type Freq = 'A' | 'T' | 'M';

export interface BlocoScores {
  rentabilidade: number;
  solidez: number;
  caixa: number;
  quantitativo: number;
}

export interface QualityDriver {
  indicator: string;
  name: string;
  value: string;
  percentile: number;
  good: boolean;
}

export type TrendLabel = 'improving' | 'stable' | 'deteriorating';

export interface AtivoResumo {
  ticker: string;
  empresa: string;
  setor: string;
  rank: number;
  quality_score: number;
  score_recent: number;
  score_structural: number;
  deterioration_penalty: number;
  improvement_bonus: number;
  trend: TrendLabel;
  bloco_scores: BlocoScores;
  drivers: QualityDriver[];
  red_flags: QualityDriver[];
  data_coverage: number;
}

export interface IndicadorPonto {
  dt_referencia: string;
  valor: number;
  indicador_codigo: string;
  indicador_nome: string;
  bloco: Bloco;
  unidade: Unit;
  freq: Freq;
  ano: number;
  trimestre?: number;
  mes?: number;
}

export interface IndicadorAtual {
  indicador_codigo: string;
  indicador_nome: string;
  bloco: Bloco;
  unidade: Unit;
  valor: number;
  dt_referencia: string;
}

export interface BuscaResult {
  ticker: string;
  empresa: string;
}

export interface AnaliseTexto {
  ticker: string;
  texto: string;
  gerado_em: string;
}

export interface ChartDataPoint {
  label: string;
  value: number;
}

export interface ValuationData {
  ticker: string;
  razao_social?: string;
  setor?: string;
  preco?: number;
  lpa?: number;
  vpa?: number;
  dpa_ttm?: number;
  valor_justo_graham?: number;
  margem_graham_pct?: number;
  preco_teto_bazin_6?: number;
  preco_teto_bazin_10?: number;
  margem_bazin_6_pct?: number;
  margem_bazin_10_pct?: number;
  status_graham_bazin?: string;
  status_simples?: string;
  pl_ttm?: number;
  pvp?: number;
  dy_ttm_pct?: number;
  market_cap_bilhoes?: number;
  ev_ebitda?: number;
  dl_ebitda?: number;
}
