#!/usr/bin/env python3
"""
core/cache.py — Short-lived cache for embeddings and selection results.

Features:
- TTL-based caching (60-120s)
- Query + role based keying
- Ingest-based invalidation
- Thread-safe operations
- Metrics tracking
"""

import time
import threading
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from core.metrics import increment_counter, observe_histogram


@dataclass
class CacheEntry:
    """Single cache entry with TTL."""
    key: str
    value: Any
    created_at: float
    ttl_seconds: float
    entity_ids: Set[str] = field(default_factory=set)  # For invalidation
    
    def is_expired(self, now: Optional[float] = None) -> bool:
        """Check if entry is expired."""
        now = now or time.time()
        return (now - self.created_at) >= self.ttl_seconds


class QueryCache:
    """
    Short-lived cache for embeddings and selection results.
    
    Features:
    - TTL-based expiration (default 60-120s)
    - Query + role normalized keying
    - Ingest-based invalidation
    - Automatic cleanup of expired entries
    - Thread-safe operations
    """
    
    def __init__(
        self,
        embedding_ttl: float = 120.0,
        selection_ttl: float = 60.0,
        cleanup_interval: float = 30.0
    ):
        """
        Initialize query cache.
        
        Args:
            embedding_ttl: TTL for embedding cache (seconds)
            selection_ttl: TTL for selection results cache (seconds)
            cleanup_interval: How often to cleanup expired entries (seconds)
        """
        self.embedding_ttl = embedding_ttl
        self.selection_ttl = selection_ttl
        self.cleanup_interval = cleanup_interval
        
        # Cache storage
        self._embedding_cache: Dict[str, CacheEntry] = {}
        self._selection_cache: Dict[str, CacheEntry] = {}
        
        # Entity -> cache keys mapping for invalidation
        self._entity_to_keys: Dict[str, Set[str]] = defaultdict(set)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Cleanup tracking
        self._last_cleanup = time.time()
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize query for cache key.
        
        Lowercases, strips whitespace, collapses multiple spaces.
        
        Args:
            query: Raw query string
            
        Returns:
            Normalized query
        """
        # Lowercase and strip
        normalized = query.lower().strip()
        
        # Collapse multiple spaces
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _make_cache_key(
        self,
        query: str,
        role: Optional[str] = None,
        prefix: str = ""
    ) -> str:
        """
        Generate cache key from query and role.
        
        Args:
            query: Query string
            role: Optional role (for RBAC)
            prefix: Optional prefix for key type
            
        Returns:
            Cache key (hash)
        """
        normalized = self._normalize_query(query)
        role_part = role or "none"
        
        # Create key string
        key_str = f"{prefix}:{normalized}:{role_part}"
        
        # Hash for consistent length
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]
        
        return f"{prefix}:{key_hash}"
    
    def _cleanup_expired(self, force: bool = False):
        """
        Cleanup expired entries.
        
        Args:
            force: Force cleanup regardless of interval
        """
        now = time.time()
        
        # Check if cleanup needed
        if not force and (now - self._last_cleanup) < self.cleanup_interval:
            return
        
        with self._lock:
            # Cleanup embeddings
            expired_embedding_keys = [
                key for key, entry in self._embedding_cache.items()
                if entry.is_expired(now)
            ]
            for key in expired_embedding_keys:
                entry = self._embedding_cache.pop(key, None)
                if entry:
                    # Remove from entity mapping
                    for entity_id in entry.entity_ids:
                        self._entity_to_keys[entity_id].discard(key)
                    increment_counter("cache.expired", labels={"type": "embedding"})
            
            # Cleanup selections
            expired_selection_keys = [
                key for key, entry in self._selection_cache.items()
                if entry.is_expired(now)
            ]
            for key in expired_selection_keys:
                entry = self._selection_cache.pop(key, None)
                if entry:
                    # Remove from entity mapping
                    for entity_id in entry.entity_ids:
                        self._entity_to_keys[entity_id].discard(key)
                    increment_counter("cache.expired", labels={"type": "selection"})
            
            # Cleanup empty entity mappings
            empty_entities = [
                entity_id for entity_id, keys in self._entity_to_keys.items()
                if not keys
            ]
            for entity_id in empty_entities:
                del self._entity_to_keys[entity_id]
            
            self._last_cleanup = now
            
            if expired_embedding_keys or expired_selection_keys:
                increment_counter("cache.cleanup", labels={
                    "embeddings": str(len(expired_embedding_keys)),
                    "selections": str(len(expired_selection_keys))
                })
    
    def get_embedding(
        self,
        query: str,
        role: Optional[str] = None
    ) -> Optional[List[float]]:
        """
        Get cached embedding for query.
        
        Args:
            query: Query string
            role: Optional role
            
        Returns:
            Cached embedding vector or None if not found
        """
        key = self._make_cache_key(query, role, prefix="emb")
        
        with self._lock:
            self._cleanup_expired()
            
            entry = self._embedding_cache.get(key)
            
            if entry is None:
                increment_counter("cache.miss", labels={"type": "embedding"})
                return None
            
            if entry.is_expired():
                # Expired, remove it
                self._embedding_cache.pop(key, None)
                for entity_id in entry.entity_ids:
                    self._entity_to_keys[entity_id].discard(key)
                increment_counter("cache.miss", labels={"type": "embedding", "reason": "expired"})
                return None
            
            # Hit
            increment_counter("cache.hit", labels={"type": "embedding"})
            return entry.value
    
    def set_embedding(
        self,
        query: str,
        embedding: List[float],
        role: Optional[str] = None,
        entity_ids: Optional[Set[str]] = None
    ):
        """
        Cache an embedding.
        
        Args:
            query: Query string
            embedding: Embedding vector
            role: Optional role
            entity_ids: Optional set of entity IDs for invalidation
        """
        key = self._make_cache_key(query, role, prefix="emb")
        entity_ids = entity_ids or set()
        
        with self._lock:
            entry = CacheEntry(
                key=key,
                value=embedding,
                created_at=time.time(),
                ttl_seconds=self.embedding_ttl,
                entity_ids=entity_ids
            )
            
            self._embedding_cache[key] = entry
            
            # Update entity mapping
            for entity_id in entity_ids:
                self._entity_to_keys[entity_id].add(key)
            
            increment_counter("cache.set", labels={"type": "embedding"})
    
    def get_selection(
        self,
        query: str,
        role: Optional[str] = None,
        **kwargs
    ) -> Optional[Any]:
        """
        Get cached selection result.
        
        Args:
            query: Query string
            role: Optional role
            **kwargs: Additional parameters (for cache key)
            
        Returns:
            Cached selection result or None if not found
        """
        # Include kwargs in key if they affect results
        key_parts = [query, role or "none"]
        if kwargs:
            # Sort for consistent keys
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}={kwargs[k]}")
        key_query = "|".join(key_parts)
        
        key = self._make_cache_key(key_query, role, prefix="sel")
        
        with self._lock:
            self._cleanup_expired()
            
            entry = self._selection_cache.get(key)
            
            if entry is None:
                increment_counter("cache.miss", labels={"type": "selection"})
                return None
            
            if entry.is_expired():
                # Expired, remove it
                self._selection_cache.pop(key, None)
                for entity_id in entry.entity_ids:
                    self._entity_to_keys[entity_id].discard(key)
                increment_counter("cache.miss", labels={"type": "selection", "reason": "expired"})
                return None
            
            # Hit
            increment_counter("cache.hit", labels={"type": "selection"})
            return entry.value
    
    def set_selection(
        self,
        query: str,
        result: Any,
        role: Optional[str] = None,
        entity_ids: Optional[Set[str]] = None,
        **kwargs
    ):
        """
        Cache a selection result.
        
        Args:
            query: Query string
            result: Selection result
            role: Optional role
            entity_ids: Optional set of entity IDs for invalidation
            **kwargs: Additional parameters (for cache key)
        """
        # Include kwargs in key if they affect results
        key_parts = [query, role or "none"]
        if kwargs:
            # Sort for consistent keys
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}={kwargs[k]}")
        key_query = "|".join(key_parts)
        
        key = self._make_cache_key(key_query, role, prefix="sel")
        entity_ids = entity_ids or set()
        
        with self._lock:
            entry = CacheEntry(
                key=key,
                value=result,
                created_at=time.time(),
                ttl_seconds=self.selection_ttl,
                entity_ids=entity_ids
            )
            
            self._selection_cache[key] = entry
            
            # Update entity mapping
            for entity_id in entity_ids:
                self._entity_to_keys[entity_id].add(key)
            
            increment_counter("cache.set", labels={"type": "selection"})
    
    def invalidate_by_entities(self, entity_ids: Set[str]):
        """
        Invalidate cache entries by entity IDs.
        
        Called on ingest to clear stale results.
        
        Args:
            entity_ids: Set of entity IDs that were updated
        """
        with self._lock:
            invalidated_keys = set()
            
            for entity_id in entity_ids:
                keys = self._entity_to_keys.get(entity_id, set()).copy()
                for key in keys:
                    invalidated_keys.add(key)
                    
                    # Remove from caches
                    self._embedding_cache.pop(key, None)
                    self._selection_cache.pop(key, None)
                    
                    # Remove from entity mapping
                    self._entity_to_keys[entity_id].discard(key)
            
            # Cleanup empty mappings
            for entity_id in entity_ids:
                if not self._entity_to_keys.get(entity_id):
                    self._entity_to_keys.pop(entity_id, None)
            
            if invalidated_keys:
                increment_counter("cache.invalidated", labels={
                    "count": str(len(invalidated_keys)),
                    "trigger": "ingest"
                })
    
    def invalidate_all(self):
        """Clear all cache entries."""
        with self._lock:
            embedding_count = len(self._embedding_cache)
            selection_count = len(self._selection_cache)
            
            self._embedding_cache.clear()
            self._selection_cache.clear()
            self._entity_to_keys.clear()
            
            increment_counter("cache.invalidated", labels={
                "embeddings": str(embedding_count),
                "selections": str(selection_count),
                "trigger": "manual"
            })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            return {
                "embeddings": {
                    "count": len(self._embedding_cache),
                    "ttl": self.embedding_ttl
                },
                "selections": {
                    "count": len(self._selection_cache),
                    "ttl": self.selection_ttl
                },
                "entities_tracked": len(self._entity_to_keys),
                "last_cleanup": self._last_cleanup
            }


# Global cache instance
_cache_instance = None
_cache_lock = threading.Lock()


def get_cache(
    embedding_ttl: float = 120.0,
    selection_ttl: float = 60.0
) -> QueryCache:
    """
    Get or create global cache instance.
    
    Args:
        embedding_ttl: TTL for embeddings (seconds)
        selection_ttl: TTL for selections (seconds)
        
    Returns:
        QueryCache instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = QueryCache(
                    embedding_ttl=embedding_ttl,
                    selection_ttl=selection_ttl
                )
    
    return _cache_instance


def invalidate_cache_on_ingest(entity_ids: Set[str]):
    """
    Invalidate cache entries on ingest.
    
    Should be called after successful ingest of new content.
    
    Args:
        entity_ids: Set of entity IDs that were created/updated
    """
    cache = get_cache()
    cache.invalidate_by_entities(entity_ids)


def reset_cache():
    """Reset global cache instance (for testing)."""
    global _cache_instance
    with _cache_lock:
        _cache_instance = None
