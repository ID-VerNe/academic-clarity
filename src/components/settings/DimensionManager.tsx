import React, { useState, useEffect, useRef } from 'react';
import { Plus, AlertCircle, Layers } from 'lucide-react';
import { api } from '../../api/client';
import { ExtractionDimension } from '../../types';
import { ConfirmDialog } from '../ui/ConfirmDialog';
import { toast } from '../ui/Toast';
import { DimensionForm, DimensionFormState, EMPTY_FORM } from './DimensionForm';
import { DimensionRow } from './DimensionRow';

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
  const [form, setForm] = useState<DimensionFormState>({ ...EMPTY_FORM });
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

  useEffect(() => { fetchDimensions(); }, []);

  // 点击空白处收起行内菜单
  useEffect(() => {
    if (!menuFor) return;
    const onClick = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuFor(null);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [menuFor]);

  /** 打开表单（新建/编辑共用：装载草稿、重置错误、显示） */
  const openForm = (next: DimensionFormState) => {
    setForm(next);
    setError(null);
    setShowForm(true);
  };

  const openNew = () => openForm({ ...EMPTY_FORM });

  const openEdit = (dim: ExtractionDimension) =>
    openForm({ id: dim.id, label: dim.label, prompt: dim.prompt, system_prompt: dim.system_prompt || '', enabled: !!dim.enabled });

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
        <DimensionForm
          form={form}
          onChange={setForm}
          onSave={handleSave}
          onClose={() => setShowForm(false)}
        />
      )}

      <div className="space-y-3">
        {dimensions.map((dim) => (
          <DimensionRow
            key={dim.id}
            dim={dim}
            busy={busy === dim.id}
            menuOpen={menuFor === dim.id}
            menuRef={menuRef}
            onEdit={() => openEdit(dim)}
            onRunBatch={() => handleRunBatch(dim)}
            onToggleMenu={() => setMenuFor(menuFor === dim.id ? null : dim.id)}
            onExport={(format) => handleExport(dim, format)}
            onRequestDelete={() => {
              setMenuFor(null);
              setDeleteTarget(dim);
            }}
          />
        ))}
        {dimensions.length === 0 && !showForm && (
          <div className="py-10 text-center">
            <Layers className="w-8 h-8 mx-auto mb-2 text-slate-300" />
            <p className="text-sm font-bold text-slate-500">还没有提取维度</p>
            <p className="text-xs text-slate-400 mt-1">新建一个维度后，可对全部文献批量提取结构化结果。</p>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        danger
        busy={!!busy}
        title="删除这个维度？"
        message={deleteTarget ? `「${deleteTarget.label}」的维度定义将被删除，已产生的提取结果会保留。` : ''}
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </section>
  );
};
