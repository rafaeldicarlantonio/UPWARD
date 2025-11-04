#!/usr/bin/env python3
"""
adapters/embeddings.py — Embeddings adapter with batching and retry logic.

Features:
- Batch up to 8 prompts per API call
- Connection pool with keep-alive
- Exponential backoff with jitter for 429/5xx errors
- Retry limits to prevent infinite loops
- Metrics tracking
"""

import os
import time
import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import threading
from queue import Queue, Empty

from openai import OpenAI
from core.metrics import increment_counter, observe_histogram


@dataclass
class EmbeddingConfig:
    """Configuration for embedding service."""
    model: str = "text-embedding-3-small"
    batch_size: int = 8
    max_retries: int = 3
    initial_backoff: float = 1.0  # seconds
    max_backoff: float = 32.0  # seconds
    jitter_factor: float = 0.2  # 20% jitter
    timeout: float = 30.0  # seconds


@dataclass
class EmbeddingResult:
    """Result of embedding operation."""
    embeddings: List[List[float]]
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    retries: int = 0
    batch_size: int = 0


class EmbeddingPoolExhausted(Exception):
    """Raised when connection pool is exhausted."""
    pass


class EmbeddingRateLimitError(Exception):
    """Raised when rate limit is hit and retries exhausted."""
    pass


class EmbeddingBatcher:
    """
    Embeddings service with batching and retry logic.
    
    Features:
    - Batches up to 8 prompts per call
    - Exponential backoff with jitter
    - Connection pool with keep-alive
    - Retry limits
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize embeddings batcher.
        
        Args:
            config: Optional configuration (defaults to EmbeddingConfig())
        """
        self.config = config or EmbeddingConfig()
        
        # Connection pool (small pool with keep-alive)
        self._pool_size = 3
        self._pool: Queue = Queue(maxsize=self._pool_size)
        self._pool_lock = threading.Lock()
        self._initialized = False
    
    def _get_client(self) -> OpenAI:
        """Get client from pool or create new one."""
        if not self._initialized:
            with self._pool_lock:
                if not self._initialized:
                    # Initialize pool
                    for _ in range(self._pool_size):
                        client = OpenAI(
                            timeout=self.config.timeout,
                            max_retries=0  # We handle retries ourselves
                        )
                        self._pool.put(client)
                    self._initialized = True
        
        try:
            # Try to get from pool (non-blocking)
            return self._pool.get(block=True, timeout=5.0)
        except Empty:
            increment_counter("embeddings.pool_exhausted")
            raise EmbeddingPoolExhausted("Connection pool exhausted")
    
    def _return_client(self, client: OpenAI):
        """Return client to pool."""
        try:
            self._pool.put(client, block=False)
        except:
            # Pool full, let it be garbage collected
            pass
    
    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate backoff time with exponential backoff and jitter.
        
        Args:
            attempt: Retry attempt number (0-indexed)
            
        Returns:
            Backoff time in seconds
        """
        # Exponential backoff: initial * (2 ^ attempt)
        backoff = self.config.initial_backoff * (2 ** attempt)
        
        # Cap at max_backoff
        backoff = min(backoff, self.config.max_backoff)
        
        # Add jitter: random +/- jitter_factor
        jitter_range = backoff * self.config.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)
        
        return max(0.1, backoff + jitter)  # At least 100ms
    
    def _should_retry(self, error: Exception) -> bool:
        """
        Determine if error is retryable.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if should retry, False otherwise
        """
        error_str = str(error).lower()
        
        # Retry on rate limits (429)
        if "429" in error_str or "rate limit" in error_str:
            return True
        
        # Retry on server errors (5xx)
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True
        
        # Retry on timeout
        if "timeout" in error_str:
            return True
        
        return False
    
    def embed_batch(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> EmbeddingResult:
        """
        Embed a batch of texts with automatic batching and retry logic.
        
        Args:
            texts: List of texts to embed (will be batched automatically)
            model: Optional model override
            
        Returns:
            EmbeddingResult with embeddings and metadata
        """
        if not texts:
            return EmbeddingResult(embeddings=[], batch_size=0)
        
        model = model or self.config.model
        
        # Split into batches of config.batch_size
        batches = [
            texts[i:i + self.config.batch_size]
            for i in range(0, len(texts), self.config.batch_size)
        ]
        
        all_embeddings = []
        total_usage = {"prompt_tokens": 0, "total_tokens": 0}
        total_latency = 0.0
        max_retries = 0
        total_batches = len(batches)
        
        for batch_idx, batch in enumerate(batches):
            result = self._embed_single_batch(
                batch,
                model,
                batch_idx=batch_idx,
                total_batches=total_batches
            )
            
            all_embeddings.extend(result.embeddings)
            
            # Aggregate metrics
            total_usage["prompt_tokens"] += result.usage.get("prompt_tokens", 0)
            total_usage["total_tokens"] += result.usage.get("total_tokens", 0)
            total_latency += result.latency_ms
            max_retries = max(max_retries, result.retries)
        
        return EmbeddingResult(
            embeddings=all_embeddings,
            usage=total_usage,
            latency_ms=total_latency,
            retries=max_retries,
            batch_size=len(batches)
        )
    
    def _embed_single_batch(
        self,
        texts: List[str],
        model: str,
        batch_idx: int = 0,
        total_batches: int = 1
    ) -> EmbeddingResult:
        """
        Embed a single batch with retry logic.
        
        Args:
            texts: List of texts (already batched, max batch_size)
            model: Model to use
            batch_idx: Index of this batch
            total_batches: Total number of batches
            
        Returns:
            EmbeddingResult for this batch
        """
        attempt = 0
        last_error = None
        
        while attempt <= self.config.max_retries:
            try:
                start_time = time.time()
                
                # Get client from pool
                client = self._get_client()
                
                try:
                    # Make API call
                    response = client.embeddings.create(
                        input=texts,
                        model=model
                    )
                    
                    # Extract embeddings
                    embeddings = [item.embedding for item in response.data]
                    
                    elapsed_ms = (time.time() - start_time) * 1000
                    
                    # Record success metrics
                    increment_counter("embeddings.success", labels={
                        "batch_size": str(len(texts)),
                        "retries": str(attempt)
                    })
                    observe_histogram("embeddings.latency_ms", elapsed_ms, labels={
                        "batch_size": str(len(texts))
                    })
                    
                    # Return client to pool
                    self._return_client(client)
                    
                    return EmbeddingResult(
                        embeddings=embeddings,
                        usage=response.usage.model_dump() if hasattr(response, 'usage') else {},
                        latency_ms=elapsed_ms,
                        retries=attempt,
                        batch_size=len(texts)
                    )
                    
                except Exception as e:
                    # Return client to pool even on error
                    self._return_client(client)
                    raise
                
            except Exception as e:
                last_error = e
                
                # Check if we should retry
                if not self._should_retry(e) or attempt >= self.config.max_retries:
                    # Record failure
                    increment_counter("embeddings.failure", labels={
                        "error_type": type(e).__name__,
                        "retries": str(attempt)
                    })
                    
                    # Max retries reached or non-retryable error
                    if "429" in str(e).lower() or "rate limit" in str(e).lower():
                        raise EmbeddingRateLimitError(
                            f"Rate limit exceeded after {attempt} retries: {str(e)}"
                        )
                    raise
                
                # Calculate backoff with jitter
                backoff = self._calculate_backoff(attempt)
                
                # Record retry
                increment_counter("embeddings.retry", labels={
                    "attempt": str(attempt),
                    "error_type": type(e).__name__
                })
                
                # Wait before retry
                time.sleep(backoff)
                attempt += 1
        
        # Should not reach here, but just in case
        raise last_error or Exception("Unknown error in embedding retry loop")
    
    def embed_single(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        Embed a single text.
        
        Convenience method that wraps embed_batch.
        
        Args:
            text: Text to embed
            model: Optional model override
            
        Returns:
            Embedding vector
        """
        result = self.embed_batch([text], model)
        return result.embeddings[0] if result.embeddings else []


# Global batcher instance
_batcher_instance = None
_batcher_lock = threading.Lock()


def get_embeddings_batcher(config: Optional[EmbeddingConfig] = None) -> EmbeddingBatcher:
    """
    Get or create global embeddings batcher.
    
    Args:
        config: Optional configuration (only used on first call)
        
    Returns:
        EmbeddingBatcher instance
    """
    global _batcher_instance
    
    if _batcher_instance is None:
        with _batcher_lock:
            if _batcher_instance is None:
                _batcher_instance = EmbeddingBatcher(config)
    
    return _batcher_instance


def embed_texts(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    """
    Embed multiple texts with automatic batching.
    
    Convenience function using global batcher.
    
    Args:
        texts: Texts to embed
        model: Optional model override
        
    Returns:
        List of embedding vectors
    """
    batcher = get_embeddings_batcher()
    result = batcher.embed_batch(texts, model)
    return result.embeddings


def embed_text(text: str, model: Optional[str] = None) -> List[float]:
    """
    Embed a single text.
    
    Convenience function using global batcher.
    
    Args:
        text: Text to embed
        model: Optional model override
        
    Returns:
        Embedding vector
    """
    batcher = get_embeddings_batcher()
    return batcher.embed_single(text, model)
