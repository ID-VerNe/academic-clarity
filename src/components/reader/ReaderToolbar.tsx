import React from 'react';
import { ChevronRight, Bookmark, Sparkles, Layout, FileText, Cpu } from 'lucide-react';

interface ReaderToolbarProps {
  onBack: () => void;
  viewMode: 'split' | 'pdf' | 'markdown';
  setViewMode: (mode: 'split' | 'pdf' | 'markdown') => void;
  title: string;
}

export const ReaderToolbar = ({
  onBack,
  viewMode,
  setViewMode,
  title
}: ReaderToolbarProps) => {
  return (
    <div className="h-14 border-b border-slate-200/60 bg-white/80 backdrop-blur-md flex items-center px-4 justify-between sticky top-0 z-50 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
      {/* Left: Navigation & Context */}
      <div className="flex items-center gap-3 min-w-0">
        <button 
          onClick={onBack} 
          className="group flex items-center gap-1.5 px-3 py-1.5 text-slate-500 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 rounded-xl transition-all duration-200 border border-slate-200/50 shadow-sm"
        >
          <ChevronRight className="w-4 h-4 rotate-180 group-hover:-translate-x-0.5 transition-transform" />
          <span className="text-xs font-bold tracking-tight">Library</span>
        </button>
        <div className="h-6 w-px bg-slate-200/60 mx-1" />
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5">
             <FileText className="w-3 h-3 text-slate-400" />
             <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] truncate">Active Document</span>
          </div>
          <p className="text-xs font-bold text-slate-800 truncate leading-tight pr-4">{title}</p>
        </div>
      </div>
      
      {/* Center: View Switcher (Ergonomic Toggle) */}
      <div className="absolute left-1/2 transform -translate-x-1/2 flex bg-slate-100/80 p-1 rounded-2xl gap-0.5 border border-slate-200/40">
        {(['pdf', 'split', 'markdown'] as const).map((mode) => (
          <button 
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`px-5 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all duration-300 ${
              viewMode === mode 
              ? 'bg-white text-indigo-600 shadow-[0_2px_8px_rgba(0,0,0,0.08)] scale-[1.02]' 
              : 'text-slate-400 hover:text-slate-600 hover:bg-white/40'
            }`}
          >
            {mode}
          </button>
        ))}
      </div>
      
      {/* Right: Advanced Actions */}
      <div className="flex items-center gap-2">
        <button className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all border border-transparent hover:border-indigo-100">
           <Bookmark className="w-4 h-4" />
        </button>
        
        <div className="w-px h-6 bg-slate-200/60 mx-1" />
        
        <button className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-all shadow-[0_4px_12px_rgba(79,70,229,0.25)] active:scale-95 group border border-indigo-500/50">
          <Sparkles className="w-3.5 h-3.5 group-hover:rotate-12 transition-transform fill-white/20" />
          <span className="text-xs font-black tracking-tight">AI Analyze</span>
        </button>
      </div>
    </div>
  );
};
