import type { AssetType } from '../../types';

interface TabBarProps {
  active: AssetType;
  onChange: (tab: AssetType) => void;
}

const TABS: { value: AssetType; label: string }[] = [
  { value: 'acoes', label: 'Ações' },
  { value: 'fiis', label: 'FIIs' },
];

export default function TabBar({ active, onChange }: TabBarProps) {
  return (
    <div className="inline-flex items-center gap-1 border border-slate-200 rounded-xl p-1 shadow-sm" style={{ backgroundColor: '#f0f4f8' }}>
      {TABS.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={`px-7 py-1 rounded-lg text-sm font-semibold transition-all duration-200 ${
            active === tab.value
              ? 'bg-white text-slate-800 shadow-sm'
              : 'text-slate-400 hover:text-slate-600'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
