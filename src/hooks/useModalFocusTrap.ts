import { useEffect, useRef } from 'react';

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href]';

interface ModalFocusTrapOptions {
  /** 弹窗当前是否可见（false 时卸载监听） */
  active: boolean;
  /** ESC 触发；经 ref 保持最新闭包，调用方无需为依赖变化重建监听 */
  onEscape?: () => void;
}

/**
 * 弹窗焦点圈定（ESC + Tab 循环 + 关闭后归还焦点）。
 * - 打开时记录来源元素并聚焦弹窗内第一个可聚焦元素
 * - Tab / Shift+Tab 在弹窗内首尾循环
 * - 关闭 / 卸载时把焦点归还给来源元素
 * 返回容器 ref，需挂到弹窗根节点上。
 */
export function useModalFocusTrap({ active, onEscape }: ModalFocusTrapOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;

  useEffect(() => {
    if (!active) return;
    lastFocusedRef.current = document.activeElement as HTMLElement;

    const focusable = () =>
      Array.from(containerRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) || []);

    focusable()[0]?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onEscapeRef.current?.();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusable();
      if (items.length === 0) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      lastFocusedRef.current?.focus?.();
    };
  }, [active]);

  return containerRef;
}
