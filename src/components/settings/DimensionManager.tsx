import React, { useState, useEffect } from 'react';
import {
  Plus, Trash2, Pencil, Play, Download, Loader2, X,
  AlertCircle, CheckCircle2, Layers
} from 'lucide-react';
import { api } from '../../api/client';
import { ExtractionDimension } from '../../types';

const EMPTY_FORM = { id: '', label: '', prompt: '', system_prompt: '', enabled: true };

/**
 * Phase 3：提取维度管理（Settings → Dimensions tab）。
 * 维度定义存 DB；「批量运行」对全部已完成文档入队（BACKGROUND）；
 * 导出 CSV/MD 走 Blob 下载。修改维度不会自动重跑（需 force）。
 */
export const DimensionManager = () => {
  const [dimensions, setDimensions] = useState<ExtractionDimension[]>([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);   // 正在操作的行 id
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchDimensions = async () => {
    try {
      const data = await api.getDimensions();
      setDimensions(data.dimensions || []);
    } catch (e) { console.error('Failed to load dimensions', e); }
  };

  useEffect(() => { fetchDimensions(); }, []);

  const openNew = () => {
    setForm({ ...EMPTY_FORM });
    setError(null);
    setShowForm(true);
  };

  const openEdit = (dim: ExtractionDimension) => {
    setForm({ id: dim.id, label: dim.label, prompt: dim.prompt,
              system_prompt: dim.system_prompt || '', enabled: !!dim.enabled });
    setError(null);
    setShowForm(true);
  };

  const handleSave = async () => {
    setError(null);
    try {
      await api.saveDimension(form);
      await fetchDimensions();
      setShowForm(false);
      setMessage(`已保存维度「${form.label}」（修改不会自动重跑，批量运行才生效）`);
    } catch (e: any) {
      setError(e?.message || 'Save failed');
    }
  };

  const handleDelete = async (dim: ExtractionDimension) => {
    if (!confirm(`删除维度「${dim.label}」？已产生的提取结果会保留。`)) return;
    setBusy(dim.id);
    try {
      await api.deleteDimension(dim.id);
      await fetchDimensions();
      setMessage(`已删除维度「${dim.label}」`);
    } finally {
      setBusy(null);
    }
  };

  const handleRunBatch = async (dim: ExtractionDimension) => {
    setBusy(dim.id);
    setMessage(null);
    try {
      const res = await api.runBatch(dim.id);
      setMessage(`「${dim.label}」已入队 ${res.queued} 篇（跳过 ${res.skipped} 篇；每文档同时只运行一个提取任务）`);
    } catch (e: any) {
      setError(e?.message || 'Batch run failed');
    } finally {
      setBusy(null);
    }
  };

  const handleExport = async (dim: ExtractionDimension, format: 'csv' | 'md') => {
    setBusy(dim.id);
    try {
      const blob = await api.exportDimension(dim.id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${dim.label}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || 'Export failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-600" />
          <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest">
            Extraction Dimensions
          </h3>
        </div>
        <button
          onClick={openNew}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-700 transition-all shadow-sm active:scale-95"
        >
          <Plus className="w-3.5 h-3.5" /> New Dimension
        </button>
      </div>

      <p className="text-[10px] text-slate-400 leading-relaxed">
        自定义提取维度（label + prompt）存于工作区数据库。「Batch Run」对全部已完成
        OCR 的文档批量提取（跳过已有结果；修改 prompt 后需再次批量运行才会更新）。
      </p>

      {message && (
        <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3 flex items-center gap-2 text-emerald-700 text-xs">
          <CheckCircle2 className="w-4 h-4 shrink-0" /> {message}
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-center gap-2 text-red-600 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {showForm && (
        <div className="bg-white border-2 border-indigo-100 rounded-2xl p-4 space-y-3 relative shadow-lg shadow-indigo-100/50">
          <button
            aria-label="Close Dimension Form"
            onClick={() => setShowForm(false)}
            className="absolute top-3 right-3 text-slate-300 hover:text-slate-600"
          >
            <X className="w-3.5 h-3.5" />
          </button>
          <h4 className="text-[10px] font-black uppercase text-indigo-600 tracking-widest">
            {form.id ? 'Edit Dimension' : 'New Dimension'}
          </h4>
          <input
            aria-label="Dimension Label"
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            placeholder="Label (e.g. Methodology) *"
            className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-indigo-300"
          />
          <textarea
            aria-label="Dimension Prompt"
            value={form.prompt}
            onChange={(e) => setForm({ ...form, prompt: e.target.value })}
            placeholder="Prompt (e.g. Extract the core methodology as JSON...) *"
            className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-24 focus:outline-none focus:border-indigo-300 resize-none"
          />
          <textarea
            aria-label="Dimension System Prompt"
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            placeholder="System prompt (optional)"
            className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-14 focus:outline-none focus:border-indigo-300 resize-none"
          />
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Enabled
          </label>
          <button
            onClick={handleSave}
            disabled={!form.label.trim() || !form.prompt.trim()}
            className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 disabled:bg-slate-300"
          >
            Save Dimension
          </button>
        </div>
      )}

      <div className="space-y-3">
        {dimensions.map((dim) => (
          <div key={dim.id}
               className="bg-white border border-slate-200 rounded-2xl p-4 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-800 truncate">{dim.label}</span>
                {!dim.enabled && (
                  <span className="px-2 py-0.5 rounded-full text-[8px] font-black uppercase bg-slate-100 text-slate-400 border border-slate-200">
                    disabled
                  </span>
                )}
              </div>
              <p className="text-[10px] text-slate-400 truncate mt-1 max-w-[380px]">{dim.prompt}</p>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                aria-label={`Edit ${dim.label}`}
                onClick={() => openEdit(dim)}
                className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                title="Edit"
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button
                aria-label={`Run Batch ${dim.label}`}
                onClick={() => handleRunBatch(dim)}
                disabled={busy === dim.id}
                className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                title="Batch Run"
              >
                {busy === dim.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              </button>
              <button
                aria-label={`Export CSV ${dim.label}`}
                onClick={() => handleExport(dim, 'csv')}
                className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                title="Export CSV"
              >
                <Download className="w-3.5 h-3.5" />
              </button>
              <button
                aria-label={`Export MD ${dim.label}`}
                onClick={() => handleExport(dim, 'md')}
                className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                title="Export Markdown"
              >
                <Download className="w-3.5 h-3.5" />
              </button>
              <button
                aria-label={`Delete ${dim.label}`}
                onClick={() => handleDelete(dim)}
                className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                title="Delete"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
        {dimensions.length === 0 && !showForm && (
          <div className="py-10 text-center opacity-40">
            <Layers className="w-8 h-8 mx-auto mb-2 text-slate-400" />
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              No dimensions yet
            </p>
          </div>
        )}
      </div>
    </section>
  );
};
