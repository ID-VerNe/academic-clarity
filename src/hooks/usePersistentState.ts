import { useEffect, useRef, useState } from 'react';

interface PersistentStateOptions<T> {
  /** 序列化函数（默认 JSON.stringify） */
  serialize?: (value: T) => string;
  /** 反序列化函数（默认 JSON.parse） */
  deserialize?: (raw: string) => T;
  /** 写入防抖毫秒数；0 = 立即写（默认） */
  debounceMs?: number;
  /** 写入前的值变换（例如 slice(-MAX_HISTORY)） */
  beforeWrite?: (value: T) => T;
}

/**
 * localStorage 容错持久化（读写均静默降级，绝不抛错）。
 * - key 变化时重新从存储读取（并回落 initial）
 * - value 变化时写回（支持防抖）
 * 语义与 Reader 会话持久化 / PdfViewer 阅读页恢复保持一致。
 */
export function usePersistentState<T>(
  key: string,
  initial: T,
  options: PersistentStateOptions<T> = {}
) {
  const { serialize = JSON.stringify, deserialize = JSON.parse, debounceMs = 0, beforeWrite } = options;
  const [value, setValue] = useState<T>(initial);
  const timerRef = useRef<number | null>(null);
  const initialRef = useRef(initial);

  // key 变化时重读
  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      setValue(raw != null ? (deserialize(raw) as T) : initialRef.current);
    } catch {
      setValue(initialRef.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // value 变化时写回（可防抖）
  useEffect(() => {
    const write = () => {
      try {
        localStorage.setItem(key, serialize(beforeWrite ? beforeWrite(value) : value));
      } catch {
        /* localStorage 不可用时静默降级 */
      }
    };
    if (debounceMs > 0) {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(write, debounceMs);
      return () => {
        if (timerRef.current) window.clearTimeout(timerRef.current);
      };
    }
    write();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, key]);

  return [value, setValue] as const;
}
