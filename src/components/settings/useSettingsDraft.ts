import { useEffect, useState } from 'react';
import { AppConfig } from '../../types';
import { FIELDS, FieldSpec } from './constants';

interface UseSettingsDraftOptions {
  isOpen: boolean;
  config: AppConfig | null;
  /** 返回 true 表示保存成功（调用方负责 toast 反馈） */
  onSaveConfig: (key: string, value: string) => Promise<boolean>;
}

const validateField = (field: FieldSpec, value: string): string | null => {
  if (field.required && !value.trim()) return '不能为空';
  return field.validate ? field.validate(value.trim()) : null;
};

/**
 * 设置弹窗草稿编排：初始化 / 脏字段追踪 / 校验 / 逐字段串行保存 / 清空确认。
 * 保存语义（只保存脏字段、逐字段串行 onSaveConfig）与重构前逐字一致。
 */
export function useSettingsDraft({ isOpen, config, onSaveConfig }: UseSettingsDraftOptions) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [savingField, setSavingField] = useState<string | null>(null);
  const [clearTarget, setClearTarget] = useState<FieldSpec | null>(null);

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
  }, [isOpen, config]);

  const isDirty = (key: string) => {
    if (!config) return false;
    const current = (config as any)[key] ?? '';
    return (draft[key] ?? '') !== current;
  };
  const dirtyKeys = Object.keys(draft).filter((k) => isDirty(k));
  const hasUnsaved = dirtyKeys.length > 0;

  /** 编辑字段：更新草稿并清除该字段的错误提示 */
  const setField = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const copy = { ...prev };
      delete copy[key];
      return copy;
    });
  };

  /** 校验全部字段并逐字段串行保存；返回 true 表示保存成功、调用方可关闭弹窗 */
  const handleSave = async (): Promise<boolean> => {
    const nextErrors: Record<string, string> = {};
    FIELDS.forEach((f) => {
      const err = validateField(f, draft[f.key] ?? '');
      if (err) nextErrors[f.key] = err;
    });
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return false;
    }
    setErrors({});

    const targets = [...FIELDS.map((f) => f.key), 'TABLE_STYLE' as const].filter((k) => isDirty(k));
    if (targets.length === 0) return false;

    let allOk = true;
    for (const key of targets) {
      setSavingField(key);
      // 逐字段串行保存是既有语义：避免并发写配置，且让「保存中…」按字段推进
      // eslint-disable-next-line no-await-in-loop
      const ok = await onSaveConfig(key, (draft[key] ?? '').trim());
      if (!ok) allOk = false;
    }
    setSavingField(null);
    return allOk;
  };

  const requestClear = (field: FieldSpec) => {
    setClearTarget(field);
  };

  const cancelClear = () => {
    setClearTarget(null);
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

  return {
    draft,
    errors,
    dirtyKeys,
    hasUnsaved,
    savingField,
    clearTarget,
    isDirty,
    setField,
    handleSave,
    requestClear,
    cancelClear,
    confirmClear,
  };
}
