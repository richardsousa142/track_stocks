import { useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingUp, TrendingDown, Minus, Building2 } from 'lucide-react';
import type { FiiMeta, TrendLabel } from '../../types';

interface FundHeaderProps {
  cnpj: string;
  meta?: FiiMeta | null;
}

const TREND_CFG: Record<TrendLabel, { icon: typeof TrendingUp; color: string; bg: string; border: string; label: string }> = {
  improving:     { icon: TrendingUp,   color: '#059669', bg: '#ecfdf5', border: '#a7f3d0', label: 'Melhorando' },
  stable:        { icon: Minus,        color: '#64748b', bg: '#f1f5f9', border: '#e2e8f0', label: 'Estável'    },
  deteriorating: { icon: TrendingDown, color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Em queda'   },
};

export default function FundHeader({ cnpj, meta }: FundHeaderProps) {
  const navigate = useNavigate();
  // Enquanto meta carrega: placeholder vazio (não exibe CNPJ bruto)
  const nome = meta?.nome_fundo ?? (meta === null ? cnpj : '');
  const segmento = meta?.segmento ?? 'FII';
  const score = meta?.quality_score;
  const trend = meta?.trend ? TREND_CFG[meta.trend] : TREND_CFG.stable;
  const TrendIcon = trend.icon;

  const scoreColor =
    score == null     ? 'text-slate-400'
    : score >= 75     ? 'text-emerald-600'
    : score >= 55     ? 'text-amber-500'
    : 'text-red-500';

  return (
    <div className="mb-6">
      <div className="flex items-center gap-4 mb-4">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700 bg-white border border-slate-200 rounded-xl px-5 py-1.5 shadow-sm transition-all hover:border-slate-300 shrink-0"
        >
          <ArrowLeft size={14} />
          Voltar
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2.5 mb-0.5">
            {nome ? (
              <h1 className="text-xl font-bold text-slate-900 leading-tight truncate">{nome}</h1>
            ) : (
              <div className="skeleton h-6 w-64 rounded-lg" />
            )}
          </div>
          <div className="flex items-center gap-2">
            <Building2 size={11} className="text-slate-400 shrink-0" />
            <span className="text-xs text-slate-400">{segmento}</span>
            {meta?.nome_administrador && (
              <>
                <span className="text-slate-300">·</span>
                <span className="text-xs text-slate-400 truncate">{meta.nome_administrador}</span>
              </>
            )}
          </div>
        </div>

        {/* Score + trend compacto */}
        {score != null && (
          <div className="flex items-center gap-3 shrink-0">
            <div
              className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-md border"
              style={{ color: trend.color, backgroundColor: trend.bg, borderColor: trend.border }}
            >
              <TrendIcon size={10} strokeWidth={2.5} />
              {trend.label}
            </div>
            <div className="bg-white border border-slate-200 rounded-xl px-4 py-2 shadow-sm text-center">
              <div className={`text-2xl font-extrabold leading-none ${scoreColor}`}>{score}</div>
              <div className="text-[9px] font-bold text-slate-400 tracking-widest uppercase mt-0.5">Score</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
