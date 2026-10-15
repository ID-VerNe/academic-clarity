import { Document } from '../../types';

export interface OutlineItem {
  text: string;
  level: number;
}

/** 目录最多展示的条目数（防止超长文档压垮侧栏） */
export const MAX_OUTLINE_ITEMS = 80;

/**
 * 从文档结构生成目录（UX-05）：
 * 优先用 OCR 结构化 blocks 的 title/subtitle；不足 2 条时回退 markdown 标题（#/##/###）。
 */
export const buildOutline = (doc: Document): OutlineItem[] => {
  const blocks = doc.ocr_structured_json?.blocks || [];
  const fromBlocks = blocks
    .filter((b) => b.type === 'title' || b.type === 'subtitle')
    .map((b) => ({ text: b.text, level: b.type === 'title' ? 1 : 2 }));
  if (fromBlocks.length > 1) return fromBlocks.slice(0, MAX_OUTLINE_ITEMS);

  const headings: OutlineItem[] = [];
  (doc.ocr_markdown || '').split('\n').forEach((line) => {
    const m = /^(#{1,3})\s+(.+)$/.exec(line.trim());
    if (m) headings.push({ text: m[2].trim(), level: m[1].length });
  });
  return headings.slice(0, MAX_OUTLINE_ITEMS);
};
