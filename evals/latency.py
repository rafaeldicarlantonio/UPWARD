#!/usr/bin/env python3
"""
evals/latency.py — Latency gates for CI/CD.

Enforces performance SLOs by checking p95 latencies against budgets.
Fails CI when budgets are exceeded with actionable error messages.

Budgets:
- retrieval p95 ≤ 500ms (dual-index)
- packing p95 ≤ 550ms
- reviewer p95 ≤ 500ms (when enabled)
- overall /chat p95 ≤ 1200ms

Supports ±10% slack via LATENCY_SLACK_PERCENT env var for nightly runs.
"""

import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Add workspace to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.metrics import get_histogram_stats


class SeverityLevel(Enum):
    """Severity level for gate violations."""
    ERROR = "error"      # Hard failure (CI fails)
    WARNING = "warning"  # Soft failure (CI passes with warning)
    INFO = "info"        # Informational only


@dataclass
class LatencyBudget:
    """Definition of a latency budget."""
    metric_name: str           # Metric to check (e.g., "retrieval_ms")
    p95_budget_ms: float       # p95 budget in milliseconds
    description: str           # Human-readable description
    labels: Optional[Dict[str, str]] = None  # Optional metric labels
    enabled_by_default: bool = True          # Whether gate is enabled by default


@dataclass
class GateResult:
    """Result of a latency gate check."""
    metric_name: str
    budget_ms: float
    actual_p95: float
    passed: bool
    severity: SeverityLevel
    message: str
    slack_applied_percent: float = 0.0


class LatencyGates:
    """
    Latency gate checker for CI/CD.
    
    Checks p95 latencies against defined budgets and fails CI
    when budgets are exceeded.
    """
    
    # Default latency budgets
    DEFAULT_BUDGETS = [
        LatencyBudget(
            metric_name="retrieval_ms",
            p95_budget_ms=500.0,
            description="Retrieval (dual-index) p95",
            labels={"method": "dual"}
        ),
        LatencyBudget(
            metric_name="graph_expand_ms",
            p95_budget_ms=200.0,
            description="Graph expansion p95"
        ),
        LatencyBudget(
            metric_name="packing_ms",
            p95_budget_ms=550.0,
            description="Context packing p95"
        ),
        LatencyBudget(
            metric_name="reviewer_ms",
            p95_budget_ms=500.0,
            description="Reviewer call p95",
            enabled_by_default=False  # Only when reviewer is enabled
        ),
        LatencyBudget(
            metric_name="chat_total_ms",
            p95_budget_ms=1200.0,
            description="Overall /chat endpoint p95"
        ),
    ]
    
    def __init__(
        self,
        budgets: Optional[List[LatencyBudget]] = None,
        slack_percent: Optional[float] = None
    ):
        """
        Initialize latency gates.
        
        Args:
            budgets: Optional custom budgets (defaults to DEFAULT_BUDGETS)
            slack_percent: Optional slack percentage (0-100) to add to budgets
                          (default: from LATENCY_SLACK_PERCENT env var or 0)
        """
        self.budgets = budgets or self.DEFAULT_BUDGETS.copy()
        
        # Get slack from env var if not provided
        if slack_percent is None:
            slack_percent = float(os.getenv("LATENCY_SLACK_PERCENT", "0"))
        
        self.slack_percent = max(0.0, min(slack_percent, 10.0))  # Cap at 10%
    
    def check_gate(self, budget: LatencyBudget) -> GateResult:
        """
        Check a single latency gate.
        
        Args:
            budget: Budget to check
            
        Returns:
            GateResult with pass/fail status and details
        """
        # Get histogram stats
        stats = get_histogram_stats(budget.metric_name, labels=budget.labels)
        
        actual_p95 = stats.get("p95", 0.0)
        count = stats.get("count", 0)
        
        # Apply slack to budget
        adjusted_budget = budget.p95_budget_ms * (1.0 + self.slack_percent / 100.0)
        
        # Check if gate passes
        if count == 0:
            # No data - treat as pass with warning
            return GateResult(
                metric_name=budget.metric_name,
                budget_ms=budget.p95_budget_ms,
                actual_p95=0.0,
                passed=True,
                severity=SeverityLevel.WARNING,
                message=f"⚠️  {budget.description}: No data (count=0)",
                slack_applied_percent=self.slack_percent
            )
        
        passed = actual_p95 <= adjusted_budget
        
        if passed:
            message = (
                f"✅ {budget.description}: "
                f"{actual_p95:.1f}ms ≤ {adjusted_budget:.1f}ms "
                f"(budget: {budget.p95_budget_ms:.0f}ms"
            )
            if self.slack_percent > 0:
                message += f", +{self.slack_percent}% slack"
            message += f", count: {count})"
            
            severity = SeverityLevel.INFO
        else:
            overage = actual_p95 - adjusted_budget
            overage_percent = (overage / adjusted_budget) * 100.0
            
            message = (
                f"❌ {budget.description}: "
                f"{actual_p95:.1f}ms > {adjusted_budget:.1f}ms "
                f"(budget: {budget.p95_budget_ms:.0f}ms"
            )
            if self.slack_percent > 0:
                message += f", +{self.slack_percent}% slack"
            message += f", overage: +{overage:.1f}ms / +{overage_percent:.1f}%, count: {count})"
            
            severity = SeverityLevel.ERROR
        
        return GateResult(
            metric_name=budget.metric_name,
            budget_ms=budget.p95_budget_ms,
            actual_p95=actual_p95,
            passed=passed,
            severity=severity,
            message=message,
            slack_applied_percent=self.slack_percent
        )
    
    def check_all_gates(
        self,
        enabled_gates: Optional[List[str]] = None
    ) -> List[GateResult]:
        """
        Check all configured latency gates.
        
        Args:
            enabled_gates: Optional list of metric names to check
                          (default: all enabled_by_default budgets)
            
        Returns:
            List of GateResults
        """
        results = []
        
        for budget in self.budgets:
            # Skip if not in enabled_gates list (when provided)
            if enabled_gates is not None:
                if budget.metric_name not in enabled_gates:
                    continue
            else:
                # Use enabled_by_default
                if not budget.enabled_by_default:
                    continue
            
            result = self.check_gate(budget)
            results.append(result)
        
        return results
    
    def print_results(self, results: List[GateResult], verbose: bool = True):
        """
        Print gate results to stdout.
        
        Args:
            results: List of GateResults to print
            verbose: Whether to print all results or only failures
        """
        print("\n" + "="*80)
        print("LATENCY GATE RESULTS")
        print("="*80)
        
        if self.slack_percent > 0:
            print(f"ℹ️  Slack applied: +{self.slack_percent}% to all budgets")
            print()
        
        # Print results
        for result in results:
            if verbose or result.severity == SeverityLevel.ERROR:
                print(result.message)
        
        print()
        
        # Summary
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        
        print(f"Summary: {passed}/{total} gates passed")
        
        if failed > 0:
            print(f"⚠️  {failed} gate(s) failed")
        else:
            print("✅ All gates passed")
        
        print("="*80 + "\n")
    
    def fail_if_exceeded(
        self,
        results: List[GateResult],
        exit_on_failure: bool = True
    ) -> bool:
        """
        Check if any gates failed and optionally exit.
        
        Args:
            results: List of GateResults to check
            exit_on_failure: Whether to sys.exit(1) on failure
            
        Returns:
            True if all gates passed, False otherwise
        """
        failed_results = [r for r in results if not r.passed and r.severity == SeverityLevel.ERROR]
        
        if failed_results:
            print("\n❌ LATENCY GATES FAILED\n", file=sys.stderr)
            print("The following latency budgets were exceeded:\n", file=sys.stderr)
            
            for result in failed_results:
                print(f"  • {result.message}", file=sys.stderr)
            
            print("\nActionable steps:", file=sys.stderr)
            print("  1. Review recent changes that may have impacted performance", file=sys.stderr)
            print("  2. Profile slow operations to identify bottlenecks", file=sys.stderr)
            print("  3. Consider optimizing hot paths or adding caching", file=sys.stderr)
            print("  4. If budgets are unrealistic, update them in evals/latency.py\n", file=sys.stderr)
            
            if exit_on_failure:
                sys.exit(1)
            
            return False
        
        return True


def check_latency_gates(
    slack_percent: Optional[float] = None,
    enabled_gates: Optional[List[str]] = None,
    verbose: bool = True,
    exit_on_failure: bool = True
) -> bool:
    """
    Convenience function to check latency gates.
    
    Args:
        slack_percent: Optional slack percentage (0-10)
        enabled_gates: Optional list of metric names to check
        verbose: Whether to print all results
        exit_on_failure: Whether to exit on failure
        
    Returns:
        True if all gates passed, False otherwise
    """
    gates = LatencyGates(slack_percent=slack_percent)
    results = gates.check_all_gates(enabled_gates=enabled_gates)
    gates.print_results(results, verbose=verbose)
    return gates.fail_if_exceeded(results, exit_on_failure=exit_on_failure)


if __name__ == "__main__":
    """
    CLI entry point for latency gate checks.
    
    Usage:
        python evals/latency.py                    # Check all gates
        python evals/latency.py --slack 10         # Apply 10% slack
        LATENCY_SLACK_PERCENT=5 python evals/latency.py  # Via env var
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Check latency gates")
    parser.add_argument(
        "--slack",
        type=float,
        default=None,
        help="Slack percentage to apply to budgets (0-10)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Print all results (default: True)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print failures"
    )
    parser.add_argument(
        "--gates",
        nargs="+",
        help="Specific gates to check (default: all enabled)"
    )
    
    args = parser.parse_args()
    
    success = check_latency_gates(
        slack_percent=args.slack,
        enabled_gates=args.gates,
        verbose=not args.quiet,
        exit_on_failure=True
    )
    
    sys.exit(0 if success else 1)
