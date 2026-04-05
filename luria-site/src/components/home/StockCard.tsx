import { useNavigate } from 'react-router-dom';
import { CheckCircle2, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { AtivoResumo, TrendLabel } from '../../types';

interface StockCardProps {
  ativo: AtivoResumo;
  delay?: number;
}

const BLOCK_META: { key: keyof AtivoResumo['bloco_scores']; label: string; barColor: string; trackColor: string }[] = [
  { key: 'rentabilidade', label: 'Rent',  barColor: '#059669', trackColor: '#d1fae5' },
  { key: 'solidez',       label: 'Solid', barColor: '#2563eb', trackColor: '#bfdbfe' },
  { key: 'caixa',         label: 'Caixa', barColor: '#d97706', trackColor: '#fde68a' },
  { key: 'quantitativo',  label: 'Quant', barColor: '#7c3aed', trackColor: '#ddd6fe' },
];

const TREND_CFG: Record<TrendLabel, { icon: typeof TrendingUp; color: string; bg: string; label: string }> = {
  improving:     { icon: TrendingUp,   color: '#059669', bg: '#ecfdf5', label: 'Melhorando' },
  stable:        { icon: Minus,        color: '#64748b', bg: '#f1f5f9', label: 'Estável' },
  deteriorating: { icon: TrendingDown, color: '#dc2626', bg: '#fef2f2', label: 'Em queda' },
};

function scoreColor(score: number): string {
  if (score >= 75) return 'text-emerald-600';
  if (score >= 55) return 'text-amber-600';
  return 'text-red-600';
}

function scoreBg(score: number): string {
  if (score >= 75) return 'bg-emerald-50 ring-emerald-200';
  if (score >= 55) return 'bg-amber-50 ring-amber-200';
  return 'bg-red-50 ring-red-200';
}

export default function StockCard({ ativo, delay = 0 }: StockCardProps) {
  const navigate = useNavigate();
  const trend = TREND_CFG[ativo.trend ?? 'stable'];
  const TrendIcon = trend.icon;

  return (
    <div
      className="bg-white rounded-2xl border border-slate-200 p-5 cursor-pointer transition-all duration-200 hover:shadow-card-hover hover:border-slate-300 group animate-fade-in-up"
      style={{ animationDelay: `${delay}ms` }}
      onClick={() => navigate(`/ativo/${ativo.ticker}`)}
    >
      {/* Top: rank + ticker + score */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2.5">
          <span className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-[11px] font-bold text-slate-500">
            {ativo.rank}
          </span>
          <div>
            <div className="text-base font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
              {ativo.ticker}
            </div>
            <div className="text-[11px] text-slate-500 leading-snug truncate max-w-[140px]">
              {ativo.empresa}
            </div>
          </div>
        </div>
        <div className={`flex flex-col items-center px-2.5 py-1.5 rounded-xl ring-1 ${scoreBg(ativo.quality_score)}`}>
          <span className={`text-xl font-extrabold leading-none ${scoreColor(ativo.quality_score)}`}>
            {ativo.quality_score}
          </span>
          <span className="text-[8px] font-semibold text-slate-400 uppercase tracking-wider mt-0.5">
            Quality
          </span>
        </div>
      </div>

      {/* Trend + score breakdown */}
      <div className="flex items-center justify-between mb-3 px-0.5">
        <div
          className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full"
          style={{ color: trend.color, backgroundColor: trend.bg }}
        >
          <TrendIcon size={11} />
          {trend.label}
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-400">
          <span>Rec <strong className="text-slate-600">{ativo.score_recent ?? '-'}</strong></span>
          <span className="w-px h-3" style={{ backgroundColor: '#e2e8f0' }} />
          <span>Estr <strong className="text-slate-600">{ativo.score_structural ?? '-'}</strong></span>
        </div>
      </div>

      {/* Block score bars */}
      <div className="space-y-1.5 mb-3">
        {BLOCK_META.map(({ key, label, barColor, trackColor }) => {
          const score = ativo.bloco_scores[key];
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="text-[10px] font-medium text-slate-500 w-9 shrink-0">{label}</span>
              <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: trackColor }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(2, score)}%`, backgroundColor: barColor }}
                />
              </div>
              <span className="text-[10px] font-semibold text-slate-600 w-5 text-right">{score}</span>
            </div>
          );
        })}
      </div>

      {/* Quality drivers */}
      <div className="flex flex-wrap gap-1 mb-3">
        {ativo.drivers.slice(0, 3).map((d) => (
          <span
            key={d.indicator}
            className="inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-emerald-50 text-emerald-700"
          >
            <CheckCircle2 size={10} />
            {d.name} {d.value}
          </span>
        ))}
        {ativo.red_flags.slice(0, 1).map((d) => (
          <span
            key={d.indicator}
            className="inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-red-50 text-red-600"
          >
            <AlertCircle size={10} />
            {d.name} {d.value}
          </span>
        ))}
      </div>

      {/* Footer */}
      <div className="pt-2.5 border-t border-slate-100 flex items-center justify-between">
        <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
          {ativo.setor || 'B3'}
        </span>
        <span className="text-[10px] text-slate-400">
          {Math.round(ativo.data_coverage * 100)}% cobertura
        </span>
      </div>
    </div>
  );
}
