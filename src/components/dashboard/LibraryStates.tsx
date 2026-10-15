import React from 'react';
import { FolderOpen, Inbox, Search, Settings, Upload } from 'lucide-react';
import { EmptyState } from '../ui/EmptyState';

/** 骨架屏（UX-38：加载态可见） */
export const LibrarySkeleton = () => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
    {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
      <div key={i} className="h-56 bg-white border-2 border-slate-100 rounded-3xl animate-pulse" />
    ))}
  </div>
);

interface EmptyLibraryProps {
  onSelectWorkspace: () => void;
  onOpenSettings: () => void;
  onImportFirst: () => void;
}

/** 空库：三步引导（UX-12 / UX-32） */
export const EmptyLibrary = ({ onSelectWorkspace, onOpenSettings, onImportFirst }: EmptyLibraryProps) => (
  <div className="py-16 px-8 text-center bg-white border-2 border-dashed border-slate-200 rounded-3xl">
    <div className="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mx-auto">
      <Inbox className="w-8 h-8 text-indigo-400" />
    </div>
    <h3 className="text-lg font-bold text-slate-800 mt-4">文献库还是空的</h3>
    <p className="text-sm text-slate-500 mt-1">按下面三步开始：</p>
    <ol className="max-w-md mx-auto mt-6 space-y-3 text-left">
      {[
        { step: '1', title: '选择工作区', desc: '指定存放 PDF 的本地文件夹' },
        { step: '2', title: '配置 OCR API Key', desc: '在设置 → 基础配置中填写' },
        { step: '3', title: '导入 PDF / LaTeX', desc: '点击右上角按钮，或直接把文件拖到本页' },
      ].map((item) => (
        <li key={item.step} className="flex items-start gap-3 bg-slate-50 rounded-2xl px-4 py-3">
          <span className="w-6 h-6 rounded-full bg-indigo-600 text-white text-xs font-bold flex items-center justify-center shrink-0">
            {item.step}
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-bold text-slate-700">{item.title}</span>
            <span className="block text-xs text-slate-500 mt-0.5">{item.desc}</span>
          </span>
        </li>
      ))}
    </ol>
    <div className="flex items-center justify-center gap-3 mt-6">
      <button
        onClick={onSelectWorkspace}
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-700 text-sm font-semibold rounded-xl hover:bg-slate-50 transition-colors"
      >
        <FolderOpen className="w-4 h-4 text-indigo-600" />
        选择工作区
      </button>
      <button
        onClick={onOpenSettings}
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-700 text-sm font-semibold rounded-xl hover:bg-slate-50 transition-colors"
      >
        <Settings className="w-4 h-4 text-indigo-600" />
        打开设置
      </button>
      <button
        onClick={onImportFirst}
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100"
      >
        <Upload className="w-4 h-4" />
        导入第一篇
      </button>
    </div>
  </div>
);

interface NoFilterResultsProps {
  onReset: () => void;
}

/** 筛选无结果（UX-12：与空库区分） */
export const NoFilterResults = ({ onReset }: NoFilterResultsProps) => (
  <EmptyState
    tone="slate"
    icon={<Search className="w-8 h-8 text-slate-300" />}
    title="没有符合当前筛选条件的文献"
  >
    <button onClick={onReset} className="text-indigo-600 font-bold text-xs hover:underline">
      重置全部筛选条件
    </button>
  </EmptyState>
);
