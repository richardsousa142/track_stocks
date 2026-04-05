import { useMemo } from 'react';

interface SparklineProps {
  data: number[];
  positive: boolean;
  width?: number;
  height?: number;
}

export default function Sparkline({ data, positive, width = 80, height = 32 }: SparklineProps) {
  const points = useMemo(() => {
    if (!data.length) return '';
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    return data
      .map(
        (v, i) =>
          `${((i / (data.length - 1)) * width).toFixed(1)},${(height - ((v - min) / range) * height).toFixed(1)}`
      )
      .join(' ');
  }, [data, width, height]);

  const color = positive ? '#059669' : '#dc2626';

  return (
    <svg width={width} height={height} className="block" aria-label="Sparkline de preço">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
