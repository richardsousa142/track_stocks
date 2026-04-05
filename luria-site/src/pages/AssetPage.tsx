import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { LineChart as LineChartIcon, BarChart3 } from 'lucide-react';
import { useIndicadorSerie, useTodosIndicadores, useValuation } from '../hooks/useIndicadores';
import { useAppStore } from '../store/useAppStore';
import { INDICATORS, BLOCOS, BLOCO_LABEL, resolveFreq } from '../config/indicators';
import type { ChartType, Freq } from '../types';
import AssetHeader from '../components/asset/AssetHeader';
import KPIStrip from '../components/asset/KPIStrip';
import AIAnalysis from '../components/asset/AIAnalysis';
import MainChart from '../components/charts/MainChart';
import MiniChart from '../components/charts/MiniChart';
import IndicatorSelector from '../components/asset/IndicatorSelector';

export default function AssetPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [mainIndicator, setMainIndicator] = useState('mkt_pl_ttm');
  const [chartType, setChartType] = useState<ChartType>('line');
  const { selectedMiniIndicators, setMiniIndicators } = useAppStore();

  const freq: Freq = resolveFreq(mainIndicator);

  const { data: mainData = [], isLoading: mainLoading } = useIndicadorSerie(
    ticker ?? '',
    mainIndicator,
    freq
  );

  const { data: allIndicadores = [] } = useTodosIndicadores(ticker ?? '');
  const { data: valuation } = useValuation(ticker ?? '');

  const empresaNome =
    valuation?.razao_social ||
    allIndicadores[0]?.indicador_nome ||
    ticker ||
    '';

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <AssetHeader
        ticker={ticker ?? ''}
        empresa={empresaNome}
        setor={valuation?.setor}
        valuation={valuation}
      />

      <KPIStrip indicadores={allIndicadores} />

      <AIAnalysis ticker={ticker ?? ''} />

      {/* Main Chart */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-sm mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">Gráfico</span>
            <select
              value={mainIndicator}
              onChange={(e) => setMainIndicator(e.target.value)}
              className="flex-1 min-w-[220px] bg-slate-50 border border-slate-200 text-slate-700 rounded-lg py-2 px-3 text-sm outline-none cursor-pointer focus:border-emerald-400 focus:ring-1 focus:ring-emerald-100 transition-all"
            >
              {BLOCOS.map((bloco) => {
                const items = Object.entries(INDICATORS).filter(([, v]) => v.bloco === bloco);
                if (!items.length) return null;
                return (
                  <optgroup key={bloco} label={BLOCO_LABEL[bloco] ?? bloco}>
                    {items.map(([k, v]) => (
                      <option key={k} value={k}>
                        {v.name}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          </div>

          <div className="flex bg-slate-100 rounded-lg p-0.5">
            {([
              { type: 'line' as const, icon: LineChartIcon, label: 'Linha' },
              { type: 'bar' as const, icon: BarChart3, label: 'Barra' },
            ]).map(({ type, icon: Icon, label }) => (
              <button
                key={type}
                onClick={() => setChartType(type)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  chartType === type
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {mainLoading ? (
          <div className="skeleton h-[280px] w-full rounded-xl" />
        ) : (
          <MainChart code={mainIndicator} data={mainData} chartType={chartType} />
        )}
      </div>

      {/* Mini Charts Section */}
      <IndicatorSelector applied={selectedMiniIndicators} onApply={setMiniIndicators} />

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {selectedMiniIndicators.map((code) => (
          <MiniChartWrapper key={code} ticker={ticker ?? ''} code={code} />
        ))}
      </div>
    </main>
  );
}

function MiniChartWrapper({ ticker, code }: { ticker: string; code: string }) {
  const freq: Freq = resolveFreq(code);
  const { data = [], isLoading } = useIndicadorSerie(ticker, code, freq);

  if (isLoading) return <div className="skeleton h-[140px] rounded-xl" />;

  return <MiniChart code={code} data={data} />;
}
