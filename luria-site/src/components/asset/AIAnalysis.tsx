import { Sparkles } from 'lucide-react';
import { useAIAnalysis } from '../../hooks/useAIAnalysis';

interface AIAnalysisProps {
  ticker: string;
}

export default function AIAnalysis({ ticker }: AIAnalysisProps) {
  const { data, isLoading, error } = useAIAnalysis(ticker);

  if (error) return null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-emerald-500 p-5 shadow-sm mb-6">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-6 h-6 rounded-lg bg-emerald-50 flex items-center justify-center">
          <Sparkles size={14} className="text-emerald-600" />
        </div>
        <span className="text-sm font-semibold text-emerald-700">Análise Luria</span>
      </div>
      {isLoading ? (
        <div className="space-y-2.5">
          <div className="skeleton h-3 w-full" />
          <div className="skeleton h-3 w-5/6" />
          <div className="skeleton h-3 w-4/6" />
        </div>
      ) : (
        <p
          className="text-sm text-slate-600 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: data?.texto ?? '' }}
        />
      )}
    </div>
  );
}
