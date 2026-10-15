import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { ChevronLeft, ChevronRight, FileText, GripVertical, Copy, Quote, ListTree } from 'lucide-react';
import { motion } from 'motion/react';

// Sub-components
import { ReaderToolbar } from './reader/ReaderToolbar';
import { PdfViewer } from './reader/PdfViewer';
import { MarkdownViewer } from './reader/MarkdownViewer';
import { ChatSidebar } from './reader/ChatSidebar';
import { api } from '../api/client';
import { toast } from './ui/Toast';

import { Document } from '../types';

interface ReaderProps {
  doc: Document;
  onBack: () => void;
  tableStyle?: string;
  onOpenSettings?: () => void;
  onReprocess?: () => void;
  key?: React.Key;
}

interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
}

interface OutlineItem {
  text: string;
  level: number;
}

const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 400;
const MAX_HISTORY = 60;

const buildOutline = (doc: Document): OutlineItem[] => {
  const blocks = doc.ocr_structured_json?.blocks || [];
  const fromBlocks = blocks
    .filter((b) => b.type === 'title' || b.type === 'subtitle')
    .map((b) => ({ text: b.text, level: b.type === 'title' ? 1 : 2 }));
  if (fromBlocks.length > 1) return fromBlocks.slice(0, 80);

  const headings: OutlineItem[] = [];
  (doc.ocr_markdown || '').split('\n').forEach((line) => {
    const m = /^(#{1,3})\s+(.+)$/.exec(line.trim());
    if (m) headings.push({ text: m[2].trim(), level: m[1].length });
  });
  return headings.slice(0, 80);
};

export const Reader = ({ doc, onBack, tableStyle, onOpenSettings, onReprocess }: ReaderProps) => {
  // .tex/.zip 文档没有 PDF 视图（server 对 /pdf 端点返回 404），默认纯 Markdown
  const [viewMode, setViewMode] = useState<'split' | 'pdf' | 'markdown'>(
    /\.(tex|zip)$/i.test(doc.filename) ? 'markdown' : 'split'
  );
  const [chatQuery, setChatQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  // Phase 2：引用模式（知识库逐字引文 → LLM，全文不外溢）
  const [citeMode, setCiteMode] = useState(false);
  const [chatFocusSignal, setChatFocusSignal] = useState(0);

  // Resizable Logic: Left Sidebar
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const isResizingLeft = useRef(false);

  // Resizable Logic: Right Sidebar
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const isResizingRight = useRef(false);

  // Resizable Logic: Mid Split
  const [splitRatio, setSplitRatio] = useState(50); // percentage for PDF
  const isResizingSplit = useRef(false);

  const markdownRef = useRef<HTMLDivElement>(null);
  const [activeHeading, setActiveHeading] = useState<string | null>(null);
  const [selectionMenu, setSelectionMenu] = useState<{ x: number; y: number; text: string } | null>(null);

  const outline = useMemo(() => buildOutline(doc), [doc]);
  const chatStorageKey = `ac:chat:${doc.id}`;

  // 会话按文档持久化（UX-19）
  useEffect(() => {
    try {
      const raw = localStorage.getItem(chatStorageKey);
      setChatHistory(raw ? (JSON.parse(raw) as ChatMessage[]) : []);
    } catch {
      setChatHistory([]);
    }
    setChatQuery('');
    setActiveHeading(null);
  }, [chatStorageKey]);

  useEffect(() => {
    try {
      localStorage.setItem(chatStorageKey, JSON.stringify(chatHistory.slice(-MAX_HISTORY)));
    } catch {
      /* localStorage 不可用时静默降级 */
    }
  }, [chatHistory, chatStorageKey]);

  const onMouseMove = useCallback(
    (e: MouseEvent) => {
      if (isResizingLeft.current) {
        const newWidth = Math.max(48, Math.min(600, e.clientX));
        setLeftWidth(newWidth);
        setLeftCollapsed(newWidth < 100);
      } else if (isResizingRight.current) {
        const newWidth = Math.max(48, Math.min(800, window.innerWidth - e.clientX));
        setRightWidth(newWidth);
        setRightCollapsed(newWidth < 100);
      } else if (isResizingSplit.current) {
        const centerArea = window.innerWidth - (leftCollapsed ? 48 : leftWidth) - (rightCollapsed ? 48 : rightWidth);
        const relativeX = e.clientX - (leftCollapsed ? 48 : leftWidth);
        const newRatio = Math.max(10, Math.min(90, (relativeX / centerArea) * 100));
        setSplitRatio(newRatio);
      }
    },
    [leftWidth, leftCollapsed, rightWidth, rightCollapsed]
  );

  const onMouseUp = useCallback(() => {
    isResizingLeft.current = false;
    isResizingRight.current = false;
    isResizingSplit.current = false;
    document.body.style.cursor = 'default';
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const startResizing = (type: 'left' | 'right' | 'split') => {
    if (type === 'left') isResizingLeft.current = true;
    if (type === 'right') isResizingRight.current = true;
    if (type === 'split') isResizingSplit.current = true;
    document.body.style.cursor = 'col-resize';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  // 划词工具条（复制 / 引用到提问）——闭合「无法摘录引文」的缺口
  useEffect(() => {
    const handleMouseUp = () => {
      const sel = window.getSelection();
      const container = markdownRef.current;
      const text = sel?.toString().trim() || '';
      if (!sel || !text || !container || sel.rangeCount === 0) {
        setSelectionMenu(null);
        return;
      }
      const range = sel.getRangeAt(0);
      if (!container.contains(range.commonAncestorContainer)) {
        setSelectionMenu(null);
        return;
      }
      const rect = range.getBoundingClientRect();
      setSelectionMenu({
        x: Math.min(Math.max(rect.left + rect.width / 2, 120), window.innerWidth - 120),
        y: Math.max(rect.top, 60),
        text,
      });
    };
    const dismiss = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target?.closest?.('[data-selection-menu]')) return;
      setSelectionMenu(null);
    };
    const dismissOnScroll = () => setSelectionMenu(null);
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('mousedown', dismiss);
    document.addEventListener('scroll', dismissOnScroll, true);
    return () => {
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('mousedown', dismiss);
      document.removeEventListener('scroll', dismissOnScroll, true);
    };
  }, []);

  const handleCopySelection = async () => {
    if (!selectionMenu) return;
    try {
      await navigator.clipboard.writeText(selectionMenu.text);
      toast.success('已复制选中的文本');
    } catch {
      toast.error('复制失败：请手动选择后使用 Ctrl+C');
    }
    setSelectionMenu(null);
  };

  const handleQuoteSelection = () => {
    if (!selectionMenu) return;
    const quoted = selectionMenu.text
      .split('\n')
      .map((line) => `> ${line}`)
      .join('\n');
    setChatQuery((prev) => (prev.trim() ? `${quoted}\n\n${prev}` : `${quoted}\n\n`));
    setRightCollapsed(false);
    setChatFocusSignal((n) => n + 1);
    setSelectionMenu(null);
    window.getSelection()?.removeAllRanges();
    toast.info('已引用到提问框，补充问题后回车发送');
  };

  const handleSendMessage = async () => {
    const userMsg = chatQuery.trim();
    if (!userMsg) return;

    setChatQuery('');
    setChatHistory((prev) => [...prev, { role: 'user', content: userMsg }]);
    setIsTyping(true);

    try {
      let data;
      if (citeMode) {
        // 引用模式：先跨库检索，只把本文档的逐字引文喂给 LLM
        // （limit 20 再按 doc_id 过滤；无命中不调 LLM，避免幻觉引文）
        const search = await api.searchKnowledge(userMsg, 20);
        const quotes = ((search.results || []) as any[])
          .filter((r) => r.doc_id === doc.id)
          .map((r) => r.quote);
        if (quotes.length === 0) {
          setChatHistory((prev) => [
            ...prev,
            {
              role: 'ai',
              content:
                '引用模式下没有找到可引用段落。\n\n可以：\n1. 到「文献库 → 知识库检索」先摄入本文档；\n2. 或关闭引用模式，改为按全文提问。',
            },
          ]);
          return;
        }
        data = await api.chat(doc.id, userMsg, quotes);
      } else {
        data = await api.chat(doc.id, userMsg);
      }
      if (data?.response) {
        setChatHistory((prev) => [...prev, { role: 'ai', content: data.response }]);
      } else {
        setChatHistory((prev) => [
          ...prev,
          { role: 'ai', content: 'AI 没有返回内容。请稍后重试；若持续失败，请检查设置中的模型配置。' },
        ]);
        setChatQuery(userMsg);
      }
    } catch (e) {
      console.error('Chat failed:', e);
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'ai',
          content:
            '连接失败：无法连接后端服务。\n\n请确认应用已完全启动；问题已放回输入框，恢复后可再次回车重试。',
        },
      ]);
      setChatQuery(userMsg);
    } finally {
      setIsTyping(false);
    }
  };

  const scrollToHeading = useCallback(
    (text: string) => {
      const container = markdownRef.current;
      if (!container) {
        setViewMode('markdown');
        window.setTimeout(() => scrollToHeading(text), 80);
        return;
      }
      const headings = Array.from(container.querySelectorAll<HTMLElement>('h1,h2,h3'));
      const key = text.trim().slice(0, 24);
      const target =
        headings.find((h) => (h.textContent || '').trim().includes(key)) ||
        headings.find((h) => key.includes((h.textContent || '').trim().slice(0, 24)));
      if (!target) {
        toast.info('未能在正文中定位到该标题');
        return;
      }
      target.scrollIntoView({ block: 'start', behavior: 'smooth' });
      setActiveHeading(text);
    },
    []
  );

  const handleAnalyze = () => {
    setRightCollapsed(false);
    setChatFocusSignal((n) => n + 1);
    setChatQuery((prev) =>
      prev.trim() ? prev : '请概括这篇论文的研究问题、方法、主要结论与局限性。'
    );
  };

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-slate-100 font-sans">
      {/* Left Sidebar：文档目录（动态生成，UX-05） */}
      <motion.aside
        animate={{ width: leftCollapsed ? 48 : leftWidth }}
        className="shrink-0 border-r border-slate-200 bg-slate-50 relative flex flex-col overflow-hidden z-30 shadow-sm select-none"
      >
        <div className="p-4 border-b border-slate-200 flex items-center justify-between overflow-hidden text-slate-900">
          {!leftCollapsed && (
            <span className="text-xs font-bold text-slate-500 truncate">文档目录</span>
          )}
          <button
            aria-label={leftCollapsed ? '展开目录栏' : '收起目录栏'}
            title={leftCollapsed ? '展开目录栏' : '收起目录栏'}
            onClick={() => setLeftCollapsed(!leftCollapsed)}
            className="p-1.5 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors shrink-0"
          >
            {leftCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {!leftCollapsed && (
          <nav className="p-3 space-y-1 overflow-y-auto custom-scrollbar">
            {outline.length === 0 ? (
              <div className="px-3 py-6 text-center">
                <ListTree className="w-6 h-6 text-slate-300 mx-auto mb-2" />
                <p className="text-xs text-slate-400 leading-relaxed">
                  这篇文档还没有可用的结构信息。
                  <br />
                  OCR 完成后会自动生成。
                </p>
              </div>
            ) : (
              outline.map((item, idx) => (
                <button
                  key={`${item.text}-${idx}`}
                  onClick={() => scrollToHeading(item.text)}
                  title={item.text}
                  className={`w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-colors ${
                    activeHeading === item.text
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-600 hover:bg-slate-200/60'
                  }`}
                  style={{ paddingLeft: item.level >= 2 ? 20 : 12 }}
                >
                  {item.level <= 1 ? (
                    <FileText className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  ) : (
                    <span className="w-3.5 shrink-0 text-center text-slate-400 leading-4">·</span>
                  )}
                  <span className="text-xs font-medium leading-snug line-clamp-2">{item.text}</span>
                </button>
              ))
            )}
          </nav>
        )}

        {/* Resize Handle: Left（常显细线 + hover 加粗 + 双击复位，UX-42） */}
        <div
          data-testid="resize-handle-left"
          role="separator"
          aria-label="调整目录栏宽度"
          title="拖拽调整宽度，双击复位"
          onMouseDown={() => startResizing('left')}
          onDoubleClick={() => {
            setLeftWidth(DEFAULT_LEFT_WIDTH);
            setLeftCollapsed(false);
          }}
          className="absolute right-0 top-0 bottom-0 w-1.5 bg-slate-200/80 hover:bg-indigo-400 cursor-col-resize z-50 transition-colors flex items-center justify-center group"
        >
          <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
        </div>
      </motion.aside>

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
              style={{ width: viewMode === 'split' ? `${splitRatio}%` : '100%' }}
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
              onMouseDown={() => startResizing('split')}
              onDoubleClick={() => setSplitRatio(50)}
              className="w-1.5 bg-slate-300 hover:bg-indigo-400 cursor-col-resize transition-colors z-40 flex items-center justify-center group"
            >
              <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
            </div>
          )}

          {(viewMode === 'markdown' || viewMode === 'split') && (
            <div
              ref={markdownRef}
              style={{ width: viewMode === 'split' ? `${100 - splitRatio}%` : '100%' }}
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
        animate={{ width: rightCollapsed ? 48 : rightWidth }}
        className="shrink-0 bg-slate-50 border-l border-slate-200 relative overflow-hidden flex flex-col z-30 shadow-sm"
      >
        {/* Resize Handle: Right */}
        <div
          role="separator"
          aria-label="调整助手栏宽度"
          title="拖拽调整宽度，双击复位"
          onMouseDown={() => startResizing('right')}
          onDoubleClick={() => {
            setRightWidth(DEFAULT_RIGHT_WIDTH);
            setRightCollapsed(false);
          }}
          className="absolute left-0 top-0 bottom-0 w-1.5 bg-slate-200/80 hover:bg-indigo-400 cursor-col-resize z-50 transition-colors flex items-center justify-center group"
        >
          <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
        </div>

        <ChatSidebar
          docId={doc.id}
          collapsed={rightCollapsed}
          setCollapsed={setRightCollapsed}
          chatHistory={chatHistory}
          chatQuery={chatQuery}
          setChatQuery={setChatQuery}
          isTyping={isTyping}
          onSendMessage={handleSendMessage}
          onClearHistory={() => {
            setChatHistory([]);
            toast.success('对话已清空');
          }}
          citeMode={citeMode}
          setCiteMode={setCiteMode}
          focusSignal={chatFocusSignal}
        />
      </motion.aside>

      {/* 划词工具条 */}
      {selectionMenu && (
        <div
          data-selection-menu
          style={{ left: selectionMenu.x, top: selectionMenu.y }}
          className="fixed -translate-x-1/2 -translate-y-[calc(100%+8px)] z-[130] flex items-center gap-1 bg-slate-900 text-white rounded-xl shadow-xl px-1.5 py-1.5 select-none"
        >
          <button
            onClick={handleCopySelection}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold hover:bg-white/10 transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
            复制
          </button>
          <div className="w-px h-4 bg-white/20" />
          <button
            onClick={handleQuoteSelection}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold hover:bg-white/10 transition-colors"
          >
            <Quote className="w-3.5 h-3.5" />
            引用到提问
          </button>
        </div>
      )}
    </div>
  );
};
