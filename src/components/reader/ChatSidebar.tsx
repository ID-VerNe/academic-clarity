import React, { useState, useEffect, useRef } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Send,
  Plus,
  Loader2,
  BrainCircuit,
  X,
  Eraser,
  MessageSquare,
  Quote
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { MetadataPanel } from './MetadataPanel';
import { api } from '../../api/client';
import { toast } from '../ui/Toast';

interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
}

interface MetadataEntry {
  id: number;
  label: string;
  content_json: string;
  created_at: string;
}

interface ChatSidebarProps {
  docId: number;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  chatHistory: ChatMessage[];
  chatQuery: string;
  setChatQuery: (query: string) => void;
  isTyping: boolean;
  onSendMessage: () => void;
  onClearHistory: () => void;
  /** 递增信号：切换到「对话」页并聚焦输入框（AI 分析 / 引用到提问） */
  focusSignal?: number;
  /** Phase 2 引用模式：开 → 只把知识库检索到的逐字引文喂给 LLM */
  citeMode?: boolean;
  setCiteMode?: (citeMode: boolean) => void;
}

type PanelTab = 'chat' | 'insight';

export const ChatSidebar = ({
  docId,
  collapsed,
  setCollapsed,
  chatHistory,
  chatQuery,
  setChatQuery,
  isTyping,
  onSendMessage,
  onClearHistory,
  focusSignal,
  citeMode = false,
  setCiteMode
}: ChatSidebarProps) => {
  const [metadataList, setMetadataList] = useState<MetadataEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [showExtractForm, setShowExtractForm] = useState(false);
  const [customLabel, setCustomLabel] = useState('');
  const [customPrompt, setCustomPrompt] = useState('');
  const [tab, setTab] = useState<PanelTab>('chat');
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pendingFocus = useRef(false);

  const fetchMetadata = async () => {
    try {
      const data = await api.getMetadata(docId);
      setMetadataList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to fetch metadata', e);
    }
  };

  useEffect(() => {
    if (!collapsed) fetchMetadata();
  }, [docId, collapsed]);

  // 新消息 / 输入中自动滚动到底部（UX-20）
  useEffect(() => {
    if (collapsed || tab !== 'chat') return;
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [chatHistory.length, isTyping, collapsed, tab]);

  // 外部聚焦信号：切到对话页并聚焦输入框
  useEffect(() => {
    if (!focusSignal) return;
    pendingFocus.current = true;
    setTab('chat');
  }, [focusSignal]);

  useEffect(() => {
    if (tab === 'chat' && !collapsed && pendingFocus.current) {
      pendingFocus.current = false;
      inputRef.current?.focus();
    }
  }, [tab, collapsed, focusSignal]);

  const handleRunExtraction = async () => {
    if (!customLabel.trim() || !customPrompt.trim()) {
      toast.error('请填写维度名称与提取提示词');
      return;
    }
    setIsExtracting(true);
    try {
      await api.extractMetadata(docId, customLabel.trim(), customPrompt.trim());
      await fetchMetadata();
      setShowExtractForm(false);
      setCustomLabel('');
      setCustomPrompt('');
      setTab('insight');
      toast.success('提取完成，结果已加入洞察列表');
    } catch (e: any) {
      console.error('Extraction failed', e);
      toast.error(`提取失败：${e?.message || '请检查后端服务与 API 配置'}`);
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <motion.aside
      animate={{ width: collapsed ? 48 : 380 }}
      className="shrink-0 bg-slate-50 relative flex flex-col overflow-hidden z-30 border-l border-slate-200 shadow-xl"
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-200 flex items-center justify-between overflow-hidden bg-white/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2 min-w-0">
          <button
            aria-label={collapsed ? '展开右侧栏' : '收起右侧栏'}
            title={collapsed ? '展开右侧栏' : '收起右侧栏'}
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors shrink-0"
          >
            {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
          {!collapsed && (
            <span className="text-xs font-bold text-slate-500 truncate">研究助手</span>
          )}
        </div>
        {!collapsed && (
          <div className="flex items-center gap-1.5 shrink-0">
            {tab === 'chat' && chatHistory.length > 0 && (
              <button
                aria-label="清空对话"
                title="清空对话"
                onClick={onClearHistory}
                className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
              >
                <Eraser className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              aria-label="新增提取维度并立即提取"
              title="新增提取维度并立即提取"
              onClick={() => {
                setShowExtractForm(true);
                setTab('insight');
              }}
              className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 transition-colors border border-indigo-100"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {collapsed ? (
        <div className="flex flex-col items-center py-8 gap-6 text-slate-300">
          <Sparkles className="w-4 h-4" />
          <BrainCircuit className="w-4 h-4" />
        </div>
      ) : (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tab 切换（UX-46：把两个滚动区合并为一个，避免滚轮迷失） */}
          <div className="px-3 pt-3 flex gap-1.5 shrink-0">
            {(
              [
                { key: 'chat' as PanelTab, label: '对话', icon: <MessageSquare className="w-3.5 h-3.5" /> },
                {
                  key: 'insight' as PanelTab,
                  label: `洞察${metadataList.length ? ` (${metadataList.length})` : ''}`,
                  icon: <BrainCircuit className="w-3.5 h-3.5" />,
                },
              ]
            ).map((item) => (
              <button
                key={item.key}
                onClick={() => setTab(item.key)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold transition-colors ${
                  tab === item.key ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-200/60'
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </div>

          {tab === 'insight' ? (
            <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
              <AnimatePresence>
                {showExtractForm && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="p-4 bg-white rounded-2xl border-2 border-indigo-100 shadow-lg shadow-indigo-100/50 space-y-3 relative"
                  >
                    <button
                      onClick={() => setShowExtractForm(false)}
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
                      value={customLabel}
                      onChange={(e) => setCustomLabel(e.target.value)}
                      placeholder="维度名称，如：方法论"
                      aria-label="维度名称"
                      className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-indigo-300"
                    />
                    <textarea
                      value={customPrompt}
                      onChange={(e) => setCustomPrompt(e.target.value)}
                      placeholder="提取提示词，如：提取主要实验数据点…"
                      aria-label="提取提示词"
                      className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50 h-20 focus:outline-none focus:border-indigo-300 resize-none"
                    />
                    <button
                      onClick={handleRunExtraction}
                      disabled={isExtracting}
                      className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 disabled:bg-slate-300"
                    >
                      {isExtracting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                      {isExtracting ? '提取中…' : '开始提取'}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {metadataList.map((meta) => (
                <MetadataPanel
                  key={meta.id}
                  data={meta.content_json}
                  label={meta.label}
                  docId={docId}
                  onVerified={fetchMetadata}
                />
              ))}

              {metadataList.length === 0 && !isExtracting && !showExtractForm && (
                <div className="py-12 text-center">
                  <BrainCircuit className="w-10 h-10 mx-auto mb-3 text-slate-300" />
                  <p className="text-sm font-bold text-slate-500">暂无洞察</p>
                  <p className="text-xs text-slate-400 mt-1 max-w-[220px] mx-auto leading-relaxed">
                    文档完成 OCR 后会自动生成 Basic Insight；也可以点右上角「+」立即提取自定义维度。
                  </p>
                </div>
              )}
            </div>
          ) : (
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
                      if (e.key === 'Enter' && !e.nativeEvent.isComposing) onSendMessage();
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
          )}
        </div>
      )}
    </motion.aside>
  );
};
