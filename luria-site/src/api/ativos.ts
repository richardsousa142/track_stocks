import client from './client';
import type { AtivoResumo, BuscaResult, IndicadorPonto, IndicadorAtual, AnaliseTexto, Freq, ValuationData } from '../types';

export async function fetchAtivos(tipo: 'acoes' | 'fiis', limit = 20, offset = 0): Promise<AtivoResumo[]> {
  const { data } = await client.get('/ativos', { params: { tipo, limit, offset } });
  return data;
}

export async function buscarAtivos(q: string): Promise<BuscaResult[]> {
  const { data } = await client.get('/ativos/busca', { params: { q } });
  return data;
}

export async function fetchIndicador(
  ticker: string,
  indicador: string,
  freq: Freq = 'T'
): Promise<IndicadorPonto[]> {
  const { data } = await client.get(`/ativos/${ticker}/indicadores`, {
    params: { indicador, freq },
  });
  return data;
}

export async function fetchTodosIndicadores(
  ticker: string,
  freq: Freq = 'T'
): Promise<IndicadorAtual[]> {
  const { data } = await client.get(`/ativos/${ticker}/todos-indicadores`, {
    params: { freq },
  });
  return data;
}

export async function fetchAnalise(ticker: string): Promise<AnaliseTexto> {
  const { data } = await client.get(`/ativos/${ticker}/analise`);
  return data;
}

export async function fetchValuation(ticker: string): Promise<ValuationData | null> {
  try {
    const { data } = await client.get(`/valuation/${ticker}`);
    return data;
  } catch {
    return null;
  }
}
