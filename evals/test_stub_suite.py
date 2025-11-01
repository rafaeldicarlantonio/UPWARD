#!/usr/bin/env python3
"""
Test script to demonstrate the eval harness with mock data.
"""

import sys
import json
import tempfile
import os
from unittest.mock import Mock, patch

# Add workspace to path
sys.path.insert(0, '/workspace')

# Import harness
import importlib.util
spec = importlib.util.spec_from_file_location("eval_run", "/workspace/evals/run.py")
eval_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_run)

EvalRunner = eval_run.EvalRunner
write_json_report = eval_run.write_json_report
print_latency_histogram = eval_run.print_latency_histogram


def mock_api_call(self, case):
    """Mock API call that simulates responses."""
    import time
    import random
    
    # Simulate processing time
    latency_base = random.uniform(50, 300)
    time.sleep(latency_base / 1000)  # Convert to seconds
    
    # Determine if test should pass
    case_id = case["id"]
    must_include = case.get("must_include", [])
    
    # Create mock answer that includes required terms
    if must_include:
        answer = f"Test answer that includes {' and '.join(must_include)}"
    else:
        answer = "Test answer"
    
    # Simulate pass/fail based on case ID
    if "fail" in case_id.lower():
        answer = "Answer without required terms"
    
    # Create result
    from evals.run import EvalResult
    
    result = EvalResult(
        case_id=case_id,
        prompt=case["prompt"],
        category=case.get("category", "test"),
        passed=all(term.lower() in answer.lower() for term in must_include),
        latency_ms=latency_base,
        total_latency_ms=latency_base,
        retrieval_latency_ms=latency_base * 0.4,
        ranking_latency_ms=latency_base * 0.2,
        packing_latency_ms=latency_base * 0.1,
        retrieved_chunks=5,
        meets_latency_constraint=latency_base < case.get("max_latency_ms", 1000),
        error=None if all(term.lower() in answer.lower() for term in must_include) else "Missing required terms"
    )
    
    return result


def main():
    """Run stub suite test."""
    print("="*80)
    print("EVAL HARNESS STUB SUITE TEST")
    print("="*80)
    print()
    
    # Create temporary testset with mock data
    testset_data = [
        {
            "id": "stub_001_pass",
            "prompt": "What is the capital of France?",
            "category": "geography",
            "must_include": ["Paris"],
            "max_latency_ms": 500
        },
        {
            "id": "stub_002_pass",
            "prompt": "What is 2+2?",
            "category": "math",
            "must_include": ["4"],
            "max_latency_ms": 500
        },
        {
            "id": "stub_003_pass",
            "prompt": "Name a programming language",
            "category": "tech",
            "must_include": ["Python", "language"],
            "max_latency_ms": 500
        },
        {
            "id": "stub_004_fail",
            "prompt": "Test failure case",
            "category": "error",
            "must_include": ["impossible", "terms"],
            "max_latency_ms": 500
        },
        {
            "id": "stub_005_slow",
            "prompt": "Simulate slow response",
            "category": "performance",
            "must_include": ["test"],
            "max_latency_ms": 100  # Very strict to trigger failure
        }
    ]
    
    # Create temporary testset file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        json.dump(testset_data, f)
        testset_path = f.name
    
    # Create temporary output directory
    output_dir = tempfile.mkdtemp()
    output_json = os.path.join(output_dir, "stub_results.json")
    
    try:
        # Create runner
        runner = EvalRunner(base_url="http://mock", api_key="mock-key")
        runner.max_latency_ms = 500
        runner.max_individual_latency_ms = 1000
        
        # Patch run_single_case with mock
        with patch.object(EvalRunner, 'run_single_case', mock_api_call):
            # Run testset
            print(f"📦 Running testset with {len(testset_data)} cases...")
            print()
            
            results = runner.run_testset(testset_path)
            
            # Generate summary
            print()
            print("="*80)
            print("GENERATING SUMMARY")
            print("="*80)
            print()
            
            summary = runner.print_summary()
            
            # Print latency histogram
            print()
            print_latency_histogram(results)
            
            # Write JSON report
            print()
            write_json_report(results, summary, output_json)
            
            # Show report content
            print()
            print("="*80)
            print("JSON REPORT SAMPLE")
            print("="*80)
            print()
            
            with open(output_json, 'r') as f:
                report = json.load(f)
            
            print(f"Timestamp: {report['timestamp']}")
            print(f"Total cases: {report['summary']['total_cases']}")
            print(f"Passed: {report['summary']['passed_cases']}")
            print(f"Failed: {report['summary']['failed_cases']}")
            print(f"Pass rate: {report['summary']['pass_rate']:.1%}")
            print(f"Avg latency: {report['summary']['avg_latency_ms']:.1f}ms")
            print(f"P95 latency: {report['summary']['p95_latency_ms']:.1f}ms")
            print()
            
            # Show category breakdown
            print("Category breakdown:")
            for category, stats in report['summary']['category_breakdown'].items():
                print(f"  {category}: {stats['passed']}/{stats['total']}")
            
            print()
            print("="*80)
            print("TEST COMPLETE")
            print("="*80)
            print()
            print(f"✅ Successfully demonstrated eval harness capabilities:")
            print(f"   • Loaded test suite definition")
            print(f"   • Executed {len(results)} test cases")
            print(f"   • Captured pass/fail status")
            print(f"   • Measured latency metrics")
            print(f"   • Generated JSON report: {output_json}")
            print(f"   • Displayed console summary")
            print(f"   • Showed latency histogram")
            print()
            
            # Clean up
            if os.path.exists(output_json):
                print(f"📄 JSON report saved to: {output_json}")
                print(f"   (View with: cat {output_json})")
            
            return 0
    
    finally:
        # Clean up temporary testset file
        if os.path.exists(testset_path):
            os.unlink(testset_path)


if __name__ == "__main__":
    sys.exit(main())
