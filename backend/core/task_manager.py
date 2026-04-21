import asyncio
import os
from datetime import datetime

class TaskManager:
    def __init__(self, concurrency=10):
        self.queue = asyncio.Queue()
        self.concurrency = concurrency
        self.workers = []
        self.active_task_ids = set() # 防止同一文档重复入队

    async def start_workers(self, app_state):
        """启动指定数量的并行 Worker"""
        print(f"[TaskHub] Launching {self.concurrency} parallel workers...")
        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker_loop(i, app_state))
            self.workers.append(worker)

    async def add_task(self, doc_id, task_func, *args):
        """向队尾添加任务"""
        if doc_id in self.active_task_ids:
            return
        self.active_task_ids.add(doc_id)
        await self.queue.put((doc_id, task_func, args, 0)) # 0 是重试次数

    async def _worker_loop(self, worker_id, app_state):
        """Worker 循环认领任务"""
        while True:
            doc_id, task_func, args, retries = await self.queue.get()
            print(f"[Worker-{worker_id}] Claimed task for Doc ID: {doc_id}")
            
            try:
                # 传入 app_state 里的 db 确保上下文一致
                await task_func(doc_id, *args, db=app_state.db)
                self.active_task_ids.remove(doc_id)
                print(f"[Worker-{worker_id}] Task SUCCESS for Doc: {doc_id}")
            except Exception as e:
                print(f"[Worker-{worker_id}] Task FAILED for Doc: {doc_id}. Error: {e}")
                
                # 失败重试逻辑：append 到队尾
                if retries < 5: # 最多重试 5 次
                    print(f"[Worker-{worker_id}] Appending Doc {doc_id} to end of queue for retry.")
                    await asyncio.sleep(2) # 稍微喘息一下，防止无限循环
                    await self.queue.put((doc_id, task_func, args, retries + 1))
                else:
                    self.active_task_ids.remove(doc_id)
                    print(f"[Worker-{worker_id}] Max retries reached for Doc: {doc_id}. Giving up.")
            
            self.queue.task_done()

# 单例模式
task_hub = TaskManager(concurrency=10)
