"""
Academic Clarity - Prometheus Metrics Module
提供Prometheus格式的指标导出
"""

import time
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from collections import defaultdict

try:
    from backend.constants import KeyPoolConfig, TaskConfig
except ImportError:
    from constants import KeyPoolConfig, TaskConfig

class Counter:
    def __init__(self, name: str, description: str = "", labels: tuple = ()):
        self.name = name
        self.description = description
        self.labels = labels
        self._value = 0.0
        self._lock = Lock()

    def inc(self, value: float = 1.0, **label_values):
        with self._lock:
            self._value += value

    def get(self) -> float:
        with self._lock:
            return self._value

class Gauge:
    def __init__(self, name: str, description: str = "", labels: tuple = ()):
        self.name = name
        self.description = description
        self.labels = labels
        self._value = 0.0
        self._lock = Lock()

    def set(self, value: float, **label_values):
        with self._lock:
            self._value = value

    def inc(self, value: float = 1.0, **label_values):
        with self._lock:
            self._value += value

    def dec(self, value: float = 1.0, **label_values):
        with self._lock:
            self._value -= value

    def get(self) -> float:
        with self._lock:
            return self._value

class Histogram:
    def __init__(self, name: str, description: str = "", buckets: tuple = None, labels: tuple = ()):
        self.name = name
        self.description = description
        self.labels = labels
        self.buckets = buckets or (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        self._sum = 0.0
        self._count = 0
        self._bucket_counts = defaultdict(int)
        self._lock = Lock()

    def observe(self, value: float, **label_values):
        with self._lock:
            self._sum += value
            self._count += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] += 1

    def get(self) -> Dict[str, float]:
        with self._lock:
            return {
                "sum": self._sum,
                "count": self._count,
                "buckets": dict(self._bucket_counts)
            }

class Summary:
    def __init__(self, name: str, description: str = "", labels: tuple = ()):
        self.name = name
        self.description = description
        self.labels = labels
        self._values = []
        self._lock = Lock()

    def observe(self, value: float, **label_values):
        with self._lock:
            self._values.append(value)
            if len(self._values) > 1000:
                self._values = self._values[-1000:]

    def get(self) -> Dict[str, float]:
        with self._lock:
            if not self._values:
                return {"count": 0, "sum": 0}
            sorted_vals = sorted(self._values)
            return {
                "count": len(self._values),
                "sum": sum(self._values),
                "p50": sorted_vals[len(sorted_vals) // 2],
                "p95": sorted_vals[int(len(sorted_vals) * 0.95)],
                "p99": sorted_vals[int(len(sorted_vals) * 0.99)]
            }

class MetricsRegistry:
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
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._summaries: Dict[str, Summary] = {}
        self._start_time = time.time()

        self._register_default_metrics()

    def _register_default_metrics(self):
        self._counters["api_requests_total"] = Counter(
            "api_requests_total",
            "Total number of API requests",
            ("method", "endpoint", "status")
        )
        self._counters["task_processed_total"] = Counter(
            "task_processed_total",
            "Total number of tasks processed",
            ("status",)
        )
        self._counters["ocr_pages_total"] = Counter(
            "ocr_pages_total",
            "Total number of OCR pages processed",
            ("status",)
        )
        self._counters["api_errors_total"] = Counter(
            "api_errors_total",
            "Total number of API errors",
            ("error_type",)
        )

        self._gauges["active_tasks"] = Gauge(
            "active_tasks",
            "Number of currently active tasks"
        )
        self._gauges["queued_tasks"] = Gauge(
            "queued_tasks",
            "Number of tasks in queue"
        )
        self._gauges["api_key_available"] = Gauge(
            "api_key_available",
            "Number of available API keys",
            ("pool",)
        )
        self._gauges["memory_usage_bytes"] = Gauge(
            "memory_usage_bytes",
            "Current memory usage in bytes"
        )
        self._gauges["cpu_percent"] = Gauge(
            "cpu_percent",
            "Current CPU usage percentage"
        )

        self._histograms["api_request_duration_seconds"] = Histogram(
            "api_request_duration_seconds",
            "API request duration in seconds",
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )
        self._histograms["task_duration_seconds"] = Histogram(
            "task_duration_seconds",
            "Task execution duration in seconds",
            buckets=(1, 5, 10, 30, 60, 120, 300, 600)
        )
        self._histograms["ocr_page_duration_seconds"] = Histogram(
            "ocr_page_duration_seconds",
            "OCR page processing duration in seconds",
            buckets=(0.5, 1, 2, 5, 10, 30)
        )

        self._summaries["request_size_bytes"] = Summary(
            "request_size_bytes",
            "Request size in bytes"
        )

    def counter(self, name: str) -> Counter:
        return self._counters.get(name)

    def gauge(self, name: str) -> Gauge:
        return self._gauges.get(name)

    def histogram(self, name: str) -> Histogram:
        return self._histograms.get(name)

    def summary(self, name: str) -> Summary:
        return self._summaries.get(name)

    def register_counter(self, name: str, description: str = "", labels: tuple = ()) -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name, description, labels)
        return self._counters[name]

    def register_gauge(self, name: str, description: str = "", labels: tuple = ()) -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, description, labels)
        return self._gauges[name]

    def register_histogram(self, name: str, description: str = "", buckets: tuple = None, labels: tuple = ()) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, description, buckets, labels)
        return self._histograms[name]

    def _format_metric(self, name: str, value: Any, metric_type: str, description: str = "", labels: tuple = (), label_values: Dict = None) -> str:
        help_line = f"# HELP {name} {description}" if description else f"# HELP {name} {name}"
        type_line = f"# TYPE {name} {metric_type}"

        if labels and label_values:
            label_str = ",".join(f'{k}="{v}"' for k, v in label_values.items())
            value_line = f"{name}{{{label_str}}} {value}"
        else:
            value_line = f"{name} {value}"

        return f"{help_line}\n{type_line}\n{value_line}"

    def export(self) -> str:
        lines = []
        lines.append(f"# Academic Clarity Prometheus Metrics")
        lines.append(f"# Exported at: {datetime.utcnow().isoformat()}Z")
        lines.append(f"")

        uptime = time.time() - self._start_time
        lines.append(self._format_metric(
            "process_uptime_seconds", f"{uptime:.2f}",
            "gauge", "Process uptime in seconds"
        ))
        lines.append("")

        for name, counter in self._counters.items():
            value = counter.get()
            lines.append(self._format_metric(
                name, f"{value}",
                "counter", counter.description
            ))
        lines.append("")

        for name, gauge in self._gauges.items():
            value = gauge.get()
            lines.append(self._format_metric(
                name, f"{value}",
                "gauge", gauge.description
            ))
        lines.append("")

        for name, histogram in self._histograms.items():
            data = histogram.get()
            lines.append(self._format_metric(
                f"{name}_sum", f"{data['sum']:.6f}",
                "histogram", f"{histogram.description} (sum)"
            ))
            lines.append(self._format_metric(
                f"{name}_count", f"{data['count']}",
                "histogram", f"{histogram.description} (count)"
            ))
            for bucket, count in sorted(data['buckets'].items()):
                lines.append(self._format_metric(
                    f"{name}_bucket", f"{count}",
                    "histogram",
                    f"{histogram.description} (bucket <= {bucket})",
                    labels=("le",),
                    label_values={"le": str(bucket)}
                ))
            lines.append(self._format_metric(
                f"{name}_bucket", f"{data['count']}",
                "histogram",
                f"{histogram.description} (bucket <= +Inf)",
                labels=("le",),
                label_values={"le": "+Inf"}
            ))
        lines.append("")

        for name, summary in self._summaries.items():
            data = summary.get()
            if data["count"] > 0:
                lines.append(self._format_metric(
                    f"{name}_sum", f"{data['sum']:.2f}",
                    "summary", f"{summary.description} (sum)"
                ))
                lines.append(self._format_metric(
                    f"{name}_count", f"{data['count']}",
                    "summary", f"{summary.description} (count)"
                ))
                for quantile in ["p50", "p95", "p99"]:
                    if quantile in data:
                        lines.append(self._format_metric(
                            f"{name}", f"{data[quantile]:.6f}",
                            "summary",
                            f"{summary.description} ({quantile})",
                            labels=("quantile",),
                            label_values={"quantile": quantile.replace("p", "")}
                        ))
        lines.append("")

        return "\n".join(lines)

    def update_from_stats(self, task_stats: Dict[str, Any], key_stats: Dict[str, Any]):
        if "active_tasks" in self._gauges:
            self._gauges["active_tasks"].set(task_stats.get("active_tasks", 0))
        if "queued_tasks" in self._gauges:
            self._gauges["queued_tasks"].set(task_stats.get("queued_tasks", 0))

        for pool_name, pool_data in key_stats.items():
            if "api_key_available" in self._gauges:
                keys = pool_data.get("keys", [])
                available = sum(1 for k in keys if k.get("is_healthy", True))
                self._gauges["api_key_available"].set(
                    available,
                    pool=pool_name
                )

    def update_system_metrics(self):
        try:
            import psutil
            if "memory_usage_bytes" in self._gauges:
                self._gauges["memory_usage_bytes"].set(psutil.Process().memory_info().rss)
            if "cpu_percent" in self._gauges:
                self._gauges["cpu_percent"].set(psutil.cpu_percent(interval=0.1))
        except ImportError:
            pass

registry = MetricsRegistry()

def get_metrics() -> str:
    registry.update_system_metrics()
    return registry.export()

def get_metrics_json() -> Dict[str, Any]:
    registry.update_system_metrics()
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "counters": {name: c.get() for name, c in registry._counters.items()},
        "gauges": {name: g.get() for name, g in registry._gauges.items()},
        "histograms": {name: h.get() for name, h in registry._histograms.items()},
        "summaries": {name: s.get() for name, s in registry._summaries.items()}
    }
