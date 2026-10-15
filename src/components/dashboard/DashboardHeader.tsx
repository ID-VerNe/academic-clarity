import React from 'react';
import { AlertTriangle, FolderOpen, Plus, RefreshCw, Settings } from 'lucide-react';
import { AppConfig } from '../../types';
import { Button } from '../ui/Button';

interface DashboardHeaderProps {
  docsCount: number;
  activeCount: number;
  filteredCount: number;
  isUploading: boolean;
  isSyncing: boolean;
  config: AppConfig | null;
  onSync: () => void;
  onSelectWorkspace: () => void;
  onImportClick: () => void;
  onOpenSettings: () => void;
}

/** 顶部区：文献库标题 / 同步 / 工作区切换 / 导入入口 + 配置引导横幅（UX-32） */
export const DashboardHeader = ({
  docsCount,
  activeCount,
  filteredCount,
  isUploading,
  isSyncing,
  config,
  onSync,
  onSelectWorkspace,
  onImportClick,
  onOpenSettings,
}: DashboardHeaderProps) => {
  // 配置完整性（UX-32）：缺 Key / 缺模型时给出可操作提示
  const missingConfig: string[] = [];
  if (config) {
    if (!config.DEEPSEEK_API_KEY) missingConfig.push('OCR API Key');
    if (!config.OCR_MODEL) missingConfig.push('OCR 模型名');
  }

  return (
    <>
      <div className="flex items-end justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">文献库</h2>
            <button
              onClick={onSync}
              disabled={isSyncing}
              aria-label="同步工作区"
              title="同步工作区（扫描文件夹并处理未完成的文献）"
              className={`p-1.5 mt-1 rounded-lg transition-all ${
                isSyncing
                  ? 'text-indigo-600 bg-indigo-50'
                  : 'text-slate-400 hover:text-indigo-600 hover:bg-indigo-50'
              }`}
            >
              <RefreshCw className={`w-5 h-5 ${isSyncing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onSelectWorkspace}
              aria-label="切换工作区"
              title="切换工作区"
              className="p-1.5 mt-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            >
              <FolderOpen className="w-5 h-5" />
            </button>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            共 {docsCount} 篇文献
            {activeCount > 0 && ` · ${activeCount} 篇处理中`}
            {filteredCount !== docsCount && ` · 当前显示 ${filteredCount} 篇`}
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <Button
            icon={<Plus className="w-4 h-4" />}
            loading={isUploading}
            onClick={() => !isUploading && onImportClick()}
            className="px-5 py-2.5 text-white shadow-lg shadow-indigo-100"
          >
            {isUploading ? '导入中…' : '导入 PDF / LaTeX'}
          </Button>
        </div>
      </div>

      {/* 配置引导横幅（UX-32） */}
      {missingConfig.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-amber-900">尚未完成 AI 配置，导入的文献将无法处理</p>
            <p className="text-xs text-amber-700 mt-1">缺少：{missingConfig.join('、')}</p>
          </div>
          <button
            onClick={onOpenSettings}
            className="flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-xs font-bold rounded-xl hover:bg-amber-700 transition-colors shrink-0"
          >
            <Settings className="w-3.5 h-3.5" />
            去设置
          </button>
        </div>
      )}
    </>
  );
};
