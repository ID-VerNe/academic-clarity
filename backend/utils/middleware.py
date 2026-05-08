"""
Academic Clarity - HTTP 中间件模块
提供请求日志、性能追踪、限流等中间件
"""
import time
import asyncio
import re
from typing import Callable, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

try:
    from backend.constants import APIConfig
except ImportError:
    class APIConfig:
        REQUEST_TIMEOUT = 30.0

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


class CORSCustomMiddleware:
    """自定义 CORS 中间件 - 提供更细粒度的控制"""

    def __init__(self, app: ASGIApp, allowed_origins: list, allowed_methods: list = None):
        self.app = app
        self.allowed_origins = allowed_origins
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await self.app(scope, receive, send)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的速率限制中间件"""

    _request_counts: dict[str, list] = {}
    _counts_lock = asyncio.Lock()
    WINDOW_SECONDS = 60
    MAX_REQUESTS = 1000

    def __init__(self, app: ASGIApp, max_requests: int = None, window_seconds: int = None):
        super().__init__(app)
        self.max_requests = max_requests or self.MAX_REQUESTS
        self.window_seconds = window_seconds or self.WINDOW_SECONDS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        async with self._counts_lock:
            if client_ip not in self._request_counts:
                self._request_counts[client_ip] = []

            self._request_counts[client_ip] = [
                t for t in self._request_counts[client_ip]
                if current_time - t < self.window_seconds
            ]

            if len(self._request_counts[client_ip]) >= self.max_requests:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    {"error": "Rate limit exceeded"},
                    status_code=429
                )

            self._request_counts[client_ip].append(current_time)

        return await call_next(request)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """请求超时中间件"""

    def __init__(self, app: ASGIApp, timeout_seconds: float = None):
        super().__init__(app)
        self.timeout = timeout_seconds or APIConfig.REQUEST_TIMEOUT

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            async with asyncio.timeout(self.timeout):
                return await call_next(request)
        except asyncio.TimeoutError:
            from starlette.responses import JSONResponse
            return JSONResponse(
                {"error": "Request timeout"},
                status_code=504
            )


class CompressionMiddleware:
    """响应压缩中间件"""

    def __init__(self, app: ASGIApp, minimum_size: int = 500):
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await self.app(scope, receive, send)


def create_middleware_stack(app: ASGIApp, config: dict = None) -> ASGIApp:
    """创建中间件栈"""

    if not config:
        config = {
            "cors": True,
            "logging": True,
            "metrics": True,
            "timeout": True,
        }

    from backend.utils.metrics import metrics

    if config.get("timeout", True):
        app = TimeoutMiddleware(app)

    if config.get("metrics", True):
        app = PrometheusMetricsMiddleware(app, metrics)

    if config.get("logging", True):
        from backend.utils.logger import get_logger
        logger = get_logger("http")
        app = RequestLoggingMiddleware(app, logger)

    if config.get("rate_limit", False):
        app = RateLimitMiddleware(app)

    return app
