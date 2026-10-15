import React from 'react';
import { School, FolderOpen, Search, Settings } from 'lucide-react';
import { View } from '../types';
import { isImeEnter } from '../utils/keyboard';

interface HeaderProps {
  workspacePath: string;
  setView: (view: View) => void;
  onOpenSettings: () => void;
  /** 全局检索词（与 Dashboard 共享，UX-02） */
  searchValue: string;
  onSearchChange: (value: string) => void;
  /** 回车提交：跳回文献库并应用当前检索词 */
  onSearchSubmit: () => void;
}

export const Header = ({
  workspacePath,
  setView,
  onOpenSettings,
  searchValue,
  onSearchChange,
  onSearchSubmit,
}: HeaderProps) => (
  <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 sticky top-0 z-50 shadow-sm">
    <div className="flex items-center gap-8 min-w-0">
      <button
        type="button"
        onClick={() => setView('dashboard')}
        aria-label="返回文献库"
        className="flex items-center gap-2 text-indigo-600 hover:text-indigo-700 transition-colors shrink-0"
      >
        <School className="w-8 h-8" />
        <h1 className="font-bold text-xl tracking-tight text-slate-900">Academic Clarity</h1>
      </button>

      <div className="h-6 w-px bg-slate-200 shrink-0" />

      <div
        className="flex items-center gap-2 text-xs font-medium text-slate-500 max-w-md truncate"
        title={workspacePath || '未选择工作区'}
      >
        <FolderOpen className="w-3.5 h-3.5 shrink-0" />
        <span className="truncate">{workspacePath || '正在加载工作区…'}</span>
      </div>
    </div>

    <div className="flex items-center gap-3">
      <div className="relative w-64">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
        <input
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          onKeyDown={(e) => {
            if (isImeEnter(e)) onSearchSubmit();
          }}
          aria-label="搜索文献库"
          title="搜索文献库（回车定位到文献库）"
          placeholder="搜索文献…"
          type="text"
          className="w-full h-9 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 text-sm outline-none transition-all"
        />
      </div>
      <button
        type="button"
        onClick={onOpenSettings}
        aria-label="打开设置"
        title="设置"
        className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-600"
      >
        <Settings className="w-5 h-5" />
      </button>
    </div>
  </header>
);
