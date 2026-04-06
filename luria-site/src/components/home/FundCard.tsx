import { Link } from 'react-router-dom';
import { Check, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { FiiResumo, TrendLabel } from '../../types';
import ScoreRing from '../ui/ScoreRing';

interface FundCardProps {
  fii: FiiResumo;
  delay?: number;
}

const BLOCK_META: { key: keyof FiiResumo['bloco_scores']; label: string; barColor: string; trackColor: string; numColor: string }[] = [
  { key: 'solidez',      label: 'Solid',  barColor: '#2563eb', trackColor: '#bfdbfe', numColor: '#2563eb' },
  { key: 'portfolio',    label: 'Port',   barColor: '#0d9488', trackColor: '#ccfbf1', numColor: '#0d9488' },
  { key: 'distribuicao', label: 'Dist',   barColor: '#059669', trackColor: '#d1fae5', numColor: '#059669' },
  { key: 'eficiencia',   label: 'Efic',   barColor: '#d97706', trackColor: '#fde68a', numColor: '#d97706' },
];

const TREND_CFG: Record<TrendLabel, { icon: typeof TrendingUp; color: string; bg: string; border: string; label: string }> = {
  improving:     { icon: TrendingUp,   color: '#059669', bg: '#ecfdf5', border: '#a7f3d0', label: 'Melhorando' },
  stable:        { icon: Minus,        color: '#64748b', bg: '#f1f5f9', border: '#e2e8f0', label: 'Estável'    },
  deteriorating: { icon: TrendingDown, color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Em queda'   },
};

const BADGE_PALETTE = [
  { bg: '#f0fdfa', text: '#0d9488' },
  { bg: '#eff6ff', text: '#2563eb' },
  { bg: '#ecfdf5', text: '#059669' },
  { bg: '#fff7ed', text: '#c2410c' },
  { bg: '#f0f9ff', text: '#0891b2' },
  { bg: '#fdf4ff', text: '#a21caf' },
];

function cnpjBadgeColor(cnpj: string) {
  const idx = (cnpj.charCodeAt(0) + (cnpj.charCodeAt(1) ?? 0)) % BADGE_PALETTE.length;
  return BADGE_PALETTE[idx];
}

function segmentoAbbr(seg: string): string {
  const map: Record<string, string> = {
    'Lajes Corporativas': 'Corp',
    'Shoppings': 'Shop',
    'Logística': 'Log',
    'Recebíveis': 'Receb',
    'Híbrido': 'Híbr',
    'Outros': 'Outro',
    'Residencial': 'Resid',
    'Educacional': 'Educ',
    'Hoteleiro': 'Hotel',
  };
  return map[seg] ?? seg.slice(0, 5);
}

export default function FundCard({ fii, delay = 0 }: FundCardProps) {
  const trend = TREND_CFG[fii.trend ?? 'stable'];
  const TrendIcon = trend.icon;
  const badge = cnpjBadgeColor(fii.cnpj);

  const allDrivers = [
    ...fii.drivers.slice(0, 3).map((d) => ({ ...d, good: true })),
    ...fii.red_flags.slice(0, 1).map((d) => ({ ...d, good: false })),
  ];

  const nomeCurto = fii.nome_fundo.length > 32
    ? fii.nome_fundo.slice(0, 30) + '…'
    : fii.nome_fundo;

  return (
    <Link
      to={`/fundo/${fii.cnpj}`}
      className="bg-white rounded-2xl border border-slate-200 p-5 transition-all duration-200 hover:shadow-card-hover hover:border-slate-300 group animate-fade-in-up flex flex-col gap-4 no-underline text-inherit"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Header: badge + nome + score ring */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-extrabold shrink-0"
            style={{ backgroundColor: badge.bg, color: badge.text }}
          >
            {fii.rank}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-base font-bold text-slate-900 group-hover:text-teal-700 transition-colors leading-none">
                {nomeCurto}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="text-[9px] font-semibold px-1.5 py-0.5 rounded-md"
                style={{ backgroundColor: badge.bg, color: badge.text }}
              >
                {segmentoAbbr(fii.segmento)}
              </span>
            </div>
          </div>
        </div>
        <ScoreRing score={fii.quality_score} size={50} />
      </div>

      {/* Barras de score */}
      <div className="bg-slate-50 rounded-xl px-3 py-3 space-y-2">
        {BLOCK_META.map(({ key, label, barColor, trackColor, numColor }) => {
          const score = fii.bloco_scores?.[key] ?? 0;
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

      {/* Trend + Rec/Estr */}
      <div className="flex items-center justify-between">
        <div
          className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-md border"
          style={{ color: trend.color, backgroundColor: trend.bg, borderColor: trend.border }}
        >
          <TrendIcon size={10} strokeWidth={2.5} />
          {trend.label}
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-400">
          <span>Rec <strong className="text-slate-600">{fii.score_recent ?? '—'}</strong></span>
          <span className="w-px h-3 bg-slate-200" />
          <span>Estr <strong className="text-slate-600">{fii.score_structural ?? '—'}</strong></span>
        </div>
      </div>

      {/* Quality drivers */}
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
