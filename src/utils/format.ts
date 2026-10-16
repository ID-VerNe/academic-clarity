/**
 * 展示层格式化工具（纯函数，无 React 依赖）。
 */

/** 处理耗时：'95 秒' / '1 分 35 秒'；非法输入返回空串 */
export const formatElapsed = (seconds: number): string => {
  if (!Number.isFinite(seconds) || seconds < 0) return '';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m} 分 ${s} 秒`;
};

/** 导入日期：zh-CN 短格式；缺失/非法返回 '未知' */
export const formatAddedAt = (value?: string): string => {
  if (!value) return '未知';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '未知';
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' });
};
