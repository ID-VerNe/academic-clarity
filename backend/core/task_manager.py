import asyncio
import os
import time
from datetime import datetime
from typing import Dict, Optional

try:
    from backend.constants import TaskConfig
except ImportError:
    from constants import TaskConfig

class TaskManager:
    def __init__(self, concurrency=None):
        if concurrency is None:
            concurrency = TaskConfig.DEFAULT_CONCURRENCY
        self.queue = asyncio.Queue()
        self.concurrency = concurrency
        self.workers = []
        self.active_task_ids: set = set()
        self.failed_task_ids: Dict[int, tuple] = {}
        # UX-26：取消支持——排队中标记跳过，运行中直接取消其 asyncio.Task
        self.cancelled_task_ids: set = set()
        self._running: Dict[int, asyncio.Task] = {}
        self._app_state = None
        self._cleanup_task = None
        self._last_cleanup = time.time()

    async def start_workers(self, app_state):
        """启动指定数量的并行 Worker"""
        self._app_state = app_state
        # 单例可能被多次 lifespan 复用：先清掉旧 loop 的残留 worker，
        # 避免 gather 到已关闭 loop 的任务导致 RuntimeError
        self.workers.clear()
        # 重建队列：asyncio.Queue 首次 get() 时绑定事件循环，
        # 复用旧队列会绑定到已关闭的 loop
        self.queue = asyncio.Queue()
        self.active_task_ids.clear()
        self.cancelled_task_ids.clear()
        self._running.clear()
        print(f"[TaskHub] Launching {self.concurrency} parallel workers...")
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

        print(f"[TaskHub] Cleaned up {to_remove} old failed task records")

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
            print(f"[TaskHub] Doc {doc_id} already in queue, skipping")
            return

        if not force and doc_id in self.failed_task_ids:
            fail_count, last_fail = self.failed_task_ids[doc_id]
            if fail_count >= TaskConfig.MAX_RETRIES:
                print(f"[TaskHub] Doc {doc_id} exceeded max retries ({fail_count}), skipping. Use force=True to requeue.")
                return

        if force and doc_id in self.failed_task_ids:
            print(f"[TaskHub] Doc {doc_id} forcing requeue, clearing failed record")
            self.failed_task_ids.pop(doc_id, None)

        # 重新入队时清除历史取消标记，否则新任务会被 worker 直接丢弃
        self.cancelled_task_ids.discard(doc_id)
        self.active_task_ids.add(doc_id)
        await self.queue.put((doc_id, task_func, args, 0))

    async def cancel_task(self, doc_id) -> bool:
        """取消排队中或运行中的任务（UX-26）。

        - 运行中：取消该任务自己的 asyncio.Task（worker 本身存活）
        - 排队中：标记跳过，worker 认领时直接丢弃
        返回 True 表示确实命中了一个排队中/运行中的任务。
        """
        running = self._running.get(doc_id)
        if running and not running.done():
            self.cancelled_task_ids.add(doc_id)
            running.cancel()
            return True
        if doc_id in self.active_task_ids:
            self.cancelled_task_ids.add(doc_id)
            return True
        return False

    async def _schedule_retry(self, doc_id, task_func, args, retries):
        """非阻塞方式调度重试，避免阻塞 worker"""
        backoff = TaskConfig.RETRY_BACKOFF[retries] if retries < len(TaskConfig.RETRY_BACKOFF) else TaskConfig.RETRY_BACKOFF[-1]
        print(f"[TaskHub] Scheduling retry {retries}/{TaskConfig.MAX_RETRIES} for Doc {doc_id} in {backoff}s (non-blocking)")
        await asyncio.sleep(backoff)
        self.failed_task_ids[doc_id] = (retries, time.time())
        self._cleanup_old_failures()
        await self.queue.put((doc_id, task_func, args, retries))

    async def _worker_loop(self, worker_id, app_state):
        """Worker 循环认领任务"""
        while True:
            doc_id, task_func, args, retries = await self.queue.get()

            # 已在排队期间被用户取消：直接丢弃，不启动任务
            if doc_id in self.cancelled_task_ids:
                self.cancelled_task_ids.discard(doc_id)
                self.active_task_ids.discard(doc_id)
                print(f"[Worker-{worker_id}] Task for Doc {doc_id} cancelled before start")
                self.queue.task_done()
                continue

            print(f"[Worker-{worker_id}] Claimed task for Doc ID: {doc_id}")

            # 任务独立成 asyncio.Task：取消只作用于它，worker 循环保持存活
            job = asyncio.create_task(task_func(doc_id, *args, db=app_state.db))
            self._running[doc_id] = job
            try:
                await job
                self.active_task_ids.discard(doc_id)
                self.failed_task_ids.pop(doc_id, None)
                print(f"[Worker-{worker_id}] Task SUCCESS for Doc: {doc_id}")
            except asyncio.CancelledError:
                if job.cancelled() and doc_id in self.cancelled_task_ids:
                    self.cancelled_task_ids.discard(doc_id)
                    self.active_task_ids.discard(doc_id)
                    print(f"[Worker-{worker_id}] Task CANCELLED for Doc: {doc_id}")
                else:
                    # worker 自身被取消（如 shutdown）：向上传播
                    raise
            except Exception as e:
                print(f"[Worker-{worker_id}] Task FAILED for Doc: {doc_id}. Error: {e}")

                if retries < TaskConfig.MAX_RETRIES:
                    asyncio.create_task(self._schedule_retry(doc_id, task_func, args, retries + 1))
                else:
                    self.active_task_ids.discard(doc_id)
                    self.failed_task_ids[doc_id] = (retries, time.time())
                    self._cleanup_old_failures()
                    print(f"[Worker-{worker_id}] Max retries reached for Doc: {doc_id}. Giving up.")
            finally:
                self._running.pop(doc_id, None)

            self.queue.task_done()

    def get_stats(self) -> Dict:
        """获取任务管理器统计信息"""
        return {
            "active_tasks": len(self.active_task_ids),
            "running_tasks": len(self._running),
            "queued_tasks": self.queue.qsize(),
            "failed_tasks": len(self.failed_task_ids),
            "failed_task_details": [
                {"doc_id": doc_id, "retries": fail_count, "last_fail": last_fail}
                for doc_id, (fail_count, last_fail) in self.failed_task_ids.items()
            ]
        }

    async def shutdown(self):
        """优雅关闭任务管理器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

task_hub = TaskManager()
