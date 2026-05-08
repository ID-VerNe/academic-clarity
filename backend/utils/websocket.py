"""
Academic Clarity - WebSocket 实时进度推送服务
支持任务进度、状态变更的实时推送
"""
import asyncio
import json
import time
from typing import Dict, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading

class EventType(str, Enum):
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    DOC_ADDED = "doc_added"
    DOC_UPDATED = "doc_updated"
    DOC_DELETED = "doc_deleted"
    OCR_STATUS_CHANGE = "ocr_status_change"
    KEY_POOL_UPDATE = "key_pool_update"
    SYSTEM_STATUS = "system_status"
    HEARTBEAT = "heartbeat"

@dataclass
class WSMessage:
    event: EventType
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    message_id: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "event": self.event.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "message_id": self.message_id
        })

    @classmethod
    def from_json(cls, raw: str) -> "WSMessage":
        parsed = json.loads(raw)
        return cls(
            event=EventType(parsed["event"]),
            data=parsed["data"],
            timestamp=parsed.get("timestamp", ""),
            message_id=parsed.get("message_id", "")
        )

class ConnectionManager:
    """WebSocket连接管理器"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._connections: Set[Any] = set()
        self._connection_lock = asyncio.Lock()
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._subscribers: Dict[str, Set[Any]] = {
            "task": set(),
            "document": set(),
            "system": set(),
            "all": set()
        }
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._message_id_counter = 0
        self._message_id_lock = threading.Lock()

    async def connect(self, websocket, channels: Optional[list] = None):
        """接受新的WebSocket连接"""
        async with self._connection_lock:
            self._connections.add(websocket)

        channels = channels or ["all"]
        for channel in channels:
            if channel in self._subscribers:
                self._subscribers[channel].add(websocket)
            self._subscribers["all"].add(websocket)

        await self.broadcast(EventType.SYSTEM_STATUS, {
            "connected": True,
            "total_connections": len(self._connections)
        }, channels=["all"])

    async def disconnect(self, websocket):
        """断开WebSocket连接"""
        async with self._connection_lock:
            self._connections.discard(websocket)

        for channel_subscribers in self._subscribers.values():
            channel_subscribers.discard(websocket)

        await self.broadcast(EventType.SYSTEM_STATUS, {
            "connected": False,
            "total_connections": len(self._connections)
        }, channels=["all"])

    def _generate_message_id(self) -> str:
        """生成唯一消息ID"""
        with self._message_id_lock:
            self._message_id_counter += 1
            return f"msg_{self._message_id_counter}_{int(time.time() * 1000)}"

    async def send(self, websocket, event: EventType, data: Dict[str, Any]):
        """向单个连接发送消息"""
        try:
            message = WSMessage(
                event=event,
                data=data,
                message_id=self._generate_message_id()
            )
            await websocket.send_text(message.to_json())
        except Exception as e:
            print(f"[WS] Send error: {e}")
            await self.disconnect(websocket)

    async def broadcast(self, event: EventType, data: Dict[str, Any],
                       channels: Optional[list] = None, exclude: Optional[Set] = None):
        """向所有订阅的连接广播消息"""
        message = WSMessage(
            event=event,
            data=data,
            message_id=self._generate_message_id()
        )
        message_str = message.to_json()

        target_channels = channels or list(self._subscribers.keys())
        targets = set()

        for channel in target_channels:
            if channel in self._subscribers:
                targets.update(self._subscribers[channel])

        if exclude:
            targets -= exclude

        disconnected = set()
        for websocket in targets:
            try:
                await websocket.send_text(message_str)
            except Exception:
                disconnected.add(websocket)

        for ws in disconnected:
            await self.disconnect(ws)

    async def send_task_update(self, doc_id: int, status: str, progress: float = 0,
                              message: str = "", metadata: Optional[Dict] = None):
        """发送任务更新"""
        event_map = {
            "pending": EventType.TASK_STARTED,
            "processing": EventType.TASK_PROGRESS,
            "completed": EventType.TASK_COMPLETED,
            "failed": EventType.TASK_FAILED,
        }

        event = event_map.get(status, EventType.TASK_PROGRESS)

        await self.broadcast(event, {
            "doc_id": doc_id,
            "status": status,
            "progress": progress,
            "message": message,
            "metadata": metadata or {}
        }, channels=["task"])

    async def send_document_update(self, action: str, doc_id: int,
                                   document: Optional[Dict] = None):
        """发送文档更新"""
        event_map = {
            "added": EventType.DOC_ADDED,
            "updated": EventType.DOC_UPDATED,
            "deleted": EventType.DOC_DELETED,
        }

        event = event_map.get(action, EventType.DOC_UPDATED)

        await self.broadcast(event, {
            "doc_id": doc_id,
            "document": document
        }, channels=["document"])

    async def send_ocr_status_change(self, doc_id: int, old_status: str,
                                     new_status: str, **kwargs):
        """发送OCR状态变更"""
        await self.broadcast(EventType.OCR_STATUS_CHANGE, {
            "doc_id": doc_id,
            "old_status": old_status,
            "new_status": new_status,
            **kwargs
        }, channels=["task", "document"])

    async def send_key_pool_update(self, service: str, stats: Dict):
        """发送密钥池更新"""
        await self.broadcast(EventType.KEY_POOL_UPDATE, {
            "service": service,
            "stats": stats
        }, channels=["system"])

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self._connections)

    def get_channel_subscribers(self, channel: str) -> int:
        """获取频道订阅者数量"""
        if channel in self._subscribers:
            return len(self._subscribers[channel])
        return 0

ws_manager = ConnectionManager()

class WebSocketProgressTracker:
    """任务进度追踪器 - 与WebSocket集成"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._active_tasks: Dict[int, Dict] = {}

    async def track_task_start(self, doc_id: int, task_type: str = "ocr"):
        """开始追踪任务"""
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
        """追踪任务进度"""
        if doc_id not in self._active_tasks:
            await self.track_task_start(doc_id)

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
        """追踪任务完成"""
        if doc_id in self._active_tasks:
            task = self._active_tasks[doc_id]
            duration = time.time() - task["start_time"]
            task["duration"] = duration
            del self._active_tasks[doc_id]

        await ws_manager.send_task_update(doc_id, "completed", 100, "Task completed", result)

    async def track_task_failure(self, doc_id: int, error: str):
        """追踪任务失败"""
        if doc_id in self._active_tasks:
            task = self._active_tasks[doc_id]
            duration = time.time() - task["start_time"]
            task["duration"] = duration
            task["error"] = error
            del self._active_tasks[doc_id]

        await ws_manager.send_task_update(doc_id, "failed", 0, error)

    def get_active_tasks(self) -> Dict[int, Dict]:
        """获取当前活动任务"""
        return dict(self._active_tasks)

progress_tracker = WebSocketProgressTracker()
