import React, { useMemo, useRef, useState } from 'react';
import { GripVertical } from 'lucide-react';
import { motion } from 'motion/react';

// Sub-components
import { ReaderToolbar } from './reader/ReaderToolbar';
import { PdfViewer } from './reader/PdfViewer';
import { MarkdownViewer } from './reader/MarkdownViewer';
import { ChatSidebar } from './reader/ChatSidebar';
import { ReaderOutline } from './reader/ReaderOutline';
import { SelectionToolbar } from './reader/SelectionToolbar';
import { buildOutline } from './reader/outline';

import { Document, ViewMode } from '../types';
import { useResizable } from '../hooks/useResizable';
import { useReaderChat } from '../hooks/useReaderChat';
import { useSelectionMenu } from '../hooks/useSelectionMenu';

interface ReaderProps {
  doc: Document;
  onBack: () => void;
  tableStyle?: string;
  onOpenSettings?: () => void;
  onReprocess?: () => void;
  key?: React.Key;
}

const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 400;
/** 分栏模式下 PDF 窗格宽度百分比（默认 / 双击复位） */
const DEFAULT_SPLIT_RATIO = 50;

export const Reader = ({ doc, onBack, tableStyle, onOpenSettings, onReprocess }: ReaderProps) => {
  // .tex/.zip 文档没有 PDF 视图（server 对 /pdf 端点返回 404），默认纯 Markdown
  const [viewMode, setViewMode] = useState<ViewMode>(
    /\.(tex|zip)$/i.test(doc.filename) ? 'markdown' : 'split'
  );
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const markdownRef = useRef<HTMLDivElement>(null);

  const chat = useReaderChat(doc.id);
  const outline = useMemo(() => buildOutline(doc), [doc]);

  // FE-07：三栏拖拽缩放统一走 useResizable（document 级监听，mouseup 移除）
  const left = useResizable(DEFAULT_LEFT_WIDTH, {
    min: 48, max: 600, collapseThreshold: 100,
    onCollapsedChange: setLeftCollapsed, resetValue: DEFAULT_LEFT_WIDTH,
  });
  const right = useResizable(DEFAULT_RIGHT_WIDTH, {
    direction: 'right',
    min: 48, max: 800, collapseThreshold: 100,
    onCollapsedChange: setRightCollapsed, resetValue: DEFAULT_RIGHT_WIDTH,
  });
  // 分栏把手：按中心区宽度换算百分比（clamp 10-90），与左右栏收起态联动
  const split = useResizable(DEFAULT_SPLIT_RATIO, {
    min: 10, max: 90, resetValue: DEFAULT_SPLIT_RATIO,
    computeValue: (event) => {
      const leftPx = leftCollapsed ? 48 : left.value;
      const rightPx = rightCollapsed ? 48 : right.value;
      return ((event.clientX - leftPx) / (window.innerWidth - leftPx - rightPx)) * 100;
    },
  });

  // 划词工具条：引用 → 会话编排（插入引用块 + 展开右栏 + 聚焦输入框）
  const selection = useSelectionMenu(markdownRef, (text) => {
    chat.insertQuote(text);
    setRightCollapsed(false);
    chat.focusChat();
  });

  const handleAnalyze = () => {
    setRightCollapsed(false);
    chat.focusChat();
    chat.prefillDefaultQuestion();
  };

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-slate-100 font-sans">
      {/* Left Sidebar：文档目录（动态生成，UX-05） */}
      <ReaderOutline
        outline={outline}
        collapsed={leftCollapsed}
        width={left.value}
        contentRef={markdownRef}
        onNeedMarkdownView={() => setViewMode('markdown')}
        onToggleCollapsed={() => setLeftCollapsed((prev) => !prev)}
        onResizeStart={left.startResizing}
        onResetWidth={left.reset}
      />

      {/* Main Area */}
      <section className="flex-1 flex flex-col min-w-0 bg-slate-200 overflow-hidden relative z-20">
        <ReaderToolbar
          onBack={onBack}
          viewMode={viewMode}
          setViewMode={setViewMode}
          title={doc.title || doc.filename}
          onAnalyze={handleAnalyze}
        />

        <div className="flex-1 flex overflow-hidden">
          {(viewMode === 'pdf' || viewMode === 'split') && (
            <div
              style={{ width: viewMode === 'split' ? `${split.value}%` : '100%' }}
              className="h-full bg-slate-300 relative"
            >
              <PdfViewer filename={doc.filename} />
            </div>
          )}

          {viewMode === 'split' && (
            <div
              role="separator"
              aria-label="调整 PDF 与文本宽度比例"
              title="拖拽调整比例，双击复位 50%"
              onMouseDown={split.startResizing}
              onDoubleClick={split.reset}
              className="w-1.5 bg-slate-300 hover:bg-indigo-400 cursor-col-resize transition-colors z-40 flex items-center justify-center group"
            >
              <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
            </div>
          )}

          {(viewMode === 'markdown' || viewMode === 'split') && (
            <div
              ref={markdownRef}
              style={{ width: viewMode === 'split' ? `${100 - split.value}%` : '100%' }}
              className="h-full bg-white overflow-y-auto px-8 lg:px-12 py-10 selection:bg-indigo-100"
            >
              <MarkdownViewer
                content={doc.ocr_markdown}
                structuredContent={doc.ocr_structured_json}
                tableStyle={tableStyle}
                isSplitView={viewMode === 'split'}
                onOpenSettings={onOpenSettings}
                onReprocess={onReprocess}
              />
            </div>
          )}
        </div>
      </section>

      {/* Right Sidebar */}
      <motion.aside
        animate={{ width: rightCollapsed ? 48 : right.value }}
        className="shrink-0 bg-slate-50 border-l border-slate-200 relative overflow-hidden flex flex-col z-30 shadow-sm"
      >
        {/* Resize Handle: Right */}
        <div
          role="separator"
          aria-label="调整助手栏宽度"
          title="拖拽调整宽度，双击复位"
          onMouseDown={right.startResizing}
          onDoubleClick={right.reset}
          className="absolute left-0 top-0 bottom-0 w-1.5 bg-slate-200/80 hover:bg-indigo-400 cursor-col-resize z-50 transition-colors flex items-center justify-center group"
        >
          <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
        </div>

        <ChatSidebar
          docId={doc.id}
          collapsed={rightCollapsed}
          setCollapsed={setRightCollapsed}
          chatHistory={chat.chatHistory}
          chatQuery={chat.chatQuery}
          setChatQuery={chat.setChatQuery}
          isTyping={chat.isTyping}
          onSendMessage={chat.sendMessage}
          onClearHistory={chat.clearHistory}
          citeMode={chat.citeMode}
          setCiteMode={chat.setCiteMode}
          focusSignal={chat.focusSignal}
        />
      </motion.aside>

      {/* 划词工具条 */}
      {selection.menu && (
        <SelectionToolbar
          menu={selection.menu}
          onCopy={selection.copySelection}
          onQuote={selection.quoteSelection}
        />
      )}
    </div>
  );
};
