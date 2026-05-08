"""
Academic Clarity - 优先级任务队列
支持任务优先级、延迟执行、死信队列、重试策略
"""
import asyncio
import time
import heapq
import uuid
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import IntEnum
from collections import defaultdict
import threading

try:
    from backend.constants import TaskConfig
except ImportError:
    class TaskConfig:
        DEFAULT_CONCURRENCY = 10
        MAX_RETRIES = 3
        RETRY_BACKOFF = [1, 5, 30]
        MAX_FAILED_TASKS = 100

class TaskPriority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4

@dataclass
class QueuedTask:
    priority: int
    doc_id: int
    task_func: Callable
    args: tuple
    kwargs: dict
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scheduled_at: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

    def __lt__(self, other: "QueuedTask") -> bool:
        if self.scheduled_at and other.scheduled_at:
            return (self.scheduled_at, self.priority) < (other.scheduled_at, other.priority)
        elif self.scheduled_at:
            return False
        elif other.scheduled_at:
            return True
        return (self.priority, self.created_at) < (other.priority, other.created_at)

    def can_retry(self, max_retries: int = TaskConfig.MAX_RETRIES) -> bool:
        return self.retry_count < max_retries

    def get_retry_delay(self) -> float:
        backoff = TaskConfig.RETRY_BACKOFF
        idx = min(self.retry_count, len(backoff) - 1)
        return backoff[idx]

    def is_ready(self) -> bool:
        if self.scheduled_at is None:
            return True
        return time.time() >= self.scheduled_at

@dataclass
class DeadLetterEntry:
    task: QueuedTask
    error: str
    failed_at: float
    failure_count: int = 1

class PriorityTaskQueue:
    def __init__(self):
        self._heap: list = []
        self._tasks_by_id: Dict[str, QueuedTask] = {}
        self._tasks_by_doc_id: Dict[int, str] = {}
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()
        self._dead_letters: Dict[str, DeadLetterEntry] = {}
        self._dead_letter_lock = threading.Lock()

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

    def move_to_dead_letter(self, task: QueuedTask, error: str):
        with self._dead_letter_lock:
            if task.task_id in self._dead_letters:
                entry = self._dead_letters[task.task_id]
                entry.failure_count += 1
                entry.error = error
                entry.failed_at = time.time()
            else:
                self._dead_letters[task.task_id] = DeadLetterEntry(task, error, time.time())

    def get_dead_letters(self) -> Dict[str, Dict]:
        with self._dead_letter_lock:
            return {
                task_id: {
                    "task_id": entry.task.task_id,
                    "doc_id": entry.task.doc_id,
                    "priority": entry.task.priority,
                    "retry_count": entry.task.retry_count,
                    "error": entry.error,
                    "failed_at": entry.failed_at,
                    "failure_count": entry.failure_count
                }
                for task_id, entry in self._dead_letters.items()
            }

    def clear_dead_letters(self):
        with self._dead_letter_lock:
            self._dead_letters.clear()

    def retry_dead_letter(self, task_id: str) -> Optional[QueuedTask]:
        with self._dead_letter_lock:
            if task_id in self._dead_letters:
                entry = self._dead_letters.pop(task_id)
                entry.task.retry_count = 0
                entry.task.scheduled_at = None
                return entry.task
        return None

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
            if task.scheduled_at:
                if task.scheduled_at <= now:
                    ready_count += 1
                else:
                    delayed_count += 1
            else:
                ready_count += 1

        return {
            "total_tasks": len(self._tasks_by_id),
            "ready_tasks": ready_count,
            "delayed_tasks": delayed_count,
            "priority_distribution": dict(priority_counts),
            "dead_letters": len(self._dead_letters)
        }

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
