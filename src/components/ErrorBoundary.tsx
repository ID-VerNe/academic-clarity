import React from 'react';
import { AlertOctagon } from 'lucide-react';

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

/**
 * 顶层错误边界：组件异常时兜底展示，避免整屏白屏。
 */
export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error?.message || '未知错误' };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-8">
        <div className="max-w-md w-full bg-white border border-slate-200 rounded-3xl p-8 text-center shadow-sm">
          <div className="w-14 h-14 bg-rose-50 rounded-2xl flex items-center justify-center mx-auto mb-5">
            <AlertOctagon className="w-7 h-7 text-rose-500" />
          </div>
          <h1 className="text-lg font-bold text-slate-900">界面出现异常</h1>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed break-all">{this.state.message}</p>
          <div className="flex justify-center gap-3 mt-6">
            <button
              onClick={() => window.location.reload()}
              className="px-5 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 transition-colors"
            >
              重新加载
            </button>
          </div>
        </div>
      </div>
    );
  }
}
