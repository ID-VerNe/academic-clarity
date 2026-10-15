import React from 'react';
import { DashboardMode } from './constants';

interface DashboardFooterProps {
  backendHealthy: boolean;
  mode: DashboardMode;
  claimsCount: number;
  filteredCount: number;
  docsCount: number;
}

/** 页脚：后端状态灯 + 按模式计数的口径（UX-36 / UX-44） */
export const DashboardFooter = ({
  backendHealthy,
  mode,
  claimsCount,
  filteredCount,
  docsCount,
}: DashboardFooterProps) => (
  <footer className="fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-md border-t border-slate-200 h-12 flex items-center px-6 justify-between z-50">
    <div className="flex items-center gap-6">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${backendHealthy ? 'bg-emerald-500' : 'bg-rose-500'}`} />
        <span className="text-xs text-slate-600 font-bold">
          {backendHealthy ? '后端已连接' : '后端未连接'}
        </span>
      </div>
      <span className="text-xs text-slate-300">|</span>
      <span className="text-xs text-slate-500 font-medium">
        {mode === 'claims' ? `${claimsCount} 条检索结果` : `${filteredCount} / ${docsCount} 篇文献`}
      </span>
    </div>
    {!backendHealthy && (
      <span className="text-xs text-rose-600 font-bold">
        无法连接后端服务，请确认应用已完全启动或重启应用
      </span>
    )}
  </footer>
);
