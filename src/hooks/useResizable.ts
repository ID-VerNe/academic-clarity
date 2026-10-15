import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseResizableOptions {
  /** 宽度换算方向：left → clientX；right → innerWidth - clientX（默认 left） */
  direction?: 'left' | 'right';
  /** 拖拽中实时 clamp 的下界 */
  min?: number;
  /** 拖拽中实时 clamp 的上界 */
  max?: number;
  /** 低于该值视为收起；配合 onCollapsedChange 使用 */
  collapseThreshold?: number;
  /** 拖拽越过收起阈值时回调（拖回时回调 false） */
  onCollapsedChange?: (collapsed: boolean) => void;
  /** 双击复位目标值；不传则 reset 为 no-op */
  resetValue?: number;
  /** 自定义位置 → 值换算（如分栏百分比）；传入时忽略 direction */
  computeValue?: (event: MouseEvent) => number;
}

/**
 * 拖拽缩放 hook（FE-07）。
 * - mousedown 挂载 document 级 mousemove/mouseup，mouseup（或组件卸载）时移除；
 * - 拖拽中实时 clamp 到 [min, max]；
 * - 可选收起阈值回调（collapsed 语义）与双击复位。
 */
export const useResizable = (initialValue: number, options: UseResizableOptions = {}) => {
  const {
    direction = 'left',
    min = 0,
    max = Number.POSITIVE_INFINITY,
    collapseThreshold,
    onCollapsedChange,
    resetValue,
    computeValue,
  } = options;

  const [value, setValue] = useState(initialValue);
  const [isResizing, setIsResizing] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  const startResizing = useCallback(() => {
    if (cleanupRef.current) return; // 拖拽进行中，忽略重复 mousedown

    const apply = (raw: number) => {
      const next = Math.max(min, Math.min(max, raw));
      setValue(next);
      if (collapseThreshold != null) onCollapsedChange?.(next < collapseThreshold);
    };
    const handleMove = (event: MouseEvent) => {
      apply(
        computeValue
          ? computeValue(event)
          : direction === 'left'
            ? event.clientX
            : window.innerWidth - event.clientX
      );
    };
    const cleanup = () => {
      cleanupRef.current = null;
      setIsResizing(false);
      document.body.style.cursor = 'default';
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', cleanup);
    };

    cleanupRef.current = cleanup;
    setIsResizing(true);
    document.body.style.cursor = 'col-resize';
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', cleanup);
  }, [direction, min, max, collapseThreshold, onCollapsedChange, computeValue]);

  // 组件卸载时兜底移除仍挂载的 document 监听
  useEffect(() => () => cleanupRef.current?.(), []);

  const reset = useCallback(() => {
    if (resetValue == null) return;
    setValue(resetValue);
    onCollapsedChange?.(false);
  }, [resetValue, onCollapsedChange]);

  return { value, isResizing, startResizing, reset, setValue };
};
