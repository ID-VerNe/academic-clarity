import React from 'react';
import { X, CheckCircle2 } from 'lucide-react';

export interface DimensionFormState {
  id: string;
  label: string;
  prompt: string;
  system_prompt: string;
  enabled: boolean;
}

export const EMPTY_FORM: DimensionFormState = {
  id: '',
  label: '',
  prompt: '',
  system_prompt: '',
  enabled: true,
};

interface DimensionFormProps {
  form: DimensionFormState;
  onChange: (form: DimensionFormState) => void;
  onSave: () => void;
  onClose: () => void;
}

/** 维度新建/编辑表单（受控；保存按钮在 label+prompt 填写前禁用） */
export const DimensionForm = ({ form, onChange, onSave, onClose }: DimensionFormProps) => (
  <div className="bg-white border-2 border-indigo-100 rounded-2xl p-4 space-y-3 relative shadow-lg shadow-indigo-100/50">
    <button
      aria-label="关闭维度表单"
      onClick={onClose}
      className="absolute top-3 right-3 text-slate-300 hover:text-slate-600"
    >
      <X className="w-3.5 h-3.5" />
    </button>
    <h4 className="text-xs font-bold text-indigo-600">{form.id ? '编辑维度' : '新建维度'}</h4>
    <input
      aria-label="维度名称"
      value={form.label}
      onChange={(e) => onChange({ ...form, label: e.target.value })}
      placeholder="名称（如：方法论）*"
      className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-indigo-300"
    />
    <textarea
      aria-label="提取提示词"
      value={form.prompt}
      onChange={(e) => onChange({ ...form, prompt: e.target.value })}
      placeholder="提示词（如：提取核心方法论并输出 JSON…）*"
      className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-24 focus:outline-none focus:border-indigo-300 resize-none"
    />
    <textarea
      aria-label="系统提示词"
      value={form.system_prompt}
      onChange={(e) => onChange({ ...form, system_prompt: e.target.value })}
      placeholder="系统提示词（可选）"
      className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-14 focus:outline-none focus:border-indigo-300 resize-none"
    />
    <label className="flex items-center gap-2 text-xs text-slate-600">
      <input
        type="checkbox"
        checked={form.enabled}
        onChange={(e) => onChange({ ...form, enabled: e.target.checked })}
      />
      启用（禁用后不参与批量运行）
    </label>
    <button
      onClick={onSave}
      disabled={!form.label.trim() || !form.prompt.trim()}
      className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 disabled:bg-slate-300"
    >
      <CheckCircle2 className="w-3.5 h-3.5" />
      保存维度
    </button>
  </div>
);
