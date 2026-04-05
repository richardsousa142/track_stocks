interface ScoreRingProps {
  score: number;
  size?: number;
}

export default function ScoreRing({ score, size = 42 }: ScoreRingProps) {
  const tier = score >= 85 ? 'high' : score >= 70 ? 'mid' : 'low';

  const styles: Record<string, string> = {
    high: 'bg-emerald-50 text-emerald-700 border-emerald-300 ring-emerald-100',
    mid: 'bg-amber-50 text-amber-700 border-amber-300 ring-amber-100',
    low: 'bg-red-50 text-red-600 border-red-300 ring-red-100',
  };

  return (
    <div
      className={`flex items-center justify-center rounded-full border text-sm font-extrabold shrink-0 ring-2 ${styles[tier]}`}
      style={{ width: size, height: size }}
    >
      {score}
    </div>
  );
}
