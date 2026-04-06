import { Link } from 'react-router-dom';
import { User, Menu } from 'lucide-react';

export default function Header() {
  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200/60">
      <div className="w-full px-4 sm:px-6 lg:px-8 xl:px-12 h-14 flex items-center justify-between">
        <Link
          to="/"
          className="text-xl font-extrabold tracking-tight text-emerald-600 hover:text-emerald-700 transition-colors"
        >
          Luria
        </Link>
        <div className="flex items-center gap-2">
          <button className="w-9 h-9 rounded-full bg-slate-50 border border-slate-200 flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
            <User size={16} />
          </button>
          <button className="w-9 h-9 rounded-full bg-slate-50 border border-slate-200 flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
            <Menu size={16} />
          </button>
        </div>
      </div>
    </header>
  );
}
