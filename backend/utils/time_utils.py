"""
Academic Clarity - 时间工具

统一 UTC ISO-8601 时间戳格式（B-DRY-18）：秒级精度 + "Z" 后缀。
输出格式与 websocket 历史格式（%Y-%m-%dT%H:%M:%SZ）保持兼容。
"""
from datetime import datetime, timezone

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now_iso() -> str:
    """当前 UTC 时间的 ISO-8601 表示（形如 2024-01-01T12:00:00Z）"""
    return datetime.now(timezone.utc).strftime(ISO_FORMAT)
