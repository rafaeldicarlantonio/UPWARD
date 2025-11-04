#!/usr/bin/env python3
"""
core/limits.py — Resource limits and bulkheads for API requests.

Implements per-user concurrency caps, queue size limits, and drop policies
to prevent dogpiling and resource exhaustion. Returns 429 with Retry-After
header when limits are exceeded.

Features:
- Per-user/session concurrency tracking
- Queue management with size caps
- Automatic drop policy on overload
- 429 responses with Retry-After headers
- Queue drain after load subsides
- Thread-safe implementation
"""

import time
import threading
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from contextlib import contextmanager
import asyncio
from enum import Enum


class OverloadPolicy(Enum):
    """Policy for handling overload situations."""
    DROP_NEWEST = "drop_newest"  # Drop new requests (fail fast)
    DROP_OLDEST = "drop_oldest"  # Drop oldest queued requests
    BLOCK = "block"              # Block until capacity available (not recommended)


@dataclass
class LimitConfig:
    """Configuration for resource limits."""
    max_concurrent_per_user: int = 3          # Max concurrent requests per user
    max_queue_size_per_user: int = 10         # Max queued requests per user
    max_concurrent_global: int = 100          # Global concurrency limit
    max_queue_size_global: int = 500          # Global queue size limit
    retry_after_seconds: int = 5              # Retry-After header value (seconds)
    queue_timeout_seconds: float = 30.0       # Max time in queue before timeout
    overload_policy: OverloadPolicy = OverloadPolicy.DROP_NEWEST
    cleanup_interval_seconds: int = 60        # Interval to cleanup stale user data


@dataclass
class UserLimits:
    """Per-user limit tracking."""
    user_id: str
    concurrent: int = 0                       # Current concurrent requests
    queue: deque = field(default_factory=deque)  # Queued request IDs
    last_activity: float = field(default_factory=time.time)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()


@dataclass
class RequestContext:
    """Context for a rate-limited request."""
    request_id: str
    user_id: str
    session_id: Optional[str]
    enqueued_at: float
    started_at: Optional[float] = None
    
    @property
    def queue_time(self) -> float:
        """Time spent in queue (seconds)."""
        if self.started_at:
            return self.started_at - self.enqueued_at
        return time.time() - self.enqueued_at
    
    @property
    def is_timed_out(self) -> bool:
        """Check if request has timed out in queue."""
        return self.queue_time > 30.0  # Default timeout


class OverloadError(Exception):
    """Exception raised when resource limits are exceeded."""
    
    def __init__(self, message: str, retry_after: int):
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


class ResourceLimiter:
    """
    Resource limiter with per-user concurrency and queue management.
    
    Implements bulkhead pattern to prevent resource exhaustion from
    individual users while maintaining overall system capacity.
    """
    
    def __init__(self, config: Optional[LimitConfig] = None):
        """
        Initialize resource limiter.
        
        Args:
            config: Limit configuration (uses defaults if not provided)
        """
        self.config = config or LimitConfig()
        self._lock = threading.RLock()
        self._user_limits: Dict[str, UserLimits] = {}
        self._global_concurrent = 0
        self._global_queue: deque = deque()
        self._request_contexts: Dict[str, RequestContext] = {}
        self._last_cleanup = time.time()
        
    def _get_user_limits(self, user_id: str) -> UserLimits:
        """Get or create user limits tracking."""
        if user_id not in self._user_limits:
            self._user_limits[user_id] = UserLimits(user_id=user_id)
        return self._user_limits[user_id]
    
    def _cleanup_stale_users(self, force: bool = False):
        """Clean up user limit data for inactive users."""
        now = time.time()
        
        if not force and now - self._last_cleanup < self.config.cleanup_interval_seconds:
            return
        
        # Remove users with no concurrent requests and no recent activity
        stale_timeout = 300  # 5 minutes
        stale_users = [
            user_id for user_id, limits in self._user_limits.items()
            if limits.concurrent == 0 and len(limits.queue) == 0
            and now - limits.last_activity > stale_timeout
        ]
        
        for user_id in stale_users:
            del self._user_limits[user_id]
        
        self._last_cleanup = now
    
    def _check_timeout(self, ctx: RequestContext) -> bool:
        """Check if request has timed out in queue."""
        return ctx.queue_time > self.config.queue_timeout_seconds
    
    def _calculate_retry_after(self) -> int:
        """
        Calculate Retry-After value based on current load.
        
        Returns minimum of:
        - Configured retry_after_seconds
        - Estimated time for queue to drain (if queue is active)
        """
        base_retry = self.config.retry_after_seconds
        
        with self._lock:
            # If global queue has items, estimate drain time
            if len(self._global_queue) > 0:
                # Assume average request takes 2 seconds
                avg_request_time = 2.0
                queue_drain_time = (len(self._global_queue) * avg_request_time) / self.config.max_concurrent_global
                estimated_retry = int(queue_drain_time) + 1
                return min(base_retry, max(1, estimated_retry))
        
        return base_retry
    
    def check_limits(self, user_id: str, session_id: Optional[str] = None, request_id: Optional[str] = None) -> RequestContext:
        """
        Check if request can proceed or should be queued/dropped.
        
        Args:
            user_id: User identifier
            session_id: Optional session identifier
            request_id: Optional request identifier (generated if not provided)
            
        Returns:
            RequestContext for the request
            
        Raises:
            OverloadError: If limits exceeded and request should be dropped
        """
        if request_id is None:
            request_id = f"{user_id}_{time.time_ns()}"
        
        ctx = RequestContext(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            enqueued_at=time.time()
        )
        
        with self._lock:
            # Periodic cleanup
            self._cleanup_stale_users()
            
            user_limits = self._get_user_limits(user_id)
            user_limits.update_activity()
            
            # Check global limits first
            if self._global_concurrent >= self.config.max_concurrent_global:
                if len(self._global_queue) >= self.config.max_queue_size_global:
                    # Global queue full - drop request
                    retry_after = self._calculate_retry_after()
                    raise OverloadError(
                        f"Global queue full ({len(self._global_queue)}/{self.config.max_queue_size_global}). "
                        f"System is overloaded.",
                        retry_after=retry_after
                    )
                
                # Add to global queue
                self._global_queue.append(ctx)
                self._request_contexts[request_id] = ctx
                return ctx
            
            # Check per-user limits
            if user_limits.concurrent >= self.config.max_concurrent_per_user:
                if len(user_limits.queue) >= self.config.max_queue_size_per_user:
                    # User queue full - apply overload policy
                    retry_after = self._calculate_retry_after()
                    
                    if self.config.overload_policy == OverloadPolicy.DROP_NEWEST:
                        raise OverloadError(
                            f"User queue full ({len(user_limits.queue)}/{self.config.max_queue_size_per_user}). "
                            f"Too many concurrent requests.",
                            retry_after=retry_after
                        )
                    elif self.config.overload_policy == OverloadPolicy.DROP_OLDEST:
                        # Drop oldest queued request
                        if user_limits.queue:
                            dropped_id = user_limits.queue.popleft()
                            if dropped_id in self._request_contexts:
                                del self._request_contexts[dropped_id]
                
                # Add to user queue
                user_limits.queue.append(request_id)
                self._request_contexts[request_id] = ctx
                return ctx
            
            # Can proceed immediately
            user_limits.concurrent += 1
            self._global_concurrent += 1
            ctx.started_at = time.time()
            self._request_contexts[request_id] = ctx
            return ctx
    
    def acquire(self, user_id: str, session_id: Optional[str] = None, request_id: Optional[str] = None) -> RequestContext:
        """
        Acquire a slot for request execution.
        
        This is a blocking call that waits in queue if necessary.
        
        Args:
            user_id: User identifier
            session_id: Optional session identifier
            request_id: Optional request identifier
            
        Returns:
            RequestContext when request can proceed
            
        Raises:
            OverloadError: If limits exceeded and request dropped
            TimeoutError: If request times out while in queue
        """
        ctx = self.check_limits(user_id, session_id, request_id)
        
        # If already started, return immediately
        if ctx.started_at is not None:
            return ctx
        
        # Wait in queue
        while True:
            # Check for timeout
            if self._check_timeout(ctx):
                with self._lock:
                    # Remove from queue
                    user_limits = self._get_user_limits(user_id)
                    if ctx.request_id in user_limits.queue:
                        user_limits.queue.remove(ctx.request_id)
                    if ctx.request_id in self._global_queue:
                        self._global_queue.remove(ctx)
                    if ctx.request_id in self._request_contexts:
                        del self._request_contexts[ctx.request_id]
                
                raise TimeoutError(
                    f"Request timed out after {ctx.queue_time:.1f}s in queue "
                    f"(limit: {self.config.queue_timeout_seconds}s)"
                )
            
            # Try to start
            with self._lock:
                user_limits = self._get_user_limits(user_id)
                
                # Check if we can start now
                if (user_limits.concurrent < self.config.max_concurrent_per_user and
                    self._global_concurrent < self.config.max_concurrent_global):
                    
                    # Remove from queues
                    if ctx.request_id in user_limits.queue:
                        user_limits.queue.remove(ctx.request_id)
                    if ctx in self._global_queue:
                        self._global_queue.remove(ctx)
                    
                    # Mark as started
                    user_limits.concurrent += 1
                    self._global_concurrent += 1
                    ctx.started_at = time.time()
                    return ctx
            
            # Sleep briefly before retrying
            time.sleep(0.1)
    
    def release(self, ctx: RequestContext):
        """
        Release a request slot.
        
        Args:
            ctx: Request context to release
        """
        with self._lock:
            # Update user limits
            user_limits = self._get_user_limits(ctx.user_id)
            if user_limits.concurrent > 0:
                user_limits.concurrent -= 1
            user_limits.update_activity()
            
            # Update global count
            if self._global_concurrent > 0:
                self._global_concurrent -= 1
            
            # Clean up context
            if ctx.request_id in self._request_contexts:
                del self._request_contexts[ctx.request_id]
    
    @contextmanager
    def limit(self, user_id: str, session_id: Optional[str] = None, request_id: Optional[str] = None):
        """
        Context manager for rate-limited execution.
        
        Usage:
            with limiter.limit(user_id="user123"):
                # Execute rate-limited code
                process_request()
        
        Args:
            user_id: User identifier
            session_id: Optional session identifier
            request_id: Optional request identifier
            
        Raises:
            OverloadError: If limits exceeded
            TimeoutError: If request times out in queue
        """
        ctx = self.acquire(user_id, session_id, request_id)
        try:
            yield ctx
        finally:
            self.release(ctx)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current limiter statistics.
        
        Returns:
            Dict with current state and metrics
        """
        with self._lock:
            user_stats = []
            for user_id, limits in self._user_limits.items():
                user_stats.append({
                    "user_id": user_id,
                    "concurrent": limits.concurrent,
                    "queued": len(limits.queue),
                    "last_activity": limits.last_activity
                })
            
            return {
                "global_concurrent": self._global_concurrent,
                "global_queue_size": len(self._global_queue),
                "total_users": len(self._user_limits),
                "active_requests": len(self._request_contexts),
                "users": user_stats,
                "config": {
                    "max_concurrent_per_user": self.config.max_concurrent_per_user,
                    "max_queue_size_per_user": self.config.max_queue_size_per_user,
                    "max_concurrent_global": self.config.max_concurrent_global,
                    "max_queue_size_global": self.config.max_queue_size_global,
                    "retry_after_seconds": self.config.retry_after_seconds,
                    "queue_timeout_seconds": self.config.queue_timeout_seconds
                }
            }
    
    def reset(self):
        """Reset all limits (for testing)."""
        with self._lock:
            self._user_limits.clear()
            self._global_concurrent = 0
            self._global_queue.clear()
            self._request_contexts.clear()


# Global limiter instance (lazy initialization)
_global_limiter: Optional[ResourceLimiter] = None
_limiter_lock = threading.Lock()


def get_limiter(config: Optional[LimitConfig] = None) -> ResourceLimiter:
    """
    Get global resource limiter instance.
    
    Args:
        config: Optional configuration (only used on first call)
        
    Returns:
        Global ResourceLimiter instance
    """
    global _global_limiter
    
    if _global_limiter is None:
        with _limiter_lock:
            if _global_limiter is None:
                _global_limiter = ResourceLimiter(config)
    
    return _global_limiter


def reset_limiter():
    """Reset global limiter instance (for testing)."""
    global _global_limiter
    
    with _limiter_lock:
        if _global_limiter is not None:
            _global_limiter.reset()
        _global_limiter = None


# FastAPI dependency for rate limiting
def get_rate_limiter():
    """FastAPI dependency to get rate limiter."""
    return get_limiter()


def create_429_response(error: OverloadError) -> Dict[str, Any]:
    """
    Create standardized 429 response.
    
    Args:
        error: OverloadError with details
        
    Returns:
        Dict suitable for JSONResponse with status_code=429
    """
    return {
        "error": "too_many_requests",
        "message": error.message,
        "retry_after": error.retry_after,
        "status": 429
    }
