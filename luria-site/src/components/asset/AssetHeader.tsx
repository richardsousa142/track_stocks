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

function fmtPct(v?: number | null): string | null {
  if (v == null || isNaN(v)) return null;
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

interface ValCardProps {
  label: string;
  value?: number | null;
  margin?: number | null;
  scheme: 'green' | 'red';
}

function ValCard({ label, value, margin, scheme }: ValCardProps) {
  if (value == null) return null;

  const isUp = margin != null && margin >= 0;

  const styles = {
    green: {
      wrap: 'bg-emerald-50 border-emerald-200',
      label: 'text-emerald-600',
      value: 'text-emerald-700',
      pct: 'text-emerald-600',
    },
    red: {
      wrap: 'bg-red-50 border-red-200',
      label: 'text-red-400',
      value: 'text-red-600',
      pct: 'text-red-500',
    },
  }[scheme];

  const pct = fmtPct(margin);

  return (
    <div className={`flex-1 rounded-2xl border px-4 py-3 ${styles.wrap}`}>
      <p className={`text-[9px] font-bold uppercase tracking-widest mb-1.5 ${styles.label}`}>
        {label}
      </p>
      <p className={`text-lg font-semibold leading-none ${styles.value}`}>
        {fmtBRL(value)}
      </p>
      {pct && (
        <p className={`flex items-center gap-1 text-xs font-semibold mt-1.5 ${styles.pct}`}>
          {isUp
            ? <TrendingUp size={11} />
            : <TrendingDown size={11} />}
          {pct}
        </p>
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
      {/* Voltar + nome + ticker */}
      <div className="flex items-center gap-4 mb-4">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700 bg-white border border-slate-200 rounded-xl px-5 py-1.5 shadow-sm transition-all hover:border-slate-300 shrink-0"
        >
          <ArrowLeft size={14} />
          Voltar
        </button>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900">{empresa || ticker}</h1>
            <Badge variant="info">{ticker}</Badge>
          </div>
          {setor && (
            <p className="text-xs text-slate-400 mt-0.5">{setor} · B3</p>
          )}
        </div>
      </div>

      {/* Cards de valuation */}
      {hasValuation && (
        <div className="flex gap-3">
          <ValCard
            label="Graham"
            value={valuation!.valor_justo_graham}
            margin={valuation!.margem_graham_pct}
            scheme={valuation!.margem_graham_pct != null && valuation!.margem_graham_pct >= 0 ? 'green' : 'red'}
          />
          <ValCard
            label="Bazin 6%"
            value={valuation!.preco_teto_bazin_6}
            margin={valuation!.margem_bazin_6_pct}
            scheme={valuation!.margem_bazin_6_pct != null && valuation!.margem_bazin_6_pct >= 0 ? 'green' : 'red'}
          />
          <ValCard
            label="Bazin 10%"
            value={valuation!.preco_teto_bazin_10}
            margin={valuation!.margem_bazin_10_pct}
            scheme={valuation!.margem_bazin_10_pct != null && valuation!.margem_bazin_10_pct >= 0 ? 'green' : 'red'}
          />
        </div>
      )}
    </div>
  );
}
