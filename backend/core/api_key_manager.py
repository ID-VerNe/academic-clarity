import asyncio
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict

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
    model_name: str = "openai/deepseek-ai/DeepSeek-OCR"
    max_concurrent: int = 5
    rpm_limit: int = 60
    tpm_limit: int = 100000
    enabled: bool = True

class APIKeyManager:
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
        
        self._keys: Dict[str, KeyState] = {}
        self._key_order: List[str] = []
        self._current_index: int = 0
        self._request_times: Dict[str, List[float]] = defaultdict(list)
        self._async_lock = asyncio.Lock()
        self._token_counts: Dict[str, List[tuple]] = defaultdict(list)
    
    def initialize_keys(self, key_configs: List[KeyConfig]):
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
    
    def add_key(self, config: KeyConfig) -> bool:
        if not config.enabled or not config.api_key:
            return False
        if config.api_key in self._keys:
            return False
        
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
        return True
    
    def remove_key(self, api_key: str) -> bool:
        if api_key not in self._keys:
            return False
        state = self._keys[api_key]
        if state.active_requests > 0:
            return False
        
        del self._keys[api_key]
        self._key_order.remove(api_key)
        if self._key_order:
            self._current_index = self._current_index % len(self._key_order)
        return True
    
    async def get_available_key(self) -> Optional[KeyState]:
        if not self._key_order:
            return None
        
        async with self._async_lock:
            checked_keys = 0
            start_index = self._current_index
            
            while checked_keys < len(self._key_order):
                api_key = self._key_order[self._current_index]
                state = self._keys.get(api_key)
                
                if state and await self._is_key_available(state):
                    self._current_index = (self._current_index + 1) % len(self._key_order)
                    return state
                
                self._current_index = (self._current_index + 1) % len(self._key_order)
                checked_keys += 1
                
                if self._current_index == start_index:
                    await asyncio.sleep(0.1)
            
            return None
    
    async def _is_key_available(self, state: KeyState) -> bool:
        if not state.is_healthy:
            if time.time() - state.last_used > 60:
                state.consecutive_errors = 0
                state.is_healthy = True
            else:
                return False
        
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
    
    async def acquire_key(self, api_key: Optional[str] = None) -> Optional[KeyState]:
        if api_key:
            state = self._keys.get(api_key)
            if state and await self._is_key_available(state):
                async with state.lock:
                    state.active_requests += 1
                    state.last_used = time.time()
                self._request_times[api_key].append(time.time())
                return state
            return None
        
        return await self.get_available_key()
    
    async def release_key(self, state: KeyState, tokens_used: int = 0):
        async with state.lock:
            state.active_requests = max(0, state.active_requests - 1)
        
        if tokens_used > 0:
            self._token_counts[state.key].append((time.time(), tokens_used))
    
    async def report_success(self, state: KeyState, tokens_used: int = 0):
        async with state.lock:
            state.consecutive_errors = 0
            if not state.is_healthy:
                state.is_healthy = True
        if tokens_used > 0:
            self._token_counts[state.key].append((time.time(), tokens_used))
    
    async def report_error(self, state: KeyState, error_type: str = ""):
        async with state.lock:
            state.consecutive_errors += 1
            if state.consecutive_errors >= 5:
                state.is_healthy = False
                print(f"[APIKeyManager] Key {state.key[:8]}... marked as unhealthy due to {state.consecutive_errors} consecutive errors")
    
    def get_key_stats(self) -> List[Dict[str, Any]]:
        stats = []
        for api_key, state in self._keys.items():
            current_time = time.time()
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
                "consecutive_errors": state.consecutive_errors,
                "last_used": state.last_used
            })
        return stats
    
    def get_next_available_key_sync(self) -> Optional[Dict[str, str]]:
        checked_keys = 0
        start_index = self._current_index
        
        while checked_keys < len(self._key_order):
            api_key = self._key_order[self._current_index]
            state = self._keys.get(api_key)
            
            if state and state.is_healthy:
                self._current_index = (self._current_index + 1) % len(self._key_order)
                return {
                    "api_key": state.key,
                    "api_base": state.api_base,
                    "model_name": state.model_name
                }
            
            self._current_index = (self._current_index + 1) % len(self._key_order)
            checked_keys += 1
            
            if self._current_index == start_index:
                break
        
        return None

api_key_manager = APIKeyManager()
