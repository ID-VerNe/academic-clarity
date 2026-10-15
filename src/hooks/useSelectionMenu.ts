import { useCallback, useEffect, useState, RefObject } from 'react';
import { toast } from '../components/ui/Toast';

export interface SelectionMenuState {
  x: number;
  y: number;
  text: string;
}

/**
 * 划词工具条（复制 / 引用到提问）——闭合「无法摘录引文」的缺口。
 * mouseup 定位（限制在容器内）、点击外部 / 滚动时关闭；
 * 引用文本交由调用方注入会话（onQuote）。
 */
export const useSelectionMenu = (
  containerRef: RefObject<HTMLElement | null>,
  onQuote: (text: string) => void
) => {
  const [menu, setMenu] = useState<SelectionMenuState | null>(null);

  useEffect(() => {
    const handleMouseUp = () => {
      const sel = window.getSelection();
      const container = containerRef.current;
      const text = sel?.toString().trim() || '';
      if (!sel || !text || !container || sel.rangeCount === 0) {
        setMenu(null);
        return;
      }
      const range = sel.getRangeAt(0);
      if (!container.contains(range.commonAncestorContainer)) {
        setMenu(null);
        return;
      }
      const rect = range.getBoundingClientRect();
      setMenu({
        x: Math.min(Math.max(rect.left + rect.width / 2, 120), window.innerWidth - 120),
        y: Math.max(rect.top, 60),
        text,
      });
    };
    const dismiss = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target?.closest?.('[data-selection-menu]')) return;
      setMenu(null);
    };
    const dismissOnScroll = () => setMenu(null);
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('mousedown', dismiss);
    document.addEventListener('scroll', dismissOnScroll, true);
    return () => {
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('mousedown', dismiss);
      document.removeEventListener('scroll', dismissOnScroll, true);
    };
  }, [containerRef]);

  const copySelection = useCallback(async () => {
    if (!menu) return;
    try {
      await navigator.clipboard.writeText(menu.text);
      toast.success('已复制选中的文本');
    } catch {
      toast.error('复制失败：请手动选择后使用 Ctrl+C');
    }
    setMenu(null);
  }, [menu]);

  const quoteSelection = useCallback(() => {
    if (!menu) return;
    onQuote(menu.text);
    setMenu(null);
    window.getSelection()?.removeAllRanges();
    toast.info('已引用到提问框，补充问题后回车发送');
  }, [menu, onQuote]);

  return { menu, copySelection, quoteSelection };
};
