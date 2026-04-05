interface BadgeProps {
  children: React.ReactNode;
  variant?: 'positive' | 'negative' | 'info' | 'neutral';
  className?: string;
}

const STYLES: Record<string, string> = {
  positive: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  negative: 'bg-red-50 text-red-600 border-red-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
  neutral: 'bg-slate-50 text-slate-600 border-slate-200',
};

export default function Badge({ children, variant = 'info', className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded-full border ${STYLES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
