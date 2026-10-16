import React, { useState } from 'react';
import { AlertCircle, Eye, EyeOff, Eraser } from 'lucide-react';
import { FieldSpec } from './constants';

interface SettingsFieldProps {
  field: FieldSpec;
  value: string;
  error?: string;
  /** 与已保存配置不一致（显示「未保存」徽标） */
  dirty: boolean;
  /** 该字段正在保存（禁用清空按钮） */
  saving: boolean;
  onChange: (value: string) => void;
  onRequestClear: () => void;
}

const inputClass = (hasError: boolean) =>
  `w-full bg-white border rounded-xl px-4 py-3 text-xs outline-none transition-all shadow-sm ${
    hasError
      ? 'border-rose-400 focus:ring-4 focus:ring-rose-50'
      : 'border-slate-200 focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400'
  }`;

/** 设置字段行：label / 未保存徽标 / 清空 / 密码显隐 / 错误提示 */
export const SettingsField = ({
  field,
  value,
  error,
  dirty,
  saving,
  onChange,
  onRequestClear,
}: SettingsFieldProps) => {
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="space-y-2">
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
            onClick={onRequestClear}
            disabled={saving}
            className="flex items-center gap-1 text-[11px] font-bold text-slate-400 hover:text-rose-600 transition-colors disabled:opacity-50"
          >
            <Eraser className="w-3 h-3" />
            清空
          </button>
        )}
      </div>
      <div className="relative">
        <input
          type={field.secret && !revealed ? 'password' : 'text'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          aria-label={field.label}
          className={inputClass(!!error) + (field.secret ? ' pr-11' : '')}
        />
        {field.secret && (
          <button
            type="button"
            onClick={() => setRevealed((prev) => !prev)}
            aria-label={revealed ? '隐藏密钥' : '显示密钥'}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
          >
            {revealed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
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
};
