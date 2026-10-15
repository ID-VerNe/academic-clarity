import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, FileText, GripVertical, ListTree } from 'lucide-react';
import { motion } from 'motion/react';
import { toast } from '../ui/Toast';
import { OutlineItem } from './outline';

/** 在正文容器中按目录文本定位标题（前后 24 字符模糊匹配，UX-05） */
const findHeadingElement = (container: HTMLElement, text: string): HTMLElement | null => {
  const headings = Array.from(container.querySelectorAll<HTMLElement>('h1,h2,h3'));
  const key = text.trim().slice(0, 24);
  return (
    headings.find((h) => (h.textContent || '').trim().includes(key)) ||
    headings.find((h) => key.includes((h.textContent || '').trim().slice(0, 24))) ||
    null
  );
};

interface ReaderOutlineProps {
  outline: OutlineItem[];
  collapsed: boolean;
  width: number;
  /** 正文滚动容器（点击目录定位用） */
  contentRef: React.RefObject<HTMLElement | null>;
  /** 正文容器不存在时请求切到文本视图（PDF 独占模式） */
  onNeedMarkdownView: () => void;
  onToggleCollapsed: () => void;
  /** 拖拽把手 mousedown：由 useResizable 接管 document 级监听 */
  onResizeStart: () => void;
  /** 双击复位默认宽度 */
  onResetWidth: () => void;
}

/** Left Sidebar：文档目录（动态生成 + 点击定位正文，UX-05） */
export const ReaderOutline = ({
  outline,
  collapsed,
  width,
  contentRef,
  onNeedMarkdownView,
  onToggleCollapsed,
  onResizeStart,
  onResetWidth,
}: ReaderOutlineProps) => {
  const [activeHeading, setActiveHeading] = useState<string | null>(null);

  // 切换文档（目录重建）时清除高亮
  useEffect(() => {
    setActiveHeading(null);
  }, [outline]);

  const scrollToHeading = (text: string) => {
    const container = contentRef.current;
    if (!container) {
      onNeedMarkdownView();
      window.setTimeout(() => scrollToHeading(text), 80);
      return;
    }
    const target = findHeadingElement(container, text);
    if (!target) {
      toast.info('未能在正文中定位到该标题');
      return;
    }
    target.scrollIntoView({ block: 'start', behavior: 'smooth' });
    setActiveHeading(text);
  };

  return (
    <motion.aside
      animate={{ width: collapsed ? 48 : width }}
      className="shrink-0 border-r border-slate-200 bg-slate-50 relative flex flex-col overflow-hidden z-30 shadow-sm select-none"
    >
      <div className="p-4 border-b border-slate-200 flex items-center justify-between overflow-hidden text-slate-900">
        {!collapsed && (
          <span className="text-xs font-bold text-slate-500 truncate">文档目录</span>
        )}
        <button
          aria-label={collapsed ? '展开目录栏' : '收起目录栏'}
          title={collapsed ? '展开目录栏' : '收起目录栏'}
          onClick={onToggleCollapsed}
          className="p-1.5 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors shrink-0"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {!collapsed && (
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
        onMouseDown={onResizeStart}
        onDoubleClick={onResetWidth}
        className="absolute right-0 top-0 bottom-0 w-1.5 bg-slate-200/80 hover:bg-indigo-400 cursor-col-resize z-50 transition-colors flex items-center justify-center group"
      >
        <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
      </div>
    </motion.aside>
  );
};
