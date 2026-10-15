import { useEffect, useState } from 'react';
import { Document } from '../types';
import { api } from '../api/client';

/**
 * 轮询处理队列（含 stage / progress / elapsed，UX-26）。
 * 每 2s 拉取一次；卸载时置 cancelled 并清定时器，避免对已卸载组件 setState。
 */
export const useActiveTasks = (): Document[] => {
  const [activeTasks, setActiveTasks] = useState<Document[]>([]);

  useEffect(() => {
    let cancelled = false;
    const fetchTasks = async () => {
      try {
        const tasks = await api.getActiveTasks();
        if (!cancelled) setActiveTasks(Array.isArray(tasks) ? tasks : []);
      } catch (e) {
        console.error('Task poll error', e);
      }
    };
    fetchTasks();
    const timer = setInterval(fetchTasks, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return activeTasks;
};
