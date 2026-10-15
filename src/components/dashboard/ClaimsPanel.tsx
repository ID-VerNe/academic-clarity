import React from 'react';
import { AlertCircle, Quote, RotateCcw, Search, X } from 'lucide-react';
import { motion } from 'motion/react';
import { Document } from '../../types';
import { useClaimsSearch } from '../../hooks/useClaimsSearch';
import { useIngestAll } from '../../hooks/useIngestAll';
import { EmptyState } from '../ui/EmptyState';
import { Button } from '../ui/Button';
import { isImeEnter } from '../../utils/keyboard';

// ── 检索条（仅 Claims 模式） ─────────────────────────────────

interface ClaimsToolbarProps {
  /** useClaimsSearch 的返回值 */
  claims: ReturnType<typeof useClaimsSearch>;
}

/** Phase 2：Knowledge Claims 检索工具条 */
export const ClaimsToolbar = ({ claims }: ClaimsToolbarProps) => {
  const { query, setQuery, search, clear, loading } = claims;

  return (
    <div className="bg-white border border-slate-200 rounded-3xl p-3 shadow-sm flex flex-wrap items-center gap-4">
      <div className="flex-1 min-w-[260px] relative group">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
        <input
          type="text"
          placeholder="在知识库中检索 claim（概念 + 逐字引文）…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (isImeEnter(e)) search();
          }}
          aria-label="检索知识库 claim"
          className="w-full pl-11 pr-10 py-2.5 bg-slate-50 border-none rounded-2xl text-sm focus:ring-2 focus:ring-indigo-100 transition-all outline-none"
        />
        {query && (
          <button
            onClick={clear}
            aria-label="清空检索"
            className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
      <Button
        icon={<Search className="w-4 h-4" />}
        loading={loading}
        disabled={!query.trim()}
        onClick={search}
        className="px-5 py-2.5 shadow-lg shadow-indigo-100"
      >
        检索
      </Button>
    </div>
  );
};

// ── 四种结果态（错误 / 无结果 / 结果网格 / 知识库引导） ──────

interface ClaimsPanelProps {
  docs: Document[];
  onSelectDoc: (doc: Document) => void;
  /** useClaimsSearch 的返回值 */
  claims: ReturnType<typeof useClaimsSearch>;
  /** useIngestAll 的返回值 */
  ingest: ReturnType<typeof useIngestAll>;
}

/** Phase 2：Claims 检索结果面板 */
export const ClaimsPanel = ({ docs, onSelectDoc, claims, ingest }: ClaimsPanelProps) => {
  const { query, results, searched, error, retry } = claims;
  const { ingesting, ingestedCount, ingestibleCount, ingestAll } = ingest;

  if (error) {
    return (
      <EmptyState
        tone="rose"
        icon={<AlertCircle className="w-8 h-8 text-rose-400" />}
        title="检索失败"
        description={error}
      >
        <button
          onClick={retry}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          重试
        </button>
      </EmptyState>
    );
  }

  if (searched && results.length === 0) {
    return (
      <EmptyState
        tone="slate"
        icon={<Search className="w-8 h-8 text-slate-300" />}
        title={`没有匹配「${query}」的 claim`}
        description="知识库检索的是 claim 文本（概念 + 引文），不是 OCR 原文。换个关键词，或先摄入更多文献。"
      />
    );
  }

  if (results.length > 0) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {results.map((c) => {
          const targetDoc = docs.find((d) => d.id === c.doc_id);
          return (
            <motion.div
              key={c.claim_id}
              whileHover={targetDoc ? { y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' } : undefined}
              onClick={() => targetDoc && onSelectDoc(targetDoc)}
              className={`bg-white border-2 border-slate-100 rounded-3xl p-6 flex flex-col gap-3 transition-all duration-300 group shadow-sm ${
                targetDoc ? 'hover:border-indigo-200 cursor-pointer' : 'opacity-60'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wide bg-indigo-50 text-indigo-700 border border-indigo-100">
                  {c.concept}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${
                    c.prompt_id.endsWith('~section')
                      ? 'bg-amber-50 text-amber-700 border-amber-100'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-100'
                  }`}
                  title={c.prompt_id.endsWith('~section') ? '章节级转述（锚指向真实段落）' : '段落级逐字引文'}
                >
                  {c.prompt_id.endsWith('~section') ? '章节转述' : '逐字引文'}
                </span>
              </div>
              <p className="text-[13px] leading-relaxed text-slate-700 font-medium">{c.quote}</p>
              <div className="mt-auto pt-3 border-t border-slate-100 flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-bold text-slate-500 truncate">{c.title || c.paper_id || '未知论文'}</p>
                  {c.heading_path && <p className="text-[11px] text-slate-400 truncate">{c.heading_path}</p>}
                </div>
                {targetDoc && (
                  <span className="text-[11px] font-bold text-indigo-600 shrink-0 ml-2">打开原文 →</span>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    );
  }

  return (
    <EmptyState
      tone="indigo"
      icon={<Quote className="w-8 h-8 text-indigo-300" />}
      title="知识库"
      description="检索跨论文的结构化 claim（概念 + 逐字引文 + 可解析锚）。先摄入已完成 OCR 与 Basic Insight 的文献，再检索。"
    >
      {ingestedCount !== null && (
        <p className="text-emerald-600 text-xs font-bold">已摄入 {ingestedCount} 篇文献，在上方检索试试。</p>
      )}
      <Button
        icon={<Quote className="w-4 h-4" />}
        loading={ingesting}
        disabled={ingestibleCount === 0}
        onClick={ingestAll}
        className="px-5 py-2.5 shadow-lg shadow-indigo-100"
      >
        {ingesting ? '摄入中…' : `摄入 ${ingestibleCount} 篇文献`}
      </Button>
      {ingestibleCount === 0 && (
        <p className="text-slate-400 text-xs">暂无可摄入的文献：需要先完成 OCR 与 Basic Insight。</p>
      )}
    </EmptyState>
  );
};
