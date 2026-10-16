import React, { useState } from 'react';
import { Ban, Clock, Loader2, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Document } from '../../types';
import { api } from '../../api/client';
import { toast } from '../ui/Toast';
import { Button } from '../ui/Button';
import { formatElapsed } from '../../utils/format';

interface ActiveTaskQueueProps {
  tasks: Document[];
  /** 取消成功后请求上层刷新文档列表 */
  onRefresh: () => void;
}

/** Active Tasks Queue（含阶段 / 进度 / 取消，UX-26） */
export const ActiveTaskQueue = ({ tasks, onRefresh }: ActiveTaskQueueProps) => {
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const handleCancelTask = async (task: Document) => {
    setCancellingId(task.id);
    try {
      const res = await api.cancelTask(task.id);
      if (res?.success) {
        toast.info(`已取消「${task.title || task.filename}」的处理`);
        onRefresh();
      } else {
        toast.error(res?.message || '取消失败：该任务可能已经结束');
      }
    } catch (e) {
      console.error('Cancel task failed', e);
      toast.error('取消失败：无法连接后端服务。');
    } finally {
      setCancellingId(null);
    }
  };

  return (
    <AnimatePresence>
      {tasks.length > 0 && (
        <motion.section
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="overflow-hidden"
        >
          <div className="bg-indigo-600 rounded-3xl p-6 text-white shadow-2xl shadow-indigo-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 fill-indigo-300 text-indigo-300" />
                <h3 className="text-sm font-black uppercase tracking-widest">处理队列</h3>
              </div>
              <span className="text-xs font-bold bg-white/20 px-2.5 py-1 rounded-full">
                {tasks.length} 篇处理中
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {tasks.map((task) => {
                const pct =
                  typeof task.progress === 'number' ? Math.max(0, Math.min(100, task.progress)) : null;
                return (
                  <div
                    key={task.id}
                    className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/20"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
                          <Loader2 className="w-4 h-4 animate-spin" />
                        </div>
                        <p className="text-xs font-bold truncate" title={task.title || task.filename}>
                          {task.title || task.filename}
                        </p>
                      </div>
                      <Button
                        variant="danger"
                        icon={<Ban className="w-3.5 h-3.5" />}
                        loading={cancellingId === task.id}
                        onClick={() => handleCancelTask(task)}
                        aria-label={`取消处理 ${task.title || task.filename}`}
                        title="取消处理"
                        className="p-1.5 shrink-0"
                      />
                    </div>
                    <p className="text-xs text-indigo-100 mt-3">{task.stage || '等待处理'}</p>
                    <div className="h-1.5 bg-white/20 rounded-full overflow-hidden mt-2">
                      {pct === null ? (
                        <div className="h-full w-1/3 bg-white/70 rounded-full animate-pulse" />
                      ) : (
                        <div
                          className="h-full bg-white rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(pct, 3)}%` }}
                        />
                      )}
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-indigo-100 mt-1.5">
                      <span>{pct === null ? '处理中…' : `${Math.round(pct)}%`}</span>
                      {typeof task.elapsed === 'number' && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          已用时 {formatElapsed(task.elapsed)}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
};
