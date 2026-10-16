"""
Academic Clarity - 限流 / 超时中间件

注意：当前 server.py 未挂载这两个中间件（仅保留实现，供后续按需启用）。
不要在此模块内做装配（历史 create_middleware_stack 工厂已删除，避免与
server.py 的双装配）。
"""
import time
import asyncio
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from constants import APIConfig


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的速率限制中间件（未挂载）"""

    def __init__(self, app: ASGIApp, max_requests: int = None, window_seconds: int = None):
        super().__init__(app)
        self.max_requests = max_requests or 1000
        self.window_seconds = window_seconds or 60
        self._request_counts: dict[str, list] = {}
        self._counts_lock = asyncio.Lock()

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
    """请求超时中间件（未挂载）"""

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
