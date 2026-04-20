import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import { FileSearch, ShieldAlert } from 'lucide-react';
import 'katex/dist/katex.min.css';

interface MarkdownViewerProps {
  content?: string;
  tableStyle?: string;
  isSplitView: boolean;
}

export const MarkdownViewer = ({ content, tableStyle, isSplitView }: MarkdownViewerProps) => {
  if (!content) {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-6 py-20 px-10 text-center bg-slate-50/30">
        <div className="p-5 bg-white rounded-3xl shadow-sm border border-slate-100">
           <FileSearch className="w-10 h-10 text-indigo-400" />
        </div>
        <div>
          <p className="text-sm font-black text-slate-800 uppercase tracking-widest">No Intelligence Data</p>
          <p className="text-xs text-slate-400 mt-2 max-w-[200px] leading-relaxed mx-auto">Please initialize DeepSeek-OCR to reconstruct the document structure.</p>
        </div>
      </div>
    );
  }

  // 简单的 XSS 过滤逻辑：移除 script 标签
  const sanitizedContent = content.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "[Script Blocked]");

  return (
    <div className={`mx-auto ${isSplitView ? 'max-w-full' : 'max-w-[850px]'} animate-in fade-in duration-700`}>
      {/* Security Banner if HTML is complex */}
      {content.includes('<') && (
        <div className="mb-8 flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-100 rounded-xl text-[10px] text-amber-700 font-bold">
           <ShieldAlert className="w-3 h-3" />
           <span>Rich content rendering enabled. Standard sanitization applied.</span>
        </div>
      )}

      <article className="prose prose-slate prose-sm lg:prose-base max-w-none 
        prose-headings:font-serif prose-headings:text-slate-900 prose-headings:tracking-tight
        prose-h1:text-3xl prose-h1:mb-10 prose-h1:pb-6 prose-h1:border-b prose-h1:border-slate-100
        prose-p:text-slate-600 prose-p:leading-[1.8] prose-p:text-[15px] prose-p:mb-6
        prose-strong:text-slate-900 prose-strong:font-bold
        prose-blockquote:border-l-4 prose-blockquote:border-indigo-500 prose-blockquote:bg-indigo-50/50 prose-blockquote:py-2 prose-blockquote:px-6 prose-blockquote:rounded-r-xl
        prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none
        prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline
      ">
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeRaw, rehypeKatex]}
          components={{
            img: ({node, ...props}) => (
              <div className="my-12 flex flex-col items-center gap-3 group">
                <img {...props} className="rounded-2xl shadow-xl border border-slate-100 group-hover:scale-[1.01] transition-transform duration-500" alt="" />
                <span className="text-[10px] text-slate-400 italic font-medium uppercase tracking-widest">Extracted Figure</span>
              </div>
            ),
            table: ({node, ...props}) => (
              <div className="overflow-x-auto my-12 rounded-2xl border border-slate-200 shadow-sm bg-white p-1">
                <table {...props} className={`w-full text-[13px] text-left border-collapse ${
                  tableStyle === 'three-line' ? 'border-t-2 border-b-2 border-slate-900' : ''
                }`} />
              </div>
            ),
            th: ({node, ...props}) => (
              <th {...props} className="bg-slate-50/80 px-4 py-3 font-bold text-slate-900 border-b border-slate-100 uppercase text-[10px] tracking-widest" />
            ),
            td: ({node, ...props}) => (
              <td {...props} className="px-4 py-3 border-b border-slate-50 text-slate-600" />
            )
          }}
        >
          {sanitizedContent}
        </ReactMarkdown>
      </article>

      <div className="h-40 flex items-center justify-center mt-20 border-t border-slate-100 opacity-20">
         <div className="w-1 h-1 rounded-full bg-slate-400 mx-1" />
         <div className="w-1 h-1 rounded-full bg-slate-400 mx-1" />
         <div className="w-1 h-1 rounded-full bg-slate-400 mx-1" />
      </div>
    </div>
  );
};
