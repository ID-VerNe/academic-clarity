"""
Academic Clarity - Redis 缓存层
提供分布式缓存能力，支持文档、元数据、API密钥池状态缓存
"""
import json
import time
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from enum import Enum
import threading

try:
    from backend.constants import CacheConfig as BackendCacheConfig
except ImportError:
    BackendCacheConfig = None

try:
    from constants import CacheConfig as LocalCacheConfig
except ImportError:
    LocalCacheConfig = None

class CacheConfig:
    DEFAULT_TTL = getattr(BackendCacheConfig, 'DEFAULT_TTL', 300) if BackendCacheConfig else 300
    DOCUMENT_TTL = getattr(BackendCacheConfig, 'DOCUMENT_TTL', 600) if BackendCacheConfig else 600
    KEYPOOL_TTL = getattr(BackendCacheConfig, 'KEYPOOL_TTL', 30) if BackendCacheConfig else 30
    ENABLED = getattr(BackendCacheConfig, 'ENABLED', False) if BackendCacheConfig else False
    MAX_IN_MEMORY_SIZE = 1000

class CacheStrategy(str, Enum):
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"

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
    """内存缓存实现 - 当Redis不可用时使用"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, max_size: int = 1000):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_size: int = 1000):
        if self._initialized:
            return
        self._initialized = True
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._access_order: List[str] = []

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
    """Redis缓存实现"""
    def __init__(self, host: str = "localhost", port: int = 6379,
                 db: int = 0, password: Optional[str] = None,
                 key_prefix: str = "ac:"):
        self._key_prefix = key_prefix
        self._redis = None
        self._fallback = InMemoryCache(CacheConfig.MAX_IN_MEMORY_SIZE)
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


class CacheManager:
    """缓存管理器"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, redis_host: Optional[str] = None, redis_port: int = 6379):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, redis_host: Optional[str] = None, redis_port: int = 6379):
        if self._initialized:
            return
        self._initialized = True

        if redis_host:
            self.cache = RedisCache(host=redis_host, port=redis_port)
        else:
            self.cache = InMemoryCache(CacheConfig.MAX_IN_MEMORY_SIZE)

        self._document_cache = DocumentCache(self.cache)
        self._metadata_cache = MetadataCache(self.cache)
        self._keypool_cache = KeyPoolCache(self.cache)

    @property
    def documents(self) -> "DocumentCache":
        return self._document_cache

    @property
    def metadata(self) -> "MetadataCache":
        return self._metadata_cache

    @property
    def keypool(self) -> "KeyPoolCache":
        return self._keypool_cache


class DocumentCache:
    """文档缓存"""
    def __init__(self, cache_backend):
        self.cache = cache_backend
        self.ttl = CacheConfig.DOCUMENT_TTL

    def get_document(self, doc_id: int) -> Optional[Dict]:
        return self.cache.get(f"doc:{doc_id}")

    def set_document(self, doc_id: int, document: Dict):
        self.cache.set(f"doc:{doc_id}", document, self.ttl)

    def invalidate_document(self, doc_id: int):
        self.cache.delete(f"doc:{doc_id}")

    def get_all_documents(self) -> Optional[List[Dict]]:
        return self.cache.get("docs:all")

    def set_all_documents(self, documents: List[Dict]):
        self.cache.set("docs:all", documents, self.ttl // 2)

    def invalidate_all_documents(self):
        self.cache.delete("docs:all")


class MetadataCache:
    """元数据缓存"""
    def __init__(self, cache_backend):
        self.cache = cache_backend
        self.ttl = CacheConfig.DEFAULT_TTL

    def get_metadata(self, doc_id: int, label: str) -> Optional[str]:
        return self.cache.get(f"meta:{doc_id}:{label}")

    def set_metadata(self, doc_id: int, label: str, content: str):
        self.cache.set(f"meta:{doc_id}:{label}", content, self.ttl)

    def invalidate_metadata(self, doc_id: int):
        for key in self.cache.keys(f"meta:{doc_id}:*"):
            self.cache.delete(key)


class KeyPoolCache:
    """密钥池统计缓存"""
    def __init__(self, cache_backend):
        self.cache = cache_backend
        self.ttl = CacheConfig.KEYPOOL_TTL

    def get_stats(self, service: str) -> Optional[Dict]:
        return self.cache.get(f"keypool:{service}:stats")

    def set_stats(self, service: str, stats: Dict):
        self.cache.set(f"keypool:{service}:stats", stats, self.ttl)

    def invalidate_stats(self, service: str):
        self.cache.delete(f"keypool:{service}:stats")


_cache_manager: Optional[CacheManager] = None

def init_cache(redis_host: Optional[str] = None, redis_port: int = 6379) -> CacheManager:
    """初始化缓存管理器"""
    global _cache_manager
    _cache_manager = CacheManager(redis_host, redis_port)
    return _cache_manager

def get_cache() -> CacheManager:
    """获取缓存管理器"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
