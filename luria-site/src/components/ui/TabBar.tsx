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
    <div className="inline-flex bg-slate-100 rounded-xl p-1 mb-8">
      {TABS.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={`px-6 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
            active === tab.value
              ? 'bg-white text-emerald-700 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
