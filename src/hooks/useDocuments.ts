import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../components/ui/Toast';
import { Document, AppConfig } from '../types';
import { BackendHealth } from './useBackendHealth';

/**
 * 文档列表 + 配置的数据层：
 * - fetchData：拉取配置与文档（支持 silent 后台刷新 / 1200ms 重试）
 * - handleSync：同步工作区并给出数量反馈（UX-03 / UX-06）
 * - 存在处理中的文档时短轮询（3s）
 * 后端健康标记通过 health 回写（成功 markHealthy / 失败 markUnhealthy）。
 */
export function useDocuments(health: BackendHealth) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const { markHealthy, markUnhealthy, registerFetchData } = health;

  /** 拉取配置 + 文档列表。silent 用于后台刷新（不闪骨架屏、不重复报错） */
  const fetchData = useCallback(async (opts?: { silent?: boolean; retries?: number }) => {
    const silent = !!opts?.silent;
    const retries = opts?.retries ?? 0;
    if (!silent) setIsLoading(true);
    try {
      let lastError: unknown = null;
      for (let attempt = 0; attempt <= retries; attempt += 1) {
        try {
          const [configData, docsData] = await Promise.all([api.getConfigs(), api.getDocuments()]);
          setConfig(configData);
          setDocs(Array.isArray(docsData) ? docsData : []);
          markHealthy();
          return;
        } catch (err) {
          lastError = err;
          if (attempt < retries) await new Promise((r) => setTimeout(r, 1200));
        }
      }
      throw lastError;
    } catch (e) {
      console.error('Fetch error:', e);
      markUnhealthy();
      if (!silent) toast.error('无法连接后端服务，请确认应用已完全启动后重试。');
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [markHealthy, markUnhealthy]);

  /** 同步工作区：完成后刷新列表并给出数量反馈（UX-03 / UX-06） */
  const handleSync = useCallback(async (opts?: { announce?: boolean }) => {
    const announce = opts?.announce ?? true;
    setIsSyncing(true);
    try {
      const res = await api.syncWorkspace();
      await fetchData({ silent: true });
      markHealthy();
      if (announce) {
        const n = Number(res?.triggered ?? 0);
        toast.success(n > 0 ? `同步完成：${n} 篇文档已加入处理队列` : '同步完成：没有待处理的新文件');
      }
    } catch (e) {
      console.error('Sync failed:', e);
      markUnhealthy();
      if (announce) toast.error('同步失败：无法连接后端服务，请稍后重试。');
    } finally {
      setIsSyncing(false);
    }
  }, [fetchData, markHealthy, markUnhealthy]);

  // 注册给健康轮询：断连恢复时自动重取（UX-36）
  useEffect(() => {
    registerFetchData(fetchData);
  }, [registerFetchData, fetchData]);

  // 存在处理中的文档时短轮询（3s）
  useEffect(() => {
    const hasProcessing = docs.some((d) => d.ocr_status === 'processing' || d.ocr_status === 'pending');
    if (!hasProcessing) return;
    const timer = setTimeout(() => fetchData({ silent: true }), 3000);
    return () => clearTimeout(timer);
  }, [docs, fetchData]);

  return { docs, config, isLoading, isSyncing, fetchData, handleSync, setDocs, setConfig };
}
