import React, { useEffect, useRef } from 'react';
import { Sparkles, Send, Quote } from 'lucide-react';
import { ChatMessage } from '../../types';
import { isImeEnter } from '../../utils/keyboard';

interface ChatPanelProps {
  chatHistory: ChatMessage[];
  chatQuery: string;
  setChatQuery: (query: string) => void;
  isTyping: boolean;
  onSendMessage: () => void;
  citeMode: boolean;
  setCiteMode?: (citeMode: boolean) => void;
  /** 由 ChatSidebar 持有（聚焦信号消费方） */
  inputRef: React.RefObject<HTMLInputElement | null>;
}

/** 对话页：消息列表 + 引用模式开关 + 输入区 */
export const ChatPanel = ({
  chatHistory,
  chatQuery,
  setChatQuery,
  isTyping,
  onSendMessage,
  citeMode,
  setCiteMode,
  inputRef,
}: ChatPanelProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // 新消息 / 输入中自动滚动到底部（UX-20）
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [chatHistory.length, isTyping]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {chatHistory.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-center px-6">
            <Sparkles className="w-8 h-8 text-indigo-300" />
            <p className="text-sm font-bold text-slate-500">针对本文档提问</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              例如：「这篇论文的核心贡献是什么？」「实验设置有哪些局限？」
            </p>
          </div>
        ) : (
          chatHistory.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] p-3 rounded-2xl text-[13px] leading-relaxed shadow-sm whitespace-pre-wrap break-words ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-none'
                    : 'bg-slate-50 border border-slate-100 text-slate-700 rounded-tl-none font-medium'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))
        )}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-slate-50 border border-slate-100 p-3 rounded-2xl rounded-tl-none flex gap-1 items-center shadow-sm">
              <div className="w-1.5 h-1.5 bg-indigo-300 rounded-full animate-bounce" />
              <div className="w-1.5 h-1.5 bg-indigo-300 rounded-full animate-bounce [animation-delay:0.2s]" />
              <div className="w-1.5 h-1.5 bg-indigo-300 rounded-full animate-bounce [animation-delay:0.4s]" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t border-slate-100 bg-white shrink-0">
        {/* Phase 2：引用模式开关（UX-21：给出后果说明） */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <Quote className="w-3 h-3 text-slate-400" />
              <span className="text-xs font-bold text-slate-500">引用模式</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
              {citeMode
                ? '开启：只把知识库中的逐字引文发给 AI，回答可回查锚点'
                : '关闭：把整篇 OCR 全文发给 AI，覆盖面更广'}
            </p>
          </div>
          <button
            aria-label="切换引用模式"
            aria-pressed={citeMode}
            onClick={() => setCiteMode?.(!citeMode)}
            className={`relative w-9 h-5 rounded-full transition-colors shrink-0 mt-0.5 ${
              citeMode ? 'bg-indigo-600' : 'bg-slate-200'
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                citeMode ? 'translate-x-4' : ''
              }`}
            />
          </button>
        </div>
        <div className="relative flex items-center gap-2">
          <input
            ref={inputRef}
            value={chatQuery}
            onChange={(e) => setChatQuery(e.target.value)}
            onKeyDown={(e) => {
              // UX-17：中文输入法选词回车不发送
              if (isImeEnter(e)) onSendMessage();
            }}
            className="w-full text-[13px] rounded-2xl border border-slate-200 bg-slate-50 pl-4 pr-12 py-3.5 text-slate-700 placeholder:text-slate-400 focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400 outline-none transition-all font-medium"
            placeholder={citeMode ? '基于引文提问…' : '针对本文档提问…'}
            aria-label="向文档提问"
            type="text"
          />
          <button
            aria-label="发送"
            onClick={onSendMessage}
            disabled={isTyping || !chatQuery.trim()}
            className="absolute right-2 p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:bg-slate-300 transition-all shadow-lg shadow-indigo-100 active:scale-95"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
