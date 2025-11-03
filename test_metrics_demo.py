#!/usr/bin/env python3
"""
Demo script to show metrics instrumentation in action.
"""

import sys
sys.path.insert(0, '/workspace')

from core.metrics import EvalMetrics, get_counter, get_gauge, get_histogram_stats, reset_metrics
from evals.run import EvalRunner, EvalSummary

# Reset metrics
reset_metrics()

print("=" * 80)
print("METRICS INSTRUMENTATION DEMO")
print("=" * 80)
print()

# Simulate a suite run
suite_name = "demo_suite"
runner = EvalRunner(suite_name=suite_name, enforce_latency_budgets=False)

print("1. Recording suite run...")
EvalMetrics.record_suite_run(suite_name, True, 5000.0, 20)
print(f"   Suite runs: {get_counter('eval.suite.runs', {'suite': suite_name, 'success': 'true'})}")
print()

print("2. Recording case results...")
for i in range(20):
    passed = i < 18  # 18 passed, 2 failed
    EvalMetrics.record_case_result(suite_name, f"case_{i:03d}", passed, "implicate_lift")

total = get_counter("eval.cases.total", {"suite": suite_name, "category": "implicate_lift"})
passed = get_counter("eval.cases.passed", {"suite": suite_name, "category": "implicate_lift"})
failed = get_counter("eval.cases.failed", {"suite": suite_name, "category": "implicate_lift"})

print(f"   Total cases: {total}")
print(f"   Passed: {passed}")
print(f"   Failed: {failed}")
print()

print("3. Recording latencies...")
latencies = [120, 150, 180, 200, 250, 300, 350, 400, 450, 500]
for lat in latencies:
    EvalMetrics.record_latency("retrieval", lat, suite_name, "implicate_lift")

stats = get_histogram_stats("eval.latency.retrieval_ms", {"operation": "retrieval", "suite": suite_name, "category": "implicate_lift"})
print(f"   Latency count: {stats['count']}")
print(f"   Latency avg: {stats['avg']:.1f}ms")
print()

print("4. Setting quality score...")
quality = passed / total if total > 0 else 0.0
EvalMetrics.set_quality_score(suite_name, quality)
retrieved_quality = EvalMetrics.get_suite_quality_score(suite_name)
print(f"   Quality score: {retrieved_quality:.1%}")
print()

print("5. Printing dashboard...")
summary = EvalSummary(
    total_cases=total,
    passed_cases=passed,
    failed_cases=failed,
    avg_latency_ms=stats['avg'],
    p95_latency_ms=450.0,
    max_latency_ms=500.0,
    category_breakdown={},
    performance_issues=[],
    latency_distribution={"p50": 200.0, "p95": 450.0}
)

runner.print_dashboard_line(summary, suite_name)
print()

print("✅ Demo complete!")
print()

