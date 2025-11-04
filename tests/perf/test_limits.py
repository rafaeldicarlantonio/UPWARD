#!/usr/bin/env python3
"""
Unit tests for resource limits and bulkheads.

Tests:
1. Per-user concurrency caps
2. Queue size limits
3. Overload simulation with 429 responses
4. Queue drain after load subsides
5. Retry-After header calculation
6. Drop policies
7. Thread safety
"""

import sys
import os
import unittest
import time
import threading
from unittest.mock import patch, Mock

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.limits import (
    ResourceLimiter,
    LimitConfig,
    OverloadError,
    OverloadPolicy,
    UserLimits,
    RequestContext,
    get_limiter,
    reset_limiter,
    create_429_response
)


class TestLimitConfig(unittest.TestCase):
    """Test LimitConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LimitConfig()
        
        self.assertEqual(config.max_concurrent_per_user, 3)
        self.assertEqual(config.max_queue_size_per_user, 10)
        self.assertEqual(config.max_concurrent_global, 100)
        self.assertEqual(config.max_queue_size_global, 500)
        self.assertEqual(config.retry_after_seconds, 5)
        self.assertEqual(config.queue_timeout_seconds, 30.0)
        self.assertEqual(config.overload_policy, OverloadPolicy.DROP_NEWEST)
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = LimitConfig(
            max_concurrent_per_user=5,
            max_queue_size_per_user=20,
            retry_after_seconds=10,
            overload_policy=OverloadPolicy.DROP_OLDEST
        )
        
        self.assertEqual(config.max_concurrent_per_user, 5)
        self.assertEqual(config.max_queue_size_per_user, 20)
        self.assertEqual(config.retry_after_seconds, 10)
        self.assertEqual(config.overload_policy, OverloadPolicy.DROP_OLDEST)


class TestUserLimits(unittest.TestCase):
    """Test UserLimits tracking."""
    
    def test_user_limits_creation(self):
        """Test creating user limits."""
        limits = UserLimits(user_id="user123")
        
        self.assertEqual(limits.user_id, "user123")
        self.assertEqual(limits.concurrent, 0)
        self.assertEqual(len(limits.queue), 0)
        self.assertIsNotNone(limits.last_activity)
    
    def test_update_activity(self):
        """Test activity timestamp update."""
        limits = UserLimits(user_id="user123")
        initial_time = limits.last_activity
        
        time.sleep(0.01)
        limits.update_activity()
        
        self.assertGreater(limits.last_activity, initial_time)


class TestRequestContext(unittest.TestCase):
    """Test RequestContext."""
    
    def test_context_creation(self):
        """Test creating request context."""
        ctx = RequestContext(
            request_id="req123",
            user_id="user123",
            session_id="session123",
            enqueued_at=time.time()
        )
        
        self.assertEqual(ctx.request_id, "req123")
        self.assertEqual(ctx.user_id, "user123")
        self.assertEqual(ctx.session_id, "session123")
        self.assertIsNone(ctx.started_at)
    
    def test_queue_time(self):
        """Test queue time calculation."""
        enqueued_at = time.time()
        ctx = RequestContext(
            request_id="req123",
            user_id="user123",
            session_id=None,
            enqueued_at=enqueued_at
        )
        
        time.sleep(0.1)
        queue_time = ctx.queue_time
        
        self.assertGreater(queue_time, 0.09)
        self.assertLess(queue_time, 0.2)


class TestResourceLimiter(unittest.TestCase):
    """Test ResourceLimiter class."""
    
    def setUp(self):
        """Create limiter with test config before each test."""
        self.config = LimitConfig(
            max_concurrent_per_user=2,
            max_queue_size_per_user=3,
            max_concurrent_global=10,
            max_queue_size_global=20,
            retry_after_seconds=5,
            queue_timeout_seconds=2.0  # Short timeout for tests
        )
        self.limiter = ResourceLimiter(self.config)
    
    def tearDown(self):
        """Clean up after each test."""
        self.limiter.reset()
    
    def test_limiter_creation(self):
        """Test creating limiter."""
        self.assertIsNotNone(self.limiter)
        self.assertEqual(self.limiter.config.max_concurrent_per_user, 2)
    
    def test_check_limits_immediate_proceed(self):
        """Test request proceeds immediately when under limits."""
        ctx = self.limiter.check_limits("user1", request_id="req1")
        
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.user_id, "user1")
        self.assertEqual(ctx.request_id, "req1")
        self.assertIsNotNone(ctx.started_at)  # Started immediately
        
        # Clean up
        self.limiter.release(ctx)
    
    def test_per_user_concurrency_cap(self):
        """Test per-user concurrency limit is enforced."""
        # Start max concurrent requests for user1
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        ctx2 = self.limiter.check_limits("user1", request_id="req2")
        
        self.assertIsNotNone(ctx1.started_at)
        self.assertIsNotNone(ctx2.started_at)
        
        # Third request should be queued
        ctx3 = self.limiter.check_limits("user1", request_id="req3")
        self.assertIsNone(ctx3.started_at)  # Not started yet
        
        # Clean up
        self.limiter.release(ctx1)
        self.limiter.release(ctx2)


class TestOverloadSimulation(unittest.TestCase):
    """Test overload scenarios that trigger 429 responses."""
    
    def setUp(self):
        """Create limiter with restrictive config for overload testing."""
        self.config = LimitConfig(
            max_concurrent_per_user=1,
            max_queue_size_per_user=2,
            max_concurrent_global=5,
            max_queue_size_global=10,
            retry_after_seconds=5
        )
        self.limiter = ResourceLimiter(self.config)
    
    def tearDown(self):
        """Clean up after each test."""
        self.limiter.reset()
    
    def test_user_queue_full_triggers_overload(self):
        """Test: User queue full triggers OverloadError with 429."""
        # Fill user's concurrency
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        self.assertIsNotNone(ctx1.started_at)
        
        # Fill user's queue
        ctx2 = self.limiter.check_limits("user1", request_id="req2")
        ctx3 = self.limiter.check_limits("user1", request_id="req3")
        self.assertIsNone(ctx2.started_at)
        self.assertIsNone(ctx3.started_at)
        
        # Next request should trigger OverloadError
        with self.assertRaises(OverloadError) as cm:
            self.limiter.check_limits("user1", request_id="req4")
        
        error = cm.exception
        self.assertIn("queue full", error.message.lower())
        self.assertEqual(error.retry_after, 5)
        
        # Clean up
        self.limiter.release(ctx1)
    
    def test_global_queue_full_triggers_overload(self):
        """Test: Global queue full triggers OverloadError."""
        contexts = []
        
        # Fill global concurrency
        for i in range(self.config.max_concurrent_global):
            ctx = self.limiter.check_limits(f"user{i}", request_id=f"req{i}")
            contexts.append(ctx)
            self.assertIsNotNone(ctx.started_at)
        
        # Fill global queue
        for i in range(self.config.max_queue_size_global):
            ctx = self.limiter.check_limits(
                f"user{self.config.max_concurrent_global + i}",
                request_id=f"req{self.config.max_concurrent_global + i}"
            )
            contexts.append(ctx)
            self.assertIsNone(ctx.started_at)
        
        # Next request should trigger OverloadError
        with self.assertRaises(OverloadError) as cm:
            self.limiter.check_limits("user999", request_id="req999")
        
        error = cm.exception
        self.assertIn("global queue full", error.message.lower())
        self.assertGreater(error.retry_after, 0)
        
        # Clean up
        for ctx in contexts:
            if ctx.started_at:
                self.limiter.release(ctx)
    
    def test_create_429_response(self):
        """Test creating 429 response from OverloadError."""
        error = OverloadError("Queue full", retry_after=10)
        response = create_429_response(error)
        
        self.assertEqual(response["status"], 429)
        self.assertEqual(response["error"], "too_many_requests")
        self.assertEqual(response["retry_after"], 10)
        self.assertIn("Queue full", response["message"])


class TestQueueDrain(unittest.TestCase):
    """Test queue drains correctly after load subsides."""
    
    def setUp(self):
        """Create limiter for queue drain testing."""
        self.config = LimitConfig(
            max_concurrent_per_user=2,
            max_queue_size_per_user=5,
            max_concurrent_global=10,
            queue_timeout_seconds=10.0  # Longer timeout for drain tests
        )
        self.limiter = ResourceLimiter(self.config)
    
    def tearDown(self):
        """Clean up after each test."""
        self.limiter.reset()
    
    def test_queue_drains_after_release(self):
        """Test: Queue drains as requests complete."""
        # Start max concurrent for user
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        ctx2 = self.limiter.check_limits("user1", request_id="req2")
        
        # Queue additional requests
        ctx3 = self.limiter.check_limits("user1", request_id="req3")
        ctx4 = self.limiter.check_limits("user1", request_id="req4")
        
        self.assertIsNotNone(ctx1.started_at)
        self.assertIsNotNone(ctx2.started_at)
        self.assertIsNone(ctx3.started_at)  # Queued
        self.assertIsNone(ctx4.started_at)  # Queued
        
        stats_before = self.limiter.get_stats()
        user_stats = next(u for u in stats_before["users"] if u["user_id"] == "user1")
        self.assertEqual(user_stats["concurrent"], 2)
        self.assertEqual(user_stats["queued"], 2)
        
        # Release one request
        self.limiter.release(ctx1)
        
        # Now queue should have decreased (one item waiting to be processed)
        stats_after = self.limiter.get_stats()
        user_stats_after = next(u for u in stats_after["users"] if u["user_id"] == "user1")
        self.assertEqual(user_stats_after["concurrent"], 1)  # One released
        
        # Clean up
        self.limiter.release(ctx2)
    
    def test_queue_empties_with_context_manager(self):
        """Test: Queue empties correctly using context manager."""
        results = []
        
        def process_request(user_id: str, request_id: str):
            """Simulate processing a request."""
            try:
                with self.limiter.limit(user_id, request_id=request_id):
                    time.sleep(0.05)  # Simulate work
                    results.append(request_id)
            except (OverloadError, TimeoutError) as e:
                results.append(f"error:{request_id}")
        
        # Start threads to simulate concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=process_request,
                args=("user1", f"req{i}")
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5.0)
        
        # All requests should complete successfully
        self.assertEqual(len(results), 5)
        successful = [r for r in results if not r.startswith("error:")]
        self.assertEqual(len(successful), 5)
        
        # Queue should be empty
        stats = self.limiter.get_stats()
        if stats["users"]:  # User might be cleaned up
            user_stats = next((u for u in stats["users"] if u["user_id"] == "user1"), None)
            if user_stats:
                self.assertEqual(user_stats["concurrent"], 0)
                self.assertEqual(user_stats["queued"], 0)


class TestRetryAfterCalculation(unittest.TestCase):
    """Test Retry-After header calculation."""
    
    def setUp(self):
        """Create limiter for retry-after testing."""
        self.config = LimitConfig(
            max_concurrent_per_user=1,
            max_queue_size_per_user=2,
            retry_after_seconds=10
        )
        self.limiter = ResourceLimiter(self.config)
    
    def tearDown(self):
        """Clean up after each test."""
        self.limiter.reset()
    
    def test_retry_after_value(self):
        """Test: Retry-After value is reasonable."""
        # Fill user queue
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        ctx2 = self.limiter.check_limits("user1", request_id="req2")
        ctx3 = self.limiter.check_limits("user1", request_id="req3")
        
        # Trigger overload
        try:
            self.limiter.check_limits("user1", request_id="req4")
            self.fail("Should have raised OverloadError")
        except OverloadError as e:
            self.assertGreater(e.retry_after, 0)
            self.assertLessEqual(e.retry_after, 30)  # Reasonable upper bound
        
        # Clean up
        self.limiter.release(ctx1)


class TestDropPolicies(unittest.TestCase):
    """Test different drop policies."""
    
    def test_drop_newest_policy(self):
        """Test DROP_NEWEST policy drops new requests."""
        config = LimitConfig(
            max_concurrent_per_user=1,
            max_queue_size_per_user=2,
            overload_policy=OverloadPolicy.DROP_NEWEST
        )
        limiter = ResourceLimiter(config)
        
        try:
            # Fill concurrency and queue
            ctx1 = limiter.check_limits("user1", request_id="req1")
            ctx2 = limiter.check_limits("user1", request_id="req2")
            ctx3 = limiter.check_limits("user1", request_id="req3")
            
            # Next request should be dropped
            with self.assertRaises(OverloadError):
                limiter.check_limits("user1", request_id="req4")
            
            # Clean up
            limiter.release(ctx1)
        finally:
            limiter.reset()
    
    def test_drop_oldest_policy(self):
        """Test DROP_OLDEST policy drops oldest queued request."""
        config = LimitConfig(
            max_concurrent_per_user=1,
            max_queue_size_per_user=2,
            overload_policy=OverloadPolicy.DROP_OLDEST
        )
        limiter = ResourceLimiter(config)
        
        try:
            # Fill concurrency and queue
            ctx1 = limiter.check_limits("user1", request_id="req1")
            ctx2 = limiter.check_limits("user1", request_id="req2")
            ctx3 = limiter.check_limits("user1", request_id="req3")
            
            # Next request should succeed by dropping oldest
            ctx4 = limiter.check_limits("user1", request_id="req4")
            self.assertIsNotNone(ctx4)
            
            # req2 should have been dropped (oldest in queue)
            stats = limiter.get_stats()
            user_stats = next(u for u in stats["users"] if u["user_id"] == "user1")
            self.assertEqual(user_stats["queued"], 2)  # req3 and req4
            
            # Clean up
            limiter.release(ctx1)
        finally:
            limiter.reset()


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of limiter."""
    
    def setUp(self):
        """Create limiter for thread safety testing."""
        self.config = LimitConfig(
            max_concurrent_per_user=5,
            max_queue_size_per_user=20,
            max_concurrent_global=50
        )
        self.limiter = ResourceLimiter(self.config)
    
    def tearDown(self):
        """Clean up after each test."""
        self.limiter.reset()
    
    def test_concurrent_access(self):
        """Test: Limiter handles concurrent access correctly."""
        results = {"success": 0, "queued": 0, "failed": 0}
        lock = threading.Lock()
        
        def make_request(user_id: str, request_id: str):
            """Simulate a request."""
            try:
                with self.limiter.limit(user_id, request_id=request_id):
                    time.sleep(0.01)  # Simulate work
                    with lock:
                        results["success"] += 1
            except OverloadError:
                with lock:
                    results["failed"] += 1
            except TimeoutError:
                with lock:
                    results["failed"] += 1
        
        # Start many concurrent threads
        threads = []
        for i in range(100):
            thread = threading.Thread(
                target=make_request,
                args=(f"user{i % 10}", f"req{i}")
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=10.0)
        
        # All requests should either succeed or fail gracefully
        total = results["success"] + results["failed"]
        self.assertEqual(total, 100)
        self.assertGreater(results["success"], 0)  # Some should succeed


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def setUp(self):
        """Create limiter for acceptance testing."""
        self.config = LimitConfig(
            max_concurrent_per_user=2,
            max_queue_size_per_user=3,
            max_concurrent_global=10,
            max_queue_size_global=20,
            retry_after_seconds=5
        )
        self.limiter = ResourceLimiter(self.config)
    
    def tearDown(self):
        """Clean up after each test."""
        self.limiter.reset()
    
    def test_acceptance_cap_concurrency_per_user(self):
        """ACCEPTANCE: Cap concurrency per user to avoid dogpiling."""
        # User can have max 2 concurrent requests
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        ctx2 = self.limiter.check_limits("user1", request_id="req2")
        
        self.assertIsNotNone(ctx1.started_at)
        self.assertIsNotNone(ctx2.started_at)
        
        # Third request is queued (not started)
        ctx3 = self.limiter.check_limits("user1", request_id="req3")
        self.assertIsNone(ctx3.started_at)
        
        # ✅ Per-user concurrency cap enforced
        stats = self.limiter.get_stats()
        user_stats = next(u for u in stats["users"] if u["user_id"] == "user1")
        self.assertEqual(user_stats["concurrent"], 2)
        self.assertEqual(user_stats["queued"], 1)
        
        # Clean up
        self.limiter.release(ctx1)
        self.limiter.release(ctx2)
    
    def test_acceptance_queue_size_caps(self):
        """ACCEPTANCE: Queue size caps prevent unbounded queueing."""
        # Fill user's concurrency
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        ctx2 = self.limiter.check_limits("user1", request_id="req2")
        
        # Fill user's queue (max 3)
        ctx3 = self.limiter.check_limits("user1", request_id="req3")
        ctx4 = self.limiter.check_limits("user1", request_id="req4")
        ctx5 = self.limiter.check_limits("user1", request_id="req5")
        
        # ✅ Queue is full
        stats = self.limiter.get_stats()
        user_stats = next(u for u in stats["users"] if u["user_id"] == "user1")
        self.assertEqual(user_stats["queued"], 3)
        
        # Next request triggers overload
        with self.assertRaises(OverloadError):
            self.limiter.check_limits("user1", request_id="req6")
        
        # ✅ Queue size cap enforced
        
        # Clean up
        self.limiter.release(ctx1)
        self.limiter.release(ctx2)
    
    def test_acceptance_overload_returns_429_with_retry_after(self):
        """ACCEPTANCE: Overload returns 429 with Retry-After header."""
        # Fill user's capacity
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        ctx2 = self.limiter.check_limits("user1", request_id="req2")
        ctx3 = self.limiter.check_limits("user1", request_id="req3")
        ctx4 = self.limiter.check_limits("user1", request_id="req4")
        ctx5 = self.limiter.check_limits("user1", request_id="req5")
        
        # Trigger overload
        try:
            self.limiter.check_limits("user1", request_id="req6")
            self.fail("Should have raised OverloadError")
        except OverloadError as error:
            # ✅ OverloadError raised
            self.assertIn("queue full", error.message.lower())
            self.assertIsNotNone(error.retry_after)
            self.assertGreater(error.retry_after, 0)
            
            # ✅ Can create 429 response with Retry-After
            response = create_429_response(error)
            self.assertEqual(response["status"], 429)
            self.assertEqual(response["retry_after"], error.retry_after)
            self.assertIn("retry_after", response)
        
        # Clean up
        self.limiter.release(ctx1)
        self.limiter.release(ctx2)
    
    def test_acceptance_load_test_triggers_429(self):
        """ACCEPTANCE: Load test simulation triggers 429 under overload."""
        contexts = []
        errors = []
        
        # Simulate load spike - many requests from one user
        for i in range(10):
            try:
                ctx = self.limiter.check_limits("heavy_user", request_id=f"req{i}")
                contexts.append(ctx)
            except OverloadError as e:
                errors.append(e)
        
        # ✅ Some requests succeeded
        self.assertGreater(len(contexts), 0)
        
        # ✅ Some requests failed with OverloadError (would be 429)
        self.assertGreater(len(errors), 0)
        
        # ✅ All errors have retry_after
        for error in errors:
            self.assertGreater(error.retry_after, 0)
        
        # Clean up
        for ctx in contexts:
            if ctx.started_at:
                self.limiter.release(ctx)
    
    def test_acceptance_queue_drains_after_load_subsides(self):
        """ACCEPTANCE: Queue drains after load subsides."""
        results = []
        
        def process_with_delay(user_id: str, request_id: str, delay: float):
            """Process request with simulated work."""
            try:
                with self.limiter.limit(user_id, request_id=request_id):
                    time.sleep(delay)
                    results.append(f"success:{request_id}")
            except (OverloadError, TimeoutError) as e:
                results.append(f"error:{request_id}")
        
        # Start initial requests that take time
        threads = []
        for i in range(5):
            delay = 0.2 if i < 2 else 0.05  # First two take longer
            thread = threading.Thread(
                target=process_with_delay,
                args=("user1", f"req{i}", delay)
            )
            threads.append(thread)
            thread.start()
        
        # Give time for queue to build up
        time.sleep(0.1)
        
        # Check queue has items
        stats_mid = self.limiter.get_stats()
        if stats_mid["users"]:
            user_stats_mid = next((u for u in stats_mid["users"] if u["user_id"] == "user1"), None)
            if user_stats_mid:
                # Some items should be queued or concurrent
                self.assertGreater(user_stats_mid["concurrent"] + user_stats_mid["queued"], 0)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # ✅ All requests completed
        self.assertEqual(len(results), 5)
        successful = [r for r in results if r.startswith("success:")]
        self.assertEqual(len(successful), 5)
        
        # ✅ Queue drained (user cleaned up or has no load)
        stats_after = self.limiter.get_stats()
        user_stats_after = next((u for u in stats_after["users"] if u["user_id"] == "user1"), None)
        if user_stats_after:
            self.assertEqual(user_stats_after["concurrent"], 0)
            self.assertEqual(user_stats_after["queued"], 0)


class TestGlobalLimiter(unittest.TestCase):
    """Test global limiter singleton."""
    
    def setUp(self):
        """Reset global limiter before each test."""
        reset_limiter()
    
    def tearDown(self):
        """Reset global limiter after each test."""
        reset_limiter()
    
    def test_get_limiter_singleton(self):
        """Test get_limiter returns singleton instance."""
        limiter1 = get_limiter()
        limiter2 = get_limiter()
        
        self.assertIs(limiter1, limiter2)
    
    def test_reset_limiter(self):
        """Test reset_limiter clears singleton."""
        limiter1 = get_limiter()
        self.assertIsNotNone(limiter1)
        
        reset_limiter()
        
        limiter2 = get_limiter()
        # After reset, should get new instance
        self.assertIsNot(limiter1, limiter2)


class TestLimiterStats(unittest.TestCase):
    """Test limiter statistics reporting."""
    
    def setUp(self):
        """Create limiter for stats testing."""
        self.config = LimitConfig(
            max_concurrent_per_user=3,
            max_queue_size_per_user=5
        )
        self.limiter = ResourceLimiter(self.config)
    
    def tearDown(self):
        """Clean up after each test."""
        self.limiter.reset()
    
    def test_get_stats_structure(self):
        """Test get_stats returns correct structure."""
        stats = self.limiter.get_stats()
        
        self.assertIn("global_concurrent", stats)
        self.assertIn("global_queue_size", stats)
        self.assertIn("total_users", stats)
        self.assertIn("active_requests", stats)
        self.assertIn("users", stats)
        self.assertIn("config", stats)
    
    def test_stats_with_active_requests(self):
        """Test stats reflect active requests."""
        # Start some requests
        ctx1 = self.limiter.check_limits("user1", request_id="req1")
        ctx2 = self.limiter.check_limits("user2", request_id="req2")
        
        stats = self.limiter.get_stats()
        
        self.assertEqual(stats["global_concurrent"], 2)
        self.assertEqual(stats["total_users"], 2)
        self.assertEqual(stats["active_requests"], 2)
        
        # Find user1 stats
        user1_stats = next(u for u in stats["users"] if u["user_id"] == "user1")
        self.assertEqual(user1_stats["concurrent"], 1)
        self.assertEqual(user1_stats["queued"], 0)
        
        # Clean up
        self.limiter.release(ctx1)
        self.limiter.release(ctx2)


if __name__ == "__main__":
    unittest.main()
