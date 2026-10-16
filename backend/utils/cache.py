"""
Academic Clarity - 缓存管理器与全局单例入口

- 后端实现见 cache_backends.py（InMemoryCache / RedisCache）
- 领域缓存见 cache_domains.py（DocumentCache / MetadataCache）
- 本模块保留原 utils.cache 的全部公开名字（向后兼容 re-export）
"""
from typing import Optional

from constants import CacheConfig
from .cache_backends import CacheEntry, InMemoryCache, RedisCache
from .cache_domains import DocumentCache, MetadataCache

__all__ = [
    "CacheEntry", "InMemoryCache", "RedisCache",
    "DocumentCache", "MetadataCache",
    "CacheManager", "init_cache", "get_cache",
]


class CacheManager:
    """缓存管理器 - 非单例模式"""
    def __init__(self, redis_host: Optional[str] = None,
                 redis_port: int = CacheConfig.REDIS_PORT):
        if redis_host:
            self.cache = RedisCache(host=redis_host, port=redis_port)
        else:
            self.cache = InMemoryCache()

        self._document_cache = DocumentCache(self.cache)
        self._metadata_cache = MetadataCache(self.cache)

    @property
    def documents(self) -> DocumentCache:
        return self._document_cache

    @property
    def metadata(self) -> MetadataCache:
        return self._metadata_cache


_cache_manager: Optional[CacheManager] = None


def init_cache(redis_host: Optional[str] = None,
               redis_port: int = CacheConfig.REDIS_PORT) -> CacheManager:
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
