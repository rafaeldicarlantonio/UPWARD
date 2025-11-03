#!/usr/bin/env python3
"""
Latency budget gates for evaluation suites.

Defines budget thresholds and helpers to validate latencies across different
operations: retrieval, packing, internal compare, external compare.

Budgets:
- Retrieval p95 ≤ 500ms
- Packing p95 ≤ 550ms
- Internal compare p95 ≤ 400ms
- External compare p95 ≤ 2000ms (with timeouts)
"""

import statistics
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class LatencyBudget(Enum):
    """Latency budget thresholds in milliseconds."""
    RETRIEVAL_P95 = 500
    PACKING_P95 = 550
    INTERNAL_COMPARE_P95 = 400
    EXTERNAL_COMPARE_P95 = 2000
    
    # Additional thresholds
    RETRIEVAL_P99 = 800
    PACKING_P99 = 800
    TOTAL_P95 = 1500  # Total end-to-end latency


@dataclass
class LatencyViolation:
    """Represents a latency budget violation."""
    operation: str
    metric: str  # e.g., "p95", "p99", "max"
    measured: float  # measured latency in ms
    budget: float  # budget threshold in ms
    excess: float  # amount over budget
    count: int  # number of samples
    
    def __str__(self) -> str:
        """Human-readable violation message."""
        return (
            f"{self.operation} {self.metric} latency {self.measured:.1f}ms "
            f"exceeds budget {self.budget:.0f}ms by {self.excess:.1f}ms "
            f"({self.count} samples)"
        )


@dataclass
class LatencyGateResult:
    """Result of latency gate validation."""
    passed: bool
    violations: List[LatencyViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """Human-readable result summary."""
        if self.passed:
            return "✅ All latency budgets passed"
        else:
            lines = ["❌ Latency budget violations:"]
            for violation in self.violations:
                lines.append(f"  • {violation}")
            return "\n".join(lines)


class LatencyGate:
    """
    Latency budget gate for validating operation latencies.
    
    Computes percentiles and checks against configured budgets.
    """
    
    def __init__(self, budgets: Optional[Dict[str, float]] = None):
        """
        Initialize latency gate.
        
        Args:
            budgets: Optional custom budget overrides (operation -> ms)
        """
        self.budgets = budgets or {}
        self._default_budgets = {
            "retrieval": LatencyBudget.RETRIEVAL_P95.value,
            "packing": LatencyBudget.PACKING_P95.value,
            "internal_compare": LatencyBudget.INTERNAL_COMPARE_P95.value,
            "external_compare": LatencyBudget.EXTERNAL_COMPARE_P95.value,
        }
    
    def get_budget(self, operation: str) -> float:
        """Get budget for operation (custom or default)."""
        return self.budgets.get(operation, self._default_budgets.get(operation, 1000.0))
    
    def validate_retrieval(
        self,
        latencies: List[float],
        budget: Optional[float] = None
    ) -> LatencyGateResult:
        """
        Validate retrieval latencies against budget.
        
        Args:
            latencies: List of retrieval latency measurements (ms)
            budget: Optional budget override (default: 500ms p95)
        
        Returns:
            LatencyGateResult with pass/fail and violations
        """
        return self._validate_operation(
            operation="retrieval",
            latencies=latencies,
            budget=budget or self.get_budget("retrieval"),
            percentile=95
        )
    
    def validate_packing(
        self,
        latencies: List[float],
        budget: Optional[float] = None
    ) -> LatencyGateResult:
        """
        Validate packing latencies against budget.
        
        Args:
            latencies: List of packing latency measurements (ms)
            budget: Optional budget override (default: 550ms p95)
        
        Returns:
            LatencyGateResult with pass/fail and violations
        """
        return self._validate_operation(
            operation="packing",
            latencies=latencies,
            budget=budget or self.get_budget("packing"),
            percentile=95
        )
    
    def validate_internal_compare(
        self,
        latencies: List[float],
        budget: Optional[float] = None
    ) -> LatencyGateResult:
        """
        Validate internal compare latencies against budget.
        
        Args:
            latencies: List of internal compare latency measurements (ms)
            budget: Optional budget override (default: 400ms p95)
        
        Returns:
            LatencyGateResult with pass/fail and violations
        """
        return self._validate_operation(
            operation="internal_compare",
            latencies=latencies,
            budget=budget or self.get_budget("internal_compare"),
            percentile=95
        )
    
    def validate_external_compare(
        self,
        latencies: List[float],
        budget: Optional[float] = None
    ) -> LatencyGateResult:
        """
        Validate external compare latencies against budget.
        
        Args:
            latencies: List of external compare latency measurements (ms)
            budget: Optional budget override (default: 2000ms p95)
        
        Returns:
            LatencyGateResult with pass/fail and violations
        """
        return self._validate_operation(
            operation="external_compare",
            latencies=latencies,
            budget=budget or self.get_budget("external_compare"),
            percentile=95
        )
    
    def validate_all(
        self,
        retrieval_latencies: List[float],
        packing_latencies: List[float],
        internal_compare_latencies: Optional[List[float]] = None,
        external_compare_latencies: Optional[List[float]] = None
    ) -> LatencyGateResult:
        """
        Validate all operation latencies against budgets.
        
        Args:
            retrieval_latencies: Retrieval latency measurements
            packing_latencies: Packing latency measurements
            internal_compare_latencies: Optional internal compare measurements
            external_compare_latencies: Optional external compare measurements
        
        Returns:
            Combined LatencyGateResult for all operations
        """
        all_violations = []
        all_warnings = []
        all_metrics = {}
        
        # Validate retrieval
        if retrieval_latencies:
            result = self.validate_retrieval(retrieval_latencies)
            all_violations.extend(result.violations)
            all_warnings.extend(result.warnings)
            all_metrics["retrieval"] = result.metrics
        
        # Validate packing
        if packing_latencies:
            result = self.validate_packing(packing_latencies)
            all_violations.extend(result.violations)
            all_warnings.extend(result.warnings)
            all_metrics["packing"] = result.metrics
        
        # Validate internal compare
        if internal_compare_latencies:
            result = self.validate_internal_compare(internal_compare_latencies)
            all_violations.extend(result.violations)
            all_warnings.extend(result.warnings)
            all_metrics["internal_compare"] = result.metrics
        
        # Validate external compare
        if external_compare_latencies:
            result = self.validate_external_compare(external_compare_latencies)
            all_violations.extend(result.violations)
            all_warnings.extend(result.warnings)
            all_metrics["external_compare"] = result.metrics
        
        return LatencyGateResult(
            passed=len(all_violations) == 0,
            violations=all_violations,
            warnings=all_warnings,
            metrics=all_metrics
        )
    
    def _validate_operation(
        self,
        operation: str,
        latencies: List[float],
        budget: float,
        percentile: int = 95
    ) -> LatencyGateResult:
        """
        Internal helper to validate operation latencies.
        
        Args:
            operation: Operation name (e.g., "retrieval")
            latencies: List of latency measurements (ms)
            budget: Budget threshold (ms)
            percentile: Percentile to check (default: 95)
        
        Returns:
            LatencyGateResult
        """
        if not latencies:
            return LatencyGateResult(
                passed=True,
                warnings=[f"No {operation} latencies to validate"],
                metrics={}
            )
        
        # Compute percentiles
        metrics = self._compute_percentiles(latencies)
        
        # Check p95 against budget
        p_key = f"p{percentile}"
        measured = metrics[p_key]
        
        violations = []
        warnings = []
        
        if measured > budget:
            excess = measured - budget
            violation = LatencyViolation(
                operation=operation,
                metric=p_key,
                measured=measured,
                budget=budget,
                excess=excess,
                count=len(latencies)
            )
            violations.append(violation)
        
        # Check for warning conditions
        # Warn if p50 is close to budget (within 20%)
        if metrics["p50"] > budget * 0.8:
            warnings.append(
                f"{operation} p50 ({metrics['p50']:.1f}ms) is close to "
                f"p95 budget ({budget:.0f}ms)"
            )
        
        # Warn if max is significantly over budget
        if metrics["max"] > budget * 2:
            warnings.append(
                f"{operation} max latency ({metrics['max']:.1f}ms) is "
                f"significantly over budget ({budget:.0f}ms)"
            )
        
        return LatencyGateResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            metrics=metrics
        )
    
    @staticmethod
    def _compute_percentiles(latencies: List[float]) -> Dict[str, float]:
        """
        Compute latency percentiles.
        
        Args:
            latencies: List of latency measurements
        
        Returns:
            Dictionary with p50, p90, p95, p99, max, avg
        """
        if not latencies:
            return {
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "count": 0
            }
        
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        return {
            "p50": sorted_latencies[int(n * 0.50)] if n > 1 else sorted_latencies[0],
            "p90": sorted_latencies[int(n * 0.90)] if n > 1 else sorted_latencies[0],
            "p95": sorted_latencies[int(n * 0.95)] if n > 1 else sorted_latencies[0],
            "p99": sorted_latencies[int(n * 0.99)] if n > 1 else sorted_latencies[0],
            "max": max(latencies),
            "avg": statistics.mean(latencies),
            "count": n
        }


def check_latency_budgets(
    results: List[Any],
    gate: Optional[LatencyGate] = None
) -> LatencyGateResult:
    """
    Check latency budgets for a list of evaluation results.
    
    Extracts latencies from results and validates against budgets.
    
    Args:
        results: List of EvalResult objects
        gate: Optional LatencyGate instance (creates default if None)
    
    Returns:
        LatencyGateResult with validation status
    """
    if gate is None:
        gate = LatencyGate()
    
    # Extract latencies by operation type
    retrieval_latencies = []
    packing_latencies = []
    internal_compare_latencies = []
    external_compare_latencies = []
    
    for result in results:
        # Retrieval latencies
        if hasattr(result, 'retrieval_latency_ms') and result.retrieval_latency_ms > 0:
            retrieval_latencies.append(result.retrieval_latency_ms)
        
        # Packing latencies
        if hasattr(result, 'packing_latency_ms') and result.packing_latency_ms > 0:
            packing_latencies.append(result.packing_latency_ms)
        
        # Compare latencies (categorize by type)
        if hasattr(result, 'category'):
            if result.category == "internal_compare" and hasattr(result, 'latency_ms'):
                internal_compare_latencies.append(result.latency_ms)
            elif result.category == "external_compare" and hasattr(result, 'latency_ms'):
                external_compare_latencies.append(result.latency_ms)
    
    # Validate all
    return gate.validate_all(
        retrieval_latencies=retrieval_latencies,
        packing_latencies=packing_latencies,
        internal_compare_latencies=internal_compare_latencies if internal_compare_latencies else None,
        external_compare_latencies=external_compare_latencies if external_compare_latencies else None
    )


def format_latency_report(result: LatencyGateResult) -> str:
    """
    Format latency gate result as human-readable report.
    
    Args:
        result: LatencyGateResult to format
    
    Returns:
        Formatted report string
    """
    lines = []
    
    # Status
    if result.passed:
        lines.append("✅ LATENCY BUDGETS: PASSED")
    else:
        lines.append("❌ LATENCY BUDGETS: FAILED")
    
    lines.append("")
    
    # Metrics
    if result.metrics:
        lines.append("Latency Metrics:")
        for operation, metrics in result.metrics.items():
            if isinstance(metrics, dict):
                lines.append(f"  {operation}:")
                lines.append(f"    p50: {metrics.get('p50', 0):.1f}ms")
                lines.append(f"    p95: {metrics.get('p95', 0):.1f}ms")
                lines.append(f"    p99: {metrics.get('p99', 0):.1f}ms")
                lines.append(f"    max: {metrics.get('max', 0):.1f}ms")
                lines.append(f"    avg: {metrics.get('avg', 0):.1f}ms")
                lines.append(f"    count: {metrics.get('count', 0)}")
        lines.append("")
    
    # Violations
    if result.violations:
        lines.append("Budget Violations:")
        for violation in result.violations:
            lines.append(f"  ❌ {violation}")
        lines.append("")
    
    # Warnings
    if result.warnings:
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  ⚠️  {warning}")
        lines.append("")
    
    return "\n".join(lines)


# Convenience functions for common checks
def assert_retrieval_budget(latencies: List[float], budget: float = 500) -> None:
    """Assert retrieval latencies are under budget (raises on failure)."""
    gate = LatencyGate()
    result = gate.validate_retrieval(latencies, budget=budget)
    if not result.passed:
        raise AssertionError(str(result))


def assert_packing_budget(latencies: List[float], budget: float = 550) -> None:
    """Assert packing latencies are under budget (raises on failure)."""
    gate = LatencyGate()
    result = gate.validate_packing(latencies, budget=budget)
    if not result.passed:
        raise AssertionError(str(result))


def assert_internal_compare_budget(latencies: List[float], budget: float = 400) -> None:
    """Assert internal compare latencies are under budget (raises on failure)."""
    gate = LatencyGate()
    result = gate.validate_internal_compare(latencies, budget=budget)
    if not result.passed:
        raise AssertionError(str(result))


def assert_external_compare_budget(latencies: List[float], budget: float = 2000) -> None:
    """Assert external compare latencies are under budget (raises on failure)."""
    gate = LatencyGate()
    result = gate.validate_external_compare(latencies, budget=budget)
    if not result.passed:
        raise AssertionError(str(result))


if __name__ == "__main__":
    # Example usage
    print("Latency Budget Gates - Example Usage")
    print("=" * 60)
    
    # Simulate some latencies
    retrieval_latencies = [200, 250, 300, 350, 400, 450, 480]
    packing_latencies = [100, 150, 200, 250, 300]
    
    # Create gate
    gate = LatencyGate()
    
    # Validate retrieval
    result = gate.validate_retrieval(retrieval_latencies)
    print(format_latency_report(result))
    
    # Simulate over-budget scenario
    print("\nSimulating over-budget retrieval:")
    slow_retrieval = [400, 500, 550, 600, 650, 700, 750]
    result = gate.validate_retrieval(slow_retrieval)
    print(format_latency_report(result))
