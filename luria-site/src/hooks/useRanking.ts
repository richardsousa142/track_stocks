import { useQuery } from '@tanstack/react-query';
import { fetchAtivos } from '../api/ativos';
import type { AssetType } from '../types';

export function useRanking(tipo: AssetType, limit = 20) {
  return useQuery({
    queryKey: ['ranking', tipo, limit],
    queryFn: () => fetchAtivos(tipo, limit, 0),
    staleTime: 5 * 60 * 1000,
  });
}
