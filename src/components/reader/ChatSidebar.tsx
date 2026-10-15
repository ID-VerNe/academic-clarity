import React, { useState, useEffect, useRef } from 'react';
import { ChevronLeft, ChevronRight, Sparkles, Plus, BrainCircuit, Eraser, MessageSquare } from 'lucide-react';
import { motion } from 'motion/react';
import { InsightPanel, useInsightPanel } from './InsightPanel';
import { ChatPanel } from './ChatPanel';
import { ChatMessage } from '../../types';

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

/** 右栏容器：头部 / 标签页编排 + 聚焦信号消费；对话与洞察分别由 ChatPanel / InsightPanel 渲染 */
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
  const [tab, setTab] = useState<PanelTab>('chat');
  const inputRef = useRef<HTMLInputElement>(null);
  const pendingFocus = useRef(false);
  const insight = useInsightPanel(docId, collapsed, () => setTab('insight'));

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
                insight.openExtractForm();
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
                  label: `洞察${insight.metadataList.length ? ` (${insight.metadataList.length})` : ''}`,
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
            <InsightPanel docId={docId} data={insight} />
          ) : (
            <ChatPanel
              chatHistory={chatHistory}
              chatQuery={chatQuery}
              setChatQuery={setChatQuery}
              isTyping={isTyping}
              onSendMessage={onSendMessage}
              citeMode={citeMode}
              setCiteMode={setCiteMode}
              inputRef={inputRef}
            />
          )}
        </div>
      )}
    </motion.aside>
  );
};
