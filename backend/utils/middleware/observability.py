"""
Academic Clarity - 可观测性中间件（请求日志 + Prometheus 指标）

这两个中间件由 server.py 挂载（app.add_middleware），属于唯一装配点。
"""
import time
import asyncio
import re
from typing import Callable, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    EXCLUDED_PATHS: Set[str] = {
        "/health",
        "/metrics",
        "/favicon.ico"
    }

    def __init__(self, app: ASGIApp, logger=None):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        start_time = time.time()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            if self.logger:
                self.logger.error(f"Request failed: {method} {path}", error=str(e))
            raise
        finally:
            duration = (time.time() - start_time) * 1000
            if self.logger:
                self.logger.log_api_call(path, method, status_code, duration)

        return response


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus 指标中间件"""

    _endpoint_cache: dict[str, str] = {}
    _cache_lock = asyncio.Lock()

    PATH_PARAM_PATTERN = re.compile(r'/\{[^}]+\}')

    def __init__(self, app: ASGIApp, metrics_collector=None):
        super().__init__(app)
        self.metrics = metrics_collector
        self._start_time = time.time()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        method = request.method
        path = request.url.path

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            raise
        finally:
            duration = time.time() - start_time

            if self.metrics:
                normalized_path = await self._normalize_path(path)
                self.metrics.record_api_request(normalized_path, method, status_code, duration)

    async def _normalize_path(self, path: str) -> str:
        """规范化路径，将参数替换为占位符"""
        if path in self._endpoint_cache:
            return self._endpoint_cache[path]

        normalized = self.PATH_PARAM_PATTERN.sub('/{param}', path)

        async with self._cache_lock:
            if len(self._endpoint_cache) > 1000:
                self._endpoint_cache.clear()
            self._endpoint_cache[path] = normalized

        return normalized
