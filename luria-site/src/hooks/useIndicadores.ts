import { useQuery } from '@tanstack/react-query';
import { fetchIndicador, fetchTodosIndicadores, fetchValuation } from '../api/ativos';
import { formatLabel } from '../config/indicators';
import type { ChartDataPoint, Freq } from '../types';

export function useIndicadorSerie(ticker: string, indicador: string, freq: Freq = 'T') {
  return useQuery({
    queryKey: ['indicador', ticker, indicador, freq],
    queryFn: async (): Promise<ChartDataPoint[]> => {
      const raw = await fetchIndicador(ticker, indicador, freq);
      return raw.map((p) => ({
        label: formatLabel(p.freq, p.ano, p.trimestre, p.mes),
        value: p.valor,
      }));
    },
    enabled: !!ticker && !!indicador,
    staleTime: 5 * 60 * 1000,
  });
}

export function useTodosIndicadores(ticker: string, freq: Freq = 'T') {
  return useQuery({
    queryKey: ['todos-indicadores', ticker, freq],
    queryFn: () => fetchTodosIndicadores(ticker, freq),
    enabled: !!ticker,
    staleTime: 5 * 60 * 1000,
  });
}

export function useValuation(ticker: string) {
  return useQuery({
    queryKey: ['valuation', ticker],
    queryFn: () => fetchValuation(ticker),
    enabled: !!ticker,
    staleTime: 10 * 60 * 1000,
  });
}
