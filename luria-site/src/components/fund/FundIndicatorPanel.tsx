import type { IndicadorAtual } from '../../types';
import { formatValue } from '../../config/indicators';

interface FundIndicatorPanelProps {
  indicadores: IndicadorAtual[];
}

interface Section {
  title: string;
  codes: string[];
  color: string;
}

const SECTIONS: Section[] = [
  {
    title: 'Patrimônio e Estrutura',
    color: '#2563eb',
    codes: [
      'fii_vpc', 'fii_patrimonio_liquido', 'fii_ativo_total',
      'fii_passivo_total', 'fii_disponibilidades',
      'fii_passivo_sobre_ativo', 'fii_passivo_sobre_pl',
      'fii_disponibilidades_sobre_ativo',
    ],
  },
  {
    title: 'Composição do Portfólio',
    color: '#0d9488',
    codes: [
      'fii_pct_total_investido', 'fii_pct_caixa', 'fii_pct_liquidez',
      'fii_pct_imoveis', 'fii_pct_imoveis_construcao', 'fii_pct_terrenos',
      'fii_pct_cri_cra', 'fii_pct_lci_lca_lig', 'fii_pct_outros_vm',
      'fii_pct_direitos_reais', 'fii_pct_recebiveis',
    ],
  },
  {
    title: 'Distribuição',
    color: '#059669',
    codes: ['fii_dy_anual', 'fii_dy_mes', 'fii_rendimentos_sobre_pl'],
  },
  {
    title: 'Eficiência de Custos',
    color: '#d97706',
    codes: ['fii_pct_despesas_adm', 'fii_taxa_adm_pagar_sobre_pl', 'fii_taxa_perf_pagar_sobre_pl'],
  },
  {
    title: 'Cotistas',
    color: '#7c3aed',
    codes: ['fii_total_cotistas', 'fii_pct_pf', 'fii_pct_pj_nao_fin'],
  },
];

export default function FundIndicatorPanel({ indicadores }: FundIndicatorPanelProps) {
  const map: Record<string, IndicadorAtual> = {};
  for (const ind of indicadores) {
    map[ind.indicador_codigo] = ind;
  }

  return (
    <div className="space-y-5 mb-6">
      {SECTIONS.map(({ title, codes, color }) => {
        const items = codes.flatMap((code) => {
          const ind = map[code];
          if (!ind) return [];
          return [ind];
        });
        if (!items.length) return null;

        return (
          <div key={title} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: color }}
              />
              <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-px bg-slate-100">
              {items.map((ind) => (
                <IndicadorCard key={ind.indicador_codigo} ind={ind} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function IndicadorCard({ ind }: { ind: IndicadorAtual }) {
  const value = formatValue(ind.indicador_codigo, ind.valor);
  const dateStr = new Date(ind.dt_referencia).toLocaleDateString('pt-BR', {
    month: 'short', year: 'numeric',
  });

  return (
    <div className="bg-white px-4 py-3">
      <div className="text-[10px] font-medium text-slate-400 mb-1 truncate">{ind.indicador_nome}</div>
      <div className="text-base font-bold text-slate-900 leading-none">{value}</div>
      <div className="text-[9px] text-slate-300 mt-1">{dateStr}</div>
    </div>
  );
}
