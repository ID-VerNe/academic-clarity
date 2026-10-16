import React from 'react';
import { ChevronLeft, Sparkles, FileText } from 'lucide-react';
import { ViewMode } from '../../types';

interface ReaderToolbarProps {
  onBack: () => void;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  title: string;
  /** 主 CTA：聚焦右侧对话并给出默认分析问题（UX-04） */
  onAnalyze: () => void;
}

const VIEW_MODES: { key: ViewMode; label: string; title: string }[] = [
  { key: 'pdf', label: 'PDF', title: '只显示 PDF 原页' },
  { key: 'split', label: '分栏', title: 'PDF 与文本对照' },
  { key: 'markdown', label: '文本', title: '只显示识别文本' },
];

export const ReaderToolbar = ({ onBack, viewMode, setViewMode, title, onAnalyze }: ReaderToolbarProps) => {
  return (
    <div className="h-14 border-b border-slate-200/60 bg-white/80 backdrop-blur-md flex items-center px-4 justify-between sticky top-0 z-50 shadow-[0_1px_2px_rgba(0,0,0,0.02)] select-none">
      {/* Left: Navigation & Context */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onBack}
          aria-label="返回文献库"
          className="group flex items-center gap-1.5 px-3 py-1.5 text-slate-500 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 rounded-xl transition-all duration-200 border border-slate-200/50 shadow-sm"
        >
          <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          <span className="text-xs font-bold tracking-tight">文献库</span>
        </button>
        <div className="h-6 w-px bg-slate-200/60 mx-1" />
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5">
            <FileText className="w-3 h-3 text-slate-400" />
            <span className="text-[11px] font-bold text-slate-400 truncate">当前文档</span>
          </div>
          <p className="text-xs font-bold text-slate-800 truncate leading-tight pr-4" title={title}>
            {title}
          </p>
        </div>
      </div>

      {/* Center: View Switcher */}
      <div className="absolute left-1/2 transform -translate-x-1/2 flex bg-slate-100/80 p-1 rounded-2xl gap-0.5 border border-slate-200/40">
        {VIEW_MODES.map((mode) => (
          <button
            key={mode.key}
            onClick={() => setViewMode(mode.key)}
            aria-label={mode.title}
            title={mode.title}
            aria-pressed={viewMode === mode.key}
            className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all duration-300 ${
              viewMode === mode.key
                ? 'bg-white text-indigo-600 shadow-[0_2px_8px_rgba(0,0,0,0.08)]'
                : 'text-slate-400 hover:text-slate-600 hover:bg-white/40'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Right: Primary Action */}
      <div className="flex items-center gap-2">
        <button
          onClick={onAnalyze}
          title="聚焦右侧对话，让 AI 分析这篇文档"
          className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-all shadow-[0_4px_12px_rgba(79,70,229,0.25)] active:scale-95 group border border-indigo-500/50"
        >
          <Sparkles className="w-3.5 h-3.5 group-hover:rotate-12 transition-transform fill-white/20" />
          <span className="text-xs font-bold tracking-tight">AI 分析</span>
        </button>
      </div>
    </div>
  );
};
