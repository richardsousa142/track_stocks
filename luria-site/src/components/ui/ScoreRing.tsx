interface ScoreRingProps {
  score: number;
  size?: number;
}

export default function ScoreRing({ score, size = 64 }: ScoreRingProps) {
  const strokeWidth = size * 0.055;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(100, Math.max(0, score)) / 100;
  const dashOffset = circumference * (1 - progress);

  const color =
    score >= 75 ? '#059669' :
    score >= 55 ? '#d97706' :
    '#dc2626';

  const trackColor =
    score >= 75 ? '#d1fae5' :
    score >= 55 ? '#fde68a' :
    '#fee2e2';

  const textColor =
    score >= 75 ? '#065f46' :
    score >= 55 ? '#92400e' :
    '#991b1b';

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth={strokeWidth}
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      {/* Center label */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center"
        style={{ color: textColor }}
      >
        <span className="font-bold leading-none" style={{ fontSize: size * 0.32 }}>
          {score}
        </span>
        <span
          className="font-bold uppercase tracking-widest leading-none mt-0.5"
          style={{ fontSize: size * 0.115, color: '#94a3b8' }}
        >
          quality
        </span>
      </div>
    </div>
  );
}
