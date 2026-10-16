"""
Academic Clarity - 缓存后端实现

内存缓存（LRU 淘汰）与 Redis 缓存（不可用时自动降级到内存）。
"""
import json
import time
from typing import Optional, Any, Dict, List
from dataclasses import dataclass

from constants import CacheConfig


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    ttl: Optional[int] = None

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self):
        self.accessed_at = time.time()
        self.access_count += 1


class InMemoryCache:
    """内存缓存实现 - 非单例模式，支持多实例"""
    def __init__(self, max_size: int = None):
        self._max_size = max_size or CacheConfig.MAX_IN_MEMORY_SIZE
        self._cache: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if entry.is_expired():
            del self._cache[key]
            return None

        entry.touch()
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._evict()

        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            accessed_at=time.time(),
            ttl=ttl
        )

    def delete(self, key: str):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()

    def _evict(self):
        if not self._cache:
            return
        oldest_key = min(self._cache.items(), key=lambda x: x[1].accessed_at)[0]
        del self._cache[oldest_key]

    def exists(self, key: str) -> bool:
        if key in self._cache:
            if self._cache[key].is_expired():
                del self._cache[key]
                return False
            return True
        return False

    def keys(self) -> List[str]:
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            del self._cache[k]
        return list(self._cache.keys())

    def size(self) -> int:
        return len(self._cache)

    def get_stats(self) -> Dict:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "total_accesses": sum(e.access_count for e in self._cache.values())
        }


class RedisCache:
    """Redis缓存实现（连接失败时自动降级到内存缓存）"""
    def __init__(self, host: str = "localhost", port: int = CacheConfig.REDIS_PORT,
                 db: int = 0, password: Optional[str] = None,
                 key_prefix: str = "ac:", fallback_max_size: int = None):
        self._key_prefix = key_prefix
        self._redis = None
        self._fallback = InMemoryCache(fallback_max_size or CacheConfig.MAX_IN_MEMORY_SIZE)
        self._connected = False

        try:
            import redis
            self._redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            self._redis.ping()
            self._connected = True
            print(f"[Cache] Redis connected: {host}:{port}")
        except Exception as e:
            print(f"[Cache] Redis unavailable, using in-memory fallback: {e}")
            self._connected = False

    def _make_key(self, key: str) -> str:
        return f"{self._key_prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        if self._connected and self._redis:
            try:
                value = self._redis.get(self._make_key(key))
                if value:
                    return json.loads(value)
            except Exception:
                pass
        return self._fallback.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if self._connected and self._redis:
            try:
                serialized = json.dumps(value)
                if ttl:
                    self._redis.setex(self._make_key(key), ttl, serialized)
                else:
                    self._redis.set(self._make_key(key), serialized)
                return
            except Exception:
                pass
        self._fallback.set(key, value, ttl)

    def delete(self, key: str):
        if self._connected and self._redis:
            try:
                self._redis.delete(self._make_key(key))
            except Exception:
                pass
        self._fallback.delete(key)

    def clear(self):
        if self._connected and self._redis:
            try:
                keys = self._redis.keys(f"{self._key_prefix}*")
                if keys:
                    self._redis.delete(*keys)
            except Exception:
                pass
        self._fallback.clear()

    def exists(self, key: str) -> bool:
        if self._connected and self._redis:
            try:
                return bool(self._redis.exists(self._make_key(key)))
            except Exception:
                pass
        return self._fallback.exists(key)

    def keys(self, pattern: str = "*") -> List[str]:
        if self._connected and self._redis:
            try:
                keys = self._redis.keys(self._make_key(pattern))
                return [k.replace(self._key_prefix, "") for k in keys]
            except Exception:
                pass
        return self._fallback.keys()

    def is_connected(self) -> bool:
        return self._connected

    def get_stats(self) -> Dict:
        if self._connected and self._redis:
            try:
                info = self._redis.info("memory")
                return {
                    "backend": "redis",
                    "connected": True,
                    "memory_used": info.get("used_memory_human", "unknown")
                }
            except Exception:
                pass
        return {
            "backend": "in_memory",
            "connected": False,
            **self._fallback.get_stats()
        }
