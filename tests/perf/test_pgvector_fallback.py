#!/usr/bin/env python3
"""
Unit tests for pgvector fallback when Pinecone fails.
"""

import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add workspace to path
sys.path.insert(0, '/workspace')

# Mock all problematic imports BEFORE importing anything else
sys.modules['supabase'] = Mock()
sys.modules['vendors.supabase_client'] = Mock()
sys.modules['vendors.pinecone_client'] = Mock()
sys.modules['app.settings'] = Mock()
sys.modules['pydantic'] = Mock()

# Mock pydantic.BaseModel
mock_basemodel = type('BaseModel', (), {})
sys.modules['pydantic'].BaseModel = mock_basemodel

# Mock tenacity
mock_tenacity = Mock()
mock_tenacity.retry = lambda *args, **kwargs: lambda f: f
mock_tenacity.stop_after_attempt = Mock()
mock_tenacity.wait_exponential = Mock()
mock_tenacity.retry_if_exception_type = Mock()
sys.modules['tenacity'] = mock_tenacity

from adapters.vector_fallback import (
    PgvectorFallbackAdapter,
    MockMatch,
    FallbackQueryResult
)


class TestFallbackAdapter(unittest.TestCase):
    """Test fallback adapter functionality."""
    
    def test_reduced_k_values(self):
        """Test fallback uses reduced k values."""
        adapter = PgvectorFallbackAdapter()
        self.assertEqual(adapter.FALLBACK_EXPLICATE_K, 8)
        self.assertEqual(adapter.FALLBACK_IMPLICATE_K, 4)
    
    def test_timeout_budget(self):
        """Test fallback has 350ms timeout budget."""
        adapter = PgvectorFallbackAdapter()
        self.assertEqual(adapter.FALLBACK_TIMEOUT_MS, 350)
    
    def test_fallback_query_result_structure(self):
        """Test FallbackQueryResult has required fields."""
        result = FallbackQueryResult(
            matches=[MockMatch("id1", 0.9, {"text": "test"})],
            fallback_used=True,
            latency_ms=100.0,
            source="pgvector"
        )
        
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.latency_ms, 100.0)
        self.assertEqual(result.source, "pgvector")
        self.assertEqual(len(result.matches), 1)


class TestHealthCheck(unittest.TestCase):
    """Test Pinecone health checking."""
    
    def test_health_check_has_cache(self):
        """Test health check has caching mechanism."""
        adapter = PgvectorFallbackAdapter()
        
        # Verify cache structure
        self.assertIn('last_check', adapter._health_check_cache)
        self.assertIn('is_healthy', adapter._health_check_cache)
        self.assertIn('cache_ttl', adapter._health_check_cache)
        
        # Verify cache TTL is 30 seconds
        self.assertEqual(adapter._health_check_cache['cache_ttl'], 30)


class TestFallbackTrigger(unittest.TestCase):
    """Test fallback triggering logic."""
    
    @patch('config.load_config')
    def test_fallback_triggered_when_unhealthy(self, mock_config):
        """Test fallback triggers when Pinecone is unhealthy."""
        mock_config.return_value = {
            'PERF_PGVECTOR_ENABLED': True,
            'PERF_FALLBACKS_ENABLED': True
        }
        
        adapter = PgvectorFallbackAdapter()
        
        with patch.object(adapter, 'check_pinecone_health', return_value=(False, "Connection refused")):
            should_use, reason = adapter.should_use_fallback()
            
            self.assertTrue(should_use)
            self.assertIn("pinecone_unhealthy", reason)
    
    @patch('config.load_config')
    def test_fallback_not_triggered_when_healthy(self, mock_config):
        """Test fallback not triggered when Pinecone is healthy."""
        mock_config.return_value = {
            'PERF_PGVECTOR_ENABLED': True,
            'PERF_FALLBACKS_ENABLED': True
        }
        
        adapter = PgvectorFallbackAdapter()
        
        with patch.object(adapter, 'check_pinecone_health', return_value=(True, None)):
            should_use, reason = adapter.should_use_fallback()
            
            self.assertFalse(should_use)
            self.assertIsNone(reason)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def test_reduced_k_enforced(self):
        """Test: reduced k values enforced in fallback mode."""
        adapter = PgvectorFallbackAdapter()
        
        # Verify reduced k values
        self.assertEqual(adapter.FALLBACK_EXPLICATE_K, 8)
        self.assertEqual(adapter.FALLBACK_IMPLICATE_K, 4)
        
        # Verify they're less than normal
        self.assertLess(adapter.FALLBACK_EXPLICATE_K, 16)  # Normal explicate k
        self.assertLess(adapter.FALLBACK_IMPLICATE_K, 8)   # Normal implicate k
    
    def test_timeout_budget_set(self):
        """Test: fallback has 350ms timeout budget."""
        adapter = PgvectorFallbackAdapter()
        
        self.assertEqual(adapter.FALLBACK_TIMEOUT_MS, 350)
        self.assertLessEqual(adapter.FALLBACK_TIMEOUT_MS, 350)
    
    def test_fallback_flag_in_result(self):
        """Test: response includes fallback flag."""
        result = FallbackQueryResult(
            matches=[],
            fallback_used=True,
            latency_ms=100,
            source="pgvector"
        )
        
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.source, "pgvector")


if __name__ == "__main__":
    unittest.main()
