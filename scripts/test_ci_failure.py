#!/usr/bin/env python3
"""
Script to deliberately break evaluation tests to verify CI failure detection.

Usage:
  # Test that CI detects functional failures
  python scripts/test_ci_failure.py --mode functional
  
  # Test that CI detects latency violations
  python scripts/test_ci_failure.py --mode latency
  
  # Test that CI detects constraint violations
  python scripts/test_ci_failure.py --mode constraint
"""

import os
import sys
import json
import argparse

# Add workspace to path
sys.path.insert(0, '/workspace')


def break_functional_test():
    """Create a test case designed to fail functionally."""
    test_case = {
        "id": "ci_test_functional_fail",
        "query": "This query will intentionally fail",
        "category": "test",
        "expected_answer": "This will not match",
        "rationale": "Deliberately broken to test CI failure detection"
    }
    
    # Write to temporary test file
    output_path = "evals/testsets/ci_fail_functional.json"
    with open(output_path, 'w') as f:
        json.dump([test_case], f, indent=2)
    
    print(f"✅ Created functional failure test: {output_path}")
    print("   This test case is designed to fail assertion checks")
    return output_path


def break_latency_test():
    """Create a test case designed to exceed latency budgets."""
    # Create test with unreasonably tight latency constraint
    test_case = {
        "id": "ci_test_latency_fail",
        "query": "Test latency budget violation",
        "category": "test",
        "max_latency_ms": 1,  # Impossibly tight
        "rationale": "Deliberately broken to test CI latency gate detection"
    }
    
    output_path = "evals/testsets/ci_fail_latency.json"
    with open(output_path, 'w') as f:
        json.dump([test_case], f, indent=2)
    
    print(f"✅ Created latency failure test: {output_path}")
    print("   This test has unrealistic latency budget (1ms)")
    return output_path


def break_constraint_test():
    """Create a test case designed to violate constraints."""
    test_cases = []
    
    # Create 10 tests that will all fail
    for i in range(10):
        test_cases.append({
            "id": f"ci_test_constraint_fail_{i}",
            "query": f"Constraint violation test {i}",
            "category": "test",
            "expected_pass": False,  # All designed to fail
            "rationale": "Deliberately broken to test CI constraint detection"
        })
    
    output_path = "evals/testsets/ci_fail_constraint.json"
    with open(output_path, 'w') as f:
        json.dump(test_cases, f, indent=2)
    
    print(f"✅ Created constraint failure test: {output_path}")
    print("   This test suite will have 0% pass rate")
    return output_path


def restore_tests():
    """Remove deliberate failure tests."""
    test_files = [
        "evals/testsets/ci_fail_functional.json",
        "evals/testsets/ci_fail_latency.json",
        "evals/testsets/ci_fail_constraint.json"
    ]
    
    removed = 0
    for test_file in test_files:
        if os.path.exists(test_file):
            os.remove(test_file)
            removed += 1
            print(f"🗑️  Removed: {test_file}")
    
    if removed > 0:
        print(f"\n✅ Cleaned up {removed} failure test file(s)")
    else:
        print("ℹ️  No failure test files to clean up")


def main():
    parser = argparse.ArgumentParser(description="Test CI failure detection")
    parser.add_argument(
        "--mode",
        choices=["functional", "latency", "constraint", "restore"],
        required=True,
        help="Type of failure to simulate (or restore to clean state)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("CI Failure Detection Test")
    print("=" * 60)
    print()
    
    if args.mode == "restore":
        restore_tests()
    elif args.mode == "functional":
        print("🔴 Creating FUNCTIONAL FAILURE test...")
        test_path = break_functional_test()
        print()
        print("To run this test:")
        print(f"  python3 evals/run.py --testset {test_path} --ci-mode")
        print()
        print("Expected result: CI should mark as FAILED (functional failure)")
    
    elif args.mode == "latency":
        print("🔴 Creating LATENCY VIOLATION test...")
        test_path = break_latency_test()
        print()
        print("To run this test:")
        print(f"  python3 evals/run.py --testset {test_path} --ci-mode")
        print()
        print("Expected result: CI should mark as FAILED (latency budget exceeded)")
    
    elif args.mode == "constraint":
        print("🔴 Creating CONSTRAINT VIOLATION test...")
        test_path = break_constraint_test()
        print()
        print("To run this test:")
        print(f"  python3 evals/run.py --testset {test_path} --ci-mode")
        print()
        print("Expected result: CI should mark as FAILED (min pass rate violated)")
    
    print()
    print("To restore clean state:")
    print("  python scripts/test_ci_failure.py --mode restore")
    print("=" * 60)


if __name__ == "__main__":
    main()
