"""
Academic Clarity - WebSocket 协议层（事件类型 / 消息封装）
"""
import json
from typing import Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from .time_utils import utc_now_iso


class EventType(str, Enum):
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    DOC_ADDED = "doc_added"
    DOC_UPDATED = "doc_updated"
    DOC_DELETED = "doc_deleted"
    OCR_STATUS_CHANGE = "ocr_status_change"
    SYSTEM_STATUS = "system_status"
    HEARTBEAT = "heartbeat"


@dataclass
class WSMessage:
    event: EventType
    data: Dict[str, Any]
    timestamp: str = field(default_factory=utc_now_iso)
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
