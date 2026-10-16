import React from 'react';

export type EmptyStateTone = 'rose' | 'slate' | 'indigo';

/** 图标圆环底色（图标本体的颜色由调用方在 icon 内自行指定，与 tone 保持成对） */
const TONE_CIRCLE: Record<EmptyStateTone, string> = {
  rose: 'bg-rose-50',
  slate: 'bg-slate-100',
  indigo: 'bg-indigo-50',
};

interface EmptyStateProps {
  /** 图标元素（含尺寸与颜色类，如 <AlertCircle className="w-8 h-8 text-rose-400" />） */
  icon: React.ReactNode;
  tone: EmptyStateTone;
  title?: React.ReactNode;
  description?: React.ReactNode;
  /** 操作区（按钮 / 补充提示），与标题、说明共用统一间距 */
  children?: React.ReactNode;
}

/**
 * 空态 / 错误态统一容器：图标圆环 + 标题 + 说明 + 可选操作区。
 * 用于「检索失败 / 无结果 / 知识库未摄入 / 筛选无结果」等场景，避免容器样式重复。
 */
export const EmptyState = ({ icon, tone, title, description, children }: EmptyStateProps) => (
  <div className="py-20 text-center space-y-4">
    <div className={`w-16 h-16 ${TONE_CIRCLE[tone]} rounded-full flex items-center justify-center mx-auto`}>
      {icon}
    </div>
    {title && <p className="text-slate-700 font-bold">{title}</p>}
    {description && <p className="text-slate-500 text-sm max-w-md mx-auto">{description}</p>}
    {children}
  </div>
);
