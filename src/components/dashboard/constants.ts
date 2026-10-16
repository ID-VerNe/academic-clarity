import type { DocStatus } from '../../utils/docStatus';

/** 仪表盘两种浏览模式（文献库 / 知识库检索） */
export type DashboardMode = 'papers' | 'claims';

/** 文献库排序键 */
export type SortKey = 'added_desc' | 'added_asc' | 'title_asc' | 'year_desc';

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'added_desc', label: '最近导入' },
  { value: 'added_asc', label: '最早导入' },
  { value: 'title_asc', label: '标题 A→Z' },
  { value: 'year_desc', label: '发表年份（新→旧）' },
];

export const STATUS_META: Record<DocStatus, { label: string; badge: string; dot: string; border: string; bar: string }> = {
  completed: {
    label: '完成',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    dot: 'bg-emerald-500',
    border: 'border-emerald-100/60',
    bar: 'bg-emerald-500',
  },
  partial: {
    label: '仅 OCR',
    badge: 'bg-amber-50 text-amber-700 border-amber-100',
    dot: 'bg-amber-500',
    border: 'border-amber-100/60',
    bar: 'bg-amber-400',
  },
  processing: {
    label: '处理中',
    badge: 'bg-indigo-50 text-indigo-700 border-indigo-100',
    dot: 'bg-indigo-500',
    border: 'border-indigo-100',
    bar: 'bg-indigo-500',
  },
  queued: {
    label: '排队中',
    badge: 'bg-slate-100 text-slate-600 border-slate-200',
    dot: 'bg-slate-400',
    border: 'border-slate-200',
    bar: 'bg-slate-400',
  },
  failed: {
    label: '失败',
    badge: 'bg-rose-50 text-rose-700 border-rose-100',
    dot: 'bg-rose-500',
    border: 'border-rose-100',
    bar: 'bg-rose-500',
  },
};

/** Basic Insight 的宽松形状（字段均可选；容错解析后按需取用） */
export interface BasicInsight {
  journal_or_conference?: string;
  date?: string;
  [key: string]: unknown;
}
