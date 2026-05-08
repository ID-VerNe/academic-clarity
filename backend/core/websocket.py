"""
Academic Clarity - WebSocket Event System
提供WebSocket实时进度推送功能
"""

import asyncio
import json
import time
from typing import Dict, Set, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from threading import Lock
from collections import defaultdict

try:
    from backend.constants import TaskConfig
except ImportError:
    from TaskConfig = None

class EventType(str, Enum):
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_QUEUED = "task_queued"
    TASK_RETRY = "task_retry"
    OCR_PAGE_START = "ocr_page_start"
    OCR_PAGE_COMPLETE = "ocr_page_complete"
    OCR_PAGE_FAILED = "ocr_page_failed"
    OCR_EXTRACTION_START = "ocr_extraction_start"
    OCR_EXTRACTION_COMPLETE = "ocr_extraction_complete"
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_UPDATED = "document_updated"
    KEY_POOL_UPDATED = "key_pool_updated"
    SYSTEM_STATUS = "system_status"

@dataclass
class Event:
    type: EventType
    doc_id: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source: str = "backend"

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "doc_id": self.doc_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

class WebSocketConnection:
    def __init__(self, websocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.subscriptions: Set[EventType] = set()
        self.doc_subscriptions: Set[int] = set()
        self._alive = True

    async def send_event(self, event: Event):
        if not self._alive:
            return
        try:
            await self.websocket.send_text(event.to_json())
        except Exception as e:
            self._alive = False

    async def send_message(self, type_: str, data: Dict):
        event = Event(type=EventType(type_), data=data)
        await self.send_event(event)

    def subscribe(self, event_types: Set[EventType]):
        self.subscriptions.update(event_types)

    def subscribe_to_document(self, doc_id: int):
        self.doc_subscriptions.add(doc_id)

    def unsubscribe_from_document(self, doc_id: int):
        self.doc_subscriptions.discard(doc_id)

    def is_interested(self, event: Event) -> bool:
        if EventType(type_) in self.subscriptions:
            return True
        if event.doc_id and event.doc_id in self.doc_subscriptions:
            return True
        return False

    def is_alive(self) -> bool:
        return self._alive

class EventBus:
    """事件总线 - 管理所有WebSocket连接和事件分发"""

    _instance = None
    _lock = Lock()

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

        self._connections: Dict[str, WebSocketConnection] = {}
        self._connection_counter = 0
        self._conn_lock = Lock()
        self._event_handlers: Dict[EventType, list] = defaultdict(list)
        self._history: list = []
        self._max_history = 100

    def register_connection(self, websocket) -> str:
        with self._conn_lock:
            self._connection_counter += 1
            client_id = f"client_{self._connection_counter}"
            conn = WebSocketConnection(websocket, client_id)
            self._connections[client_id] = conn
            return client_id

    def unregister_connection(self, client_id: str):
        with self._conn_lock:
            if client_id in self._connections:
                self._connections[client_id]._alive = False
                del self._connections[client_id]

    async def broadcast(self, event: Event, include_source: bool = True):
        if include_source and event.source == "backend":
            pass

        self._add_to_history(event)

        dead_connections = []
        for client_id, conn in self._connections.items():
            if not conn.is_alive():
                dead_connections.append(client_id)
                continue

            if conn.is_interested(event):
                await conn.send_event(event)

        for client_id in dead_connections:
            self.unregister_connection(client_id)

    async def send_to_document_subscribers(self, doc_id: int, event: Event):
        """仅发送给订阅了该文档的客户端"""
        event.doc_id = doc_id
        await self.broadcast(event)

    def add_handler(self, event_type: EventType, handler: Callable):
        self._event_handlers[event_type].append(handler)

    def remove_handler(self, event_type: EventType, handler: Callable):
        if event_type in self._event_handlers:
            self._event_handlers[event_type].remove(handler)

    async def emit(self, event: Event):
        """触发事件，同时调用处理器并广播"""
        for handler in self._event_handlers.get(event.type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                print(f"[EventBus] Handler error: {e}")

        await self.broadcast(event)

    def _add_to_history(self, event: Event):
        self._history.append(event.to_dict())
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(self, event_type: EventType = None, limit: int = 50) -> list:
        if event_type:
            filtered = [e for e in self._history if e["type"] == event_type.value]
            return filtered[-limit:]
        return self._history[-limit:]

    def get_connection_count(self) -> int:
        with self._conn_lock:
            return sum(1 for c in self._connections.values() if c.is_alive())

    def get_stats(self) -> Dict:
        with self._conn_lock:
            return {
                "total_connections": len(self._connections),
                "alive_connections": sum(1 for c in self._connections.values() if c.is_alive()),
                "event_types_subscribed": len(self._event_handlers),
                "history_size": len(self._history)
            }

class TaskProgressTracker:
    """任务进度追踪器"""

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._progress: Dict[int, Dict] = {}
        self._lock = Lock()

    def start_task(self, doc_id: int, task_type: str, total_steps: int = 1):
        with self._lock:
            self._progress[doc_id] = {
                "task_type": task_type,
                "status": "running",
                "current_step": 0,
                "total_steps": total_steps,
                "started_at": time.time(),
                "steps": []
            }
        event = Event(
            type=EventType.TASK_STARTED,
            doc_id=doc_id,
            data={"task_type": task_type, "total_steps": total_steps}
        )
        asyncio.create_task(self._event_bus.emit(event))

    def update_progress(self, doc_id: int, step: int, step_name: str = "", metadata: Dict = None):
        with self._lock:
            if doc_id not in self._progress:
                return
            self._progress[doc_id]["current_step"] = step
            if step_name:
                self._progress[doc_id]["steps"].append({
                    "step": step,
                    "name": step_name,
                    "timestamp": time.time()
                })
            progress_data = dict(self._progress[doc_id])
            progress_data["percent"] = round((step / self._progress[doc_id]["total_steps"]) * 100, 1)
            if metadata:
                progress_data.update(metadata)

        event = Event(
            type=EventType.TASK_PROGRESS,
            doc_id=doc_id,
            data=progress_data
        )
        asyncio.create_task(self._event_bus.emit(event))

    def complete_task(self, doc_id: int, result: Dict = None):
        with self._lock:
            if doc_id not in self._progress:
                return
            self._progress[doc_id]["status"] = "completed"
            self._progress[doc_id]["completed_at"] = time.time()
            duration = self._progress[doc_id]["completed_at"] - self._progress[doc_id]["started_at"]
            completion_data = {
                "task_type": self._progress[doc_id]["task_type"],
                "duration_seconds": round(duration, 2)
            }
            if result:
                completion_data["result"] = result

        event = Event(
            type=EventType.TASK_COMPLETED,
            doc_id=doc_id,
            data=completion_data
        )
        asyncio.create_task(self._event_bus.emit(event))

        del self._progress[doc_id]

    def fail_task(self, doc_id: int, error: str):
        with self._lock:
            if doc_id not in self._progress:
                return
            self._progress[doc_id]["status"] = "failed"
            self._progress[doc_id]["failed_at"] = time.time()
            duration = self._progress[doc_id]["failed_at"] - self._progress[doc_id]["started_at"]

        event = Event(
            type=EventType.TASK_FAILED,
            doc_id=doc_id,
            data={
                "task_type": self._progress[doc_id]["task_type"],
                "error": error,
                "duration_seconds": round(duration, 2)
            }
        )
        asyncio.create_task(self._event_bus.emit(event))

    def get_progress(self, doc_id: int) -> Optional[Dict]:
        with self._lock:
            return self._progress.get(doc_id)

event_bus = EventBus()
progress_tracker = TaskProgressTracker(event_bus)

def get_event_bus() -> EventBus:
    return event_bus

def get_progress_tracker() -> TaskProgressTracker:
    return progress_tracker
