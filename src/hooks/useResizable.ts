import { useState, useCallback, useRef } from 'react';

export const useResizable = (initialWidth: number, minWidth: number, maxWidth: number, direction: 'left' | 'right' = 'left') => {
  const [width, setWidth] = useState(initialWidth);
  const [isResizing, setIsResizing] = useState(false);
  const isResizingRef = useRef(false);

  const startResizing = useCallback(() => {
    setIsResizing(true);
    isResizingRef.current = true;
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
    isResizingRef.current = false;
  }, []);

  const resize = useCallback((event: MouseEvent) => {
    if (!isResizingRef.current) return;

    let newWidth: number;
    if (direction === 'left') {
      newWidth = event.clientX;
    } else {
      newWidth = window.innerWidth - event.clientX;
    }

    if (newWidth >= minWidth && newWidth <= maxWidth) {
      setWidth(newWidth);
    }
  }, [minWidth, maxWidth, direction]);

  return { width, isResizing, startResizing, stopResizing, resize };
};
