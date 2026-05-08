"""
Academic Clarity - Prometheus 指标导出
提供系统运行时的各类指标收集和导出
"""
import time
import threading
from typing import Dict, List, Optional, Callable
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

try:
    from backend.constants import APIConfig
except ImportError:
    from constants import APIConfig

@dataclass
class TimeSeriesPoint:
    """时间序列数据点"""
    timestamp: float
    value: float

class MetricsCollector:
    """应用指标收集器"""
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

        self.api_requests_total = Counter(
            'academic_clarity_api_requests_total',
            'Total API requests',
            ['endpoint', 'method', 'status']
        )

        self.api_request_duration = Histogram(
            'academic_clarity_api_request_duration_seconds',
            'API request duration in seconds',
            ['endpoint', 'method'],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )

        self.tasks_total = Counter(
            'academic_clarity_tasks_total',
            'Total tasks processed',
            ['status']
        )

        self.tasks_in_progress = Gauge(
            'academic_clarity_tasks_in_progress',
            'Number of tasks currently in progress'
        )

        self.tasks_queued = Gauge(
            'academic_clarity_tasks_queued',
            'Number of tasks in queue'
        )

        self.api_key_usage = Gauge(
            'academic_clarity_api_key_usage',
            'API key usage metrics',
            ['service', 'api_key_prefix']
        )

        self.api_key_health = Gauge(
            'academic_clarity_api_key_health',
            'API key health status (1=healthy, 0=unhealthy)',
            ['service', 'api_key_prefix']
        )

        self.database_operations = Histogram(
            'academic_clarity_database_operations_seconds',
            'Database operation duration',
            ['operation'],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5)
        )

        self.ocr_pages_processed = Counter(
            'academic_clarity_ocr_pages_processed_total',
            'Total OCR pages processed',
            ['status']
        )

        self.ocr_duration = Histogram(
            'academic_clarity_ocr_duration_seconds',
            'OCR processing duration',
            buckets=(1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
        )

        self.app_info = Info(
            'academic_clarity_app',
            'Application information'
        )

        self._custom_gauges: Dict[str, Gauge] = {}
        self._custom_counters: Dict[str, Counter] = {}
        self._time_series: Dict[str, List[TimeSeriesPoint]] = defaultdict(list)

        self._start_time = time.time()

    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """记录API请求"""
        self.api_requests_total.labels(endpoint=endpoint, method=method, status=str(status_code)).inc()
        self.api_request_duration.labels(endpoint=endpoint, method=method).observe(duration)

    def record_task(self, status: str):
        """记录任务完成"""
        self.tasks_total.labels(status=status).inc()

    def set_tasks_in_progress(self, count: int):
        """设置正在处理的任务数"""
        self.tasks_in_progress.set(count)

    def set_tasks_queued(self, count: int):
        """设置队列中的任务数"""
        self.tasks_queued.set(count)

    def update_key_stats(self, service: str, key_prefix: str, rpm_used: int, rpm_limit: int,
                        tpm_used: int, tpm_limit: int, is_healthy: bool):
        """更新API密钥统计"""
        self.api_key_usage.labels(service=service, api_key_prefix=key_prefix).set(
            rpm_used / rpm_limit if rpm_limit > 0 else 0
        )
        self.api_key_health.labels(service=service, api_key_prefix=key_prefix).set(
            1 if is_healthy else 0
        )

    def record_database_operation(self, operation: str, duration: float):
        """记录数据库操作"""
        self.database_operations.labels(operation=operation).observe(duration)

    def record_ocr_page(self, status: str):
        """记录OCR页面处理"""
        self.ocr_pages_processed.labels(status=status).inc()

    def record_ocr_duration(self, duration: float):
        """记录OCR处理时长"""
        self.ocr_duration.observe(duration)

    def set_app_info(self, **kwargs):
        """设置应用信息"""
        self.app_info.info(kwargs)

    def create_gauge(self, name: str, description: str, labels: Optional[List[str]] = None):
        """创建自定义Gauge"""
        if name in self._custom_gauges:
            return self._custom_gauges[name]

        if labels:
            self._custom_gauges[name] = Gauge(name, description, labels)
        else:
            self._custom_gauges[name] = Gauge(name, description)
        return self._custom_gauges[name]

    def create_counter(self, name: str, description: str, labels: Optional[List[str]] = None):
        """创建自定义Counter"""
        if name in self._custom_counters:
            return self._custom_counters[name]

        if labels:
            self._custom_counters[name] = Counter(name, description, labels)
        else:
            self._custom_counters[name] = Counter(name, description)
        return self._custom_counters[name]

    def add_time_series_point(self, name: str, value: float):
        """添加时间序列数据点"""
        self._time_series[name].append(TimeSeriesPoint(timestamp=time.time(), value=value))
        cutoff = time.time() - 3600
        self._time_series[name] = [
            p for p in self._time_series[name] if p.timestamp > cutoff
        ]

    def get_uptime(self) -> float:
        """获取应用运行时间（秒）"""
        return time.time() - self._start_time

    def get_summary(self) -> Dict:
        """获取指标摘要"""
        return {
            "uptime_seconds": self.get_uptime(),
            "uptime_human": str(timedelta(seconds=int(self.get_uptime()))),
            "tasks_in_progress": self.tasks_in_progress._value.get(),
            "tasks_queued": self.tasks_queued._value.get(),
        }

    def get_prometheus_metrics(self) -> Response:
        """生成Prometheus格式的指标"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

metrics = MetricsCollector()

class MetricsMiddleware:
    """API指标中间件"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        path = scope.get("path", "")
        method = scope.get("method", "GET")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                duration = time.time() - start_time
                endpoint = self._normalize_endpoint(path)
                metrics.record_api_request(endpoint, method, status_code, duration)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _normalize_endpoint(self, path: str) -> str:
        """标准化端点路径，将参数替换为占位符"""
        parts = path.split('/')
        normalized = []
        for i, part in enumerate(parts):
            if part.isdigit():
                normalized.append('{id}')
            elif part.startswith('{'):
                normalized.append('{param}')
            else:
                normalized.append(part)
        return '/'.join(normalized)
