import type { IndicadorAtual } from '../../types';

interface FundKPIStripProps {
  indicadores: IndicadorAtual[];
}

function fmtPct(v: number) {
  return `${(v * 100).toFixed(2)}%`;
}

function fmtBRL(v: number) {
  if (Math.abs(v) >= 1e9) return `R$ ${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `R$ ${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `R$ ${(v / 1e3).toFixed(1)}K`;
  return `R$ ${v.toFixed(2)}`;
}

function fmtNum(v: number) {
  return v.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
}

interface KPIConfig {
  code: string;
  label: string;
  fmt: (v: number) => string;
  goodFn?: (v: number) => boolean;
  color?: string;
}

const KPI_CONFIGS: KPIConfig[] = [
  { code: 'fii_vpc',                label: 'VPC',            fmt: fmtBRL },
  { code: 'fii_patrimonio_liquido', label: 'Patrim. Líq.',   fmt: fmtBRL },
  { code: 'fii_passivo_sobre_ativo',label: 'Passivo/Ativo',  fmt: (v) => v.toFixed(2), goodFn: (v) => v < 0.3 },
  { code: 'fii_dy_anual',           label: 'DY Anual (12M)', fmt: fmtPct, goodFn: (v) => v > 0.06 },
  { code: 'fii_dy_mes',             label: 'DY Mensal',      fmt: fmtPct, goodFn: (v) => v > 0.004 },
  { code: 'fii_pct_total_investido',label: '% Investido',    fmt: fmtPct },
  { code: 'fii_total_cotistas',     label: 'Cotistas',       fmt: fmtNum },
];

export default function FundKPIStrip({ indicadores }: FundKPIStripProps) {
  const map: Record<string, number> = {};
  for (const ind of indicadores) {
    map[ind.indicador_codigo] = ind.valor;
  }

  const items = KPI_CONFIGS.flatMap(({ code, label, fmt, goodFn }) => {
    const val = map[code];
    if (val == null) return [];
    const good = goodFn ? goodFn(val) : null;
    const color =
      good === true ? 'text-emerald-600'
      : good === false ? 'text-red-500'
      : 'text-slate-900';
    return [{ label, value: fmt(val), color }];
  });

  if (!items.length) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-5">
      {items.map(({ label, value, color }) => (
        <div
          key={label}
          className="bg-white rounded-xl border border-slate-200 px-4 py-3 shadow-sm"
        >
          <div className="text-[11px] text-slate-500 font-medium mb-1">{label}</div>
          <div className={`text-xl font-extrabold ${color} leading-none`}>{value}</div>
        </div>
      ))}
    </div>
  );
}
