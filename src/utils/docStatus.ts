import type { Document } from '../types';

/** 文献卡片状态：由 ocr_status + markdown + insight 三字段联合判定 */
export type DocStatus = 'completed' | 'partial' | 'processing' | 'queued' | 'failed';

export const getDocStatus = (doc: Document): DocStatus => {
  if (doc.ocr_status === 'processing') return 'processing';
  if (doc.ocr_status === 'pending') return 'queued';
  if (doc.ocr_status === 'failed') return 'failed';
  const hasMarkdown = !!doc.ocr_markdown && doc.ocr_markdown.length > 10;
  if (!hasMarkdown) return 'failed';
  return doc.basic_insight_json ? 'completed' : 'partial';
};
