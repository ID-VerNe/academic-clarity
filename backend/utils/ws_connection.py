"""
Academic Clarity - WebSocket 连接管理（连接集合 / 频道订阅 / 广播）

- 单例经 utils.singleton.SingletonMeta（B-DRY-24）
- B-SRP-19：接入 WebSocketConfig.MAX_CONNECTIONS 连接上限，超限拒绝并记日志
- 心跳：_heartbeat_task 字段已删除（从未启动）；客户端心跳由 server.py 端点
  的 pong 逻辑应答，连接管理器不主动发心跳
"""
import asyncio
import time
from typing import Dict, Set, Optional, Any

from constants import WebSocketConfig
from .logger import get_logger
from .singleton import SingletonMeta
from .ws_protocol import EventType, WSMessage

ws_logger = get_logger("websocket")


class ConnectionManager(metaclass=SingletonMeta):
    """WebSocket连接管理器 - 使用asyncio.Lock替代threading.Lock"""

    # 冻结接口：server/routes 通过 `ws_manager.WSMessage.from_json(...)` 解析入站消息
    WSMessage = WSMessage

    def __init__(self):
        self._connections: Set[Any] = set()
        self._connection_lock = asyncio.Lock()
        self._subscribers: Dict[str, Set[Any]] = {
            "task": set(),
            "document": set(),
            "system": set(),
            "all": set()
        }
        self._message_id_counter = 0

    async def connect(self, websocket, channels: Optional[list] = None):
        async with self._connection_lock:
            if len(self._connections) >= WebSocketConfig.MAX_CONNECTIONS:
                ws_logger.error(
                    "WebSocket connection refused: max connections reached",
                    total_connections=len(self._connections),
                    max_connections=WebSocketConfig.MAX_CONNECTIONS,
                )
                raise ConnectionError("WebSocket max connections reached")

            self._connections.add(websocket)
            self._subscribers["all"].add(websocket)

            if channels:
                for channel in channels:
                    if channel != "all" and channel in self._subscribers:
                        self._subscribers[channel].add(websocket)

        await self.broadcast_safe(EventType.SYSTEM_STATUS, {
            "connected": True,
            "total_connections": len(self._connections)
        }, channels=["all"])

    async def disconnect(self, websocket):
        async with self._connection_lock:
            self._connections.discard(websocket)
            for channel_subscribers in self._subscribers.values():
                channel_subscribers.discard(websocket)

        await self.broadcast_safe(EventType.SYSTEM_STATUS, {
            "connected": False,
            "total_connections": len(self._connections)
        }, channels=["all"])

    def _generate_message_id(self) -> str:
        self._message_id_counter += 1
        return f"msg_{self._message_id_counter}_{int(time.time() * 1000)}"

    async def send(self, websocket, event: EventType, data: Dict[str, Any]):
        try:
            message = WSMessage(
                event=event,
                data=data,
                message_id=self._generate_message_id()
            )
            await websocket.send_text(message.to_json())
        except Exception:
            await self.disconnect(websocket)

    async def broadcast_safe(self, event: EventType, data: Dict[str, Any],
                             channels: Optional[list] = None, exclude: Optional[Set] = None):
        """安全的广播 - 捕获所有异常"""
        try:
            await self.broadcast(event, data, channels, exclude)
        except Exception:
            pass

    async def broadcast(self, event: EventType, data: Dict[str, Any],
                        channels: Optional[list] = None, exclude: Optional[Set] = None):
        """向所有订阅的连接广播消息"""
        message = WSMessage(
            event=event,
            data=data,
            message_id=self._generate_message_id()
        )
        message_str = message.to_json()

        async with self._connection_lock:
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
                self._connections.discard(ws)
                for channel_subscribers in self._subscribers.values():
                    channel_subscribers.discard(ws)

    async def send_task_update(self, doc_id: int, status: str, progress: float = 0,
                               message: str = "", metadata: Optional[Dict] = None):
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
        await self.broadcast(EventType.OCR_STATUS_CHANGE, {
            "doc_id": doc_id,
            "old_status": old_status,
            "new_status": new_status,
            **kwargs
        }, channels=["task", "document"])

    def get_connection_count(self) -> int:
        return len(self._connections)

    def get_channel_subscribers(self, channel: str) -> int:
        if channel in self._subscribers:
            return len(self._subscribers[channel])
        return 0


ws_manager = ConnectionManager()
