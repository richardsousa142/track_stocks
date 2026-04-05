import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis,
  Tooltip, ResponsiveContainer,
  ReferenceLine, ReferenceArea,
} from 'recharts';
import { INDICATORS, BLOCO_COLORS, formatValue, isGood, getStatusColor } from '../../config/indicators';
import type { ChartDataPoint, Bloco } from '../../types';

interface MiniChartProps {
  code: string;
  data: ChartDataPoint[];
}

function MiniTooltip({ active, payload, label, code, color }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white shadow-md rounded-md border border-slate-200 px-2.5 py-1.5 text-[11px]">
      <div className="text-slate-400 mb-0.5">{label}</div>
      <div className="font-bold" style={{ color }}>
        {formatValue(code, payload[0].value)}
      </div>
    </div>
  );
}

export default function MiniChart({ code, data }: MiniChartProps) {
  const ind = INDICATORS[code];
  if (!ind) return null;

  const { last, color, yMin, yMax, thr, gradId } = useMemo(() => {
    const vals = data.map((d) => d.value);
    const lastVal = vals[vals.length - 1] ?? 0;
    const clr = getStatusColor(code, lastVal);
    const mn = Math.min(...vals);
    const mx = Math.max(...vals);
    const threshold = ind.threshold;
    const yMn = threshold !== undefined ? Math.min(mn, threshold) * 0.88 : mn * 0.9;
    const yMx = threshold !== undefined ? Math.max(mx, threshold) * 1.1 : mx * 1.1;
    return {
      last: lastVal,
      color: clr,
      yMin: yMn,
      yMax: yMx,
      thr: threshold,
      gradId: `g${code.replace(/[^a-z0-9]/g, '')}`,
    };
  }, [data, code, ind]);

  if (!data.length) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4 text-center text-xs text-slate-400">
        Dados insuficientes
      </div>
    );
  }

  return (
    <div
      className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-card transition-shadow"
      aria-label={`Mini gráfico ${ind.name}`}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <div
            className="text-[10px] font-extrabold mb-0.5 tracking-widest uppercase"
            style={{ color: BLOCO_COLORS[ind.bloco as Bloco] || '#64748b' }}
          >
            {ind.bloco}
          </div>
          <div className="text-xs font-medium text-slate-700 leading-snug">
            {ind.name}
          </div>
        </div>
        <div className="text-right">
          <div className="text-base font-extrabold" style={{ color }}>
            {formatValue(code, last)}
          </div>
          <div className="text-[9px] text-slate-400 mt-px">
            {ind.higherBetter ? '↑ maior=melhor' : '↓ menor=melhor'}
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={64}>
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.15} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          {thr !== undefined && (
            <>
              {ind.higherBetter ? (
                <>
                  <ReferenceArea y1={yMin} y2={thr} fill="rgba(220,38,38,.04)" />
                  <ReferenceArea y1={thr} y2={yMax} fill="rgba(5,150,105,.04)" />
                </>
              ) : (
                <>
                  <ReferenceArea y1={yMin} y2={thr} fill="rgba(5,150,105,.04)" />
                  <ReferenceArea y1={thr} y2={yMax} fill="rgba(220,38,38,.04)" />
                </>
              )}
              <ReferenceLine y={thr} stroke="rgba(217,119,6,.5)" strokeDasharray="3 2" strokeWidth={1} />
            </>
          )}
          <XAxis dataKey="label" hide />
          <YAxis domain={[yMin, yMax]} hide />
          <Tooltip content={<MiniTooltip code={code} color={color} />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${gradId})`}
            dot={false}
            activeDot={{ r: 3, fill: color, stroke: '#fff', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>

      {thr !== undefined && (
        <div className="flex items-center gap-1.5 mt-1.5">
          <div className="w-3 h-px bg-amber-400" />
          <span className="text-[9px] text-slate-400">limiar {formatValue(code, thr)}</span>
        </div>
      )}
    </div>
  );
}
