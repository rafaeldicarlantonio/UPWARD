#!/usr/bin/env python3
"""
Unit tests for CI latency gates.

Tests:
1. Gates pass when within budget
2. Gates fail when budget exceeded
3. Slack percentage applied correctly
4. Multiple gate checking
5. Acceptance criteria
"""

import sys
import os
import unittest
from unittest.mock import patch, Mock

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.latency import (
    LatencyGates,
    LatencyBudget,
    SeverityLevel,
    GateResult,
    check_latency_gates
)
from core.metrics import reset_metrics, observe_histogram


class TestLatencyBudget(unittest.TestCase):
    """Test LatencyBudget dataclass."""
    
    def test_budget_creation(self):
        """Test creating a budget."""
        budget = LatencyBudget(
            metric_name="retrieval_ms",
            p95_budget_ms=500.0,
            description="Retrieval p95"
        )
        
        self.assertEqual(budget.metric_name, "retrieval_ms")
        self.assertEqual(budget.p95_budget_ms, 500.0)
        self.assertTrue(budget.enabled_by_default)
    
    def test_budget_with_labels(self):
        """Test budget with metric labels."""
        budget = LatencyBudget(
            metric_name="retrieval_ms",
            p95_budget_ms=500.0,
            description="Retrieval p95",
            labels={"method": "dual"}
        )
        
        self.assertIsNotNone(budget.labels)
        self.assertEqual(budget.labels["method"], "dual")


class TestLatencyGates(unittest.TestCase):
    """Test LatencyGates class."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_gate_passes_within_budget(self):
        """Test gate passes when within budget."""
        # Record values within budget (p95 should be ~450ms)
        for i in range(1, 101):
            if i <= 95:
                observe_histogram("retrieval_ms", 400.0)
            else:
                observe_histogram("retrieval_ms", 450.0)
        
        budget = LatencyBudget(
            metric_name="retrieval_ms",
            p95_budget_ms=500.0,
            description="Retrieval p95"
        )
        
        gates = LatencyGates()
        result = gates.check_gate(budget)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.severity, SeverityLevel.INFO)
        self.assertLessEqual(result.actual_p95, 500.0)
    
    def test_gate_fails_when_exceeded(self):
        """Test gate fails when budget exceeded."""
        # Record values exceeding budget (p95 should be ~600ms)
        for i in range(1, 101):
            if i <= 95:
                observe_histogram("retrieval_ms", 500.0)
            else:
                observe_histogram("retrieval_ms", 600.0)
        
        budget = LatencyBudget(
            metric_name="retrieval_ms",
            p95_budget_ms=500.0,
            description="Retrieval p95"
        )
        
        gates = LatencyGates()
        result = gates.check_gate(budget)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.severity, SeverityLevel.ERROR)
        self.assertGreater(result.actual_p95, 500.0)
    
    def test_gate_with_no_data(self):
        """Test gate with no data returns warning."""
        budget = LatencyBudget(
            metric_name="nonexistent_metric",
            p95_budget_ms=500.0,
            description="Nonexistent metric"
        )
        
        gates = LatencyGates()
        result = gates.check_gate(budget)
        
        self.assertTrue(result.passed)  # Pass with warning
        self.assertEqual(result.severity, SeverityLevel.WARNING)
        self.assertEqual(result.actual_p95, 0.0)


class TestSlackPercentage(unittest.TestCase):
    """Test slack percentage application."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_slack_increases_budget(self):
        """Test slack increases budget allowance."""
        # Record values slightly exceeding base budget (p95 ~525ms)
        for i in range(1, 101):
            if i <= 95:
                observe_histogram("retrieval_ms", 500.0)
            else:
                observe_histogram("retrieval_ms", 525.0)
        
        budget = LatencyBudget(
            metric_name="retrieval_ms",
            p95_budget_ms=500.0,
            description="Retrieval p95"
        )
        
        # Without slack - should fail
        gates_no_slack = LatencyGates(slack_percent=0)
        result_no_slack = gates_no_slack.check_gate(budget)
        self.assertFalse(result_no_slack.passed)
        
        # With 10% slack (budget becomes 550ms) - should pass
        gates_with_slack = LatencyGates(slack_percent=10.0)
        result_with_slack = gates_with_slack.check_gate(budget)
        self.assertTrue(result_with_slack.passed)
        self.assertEqual(result_with_slack.slack_applied_percent, 10.0)
    
    def test_slack_from_env_var(self):
        """Test slack from LATENCY_SLACK_PERCENT env var."""
        with patch.dict(os.environ, {"LATENCY_SLACK_PERCENT": "5"}):
            gates = LatencyGates()
            self.assertEqual(gates.slack_percent, 5.0)
    
    def test_slack_capped_at_10_percent(self):
        """Test slack is capped at 10%."""
        gates = LatencyGates(slack_percent=20.0)  # Try to set 20%
        self.assertEqual(gates.slack_percent, 10.0)  # Capped at 10%


class TestMultipleGates(unittest.TestCase):
    """Test checking multiple gates."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_check_all_gates(self):
        """Test checking multiple gates."""
        # Record metrics for multiple operations
        for _ in range(100):
            observe_histogram("retrieval_ms", 450.0)  # Within budget
            observe_histogram("packing_ms", 600.0)    # Exceeds budget
        
        gates = LatencyGates()
        results = gates.check_all_gates(enabled_gates=["retrieval_ms", "packing_ms"])
        
        self.assertEqual(len(results), 2)
        
        # Retrieval should pass
        retrieval_result = next(r for r in results if r.metric_name == "retrieval_ms")
        self.assertTrue(retrieval_result.passed)
        
        # Packing should fail
        packing_result = next(r for r in results if r.metric_name == "packing_ms")
        self.assertFalse(packing_result.passed)
    
    def test_enabled_gates_filter(self):
        """Test filtering by enabled gates."""
        gates = LatencyGates()
        
        # Check only retrieval_ms
        results = gates.check_all_gates(enabled_gates=["retrieval_ms"])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metric_name, "retrieval_ms")


class TestFailIfExceeded(unittest.TestCase):
    """Test fail_if_exceeded logic."""
    
    def test_returns_true_when_all_pass(self):
        """Test returns True when all gates pass."""
        results = [
            GateResult(
                metric_name="retrieval_ms",
                budget_ms=500.0,
                actual_p95=450.0,
                passed=True,
                severity=SeverityLevel.INFO,
                message="✅ Pass"
            )
        ]
        
        gates = LatencyGates()
        success = gates.fail_if_exceeded(results, exit_on_failure=False)
        
        self.assertTrue(success)
    
    def test_returns_false_when_any_fail(self):
        """Test returns False when any gate fails."""
        results = [
            GateResult(
                metric_name="retrieval_ms",
                budget_ms=500.0,
                actual_p95=450.0,
                passed=True,
                severity=SeverityLevel.INFO,
                message="✅ Pass"
            ),
            GateResult(
                metric_name="packing_ms",
                budget_ms=550.0,
                actual_p95=600.0,
                passed=False,
                severity=SeverityLevel.ERROR,
                message="❌ Fail"
            )
        ]
        
        gates = LatencyGates()
        success = gates.fail_if_exceeded(results, exit_on_failure=False)
        
        self.assertFalse(success)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_simulated_slowdowns_fail_ci(self):
        """Test: simulated slowdowns fail CI with actionable output."""
        # Simulate slow retrieval (p95 ~650ms, exceeds 500ms budget)
        for i in range(1, 101):
            if i <= 95:
                observe_histogram("retrieval_ms", 600.0, labels={"method": "dual"})
            else:
                observe_histogram("retrieval_ms", 650.0, labels={"method": "dual"})
        
        # Simulate slow packing (p95 ~700ms, exceeds 550ms budget)
        for i in range(1, 101):
            if i <= 95:
                observe_histogram("packing_ms", 650.0)
            else:
                observe_histogram("packing_ms", 700.0)
        
        gates = LatencyGates()
        results = gates.check_all_gates(enabled_gates=["retrieval_ms", "packing_ms"])
        
        # ✅ Both gates should fail
        retrieval_result = next(r for r in results if r.metric_name == "retrieval_ms")
        packing_result = next(r for r in results if r.metric_name == "packing_ms")
        
        self.assertFalse(retrieval_result.passed)
        self.assertFalse(packing_result.passed)
        
        # ✅ Should return False (CI would fail)
        success = gates.fail_if_exceeded(results, exit_on_failure=False)
        self.assertFalse(success)
        
        # ✅ Verify actionable messages
        self.assertIn("❌", retrieval_result.message)
        self.assertIn("overage", retrieval_result.message)
    
    def test_env_var_allows_slack_on_nightly(self):
        """Test: env var allows ±10% slack on nightly only."""
        # Simulate retrieval at 525ms (exceeds 500ms, but within 10% slack)
        for i in range(1, 101):
            if i <= 95:
                observe_histogram("retrieval_ms", 500.0, labels={"method": "dual"})
            else:
                observe_histogram("retrieval_ms", 525.0, labels={"method": "dual"})
        
        # ✅ Without slack (PR mode) - should fail
        gates_pr = LatencyGates(slack_percent=0)
        results_pr = gates_pr.check_all_gates(enabled_gates=["retrieval_ms"])
        self.assertFalse(results_pr[0].passed)
        
        # ✅ With 10% slack (nightly mode) - should pass
        # 500ms * 1.10 = 550ms, and p95 is ~525ms
        gates_nightly = LatencyGates(slack_percent=10.0)
        results_nightly = gates_nightly.check_all_gates(enabled_gates=["retrieval_ms"])
        self.assertTrue(results_nightly[0].passed)
        
        # ✅ Verify slack is applied
        self.assertEqual(results_nightly[0].slack_applied_percent, 10.0)
    
    def test_all_budgets_enforced(self):
        """Test: all required budgets are enforced."""
        gates = LatencyGates()
        
        # ✅ Verify all required budgets exist
        budget_names = [b.metric_name for b in gates.budgets]
        
        self.assertIn("retrieval_ms", budget_names)
        self.assertIn("packing_ms", budget_names)
        self.assertIn("reviewer_ms", budget_names)
        self.assertIn("chat_total_ms", budget_names)
        
        # ✅ Verify budget values
        retrieval_budget = next(b for b in gates.budgets if b.metric_name == "retrieval_ms")
        packing_budget = next(b for b in gates.budgets if b.metric_name == "packing_ms")
        reviewer_budget = next(b for b in gates.budgets if b.metric_name == "reviewer_ms")
        chat_budget = next(b for b in gates.budgets if b.metric_name == "chat_total_ms")
        
        self.assertEqual(retrieval_budget.p95_budget_ms, 500.0)
        self.assertEqual(packing_budget.p95_budget_ms, 550.0)
        self.assertEqual(reviewer_budget.p95_budget_ms, 500.0)
        self.assertEqual(chat_budget.p95_budget_ms, 1200.0)
    
    def test_clear_failure_messages(self):
        """Test: clear failure messages with actionable guidance."""
        # Simulate slow operation
        for _ in range(100):
            observe_histogram("retrieval_ms", 650.0, labels={"method": "dual"})
        
        gates = LatencyGates()
        results = gates.check_all_gates(enabled_gates=["retrieval_ms"])
        
        result = results[0]
        
        # ✅ Verify message clarity
        self.assertIn("❌", result.message)  # Failure indicator
        self.assertIn("ms", result.message)  # Shows actual latency
        self.assertIn("budget", result.message)  # Shows budget
        self.assertIn("overage", result.message)  # Shows how much exceeded
        
        # ✅ Verify actionable output would be shown
        # (fail_if_exceeded prints actionable steps to stderr)
        success = gates.fail_if_exceeded(results, exit_on_failure=False)
        self.assertFalse(success)


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_check_latency_gates_function(self):
        """Test check_latency_gates convenience function."""
        # Record passing metrics
        for _ in range(100):
            observe_histogram("retrieval_ms", 450.0, labels={"method": "dual"})
        
        success = check_latency_gates(
            enabled_gates=["retrieval_ms"],
            exit_on_failure=False
        )
        
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
