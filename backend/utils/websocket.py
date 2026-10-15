"""
Academic Clarity - WebSocket 实时进度推送服务（门面）

实现拆分：
- ws_protocol.py   协议层（EventType / WSMessage）
- ws_connection.py 连接管理（ConnectionManager / ws_manager）
- ws_progress.py   进度追踪（WebSocketProgressTracker / progress_tracker）

本模块仅做向后兼容 re-export，既有 `from utils.websocket import ...` 不受影响。
"""
from .ws_protocol import EventType, WSMessage
from .ws_connection import ConnectionManager, ws_manager
from .ws_progress import WebSocketProgressTracker, progress_tracker

__all__ = [
    "EventType",
    "WSMessage",
    "ConnectionManager",
    "ws_manager",
    "WebSocketProgressTracker",
    "progress_tracker",
]
