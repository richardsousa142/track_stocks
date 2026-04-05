import { useAppStore } from '../store/useAppStore';
import { useRanking } from '../hooks/useRanking';
import TabBar from '../components/ui/TabBar';
import SearchBar from '../components/home/SearchBar';
import StockCard from '../components/home/StockCard';
import { SkeletonCard } from '../components/ui/Skeleton';

export default function HomePage() {
  const { activeTab, setActiveTab } = useAppStore();
  const { data: ativos, isLoading, isError, refetch } = useRanking(activeTab);

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {activeTab === 'acoes' ? 'Melhores Ações' : 'Melhores FIIs'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Rankeados por Quality Score — rentabilidade, solidez, caixa e consistência
          </p>
          <span className="inline-flex items-center gap-1 mt-2 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
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
            Sem o backend nessa porta, a lista fica vazia. Suba a API do projeto e recarregue, ou abra o console (F12) para ver o erro de rede.
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

      {!isLoading && !isError && ativos?.length === 0 && (
        <div className="text-center py-16">
          <p className="text-slate-500 text-sm">Nenhum ativo encontrado com dados suficientes.</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading
          ? Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)
          : !isError && (ativos ?? []).map((a, i) => <StockCard key={a.ticker} ativo={a} delay={i * 40} />)}
      </div>
    </main>
  );
}
