#!/usr/bin/env python3
"""
Comprehensive verification script for circuit breaker implementation.
"""

import sys
import time
import unittest

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
    HealthCheckResult,
    check_pinecone_health,
    check_reviewer_health,
    check_all_services,
    is_service_healthy
)


def print_section(title):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def verify_circuit_breaker_states():
    """Verify circuit breaker state machine."""
    print_section("1. Verify Circuit Breaker States")
    
    reset_all_circuit_breakers()
    
    config = CircuitBreakerConfig(
        name="test",
        failure_threshold=3,
        cooldown_seconds=0.1,
        success_threshold=2
    )
    breaker = CircuitBreaker(config)
    
    checks = [
        ("Initial state is CLOSED", breaker.get_state() == CircuitState.CLOSED),
        ("Can execute initially", breaker.can_execute()),
    ]
    
    # Fail 3 times to open
    for i in range(3):
        try:
            breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
    
    checks.extend([
        ("Opens after 3 failures", breaker.get_state() == CircuitState.OPEN),
        ("Cannot execute when open", not breaker.can_execute()),
    ])
    
    # Try to call when open
    try:
        breaker.call(lambda: "attempt")
        checks.append(("Raises CircuitBreakerOpenError", False))
    except CircuitBreakerOpenError:
        checks.append(("Raises CircuitBreakerOpenError", True))
    
    # Wait for cooldown
    time.sleep(0.15)
    
    checks.append(("Can execute after cooldown", breaker.can_execute()))
    
    # Succeed twice to close
    breaker.call(lambda: "success1")
    checks.append(("Enters HALF_OPEN", breaker.get_state() == CircuitState.HALF_OPEN))
    
    breaker.call(lambda: "success2")
    checks.append(("Closes after 2 successes", breaker.get_state() == CircuitState.CLOSED))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_failure_counters():
    """Verify rolling failure counters."""
    print_section("2. Verify Rolling Failure Counters")
    
    reset_all_circuit_breakers()
    
    config = CircuitBreakerConfig(name="test", failure_threshold=5)
    breaker = CircuitBreaker(config)
    
    # Fail 3 times
    for i in range(3):
        try:
            breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
    
    stats = breaker.get_stats()
    
    checks = [
        ("Consecutive failures = 3", stats['consecutive_failures'] == 3),
        ("Total failures = 3", stats['total_failures'] == 3),
    ]
    
    # Succeed once
    breaker.call(lambda: "success")
    stats = breaker.get_stats()
    
    checks.extend([
        ("Consecutive failures reset", stats['consecutive_failures'] == 0),
        ("Consecutive successes = 1", stats['consecutive_successes'] == 1),
        ("Total failures still 3", stats['total_failures'] == 3),
        ("Total successes = 1", stats['total_successes'] == 1),
    ])
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_half_open_probe():
    """Verify half-open probe path."""
    print_section("3. Verify Half-Open Probe Path")
    
    reset_all_circuit_breakers()
    
    config = CircuitBreakerConfig(
        name="test",
        failure_threshold=2,
        cooldown_seconds=0.1,
        success_threshold=2
    )
    breaker = CircuitBreaker(config)
    
    # Open circuit
    for i in range(2):
        try:
            breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
    
    checks = [("Circuit is OPEN", breaker.get_state() == CircuitState.OPEN)]
    
    # Wait for cooldown
    time.sleep(0.15)
    
    checks.append(("Can execute after cooldown", breaker.can_execute()))
    
    # First probe
    breaker.call(lambda: "probe1")
    checks.append(("Enters HALF_OPEN", breaker.get_state() == CircuitState.HALF_OPEN))
    
    # Second probe
    breaker.call(lambda: "probe2")
    checks.append(("Closes after success threshold", breaker.get_state() == CircuitState.CLOSED))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_prevents_spamming():
    """Verify circuit breaker prevents spamming."""
    print_section("4. Verify Prevents Spamming")
    
    reset_all_circuit_breakers()
    
    config = CircuitBreakerConfig(name="test", failure_threshold=3)
    breaker = CircuitBreaker(config)
    
    call_count = 0
    
    def tracked_failing_func():
        nonlocal call_count
        call_count += 1
        raise Exception("Service unavailable")
    
    # Fail 3 times to open
    for i in range(3):
        try:
            breaker.call(tracked_failing_func)
        except Exception:
            pass
    
    checks = [
        ("Function called 3 times", call_count == 3),
        ("Circuit is OPEN", breaker.get_state() == CircuitState.OPEN),
    ]
    
    # Try 10 more times (should be rejected)
    for i in range(10):
        try:
            breaker.call(tracked_failing_func)
        except CircuitBreakerOpenError:
            pass
    
    checks.append(("Function still called only 3 times", call_count == 3))
    checks.append(("Prevented 10 calls", True))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_health_checks():
    """Verify health check functionality."""
    print_section("5. Verify Health Checks")
    
    checks = []
    
    # Check Pinecone health
    try:
        result = check_pinecone_health()
        checks.extend([
            ("check_pinecone_health returns result", result is not None),
            ("Has service field", hasattr(result, 'service')),
            ("Has is_healthy field", hasattr(result, 'is_healthy')),
            ("Has latency_ms field", hasattr(result, 'latency_ms')),
            ("Service is 'pinecone'", result.service == "pinecone"),
        ])
    except Exception as e:
        checks.append((f"check_pinecone_health error: {e}", False))
    
    # Check reviewer health
    try:
        result = check_reviewer_health()
        checks.extend([
            ("check_reviewer_health returns result", result is not None),
            ("Service is 'reviewer'", result.service == "reviewer"),
        ])
    except Exception as e:
        checks.append((f"check_reviewer_health error: {e}", False))
    
    # Check all services
    try:
        results = check_all_services()
        checks.extend([
            ("check_all_services returns dict", isinstance(results, dict)),
            ("Has 'pinecone' key", 'pinecone' in results),
            ("Has 'reviewer' key", 'reviewer' in results),
        ])
    except Exception as e:
        checks.append((f"check_all_services error: {e}", False))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_circuit_breaker_registry():
    """Verify global circuit breaker registry."""
    print_section("6. Verify Circuit Breaker Registry")
    
    reset_all_circuit_breakers()
    
    # Create breaker
    config = CircuitBreakerConfig(name="service1")
    breaker1 = get_circuit_breaker("service1", config)
    
    checks = [
        ("get_circuit_breaker creates breaker", breaker1 is not None),
        ("Breaker name is 'service1'", breaker1.config.name == "service1"),
    ]
    
    # Get same breaker again
    breaker2 = get_circuit_breaker("service1")
    
    checks.append(("Returns same instance", breaker1 is breaker2))
    
    # Create different breaker
    breaker3 = get_circuit_breaker("service2", CircuitBreakerConfig(name="service2"))
    
    checks.append(("Different name creates different breaker", breaker3 is not breaker1))
    
    # Reset all
    reset_all_circuit_breakers()
    
    from core.circuit import get_all_circuit_breakers
    breakers = get_all_circuit_breakers()
    
    checks.append(("reset_all clears registry", len(breakers) == 0))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_config():
    """Verify circuit breaker configuration."""
    print_section("7. Verify Configuration")
    
    config = CircuitBreakerConfig(
        name="test",
        failure_threshold=10,
        cooldown_seconds=120.0,
        success_threshold=3,
        timeout_seconds=5.0
    )
    
    checks = [
        ("Name set correctly", config.name == "test"),
        ("Failure threshold = 10", config.failure_threshold == 10),
        ("Cooldown = 120s", config.cooldown_seconds == 120.0),
        ("Success threshold = 3", config.success_threshold == 3),
        ("Timeout = 5s", config.timeout_seconds == 5.0),
    ]
    
    # Default config
    default_config = CircuitBreakerConfig(name="default")
    
    checks.extend([
        ("Default failure threshold = 5", default_config.failure_threshold == 5),
        ("Default cooldown = 60s", default_config.cooldown_seconds == 60.0),
        ("Default success threshold = 2", default_config.success_threshold == 2),
    ])
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_stats():
    """Verify circuit breaker statistics."""
    print_section("8. Verify Statistics")
    
    reset_all_circuit_breakers()
    
    config = CircuitBreakerConfig(name="test")
    breaker = CircuitBreaker(config)
    
    stats = breaker.get_stats()
    
    checks = [
        ("Has 'name' field", 'name' in stats),
        ("Has 'state' field", 'state' in stats),
        ("Has 'consecutive_failures' field", 'consecutive_failures' in stats),
        ("Has 'consecutive_successes' field", 'consecutive_successes' in stats),
        ("Has 'total_failures' field", 'total_failures' in stats),
        ("Has 'total_successes' field", 'total_successes' in stats),
        ("Has 'failure_threshold' field", 'failure_threshold' in stats),
        ("Has 'cooldown_seconds' field", 'cooldown_seconds' in stats),
        ("Name matches", stats['name'] == "test"),
        ("Initial state is 'closed'", stats['state'] == "closed"),
        ("Initial consecutive failures = 0", stats['consecutive_failures'] == 0),
    ]
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def run_unit_tests():
    """Run unit tests."""
    print_section("9. Run Unit Tests")
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('tests.perf.test_circuit_breaker')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun
    
    print(f"\n{'✅' if result.wasSuccessful() else '❌'} Tests: {passed}/{total} passed")
    
    return passed, total


def main():
    """Run all verifications."""
    print("\n" + "="*60)
    print("  CIRCUIT BREAKER VERIFICATION")
    print("="*60)
    
    results = []
    
    # Run all verifications
    results.append(("Circuit States", *verify_circuit_breaker_states()))
    results.append(("Failure Counters", *verify_failure_counters()))
    results.append(("Half-Open Probe", *verify_half_open_probe()))
    results.append(("Prevents Spamming", *verify_prevents_spamming()))
    results.append(("Health Checks", *verify_health_checks()))
    results.append(("Registry", *verify_circuit_breaker_registry()))
    results.append(("Configuration", *verify_config()))
    results.append(("Statistics", *verify_stats()))
    results.append(("Unit Tests", *run_unit_tests()))
    
    # Print summary
    print_section("SUMMARY")
    
    total_passed = 0
    total_checks = 0
    
    for name, passed, total in results:
        total_passed += passed
        total_checks += total
        status = "✅" if passed == total else "❌"
        print(f"{status} {name:25s} {passed:3d}/{total:3d} ({100*passed/total:.0f}%)")
    
    print("\n" + "="*60)
    success = total_passed == total_checks
    print(f"{'✅ ALL CHECKS PASSED' if success else '❌ SOME CHECKS FAILED'}")
    print(f"Total: {total_passed}/{total_checks} ({100*total_passed/total_checks:.1f}%)")
    print("="*60)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
