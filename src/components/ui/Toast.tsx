import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

/**
 * 轻量全局反馈体系（Toast）。
 * 用法：`toast.success('已保存')` / `toast.error('连接失败')` / `toast.info('处理中')`。
 * 宿主组件 `<ToastHost/>` 挂载在 App 根部。
 */

export type ToastKind = 'success' | 'error' | 'info';

export interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

type Listener = (items: ToastItem[]) => void;

let items: ToastItem[] = [];
const listeners = new Set<Listener>();
let seq = 0;
const AUTO_DISMISS_MS = 4500;

function emit() {
  const snapshot = [...items];
  listeners.forEach((l) => l(snapshot));
}

export function dismissToast(id: number) {
  items = items.filter((t) => t.id !== id);
  emit();
}

/** 仅供测试：清空队列 */
export function clearToasts() {
  items = [];
  emit();
}

function push(kind: ToastKind, message: string) {
  const id = ++seq;
  items = [...items, { id, kind, message }];
  emit();
  setTimeout(() => dismissToast(id), AUTO_DISMISS_MS);
}

export const toast = {
  success: (message: string) => push('success', message),
  error: (message: string) => push('error', message),
  info: (message: string) => push('info', message),
};

const KIND_STYLE: Record<ToastKind, { icon: React.ReactNode; border: string; iconColor: string }> = {
  success: { icon: <CheckCircle2 className="w-4 h-4" />, border: 'border-emerald-200', iconColor: 'text-emerald-600' },
  error: { icon: <AlertCircle className="w-4 h-4" />, border: 'border-rose-200', iconColor: 'text-rose-600' },
  info: { icon: <Info className="w-4 h-4" />, border: 'border-indigo-200', iconColor: 'text-indigo-600' },
};

export const ToastHost = () => {
  const [list, setList] = useState<ToastItem[]>(items);

  useEffect(() => {
    const listener: Listener = (next) => setList(next);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  return (
    <div
      data-testid="toast-host"
      role="status"
      aria-live="polite"
      className="fixed bottom-16 right-6 z-[200] flex flex-col gap-2 max-w-sm"
    >
      <AnimatePresence>
        {list.map((t) => {
          const style = KIND_STYLE[t.kind];
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              className={`flex items-start gap-2.5 bg-white border ${style.border} rounded-xl px-4 py-3 shadow-lg shadow-slate-200/60`}
            >
              <span className={`${style.iconColor} mt-0.5 shrink-0`}>{style.icon}</span>
              <p className="text-xs font-medium text-slate-700 leading-relaxed flex-1">{t.message}</p>
              <button
                aria-label="关闭提示"
                onClick={() => dismissToast(t.id)}
                className="text-slate-300 hover:text-slate-500 transition-colors shrink-0"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
};
