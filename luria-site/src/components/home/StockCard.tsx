import { Link } from 'react-router-dom';
import { Check, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { AtivoResumo, TrendLabel } from '../../types';
import ScoreRing from '../ui/ScoreRing';

interface StockCardProps {
  ativo: AtivoResumo;
  delay?: number;
}

const BLOCK_META: { key: keyof AtivoResumo['bloco_scores']; label: string; barColor: string; trackColor: string; numColor: string }[] = [
  { key: 'rentabilidade', label: 'Rent',  barColor: '#059669', trackColor: '#d1fae5', numColor: '#059669' },
  { key: 'solidez',       label: 'Solid', barColor: '#2563eb', trackColor: '#bfdbfe', numColor: '#2563eb' },
  { key: 'caixa',         label: 'Caixa', barColor: '#d97706', trackColor: '#fde68a', numColor: '#d97706' },
  { key: 'quantitativo',  label: 'Quant', barColor: '#7c3aed', trackColor: '#ddd6fe', numColor: '#7c3aed' },
];

const TREND_CFG: Record<TrendLabel, { icon: typeof TrendingUp; color: string; bg: string; border: string; label: string }> = {
  improving:     { icon: TrendingUp,   color: '#059669', bg: '#ecfdf5', border: '#a7f3d0', label: 'Melhorando' },
  stable:        { icon: Minus,        color: '#64748b', bg: '#f1f5f9', border: '#e2e8f0', label: 'Estável'    },
  deteriorating: { icon: TrendingDown, color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Em queda'   },
};

const BADGE_PALETTE = [
  { bg: '#ecfdf5', text: '#059669' },
  { bg: '#eff6ff', text: '#2563eb' },
  { bg: '#f5f3ff', text: '#7c3aed' },
  { bg: '#fff7ed', text: '#c2410c' },
  { bg: '#f0f9ff', text: '#0891b2' },
  { bg: '#fdf4ff', text: '#a21caf' },
];

function tickerBadgeColor(ticker: string) {
  const idx = (ticker.charCodeAt(0) + (ticker.charCodeAt(1) ?? 0)) % BADGE_PALETTE.length;
  return BADGE_PALETTE[idx];
}


export default function StockCard({ ativo, delay = 0 }: StockCardProps) {
  const trend = TREND_CFG[ativo.trend ?? 'stable'];
  const TrendIcon = trend.icon;
  const badge = tickerBadgeColor(ativo.ticker);

  const allDrivers = [
    ...ativo.drivers.slice(0, 3).map((d) => ({ ...d, good: true })),
    ...ativo.red_flags.slice(0, 1).map((d) => ({ ...d, good: false })),
  ];

  return (
    <Link
      to={`/ativo/${ativo.ticker}`}
      className="bg-white rounded-2xl border border-slate-200 p-5 transition-all duration-200 hover:shadow-card-hover hover:border-slate-300 group animate-fade-in-up flex flex-col gap-4 no-underline text-inherit"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Header: badge + nome + score ring */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {/* Rank badge colorido */}
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-extrabold shrink-0"
            style={{ backgroundColor: badge.bg, color: badge.text }}
          >
            {ativo.rank}
          </div>
          <div className="min-w-0">
            <div className="text-base font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
              {ativo.ticker}
            </div>
            <div className="text-[11px] text-slate-400 truncate leading-tight">
              {ativo.empresa}
            </div>
          </div>
        </div>
        <ScoreRing score={ativo.quality_score} size={50} />
      </div>

      {/* Barras de score */}
      <div className="bg-slate-50 rounded-xl px-3 py-3 space-y-2">
        {BLOCK_META.map(({ key, label, barColor, trackColor, numColor }) => {
          const score = ativo.bloco_scores[key];
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="text-[10px] font-medium text-slate-400 w-9 shrink-0">{label}</span>
              <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: trackColor }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(2, score)}%`, backgroundColor: barColor }}
                />
              </div>
              <span className="text-[10px] font-bold w-6 text-right" style={{ color: numColor }}>
                {score}
              </span>
            </div>
          );
        })}
      </div>

      {/* Trend + Rec / Estr */}
      <div className="flex items-center justify-between">
        <div
          className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-md border"
          style={{ color: trend.color, backgroundColor: trend.bg, borderColor: trend.border }}
        >
          <TrendIcon size={10} strokeWidth={2.5} />
          {trend.label}
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-400">
          <span>Rec <strong className="text-slate-600">{ativo.score_recent ?? '—'}</strong></span>
          <span className="w-px h-3 bg-slate-200" />
          <span>Estr <strong className="text-slate-600">{ativo.score_structural ?? '—'}</strong></span>
        </div>
      </div>

      {/* Indicadores em grid 2 colunas */}
      {allDrivers.length > 0 && (
        <div className="grid grid-cols-2 gap-1.5 pt-3 border-t border-slate-100">
          {allDrivers.map((d) =>
            d.good ? (
              <span
                key={d.indicator}
                className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 truncate"
              >
                <Check size={10} strokeWidth={2.5} className="shrink-0" />
                <span className="truncate">{d.name} {d.value}</span>
              </span>
            ) : (
              <span
                key={d.indicator}
                className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-md bg-red-50 text-red-600 border border-red-200 truncate"
              >
                <AlertCircle size={10} className="shrink-0" />
                <span className="truncate">{d.name} {d.value}</span>
              </span>
            )
          )}
        </div>
      )}
    </Link>
  );
}
