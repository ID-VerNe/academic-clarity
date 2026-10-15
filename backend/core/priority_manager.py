"""
Academic Clarity - 优先级队列 worker 管理器

消费 PriorityTaskQueue：并发 worker 池、任务执行、重试（QueuedTask 退避表）、
重试耗尽后移入死信。`priority_task_hub` 单例经 core.priority_queue 惰性
re-export（`from core.priority_queue import priority_task_hub` 冻结导入不变）。
"""
import asyncio
import time
from typing import Callable, Dict, Optional
from collections import defaultdict

from constants import TaskConfig
from core.priority_models import TaskPriority, QueuedTask
from core.priority_queue import PriorityTaskQueue


class PriorityTaskManager:
    def __init__(self, concurrency: Optional[int] = None):
        if concurrency is None:
            concurrency = TaskConfig.DEFAULT_CONCURRENCY

        self.queue = PriorityTaskQueue()
        self.concurrency = concurrency
        self.workers: list = []
        self._app_state = None
        self._running = False
        self._active_task_ids: Dict[int, str] = {}
        self._worker_stats: Dict[int, Dict] = defaultdict(lambda: {"tasks": 0, "errors": 0})

    async def start(self, app_state):
        self._app_state = app_state
        self._running = True

        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker_loop(i))
            self.workers.append(worker)

        print(f"[PriorityTaskHub] Started {self.concurrency} workers")

    async def stop(self):
        self._running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        print("[PriorityTaskHub] Stopped")

    async def add_task(self, doc_id: int, task_func: Callable, *args,
                       priority: TaskPriority = TaskPriority.NORMAL,
                       force: bool = False, **kwargs) -> Optional[str]:
        if not force and doc_id in self._active_task_ids:
            print(f"[PriorityTaskHub] Doc {doc_id} already processing, skipping")
            return None

        task = QueuedTask(
            priority=priority.value,
            doc_id=doc_id,
            task_func=task_func,
            args=args,
            kwargs=kwargs
        )

        if force:
            await self.queue.cancel_by_doc_id(doc_id)

        self._active_task_ids[doc_id] = task.task_id
        return await self.queue.enqueue(task)

    async def _worker_loop(self, worker_id: int):
        while self._running:
            task = await self.queue.wait_for_task(timeout=1.0)

            if task is None:
                continue

            print(f"[Worker-{worker_id}] Processing Doc {task.doc_id} (Priority: {TaskPriority(task.priority).name})")
            start_time = time.time()

            try:
                await task.task_func(task.doc_id, *task.args, db=self._app_state.db, **task.kwargs)
                self._worker_stats[worker_id]["tasks"] += 1
                print(f"[Worker-{worker_id}] Completed Doc {task.doc_id} in {time.time() - start_time:.2f}s")

            except Exception as e:
                self._worker_stats[worker_id]["errors"] += 1
                error_msg = str(e)

                if task.can_retry():
                    print(f"[Worker-{worker_id}] Retrying Doc {task.doc_id} ({task.retry_count}/{TaskConfig.MAX_RETRIES}): {error_msg}")
                    await self.queue.requeue_with_delay(task)
                else:
                    print(f"[Worker-{worker_id}] Max retries reached for Doc {task.doc_id}: {error_msg}")
                    self.queue.move_to_dead_letter(task, error_msg)
            finally:
                if self._active_task_ids.get(task.doc_id) == task.task_id:
                    self._active_task_ids.pop(task.doc_id, None)

    def get_stats(self) -> Dict:
        return {
            "queue_stats": self.queue.get_stats(),
            "active_tasks": len(self._active_task_ids),
            "worker_stats": dict(self._worker_stats)
        }


priority_task_hub = PriorityTaskManager()
