import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle } from 'lucide-react';
import { useModalFocusTrap } from '../../hooks/useModalFocusTrap';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * 应用内确认弹窗（替代 window.confirm）：
 * - 视觉与产品一致、支持中文文案
 * - ESC 关闭、初始焦点落在「取消」（破坏性操作的安全默认）、Tab 圈定（与设置弹窗共用 useModalFocusTrap）
 */
export const ConfirmDialog = ({
  open,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) => {
  const dialogRef = useModalFocusTrap({ active: open, onEscape: onCancel });

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onCancel}
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
          />
          <motion.div
            ref={dialogRef}
            role="alertdialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl border border-slate-200 p-6"
          >
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-xl shrink-0 ${danger ? 'bg-rose-50 text-rose-600' : 'bg-indigo-50 text-indigo-600'}`}>
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-slate-900">{title}</h3>
                {message && <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{message}</p>}
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={onCancel}
                disabled={busy}
                className="px-4 py-2 text-xs font-bold text-slate-600 rounded-xl hover:bg-slate-100 transition-colors disabled:opacity-50"
              >
                {cancelText}
              </button>
              <button
                onClick={onConfirm}
                disabled={busy}
                className={`px-4 py-2 text-xs font-bold text-white rounded-xl transition-colors disabled:opacity-50 ${
                  danger ? 'bg-rose-600 hover:bg-rose-700' : 'bg-indigo-600 hover:bg-indigo-700'
                }`}
              >
                {confirmText}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
