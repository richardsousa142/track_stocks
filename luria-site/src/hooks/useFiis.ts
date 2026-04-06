import { useQuery } from '@tanstack/react-query';
import { fetchFiis, fetchFii, fetchFiiIndicador, fetchFiiTodosIndicadores } from '../api/fiis';
import { formatLabel } from '../config/indicators';
import type { ChartDataPoint } from '../types';

export function useFiis(limit = 50) {
  return useQuery({
    queryKey: ['fiis', limit],
    queryFn: () => fetchFiis(limit),
    staleTime: 5 * 60 * 1000,
  });
}

export function useFii(cnpj: string) {
  return useQuery({
    queryKey: ['fii', cnpj],
    queryFn: () => fetchFii(cnpj),
    enabled: !!cnpj,
    staleTime: 10 * 60 * 1000,
  });
}

export function useFiiIndicadorSerie(cnpj: string, indicador: string) {
  return useQuery({
    queryKey: ['fii-indicador', cnpj, indicador],
    queryFn: async (): Promise<ChartDataPoint[]> => {
      const raw = await fetchFiiIndicador(cnpj, indicador, 'M');
      return raw.map((p) => ({
        label: formatLabel(p.freq, p.ano, p.trimestre, p.mes),
        value: p.valor,
      }));
    },
    enabled: !!cnpj && !!indicador,
    staleTime: 5 * 60 * 1000,
  });
}

export function useFiiTodosIndicadores(cnpj: string) {
  return useQuery({
    queryKey: ['fii-todos-indicadores', cnpj],
    queryFn: () => fetchFiiTodosIndicadores(cnpj),
    enabled: !!cnpj,
    staleTime: 5 * 60 * 1000,
  });
}
