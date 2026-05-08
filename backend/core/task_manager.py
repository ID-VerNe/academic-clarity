import asyncio
import os
import time
from datetime import datetime
from typing import Dict, Optional

try:
    from backend.config import TaskConfig
except ImportError:
    from config import TaskConfig

class TaskManager:
    def __init__(self, concurrency=None):
        if concurrency is None:
            concurrency = TaskConfig.DEFAULT_CONCURRENCY
        self.queue = asyncio.Queue()
        self.concurrency = concurrency
        self.workers = []
        self.active_task_ids: set = set()
        self.failed_task_ids: Dict[int, tuple] = {}

    async def start_workers(self, app_state):
        """启动指定数量的并行 Worker"""
        print(f"[TaskHub] Launching {self.concurrency} parallel workers...")
        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker_loop(i, app_state))
            self.workers.append(worker)

    async def add_task(self, doc_id, task_func, *args):
        """向队尾添加任务"""
        if doc_id in self.active_task_ids:
            print(f"[TaskHub] Doc {doc_id} already in queue, skipping")
            return

        if doc_id in self.failed_task_ids:
            fail_count, last_fail = self.failed_task_ids[doc_id]
            if fail_count >= TaskConfig.MAX_RETRIES:
                print(f"[TaskHub] Doc {doc_id} exceeded max retries ({fail_count}), skipping")
                return

        self.active_task_ids.add(doc_id)
        await self.queue.put((doc_id, task_func, args, 0))

    async def _worker_loop(self, worker_id, app_state):
        """Worker 循环认领任务"""
        while True:
            doc_id, task_func, args, retries = await self.queue.get()
            print(f"[Worker-{worker_id}] Claimed task for Doc ID: {doc_id}")

            try:
                await task_func(doc_id, *args, db=app_state.db)
                self.active_task_ids.discard(doc_id)
                self.failed_task_ids.pop(doc_id, None)
                print(f"[Worker-{worker_id}] Task SUCCESS for Doc: {doc_id}")
            except Exception as e:
                print(f"[Worker-{worker_id}] Task FAILED for Doc: {doc_id}. Error: {e}")

                if retries < TaskConfig.MAX_RETRIES:
                    backoff = TaskConfig.RETRY_BACKOFF[retries] if retries < len(TaskConfig.RETRY_BACKOFF) else TaskConfig.RETRY_BACKOFF[-1]
                    print(f"[Worker-{worker_id}] Scheduling retry {retries + 1}/{TaskConfig.MAX_RETRIES} for Doc {doc_id} with backoff {backoff}s")
                    await asyncio.sleep(backoff)

                    self.failed_task_ids[doc_id] = (retries + 1, time.time())
                    await self.queue.put((doc_id, task_func, args, retries + 1))
                else:
                    self.active_task_ids.discard(doc_id)
                    self.failed_task_ids[doc_id] = (retries, time.time())
                    print(f"[Worker-{worker_id}] Max retries reached for Doc: {doc_id}. Giving up.")

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

task_hub = TaskManager()
