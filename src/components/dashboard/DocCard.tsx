import React from 'react';
import {
  AlertCircle,
  BookOpen,
  Building2,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from 'lucide-react';
import { motion } from 'motion/react';
import { Document } from '../../types';
import { getDocStatus } from '../../utils/docStatus';
import { safeParseJson } from '../../utils/json';
import { formatAddedAt } from '../../utils/format';
import { BasicInsight, STATUS_META } from './constants';

interface DocCardProps {
  doc: Document;
  onSelectDoc: (doc: Document) => void;
  onDelete: (doc: Document) => void;
  onReprocess: (id: number) => void;
}

/** 文献库卡片：状态徽标 + 洞察摘要 + 阅读 / 删除 / 重新处理 */
export const DocCard = ({ doc, onSelectDoc, onDelete, onReprocess }: DocCardProps) => {
  const status = getDocStatus(doc);
  const meta = STATUS_META[status];
  const insight = safeParseJson<BasicInsight>(doc.basic_insight_json);
  const displayTitle = doc.title || doc.filename;

  return (
    <motion.div
      whileHover={{ y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
      className={`bg-white border-2 rounded-3xl p-6 flex flex-col justify-between hover:border-indigo-200 transition-all duration-300 group relative overflow-hidden cursor-pointer shadow-sm ${meta.border}`}
      onClick={() => onSelectDoc(doc)}
    >
      <div
        className={`absolute top-0 left-0 w-full h-1 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500 ${meta.bar}`}
      />

      <div>
        <div className="flex items-center justify-between mb-5 gap-2">
          <div
            className={`px-2.5 py-1 rounded-full text-[11px] font-bold border flex items-center gap-1.5 ${meta.badge}`}
          >
            {status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
            {status === 'partial' && <ShieldAlert className="w-3 h-3" />}
            {status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
            {status === 'queued' && <Clock className="w-3 h-3" />}
            {status === 'failed' && <AlertCircle className="w-3 h-3" />}
            {meta.label}
          </div>
          <div className="flex items-center gap-1">
            {(status === 'failed' || status === 'partial') && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onReprocess(doc.id);
                }}
                aria-label={`重新处理 ${displayTitle}`}
                title="重新处理（重跑 OCR 与洞察提取）"
                className="p-1.5 hover:bg-indigo-50 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        <h3 className="font-serif text-lg text-slate-800 leading-snug line-clamp-2 group-hover:text-indigo-600 transition-colors mb-2">
          {displayTitle}
        </h3>

        {insight?.journal_or_conference && (
          <div className="flex items-center gap-2 mb-2">
            <Building2 className="w-3 h-3 text-indigo-400 shrink-0" />
            <span className="text-xs font-medium text-slate-500 truncate">
              {insight.journal_or_conference}
            </span>
          </div>
        )}

        <div className="flex items-center gap-2 text-slate-400">
          <FileText className="w-3 h-3 shrink-0" />
          <p className="text-xs font-medium truncate italic max-w-[150px]">{doc.filename}</p>
        </div>
      </div>

      <div className="flex items-end justify-between mt-8 gap-3">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-baseline gap-1.5">
            <span className="text-[11px] text-slate-400 shrink-0">发表</span>
            <span className="text-xs text-slate-600 font-medium truncate">
              {insight?.date || '未知'}
            </span>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-[11px] text-slate-400 shrink-0">导入</span>
            <span className="text-xs text-slate-600 font-medium truncate">
              {formatAddedAt(doc.added_at)}
            </span>
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelectDoc(doc);
            }}
            aria-label={`阅读 ${displayTitle}`}
            title="阅读"
            className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all duration-200"
          >
            <BookOpen className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(doc);
            }}
            aria-label={`删除 ${displayTitle}`}
            title="删除"
            className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-all duration-200"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </motion.div>
  );
};
