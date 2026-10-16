"""
Academic Clarity - 指标埋点收集器与 Prometheus 导出

- 指标对象定义见 metrics_registry.py（MetricRegistry）
- 时间序列见 metrics_timeseries.py（TimeSeriesStore）
- 本模块保留原 utils.metrics 的全部公开名字（metrics / MetricsCollector /
  get_prometheus_metrics），其中 get_prometheus_metrics 为模块级薄封装，
  供 `from utils.metrics import metrics, get_prometheus_metrics` 使用。
"""
import time
from datetime import timedelta
from typing import Dict, List, Optional

from fastapi import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .singleton import SingletonMeta
from .metrics_registry import MetricRegistry
from .metrics_timeseries import TimeSeriesStore


class MetricsCollector(metaclass=SingletonMeta):
    """应用指标收集器（单例；双检锁线程安全语义由 SingletonMeta 提供）"""

    def __init__(self):
        self.registry = MetricRegistry()
        self._time_series = TimeSeriesStore()
        self._start_time = time.time()

    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """记录API请求"""
        self.registry.api_requests_total.labels(
            endpoint=endpoint, method=method, status=str(status_code)).inc()
        self.registry.api_request_duration.labels(endpoint=endpoint, method=method).observe(duration)

    def record_task(self, status: str):
        """记录任务完成"""
        self.registry.tasks_total.labels(status=status).inc()

    def set_tasks_in_progress(self, count: int):
        """设置正在处理的任务数"""
        self.registry.tasks_in_progress.set(count)

    def set_tasks_queued(self, count: int):
        """设置队列中的任务数"""
        self.registry.tasks_queued.set(count)

    def record_database_operation(self, operation: str, duration: float):
        """记录数据库操作"""
        self.registry.database_operations.labels(operation=operation).observe(duration)

    def record_ocr_page(self, status: str):
        """记录OCR页面处理"""
        self.registry.ocr_pages_processed.labels(status=status).inc()

    def record_ocr_duration(self, duration: float):
        """记录OCR处理时长"""
        self.registry.ocr_duration.observe(duration)

    def set_app_info(self, **kwargs):
        """设置应用信息"""
        self.registry.app_info.info(kwargs)

    def create_gauge(self, name: str, description: str,
                     labels: Optional[List[str]] = None):
        """创建自定义Gauge"""
        return self.registry.create_gauge(name, description, labels)

    def create_counter(self, name: str, description: str,
                       labels: Optional[List[str]] = None):
        """创建自定义Counter"""
        return self.registry.create_counter(name, description, labels)

    def add_time_series_point(self, name: str, value: float):
        """添加时间序列数据点"""
        self._time_series.add_point(name, value)

    def get_uptime(self) -> float:
        """获取应用运行时间（秒）"""
        return time.time() - self._start_time

    def get_summary(self) -> Dict:
        """获取指标摘要"""
        return {
            "uptime_seconds": self.get_uptime(),
            "uptime_human": str(timedelta(seconds=int(self.get_uptime()))),
            "tasks_in_progress": self.registry.tasks_in_progress._value.get(),
            "tasks_queued": self.registry.tasks_queued._value.get(),
        }

    def get_prometheus_metrics(self) -> Response:
        """生成Prometheus格式的指标（Response 薄封装，装配点仍在 server.py）"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )


metrics = MetricsCollector()


def get_prometheus_metrics() -> Response:
    """模块级薄封装（冻结接口）"""
    return metrics.get_prometheus_metrics()
