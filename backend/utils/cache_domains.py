"""
Academic Clarity - 领域缓存（文档 / 元数据）

基于通用缓存后端（InMemoryCache / RedisCache）的键空间封装。
"""
from typing import Optional, Dict, List

from constants import CacheConfig


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
