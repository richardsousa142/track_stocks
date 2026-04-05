interface SkeletonProps {
  className?: string;
}

export function SkeletonCard({ className = '' }: SkeletonProps) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 p-5 ${className}`}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="skeleton h-4 w-16 mb-2" />
          <div className="skeleton h-3 w-28" />
        </div>
        <div className="skeleton h-10 w-10 rounded-full" />
      </div>
      <div className="flex justify-between items-end">
        <div>
          <div className="skeleton h-4 w-20 mb-2" />
          <div className="skeleton h-5 w-14 rounded-full" />
        </div>
        <div className="skeleton h-8 w-20" />
      </div>
    </div>
  );
}

export function SkeletonChart({ className = '' }: SkeletonProps) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 p-5 ${className}`}>
      <div className="skeleton h-5 w-40 mb-4" />
      <div className="skeleton h-[210px] w-full rounded-xl" />
    </div>
  );
}
