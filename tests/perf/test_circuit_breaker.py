#!/usr/bin/env python3
"""
Unit tests for circuit breaker implementation.

Tests:
1. Circuit breaker states and transitions
2. Failure threshold and opening
3. Cooldown and half-open state
4. Success threshold and closing
5. Integration with health checks
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.circuit import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    get_circuit_breaker,
    reset_all_circuit_breakers
)
from core.health import (
    check_pinecone_health,
    check_reviewer_health,
    HealthCheckResult,
    is_service_healthy
)


class TestCircuitBreakerStates(unittest.TestCase):
    """Test circuit breaker state transitions."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        config = CircuitBreakerConfig(name="test", failure_threshold=3)
        breaker = CircuitBreaker(config)
        
        self.assertEqual(breaker.get_state(), CircuitState.CLOSED)
        self.assertTrue(breaker.can_execute())
    
    def test_opens_after_threshold_failures(self):
        """Test circuit opens after failure threshold."""
        config = CircuitBreakerConfig(name="test", failure_threshold=3)
        breaker = CircuitBreaker(config)
        
        def failing_func():
            raise Exception("Service unavailable")
        
        # Fail 3 times
        for i in range(3):
            with self.assertRaises(Exception):
                breaker.call(failing_func)
        
        # Should now be OPEN
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)
        self.assertFalse(breaker.can_execute())
    
    def test_rejects_calls_when_open(self):
        """Test circuit breaker rejects calls when open."""
        config = CircuitBreakerConfig(name="test", failure_threshold=2)
        breaker = CircuitBreaker(config)
        
        def failing_func():
            raise Exception("Fail")
        
        # Open the circuit
        for i in range(2):
            with self.assertRaises(Exception):
                breaker.call(failing_func)
        
        # Next call should be rejected
        with self.assertRaises(CircuitBreakerOpenError):
            breaker.call(lambda: "success")
    
    def test_transitions_to_half_open_after_cooldown(self):
        """Test circuit moves to HALF_OPEN after cooldown."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=2,
            cooldown_seconds=0.1  # Short cooldown for testing
        )
        breaker = CircuitBreaker(config)
        
        def failing_func():
            raise Exception("Fail")
        
        # Open the circuit
        for i in range(2):
            with self.assertRaises(Exception):
                breaker.call(failing_func)
        
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)
        
        # Wait for cooldown
        time.sleep(0.15)
        
        # Should allow execution (transitions to HALF_OPEN)
        self.assertTrue(breaker.can_execute())
    
    def test_half_open_closes_on_success(self):
        """Test HALF_OPEN closes after success threshold."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=2,
            cooldown_seconds=0.1,
            success_threshold=2
        )
        breaker = CircuitBreaker(config)
        
        # Open the circuit
        for i in range(2):
            with self.assertRaises(Exception):
                breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)
        
        # Wait for cooldown
        time.sleep(0.15)
        
        # Succeed twice
        breaker.call(lambda: "success")
        self.assertEqual(breaker.get_state(), CircuitState.HALF_OPEN)
        
        breaker.call(lambda: "success")
        
        # Should now be CLOSED
        self.assertEqual(breaker.get_state(), CircuitState.CLOSED)
    
    def test_half_open_reopens_on_failure(self):
        """Test HALF_OPEN returns to OPEN on any failure."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=2,
            cooldown_seconds=0.1
        )
        breaker = CircuitBreaker(config)
        
        # Open the circuit
        for i in range(2):
            with self.assertRaises(Exception):
                breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        
        time.sleep(0.15)
        
        # Succeed once (enters HALF_OPEN)
        breaker.call(lambda: "success")
        self.assertEqual(breaker.get_state(), CircuitState.HALF_OPEN)
        
        # Fail once
        with self.assertRaises(Exception):
            breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail again")))
        
        # Should return to OPEN
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)


class TestCircuitBreakerMetrics(unittest.TestCase):
    """Test circuit breaker metrics and statistics."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_tracks_consecutive_failures(self):
        """Test circuit tracks consecutive failures."""
        config = CircuitBreakerConfig(name="test", failure_threshold=5)
        breaker = CircuitBreaker(config)
        
        for i in range(3):
            with self.assertRaises(Exception):
                breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        
        stats = breaker.get_stats()
        self.assertEqual(stats['consecutive_failures'], 3)
        self.assertEqual(stats['total_failures'], 3)
    
    def test_resets_consecutive_on_success(self):
        """Test consecutive failures reset on success."""
        config = CircuitBreakerConfig(name="test", failure_threshold=5)
        breaker = CircuitBreaker(config)
        
        # Fail twice
        for i in range(2):
            with self.assertRaises(Exception):
                breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        
        self.assertEqual(breaker.stats.consecutive_failures, 2)
        
        # Succeed once
        breaker.call(lambda: "success")
        
        # Consecutive failures should reset
        self.assertEqual(breaker.stats.consecutive_failures, 0)
        self.assertEqual(breaker.stats.consecutive_successes, 1)
    
    def test_get_stats_returns_complete_info(self):
        """Test get_stats returns all relevant information."""
        config = CircuitBreakerConfig(
            name="test_service",
            failure_threshold=3,
            cooldown_seconds=30.0
        )
        breaker = CircuitBreaker(config)
        
        stats = breaker.get_stats()
        
        # Check all expected keys
        self.assertIn('name', stats)
        self.assertIn('state', stats)
        self.assertIn('consecutive_failures', stats)
        self.assertIn('consecutive_successes', stats)
        self.assertIn('total_failures', stats)
        self.assertIn('total_successes', stats)
        self.assertIn('failure_threshold', stats)
        self.assertIn('cooldown_seconds', stats)
        
        self.assertEqual(stats['name'], 'test_service')
        self.assertEqual(stats['failure_threshold'], 3)
        self.assertEqual(stats['cooldown_seconds'], 30.0)


class TestCircuitBreakerRegistry(unittest.TestCase):
    """Test global circuit breaker registry."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_get_circuit_breaker_creates_if_not_exists(self):
        """Test get_circuit_breaker creates new breaker."""
        config = CircuitBreakerConfig(name="service1")
        breaker1 = get_circuit_breaker("service1", config)
        
        self.assertIsNotNone(breaker1)
        self.assertEqual(breaker1.config.name, "service1")
    
    def test_get_circuit_breaker_returns_same_instance(self):
        """Test get_circuit_breaker returns singleton."""
        config = CircuitBreakerConfig(name="service2")
        breaker1 = get_circuit_breaker("service2", config)
        breaker2 = get_circuit_breaker("service2")
        
        self.assertIs(breaker1, breaker2)
    
    def test_reset_all_clears_registry(self):
        """Test reset_all clears all breakers."""
        get_circuit_breaker("s1", CircuitBreakerConfig(name="s1"))
        get_circuit_breaker("s2", CircuitBreakerConfig(name="s2"))
        
        reset_all_circuit_breakers()
        
        # Should be empty after reset
        from core.circuit import get_all_circuit_breakers
        breakers = get_all_circuit_breakers()
        self.assertEqual(len(breakers), 0)


class TestHealthChecks(unittest.TestCase):
    """Test health check functions."""
    
    def test_health_check_result_structure(self):
        """Test HealthCheckResult has correct structure."""
        result = HealthCheckResult(
            service="test_service",
            is_healthy=True,
            latency_ms=100.0,
            error=None,
            details={"status": "ok"}
        )
        
        self.assertEqual(result.service, "test_service")
        self.assertTrue(result.is_healthy)
        self.assertEqual(result.latency_ms, 100.0)
        self.assertIsNone(result.error)
        self.assertEqual(result.details["status"], "ok")
        self.assertIsNotNone(result.timestamp)
    
    def test_health_check_result_with_error(self):
        """Test HealthCheckResult captures errors."""
        result = HealthCheckResult(
            service="failing_service",
            is_healthy=False,
            latency_ms=50.0,
            error="Connection refused"
        )
        
        self.assertFalse(result.is_healthy)
        self.assertEqual(result.error, "Connection refused")
    
    def test_health_check_result_repr(self):
        """Test HealthCheckResult string representation."""
        result = HealthCheckResult(
            service="test",
            is_healthy=True,
            latency_ms=123.4
        )
        
        repr_str = repr(result)
        self.assertIn("test", repr_str)
        self.assertIn("healthy", repr_str)
        self.assertIn("123.4", repr_str)


class TestIntegration(unittest.TestCase):
    """Test integration between circuit breaker and health checks."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_circuit_breaker_with_health_check(self):
        """Test using health check as circuit breaker probe."""
        config = CircuitBreakerConfig(
            name="pinecone_test",
            failure_threshold=2,
            cooldown_seconds=0.1
        )
        breaker = CircuitBreaker(config)
        
        # Simulate failing health checks
        def failing_health_check():
            result = HealthCheckResult(
                service="pinecone",
                is_healthy=False,
                latency_ms=100,
                error="Connection timeout"
            )
            if not result.is_healthy:
                raise Exception(result.error)
            return result
        
        # Fail twice to open circuit
        for i in range(2):
            with self.assertRaises(Exception):
                breaker.call(failing_health_check)
        
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)
        
        # Wait for cooldown
        time.sleep(0.15)
        
        # Successful health check
        def successful_health_check():
            return HealthCheckResult(
                service="pinecone",
                is_healthy=True,
                latency_ms=50
            )
        
        result = breaker.call(successful_health_check)
        self.assertTrue(result.is_healthy)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_breaker_opens_after_failures(self):
        """Test: breaker opens after N consecutive failures."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=5
        )
        breaker = CircuitBreaker(config)
        
        # Fail 5 times
        for i in range(5):
            with self.assertRaises(Exception):
                breaker.call(lambda: (_ for _ in ()).throw(Exception("Service down")))
        
        # ? Breaker should be OPEN
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)
        
        # ? Prevents spamming - next call rejected
        with self.assertRaises(CircuitBreakerOpenError) as cm:
            breaker.call(lambda: "attempt")
        
        self.assertIn("Circuit breaker", str(cm.exception))
        self.assertIn("OPEN", str(cm.exception))
    
    def test_half_open_allows_probe_then_closes(self):
        """Test: half-open allows probe call, closes on success."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=3,
            cooldown_seconds=0.1,
            success_threshold=2
        )
        breaker = CircuitBreaker(config)
        
        # Open the circuit
        for i in range(3):
            with self.assertRaises(Exception):
                breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)
        
        # Wait for cooldown
        time.sleep(0.15)
        
        # ? Half-open allows probe call
        self.assertTrue(breaker.can_execute())
        
        # First success (enters HALF_OPEN)
        result1 = breaker.call(lambda: "probe_success")
        self.assertEqual(result1, "probe_success")
        self.assertEqual(breaker.get_state(), CircuitState.HALF_OPEN)
        
        # Second success
        result2 = breaker.call(lambda: "probe_success_2")
        self.assertEqual(result2, "probe_success_2")
        
        # ? Closes on success
        self.assertEqual(breaker.get_state(), CircuitState.CLOSED)
    
    def test_prevents_spamming_failed_service(self):
        """Test: circuit breaker prevents spamming failed service."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=3
        )
        breaker = CircuitBreaker(config)
        
        call_count = 0
        
        def tracked_failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Service unavailable")
        
        # Fail 3 times to open
        for i in range(3):
            with self.assertRaises(Exception):
                breaker.call(tracked_failing_func)
        
        self.assertEqual(call_count, 3)
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)
        
        # ? Next 10 attempts should NOT call the function
        for i in range(10):
            with self.assertRaises(CircuitBreakerOpenError):
                breaker.call(tracked_failing_func)
        
        # Function was not called (prevented spamming)
        self.assertEqual(call_count, 3, "Should not have called function after opening")


if __name__ == "__main__":
    unittest.main()
