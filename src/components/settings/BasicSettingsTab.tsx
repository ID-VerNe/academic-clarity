import React from 'react';
import { FolderOpen } from 'lucide-react';
import { AppConfig } from '../../types';
import { FIELDS, TABLE_STYLES, FieldSpec } from './constants';
import { SettingsField } from './SettingsField';

interface BasicSettingsTabProps {
  config: AppConfig | null;
  draft: Record<string, string>;
  errors: Record<string, string>;
  savingField: string | null;
  isDirty: (key: string) => boolean;
  setField: (key: string, value: string) => void;
  requestClear: (field: FieldSpec) => void;
  onSelectWorkspace: () => void;
}

/** 基础配置 tab：工作区 / 三个 OCR 字段 / 表格样式 / 说明 */
export const BasicSettingsTab = ({
  config,
  draft,
  errors,
  savingField,
  isDirty,
  setField,
  requestClear,
  onSelectWorkspace,
}: BasicSettingsTabProps) => (
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

    {FIELDS.map((field) => (
      <SettingsField
        key={field.key}
        field={field}
        value={draft[field.key] ?? ''}
        error={errors[field.key]}
        dirty={isDirty(field.key)}
        saving={savingField === field.key}
        onChange={(value) => setField(field.key, value)}
        onRequestClear={() => requestClear(field)}
      />
    ))}

    <div className="space-y-2">
      <label className="text-xs font-bold text-slate-500">表格样式</label>
      <select
        value={draft.TABLE_STYLE ?? 'three-line'}
        onChange={(e) => setField('TABLE_STYLE', e.target.value)}
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
);
