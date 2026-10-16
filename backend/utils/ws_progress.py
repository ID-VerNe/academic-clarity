"""
Academic Clarity - 任务进度追踪（内存状态机 + 广播）

状态机语义保持原样：track_task_start/progress/complete/failure 更新
_active_tasks 并经 ws_manager 广播；get_stage 提供 /tasks 轮询快照。
"""
import asyncio
import time
from typing import Dict, Optional

from .singleton import SingletonMeta
from .ws_connection import ws_manager


class WebSocketProgressTracker(metaclass=SingletonMeta):
    """任务进度追踪器"""

    def __init__(self):
        self._active_tasks: Dict[int, Dict] = {}
        self._lock = asyncio.Lock()

    async def track_task_start(self, doc_id: int, task_type: str = "ocr"):
        async with self._lock:
            self._active_tasks[doc_id] = {
                "type": task_type,
                "start_time": time.time(),
                "progress": 0,
                "last_update": time.time(),
                "steps": []
            }
        await ws_manager.send_task_update(doc_id, "pending", 0, "Task started")

    async def track_task_progress(self, doc_id: int, progress: float,
                                  step: Optional[str] = None):
        async with self._lock:
            if doc_id not in self._active_tasks:
                self._active_tasks[doc_id] = {
                    "type": "ocr",
                    "start_time": time.time(),
                    "progress": 0,
                    "last_update": time.time(),
                    "steps": []
                }

            task = self._active_tasks[doc_id]
            task["progress"] = progress
            task["last_update"] = time.time()
            if step:
                task["steps"].append({
                    "step": step,
                    "timestamp": time.time()
                })

        await ws_manager.send_task_update(doc_id, "processing", progress, step)

    async def track_task_complete(self, doc_id: int, result: Optional[Dict] = None):
        async with self._lock:
            if doc_id in self._active_tasks:
                task = self._active_tasks[doc_id]
                duration = time.time() - task["start_time"]
                task["duration"] = duration
                del self._active_tasks[doc_id]

        await ws_manager.send_task_update(doc_id, "completed", 100, "Task completed", result)

    async def track_task_failure(self, doc_id: int, error: str):
        async with self._lock:
            if doc_id in self._active_tasks:
                task = self._active_tasks[doc_id]
                duration = time.time() - task["start_time"]
                task["duration"] = duration
                task["error"] = error
                del self._active_tasks[doc_id]

        await ws_manager.send_task_update(doc_id, "failed", 0, error)

    def get_active_tasks(self) -> Dict[int, Dict]:
        return dict(self._active_tasks)

    def get_stage(self, doc_id: int) -> Optional[Dict]:
        """当前阶段快照（供 /tasks 轮询合并展示；无记录返回 None）"""
        task = self._active_tasks.get(doc_id)
        if not task:
            return None
        steps = task.get("steps") or []
        return {
            "stage": steps[-1]["step"] if steps else "已加入队列",
            "progress": task.get("progress", 0),
            "elapsed": round(time.time() - task.get("start_time", time.time()), 1),
        }


progress_tracker = WebSocketProgressTracker()
