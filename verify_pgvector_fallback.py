#!/usr/bin/env python3
"""
Comprehensive verification script for pgvector fallback implementation.
"""

import sys
import unittest
from unittest.mock import Mock, patch

# Mock problematic imports
sys.modules['supabase'] = Mock()
sys.modules['vendors.supabase_client'] = Mock()
sys.modules['vendors.pinecone_client'] = Mock()
sys.modules['app.settings'] = Mock()
sys.modules['pydantic'] = Mock()
sys.modules['pydantic'].BaseModel = type('BaseModel', (), {})
sys.modules['tenacity'] = Mock()
sys.modules['tenacity'].retry = lambda *args, **kwargs: lambda f: f
sys.modules['tenacity'].stop_after_attempt = Mock()
sys.modules['tenacity'].wait_exponential = Mock()
sys.modules['tenacity'].retry_if_exception_type = Mock()

# Add workspace to path
sys.path.insert(0, '/workspace')

from adapters.vector_fallback import (
    PgvectorFallbackAdapter,
    FallbackQueryResult,
    MockMatch,
    get_fallback_adapter
)


def print_section(title):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def verify_constants():
    """Verify fallback adapter constants."""
    print_section("1. Verify Constants")
    
    adapter = PgvectorFallbackAdapter()
    
    checks = [
        ("FALLBACK_EXPLICATE_K", adapter.FALLBACK_EXPLICATE_K, 8),
        ("FALLBACK_IMPLICATE_K", adapter.FALLBACK_IMPLICATE_K, 4),
        ("FALLBACK_TIMEOUT_MS", adapter.FALLBACK_TIMEOUT_MS, 350),
    ]
    
    passed = 0
    for name, actual, expected in checks:
        if actual == expected:
            print(f"✅ {name} = {actual}")
            passed += 1
        else:
            print(f"❌ {name} = {actual} (expected {expected})")
    
    return passed, len(checks)


def verify_reduced_k():
    """Verify k values are reduced from normal."""
    print_section("2. Verify Reduced K Values")
    
    adapter = PgvectorFallbackAdapter()
    
    checks = [
        ("Explicate k < 16", adapter.FALLBACK_EXPLICATE_K < 16),
        ("Implicate k < 8", adapter.FALLBACK_IMPLICATE_K < 8),
        ("Explicate reduction = 50%", adapter.FALLBACK_EXPLICATE_K == 16 / 2),
        ("Implicate reduction = 50%", adapter.FALLBACK_IMPLICATE_K == 8 / 2),
    ]
    
    passed = 0
    for name, condition in checks:
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}")
    
    return passed, len(checks)


def verify_health_check():
    """Verify health check functionality."""
    print_section("3. Verify Health Check")
    
    adapter = PgvectorFallbackAdapter()
    
    checks = [
        ("Has health check cache", hasattr(adapter, '_health_check_cache')),
        ("Cache has 'last_check'", 'last_check' in adapter._health_check_cache),
        ("Cache has 'is_healthy'", 'is_healthy' in adapter._health_check_cache),
        ("Cache has 'cache_ttl'", 'cache_ttl' in adapter._health_check_cache),
        ("Cache TTL = 30s", adapter._health_check_cache['cache_ttl'] == 30),
    ]
    
    passed = 0
    for name, condition in checks:
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}")
    
    return passed, len(checks)


def verify_fallback_result():
    """Verify FallbackQueryResult structure."""
    print_section("4. Verify FallbackQueryResult")
    
    result = FallbackQueryResult(
        matches=[MockMatch("id1", 0.9, {"text": "test"})],
        fallback_used=True,
        latency_ms=100.0,
        source="pgvector"
    )
    
    checks = [
        ("Has matches field", hasattr(result, 'matches')),
        ("Has fallback_used field", hasattr(result, 'fallback_used')),
        ("Has latency_ms field", hasattr(result, 'latency_ms')),
        ("Has source field", hasattr(result, 'source')),
        ("fallback_used = True", result.fallback_used == True),
        ("source = 'pgvector'", result.source == "pgvector"),
        ("matches length = 1", len(result.matches) == 1),
    ]
    
    passed = 0
    for name, condition in checks:
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}")
    
    return passed, len(checks)


def verify_methods():
    """Verify adapter has required methods."""
    print_section("5. Verify Adapter Methods")
    
    adapter = PgvectorFallbackAdapter()
    
    methods = [
        "check_pinecone_health",
        "should_use_fallback",
        "query_explicate_fallback",
        "query_implicate_fallback",
        "_get_role_rank",
        "_format_vector",
    ]
    
    passed = 0
    for method in methods:
        if hasattr(adapter, method) and callable(getattr(adapter, method)):
            print(f"✅ {method}()")
            passed += 1
        else:
            print(f"❌ {method}() missing")
    
    return passed, len(methods)


def verify_singleton():
    """Verify singleton pattern."""
    print_section("6. Verify Singleton Pattern")
    
    adapter1 = get_fallback_adapter()
    adapter2 = get_fallback_adapter()
    
    checks = [
        ("get_fallback_adapter() works", adapter1 is not None),
        ("Returns same instance", adapter1 is adapter2),
        ("Instance is PgvectorFallbackAdapter", isinstance(adapter1, PgvectorFallbackAdapter)),
    ]
    
    passed = 0
    for name, condition in checks:
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}")
    
    return passed, len(checks)


def verify_mock_match():
    """Verify MockMatch class."""
    print_section("7. Verify MockMatch")
    
    match = MockMatch(
        id="test_id",
        score=0.95,
        metadata={"text": "test", "title": "Test"}
    )
    
    checks = [
        ("Has id attribute", hasattr(match, 'id')),
        ("Has score attribute", hasattr(match, 'score')),
        ("Has metadata attribute", hasattr(match, 'metadata')),
        ("id = 'test_id'", match.id == "test_id"),
        ("score = 0.95", match.score == 0.95),
        ("metadata has 'text'", 'text' in match.metadata),
    ]
    
    passed = 0
    for name, condition in checks:
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}")
    
    return passed, len(checks)


def verify_trigger_logic():
    """Verify fallback trigger logic."""
    print_section("8. Verify Trigger Logic")
    
    adapter = PgvectorFallbackAdapter()
    
    # Test 1: Unhealthy Pinecone triggers fallback
    with patch.object(adapter, 'check_pinecone_health', return_value=(False, "Connection error")):
        with patch('config.load_config', return_value={'PERF_PGVECTOR_ENABLED': True, 'PERF_FALLBACKS_ENABLED': True}):
            should_use, reason = adapter.should_use_fallback()
            check1 = should_use == True and reason is not None
    
    # Test 2: Healthy Pinecone doesn't trigger fallback
    with patch.object(adapter, 'check_pinecone_health', return_value=(True, None)):
        with patch('config.load_config', return_value={'PERF_PGVECTOR_ENABLED': True, 'PERF_FALLBACKS_ENABLED': True}):
            should_use, reason = adapter.should_use_fallback()
            check2 = should_use == False and reason is None
    
    checks = [
        ("Unhealthy triggers fallback", check1),
        ("Healthy doesn't trigger", check2),
    ]
    
    passed = 0
    for name, condition in checks:
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}")
    
    return passed, len(checks)


def run_unit_tests():
    """Run unit tests."""
    print_section("9. Run Unit Tests")
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('tests.perf.test_pgvector_fallback')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun
    
    print(f"\n{'✅' if result.wasSuccessful() else '❌'} Tests: {passed}/{total} passed")
    
    return passed, total


def main():
    """Run all verifications."""
    print("\n" + "="*60)
    print("  PGVECTOR FALLBACK VERIFICATION")
    print("="*60)
    
    results = []
    
    # Run all verifications
    results.append(("Constants", *verify_constants()))
    results.append(("Reduced K", *verify_reduced_k()))
    results.append(("Health Check", *verify_health_check()))
    results.append(("FallbackQueryResult", *verify_fallback_result()))
    results.append(("Adapter Methods", *verify_methods()))
    results.append(("Singleton Pattern", *verify_singleton()))
    results.append(("MockMatch", *verify_mock_match()))
    results.append(("Trigger Logic", *verify_trigger_logic()))
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
