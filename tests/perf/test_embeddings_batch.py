#!/usr/bin/env python3
"""
Unit tests for embeddings batching, pooling, and retry logic.

Tests:
1. Batching reduces network calls
2. Retry ceilings are respected
3. Exponential backoff with jitter
4. Connection pooling
5. Rate limit handling
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock, call
from queue import Queue

# Add workspace to path
sys.path.insert(0, '/workspace')

# Mock OpenAI module before importing embeddings
sys.modules['openai'] = Mock()

from adapters.embeddings import (
    EmbeddingBatcher,
    EmbeddingConfig,
    EmbeddingResult,
    EmbeddingPoolExhausted,
    EmbeddingRateLimitError,
    get_embeddings_batcher,
    embed_texts,
    embed_text
)


class TestEmbeddingConfig(unittest.TestCase):
    """Test embedding configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = EmbeddingConfig()
        
        self.assertEqual(config.model, "text-embedding-3-small")
        self.assertEqual(config.batch_size, 8)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.initial_backoff, 1.0)
        self.assertEqual(config.max_backoff, 32.0)
        self.assertEqual(config.jitter_factor, 0.2)
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = EmbeddingConfig(
            model="text-embedding-3-large",
            batch_size=16,
            max_retries=5
        )
        
        self.assertEqual(config.model, "text-embedding-3-large")
        self.assertEqual(config.batch_size, 16)
        self.assertEqual(config.max_retries, 5)


class TestBatching(unittest.TestCase):
    """Test embedding batching logic."""
    
    def test_batches_8_texts_into_single_call(self):
        """Test: 8 texts batched into single API call."""
        config = EmbeddingConfig(batch_size=8, max_retries=0)
        batcher = EmbeddingBatcher(config)
        
        # Mock OpenAI client
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(8)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {"prompt_tokens": 80, "total_tokens": 80}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            mock_client.embeddings.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            
            # Embed 8 texts
            texts = [f"text_{i}" for i in range(8)]
            result = batcher.embed_batch(texts)
            
            # Should make exactly 1 API call
            self.assertEqual(mock_client.embeddings.create.call_count, 1)
            self.assertEqual(len(result.embeddings), 8)
            self.assertEqual(result.batch_size, 1)  # 1 batch
    
    def test_batches_16_texts_into_two_calls(self):
        """Test: 16 texts batched into 2 API calls."""
        config = EmbeddingConfig(batch_size=8, max_retries=0)
        batcher = EmbeddingBatcher(config)
        
        # Mock OpenAI client
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(8)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {"prompt_tokens": 80, "total_tokens": 80}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            mock_client.embeddings.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            
            # Embed 16 texts
            texts = [f"text_{i}" for i in range(16)]
            result = batcher.embed_batch(texts)
            
            # Should make exactly 2 API calls (16 / 8 = 2)
            self.assertEqual(mock_client.embeddings.create.call_count, 2)
            self.assertEqual(len(result.embeddings), 16)
            self.assertEqual(result.batch_size, 2)  # 2 batches
    
    def test_fewer_network_calls_with_batching(self):
        """Test: batching reduces network calls."""
        config = EmbeddingConfig(batch_size=8, max_retries=0)
        batcher = EmbeddingBatcher(config)
        
        def create_mock_response(batch_size):
            """Create mock response matching batch size."""
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(batch_size)]
            mock_response.usage = Mock()
            mock_response.usage.model_dump = lambda: {"prompt_tokens": batch_size * 10, "total_tokens": batch_size * 10}
            return mock_response
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            # Return responses matching the batch sizes: 8, 8, 4
            mock_client.embeddings.create.side_effect = [
                create_mock_response(8),
                create_mock_response(8),
                create_mock_response(4)
            ]
            MockOpenAI.return_value = mock_client
            
            # Without batching: 20 texts = 20 calls
            # With batching (batch_size=8): 20 texts = 3 calls (8+8+4)
            texts = [f"text_{i}" for i in range(20)]
            result = batcher.embed_batch(texts)
            
            # Should make only 3 API calls instead of 20
            self.assertEqual(mock_client.embeddings.create.call_count, 3)
            self.assertEqual(len(result.embeddings), 20)
            self.assertEqual(result.batch_size, 3)


class TestRetryLogic(unittest.TestCase):
    """Test retry logic and ceilings."""
    
    def test_retry_ceiling_respected(self):
        """Test: retries capped at max_retries."""
        config = EmbeddingConfig(batch_size=8, max_retries=3)
        batcher = EmbeddingBatcher(config)
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            # Always fail with rate limit error
            mock_client.embeddings.create.side_effect = Exception("429 Rate limit exceeded")
            MockOpenAI.return_value = mock_client
            
            # Should retry up to max_retries, then raise
            with self.assertRaises(EmbeddingRateLimitError):
                batcher.embed_batch(["text"])
            
            # Should call: initial + 3 retries = 4 total calls
            self.assertEqual(mock_client.embeddings.create.call_count, 4)
    
    def test_retry_on_rate_limit_429(self):
        """Test: retries on 429 rate limit errors."""
        config = EmbeddingConfig(batch_size=8, max_retries=2, initial_backoff=0.01)
        batcher = EmbeddingBatcher(config)
        
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            # Fail twice, then succeed
            mock_client.embeddings.create.side_effect = [
                Exception("429 Too Many Requests"),
                Exception("429 Too Many Requests"),
                mock_response
            ]
            MockOpenAI.return_value = mock_client
            
            result = batcher.embed_batch(["text"])
            
            # Should succeed after 2 retries
            self.assertEqual(len(result.embeddings), 1)
            self.assertEqual(result.retries, 2)
            self.assertEqual(mock_client.embeddings.create.call_count, 3)
    
    def test_retry_on_5xx_errors(self):
        """Test: retries on 5xx server errors."""
        config = EmbeddingConfig(batch_size=8, max_retries=2, initial_backoff=0.01)
        batcher = EmbeddingBatcher(config)
        
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            # Fail with 503, then succeed
            mock_client.embeddings.create.side_effect = [
                Exception("503 Service Unavailable"),
                mock_response
            ]
            MockOpenAI.return_value = mock_client
            
            result = batcher.embed_batch(["text"])
            
            # Should succeed after 1 retry
            self.assertEqual(len(result.embeddings), 1)
            self.assertEqual(result.retries, 1)
            self.assertEqual(mock_client.embeddings.create.call_count, 2)
    
    def test_no_retry_on_non_retryable_errors(self):
        """Test: no retry on non-retryable errors (e.g., 400)."""
        config = EmbeddingConfig(batch_size=8, max_retries=3)
        batcher = EmbeddingBatcher(config)
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            # Non-retryable error
            mock_client.embeddings.create.side_effect = Exception("400 Bad Request")
            MockOpenAI.return_value = mock_client
            
            with self.assertRaises(Exception) as cm:
                batcher.embed_batch(["text"])
            
            # Should not retry (only 1 call)
            self.assertEqual(mock_client.embeddings.create.call_count, 1)


class TestExponentialBackoff(unittest.TestCase):
    """Test exponential backoff with jitter."""
    
    def test_backoff_increases_exponentially(self):
        """Test: backoff time increases exponentially."""
        config = EmbeddingConfig(initial_backoff=1.0, max_backoff=32.0, jitter_factor=0)
        batcher = EmbeddingBatcher(config)
        
        # Calculate backoff for attempts 0, 1, 2, 3
        backoff_0 = batcher._calculate_backoff(0)  # 1.0 * 2^0 = 1.0
        backoff_1 = batcher._calculate_backoff(1)  # 1.0 * 2^1 = 2.0
        backoff_2 = batcher._calculate_backoff(2)  # 1.0 * 2^2 = 4.0
        backoff_3 = batcher._calculate_backoff(3)  # 1.0 * 2^3 = 8.0
        
        # Should increase exponentially
        self.assertAlmostEqual(backoff_0, 1.0, places=1)
        self.assertAlmostEqual(backoff_1, 2.0, places=1)
        self.assertAlmostEqual(backoff_2, 4.0, places=1)
        self.assertAlmostEqual(backoff_3, 8.0, places=1)
    
    def test_backoff_caps_at_max(self):
        """Test: backoff caps at max_backoff."""
        config = EmbeddingConfig(initial_backoff=1.0, max_backoff=10.0, jitter_factor=0)
        batcher = EmbeddingBatcher(config)
        
        # Large attempt number
        backoff = batcher._calculate_backoff(10)  # Would be 1024, capped at 10
        
        self.assertAlmostEqual(backoff, 10.0, places=1)
    
    def test_backoff_includes_jitter(self):
        """Test: backoff includes jitter."""
        config = EmbeddingConfig(initial_backoff=1.0, jitter_factor=0.2)
        batcher = EmbeddingBatcher(config)
        
        # Calculate multiple backoffs for attempt 0
        backoffs = [batcher._calculate_backoff(0) for _ in range(10)]
        
        # All should be different (due to jitter)
        unique_backoffs = set(backoffs)
        self.assertGreater(len(unique_backoffs), 1, "Jitter should cause variance")
        
        # All should be within reasonable range: 1.0 +/- 20%
        # 1.0 * 0.8 = 0.8 to 1.0 * 1.2 = 1.2
        for backoff in backoffs:
            self.assertGreaterEqual(backoff, 0.7)
            self.assertLessEqual(backoff, 1.3)


class TestConnectionPooling(unittest.TestCase):
    """Test connection pool functionality."""
    
    def test_connection_pool_initialized(self):
        """Test: connection pool is initialized."""
        config = EmbeddingConfig()
        batcher = EmbeddingBatcher(config)
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            MockOpenAI.return_value = mock_client
            
            # Get client (triggers initialization)
            client = batcher._get_client()
            
            # Should have initialized pool
            self.assertTrue(batcher._initialized)
            
            # Return client
            batcher._return_client(client)
    
    def test_connection_pool_reuses_clients(self):
        """Test: pool reuses clients."""
        config = EmbeddingConfig()
        batcher = EmbeddingBatcher(config)
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            MockOpenAI.return_value = mock_client
            
            # Get and return client twice
            client1 = batcher._get_client()
            batcher._return_client(client1)
            
            client2 = batcher._get_client()
            batcher._return_client(client2)
            
            # Should have created only pool_size clients initially
            # (3 clients for pool initialization)
            self.assertEqual(MockOpenAI.call_count, 3)
    
    def test_pool_exhaustion_raises_error(self):
        """Test: pool exhaustion raises EmbeddingPoolExhausted."""
        config = EmbeddingConfig()
        batcher = EmbeddingBatcher(config)
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            MockOpenAI.return_value = mock_client
            
            # Get all clients from pool (3 clients)
            clients = []
            for _ in range(3):
                clients.append(batcher._get_client())
            
            # Try to get one more (should timeout and raise)
            with patch('adapters.embeddings.Queue.get') as mock_get:
                from queue import Empty
                mock_get.side_effect = Empty()
                
                with self.assertRaises(EmbeddingPoolExhausted):
                    batcher._get_client()


class TestHelperFunctions(unittest.TestCase):
    """Test convenience helper functions."""
    
    def test_should_retry_on_429(self):
        """Test: _should_retry returns True for 429."""
        batcher = EmbeddingBatcher()
        
        error = Exception("429 Rate limit exceeded")
        self.assertTrue(batcher._should_retry(error))
    
    def test_should_retry_on_5xx(self):
        """Test: _should_retry returns True for 5xx."""
        batcher = EmbeddingBatcher()
        
        self.assertTrue(batcher._should_retry(Exception("500 Internal Server Error")))
        self.assertTrue(batcher._should_retry(Exception("502 Bad Gateway")))
        self.assertTrue(batcher._should_retry(Exception("503 Service Unavailable")))
        self.assertTrue(batcher._should_retry(Exception("504 Gateway Timeout")))
    
    def test_should_not_retry_on_4xx(self):
        """Test: _should_retry returns False for 4xx (except 429)."""
        batcher = EmbeddingBatcher()
        
        self.assertFalse(batcher._should_retry(Exception("400 Bad Request")))
        self.assertFalse(batcher._should_retry(Exception("401 Unauthorized")))
        self.assertFalse(batcher._should_retry(Exception("404 Not Found")))


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    def test_embed_texts_convenience(self):
        """Test: embed_texts convenience function."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(3)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            mock_client.embeddings.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            
            # Reset global instance
            import adapters.embeddings
            adapters.embeddings._batcher_instance = None
            
            embeddings = embed_texts(["text1", "text2", "text3"])
            
            self.assertEqual(len(embeddings), 3)
            self.assertEqual(len(embeddings[0]), 1536)
    
    def test_embed_text_convenience(self):
        """Test: embed_text convenience function."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            mock_client.embeddings.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            
            # Reset global instance
            import adapters.embeddings
            adapters.embeddings._batcher_instance = None
            
            embedding = embed_text("single text")
            
            self.assertEqual(len(embedding), 1536)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def test_fewer_network_calls_at_same_workload(self):
        """Test: batching reduces network calls at same workload."""
        config = EmbeddingConfig(batch_size=8, max_retries=0)
        batcher = EmbeddingBatcher(config)
        
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(8)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            mock_client.embeddings.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            
            # Workload: 24 texts
            # Without batching: 24 network calls
            # With batching (batch_size=8): 3 network calls (24/8 = 3)
            texts = [f"text_{i}" for i in range(24)]
            result = batcher.embed_batch(texts)
            
            # ? Fewer network calls
            network_calls = mock_client.embeddings.create.call_count
            self.assertEqual(network_calls, 3, "Should make only 3 calls instead of 24")
            
            # ? Same workload results
            self.assertEqual(len(result.embeddings), 24, "Should return all 24 embeddings")
    
    def test_retries_capped_at_max_retries(self):
        """Test: retries capped at configured max."""
        config = EmbeddingConfig(batch_size=8, max_retries=3, initial_backoff=0.01)
        batcher = EmbeddingBatcher(config)
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            # Always fail
            mock_client.embeddings.create.side_effect = Exception("429 Rate limit")
            MockOpenAI.return_value = mock_client
            
            with self.assertRaises(EmbeddingRateLimitError):
                batcher.embed_batch(["text"])
            
            # ? Retries capped
            # Initial call + max_retries (3) = 4 total
            self.assertEqual(mock_client.embeddings.create.call_count, 4)
    
    def test_exponential_backoff_with_jitter(self):
        """Test: exponential backoff with jitter on 429/5xx."""
        config = EmbeddingConfig(
            batch_size=8,
            max_retries=2,
            initial_backoff=0.1,
            jitter_factor=0.2
        )
        batcher = EmbeddingBatcher(config)
        
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            # Fail twice with 429, then succeed
            mock_client.embeddings.create.side_effect = [
                Exception("429 Too Many Requests"),
                Exception("429 Too Many Requests"),
                mock_response
            ]
            MockOpenAI.return_value = mock_client
            
            with patch('time.sleep') as mock_sleep:
                result = batcher.embed_batch(["text"])
                
                # ? Should have called sleep (backoff)
                self.assertEqual(mock_sleep.call_count, 2)
                
                # ? Backoff should increase
                call_args = [call[0][0] for call in mock_sleep.call_args_list]
                self.assertGreater(call_args[1], call_args[0], "Second backoff should be longer")
    
    def test_batch_size_8(self):
        """Test: default batch size is 8."""
        config = EmbeddingConfig()
        self.assertEqual(config.batch_size, 8)
        
        batcher = EmbeddingBatcher(config)
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(8)]
        mock_response.usage = Mock()
        mock_response.usage.model_dump = lambda: {}
        
        with patch('adapters.embeddings.OpenAI') as MockOpenAI:
            mock_client = Mock()
            mock_client.embeddings.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            
            # 8 texts should fit in 1 batch
            texts = [f"text_{i}" for i in range(8)]
            result = batcher.embed_batch(texts)
            
            # ? Exactly 1 call for 8 texts
            self.assertEqual(mock_client.embeddings.create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
