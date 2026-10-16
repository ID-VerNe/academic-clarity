"""
Academic Clarity - 指标时间序列存储（滑动窗口）

仅保留最近 RETENTION_SECONDS 秒的数据点，防止内存无限增长。
"""
import time
from typing import Dict, List
from dataclasses import dataclass
from collections import defaultdict

RETENTION_SECONDS = 3600


@dataclass
class TimeSeriesPoint:
    """时间序列数据点"""
    timestamp: float
    value: float


class TimeSeriesStore:
    """滑动窗口时间序列（默认保留最近 1 小时）"""

    def __init__(self, retention_seconds: float = RETENTION_SECONDS):
        self._retention = retention_seconds
        self._series: Dict[str, List[TimeSeriesPoint]] = defaultdict(list)

    def add_point(self, name: str, value: float):
        """添加数据点并淘汰窗口外的旧点"""
        self._series[name].append(TimeSeriesPoint(timestamp=time.time(), value=value))
        cutoff = time.time() - self._retention
        self._series[name] = [
            p for p in self._series[name] if p.timestamp > cutoff
        ]
