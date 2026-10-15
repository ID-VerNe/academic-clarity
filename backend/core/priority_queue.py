"""
Academic Clarity - 优先级任务队列（堆存储 / 延迟重试 / 按 doc 去重）

- 任务模型见 priority_models.py
- 死信存储见 dead_letter_store.py（threading.Lock，保持原语义）
- worker 池见 priority_manager.py；本模块对 PriorityTaskManager /
  priority_task_hub 做惰性 re-export（PEP 562），保持
  `from core.priority_queue import ...` 冻结导入不变，并避免两个模块循环导入
"""
import asyncio
import heapq
import time
from typing import Dict, Optional, Callable
from collections import defaultdict

from core.priority_models import TaskPriority, QueuedTask, DeadLetterEntry  # noqa: F401 (re-export)
from core.dead_letter_store import DeadLetterStore

__all__ = [
    "TaskPriority", "QueuedTask", "DeadLetterEntry",
    "PriorityTaskQueue", "PriorityTaskManager", "priority_task_hub",
]


class PriorityTaskQueue:
    """优先级任务队列（asyncio.Lock 保护；延迟任务按 scheduled_at 排序）"""

    def __init__(self):
        self._heap: list = []
        self._tasks_by_id: Dict[str, QueuedTask] = {}
        self._tasks_by_doc_id: Dict[int, str] = {}
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()
        self._dead_letters = DeadLetterStore()

    async def enqueue(self, task: QueuedTask) -> str:
        async with self._lock:
            existing_id = self._tasks_by_doc_id.get(task.doc_id)
            if existing_id:
                existing = self._tasks_by_id.get(existing_id)
                if existing:
                    if task.priority < existing.priority:
                        await self._remove_task_internal(existing_id)
                    else:
                        return existing_id

            heapq.heappush(self._heap, task)
            self._tasks_by_id[task.task_id] = task
            self._tasks_by_doc_id[task.doc_id] = task.task_id
            self._event.set()

        return task.task_id

    async def enqueue_priority(self, doc_id: int, task_func: Callable,
                               *args, priority: TaskPriority = TaskPriority.NORMAL,
                               **kwargs) -> str:
        task = QueuedTask(
            priority=priority.value,
            doc_id=doc_id,
            task_func=task_func,
            args=args,
            kwargs=kwargs
        )
        return await self.enqueue(task)

    async def _remove_task_internal(self, task_id: str) -> Optional[QueuedTask]:
        if task_id in self._tasks_by_id:
            task = self._tasks_by_id.pop(task_id)
            self._tasks_by_doc_id.pop(task.doc_id, None)
            return task
        return None

    async def dequeue(self, timeout: float = 1.0) -> Optional[QueuedTask]:
        while True:
            async with self._lock:
                if not self._heap:
                    self._event.clear()
                    return None

                task = self._heap[0]

                if not task.is_ready():
                    return None

                task = heapq.heappop(self._heap)
                if task.task_id in self._tasks_by_id:
                    del self._tasks_by_id[task.task_id]
                    self._tasks_by_doc_id.pop(task.doc_id, None)
                    if not self._heap:
                        self._event.clear()
                    return task

            await asyncio.sleep(0.1)

    async def requeue_with_delay(self, task: QueuedTask, delay: Optional[float] = None):
        if delay is None:
            delay = task.get_retry_delay()

        task.retry_count += 1
        task.scheduled_at = time.time() + delay

        async with self._lock:
            heapq.heappush(self._heap, task)
            self._tasks_by_id[task.task_id] = task
            self._event.set()

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            return await self._remove_task_internal(task_id)

    async def cancel_by_doc_id(self, doc_id: int) -> bool:
        async with self._lock:
            task_id = self._tasks_by_doc_id.get(doc_id)
            if task_id:
                await self._remove_task_internal(task_id)
                return True
        return False

    # ── 死信（委托 DeadLetterStore；threading.Lock 语义不变） ──

    def move_to_dead_letter(self, task: QueuedTask, error: str):
        self._dead_letters.move(task, error)

    def get_dead_letters(self) -> Dict[str, Dict]:
        return self._dead_letters.get_all()

    def clear_dead_letters(self):
        self._dead_letters.clear()

    def retry_dead_letter(self, task_id: str) -> Optional[QueuedTask]:
        return self._dead_letters.pop_for_retry(task_id)

    async def wait_for_task(self, timeout: Optional[float] = None) -> Optional[QueuedTask]:
        while True:
            task = await self.dequeue(timeout=1.0)
            if task:
                return task

            if timeout:
                try:
                    await asyncio.wait_for(self._event.wait(), timeout=min(timeout, 1.0))
                except asyncio.TimeoutError:
                    return None
            else:
                await self._event.wait()

    def size(self) -> int:
        return len(self._tasks_by_id)

    def is_empty(self) -> bool:
        return len(self._tasks_by_id) == 0

    def get_task_ids(self) -> list:
        return list(self._tasks_by_id.keys())

    def get_stats(self) -> Dict:
        priority_counts = defaultdict(int)
        now = time.time()
        ready_count = 0
        delayed_count = 0

        for task in self._tasks_by_id.values():
            priority_counts[task.priority] += 1
            if task.scheduled_at and task.scheduled_at > now:
                delayed_count += 1
            else:
                ready_count += 1

        return {
            "total_tasks": len(self._tasks_by_id),
            "ready_tasks": ready_count,
            "delayed_tasks": delayed_count,
            "priority_distribution": dict(priority_counts),
            "dead_letters": self._dead_letters.count()
        }


def __getattr__(name: str):
    """惰性 re-export worker 管理器（避免与 priority_manager 循环导入）"""
    if name in ("PriorityTaskManager", "priority_task_hub"):
        from core.priority_manager import PriorityTaskManager, priority_task_hub
        return {
            "PriorityTaskManager": PriorityTaskManager,
            "priority_task_hub": priority_task_hub,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
