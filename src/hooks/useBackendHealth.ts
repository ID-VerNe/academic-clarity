import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

export type FetchData = (opts?: { silent?: boolean; retries?: number }) => Promise<void>;

export interface BackendHealth {
  /** 后端健康状态（页脚状态灯 / 连接反馈） */
  backendHealthy: boolean;
  /** 标记后端可达（清除断连标记） */
  markHealthy: () => void;
  /** 标记后端不可达（进入断连态，等待 30s 轮询恢复） */
  markUnhealthy: () => void;
  /** useDocuments 注册数据重取函数（断连恢复时由 30s 轮询调用） */
  registerFetchData: (fn: FetchData) => void;
}

/**
 * 后端健康状态 + 30s 健康轮询（UX-36）。
 * 从「断连」恢复时自动重取数据；fetchData 经 registerFetchData 注入，
 * 避免与 useDocuments 形成循环依赖。
 */
export function useBackendHealth(): BackendHealth {
  const [backendHealthy, setBackendHealthy] = useState(true);
  const wasUnhealthy = useRef(false);
  const fetchDataRef = useRef<FetchData | null>(null);

  const markHealthy = useCallback(() => {
    setBackendHealthy(true);
    wasUnhealthy.current = false;
  }, []);

  const markUnhealthy = useCallback(() => {
    setBackendHealthy(false);
    wasUnhealthy.current = true;
  }, []);

  const registerFetchData = useCallback((fn: FetchData) => {
    fetchDataRef.current = fn;
  }, []);

  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        await api.health();
        if (cancelled) return;
        if (wasUnhealthy.current) {
          markHealthy();
          fetchDataRef.current?.({ silent: true });
        } else {
          markHealthy();
        }
      } catch {
        if (!cancelled) markUnhealthy();
      }
    };
    const timer = setInterval(ping, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [markHealthy, markUnhealthy]);

  return { backendHealthy, markHealthy, markUnhealthy, registerFetchData };
}
