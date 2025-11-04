#!/usr/bin/env python3
"""
Unit tests for query cache with TTL and invalidation.

Tests:
1. Cache hits on repeated queries
2. Cache misses on first query
3. TTL expiration
4. Ingest-based invalidation
5. Role-based keying
6. Entity tracking
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Set

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.cache import (
    QueryCache,
    CacheEntry,
    get_cache,
    invalidate_cache_on_ingest,
    reset_cache
)


class TestCacheEntry(unittest.TestCase):
    """Test CacheEntry dataclass."""
    
    def test_entry_creation(self):
        """Test creating cache entry."""
        entry = CacheEntry(
            key="test_key",
            value=[0.1, 0.2],
            created_at=time.time(),
            ttl_seconds=60.0
        )
        
        self.assertEqual(entry.key, "test_key")
        self.assertEqual(entry.value, [0.1, 0.2])
        self.assertFalse(entry.is_expired())
    
    def test_entry_expiration(self):
        """Test entry expiration."""
        past_time = time.time() - 120  # 2 minutes ago
        entry = CacheEntry(
            key="test_key",
            value=[0.1, 0.2],
            created_at=past_time,
            ttl_seconds=60.0
        )
        
        self.assertTrue(entry.is_expired())
    
    def test_entry_with_entities(self):
        """Test entry with entity tracking."""
        entry = CacheEntry(
            key="test_key",
            value=[0.1, 0.2],
            created_at=time.time(),
            ttl_seconds=60.0,
            entity_ids={"entity1", "entity2"}
        )
        
        self.assertEqual(len(entry.entity_ids), 2)
        self.assertIn("entity1", entry.entity_ids)


class TestCacheKeyGeneration(unittest.TestCase):
    """Test cache key generation and normalization."""
    
    def test_query_normalization(self):
        """Test query normalization."""
        cache = QueryCache()
        
        # Different forms of same query should normalize to same
        q1 = cache._normalize_query("What is AI?")
        q2 = cache._normalize_query("what is ai?")
        q3 = cache._normalize_query("  WHAT   IS   AI?  ")
        
        self.assertEqual(q1, q2)
        self.assertEqual(q2, q3)
        self.assertEqual(q1, "what is ai?")
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        cache = QueryCache()
        
        key1 = cache._make_cache_key("What is AI?", role="admin", prefix="emb")
        key2 = cache._make_cache_key("what is ai?", role="admin", prefix="emb")
        
        # Same normalized query and role should produce same key
        self.assertEqual(key1, key2)
        self.assertTrue(key1.startswith("emb:"))
    
    def test_role_based_keying(self):
        """Test role affects cache key."""
        cache = QueryCache()
        
        key_admin = cache._make_cache_key("query", role="admin", prefix="sel")
        key_user = cache._make_cache_key("query", role="user", prefix="sel")
        key_none = cache._make_cache_key("query", role=None, prefix="sel")
        
        # Different roles should produce different keys
        self.assertNotEqual(key_admin, key_user)
        self.assertNotEqual(key_admin, key_none)
        self.assertNotEqual(key_user, key_none)


class TestEmbeddingCache(unittest.TestCase):
    """Test embedding caching."""
    
    def setUp(self):
        """Create fresh cache for each test."""
        self.cache = QueryCache(embedding_ttl=120.0, selection_ttl=60.0)
    
    def test_embedding_miss_on_first_query(self):
        """Test cache miss on first query."""
        embedding = self.cache.get_embedding("What is AI?")
        
        self.assertIsNone(embedding)
    
    def test_embedding_hit_on_repeated_query(self):
        """Test cache hit on repeated query."""
        query = "What is AI?"
        expected_embedding = [0.1, 0.2, 0.3]
        
        # Set
        self.cache.set_embedding(query, expected_embedding)
        
        # Get
        cached = self.cache.get_embedding(query)
        
        self.assertIsNotNone(cached)
        self.assertEqual(cached, expected_embedding)
    
    def test_embedding_role_isolation(self):
        """Test different roles have separate caches."""
        query = "What is AI?"
        emb_admin = [0.1, 0.2]
        emb_user = [0.3, 0.4]
        
        # Set for different roles
        self.cache.set_embedding(query, emb_admin, role="admin")
        self.cache.set_embedding(query, emb_user, role="user")
        
        # Get for different roles
        cached_admin = self.cache.get_embedding(query, role="admin")
        cached_user = self.cache.get_embedding(query, role="user")
        
        self.assertEqual(cached_admin, emb_admin)
        self.assertEqual(cached_user, emb_user)
        self.assertNotEqual(cached_admin, cached_user)
    
    def test_embedding_ttl_expiration(self):
        """Test embedding expires after TTL."""
        cache = QueryCache(embedding_ttl=0.1)  # 100ms TTL
        
        query = "What is AI?"
        embedding = [0.1, 0.2]
        
        # Set
        cache.set_embedding(query, embedding)
        
        # Should be cached immediately
        self.assertIsNotNone(cache.get_embedding(query))
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        self.assertIsNone(cache.get_embedding(query))


class TestSelectionCache(unittest.TestCase):
    """Test selection result caching."""
    
    def setUp(self):
        """Create fresh cache for each test."""
        self.cache = QueryCache(embedding_ttl=120.0, selection_ttl=60.0)
    
    def test_selection_miss_on_first_query(self):
        """Test cache miss on first query."""
        result = self.cache.get_selection("What is AI?")
        
        self.assertIsNone(result)
    
    def test_selection_hit_on_repeated_query(self):
        """Test cache hit on repeated query."""
        query = "What is AI?"
        expected_result = {
            "context": [{"id": "mem1", "text": "AI is..."}],
            "ranked_ids": ["mem1"],
            "strategy_used": "dual"
        }
        
        # Set
        self.cache.set_selection(query, expected_result)
        
        # Get
        cached = self.cache.get_selection(query)
        
        self.assertIsNotNone(cached)
        self.assertEqual(cached, expected_result)
    
    def test_selection_with_kwargs(self):
        """Test selection caching with kwargs."""
        query = "What is AI?"
        result1 = {"k": 8}
        result2 = {"k": 16}
        
        # Set with different kwargs
        self.cache.set_selection(query, result1, k=8)
        self.cache.set_selection(query, result2, k=16)
        
        # Get with different kwargs
        cached1 = self.cache.get_selection(query, k=8)
        cached2 = self.cache.get_selection(query, k=16)
        
        self.assertEqual(cached1, result1)
        self.assertEqual(cached2, result2)
        self.assertNotEqual(cached1, cached2)
    
    def test_selection_ttl_expiration(self):
        """Test selection expires after TTL."""
        cache = QueryCache(selection_ttl=0.1)  # 100ms TTL
        
        query = "What is AI?"
        result = {"context": []}
        
        # Set
        cache.set_selection(query, result)
        
        # Should be cached immediately
        self.assertIsNotNone(cache.get_selection(query))
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        self.assertIsNone(cache.get_selection(query))


class TestInvalidation(unittest.TestCase):
    """Test cache invalidation."""
    
    def setUp(self):
        """Create fresh cache for each test."""
        self.cache = QueryCache(embedding_ttl=120.0, selection_ttl=60.0)
    
    def test_invalidate_by_entities(self):
        """Test invalidating by entity IDs."""
        query = "What is AI?"
        embedding = [0.1, 0.2]
        result = {"context": [{"id": "mem1"}]}
        
        # Set with entity tracking
        self.cache.set_embedding(query, embedding, entity_ids={"mem1", "mem2"})
        self.cache.set_selection(query, result, entity_ids={"mem1", "mem3"})
        
        # Should be cached
        self.assertIsNotNone(self.cache.get_embedding(query))
        self.assertIsNotNone(self.cache.get_selection(query))
        
        # Invalidate by entity
        self.cache.invalidate_by_entities({"mem1"})
        
        # Both should be invalidated (both reference mem1)
        self.assertIsNone(self.cache.get_embedding(query))
        self.assertIsNone(self.cache.get_selection(query))
    
    def test_partial_invalidation(self):
        """Test invalidating only affected entries."""
        query1 = "What is AI?"
        query2 = "What is ML?"
        
        # Set with different entities
        self.cache.set_embedding(query1, [0.1], entity_ids={"mem1"})
        self.cache.set_embedding(query2, [0.2], entity_ids={"mem2"})
        
        # Invalidate only mem1
        self.cache.invalidate_by_entities({"mem1"})
        
        # Only query1 should be invalidated
        self.assertIsNone(self.cache.get_embedding(query1))
        self.assertIsNotNone(self.cache.get_embedding(query2))
    
    def test_invalidate_all(self):
        """Test clearing all cache."""
        # Set multiple entries
        self.cache.set_embedding("query1", [0.1])
        self.cache.set_embedding("query2", [0.2])
        self.cache.set_selection("query1", {"result": 1})
        
        # Invalidate all
        self.cache.invalidate_all()
        
        # All should be gone
        self.assertIsNone(self.cache.get_embedding("query1"))
        self.assertIsNone(self.cache.get_embedding("query2"))
        self.assertIsNone(self.cache.get_selection("query1"))


class TestCleanup(unittest.TestCase):
    """Test automatic cleanup of expired entries."""
    
    def test_cleanup_removes_expired(self):
        """Test cleanup removes expired entries."""
        cache = QueryCache(embedding_ttl=0.1, cleanup_interval=0.0)
        
        # Set entries
        cache.set_embedding("query1", [0.1])
        cache.set_embedding("query2", [0.2])
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Force cleanup
        cache._cleanup_expired(force=True)
        
        # Check internal state
        self.assertEqual(len(cache._embedding_cache), 0)
    
    def test_cleanup_preserves_fresh(self):
        """Test cleanup preserves fresh entries."""
        cache = QueryCache(embedding_ttl=10.0, cleanup_interval=0.0)
        
        # Set fresh entry
        cache.set_embedding("query", [0.1])
        
        # Cleanup (nothing should be removed)
        cache._cleanup_expired(force=True)
        
        # Should still be cached
        self.assertIsNotNone(cache.get_embedding("query"))


class TestGlobalInstance(unittest.TestCase):
    """Test global cache instance."""
    
    def tearDown(self):
        """Reset global cache after each test."""
        reset_cache()
    
    def test_get_cache_singleton(self):
        """Test get_cache returns singleton."""
        cache1 = get_cache()
        cache2 = get_cache()
        
        self.assertIs(cache1, cache2)
    
    def test_reset_cache(self):
        """Test resetting global cache."""
        cache1 = get_cache()
        reset_cache()
        cache2 = get_cache()
        
        # Should be different instances
        self.assertIsNot(cache1, cache2)
    
    def test_invalidate_cache_on_ingest(self):
        """Test convenience function for ingest invalidation."""
        cache = get_cache()
        
        # Set entry with entity
        cache.set_embedding("query", [0.1], entity_ids={"mem1"})
        
        # Should be cached
        self.assertIsNotNone(cache.get_embedding("query"))
        
        # Invalidate via convenience function
        invalidate_cache_on_ingest({"mem1"})
        
        # Should be invalidated
        self.assertIsNone(cache.get_embedding("query"))


class TestCacheStats(unittest.TestCase):
    """Test cache statistics."""
    
    def test_get_stats(self):
        """Test getting cache statistics."""
        cache = QueryCache()
        
        # Add some entries
        cache.set_embedding("query1", [0.1])
        cache.set_selection("query2", {"result": 1}, entity_ids={"mem1"})
        
        stats = cache.get_stats()
        
        self.assertEqual(stats["embeddings"]["count"], 1)
        self.assertEqual(stats["selections"]["count"], 1)
        self.assertEqual(stats["entities_tracked"], 1)
        self.assertIn("last_cleanup", stats)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def setUp(self):
        """Create fresh cache for each test."""
        reset_cache()
        self.cache = get_cache(embedding_ttl=120.0, selection_ttl=60.0)
    
    def tearDown(self):
        """Reset global cache after each test."""
        reset_cache()
    
    def test_repeated_queries_hit_cache(self):
        """Test: repeated queries hit cache."""
        query = "What is machine learning?"
        embedding = [0.1] * 1536
        result = {
            "context": [{"id": "mem1", "text": "ML is..."}],
            "ranked_ids": ["mem1"],
            "strategy_used": "dual"
        }
        
        # First query - cache miss
        self.assertIsNone(self.cache.get_embedding(query))
        self.assertIsNone(self.cache.get_selection(query))
        
        # Set cache
        self.cache.set_embedding(query, embedding)
        self.cache.set_selection(query, result)
        
        # ✅ Repeated queries hit cache
        for _ in range(5):
            cached_emb = self.cache.get_embedding(query)
            cached_result = self.cache.get_selection(query)
            
            self.assertIsNotNone(cached_emb)
            self.assertIsNotNone(cached_result)
            self.assertEqual(cached_emb, embedding)
            self.assertEqual(cached_result, result)
    
    def test_invalidation_clears_stale_results(self):
        """Test: invalidation test clears stale results."""
        query = "What is entity X?"
        embedding = [0.1] * 1536
        result = {
            "context": [{"id": "mem123", "text": "Entity X is..."}],
            "ranked_ids": ["mem123"]
        }
        
        # Set cache with entity tracking
        entity_ids = {"mem123", "entity_x"}
        self.cache.set_embedding(query, embedding, entity_ids=entity_ids)
        self.cache.set_selection(query, result, entity_ids=entity_ids)
        
        # Verify cached
        self.assertIsNotNone(self.cache.get_embedding(query))
        self.assertIsNotNone(self.cache.get_selection(query))
        
        # ✅ Simulate ingest event affecting entity_x
        invalidate_cache_on_ingest({"entity_x"})
        
        # ✅ Stale results should be cleared
        self.assertIsNone(self.cache.get_embedding(query))
        self.assertIsNone(self.cache.get_selection(query))
    
    def test_ttl_expiration(self):
        """Test: entries expire after TTL."""
        cache = QueryCache(embedding_ttl=0.1, selection_ttl=0.1)
        
        query = "What is AI?"
        embedding = [0.1, 0.2]
        result = {"context": []}
        
        # Set
        cache.set_embedding(query, embedding)
        cache.set_selection(query, result)
        
        # Should be cached
        self.assertIsNotNone(cache.get_embedding(query))
        self.assertIsNotNone(cache.get_selection(query))
        
        # ✅ Wait for TTL
        time.sleep(0.15)
        
        # ✅ Should be expired
        self.assertIsNone(cache.get_embedding(query))
        self.assertIsNone(cache.get_selection(query))
    
    def test_normalized_queries_hit_same_cache(self):
        """Test: normalized queries hit same cache."""
        # Different forms of same query
        queries = [
            "What is AI?",
            "what is ai?",
            "  WHAT   IS   AI?  ",
            "What Is Ai?"
        ]
        
        embedding = [0.1, 0.2]
        
        # Set with first form
        self.cache.set_embedding(queries[0], embedding)
        
        # ✅ All forms should hit same cache
        for query in queries:
            cached = self.cache.get_embedding(query)
            self.assertIsNotNone(cached)
            self.assertEqual(cached, embedding)
    
    def test_role_isolation(self):
        """Test: different roles have isolated caches."""
        query = "Sensitive data query"
        emb_admin = [0.1] * 10
        emb_user = [0.2] * 10
        
        # Set for different roles
        self.cache.set_embedding(query, emb_admin, role="admin")
        self.cache.set_embedding(query, emb_user, role="user")
        
        # ✅ Different roles get different results
        cached_admin = self.cache.get_embedding(query, role="admin")
        cached_user = self.cache.get_embedding(query, role="user")
        
        self.assertEqual(cached_admin, emb_admin)
        self.assertEqual(cached_user, emb_user)
        self.assertNotEqual(cached_admin, cached_user)


if __name__ == "__main__":
    unittest.main()
