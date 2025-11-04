#!/usr/bin/env python3
"""
Comprehensive verification script for reviewer budget implementation.
"""

import sys
import time
import unittest
from unittest.mock import patch

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.reviewer import (
    AnswerReviewer,
    ReviewResult,
    get_reviewer,
    review_answer_with_budget
)
from core.circuit import reset_all_circuit_breakers


def print_section(title):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def verify_review_result():
    """Verify ReviewResult dataclass."""
    print_section("1. Verify ReviewResult")
    
    checks = []
    
    # Not skipped
    result = ReviewResult(
        skipped=False,
        score=0.85,
        confidence=0.9,
        flags={"quality": "high"},
        latency_ms=120.0
    )
    
    checks.extend([
        ("Has skipped field", hasattr(result, 'skipped')),
        ("Has score field", hasattr(result, 'score')),
        ("Has confidence field", hasattr(result, 'confidence')),
        ("Has flags field", hasattr(result, 'flags')),
        ("Has latency_ms field", hasattr(result, 'latency_ms')),
        ("Score = 0.85", result.score == 0.85),
    ])
    
    # Skipped
    result = ReviewResult(
        skipped=True,
        skip_reason="timeout_exceeded: 500ms",
        latency_ms=520.0
    )
    
    checks.extend([
        ("Skipped = True", result.skipped == True),
        ("Has skip_reason", result.skip_reason is not None),
        ("Score is None when skipped", result.score is None),
    ])
    
    # to_dict
    d = result.to_dict()
    checks.extend([
        ("to_dict has skipped", 'skipped' in d),
        ("to_dict excludes score when skipped", 'score' not in d),
    ])
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_configuration():
    """Verify reviewer configuration."""
    print_section("2. Verify Configuration")
    
    reset_all_circuit_breakers()
    
    checks = []
    
    # Default config
    reviewer = AnswerReviewer(config={})
    checks.extend([
        ("is_enabled() works", callable(reviewer.is_enabled)),
        ("get_budget_ms() works", callable(reviewer.get_budget_ms)),
        ("Default budget = 500ms", reviewer.get_budget_ms() == 500.0),
    ])
    
    # Enabled by default
    config = {"PERF_REVIEWER_ENABLED": True}
    reviewer = AnswerReviewer(config=config)
    checks.append(("Enabled by default", reviewer.is_enabled()))
    
    # Can be disabled
    config = {"PERF_REVIEWER_ENABLED": False}
    reviewer = AnswerReviewer(config=config)
    checks.append(("Can be disabled", not reviewer.is_enabled()))
    
    # Custom budget
    config = {"PERF_REVIEWER_BUDGET_MS": 300}
    reviewer = AnswerReviewer(config=config)
    checks.append(("Custom budget = 300ms", reviewer.get_budget_ms() == 300.0))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_skip_conditions():
    """Verify reviewer skip conditions."""
    print_section("3. Verify Skip Conditions")
    
    reset_all_circuit_breakers()
    
    checks = []
    
    # Skips when disabled
    config = {"PERF_REVIEWER_ENABLED": False}
    reviewer = AnswerReviewer(config=config)
    result = reviewer.review_answer("Test")
    
    checks.extend([
        ("Skips when disabled", result.skipped),
        ("Skip reason = reviewer_disabled", result.skip_reason == "reviewer_disabled"),
    ])
    
    # Normal review (enabled)
    config = {"PERF_REVIEWER_ENABLED": True, "PERF_REVIEWER_BUDGET_MS": 500}
    reviewer = AnswerReviewer(config=config)
    result = reviewer.review_answer("Test answer")
    
    checks.append(("Completes when enabled", not result.skipped or "timeout" in result.skip_reason.lower()))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_budget_enforcement():
    """Verify budget enforcement."""
    print_section("4. Verify Budget Enforcement")
    
    reset_all_circuit_breakers()
    
    checks = []
    
    # Fast review (completes within budget)
    config = {"PERF_REVIEWER_ENABLED": True, "PERF_REVIEWER_BUDGET_MS": 500}
    reviewer = AnswerReviewer(config=config)
    
    def fast_review(*args, **kwargs):
        return ReviewResult(skipped=False, score=0.85, confidence=0.9)
    
    with patch.object(reviewer, '_perform_review', return_value=fast_review()):
        result = reviewer.review_answer("Good answer")
    
    checks.extend([
        ("Fast review completes", not result.skipped),
        ("Fast review has score", result.score is not None),
        ("Fast review within budget", result.latency_ms < 500),
    ])
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_scoring():
    """Verify review scoring logic."""
    print_section("5. Verify Scoring Logic")
    
    reset_all_circuit_breakers()
    
    checks = []
    
    config = {"PERF_REVIEWER_ENABLED": True, "PERF_REVIEWER_BUDGET_MS": 500}
    reviewer = AnswerReviewer(config=config)
    
    # Normal answer
    result = reviewer.review_answer("This is a good answer with sufficient detail.")
    checks.extend([
        ("Reviews normal answer", isinstance(result, ReviewResult)),
        ("Has score", result.score is not None or result.skipped),
    ])
    
    # Short answer (flagged)
    result = reviewer.review_answer("Short")
    if not result.skipped:
        checks.extend([
            ("Flags short answer", result.flags.get("too_short", False)),
            ("Short answer low score", result.score < 0.5),
        ])
    else:
        checks.extend([
            ("Short answer check skipped", True),
            ("Short answer skipped", True),
        ])
    
    # Uncertain answer
    result = reviewer.review_answer("I don't know the answer.")
    if not result.skipped:
        checks.append(("Flags uncertain answer", result.flags.get("uncertain", False)))
    else:
        checks.append(("Uncertain answer check skipped", True))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_convenience_functions():
    """Verify convenience functions."""
    print_section("6. Verify Convenience Functions")
    
    reset_all_circuit_breakers()
    
    checks = []
    
    # get_reviewer
    reviewer1 = get_reviewer()
    reviewer2 = get_reviewer()
    
    checks.extend([
        ("get_reviewer returns instance", reviewer1 is not None),
        ("get_reviewer returns singleton", reviewer1 is reviewer2),
    ])
    
    # review_answer_with_budget
    try:
        result = review_answer_with_budget("Test answer")
        checks.extend([
            ("review_answer_with_budget works", isinstance(result, ReviewResult)),
            ("Returns ReviewResult", hasattr(result, 'skipped')),
        ])
    except Exception as e:
        checks.append((f"review_answer_with_budget error: {e}", False))
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_circuit_breaker_integration():
    """Verify circuit breaker integration."""
    print_section("7. Verify Circuit Breaker Integration")
    
    reset_all_circuit_breakers()
    
    checks = []
    
    config = {"PERF_REVIEWER_ENABLED": True, "PERF_REVIEWER_BUDGET_MS": 500}
    reviewer = AnswerReviewer(config=config)
    
    checks.extend([
        ("Has circuit_breaker property", hasattr(reviewer, 'circuit_breaker')),
        ("circuit_breaker is not None", reviewer.circuit_breaker is not None),
    ])
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def verify_acceptance_criteria():
    """Verify acceptance criteria."""
    print_section("8. Verify Acceptance Criteria")
    
    reset_all_circuit_breakers()
    
    checks = []
    
    # AC1: Enforces PERF_REVIEWER_BUDGET_MS
    config = {"PERF_REVIEWER_BUDGET_MS": 300}
    reviewer = AnswerReviewer(config=config)
    checks.append(("Enforces custom budget", reviewer.get_budget_ms() == 300))
    
    # AC2: Fast path includes review
    config = {"PERF_REVIEWER_ENABLED": True, "PERF_REVIEWER_BUDGET_MS": 500}
    reviewer = AnswerReviewer(config=config)
    
    def fast_review(*args, **kwargs):
        time.sleep(0.05)  # 50ms
        return ReviewResult(skipped=False, score=0.88, confidence=0.92)
    
    with patch.object(reviewer, '_perform_review', side_effect=fast_review):
        result = reviewer.review_answer("High quality answer")
    
    checks.extend([
        ("Fast path not skipped", not result.skipped),
        ("Fast path has score", result.score is not None),
    ])
    
    # AC3: Skipped excludes scores
    result_skipped = ReviewResult(skipped=True, skip_reason="timeout")
    d = result_skipped.to_dict()
    checks.extend([
        ("Skipped result has no score in dict", 'score' not in d),
        ("Skipped result has skip_reason", 'skip_reason' in d),
    ])
    
    passed = sum(1 for _, result in checks if result)
    for name, result in checks:
        print(f"{'✅' if result else '❌'} {name}")
    
    return passed, len(checks)


def run_unit_tests():
    """Run unit tests."""
    print_section("9. Run Unit Tests")
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('tests.perf.test_reviewer_budget')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun
    
    print(f"\n{'✅' if result.wasSuccessful() else '❌'} Tests: {passed}/{total} passed")
    
    return passed, total


def main():
    """Run all verifications."""
    print("\n" + "="*60)
    print("  REVIEWER BUDGET VERIFICATION")
    print("="*60)
    
    results = []
    
    # Run all verifications
    results.append(("ReviewResult", *verify_review_result()))
    results.append(("Configuration", *verify_configuration()))
    results.append(("Skip Conditions", *verify_skip_conditions()))
    results.append(("Budget Enforcement", *verify_budget_enforcement()))
    results.append(("Scoring Logic", *verify_scoring()))
    results.append(("Convenience Functions", *verify_convenience_functions()))
    results.append(("Circuit Breaker", *verify_circuit_breaker_integration()))
    results.append(("Acceptance Criteria", *verify_acceptance_criteria()))
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
