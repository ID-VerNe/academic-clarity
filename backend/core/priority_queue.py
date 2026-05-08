"""
Academic Clarity - Priority Task Queue
基于优先级的任务队列，支持多优先级和任务依赖
"""

import asyncio
import time
import heapq
from typing import Dict, Set, Optional, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from collections import defaultdict
import threading

try:
    from backend.constants import TaskConfig
except ImportError:
    class TaskConfig:
        DEFAULT_CONCURRENCY = 10

class Priority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4

@dataclass(order=True)
class PrioritizedTask:
    priority: int
    created_at: float = field(compare=False)
    doc_id: int = field(compare=False)
    task_id: str = field(compare=False)
    task_func: Callable = field(compare=False)
    args: tuple = field(compare=False)
    kwargs: dict = field(compare=False)
    retry_count: int = field(compare=False, default=0)
    dependencies: Set[str] = field(compare=False, default_factory=set)
    metadata: Dict = field(compare=False, default_factory=dict)

    def __hash__(self):
        return hash(self.task_id)

@dataclass
class TaskResult:
    task_id: str
    doc_id: int
    status: str
    result: Any = None
    error: str = None
    started_at: float = field(default_factory=time.time)
    completed_at: float = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "doc_id": self.doc_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "duration_seconds": round(self.completed_at - self.started_at, 2) if self.completed_at else None,
            "started_at": datetime.fromtimestamp(self.started_at).isoformat(),
            "completed_at": datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None
        }

class PriorityTaskQueue:
    def __init__(self):
        self._queues: Dict[Priority, list] = {
            priority: [] for priority in Priority
        }
        self._task_map: Dict[str, PrioritizedTask] = {}
        self._running_tasks: Dict[str, PrioritizedTask] = {}
        self._completed_tasks: Dict[str, TaskResult] = {}
        self._task_counter = 0
        self._counter_lock = threading.Lock()

    def _generate_task_id(self) -> str:
        with self._counter_lock:
            self._task_counter += 1
            return f"task_{self._task_counter}_{int(time.time() * 1000)}"

    def enqueue(
        self,
        doc_id: int,
        task_func: Callable,
        *args,
        priority: Priority = Priority.NORMAL,
        dependencies: Set[str] = None,
        metadata: Dict = None,
        **kwargs
    ) -> str:
        task_id = self._generate_task_id()

        task = PrioritizedTask(
            priority=priority.value,
            created_at=time.time(),
            doc_id=doc_id,
            task_id=task_id,
            task_func=task_func,
            args=args,
            kwargs=kwargs,
            dependencies=dependencies or set(),
            metadata=metadata or {}
        )

        self._task_map[task_id] = task
        heapq.heappush(self._queues[Priority(priority)], (task.priority, task.created_at, task_id))

        return task_id

    def _check_dependencies(self, task: PrioritizedTask) -> bool:
        for dep_id in task.dependencies:
            if dep_id in self._running_tasks:
                return False
            if dep_id not in self._completed_tasks:
                return False
            result = self._completed_tasks[dep_id]
            if result.status != "completed":
                return False
        return True

    def dequeue(self) -> Optional[PrioritizedTask]:
        for priority in Priority:
            queue = self._queues[priority]
            while queue:
                _, _, task_id = heapq.heappop(queue)
                task = self._task_map.get(task_id)

                if task is None:
                    continue

                if task_id in self._completed_tasks:
                    continue

                if self._check_dependencies(task):
                    self._running_tasks[task_id] = task
                    return task
                else:
                    heapq.heappush(queue, (task.priority, task.created_at, task_id))
                    break

        return None

    def mark_running(self, task_id: str) -> bool:
        if task_id in self._task_map:
            task = self._task_map[task_id]
            self._running_tasks[task_id] = task
            return True
        return False

    def mark_completed(self, task_id: str, result: Any = None):
        if task_id in self._running_tasks:
            task = self._running_tasks.pop(task_id)
            self._completed_tasks[task_id] = TaskResult(
                task_id=task_id,
                doc_id=task.doc_id,
                status="completed",
                result=result,
                completed_at=time.time()
            )
            return True
        return False

    def mark_failed(self, task_id: str, error: str):
        if task_id in self._running_tasks:
            task = self._running_tasks.pop(task_id)
            self._completed_tasks[task_id] = TaskResult(
                task_id=task_id,
                doc_id=task.doc_id,
                status="failed",
                error=error,
                completed_at=time.time()
            )
            return True
        return False

    def get_task_status(self, task_id: str) -> Optional[str]:
        if task_id in self._running_tasks:
            return "running"
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id].status
        if task_id in self._task_map:
            return "queued"
        return None

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        return self._completed_tasks.get(task_id)

    def get_queue_size(self, priority: Priority = None) -> int:
        if priority is not None:
            return len(self._queues[priority])
        return sum(len(q) for q in self._queues.values())

    def get_stats(self) -> Dict:
        return {
            "queued": self.get_queue_size(),
            "queued_by_priority": {
                priority.name: len(self._queues[priority])
                for priority in Priority
            },
            "running": len(self._running_tasks),
            "completed": len(self._completed_tasks),
            "failed": sum(1 for r in self._completed_tasks.values() if r.status == "failed"),
            "total": len(self._task_map)
        }

    def clear_completed(self, before_timestamp: float = None):
        if before_timestamp is None:
            before_timestamp = time.time() - 3600

        to_remove = [
            task_id for task_id, result in self._completed_tasks.items()
            if result.completed_at < before_timestamp
        ]

        for task_id in to_remove:
            del self._completed_tasks[task_id]
            self._task_map.pop(task_id, None)

        return len(to_remove)

class PriorityTaskManager:
    """带优先级的任务管理器"""

    def __init__(self, concurrency: int = None):
        if concurrency is None:
            concurrency = TaskConfig.DEFAULT_CONCURRENCY
        self._queue = PriorityTaskQueue()
        self._concurrency = concurrency
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._worker_semaphore = asyncio.Semaphore(concurrency)
        self._active_tasks: Dict[str, asyncio.Task] = {}

    async def start(self):
        self._running = True
        for i in range(self._concurrency):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def stop(self):
        self._running = False
        for worker in self._workers:
            worker.cancel()
        for task in self._active_tasks.values():
            task.cancel()
        await asyncio.gather(*self._workers, *self._active_tasks.values(), return_exceptions=True)
        self._workers.clear()
        self._active_tasks.clear()

    async def _worker(self, worker_id: int):
        while self._running:
            async with self._worker_semaphore:
                task = self._queue.dequeue()
                if task is None:
                    await asyncio.sleep(0.1)
                    continue

                self._queue.mark_running(task.task_id)
                active_task = asyncio.create_task(self._execute_task(task, worker_id))
                self._active_tasks[task.task_id] = active_task

                try:
                    await active_task
                finally:
                    self._active_tasks.pop(task.task_id, None)

    async def _execute_task(self, task: PrioritizedTask, worker_id: int):
        try:
            result = await task.task_func(task.doc_id, *task.args, **task.kwargs)
            self._queue.mark_completed(task.task_id, result)
        except Exception as e:
            self._queue.mark_failed(task.task_id, str(e))

    def add_task(
        self,
        doc_id: int,
        task_func: Callable,
        *args,
        priority: Priority = Priority.NORMAL,
        dependencies: Set[str] = None,
        **kwargs
    ) -> str:
        return self._queue.enqueue(
            doc_id=doc_id,
            task_func=task_func,
            *args,
            priority=priority,
            dependencies=dependencies,
            **kwargs
        )

    def get_task_status(self, task_id: str) -> Optional[str]:
        return self._queue.get_task_status(task_id)

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        return self._queue.get_task_result(task_id)

    def get_stats(self) -> Dict:
        stats = self._queue.get_stats()
        stats["concurrency"] = self._concurrency
        stats["active"] = len(self._active_tasks)
        return stats

priority_task_manager = PriorityTaskManager()

def get_priority_queue() -> PriorityTaskQueue:
    return priority_task_manager._queue

def get_priority_task_manager() -> PriorityTaskManager:
    return priority_task_manager
