import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Search, Building2 } from 'lucide-react';
import { buscarAtivos } from '../../api/ativos';

export default function SearchBar() {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { data: results = [] } = useQuery({
    queryKey: ['busca', query],
    queryFn: () => buscarAtivos(query),
    enabled: query.length >= 2,
    staleTime: 30_000,
  });

  const handleChange = useCallback((value: string) => {
    setQuery(value);
    setOpen(value.length >= 2);
  }, []);

  const handleSelect = useCallback(
    (ticker: string, tipo?: string) => {
      setOpen(false);
      setQuery('');
      if (tipo === 'fii') {
        navigate(`/fundo/${ticker}`);
      } else {
        navigate(`/ativo/${ticker}`);
      }
    },
    [navigate]
  );

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  return (
    <div className="relative mb-7" ref={ref}>
      <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 pointer-events-none" />
      <input
        type="text"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        placeholder="Buscar ativo ou fundo...  ex: WEGE3, VALE3, fundo logístico"
        className="w-full bg-white border border-slate-200 text-slate-800 rounded-xl py-3 pl-11 pr-4 text-sm outline-none transition-all placeholder:text-slate-300 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 shadow-sm"
      />
      {open && results.length > 0 && (
        <div className="absolute top-[calc(100%+6px)] left-0 right-0 bg-white border border-slate-200 rounded-xl overflow-hidden z-50 shadow-dropdown animate-slide-down">
          {results.map((r) => (
            <div
              key={r.tipo === 'fii' ? `fii-${r.ticker}` : r.ticker}
              onClick={() => handleSelect(r.ticker, r.tipo)}
              className="flex items-center gap-2.5 px-4 py-3 cursor-pointer text-sm hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0"
            >
              {r.tipo === 'fii' ? (
                <Building2 size={13} className="text-teal-500 shrink-0" />
              ) : (
                <span className="font-bold text-slate-900">{r.ticker}</span>
              )}
              {r.tipo !== 'fii' && <span className="text-slate-300">·</span>}
              <span className={`text-xs truncate ${r.tipo === 'fii' ? 'font-medium text-slate-700' : 'text-slate-500'}`}>
                {r.empresa}
              </span>
              {r.tipo === 'fii' && r.segmento && (
                <span className="ml-auto text-[10px] font-medium text-teal-600 bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded-md shrink-0">
                  {r.segmento}
                </span>
              )}
              {r.tipo !== 'fii' && (
                <span className="ml-auto text-[10px] font-medium text-blue-600 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded-md shrink-0">
                  Ação
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
