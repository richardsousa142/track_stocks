import { TrendingUp, TrendingDown } from 'lucide-react';
import type { IndicadorAtual } from '../../types';

interface KPIStripProps {
  score?: number;
  indicadores: IndicadorAtual[];
}

interface KPIItem {
  label: string;
  value: string;
  color: string;
  icon?: 'up' | 'down';
}

export default function KPIStrip({ score, indicadores }: KPIStripProps) {
  const kpis: KPIItem[] = [];

  if (score !== undefined) {
    const clr = score >= 85 ? 'text-emerald-600' : score >= 70 ? 'text-amber-600' : 'text-red-600';
    kpis.push({ label: 'Score Geral', value: String(score), color: clr });
  }

  const retorno12m = indicadores.find((i) => i.indicador_codigo === 'mkt_mean_return_252d');
  if (retorno12m) {
    const val = retorno12m.valor;
    kpis.push({
      label: 'Retorno 12m',
      value: `${val >= 0 ? '+' : ''}${(val * 100).toFixed(0)}%`,
      color: val >= 0 ? 'text-emerald-600' : 'text-red-600',
      icon: val >= 0 ? 'up' : 'down',
    });
  }

  const sharpe = indicadores.find((i) => i.indicador_codigo === 'mkt_sharpe_252d');
  if (sharpe) {
    kpis.push({ label: 'Sharpe 252d', value: sharpe.valor.toFixed(2), color: 'text-blue-600' });
  }

  const sortino = indicadores.find((i) => i.indicador_codigo === 'mkt_sortino_252d');
  if (sortino) {
    kpis.push({ label: 'Sortino 252d', value: sortino.valor.toFixed(2), color: 'text-blue-600' });
  }

  if (!kpis.length) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className="bg-white rounded-xl border border-slate-200 px-4 py-3 shadow-sm"
        >
          <div className="text-[11px] text-slate-500 font-medium mb-1">{kpi.label}</div>
          <div className={`text-2xl font-extrabold ${kpi.color} flex items-center gap-1`}>
            {kpi.icon === 'up' && <TrendingUp size={16} />}
            {kpi.icon === 'down' && <TrendingDown size={16} />}
            {kpi.value}
          </div>
        </div>
      ))}
    </div>
  );
}
