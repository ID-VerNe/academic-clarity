import React from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import { FileSearch, ShieldCheck, Settings, RefreshCw } from 'lucide-react';
import type { OCRStructuredContent } from '../../types';
import 'katex/dist/katex.min.css';

interface MarkdownViewerProps {
  content?: string;
  structuredContent?: OCRStructuredContent;
  tableStyle?: string;
  isSplitView: boolean;
  /** 空态引导：去设置配置 OCR（UX-25） */
  onOpenSettings?: () => void;
  /** 空态引导：重新处理（UX-25） */
  onReprocess?: () => void;
}

export const MarkdownViewer = ({
  content,
  structuredContent,
  tableStyle,
  isSplitView,
  onOpenSettings,
  onReprocess,
}: MarkdownViewerProps) => {
  const hasStructuredBlocks = Boolean(structuredContent?.blocks?.length);
  const sanitizeMarkdown = (value: string) =>
    value.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '[Script Blocked]');
  const allowDataImageUrl = (url: string) =>
    url.startsWith('data:image/') ? url : defaultUrlTransform(url);

  const markdownComponents = {
    img: ({ node, ...props }) => (
      <img {...props} className="my-8 rounded-2xl shadow-xl border border-slate-100 max-w-full" alt="" />
    ),
    table: ({ node, ...props }) => (
      <div className="overflow-x-auto my-12 rounded-2xl border border-slate-200 shadow-sm bg-white p-1">
        <table
          {...props}
          className={`w-full text-[13px] text-left border-collapse ${
            tableStyle === 'three-line' ? 'border-t-2 border-b-2 border-slate-900' : ''
          }`}
        />
      </div>
    ),
    th: ({ node, ...props }) => (
      <th
        {...props}
        className="bg-slate-50/80 px-4 py-3 font-bold text-slate-900 border-b border-slate-100 text-[11px] tracking-wide"
      />
    ),
    td: ({ node, ...props }) => <td {...props} className="px-4 py-3 border-b border-slate-50 text-slate-600" />,
  };

  if (!content && !hasStructuredBlocks) {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-6 py-20 px-10 text-center bg-slate-50/30">
        <div className="p-5 bg-white rounded-3xl shadow-sm border border-slate-100">
          <FileSearch className="w-10 h-10 text-indigo-400" />
        </div>
        <div className="max-w-sm">
          <p className="text-sm font-bold text-slate-800">暂无识别文本</p>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            这篇文档还没有 OCR 结果。请确认已在设置中配置 OCR API Key 与模型，然后重新处理。
          </p>
        </div>
        <div className="flex items-center gap-3">
          {onReprocess && (
            <button
              onClick={onReprocess}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              重新处理
            </button>
          )}
          {onOpenSettings && (
            <button
              onClick={onOpenSettings}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors"
            >
              <Settings className="w-3.5 h-3.5 text-indigo-600" />
              去设置
            </button>
          )}
        </div>
      </div>
    );
  }

  // 简单的 XSS 过滤逻辑：移除 script 标签
  const sanitizedContent = sanitizeMarkdown(content || '');
  const hasRichContent =
    Boolean(content?.includes('<')) || Boolean(structuredContent?.blocks?.some((block) => block.text.includes('<')));

  return (
    <div className={`mx-auto ${isSplitView ? 'max-w-full' : 'max-w-[850px]'} animate-in fade-in duration-700`}>
      {/* 富文本提示（UX-43：用户可读的措辞，替代开发者文案） */}
      {hasRichContent && (
        <div className="mb-8 flex items-center gap-2 px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-[11px] text-slate-500">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
          <span>本文档含富文本内容，已做安全过滤（脚本与外部链接已处理）</span>
        </div>
      )}

      {hasStructuredBlocks ? (
        <article className="max-w-none space-y-6">
          {structuredContent!.blocks.map((block, index) => {
            if (block.type === 'title') {
              return (
                <h1
                  key={index}
                  className="font-serif text-3xl text-slate-900 tracking-tight mb-8 pb-6 border-b border-slate-100"
                >
                  {block.text}
                </h1>
              );
            }
            if (block.type === 'subtitle') {
              return (
                <h2 key={index} className="font-serif text-xl text-slate-800 tracking-tight mt-8 mb-4">
                  {block.text}
                </h2>
              );
            }
            return (
              <div
                key={index}
                className="prose prose-slate prose-sm lg:prose-base max-w-none prose-p:text-slate-600 prose-p:leading-[1.8] prose-p:text-[15px] prose-p:mb-6 prose-strong:text-slate-900 prose-strong:font-bold prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none"
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeRaw, rehypeKatex]}
                  components={markdownComponents}
                  urlTransform={allowDataImageUrl}
                >
                  {sanitizeMarkdown(block.text)}
                </ReactMarkdown>
              </div>
            );
          })}
        </article>
      ) : (
        <article
          className="prose prose-slate prose-sm lg:prose-base max-w-none 
          prose-headings:font-serif prose-headings:text-slate-900 prose-headings:tracking-tight
          prose-h1:text-3xl prose-h1:mb-10 prose-h1:pb-6 prose-h1:border-b prose-h1:border-slate-100
          prose-p:text-slate-600 prose-p:leading-[1.8] prose-p:text-[15px] prose-p:mb-6
          prose-strong:text-slate-900 prose-strong:font-bold
          prose-blockquote:border-l-4 prose-blockquote:border-indigo-500 prose-blockquote:bg-indigo-50/50 prose-blockquote:py-2 prose-blockquote:px-6 prose-blockquote:rounded-r-xl
          prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none
          prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline
        "
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeRaw, rehypeKatex]}
            components={markdownComponents}
            urlTransform={allowDataImageUrl}
          >
            {sanitizedContent}
          </ReactMarkdown>
        </article>
      )}

      <div className="h-40 flex items-center justify-center mt-20 border-t border-slate-100 opacity-20">
        <div className="w-1 h-1 rounded-full bg-slate-400 mx-1" />
        <div className="w-1 h-1 rounded-full bg-slate-400 mx-1" />
        <div className="w-1 h-1 rounded-full bg-slate-400 mx-1" />
      </div>
    </div>
  );
};
