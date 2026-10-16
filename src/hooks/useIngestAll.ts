import { useState } from 'react';
import { Document } from '../types';
import { api } from '../api/client';
import { toast } from '../components/ui/Toast';

/** 可摄入判定：已完成 OCR 且已有 Basic Insight */
const isIngestible = (doc: Document) => doc.ocr_status === 'completed' && !!doc.basic_insight_json;

/**
 * 批量摄入：把已完成 OCR + Basic Insight 的文档写入知识库（幂等）。
 * 暴露 ingesting / ingestedCount / ingestibleCount 供面板渲染。
 */
export const useIngestAll = (docs: Document[]) => {
  const [ingesting, setIngesting] = useState(false);
  const [ingestedCount, setIngestedCount] = useState<number | null>(null);

  const ingestibleCount = docs.filter(isIngestible).length;

  const ingestAll = async () => {
    const targets = docs.filter(isIngestible);
    if (targets.length === 0) {
      toast.info('没有可摄入的文献：需要先完成 OCR 与 Basic Insight');
      return;
    }
    setIngesting(true);
    try {
      for (const d of targets) {
        await api.ingestKnowledge(d.id);
      }
      setIngestedCount(targets.length);
      toast.success(`已摄入 ${targets.length} 篇文献，可以开始检索`);
    } catch (e) {
      console.error('Knowledge ingest failed', e);
      toast.error('摄入失败：无法连接后端服务，请稍后重试。');
    } finally {
      setIngesting(false);
    }
  };

  return { ingesting, ingestedCount, ingestibleCount, ingestAll };
};
