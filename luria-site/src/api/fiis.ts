import client from './client';
import type { FiiResumo, FiiMeta, IndicadorPonto, IndicadorAtual } from '../types';

export async function fetchFiis(limit = 20, offset = 0): Promise<FiiResumo[]> {
  const { data } = await client.get('/fiis', { params: { limit, offset } });
  return data;
}

export async function fetchFii(cnpj: string): Promise<FiiMeta | null> {
  try {
    const { data } = await client.get(`/fiis/${cnpj}`);
    return data;
  } catch {
    return null;
  }
}

export async function fetchFiiIndicador(
  cnpj: string,
  indicador: string,
  freq = 'M'
): Promise<IndicadorPonto[]> {
  const { data } = await client.get(`/fiis/${cnpj}/indicadores`, {
    params: { indicador, freq },
  });
  return data;
}

export async function fetchFiiTodosIndicadores(cnpj: string): Promise<IndicadorAtual[]> {
  const { data } = await client.get(`/fiis/${cnpj}/todos-indicadores`);
  return data;
}
