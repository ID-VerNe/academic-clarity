"""
Academic Clarity - 重试退避工具

统一各处的退避表取值 + 越界 clamp 逻辑（B-DRY-06）。
"""
from typing import Sequence


def backoff_delay(attempt: int, schedule: Sequence[float]) -> float:
    """从退避表取第 attempt 次（0 起）重试延迟。

    超出表长时 clamp 到最后一档；attempt 为负按 0 处理；空表返回 0。
    """
    if not schedule:
        return 0.0
    idx = min(max(attempt, 0), len(schedule) - 1)
    return schedule[idx]
