import React from 'react';
import { DocStatus } from '../../utils/docStatus';
import { DashboardMode, STATUS_META } from './constants';

interface DashboardTabsProps {
  mode: DashboardMode;
  onModeChange: (mode: DashboardMode) => void;
  searchQuery: string;
  filteredCount: number;
  docsCount: number;
}

/** 模式切换 tab（文献 / 知识库检索）+ 状态图例 + 检索范围说明 */
export const DashboardTabs = ({
  mode,
  onModeChange,
  searchQuery,
  filteredCount,
  docsCount,
}: DashboardTabsProps) => (
  <>
    <div className="flex items-center justify-between mb-6 border-b border-slate-200 pb-px">
      <div className="flex gap-8">
        <button
          onClick={() => onModeChange('papers')}
          className={`font-bold text-sm border-b-2 pb-4 -mb-px transition-colors ${
            mode === 'papers' ? 'text-indigo-600 border-indigo-600' : 'text-slate-400 border-transparent hover:text-slate-600'
          }`}
        >
          文献
          {mode === 'papers' && filteredCount !== docsCount && `（${filteredCount}/${docsCount}）`}
        </button>
        <button
          onClick={() => onModeChange('claims')}
          className={`font-bold text-sm border-b-2 pb-4 -mb-px transition-colors ${
            mode === 'claims' ? 'text-indigo-600 border-indigo-600' : 'text-slate-400 border-transparent hover:text-slate-600'
          }`}
        >
          知识库检索
        </button>
      </div>
      {mode === 'papers' && (
        <div className="flex items-center gap-4 pb-4">
          {(['completed', 'partial', 'processing', 'failed'] as DocStatus[]).map((s) => (
            <div key={s} className="flex items-center gap-1.5 text-[11px] font-bold text-slate-500">
              <div className={`w-2 h-2 rounded-full ${STATUS_META[s].dot}`} />
              {STATUS_META[s].label}
            </div>
          ))}
        </div>
      )}
    </div>

    {/* 检索范围说明（UX-13：兑现 placeholder 承诺） */}
    {mode === 'papers' && searchQuery.trim() && (
      <p className="text-xs text-slate-500 mb-4">
        「{searchQuery.trim()}」匹配到 {filteredCount} 篇（检索范围：标题、文件名、作者、期刊、年份与洞察字段）
      </p>
    )}
  </>
);
