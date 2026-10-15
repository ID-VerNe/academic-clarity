import React, { useState, useEffect, useRef } from 'react';
import { X, Settings, Database, FolderOpen, Save, Loader2, AlertCircle, Layers, Eye, EyeOff, Eraser } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { AppConfig } from '../types';
import { ConfirmDialog } from './ui/ConfirmDialog';
import { DimensionManager } from './settings/DimensionManager';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig | null;
  /** 返回 true 表示保存成功（调用方负责 toast 反馈） */
  onSaveConfig: (key: string, value: string) => Promise<boolean>;
  onSelectWorkspace: () => void;
}

type TabType = 'basic' | 'dimensions';

interface FieldSpec {
  key: keyof AppConfig & string;
  label: string;
  hint: string;
  placeholder: string;
  secret?: boolean;
  required?: boolean;
  validate?: (value: string) => string | null;
}

const FIELDS: FieldSpec[] = [
  {
    key: 'DEEPSEEK_API_KEY',
    label: 'OCR API Key',
    hint: '用于调用 OCR 模型（DeepSeek-OCR / SiliconFlow）',
    placeholder: 'sk-...',
    secret: true,
    required: true,
  },
  {
    key: 'API_BASE',
    label: 'API Base URL',
    hint: 'OCR 服务地址；本地代理可填 http://localhost:37210/v1',
    placeholder: 'https://api.siliconflow.cn/v1',
    required: true,
    validate: (v) => (/^https?:\/\//.test(v) ? null : '必须以 http:// 或 https:// 开头'),
  },
  {
    key: 'OCR_MODEL',
    label: 'OCR 模型名',
    hint: '如 deepseek-ai/DeepSeek-OCR',
    placeholder: 'deepseek-ai/DeepSeek-OCR',
    required: true,
  },
];

const TABLE_STYLES = [
  { value: 'three-line', label: '三线表（学术论文常用）' },
  { value: 'grid', label: '网格表' },
];

/**
 * 设置弹窗。
 * - 多 Key 轮询已由本地代理承担，应用内只保留单 Key 配置（不再提供 Key 池编辑）
 * - 显式保存 + 保存反馈 + 空值保护（UX-29）
 * - ESC 关闭、焦点圈定、未保存提醒（UX-31）
 */
export const SettingsModal = ({
  isOpen,
  onClose,
  config,
  onSaveConfig,
  onSelectWorkspace,
}: SettingsModalProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('basic');
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [savingField, setSavingField] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [confirmClose, setConfirmClose] = useState(false);
  const [clearTarget, setClearTarget] = useState<FieldSpec | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  // 打开时用最新配置初始化草稿
  useEffect(() => {
    if (!isOpen || !config) return;
    setDraft({
      DEEPSEEK_API_KEY: config.DEEPSEEK_API_KEY || '',
      API_BASE: config.API_BASE || '',
      OCR_MODEL: config.OCR_MODEL || '',
      TABLE_STYLE: config.TABLE_STYLE || 'three-line',
    });
    setErrors({});
    setActiveTab('basic');
  }, [isOpen, config]);

  const isDirty = (key: string) => {
    if (!config) return false;
    const current = (config as any)[key] ?? '';
    return (draft[key] ?? '') !== current;
  };
  const dirtyKeys = Object.keys(draft).filter((k) => isDirty(k));
  const hasUnsaved = dirtyKeys.length > 0;

  // ESC 关闭 + 焦点圈定 + 关闭后归还焦点
  useEffect(() => {
    if (!isOpen) return;
    lastFocusedRef.current = document.activeElement as HTMLElement;
    const focusable = () =>
      Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href]'
        ) || []
      );
    const first = focusable()[0];
    first?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        requestClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusable();
      if (items.length === 0) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      lastFocusedRef.current?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, hasUnsaved]);

  if (!isOpen) return null;

  const requestClose = () => {
    if (hasUnsaved) {
      setConfirmClose(true);
      return;
    }
    onClose();
  };

  const validateField = (field: FieldSpec, value: string): string | null => {
    if (field.required && !value.trim()) return '不能为空';
    return field.validate ? field.validate(value.trim()) : null;
  };

  const handleSave = async () => {
    const nextErrors: Record<string, string> = {};
    FIELDS.forEach((f) => {
      const err = validateField(f, draft[f.key] ?? '');
      if (err) nextErrors[f.key] = err;
    });
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setErrors({});

    const targets = [...FIELDS.map((f) => f.key), 'TABLE_STYLE' as const].filter((k) => isDirty(k));
    if (targets.length === 0) return;

    let allOk = true;
    for (const key of targets) {
      setSavingField(key);
      // eslint-disable-next-line no-await-in-loop
      const ok = await onSaveConfig(key, (draft[key] ?? '').trim());
      if (!ok) allOk = false;
    }
    setSavingField(null);
    if (allOk) onClose();
  };

  const handleClear = async (field: FieldSpec) => {
    setClearTarget(field);
  };

  const confirmClear = async () => {
    if (!clearTarget) return;
    const key = clearTarget.key;
    setSavingField(key);
    const ok = await onSaveConfig(key, '');
    setSavingField(null);
    if (ok) {
      setDraft((prev) => ({ ...prev, [key]: '' }));
      setErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
    setClearTarget(null);
  };

  const renderTab = (tab: TabType, label: string, icon: React.ReactNode) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
        activeTab === tab ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-100'
      }`}
    >
      {icon}
      {label}
    </button>
  );

  const inputClass = (hasError: boolean) =>
    `w-full bg-white border rounded-xl px-4 py-3 text-xs outline-none transition-all shadow-sm ${
      hasError
        ? 'border-rose-400 focus:ring-4 focus:ring-rose-50'
        : 'border-slate-200 focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400'
    }`;

  return (
    <>
      <AnimatePresence>
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={requestClose}
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
          />

          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label="设置"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-3xl bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-200"
          >
            <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-600 rounded-xl">
                  <Settings className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900">设置</h2>
                  <p className="text-xs text-slate-400">配置 OCR 引擎与提取维度</p>
                </div>
              </div>
              <button
                onClick={requestClose}
                aria-label="关闭设置"
                className="p-2 hover:bg-slate-200 rounded-full text-slate-400 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-8 py-4 border-b border-slate-100 flex gap-2">
              {renderTab('basic', '基础配置', <Database className="w-3 h-3" />)}
              {renderTab('dimensions', '提取维度', <Layers className="w-3 h-3" />)}
            </div>

            <div className="p-8 max-h-[60vh] overflow-y-auto custom-scrollbar">
              {activeTab === 'basic' && (
                <section className="space-y-6">
                  <div className="space-y-3">
                    <label className="block text-xs font-bold text-slate-500">当前工作区</label>
                    <div className="flex items-center gap-3">
                      <div
                        className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-xs font-mono text-slate-600 truncate shadow-sm"
                        title={config?.WORKSPACE_PATH || ''}
                      >
                        {config?.WORKSPACE_PATH || '尚未选择'}
                      </div>
                      <button
                        onClick={onSelectWorkspace}
                        className="flex items-center gap-2 px-4 py-3 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50 transition-all shadow-sm active:scale-95 shrink-0"
                      >
                        <FolderOpen className="w-4 h-4 text-indigo-600" />
                        切换
                      </button>
                    </div>
                  </div>

                  {FIELDS.map((field) => {
                    const value = draft[field.key] ?? '';
                    const error = errors[field.key];
                    const dirty = isDirty(field.key);
                    return (
                      <div key={field.key} className="space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <label className="text-xs font-bold text-slate-500 flex items-center gap-2">
                            {field.label}
                            {dirty && (
                              <span className="px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[11px] font-bold">
                                未保存
                              </span>
                            )}
                          </label>
                          {value && (
                            <button
                              onClick={() => handleClear(field)}
                              disabled={savingField === field.key}
                              className="flex items-center gap-1 text-[11px] font-bold text-slate-400 hover:text-rose-600 transition-colors disabled:opacity-50"
                            >
                              <Eraser className="w-3 h-3" />
                              清空
                            </button>
                          )}
                        </div>
                        <div className="relative">
                          <input
                            type={field.secret && !revealed[field.key] ? 'password' : 'text'}
                            value={value}
                            onChange={(e) => {
                              const next = e.target.value;
                              setDraft((prev) => ({ ...prev, [field.key]: next }));
                              setErrors((prev) => {
                                const copy = { ...prev };
                                delete copy[field.key];
                                return copy;
                              });
                            }}
                            placeholder={field.placeholder}
                            aria-label={field.label}
                            className={inputClass(!!error) + (field.secret ? ' pr-11' : '')}
                          />
                          {field.secret && (
                            <button
                              type="button"
                              onClick={() => setRevealed((prev) => ({ ...prev, [field.key]: !prev[field.key] }))}
                              aria-label={revealed[field.key] ? '隐藏密钥' : '显示密钥'}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                            >
                              {revealed[field.key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          )}
                        </div>
                        {error ? (
                          <p className="text-[11px] text-rose-500 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            {error}
                          </p>
                        ) : (
                          <p className="text-[11px] text-slate-400">{field.hint}</p>
                        )}
                      </div>
                    );
                  })}

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-500">表格样式</label>
                    <select
                      value={draft.TABLE_STYLE ?? 'three-line'}
                      onChange={(e) => setDraft((prev) => ({ ...prev, TABLE_STYLE: e.target.value }))}
                      aria-label="表格样式"
                      className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-xs outline-none focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400 transition-all shadow-sm cursor-pointer"
                    >
                      {TABLE_STYLES.map((s) => (
                        <option key={s.value} value={s.value}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                    <p className="text-[11px] text-slate-400">影响阅读器中 Markdown 表格的渲染方式</p>
                  </div>

                  <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4">
                    <p className="text-xs text-slate-500 leading-relaxed">
                      多 Key 轮询已由本地代理承担，此处只需配置代理地址与单个 Key。
                      LLM（洞察提取 / 对话）使用后端默认配置。
                    </p>
                  </div>
                </section>
              )}

              {activeTab === 'dimensions' && <DimensionManager />}
            </div>

            <div className="px-8 py-6 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-4">
              <p className="text-xs text-slate-500">
                {hasUnsaved ? `有 ${dirtyKeys.length} 项未保存的修改` : '所有修改已保存'}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={requestClose}
                  className="px-6 py-3 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-100 transition-all"
                >
                  {hasUnsaved ? '放弃修改' : '关闭'}
                </button>
                <button
                  onClick={handleSave}
                  disabled={!hasUnsaved || !!savingField}
                  className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 shadow-lg shadow-indigo-100 transition-all disabled:opacity-40 disabled:shadow-none"
                >
                  {savingField ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {savingField ? '保存中…' : '保存'}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      </AnimatePresence>

      <ConfirmDialog
        open={confirmClose}
        danger
        title="放弃未保存的修改？"
        message="关闭后本次修改将丢失。"
        confirmText="放弃修改"
        cancelText="继续编辑"
        onConfirm={() => {
          setConfirmClose(false);
          onClose();
        }}
        onCancel={() => setConfirmClose(false)}
      />

      <ConfirmDialog
        open={!!clearTarget}
        danger
        busy={!!savingField}
        title={`清空「${clearTarget?.label ?? ''}」？`}
        message="清空后该配置将变为空值，相关功能可能不可用。"
        confirmText="清空"
        cancelText="取消"
        onConfirm={confirmClear}
        onCancel={() => setClearTarget(null)}
      />
    </>
  );
};
