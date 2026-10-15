import React, { useEffect, useState } from 'react';
import { Sparkles, Loader2, BrainCircuit, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { MetadataPanel } from './MetadataPanel';
import { api } from '../../api/client';
import { toast } from '../ui/Toast';

export interface MetadataEntry {
  id: number;
  label: string;
  content_json: string;
  created_at: string;
}

export interface InsightPanelData {
  metadataList: MetadataEntry[];
  isExtracting: boolean;
  showExtractForm: boolean;
  customLabel: string;
  customPrompt: string;
  openExtractForm: () => void;
  closeExtractForm: () => void;
  setCustomLabel: (value: string) => void;
  setCustomPrompt: (value: string) => void;
  runExtraction: () => void;
  refresh: () => void;
}

/** 洞察数据编排：元数据拉取 + 「立即提取」（仅本文档，不落维度库） */
export const useInsightPanel = (
  docId: number,
  collapsed: boolean,
  onExtracted: () => void
): InsightPanelData => {
  const [metadataList, setMetadataList] = useState<MetadataEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [showExtractForm, setShowExtractForm] = useState(false);
  const [customLabel, setCustomLabel] = useState('');
  const [customPrompt, setCustomPrompt] = useState('');

  const refresh = async () => {
    try {
      const data = await api.getMetadata(docId);
      setMetadataList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to fetch metadata', e);
    }
  };

  useEffect(() => {
    if (!collapsed) refresh();
  }, [docId, collapsed]);

  const runExtraction = async () => {
    if (!customLabel.trim() || !customPrompt.trim()) {
      toast.error('请填写维度名称与提取提示词');
      return;
    }
    setIsExtracting(true);
    try {
      await api.extractMetadata(docId, customLabel.trim(), customPrompt.trim());
      await refresh();
      setShowExtractForm(false);
      setCustomLabel('');
      setCustomPrompt('');
      onExtracted();
      toast.success('提取完成，结果已加入洞察列表');
    } catch (e: any) {
      console.error('Extraction failed', e);
      toast.error(`提取失败：${e?.message || '请检查后端服务与 API 配置'}`);
    } finally {
      setIsExtracting(false);
    }
  };

  return {
    metadataList,
    isExtracting,
    showExtractForm,
    customLabel,
    customPrompt,
    openExtractForm: () => setShowExtractForm(true),
    closeExtractForm: () => setShowExtractForm(false),
    setCustomLabel,
    setCustomPrompt,
    runExtraction,
    refresh,
  };
};

interface InsightPanelProps {
  docId: number;
  data: InsightPanelData;
}

/** 洞察页：自定义提取表单 + 元数据面板列表（数据由 useInsightPanel 提供） */
export const InsightPanel = ({ docId, data }: InsightPanelProps) => {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
      <AnimatePresence>
        {data.showExtractForm && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="p-4 bg-white rounded-2xl border-2 border-indigo-100 shadow-lg shadow-indigo-100/50 space-y-3 relative"
          >
            <button
              onClick={data.closeExtractForm}
              aria-label="关闭提取表单"
              className="absolute top-2 right-2 text-slate-300 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
            <h5 className="text-xs font-bold text-indigo-600">立即提取（仅本文档）</h5>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              与「设置 → 提取维度」不同：这里只对当前文档执行一次提取，不会保存为可复用维度。
            </p>
            <input
              value={data.customLabel}
              onChange={(e) => data.setCustomLabel(e.target.value)}
              placeholder="维度名称，如：方法论"
              aria-label="维度名称"
              className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-indigo-300"
            />
            <textarea
              value={data.customPrompt}
              onChange={(e) => data.setCustomPrompt(e.target.value)}
              placeholder="提取提示词，如：提取主要实验数据点…"
              aria-label="提取提示词"
              className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-20 focus:outline-none focus:border-indigo-300 resize-none"
            />
            <button
              onClick={data.runExtraction}
              disabled={data.isExtracting}
              className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 disabled:bg-slate-300"
            >
              {data.isExtracting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {data.isExtracting ? '提取中…' : '开始提取'}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {data.metadataList.map((meta) => (
        <MetadataPanel
          key={meta.id}
          data={meta.content_json}
          label={meta.label}
          docId={docId}
          onVerified={data.refresh}
        />
      ))}

      {data.metadataList.length === 0 && !data.isExtracting && !data.showExtractForm && (
        <div className="py-12 text-center">
          <BrainCircuit className="w-10 h-10 mx-auto mb-3 text-slate-300" />
          <p className="text-sm font-bold text-slate-500">暂无洞察</p>
          <p className="text-xs text-slate-400 mt-1 max-w-[220px] mx-auto leading-relaxed">
            文档完成 OCR 后会自动生成 Basic Insight；也可以点右上角「+」立即提取自定义维度。
          </p>
        </div>
      )}
    </div>
  );
};
