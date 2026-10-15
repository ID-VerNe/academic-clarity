"""
Academic Clarity - Prometheus 指标对象定义与自定义指标注册表

纯定义层：不持有单例、不做埋点（埋点见 metrics.py）。
"""
from typing import Dict, List, Optional
from prometheus_client import Counter, Histogram, Gauge, Info


class MetricRegistry:
    """应用级 Prometheus 指标对象集合 + 自定义指标注册"""

    def __init__(self):
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

    def create_gauge(self, name: str, description: str,
                     labels: Optional[List[str]] = None) -> Gauge:
        """创建（或复用）自定义Gauge"""
        if name in self._custom_gauges:
            return self._custom_gauges[name]

        if labels:
            self._custom_gauges[name] = Gauge(name, description, labels)
        else:
            self._custom_gauges[name] = Gauge(name, description)
        return self._custom_gauges[name]

    def create_counter(self, name: str, description: str,
                       labels: Optional[List[str]] = None) -> Counter:
        """创建（或复用）自定义Counter"""
        if name in self._custom_counters:
            return self._custom_counters[name]

        if labels:
            self._custom_counters[name] = Counter(name, description, labels)
        else:
            self._custom_counters[name] = Counter(name, description)
        return self._custom_counters[name]
