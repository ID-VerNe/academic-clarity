"""
Academic Clarity - 优先级队列任务模型（TaskPriority / QueuedTask / DeadLetterEntry）
"""
import time
import uuid
from typing import Callable, Dict, Optional
from dataclasses import dataclass, field
from enum import IntEnum

from constants import TaskConfig
from utils.retry import backoff_delay


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
        return backoff_delay(self.retry_count, TaskConfig.RETRY_BACKOFF)

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
