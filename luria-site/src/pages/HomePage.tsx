import { useAppStore } from '../store/useAppStore';
import { useRanking } from '../hooks/useRanking';
import { useFiis } from '../hooks/useFiis';
import TabBar from '../components/ui/TabBar';
import SearchBar from '../components/home/SearchBar';
import StockCard from '../components/home/StockCard';
import FundCard from '../components/home/FundCard';
import { SkeletonCard } from '../components/ui/Skeleton';

export default function HomePage() {
  const { activeTab, setActiveTab } = useAppStore();
  const { data: ativos, isLoading: acoesLoading, isError: acoesError, refetch: acoesRefetch } = useRanking('acoes');
  const { data: fiis, isLoading: fiisLoading, isError: fiisError, refetch: fiisRefetch } = useFiis(60);

  const isFiis    = activeTab === 'fiis';
  const isLoading = isFiis ? fiisLoading : acoesLoading;
  const isError   = isFiis ? fiisError   : acoesError;
  const refetch   = isFiis ? fiisRefetch : acoesRefetch;

  const subtitle = isFiis
    ? 'Rankeados por Quality Score — solidez, portfólio, distribuição e eficiência'
    : 'Rankeados por Quality Score — rentabilidade, solidez, caixa e consistência';

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 py-8">
      {/* Cabeçalho */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-5 mb-7">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {isFiis ? 'Melhores FIIs' : 'Melhores Ações'}
          </h1>
          <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
          <span className="inline-flex items-center gap-1.5 mt-2.5 text-[11px] font-medium text-emerald-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Recency-weighted · presente vale mais que o passado
          </span>
        </div>
        <TabBar active={activeTab} onChange={setActiveTab} />
      </div>

      <SearchBar />

      {!isLoading && isError && (
        <div
          className="mb-8 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-950 shadow-sm"
          role="alert"
        >
          <p className="font-semibold">Não foi possível carregar o ranking</p>
          <p className="mt-2 text-amber-900/90 leading-relaxed">
            O site chama <code className="rounded bg-amber-100/90 px-1.5 py-0.5 text-xs">/api/…</code> e o
            Vite encaminha para <code className="rounded bg-amber-100/90 px-1.5 py-0.5 text-xs">http://localhost:8000</code>.
            Sem o backend nessa porta, a lista fica vazia.
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-4 text-xs font-bold uppercase tracking-wide text-amber-900 underline decoration-amber-600 underline-offset-2 hover:text-amber-950"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {!isLoading && !isError && !isFiis && (ativos ?? []).length === 0 && (
        <div className="text-center py-16">
          <p className="text-slate-500 text-sm">Nenhuma ação encontrada com dados suficientes.</p>
        </div>
      )}

      {!isLoading && !isError && isFiis && (fiis ?? []).length === 0 && (
        <div className="text-center py-16">
          <p className="text-slate-500 text-sm">Nenhum FII encontrado com dados suficientes.</p>
        </div>
      )}

      {isFiis ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {isLoading
            ? Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)
            : !isError && (fiis ?? []).map((f, i) => (
                <FundCard key={f.cnpj} fii={f} delay={i * 40} />
              ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {isLoading
            ? Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)
            : !isError && (ativos ?? []).map((a, i) => (
                <StockCard key={a.ticker} ativo={a} delay={i * 40} />
              ))}
        </div>
      )}
    </main>
  );
}
