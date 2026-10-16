import React from 'react';
import {
  Pencil, Play, Loader2, MoreHorizontal, FileSpreadsheet, FileText, Trash2,
} from 'lucide-react';
import { ExtractionDimension } from '../../types';

interface DimensionRowProps {
  dim: ExtractionDimension;
  /** 该行正在执行操作（批量运行 / 删除 / 导出） */
  busy: boolean;
  menuOpen: boolean;
  /** 行内菜单容器 ref（父组件用于点击空白收起） */
  menuRef: React.RefObject<HTMLDivElement | null>;
  onEdit: () => void;
  onRunBatch: () => void;
  onToggleMenu: () => void;
  onExport: (format: 'csv' | 'md') => void;
  onRequestDelete: () => void;
}

/** 维度行：名称 / 禁用徽标 / 编辑 / 批量运行 / 「更多操作」菜单（导出、删除） */
export const DimensionRow = ({
  dim,
  busy,
  menuOpen,
  menuRef,
  onEdit,
  onRunBatch,
  onToggleMenu,
  onExport,
  onRequestDelete,
}: DimensionRowProps) => (
  <div className="bg-white border border-slate-200 rounded-2xl p-4 flex items-start justify-between gap-3">
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <span className="text-sm font-bold text-slate-800 truncate">{dim.label}</span>
        {!dim.enabled && (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-500 border border-slate-200">
            已禁用
          </span>
        )}
      </div>
      <p className="text-xs text-slate-400 truncate mt-1 max-w-[380px]" title={dim.prompt}>
        {dim.prompt}
      </p>
    </div>
    <div className="flex items-center gap-1 shrink-0">
      <button
        aria-label={`编辑 ${dim.label}`}
        onClick={onEdit}
        className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
        title="编辑"
      >
        <Pencil className="w-3.5 h-3.5" />
      </button>
      <button
        aria-label={`批量运行 ${dim.label}`}
        onClick={onRunBatch}
        disabled={busy || !dim.enabled}
        className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors disabled:opacity-40 disabled:hover:bg-emerald-50"
        title={dim.enabled ? '对全部已完成文献批量提取' : '维度已禁用'}
      >
        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
        批量运行
      </button>
      <div className="relative" ref={menuOpen ? menuRef : undefined}>
        <button
          aria-label={`更多操作 ${dim.label}`}
          aria-expanded={menuOpen}
          onClick={onToggleMenu}
          className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          title="更多操作"
        >
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
        {menuOpen && (
          <div className="absolute right-0 top-full mt-1 z-30 w-44 bg-white border border-slate-200 rounded-xl shadow-xl py-1">
            <button
              onClick={() => onExport('csv')}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              导出 CSV
            </button>
            <button
              onClick={() => onExport('md')}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              <FileText className="w-3.5 h-3.5" />
              导出 Markdown
            </button>
            <div className="my-1 h-px bg-slate-100" />
            <button
              onClick={onRequestDelete}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs font-bold text-rose-600 hover:bg-rose-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              删除维度
            </button>
          </div>
        )}
      </div>
    </div>
  </div>
);
