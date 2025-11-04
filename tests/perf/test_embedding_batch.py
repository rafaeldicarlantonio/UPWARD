#!/usr/bin/env python3
"""
Unit tests for embedding batching and retry logic.

Tests:
1. Batching reduces network calls
2. Retry limits enforced
3. Exponential backoff with jitter
4. Connection pooling
5. No thundering herd
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock, call
from typing import List

# Add workspace to path
sys.path.insert(0, '/workspace')

# Mock openai before importing
sys.modules['openai'] = Mock()

from adapters.embeddings import (
    EmbeddingBatcher,
    EmbeddingConfig,
    EmbeddingResult,
    EmbeddingRateLimitError,
    EmbeddingPoolExhausted,
    get_embeddings_batcher,
    embed_texts,
    embed_text
)


class MockEmbeddingResponse:
    """Mock OpenAI embedding response."""
    
    def __init__(self, num_embeddings: int, dimension: int = 1536):
        self.data = [
            Mock(embedding=[0.1 * i] * dimension)
            for i in range(num_embeddings)
        ]
        self.usage = Mock()
        self.usage.model_dump.return_value = {
            "prompt_tokens": num_embeddings * 10,
            "total_tokens": num_embeddings * 10
        }


class TestEmbeddingConfig(unittest.TestCase):
    """Test embedding configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = EmbeddingConfig()
        
        self.assertEqual(config.batch_size, 8)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.initial_backoff, 1.0)
        self.assertEqual(config.max_backoff, 32.0)
        self.assertEqual(config.jitter_factor, 0.2)
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = EmbeddingConfig(
            batch_size=16,
            max_retries=5,
            initial_backoff=0.5
        )
        
        self.assertEqual(config.batch_size, 16)
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.initial_backoff, 0.5)


class TestBatching(unittest.TestCase):
    """Test batching logic."""
    
    def test_single_batch(self):
        """Test embedding within single batch."""
        config = EmbeddingConfig(batch_size=8)
        batcher = EmbeddingBatcher(config)
        
        # Mock client
        mock_client = Mock()
        mock_client.embeddings.create.return_value = MockEmbeddingResponse(5)
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                result = batcher.embed_batch(["text1", "text2", "text3", "text4", "text5"])
        
        # Should make single API call
        self.assertEqual(mock_client.embeddings.create.call_count, 1)
        self.assertEqual(len(result.embeddings), 5)
        self.assertEqual(result.batch_size, 1)
    
    def test_multiple_batches(self):
        """Test splitting into multiple batches."""
        config = EmbeddingConfig(batch_size=3)
        batcher = EmbeddingBatcher(config)
        
        # Mock client
        mock_client = Mock()
        mock_client.embeddings.create.side_effect = [
            MockEmbeddingResponse(3),
            MockEmbeddingResponse(3),
            MockEmbeddingResponse(2)
        ]
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                result = batcher.embed_batch([f"text{i}" for i in range(8)])
        
        # Should make 3 API calls (3, 3, 2)
        self.assertEqual(mock_client.embeddings.create.call_count, 3)
        self.assertEqual(len(result.embeddings), 8)
        self.assertEqual(result.batch_size, 3)
    
    def test_batching_reduces_calls(self):
        """Test that batching reduces network calls."""
        config = EmbeddingConfig(batch_size=8)
        batcher = EmbeddingBatcher(config)
        
        # Mock client
        mock_client = Mock()
        mock_client.embeddings.create.return_value = MockEmbeddingResponse(8)
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                # 8 texts in one batch
                result = batcher.embed_batch([f"text{i}" for i in range(8)])
        
        # ✅ Only 1 call for 8 texts
        self.assertEqual(mock_client.embeddings.create.call_count, 1)
        
        # Without batching, would need 8 calls
        # With batching: 1 call
        # Reduction: 8x
    
    def test_empty_batch(self):
        """Test handling empty input."""
        batcher = EmbeddingBatcher()
        result = batcher.embed_batch([])
        
        self.assertEqual(len(result.embeddings), 0)
        self.assertEqual(result.batch_size, 0)


class TestRetryLogic(unittest.TestCase):
    """Test retry logic and limits."""
    
    def test_success_no_retry(self):
        """Test successful call without retries."""
        config = EmbeddingConfig(max_retries=3)
        batcher = EmbeddingBatcher(config)
        
        mock_client = Mock()
        mock_client.embeddings.create.return_value = MockEmbeddingResponse(1)
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                result = batcher.embed_batch(["text"])
        
        # No retries needed
        self.assertEqual(result.retries, 0)
        self.assertEqual(mock_client.embeddings.create.call_count, 1)
    
    def test_retry_on_rate_limit(self):
        """Test retry on 429 rate limit."""
        config = EmbeddingConfig(max_retries=2, initial_backoff=0.1)
        batcher = EmbeddingBatcher(config)
        
        mock_client = Mock()
        # Fail twice, then succeed
        mock_client.embeddings.create.side_effect = [
            Exception("429 Rate limit exceeded"),
            Exception("429 Rate limit exceeded"),
            MockEmbeddingResponse(1)
        ]
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                result = batcher.embed_batch(["text"])
        
        # Should retry twice and succeed on 3rd attempt
        self.assertEqual(result.retries, 2)
        self.assertEqual(mock_client.embeddings.create.call_count, 3)
    
    def test_retry_limit_enforced(self):
        """Test that retry limit is enforced."""
        config = EmbeddingConfig(max_retries=2, initial_backoff=0.1)
        batcher = EmbeddingBatcher(config)
        
        mock_client = Mock()
        # Always fail with rate limit
        mock_client.embeddings.create.side_effect = Exception("429 Rate limit exceeded")
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                with self.assertRaises(EmbeddingRateLimitError) as cm:
                    batcher.embed_batch(["text"])
        
        # ✅ Should try max_retries + 1 times (initial + 2 retries = 3 total)
        self.assertEqual(mock_client.embeddings.create.call_count, 3)
        self.assertIn("after 2 retries", str(cm.exception))
    
    def test_no_retry_on_client_error(self):
        """Test no retry on non-retryable errors."""
        config = EmbeddingConfig(max_retries=3)
        batcher = EmbeddingBatcher(config)
        
        mock_client = Mock()
        mock_client.embeddings.create.side_effect = Exception("400 Bad Request")
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                with self.assertRaises(Exception) as cm:
                    batcher.embed_batch(["text"])
        
        # Should not retry on 400
        self.assertEqual(mock_client.embeddings.create.call_count, 1)
        self.assertIn("400", str(cm.exception))


class TestExponentialBackoff(unittest.TestCase):
    """Test exponential backoff with jitter."""
    
    def test_backoff_increases_exponentially(self):
        """Test backoff increases exponentially."""
        config = EmbeddingConfig(initial_backoff=1.0, jitter_factor=0.0)
        batcher = EmbeddingBatcher(config)
        
        # Calculate backoff for different attempts
        backoff0 = batcher._calculate_backoff(0)
        backoff1 = batcher._calculate_backoff(1)
        backoff2 = batcher._calculate_backoff(2)
        
        # Should roughly double each time (no jitter)
        self.assertAlmostEqual(backoff0, 1.0, delta=0.1)
        self.assertAlmostEqual(backoff1, 2.0, delta=0.1)
        self.assertAlmostEqual(backoff2, 4.0, delta=0.1)
    
    def test_backoff_caps_at_max(self):
        """Test backoff caps at max_backoff."""
        config = EmbeddingConfig(
            initial_backoff=1.0,
            max_backoff=10.0,
            jitter_factor=0.0
        )
        batcher = EmbeddingBatcher(config)
        
        # High attempt number
        backoff = batcher._calculate_backoff(10)  # Would be 1024 without cap
        
        # Should be capped at max_backoff
        self.assertLessEqual(backoff, 10.0)
    
    def test_jitter_prevents_thundering_herd(self):
        """Test jitter adds randomness to prevent thundering herd."""
        config = EmbeddingConfig(initial_backoff=1.0, jitter_factor=0.2)
        batcher = EmbeddingBatcher(config)
        
        # Calculate backoff multiple times
        backoffs = [batcher._calculate_backoff(0) for _ in range(10)]
        
        # All should be different (jitter)
        unique_backoffs = set(backoffs)
        self.assertGreater(len(unique_backoffs), 1, "Jitter should create variation")
        
        # All should be within jitter range of base (1.0 +/- 20%)
        for b in backoffs:
            self.assertGreater(b, 0.7)
            self.assertLess(b, 1.3)
    
    def test_concurrent_retries_have_different_backoffs(self):
        """Test concurrent retries don't align (no thundering herd)."""
        config = EmbeddingConfig(initial_backoff=1.0, jitter_factor=0.2)
        
        # Simulate 5 concurrent clients
        batchers = [EmbeddingBatcher(config) for _ in range(5)]
        
        # All calculate backoff for attempt 1
        backoffs = [b._calculate_backoff(1) for b in batchers]
        
        # ✅ Should all be different due to jitter
        unique_backoffs = set(backoffs)
        self.assertGreater(len(unique_backoffs), 1, "Jitter prevents thundering herd")


class TestConnectionPooling(unittest.TestCase):
    """Test connection pooling."""
    
    def test_pool_initialization(self):
        """Test connection pool is initialized."""
        batcher = EmbeddingBatcher()
        
        # Force initialization
        with patch('adapters.embeddings.OpenAI') as mock_openai:
            mock_openai.return_value = Mock()
            client = batcher._get_client()
            batcher._return_client(client)
        
        self.assertTrue(batcher._initialized)
        self.assertEqual(mock_openai.call_count, 3)  # Pool size of 3
    
    def test_pool_reuse(self):
        """Test clients are reused from pool."""
        batcher = EmbeddingBatcher()
        
        with patch('adapters.embeddings.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            # Get and return client twice
            client1 = batcher._get_client()
            batcher._return_client(client1)
            
            client2 = batcher._get_client()
            batcher._return_client(client2)
        
        # Should reuse, not create new clients
        self.assertEqual(mock_openai.call_count, 3)  # Only initial pool creation
    
    def test_pool_exhaustion(self):
        """Test pool exhaustion handling."""
        config = EmbeddingConfig()
        batcher = EmbeddingBatcher(config)
        
        with patch('adapters.embeddings.OpenAI') as mock_openai:
            mock_openai.return_value = Mock()
            
            # Get all clients from pool
            clients = []
            for _ in range(3):
                clients.append(batcher._get_client())
            
            # Next get should timeout
            with self.assertRaises(EmbeddingPoolExhausted):
                batcher._get_client()
            
            # Return clients
            for c in clients:
                batcher._return_client(c)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    def test_embed_texts(self):
        """Test embed_texts convenience function."""
        with patch('adapters.embeddings._batcher_instance', None):
            mock_batcher = Mock()
            mock_batcher.embed_batch.return_value = EmbeddingResult(
                embeddings=[[0.1], [0.2]],
                batch_size=1
            )
            
            with patch('adapters.embeddings.EmbeddingBatcher', return_value=mock_batcher):
                result = embed_texts(["text1", "text2"])
        
        self.assertEqual(len(result), 2)
        mock_batcher.embed_batch.assert_called_once()
    
    def test_embed_text(self):
        """Test embed_text convenience function."""
        with patch('adapters.embeddings._batcher_instance', None):
            mock_batcher = Mock()
            mock_batcher.embed_single.return_value = [0.1, 0.2]
            
            with patch('adapters.embeddings.EmbeddingBatcher', return_value=mock_batcher):
                result = embed_text("text")
        
        self.assertEqual(result, [0.1, 0.2])
        mock_batcher.embed_single.assert_called_once()


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def test_throughput_shows_fewer_network_calls(self):
        """Test: throughput test shows fewer network calls due to batching."""
        config = EmbeddingConfig(batch_size=8)
        batcher = EmbeddingBatcher(config)
        
        # Mock client
        mock_client = Mock()
        call_count = 0
        
        def mock_create(input, model):
            nonlocal call_count
            call_count += 1
            return MockEmbeddingResponse(len(input))
        
        mock_client.embeddings.create.side_effect = mock_create
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                # Embed 24 texts
                result = batcher.embed_batch([f"text{i}" for i in range(24)])
        
        # ✅ Without batching: 24 calls
        # ✅ With batching (batch_size=8): 3 calls (24/8 = 3)
        self.assertEqual(call_count, 3, "Should make 3 batched calls")
        self.assertEqual(len(result.embeddings), 24)
        
        # Verify batching efficiency: 8x reduction
        calls_without_batching = 24
        calls_with_batching = call_count
        efficiency = calls_without_batching / calls_with_batching
        self.assertGreaterEqual(efficiency, 8.0)
    
    def test_retries_capped(self):
        """Test: retries are capped at max_retries."""
        config = EmbeddingConfig(max_retries=3, initial_backoff=0.05)
        batcher = EmbeddingBatcher(config)
        
        mock_client = Mock()
        attempt_count = 0
        
        def failing_create(input, model):
            nonlocal attempt_count
            attempt_count += 1
            raise Exception("503 Service Unavailable")
        
        mock_client.embeddings.create.side_effect = failing_create
        
        with patch.object(batcher, '_get_client', return_value=mock_client):
            with patch.object(batcher, '_return_client'):
                with self.assertRaises(Exception):
                    batcher.embed_batch(["text"])
        
        # ✅ Retries capped: initial attempt + max_retries = 4 total
        self.assertEqual(attempt_count, 4)
    
    def test_no_thundering_herd(self):
        """Test: jitter prevents thundering herd."""
        config = EmbeddingConfig(initial_backoff=1.0, jitter_factor=0.3)
        
        # Simulate 10 concurrent clients all retrying at the same time
        batchers = [EmbeddingBatcher(config) for _ in range(10)]
        
        # All calculate backoff for same attempt
        backoffs = [b._calculate_backoff(2) for b in batchers]
        
        # ✅ All backoffs should be different (no thundering herd)
        unique_backoffs = len(set(backoffs))
        self.assertGreater(unique_backoffs, 7, "Jitter should create variation")
        
        # Calculate spread
        backoff_range = max(backoffs) - min(backoffs)
        mean_backoff = sum(backoffs) / len(backoffs)
        
        # ✅ Spread should be significant (30% jitter on ~4s backoff = ~1.2s spread)
        self.assertGreater(backoff_range, 1.0, "Should have significant spread")


if __name__ == "__main__":
    unittest.main()
