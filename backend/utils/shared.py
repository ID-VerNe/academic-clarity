"""
Academic Clarity - 共享工具模块
提供通用的异步工具函数和数据结构
"""
import asyncio
import time
from typing import Optional, Any, Callable, TypeVar, Generic
from contextlib import asynccontextmanager
import threading

T = TypeVar('T')

class AsyncSemaphoreWithTimeout:
    """带超时控制的异步信号量"""
    def __init__(self, value: int = 1, timeout: float = 30.0):
        self._semaphore = asyncio.Semaphore(value)
        self._timeout = timeout

    async def acquire(self) -> bool:
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def release(self):
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()


class RateLimiter:
    """基于令牌桶的速率限制器"""
    def __init__(self, rate: float, capacity: float):
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> bool:
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def wait_for_token(self, tokens: float = 1.0, timeout: Optional[float] = None) -> bool:
        start_time = time.time()
        while True:
            if await self.acquire(tokens):
                return True
            if timeout and (time.time() - start_time) >= timeout:
                return False
            await asyncio.sleep(0.1)


class TimedCache(Generic[T]):
    """带过期时间的缓存"""
    def __init__(self, ttl: float = 60.0, max_size: int = 1000):
        self._cache: dict[str, tuple[T, float]] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        async with self._lock:
            if key in self._cache:
                value, expire_at = self._cache[key]
                if time.time() < expire_at:
                    return value
                del self._cache[key]
        return None

    async def set(self, key: str, value: T, ttl: Optional[float] = None):
        async with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            self._cache[key] = (value, time.time() + (ttl or self._ttl))

    async def delete(self, key: str):
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self):
        async with self._lock:
            self._cache.clear()

    def _evict_oldest(self):
        if not self._cache:
            return
        oldest_key = min(self._cache.items(), key=lambda x: x[1][1])[0]
        del self._cache[oldest_key]


class CircuitBreaker:
    """熔断器 - 防止级联故障"""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def record_success(self):
        async with self._lock:
            self._failure_count = 0
            self._state = "closed"

    async def record_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._failure_threshold:
                self._state = "open"

    async def can_execute(self) -> bool:
        async with self._lock:
            if self._state == "closed":
                return True

            if self._state == "open":
                if self._last_failure_time:
                    if time.time() - self._last_failure_time > self._recovery_timeout:
                        self._state = "half-open"
                        return True
                return False

            return True

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> Optional[T]:
        if not await self.can_execute():
            raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure()
            raise e


class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""
    pass


class RetryPolicy:
    """重试策略"""
    def __init__(self, max_retries: int = 3, backoff_multiplier: float = 2.0, initial_delay: float = 1.0):
        self._max_retries = max_retries
        self._backoff = backoff_multiplier
        self._initial_delay = initial_delay

    def get_delay(self, attempt: int) -> float:
        return self._initial_delay * (self._backoff ** attempt)

    async def execute(self, func: Callable, *args, **kwargs):
        last_exception = None
        for attempt in range(self._max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self._max_retries - 1:
                    delay = self.get_delay(attempt)
                    await asyncio.sleep(delay)
        raise last_exception


class AtomicCounter:
    """线程安全的原子计数器"""
    def __init__(self, initial: int = 0):
        self._value = initial
        self._lock = threading.Lock()

    def increment(self, delta: int = 1) -> int:
        with self._lock:
            self._value += delta
            return self._value

    def decrement(self, delta: int = 1) -> int:
        with self._lock:
            self._value -= delta
            return self._value

    def get(self) -> int:
        with self._lock:
            return self._value

    def set(self, value: int):
        with self._lock:
            self._value = value


class Once:
    """确保函数只执行一次"""
    def __init__(self):
        self._executed = False
        self._lock = threading.Lock()
        self._result = None
        self._error = None

    def do(self, func: Callable, *args, **kwargs):
        with self._lock:
            if self._executed:
                if self._error:
                    raise self._error
                return self._result

            self._executed = True
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = loop.create_task(self._run_async(func, args, kwargs))
                    self._result = future
                else:
                    if asyncio.iscoroutinefunction(func):
                        self._result = loop.run_until_complete(func(*args, **kwargs))
                    else:
                        self._result = func(*args, **kwargs)
                return self._result
            except Exception as e:
                self._error = e
                raise

    async def _run_async(self, func: Callable, args: tuple, kwargs: dict):
        return await func(*args, **kwargs)


@asynccontextmanager
async def timeout_context(seconds: float, error_message: str = "Operation timed out"):
    """超时上下文管理器"""
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise TimeoutError(error_message)


def chunk_list(lst: list, chunk_size: int) -> list:
    """将列表分块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """安全除法"""
    return a / b if b != 0 else default
