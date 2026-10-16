"""
Academic Clarity - task_hub 重试调度与失败记录

语义边界（与 core.priority_queue 的区别见 core/README.md）：
- 失败计数按 doc_id 累计；达到 TaskConfig.MAX_RETRIES 后阻止重新入队（除非 force）
- 重试为非阻塞调度（独立 asyncio.Task），退避期间不占用 worker
- 失败记录超上限时按时间淘汰最旧记录（防内存增长）
"""
import asyncio
import time
from typing import Callable, Dict, Tuple

from constants import TaskConfig
from utils.retry import backoff_delay


class TaskRetryTracker:
    """失败记录（doc_id -> (retries, last_fail)）+ 重试调度 + 过期清理"""

    def __init__(self):
        self.failed_task_ids: Dict[int, Tuple[int, float]] = {}

    def cleanup_old_failures(self):
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

    def record_failure(self, doc_id: int, retries: int):
        self.failed_task_ids[doc_id] = (retries, time.time())
        self.cleanup_old_failures()

    async def schedule_retry(self, doc_id: int, task_func: Callable, args: tuple,
                             retries: int, queue: asyncio.Queue):
        """非阻塞方式调度重试，避免阻塞 worker"""
        backoff = backoff_delay(retries, TaskConfig.RETRY_BACKOFF)
        print(f"[TaskHub] Scheduling retry {retries}/{TaskConfig.MAX_RETRIES} for Doc {doc_id} in {backoff}s (non-blocking)")
        await asyncio.sleep(backoff)
        self.record_failure(doc_id, retries)
        await queue.put((doc_id, task_func, args, retries))

    async def cleanup_loop(self):
        """定期清理失败的记录"""
        while True:
            await asyncio.sleep(300)
            self.cleanup_old_failures()
