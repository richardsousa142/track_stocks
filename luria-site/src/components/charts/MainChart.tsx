import { useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceArea, Cell,
} from 'recharts';
import type { ChartType, ChartDataPoint } from '../../types';
import { INDICATORS, formatValue, isGood, getStatusColor } from '../../config/indicators';

interface MainChartProps {
  code: string;
  data: ChartDataPoint[];
  chartType: ChartType;
}

function CustomTooltip({ active, payload, label, code, color }: any) {
  if (!active || !payload?.length) return null;
  const ind = INDICATORS[code];
  const thr = ind?.threshold;

  return (
    <div className="bg-white shadow-lg rounded-lg border border-slate-200 px-3.5 py-2.5 text-xs">
      <div className="text-slate-500 mb-1">{label}</div>
      <div className="text-base font-extrabold" style={{ color }}>
        {formatValue(code, payload[0].value)}
      </div>
      {thr !== undefined && (
        <div className="text-slate-400 text-[10px] mt-0.5">
          limiar {formatValue(code, thr)}
        </div>
      )}
    </div>
  );
}

export default function MainChart({ code, data, chartType }: MainChartProps) {
  const ind = INDICATORS[code];

  const { last, color, yMin, yMax, thr } = useMemo(() => {
    const vals = data.map((d) => d.value);
    const lastVal = vals[vals.length - 1] ?? 0;
    const clr = getStatusColor(code, lastVal);
    const mn = Math.min(...vals);
    const mx = Math.max(...vals);
    const threshold = ind?.threshold;
    const yMn = threshold !== undefined ? Math.min(mn, threshold) * 0.85 : mn * 0.9;
    const yMx = threshold !== undefined ? Math.max(mx, threshold) * 1.12 : mx * 1.1;
    return { last: lastVal, color: clr, yMin: yMn, yMax: yMx, thr: threshold };
  }, [data, code, ind]);

  const good = thr !== undefined ? isGood(code, last) : null;

  if (!data.length) {
    return (
      <div className="py-12 text-center text-slate-400 text-sm">
        Dados insuficientes para este indicador
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-end mb-4">
        <div>
          <div className="text-3xl font-extrabold" style={{ color }}>
            {formatValue(code, last)}
          </div>
          <div className="text-sm text-slate-500 mt-0.5">{ind?.name}</div>
        </div>
        {thr !== undefined && (
          <div className="text-right">
            <div className="flex items-center gap-1.5 justify-end">
              <div
                className="w-2 h-2 rounded-full"
                style={{ background: good ? '#059669' : '#dc2626' }}
              />
              <span className="text-xs font-semibold" style={{ color: good ? '#059669' : '#dc2626' }}>
                {good
                  ? ind?.higherBetter ? 'Acima do limiar' : 'Abaixo do limiar'
                  : ind?.higherBetter ? 'Abaixo do limiar' : 'Acima do limiar'}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Limiar: {formatValue(code, thr)}
            </div>
          </div>
        )}
      </div>

      <ResponsiveContainer width="100%" height={240}>
        {chartType === 'line' ? (
          <AreaChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="mainGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.15} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            {thr !== undefined && (
              <>
                {ind?.higherBetter ? (
                  <>
                    <ReferenceArea y1={yMin} y2={thr} fill="rgba(220,38,38,0.03)" />
                    <ReferenceArea y1={thr} y2={yMax} fill="rgba(5,150,105,0.03)" />
                  </>
                ) : (
                  <>
                    <ReferenceArea y1={yMin} y2={thr} fill="rgba(5,150,105,0.03)" />
                    <ReferenceArea y1={thr} y2={yMax} fill="rgba(220,38,38,0.03)" />
                  </>
                )}
                <ReferenceLine
                  y={thr}
                  stroke="#d97706"
                  strokeDasharray="6 3"
                  strokeWidth={1.5}
                  label={{ value: 'limiar', fill: '#d97706', fontSize: 10, position: 'insideTopRight' }}
                />
              </>
            )}
            <XAxis
              dataKey="label"
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval={Math.max(0, Math.floor(data.length / 6) - 1)}
            />
            <YAxis
              domain={[yMin, yMax]}
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => formatValue(code, v)}
              width={52}
            />
            <Tooltip content={<CustomTooltip code={code} color={color} />} />
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              fill="url(#mainGrad)"
              dot={false}
              activeDot={{ r: 4, fill: color, stroke: '#fff', strokeWidth: 2 }}
            />
          </AreaChart>
        ) : (
          <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            {thr !== undefined && (
              <ReferenceLine y={thr} stroke="#d97706" strokeDasharray="6 3" strokeWidth={1.5} />
            )}
            <XAxis
              dataKey="label"
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval={Math.max(0, Math.floor(data.length / 6) - 1)}
            />
            <YAxis
              domain={[yMin, yMax]}
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => formatValue(code, v)}
              width={52}
            />
            <Tooltip content={<CustomTooltip code={code} color={color} />} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {data.map((d, i) => {
                const g = thr !== undefined ? isGood(code, d.value) : null;
                const c = g === null ? '#2563eb' : g ? '#059669' : '#dc2626';
                return <Cell key={i} fill={c} fillOpacity={0.75} />;
              })}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
