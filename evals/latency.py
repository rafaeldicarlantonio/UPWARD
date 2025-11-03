#!/usr/bin/env python3
"""
Latency budget gates for evaluation suites.

Defines performance budgets for different operations and provides
helpers to check if results meet the budgets.

Budgets:
- Retrieval p95 ≤ 500ms
- Packing p95 ≤ 550ms
- Internal compare p95 ≤ 400ms
- External compare p95 ≤ 2000ms (with timeout handling)
"""

import statistics
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class OperationType(Enum):
    """Types of operations with latency budgets."""
    RETRIEVAL = "retrieval"
    PACKING = "packing"
    INTERNAL_COMPARE = "internal_compare"
    EXTERNAL_COMPARE = "external_compare"
    SCORING = "scoring"
    TOTAL = "total"


@dataclass
class LatencyBudget:
    """Latency budget definition."""
    operation: OperationType
    p50_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    p99_ms: Optional[float] = None
    max_ms: Optional[float] = None
    description: str = ""


# Standard latency budgets
STANDARD_BUDGETS = {
    OperationType.RETRIEVAL: LatencyBudget(
        operation=OperationType.RETRIEVAL,
        p95_ms=500.0,
        description="Retrieval latency (DB query + ranking)"
    ),
    OperationType.PACKING: LatencyBudget(
        operation=OperationType.PACKING,
        p95_ms=550.0,
        description="Packing latency (answer generation + formatting)"
    ),
    OperationType.INTERNAL_COMPARE: LatencyBudget(
        operation=OperationType.INTERNAL_COMPARE,
        p95_ms=400.0,
        description="Internal compare latency"
    ),
    OperationType.EXTERNAL_COMPARE: LatencyBudget(
        operation=OperationType.EXTERNAL_COMPARE,
        p95_ms=2000.0,
        max_ms=3000.0,
        description="External compare latency (with timeout)"
    ),
    OperationType.SCORING: LatencyBudget(
        operation=OperationType.SCORING,
        p95_ms=200.0,
        description="Scoring latency (Pareto gate)"
    ),
}


@dataclass
class LatencyMetrics:
    """Computed latency metrics."""
    count: int
    mean_ms: float
    median_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    std_dev_ms: float = 0.0
    
    @classmethod
    def from_latencies(cls, latencies: List[float]) -> 'LatencyMetrics':
        """Compute metrics from list of latencies."""
        if not latencies:
            return cls(
                count=0,
                mean_ms=0.0,
                median_ms=0.0,
                p50_ms=0.0,
                p90_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                min_ms=0.0,
                max_ms=0.0,
                std_dev_ms=0.0
            )
        
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        # Compute percentiles
        p50 = compute_percentile(sorted_latencies, 50)
        p90 = compute_percentile(sorted_latencies, 90)
        p95 = compute_percentile(sorted_latencies, 95)
        p99 = compute_percentile(sorted_latencies, 99)
        
        return cls(
            count=n,
            mean_ms=statistics.mean(latencies),
            median_ms=statistics.median(latencies),
            p50_ms=p50,
            p90_ms=p90,
            p95_ms=p95,
            p99_ms=p99,
            min_ms=min(latencies),
            max_ms=max(latencies),
            std_dev_ms=statistics.stdev(latencies) if n > 1 else 0.0
        )


@dataclass
class LatencyGateResult:
    """Result of latency gate check."""
    operation: OperationType
    passed: bool
    budget: LatencyBudget
    metrics: LatencyMetrics
    violations: List[str] = field(default_factory=list)
    message: str = ""


def compute_percentile(sorted_values: List[float], percentile: float) -> float:
    """
    Compute percentile from sorted values.
    
    Args:
        sorted_values: List of values in sorted order
        percentile: Percentile to compute (0-100)
    
    Returns:
        Percentile value
    """
    if not sorted_values:
        return 0.0
    
    if len(sorted_values) == 1:
        return sorted_values[0]
    
    # Linear interpolation method
    n = len(sorted_values)
    k = (n - 1) * (percentile / 100.0)
    f = int(k)
    c = k - f
    
    if f + 1 < n:
        return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
    else:
        return sorted_values[f]


def check_latency_budget(
    latencies: List[float],
    operation: OperationType,
    custom_budget: Optional[LatencyBudget] = None
) -> LatencyGateResult:
    """
    Check if latencies meet budget for operation.
    
    Args:
        latencies: List of latency values in milliseconds
        operation: Type of operation
        custom_budget: Optional custom budget (uses standard if None)
    
    Returns:
        LatencyGateResult with pass/fail status
    """
    # Get budget
    budget = custom_budget or STANDARD_BUDGETS.get(operation)
    if not budget:
        raise ValueError(f"No budget defined for operation: {operation}")
    
    # Compute metrics
    metrics = LatencyMetrics.from_latencies(latencies)
    
    # Check budget constraints
    violations = []
    passed = True
    
    if budget.p50_ms is not None and metrics.p50_ms > budget.p50_ms:
        violations.append(f"p50 {metrics.p50_ms:.1f}ms exceeds budget {budget.p50_ms:.1f}ms")
        passed = False
    
    if budget.p95_ms is not None and metrics.p95_ms > budget.p95_ms:
        violations.append(f"p95 {metrics.p95_ms:.1f}ms exceeds budget {budget.p95_ms:.1f}ms")
        passed = False
    
    if budget.p99_ms is not None and metrics.p99_ms > budget.p99_ms:
        violations.append(f"p99 {metrics.p99_ms:.1f}ms exceeds budget {budget.p99_ms:.1f}ms")
        passed = False
    
    if budget.max_ms is not None and metrics.max_ms > budget.max_ms:
        violations.append(f"max {metrics.max_ms:.1f}ms exceeds budget {budget.max_ms:.1f}ms")
        passed = False
    
    # Generate message
    if passed:
        message = f"✅ {operation.value} latency within budget (p95: {metrics.p95_ms:.1f}ms ≤ {budget.p95_ms:.1f}ms)"
    else:
        message = f"❌ {operation.value} latency EXCEEDS budget: {'; '.join(violations)}"
    
    return LatencyGateResult(
        operation=operation,
        passed=passed,
        budget=budget,
        metrics=metrics,
        violations=violations,
        message=message
    )


def check_multiple_budgets(
    latencies_by_operation: Dict[OperationType, List[float]],
    custom_budgets: Optional[Dict[OperationType, LatencyBudget]] = None
) -> Dict[OperationType, LatencyGateResult]:
    """
    Check multiple operations against their budgets.
    
    Args:
        latencies_by_operation: Dictionary mapping operation to latency list
        custom_budgets: Optional custom budgets (uses standard for missing)
    
    Returns:
        Dictionary mapping operation to gate result
    """
    results = {}
    
    for operation, latencies in latencies_by_operation.items():
        custom_budget = custom_budgets.get(operation) if custom_budgets else None
        results[operation] = check_latency_budget(latencies, operation, custom_budget)
    
    return results


def format_latency_report(
    results: Dict[OperationType, LatencyGateResult],
    verbose: bool = True
) -> str:
    """
    Format latency gate results as a report.
    
    Args:
        results: Dictionary of latency gate results
        verbose: Include detailed metrics
    
    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("LATENCY BUDGET REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # Summary
    total_checks = len(results)
    passed_checks = sum(1 for r in results.values() if r.passed)
    failed_checks = total_checks - passed_checks
    
    lines.append(f"Total Checks: {total_checks}")
    lines.append(f"Passed: {passed_checks}")
    lines.append(f"Failed: {failed_checks}")
    lines.append("")
    
    # Details
    for operation, result in sorted(results.items(), key=lambda x: x[0].value):
        status = "✅ PASS" if result.passed else "❌ FAIL"
        lines.append(f"{operation.value}: {status}")
        
        if verbose:
            metrics = result.metrics
            lines.append(f"  Count: {metrics.count}")
            lines.append(f"  Mean: {metrics.mean_ms:.1f}ms")
            lines.append(f"  p50: {metrics.p50_ms:.1f}ms")
            lines.append(f"  p95: {metrics.p95_ms:.1f}ms")
            lines.append(f"  Max: {metrics.max_ms:.1f}ms")
            
            if result.budget.p95_ms:
                lines.append(f"  Budget p95: {result.budget.p95_ms:.1f}ms")
            
            if result.violations:
                lines.append(f"  Violations:")
                for violation in result.violations:
                    lines.append(f"    - {violation}")
        
        lines.append("")
    
    return "\n".join(lines)


class LatencyGate:
    """Helper class for managing latency gates in test suites."""
    
    def __init__(self, custom_budgets: Optional[Dict[OperationType, LatencyBudget]] = None):
        """
        Initialize latency gate.
        
        Args:
            custom_budgets: Optional custom budgets (uses standard if None)
        """
        self.custom_budgets = custom_budgets or {}
        self.latencies: Dict[OperationType, List[float]] = {}
        self.results: Dict[OperationType, LatencyGateResult] = {}
    
    def record(self, operation: OperationType, latency_ms: float):
        """Record a latency measurement."""
        if operation not in self.latencies:
            self.latencies[operation] = []
        self.latencies[operation].append(latency_ms)
    
    def record_batch(self, operation: OperationType, latencies_ms: List[float]):
        """Record multiple latency measurements."""
        if operation not in self.latencies:
            self.latencies[operation] = []
        self.latencies[operation].extend(latencies_ms)
    
    def check_budgets(self) -> bool:
        """
        Check all recorded latencies against budgets.
        
        Returns:
            True if all budgets met, False otherwise
        """
        self.results = check_multiple_budgets(self.latencies, self.custom_budgets)
        return all(r.passed for r in self.results.values())
    
    def get_failures(self) -> List[str]:
        """Get list of failure messages."""
        return [r.message for r in self.results.values() if not r.passed]
    
    def get_report(self, verbose: bool = True) -> str:
        """Get formatted report."""
        if not self.results:
            self.check_budgets()
        return format_latency_report(self.results, verbose)
    
    def reset(self):
        """Clear all recorded latencies and results."""
        self.latencies.clear()
        self.results.clear()


def assert_latency_budget(
    latencies: List[float],
    operation: OperationType,
    custom_budget: Optional[LatencyBudget] = None
):
    """
    Assert that latencies meet budget, raising AssertionError if not.
    
    Args:
        latencies: List of latency values
        operation: Operation type
        custom_budget: Optional custom budget
    
    Raises:
        AssertionError: If budget is violated
    """
    result = check_latency_budget(latencies, operation, custom_budget)
    
    if not result.passed:
        violations_text = "\n  ".join(result.violations)
        raise AssertionError(
            f"Latency budget violated for {operation.value}:\n  {violations_text}"
        )


if __name__ == "__main__":
    # Example usage
    print("Latency Budget Gates - Example Usage")
    print("=" * 60)
    print()
    
    # Example 1: Single operation check
    retrieval_latencies = [450, 480, 520, 490, 510]
    result = check_latency_budget(retrieval_latencies, OperationType.RETRIEVAL)
    print(f"Example 1: {result.message}")
    print(f"  Metrics: p95={result.metrics.p95_ms:.1f}ms, max={result.metrics.max_ms:.1f}ms")
    print()
    
    # Example 2: Multiple operations
    latencies_by_op = {
        OperationType.RETRIEVAL: [400, 450, 480, 490, 495],
        OperationType.PACKING: [500, 520, 540, 550, 560],
        OperationType.SCORING: [150, 160, 170, 180, 190]
    }
    
    results = check_multiple_budgets(latencies_by_op)
    print("Example 2: Multiple operations")
    for op, result in results.items():
        print(f"  {result.message}")
    print()
    
    # Example 3: Using LatencyGate helper
    gate = LatencyGate()
    gate.record_batch(OperationType.RETRIEVAL, [400, 450, 480, 490, 495])
    gate.record_batch(OperationType.PACKING, [500, 520, 540, 550, 560])
    
    if gate.check_budgets():
        print("Example 3: ✅ All budgets met")
    else:
        print("Example 3: ❌ Budget violations:")
        for failure in gate.get_failures():
            print(f"  {failure}")
    
    print()
    print(gate.get_report(verbose=False))
