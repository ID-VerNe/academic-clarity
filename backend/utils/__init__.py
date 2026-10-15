"""
Academic Clarity - Utils 包门面

B-SRP-23：门面改为惰性 re-export。
`from utils import X` / `utils.X` 行为保持兼容，但 `import utils` 不再一次性
加载全部子模块，也不会触发模块级单例初始化；单例仅在首次访问对应名字时创建。
"""
import sys
from importlib import import_module
from types import ModuleType

# 名称 -> (子模块, 模块内属性)
_EXPORTS = {
    "get_logger": ("logger", "get_logger"),
    "StructuredLogger": ("logger", "StructuredLogger"),
    "core_logger": ("logger", "core_logger"),
    "api_logger": ("logger", "api_logger"),
    "task_logger": ("logger", "task_logger"),
    "db_logger": ("logger", "db_logger"),
    "key_logger": ("logger", "key_logger"),
    "metrics": ("metrics", "metrics"),
    "MetricsCollector": ("metrics", "MetricsCollector"),
    "health_checker": ("health", "health_checker"),
    "HealthChecker": ("health", "HealthChecker"),
    "HealthCheckResult": ("health", "HealthCheckResult"),
    "init_cache": ("cache", "init_cache"),
    "get_cache": ("cache", "get_cache"),
    "CacheManager": ("cache", "CacheManager"),
    "InMemoryCache": ("cache", "InMemoryCache"),
    "RedisCache": ("cache", "RedisCache"),
    "ws_manager": ("websocket", "ws_manager"),
    "progress_tracker": ("websocket", "progress_tracker"),
    "EventType": ("websocket", "EventType"),
    "ConnectionManager": ("websocket", "ConnectionManager"),
    "PrometheusMetricsMiddleware": ("middleware", "PrometheusMetricsMiddleware"),
    "RequestLoggingMiddleware": ("middleware", "RequestLoggingMiddleware"),
    "RateLimitMiddleware": ("middleware", "RateLimitMiddleware"),
    "TimeoutMiddleware": ("middleware", "TimeoutMiddleware"),
}


class _LazyFacade(ModuleType):
    """惰性导出：属性访问时按需导入对应子模块。

    用 `__getattribute__`（而非仅 PEP 562 `__getattr__`）是为了处理与子模块
    同名的导出（如 `metrics` 单例 vs `utils.metrics` 子模块）：保证
    `from utils import metrics` 恒返回单例，与旧门面的语义一致。
    """

    def __getattribute__(self, name: str):
        if name in _EXPORTS:
            module_name, attr_name = _EXPORTS[name]
            module = import_module(f".{module_name}", __name__)
            return getattr(module, attr_name)
        return super().__getattribute__(name)


def __dir__():
    return sorted(_EXPORTS)


__all__ = list(_EXPORTS.keys())

sys.modules[__name__].__class__ = _LazyFacade
