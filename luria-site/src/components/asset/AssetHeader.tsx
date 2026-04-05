import { useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingDown, TrendingUp } from 'lucide-react';
import Badge from '../ui/Badge';
import type { ValuationData } from '../../types';

interface AssetHeaderProps {
  ticker: string;
  empresa: string;
  setor?: string;
  valuation?: ValuationData | null;
}

function fmtBRL(v?: number | null) {
  if (v == null || isNaN(v)) return '—';
  return `R$ ${v.toFixed(2)}`;
}

function fmtPct(v?: number | null) {
  if (v == null || isNaN(v)) return null;
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

interface ValuationBadgeProps {
  label: string;
  value?: number | null;
  margin?: number | null;
  colorScheme: 'emerald' | 'cyan' | 'amber';
}

function ValuationBadge({ label, value, margin, colorScheme }: ValuationBadgeProps) {
  if (value == null) return null;

  const schemes = {
    emerald: {
      wrap: 'bg-emerald-50 border-emerald-200',
      label: 'text-emerald-600',
      value: 'text-emerald-900',
      pct: margin != null && margin >= 0 ? 'text-emerald-600' : 'text-red-500',
    },
    cyan: {
      wrap: 'bg-cyan-50 border-cyan-200',
      label: 'text-cyan-600',
      value: 'text-cyan-900',
      pct: margin != null && margin >= 0 ? 'text-emerald-600' : 'text-red-500',
    },
    amber: {
      wrap: 'bg-amber-50 border-amber-200',
      label: 'text-amber-600',
      value: 'text-amber-900',
      pct: margin != null && margin >= 0 ? 'text-emerald-600' : 'text-red-500',
    },
  };

  const s = schemes[colorScheme];
  const pctStr = fmtPct(margin);

  return (
    <div className={`flex flex-col px-3 py-2 rounded-xl border ${s.wrap} min-w-[110px]`}>
      <span className={`text-[10px] font-semibold uppercase tracking-wide ${s.label} mb-0.5`}>
        {label}
      </span>
      <span className={`text-sm font-bold ${s.value} leading-tight`}>{fmtBRL(value)}</span>
      {pctStr && (
        <span className={`text-[11px] font-semibold ${s.pct} flex items-center gap-0.5 mt-0.5`}>
          {margin != null && margin >= 0
            ? <TrendingDown size={10} />
            : <TrendingUp size={10} />}
          {pctStr}
        </span>
      )}
    </div>
  );
}

export default function AssetHeader({ ticker, empresa, setor, valuation }: AssetHeaderProps) {
  const navigate = useNavigate();

  const hasValuation =
    valuation != null &&
    (valuation.valor_justo_graham != null ||
      valuation.preco_teto_bazin_6 != null ||
      valuation.preco_teto_bazin_10 != null);

  return (
    <div className="mb-6">
      {/* Linha principal: voltar + ticker/nome */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate('/')}
          className="mt-0.5 w-9 h-9 rounded-xl bg-white border border-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 transition-all shadow-sm shrink-0"
        >
          <ArrowLeft size={16} />
        </button>

        <div className="flex-1 min-w-0">
          {/* Nome + ticker */}
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900 truncate">{empresa || ticker}</h1>
            <Badge variant="info">{ticker}</Badge>
          </div>
          {setor && (
            <p className="text-xs text-slate-500 mt-0.5">{setor} · B3</p>
          )}

          {/* Badges de valuation */}
          {hasValuation && (
            <div className="flex flex-wrap gap-2 mt-3">
              <ValuationBadge
                label="Graham"
                value={valuation!.valor_justo_graham}
                margin={valuation!.margem_graham_pct}
                colorScheme="emerald"
              />
              <ValuationBadge
                label="Bazin 6%"
                value={valuation!.preco_teto_bazin_6}
                margin={valuation!.margem_bazin_6_pct}
                colorScheme="cyan"
              />
              <ValuationBadge
                label="Bazin 10%"
                value={valuation!.preco_teto_bazin_10}
                margin={valuation!.margem_bazin_10_pct}
                colorScheme="amber"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
