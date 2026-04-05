import { useQuery } from '@tanstack/react-query';
import { fetchAnalise } from '../api/ativos';

export function useAIAnalysis(ticker: string) {
  return useQuery({
    queryKey: ['analise', ticker],
    queryFn: () => fetchAnalise(ticker),
    enabled: !!ticker,
    staleTime: 24 * 60 * 60 * 1000,
  });
}
