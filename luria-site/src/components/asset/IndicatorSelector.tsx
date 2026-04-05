import { useState, useCallback, useMemo } from 'react';
import { Check, Search, SlidersHorizontal, X } from 'lucide-react';
import { INDICATORS, BLOCOS, BLOCO_COLORS, BLOCO_LABEL } from '../../config/indicators';
import type { Bloco } from '../../types';

interface IndicatorSelectorProps {
  applied: string[];
  onApply: (codes: string[]) => void;
}

const CHIP_SELECTED: Record<string, { bg: string; border: string; text: string; ring: string }> = {
  BP:  { bg: 'bg-blue-50',    border: 'border-blue-300',    text: 'text-blue-700',    ring: 'ring-blue-200' },
  DRE: { bg: 'bg-violet-50',  border: 'border-violet-300',  text: 'text-violet-700',  ring: 'ring-violet-200' },
  DFC: { bg: 'bg-amber-50',   border: 'border-amber-300',   text: 'text-amber-700',   ring: 'ring-amber-200' },
  CMB: { bg: 'bg-emerald-50', border: 'border-emerald-300', text: 'text-emerald-700', ring: 'ring-emerald-200' },
  MKT: { bg: 'bg-rose-50',    border: 'border-rose-300',    text: 'text-rose-700',    ring: 'ring-rose-200' },
  HST: { bg: 'bg-slate-100',  border: 'border-slate-300',   text: 'text-slate-600',   ring: 'ring-slate-200' },
  VAL: { bg: 'bg-cyan-50',    border: 'border-cyan-300',    text: 'text-cyan-700',    ring: 'ring-cyan-200' },
};

export default function IndicatorSelector({ applied, onApply }: IndicatorSelectorProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [search, setSearch] = useState('');

  const totalAvailable = Object.keys(INDICATORS).length;

  const handleOpen = useCallback(() => {
    setDraft([...applied]);
    setSearch('');
    setOpen(true);
  }, [applied]);

  const handleClose = useCallback(() => {
    setOpen(false);
    setDraft([]);
    setSearch('');
  }, []);

  const handleConfirm = useCallback(() => {
    onApply(draft);
    setOpen(false);
    setSearch('');
  }, [draft, onApply]);

  const toggleDraft = useCallback((code: string) => {
    setDraft((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }, []);

  const filtered = useMemo(
    () =>
      Object.entries(INDICATORS).filter(
        ([k, v]) =>
          k.toLowerCase().includes(search.toLowerCase()) ||
          v.name.toLowerCase().includes(search.toLowerCase())
      ),
    [search]
  );

  const hasChanges = useMemo(() => {
    if (draft.length !== applied.length) return true;
    const sortedDraft = [...draft].sort();
    const sortedApplied = [...applied].sort();
    return sortedDraft.some((v, i) => v !== sortedApplied[i]);
  }, [draft, applied]);

  return (
    <div className="mb-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Indicadores</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {applied.length} de {totalAvailable} gráficos aplicados
          </p>
        </div>
        <button
          onClick={open ? handleClose : handleOpen}
          className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border text-xs font-semibold transition-all ${
            open
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
              : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 shadow-sm'
          }`}
        >
          {open ? <X size={14} /> : <SlidersHorizontal size={14} />}
          {open ? 'Fechar' : 'Editar seleção'}
        </button>
      </div>

      {/* Panel */}
      {open && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-card overflow-hidden mb-4 animate-slide-down">
          {/* Search + summary bar */}
          <div className="p-4 border-b border-slate-100">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filtrar indicadores..."
                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg py-2 pl-9 pr-3 text-sm outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-100 transition-all placeholder:text-slate-400"
              />
            </div>
            <div className="flex items-center gap-3 mt-3 text-[11px]">
              <span className="inline-flex items-center gap-1 text-slate-500">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                {draft.length} selecionados
              </span>
              {hasChanges && (
                <span className="inline-flex items-center gap-1 text-amber-600 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  alterações pendentes
                </span>
              )}
            </div>
          </div>

          {/* Indicator groups */}
          <div className="p-4 max-h-[400px] overflow-y-auto">
            {BLOCOS.map((bloco) => {
              const group = filtered.filter(([, v]) => v.bloco === bloco);
              if (!group.length) return null;
              const bc = BLOCO_COLORS[bloco];
              const selectedInGroup = group.filter(([k]) => draft.includes(k)).length;

              return (
                <div key={bloco} className="mb-5 last:mb-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="text-[10px] font-extrabold uppercase tracking-widest"
                      style={{ color: bc }}
                    >
                      {bloco}
                    </span>
                    <span className="text-[10px] text-slate-400 font-medium">
                      {BLOCO_LABEL[bloco] ?? bloco}
                    </span>
                    <span className="text-[10px] text-slate-400 ml-auto">
                      {selectedInGroup}/{group.length}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {group.map(([k, v]) => (
                      <IndicatorChip
                        key={k}
                        code={k}
                        name={v.name}
                        bloco={v.bloco}
                        selected={draft.includes(k)}
                        onToggle={toggleDraft}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer with actions */}
          <div className="flex items-center justify-between p-4 border-t border-slate-100 bg-slate-50/50">
            <span className="text-xs text-slate-500">
              {draft.length} de {totalAvailable} indicadores
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={handleClose}
                className="px-3.5 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirm}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!hasChanges && draft.length === applied.length}
              >
                Confirmar {draft.length} gráficos
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface IndicatorChipProps {
  code: string;
  name: string;
  bloco: Bloco;
  selected: boolean;
  onToggle: (code: string) => void;
}

function IndicatorChip({ code, name, bloco, selected, onToggle }: IndicatorChipProps) {
  const styles = CHIP_SELECTED[bloco] || CHIP_SELECTED.HST;

  return (
    <button
      onClick={() => onToggle(code)}
      className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full border text-[11px] font-medium transition-all duration-150 ${
        selected
          ? `${styles.bg} ${styles.border} ${styles.text} ring-1 ${styles.ring}`
          : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700'
      }`}
    >
      {selected && <Check size={12} strokeWidth={2.5} className="shrink-0" />}
      {name}
    </button>
  );
}
