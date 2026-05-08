"""
Academic Clarity - Redis Cache Layer
提供Redis缓存功能，支持文档缓存、OCR结果缓存、会话缓存
"""

import os
import json
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

try:
    from backend.constants import CacheConfig
except ImportError:
    from constants import CacheConfig

class CacheStrategy(str, Enum):
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"

@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: int = 3600

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

class InMemoryCache:
    """简单的内存缓存实现，作为Redis的替代方案（无需外部依赖）"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            entry.touch()
            return entry.value

    def set(self, key: str, value: Any, ttl: int = None):
        with self._lock:
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_lru()
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl or self._default_ttl
            )
            self._cache[key] = entry

    def delete(self, key: str):
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()

    def _evict_lru(self):
        """驱逐最久未使用的条目"""
        if not self._cache:
            return
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]

    def cleanup_expired(self):
        """清理过期条目"""
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_entries = len(self._cache)
            expired_count = sum(1 for v in self._cache.values() if v.is_expired())
            total_accesses = sum(v.access_count for v in self._cache.values())
            return {
                "total_entries": total_entries,
                "expired_entries": expired_count,
                "max_size": self._max_size,
                "total_accesses": total_accesses,
                "utilization": total_entries / self._max_size if self._max_size > 0 else 0
            }

class RedisCache:
    """Redis缓存实现（需要redis-py库）"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", default_ttl: int = 3600):
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._client = None
        self._available = False
        self._connect()

    def _connect(self):
        try:
            import redis
            self._client = redis.from_url(self._redis_url)
            self._client.ping()
            self._available = True
        except ImportError:
            print("[Cache] redis-py not installed, using in-memory fallback")
            self._available = False
        except Exception as e:
            print(f"[Cache] Redis connection failed: {e}, using in-memory fallback")
            self._available = False

    def get(self, key: str) -> Optional[Any]:
        if not self._available:
            return None
        try:
            value = self._client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            print(f"[Cache] Redis GET error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = None):
        if not self._available:
            return
        try:
            ttl = ttl or self._default_ttl
            serialized = json.dumps(value)
            self._client.setex(key, ttl, serialized)
        except Exception as e:
            print(f"[Cache] Redis SET error: {e}")

    def delete(self, key: str):
        if not self._available:
            return
        try:
            self._client.delete(key)
        except Exception as e:
            print(f"[Cache] Redis DELETE error: {e}")

    def clear(self):
        if not self._available:
            return
        try:
            self._client.flushdb()
        except Exception as e:
            print(f"[Cache] Redis CLEAR error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        if not self._available:
            return {"backend": "none", "available": False}
        try:
            info = self._client.info("stats")
            return {
                "backend": "redis",
                "available": True,
                "connected_clients": self._client.info("clients")["connected_clients"],
                "total_commands": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0)
            }
        except Exception as e:
            return {"backend": "redis", "available": False, "error": str(e)}

class CacheManager:
    """统一的缓存管理器"""

    def __init__(self):
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        default_ttl = 3600

        self._redis = RedisCache(redis_url, default_ttl)
        self._memory = InMemoryCache(max_size=1000, default_ttl=default_ttl)
        self._use_redis = self._redis._available

    def get(self, key: str) -> Optional[Any]:
        if self._use_redis:
            value = self._redis.get(key)
            if value is not None:
                return value
        return self._memory.get(key)

    def set(self, key: str, value: Any, ttl: int = None):
        if self._use_redis:
            self._redis.set(key, value, ttl)
        self._memory.set(key, value, ttl)

    def delete(self, key: str):
        if self._use_redis:
            self._redis.delete(key)
        self._memory.delete(key)

    def clear(self):
        if self._use_redis:
            self._redis.clear()
        self._memory.clear()

    def get_document_cache(self, doc_id: int) -> Optional[Dict]:
        return self.get(f"doc:{doc_id}")

    def set_document_cache(self, doc_id: int, data: Dict, ttl: int = 7200):
        self.set(f"doc:{doc_id}", data, ttl)

    def invalidate_document_cache(self, doc_id: int):
        self.delete(f"doc:{doc_id}")

    def get_ocr_result(self, doc_id: int) -> Optional[Dict]:
        return self.get(f"ocr:{doc_id}")

    def set_ocr_result(self, doc_id: int, result: Dict, ttl: int = 86400):
        self.set(f"ocr:{doc_id}", result, ttl)

    def get_metadata_cache(self, doc_id: int, label: str) -> Optional[str]:
        return self.get(f"meta:{doc_id}:{label}")

    def set_metadata_cache(self, doc_id: int, label: str, value: str, ttl: int = 86400):
        self.set(f"meta:{doc_id}:{label}", value, ttl)

    def get_session(self, session_id: str) -> Optional[Dict]:
        return self.get(f"session:{session_id}")

    def set_session(self, session_id: str, data: Dict, ttl: int = 3600):
        self.set(f"session:{session_id}", data, ttl)

    def invalidate_session(self, session_id: str):
        self.delete(f"session:{session_id}")

    def cleanup(self):
        """清理过期缓存"""
        expired = self._memory.cleanup_expired()
        return {"cleaned_entries": expired}

    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "backend": "redis" if self._use_redis else "memory",
            "memory_cache": self._memory.get_stats(),
            "redis_cache": self._redis.get_stats()
        }
        return stats

cache_manager = CacheManager()

def get_cache() -> CacheManager:
    return cache_manager
