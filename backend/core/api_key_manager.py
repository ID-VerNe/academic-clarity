import asyncio
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

try:
    from backend.constants import KeyPoolConfig, OCRConfig
except ImportError:
    from constants import KeyPoolConfig, OCRConfig

@dataclass
class KeyState:
    key: str
    api_base: str
    model_name: str
    max_concurrent: int = 5
    rpm_limit: int = 60
    tpm_limit: int = 100000
    active_requests: int = 0
    last_used: float = 0.0
    consecutive_errors: int = 0
    is_healthy: bool = True
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

@dataclass
class KeyConfig:
    api_key: str
    api_base: str = "https://api.siliconflow.cn/v1"
    model_name: str = ""
    max_concurrent: int = 5
    rpm_limit: int = 60
    tpm_limit: int = 100000
    enabled: bool = True

class ServiceKeyPool:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._keys: Dict[str, KeyState] = {}
        self._key_order: List[str] = []
        self._current_index: int = 0
        self._request_times: Dict[str, List[float]] = defaultdict(list)
        self._async_lock = asyncio.Lock()
        self._token_counts: Dict[str, List[tuple]] = defaultdict(list)

    def initialize(self, key_configs: List[KeyConfig]):
        self._keys.clear()
        self._key_order.clear()
        self._current_index = 0
        self._request_times.clear()
        self._token_counts.clear()

        for config in key_configs:
            if not config.enabled or not config.api_key:
                continue
            state = KeyState(
                key=config.api_key,
                api_base=config.api_base,
                model_name=config.model_name,
                max_concurrent=config.max_concurrent,
                rpm_limit=config.rpm_limit,
                tpm_limit=config.tpm_limit
            )
            self._keys[config.api_key] = state
            self._key_order.append(config.api_key)

        print(f"[KeyPool:{self.service_name}] Initialized with {len(self._key_order)} keys")

    async def get_available_key(self) -> Optional[KeyState]:
        """
        获取可用的API密钥
        修复：完全避免在锁内执行任何await操作
        """
        if not self._key_order:
            return None

        max_attempts = 3
        for attempt in range(max_attempts):
            candidates = []
            async with self._async_lock:
                checked_keys = 0
                while checked_keys < len(self._key_order):
                    api_key = self._key_order[self._current_index]
                    state = self._keys.get(api_key)

                    if state and self._is_key_healthy_sync(state):
                        candidates.append(state)

                    self._current_index = (self._current_index + 1) % len(self._key_order)
                    checked_keys += 1

            for state in candidates:
                if await self._check_rate_limits(state):
                    return state

            if attempt < max_attempts - 1:
                await asyncio.sleep(KeyPoolConfig.RETRY_INTERVAL * (attempt + 1))

        return None

    def _is_key_healthy_sync(self, state: KeyState) -> bool:
        """同步检查密钥健康状态（不含异步操作）"""
        if not state.is_healthy:
            if time.time() - state.last_used > KeyPoolConfig.HEALTH_CHECK_COOLDOWN:
                state.consecutive_errors = 0
                state.is_healthy = True
                return True
            return False
        return True

    async def _check_rate_limits(self, state: KeyState) -> bool:
        """检查速率限制"""
        current_time = time.time()

        self._request_times[state.key] = [
            t for t in self._request_times[state.key]
            if current_time - t < 60
        ]

        if len(self._request_times[state.key]) >= state.rpm_limit:
            return False

        if state.active_requests >= state.max_concurrent:
            return False

        self._token_counts[state.key] = [
            (t, c) for t, c in self._token_counts[state.key]
            if current_time - t < 60
        ]

        recent_tokens = sum(c for _, c in self._token_counts[state.key])
        if recent_tokens >= state.tpm_limit:
            return False

        return True

    async def acquire_key(self) -> Optional[KeyState]:
        """获取密钥并增加活跃请求计数"""
        key_state = await self.get_available_key()
        if key_state:
            async with key_state.lock:
                key_state.active_requests += 1
                key_state.last_used = time.time()
            self._request_times[key_state.key].append(time.time())
        return key_state

    async def release_key(self, state: KeyState, tokens_used: int = 0):
        """释放密钥"""
        async with state.lock:
            state.active_requests = max(0, state.active_requests - 1)

        if tokens_used > 0:
            self._token_counts[state.key].append((time.time(), tokens_used))

    async def report_success(self, state: KeyState, tokens_used: int = 0):
        """报告成功调用"""
        async with state.lock:
            state.consecutive_errors = 0
            if not state.is_healthy:
                state.is_healthy = True
        if tokens_used > 0:
            self._token_counts[state.key].append((time.time(), tokens_used))

    async def report_error(self, state: KeyState, error_type: str = ""):
        """报告错误调用"""
        async with state.lock:
            state.consecutive_errors += 1
            if state.consecutive_errors >= KeyPoolConfig.UNHEALTHY_THRESHOLD:
                state.is_healthy = False
                print(f"[KeyPool:{self.service_name}] Key {state.key[:8]}... marked unhealthy ({state.consecutive_errors} errors)")

    def get_stats(self) -> List[Dict[str, Any]]:
        """获取密钥池统计信息"""
        stats = []
        current_time = time.time()

        for api_key, state in self._keys.items():
            recent_requests = len([
                t for t in self._request_times[api_key]
                if current_time - t < 60
            ])
            recent_tokens = sum(
                c for t, c in self._token_counts[api_key]
                if current_time - t < 60
            )

            stats.append({
                "api_key": f"{api_key[:8]}...",
                "api_base": state.api_base,
                "model_name": state.model_name,
                "active_requests": state.active_requests,
                "max_concurrent": state.max_concurrent,
                "rpm_limit": state.rpm_limit,
                "rpm_used": recent_requests,
                "tpm_limit": state.tpm_limit,
                "tpm_used": recent_tokens,
                "is_healthy": state.is_healthy,
                "consecutive_errors": state.consecutive_errors
            })
        return stats

    def is_enabled(self) -> bool:
        """检查密钥池是否启用"""
        return len(self._key_order) > 0


class MultiServiceKeyManager:
    _instance = None
    _lock = threading.Lock()
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        with MultiServiceKeyManager._init_lock:
            if self._initialized:
                return
            self._initialized = True

            self._pools: Dict[str, ServiceKeyPool] = {
                "ocr": ServiceKeyPool("ocr"),
                "llm": ServiceKeyPool("llm")
            }

    def initialize_pool(self, service: str, key_configs: List[KeyConfig]):
        if service in self._pools:
            self._pools[service].initialize(key_configs)
        else:
            new_pool = ServiceKeyPool(service)
            new_pool.initialize(key_configs)
            self._pools[service] = new_pool

    def get_pool(self, service: str) -> Optional[ServiceKeyPool]:
        return self._pools.get(service)

    def get_all_stats(self) -> Dict[str, Any]:
        return {
            service: {
                "enabled": pool.is_enabled(),
                "keys": pool.get_stats()
            }
            for service, pool in self._pools.items()
        }


key_manager = MultiServiceKeyManager()
