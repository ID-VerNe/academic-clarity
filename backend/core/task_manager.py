import asyncio
import os
import time
from datetime import datetime
from typing import Dict, Optional

try:
    from backend.constants import TaskConfig
except ImportError:
    from constants import TaskConfig

try:
    from backend.utils.logger import get_logger
except ImportError:
    from utils.logger import get_logger

class TaskManager:
    def __init__(self, concurrency=None):
        if concurrency is None:
            concurrency = TaskConfig.DEFAULT_CONCURRENCY
        self.queue = asyncio.Queue()
        self.concurrency = concurrency
        self.workers = []
        self.active_task_ids: set = set()
        self.failed_task_ids: Dict[int, tuple] = {}
        self._app_state = None
        self._cleanup_task = None
        self._last_cleanup = time.time()
        self._running = False
        self._logger = get_logger()

    async def start_workers(self, app_state):
        """启动指定数量的并行 Worker"""
        self._app_state = app_state
        self._running = True
        self._logger.info(
            "Starting TaskHub workers",
            event="taskhub_start",
            concurrency=self.concurrency
        )
        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker_loop(i, app_state))
            self.workers.append(worker)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def _cleanup_old_failures(self):
        """清理过期的失败任务记录，防止内存无限增长"""
        if len(self.failed_task_ids) <= TaskConfig.MAX_FAILED_TASKS:
            return

        sorted_tasks = sorted(
            self.failed_task_ids.items(),
            key=lambda x: x[1][1]
        )

        to_remove = len(self.failed_task_ids) - TaskConfig.MAX_FAILED_TASKS
        for doc_id, _ in sorted_tasks[:to_remove]:
            self.failed_task_ids.pop(doc_id, None)

        self._logger.info(
            f"Cleaned up {to_remove} old failed task records",
            event="cleanup",
            removed_count=to_remove
        )

    async def _cleanup_loop(self):
        """定期清理失败的记录"""
        while True:
            await asyncio.sleep(300)
            self._cleanup_old_failures()

    async def add_task(self, doc_id, task_func, *args, force: bool = False):
        """向队尾添加任务

        Args:
            force: 如果为 True，即使任务超过最大重试次数也强制重新入队
        """
        if doc_id in self.active_task_ids:
            self._logger.debug(
                f"Doc {doc_id} already in queue, skipping",
                event="task_skip",
                reason="already_active",
                doc_id=doc_id
            )
            return

        if not force and doc_id in self.failed_task_ids:
            fail_count, last_fail = self.failed_task_ids[doc_id]
            if fail_count >= TaskConfig.MAX_RETRIES:
                self._logger.info(
                    f"Doc {doc_id} exceeded max retries",
                    event="task_skip",
                    reason="max_retries_exceeded",
                    doc_id=doc_id,
                    fail_count=fail_count
                )
                return

        if force and doc_id in self.failed_task_ids:
            self._logger.info(
                f"Doc {doc_id} forcing requeue, clearing failed record",
                event="task_force_requeue",
                doc_id=doc_id
            )
            self.failed_task_ids.pop(doc_id, None)

        self.active_task_ids.add(doc_id)
        await self.queue.put((doc_id, task_func, args, 0))
        self._logger.debug(
            f"Task queued for Doc {doc_id}",
            event="task_queued",
            doc_id=doc_id
        )

    async def _schedule_retry(self, doc_id, task_func, args, retries):
        """非阻塞方式调度重试，避免阻塞 worker"""
        backoff = TaskConfig.RETRY_BACKOFF[retries] if retries < len(TaskConfig.RETRY_BACKOFF) else TaskConfig.RETRY_BACKOFF[-1]
        self._logger.info(
            f"Scheduling retry for Doc {doc_id}",
            event="retry_scheduled",
            doc_id=doc_id,
            retry_count=retries,
            backoff_seconds=backoff
        )
        await asyncio.sleep(backoff)
        self.failed_task_ids[doc_id] = (retries, time.time())
        self._cleanup_old_failures()
        await self.queue.put((doc_id, task_func, args, retries))

    async def _worker_loop(self, worker_id, app_state):
        """Worker 循环认领任务"""
        while self._running:
            doc_id, task_func, args, retries = await self.queue.get()
            start_time = time.time()

            self._logger.info(
                f"Worker {worker_id} processing Doc {doc_id}",
                event="task_start",
                worker_id=worker_id,
                doc_id=doc_id,
                retry_count=retries
            )

            try:
                await task_func(doc_id, *args, db=app_state.db)
                self.active_task_ids.discard(doc_id)
                self.failed_task_ids.pop(doc_id, None)
                duration = time.time() - start_time
                self._logger.info(
                    f"Task SUCCESS for Doc {doc_id}",
                    event="task_complete",
                    worker_id=worker_id,
                    doc_id=doc_id,
                    duration_ms=round(duration * 1000, 2),
                    status="success"
                )
            except Exception as e:
                duration = time.time() - start_time
                self._logger.error(
                    f"Task FAILED for Doc {doc_id}",
                    event="task_error",
                    worker_id=worker_id,
                    doc_id=doc_id,
                    duration_ms=round(duration * 1000, 2),
                    error=str(e)
                )

                if retries < TaskConfig.MAX_RETRIES:
                    asyncio.create_task(self._schedule_retry(doc_id, task_func, args, retries + 1))
                else:
                    self.active_task_ids.discard(doc_id)
                    self.failed_task_ids[doc_id] = (retries, time.time())
                    self._cleanup_old_failures()
                    self._logger.warning(
                        f"Max retries reached for Doc {doc_id}, giving up",
                        event="task_abandoned",
                        doc_id=doc_id,
                        total_retries=retries
                    )

            self.queue.task_done()

    def get_stats(self) -> Dict:
        """获取任务管理器统计信息"""
        return {
            "active_tasks": len(self.active_task_ids),
            "queued_tasks": self.queue.qsize(),
            "failed_tasks": len(self.failed_task_ids),
            "failed_task_details": [
                {"doc_id": doc_id, "retries": fail_count, "last_fail": last_fail}
                for doc_id, (fail_count, last_fail) in self.failed_task_ids.items()
            ]
        }

    async def stop(self):
        """优雅停止任务管理器"""
        self._running = False
        self._logger.info(
            "Stopping TaskHub workers",
            event="taskhub_stop"
        )
        if self._cleanup_task:
            self._cleanup_task.cancel()
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self._logger.info(
            "All TaskHub workers stopped",
            event="taskhub_stopped"
        )

task_hub = TaskManager()
