import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { LineChart as LineChartIcon, BarChart3, SlidersHorizontal, X, Check, Search } from 'lucide-react';
import { useFii, useFiiIndicadorSerie, useFiiTodosIndicadores } from '../hooks/useFiis';
import { INDICATORS, FII_BLOCOS, BLOCO_COLORS, BLOCO_LABEL, BLOCO_BG } from '../config/indicators';
import type { ChartType, Bloco } from '../types';
import FundHeader from '../components/fund/FundHeader';
import FundKPIStrip from '../components/fund/FundKPIStrip';
import FundIndicatorPanel from '../components/fund/FundIndicatorPanel';
import MainChart from '../components/charts/MainChart';
import MiniChart from '../components/charts/MiniChart';

const FII_INDICATORS = Object.entries(INDICATORS).filter(([, v]) => v.bloco === 'FII');
const DEFAULT_MAIN = 'fii_passivo_sobre_ativo';
const DEFAULT_MINI = ['fii_dy_anual', 'fii_dy_mes', 'fii_passivo_sobre_ativo', 'fii_pct_total_investido'];

export default function FundPage() {
  const { cnpj } = useParams<{ cnpj: string }>();
  const [mainIndicator, setMainIndicator] = useState(DEFAULT_MAIN);
  const [chartType, setChartType] = useState<ChartType>('line');
  const [selectedMini, setSelectedMini] = useState<string[]>(DEFAULT_MINI);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorDraft, setSelectorDraft] = useState<string[]>([]);
  const [selectorSearch, setSelectorSearch] = useState('');

  const { data: meta } = useFii(cnpj ?? '');
  const { data: allIndicadores = [] } = useFiiTodosIndicadores(cnpj ?? '');
  const { data: mainData = [], isLoading: mainLoading } = useFiiIndicadorSerie(cnpj ?? '', mainIndicator);

  function openSelector() {
    setSelectorDraft([...selectedMini]);
    setSelectorSearch('');
    setSelectorOpen(true);
  }

  function closeSelector() {
    setSelectorOpen(false);
    setSelectorDraft([]);
  }

  function confirmSelector() {
    setSelectedMini(selectorDraft);
    setSelectorOpen(false);
  }

  const filteredForSelector = FII_INDICATORS.filter(
    ([k, v]) =>
      k.toLowerCase().includes(selectorSearch.toLowerCase()) ||
      v.name.toLowerCase().includes(selectorSearch.toLowerCase())
  );

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 py-6">
      <FundHeader cnpj={cnpj ?? ''} meta={meta} />

      <FundKPIStrip indicadores={allIndicadores} />

      {/* Main Chart */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-sm mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">Gráfico</span>
            <select
              value={mainIndicator}
              onChange={(e) => setMainIndicator(e.target.value)}
              className="flex-1 min-w-[220px] bg-slate-50 border border-slate-200 text-slate-700 rounded-lg py-2 px-3 text-sm outline-none cursor-pointer focus:border-teal-400 focus:ring-1 focus:ring-teal-100 transition-all"
            >
              {FII_BLOCOS.map((bloco) => {
                const items = Object.entries(INDICATORS).filter(([, v]) => v.bloco === bloco);
                if (!items.length) return null;
                return (
                  <optgroup key={bloco} label={BLOCO_LABEL[bloco] ?? bloco}>
                    {items.map(([k, v]) => (
                      <option key={k} value={k}>{v.name}</option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          </div>

          <div className="flex bg-slate-100 rounded-lg p-0.5">
            {([
              { type: 'line' as const, icon: LineChartIcon, label: 'Linha' },
              { type: 'bar'  as const, icon: BarChart3,     label: 'Barra' },
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

      {/* Indicator Panel — grid organizado por categoria */}
      <FundIndicatorPanel indicadores={allIndicadores} />

      {/* Mini Charts Section */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Séries históricas</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {selectedMini.length} de {FII_INDICATORS.length} indicadores
            </p>
          </div>
          <button
            onClick={selectorOpen ? closeSelector : openSelector}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border text-xs font-semibold transition-all ${
              selectorOpen
                ? 'border-teal-300 bg-teal-50 text-teal-700'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 shadow-sm'
            }`}
          >
            {selectorOpen ? <X size={14} /> : <SlidersHorizontal size={14} />}
            {selectorOpen ? 'Fechar' : 'Editar seleção'}
          </button>
        </div>

        {selectorOpen && (
          <div className="bg-white border border-slate-200 rounded-xl shadow-card overflow-hidden mb-4 animate-slide-down">
            <div className="p-4 border-b border-slate-100">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={selectorSearch}
                  onChange={(e) => setSelectorSearch(e.target.value)}
                  placeholder="Filtrar indicadores FII..."
                  className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg py-2 pl-9 pr-3 text-sm outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-100 transition-all placeholder:text-slate-400"
                />
              </div>
              <div className="flex items-center gap-3 mt-3 text-[11px]">
                <span className="inline-flex items-center gap-1 text-slate-500">
                  <span className="w-2 h-2 rounded-full bg-teal-500" />
                  {selectorDraft.length} selecionados
                </span>
              </div>
            </div>

            <div className="p-4 max-h-[360px] overflow-y-auto">
              {FII_BLOCOS.map((bloco) => {
                const group = filteredForSelector.filter(([, v]) => v.bloco === bloco);
                if (!group.length) return null;
                const bc = BLOCO_COLORS[bloco as Bloco];
                return (
                  <div key={bloco} className="mb-4 last:mb-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] font-extrabold uppercase tracking-widest" style={{ color: bc }}>
                        {bloco}
                      </span>
                      <span className="text-[10px] text-slate-400 font-medium">{BLOCO_LABEL[bloco] ?? bloco}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {group.map(([k, v]) => {
                        const selected = selectorDraft.includes(k);
                        const styles = BLOCO_BG[v.bloco] || BLOCO_BG.HST;
                        return (
                          <button
                            key={k}
                            onClick={() =>
                              setSelectorDraft((prev) =>
                                prev.includes(k) ? prev.filter((c) => c !== k) : [...prev, k]
                              )
                            }
                            className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full border text-[11px] font-medium transition-all duration-150 ${
                              selected
                                ? `${styles} ring-1 ring-teal-200`
                                : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700'
                            }`}
                          >
                            {selected && <Check size={12} strokeWidth={2.5} className="shrink-0" />}
                            {v.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between p-4 border-t border-slate-100 bg-slate-50/50">
              <span className="text-xs text-slate-500">{selectorDraft.length} indicadores</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={closeSelector}
                  className="px-3.5 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={confirmSelector}
                  className="px-4 py-2 rounded-lg bg-teal-600 text-xs font-semibold text-white hover:bg-teal-700 transition-colors shadow-sm"
                >
                  Confirmar {selectorDraft.length} gráficos
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {selectedMini.map((code) => (
          <FundMiniChart key={code} cnpj={cnpj ?? ''} code={code} />
        ))}
      </div>
    </main>
  );
}

function FundMiniChart({ cnpj, code }: { cnpj: string; code: string }) {
  const { data = [], isLoading } = useFiiIndicadorSerie(cnpj, code);
  if (isLoading) return <div className="skeleton h-[140px] rounded-xl" />;
  return <MiniChart code={code} data={data} />;
}
