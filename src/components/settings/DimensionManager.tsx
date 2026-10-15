import React, { useState, useEffect, useRef } from 'react';
import {
  Plus, Trash2, Pencil, Play, Download, Loader2, X,
  AlertCircle, CheckCircle2, Layers, MoreHorizontal, FileSpreadsheet, FileText
} from 'lucide-react';
import { api } from '../../api/client';
import { ExtractionDimension } from '../../types';
import { ConfirmDialog } from '../ui/ConfirmDialog';
import { toast } from '../ui/Toast';

const EMPTY_FORM = { id: '', label: '', prompt: '', system_prompt: '', enabled: true };

/**
 * Phase 3：提取维度管理（设置 → 提取维度）。
 * 维度定义存 DB；「批量运行」对全部已完成文档入队（BACKGROUND）；
 * 导出 CSV/MD 走 Blob 下载。修改维度不会自动重跑（需再次批量运行）。
 *
 * 注意：与阅读器侧栏的「立即提取」不同——这里的维度可复用、可批量；
 * 「立即提取」只对当前文档执行一次、不落维度表。
 */
export const DimensionManager = () => {
  const [dimensions, setDimensions] = useState<ExtractionDimension[]>([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState<string | null>(null); // 正在操作的行 id
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ExtractionDimension | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const fetchDimensions = async () => {
    try {
      const data = await api.getDimensions();
      setDimensions(data?.dimensions || []);
    } catch (e) {
      console.error('Failed to load dimensions', e);
    }
  };

  useEffect(() => {
    fetchDimensions();
  }, []);

  // 点击空白处收起行内菜单
  useEffect(() => {
    if (!menuFor) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current?.contains(e.target as Node)) return;
      setMenuFor(null);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [menuFor]);

  const openNew = () => {
    setForm({ ...EMPTY_FORM });
    setError(null);
    setShowForm(true);
  };

  const openEdit = (dim: ExtractionDimension) => {
    setForm({
      id: dim.id,
      label: dim.label,
      prompt: dim.prompt,
      system_prompt: dim.system_prompt || '',
      enabled: !!dim.enabled,
    });
    setError(null);
    setShowForm(true);
  };

  const handleSave = async () => {
    setError(null);
    try {
      await api.saveDimension(form);
      await fetchDimensions();
      setShowForm(false);
      toast.success(`已保存维度「${form.label}」（修改需再次批量运行才会生效）`);
    } catch (e: any) {
      setError(e?.message || '保存失败');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const dim = deleteTarget;
    setBusy(dim.id);
    try {
      await api.deleteDimension(dim.id);
      await fetchDimensions();
      toast.success(`已删除维度「${dim.label}」（已产生的提取结果保留）`);
      setDeleteTarget(null);
    } catch (e: any) {
      toast.error(`删除失败：${e?.message || '请稍后重试'}`);
    } finally {
      setBusy(null);
    }
  };

  const handleRunBatch = async (dim: ExtractionDimension) => {
    setBusy(dim.id);
    try {
      const res = await api.runBatch(dim.id);
      toast.success(`「${dim.label}」已入队 ${res.queued} 篇（跳过 ${res.skipped} 篇）`);
    } catch (e: any) {
      toast.error(`批量运行失败：${e?.message || '请稍后重试'}`);
    } finally {
      setBusy(null);
    }
  };

  const handleExport = async (dim: ExtractionDimension, format: 'csv' | 'md') => {
    setBusy(dim.id);
    setMenuFor(null);
    try {
      const blob = await api.exportDimension(dim.id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${dim.label}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`已导出「${dim.label}」为 ${format.toUpperCase()}`);
    } catch (e: any) {
      toast.error(`导出失败：${e?.message || '请稍后重试'}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-700">提取维度</h3>
        </div>
        <button
          onClick={openNew}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-700 transition-all shadow-sm active:scale-95"
        >
          <Plus className="w-3.5 h-3.5" />
          新建维度
        </button>
      </div>

      <p className="text-xs text-slate-500 leading-relaxed">
        维度由「名称 + 提示词」定义，保存在工作区数据库中。点「批量运行」对全部已完成 OCR
        的文献提取（跳过已有结果；改了提示词需再次批量运行才会更新）。
      </p>

      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-center gap-2 text-rose-600 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {showForm && (
        <div className="bg-white border-2 border-indigo-100 rounded-2xl p-4 space-y-3 relative shadow-lg shadow-indigo-100/50">
          <button
            aria-label="关闭维度表单"
            onClick={() => setShowForm(false)}
            className="absolute top-3 right-3 text-slate-300 hover:text-slate-600"
          >
            <X className="w-3.5 h-3.5" />
          </button>
          <h4 className="text-xs font-bold text-indigo-600">{form.id ? '编辑维度' : '新建维度'}</h4>
          <input
            aria-label="维度名称"
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            placeholder="名称（如：方法论）*"
            className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-indigo-300"
          />
          <textarea
            aria-label="提取提示词"
            value={form.prompt}
            onChange={(e) => setForm({ ...form, prompt: e.target.value })}
            placeholder="提示词（如：提取核心方法论并输出 JSON…）*"
            className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-24 focus:outline-none focus:border-indigo-300 resize-none"
          />
          <textarea
            aria-label="系统提示词"
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            placeholder="系统提示词（可选）"
            className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-14 focus:outline-none focus:border-indigo-300 resize-none"
          />
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            启用（禁用后不参与批量运行）
          </label>
          <button
            onClick={handleSave}
            disabled={!form.label.trim() || !form.prompt.trim()}
            className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 disabled:bg-slate-300"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            保存维度
          </button>
        </div>
      )}

      <div className="space-y-3">
        {dimensions.map((dim) => (
          <div
            key={dim.id}
            className="bg-white border border-slate-200 rounded-2xl p-4 flex items-start justify-between gap-3"
          >
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
                onClick={() => openEdit(dim)}
                className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                title="编辑"
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button
                aria-label={`批量运行 ${dim.label}`}
                onClick={() => handleRunBatch(dim)}
                disabled={busy === dim.id || !dim.enabled}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors disabled:opacity-40 disabled:hover:bg-emerald-50"
                title={dim.enabled ? '对全部已完成文献批量提取' : '维度已禁用'}
              >
                {busy === dim.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                批量运行
              </button>
              <div className="relative" ref={menuFor === dim.id ? menuRef : undefined}>
                <button
                  aria-label={`更多操作 ${dim.label}`}
                  aria-expanded={menuFor === dim.id}
                  onClick={() => setMenuFor(menuFor === dim.id ? null : dim.id)}
                  className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                  title="更多操作"
                >
                  <MoreHorizontal className="w-3.5 h-3.5" />
                </button>
                {menuFor === dim.id && (
                  <div className="absolute right-0 top-full mt-1 z-30 w-44 bg-white border border-slate-200 rounded-xl shadow-xl py-1">
                    <button
                      onClick={() => handleExport(dim, 'csv')}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                    >
                      <FileSpreadsheet className="w-3.5 h-3.5" />
                      导出 CSV
                    </button>
                    <button
                      onClick={() => handleExport(dim, 'md')}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      导出 Markdown
                    </button>
                    <div className="my-1 h-px bg-slate-100" />
                    <button
                      onClick={() => {
                        setMenuFor(null);
                        setDeleteTarget(dim);
                      }}
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
        ))}
        {dimensions.length === 0 && !showForm && (
          <div className="py-10 text-center">
            <Layers className="w-8 h-8 mx-auto mb-2 text-slate-300" />
            <p className="text-sm font-bold text-slate-500">还没有提取维度</p>
            <p className="text-xs text-slate-400 mt-1">
              新建一个维度后，可对全部文献批量提取结构化结果。
            </p>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        danger
        busy={!!busy}
        title="删除这个维度？"
        message={
          deleteTarget
            ? `「${deleteTarget.label}」的维度定义将被删除，已产生的提取结果会保留。`
            : ''
        }
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </section>
  );
};
