"""
Academic Clarity - 死信存储

threading.Lock 保护（与队列主体的 asyncio.Lock 区分，拆分时保持原语义：
死信读写发生在 worker 的同步路径上）。
"""
import threading
import time
from typing import Dict, Optional

from core.priority_models import DeadLetterEntry, QueuedTask


class DeadLetterStore:
    """死信队列存储"""

    def __init__(self):
        self._entries: Dict[str, DeadLetterEntry] = {}
        self._lock = threading.Lock()

    def move(self, task: QueuedTask, error: str):
        """任务移入死信；同一任务重复失败时累计 failure_count"""
        with self._lock:
            if task.task_id in self._entries:
                entry = self._entries[task.task_id]
                entry.failure_count += 1
                entry.error = error
                entry.failed_at = time.time()
            else:
                self._entries[task.task_id] = DeadLetterEntry(task, error, time.time())

    def get_all(self) -> Dict[str, Dict]:
        with self._lock:
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
                for task_id, entry in self._entries.items()
            }

    def clear(self):
        with self._lock:
            self._entries.clear()

    def pop_for_retry(self, task_id: str) -> Optional[QueuedTask]:
        """取出死信任务并重置重试状态（供重新入队）"""
        with self._lock:
            if task_id in self._entries:
                entry = self._entries.pop(task_id)
                entry.task.retry_count = 0
                entry.task.scheduled_at = None
                return entry.task
        return None

    def count(self) -> int:
        return len(self._entries)
