#!/usr/bin/env python3
"""
Unit tests for latency budget gates.

Tests verify:
1. Budget thresholds are correctly defined
2. Validation correctly identifies violations
3. Over-budget scenarios produce failure messages
4. Integration with eval harness marks suite as failed
5. Different operation types have correct budgets
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.latency import (
    LatencyBudget,
    LatencyViolation,
    LatencyGateResult,
    LatencyGate,
    check_latency_budgets,
    format_latency_report,
    assert_retrieval_budget,
    assert_packing_budget,
    assert_internal_compare_budget,
    assert_external_compare_budget
)


class TestLatencyBudgetConstants(unittest.TestCase):
    """Test latency budget constant definitions."""
    
    def test_retrieval_budget(self):
        """Test retrieval budget is 500ms."""
        self.assertEqual(LatencyBudget.RETRIEVAL_P95.value, 500)
    
    def test_packing_budget(self):
        """Test packing budget is 550ms."""
        self.assertEqual(LatencyBudget.PACKING_P95.value, 550)
    
    def test_internal_compare_budget(self):
        """Test internal compare budget is 400ms."""
        self.assertEqual(LatencyBudget.INTERNAL_COMPARE_P95.value, 400)
    
    def test_external_compare_budget(self):
        """Test external compare budget is 2000ms."""
        self.assertEqual(LatencyBudget.EXTERNAL_COMPARE_P95.value, 2000)


class TestLatencyViolation(unittest.TestCase):
    """Test latency violation representation."""
    
    def test_violation_creation(self):
        """Test creating a latency violation."""
        violation = LatencyViolation(
            operation="retrieval",
            metric="p95",
            measured=650.0,
            budget=500.0,
            excess=150.0,
            count=10
        )
        
        self.assertEqual(violation.operation, "retrieval")
        self.assertEqual(violation.metric, "p95")
        self.assertEqual(violation.measured, 650.0)
        self.assertEqual(violation.budget, 500.0)
        self.assertEqual(violation.excess, 150.0)
    
    def test_violation_string(self):
        """Test violation string representation."""
        violation = LatencyViolation(
            operation="packing",
            metric="p95",
            measured=600.0,
            budget=550.0,
            excess=50.0,
            count=5
        )
        
        msg = str(violation)
        self.assertIn("packing", msg)
        self.assertIn("p95", msg)
        self.assertIn("600", msg)
        self.assertIn("550", msg)
        self.assertIn("50", msg)


class TestLatencyGateResult(unittest.TestCase):
    """Test latency gate result."""
    
    def test_passed_result(self):
        """Test passed result."""
        result = LatencyGateResult(passed=True, violations=[], warnings=[])
        
        self.assertTrue(result.passed)
        self.assertEqual(len(result.violations), 0)
        
        msg = str(result)
        self.assertIn("passed", msg.lower())
    
    def test_failed_result(self):
        """Test failed result with violations."""
        violation = LatencyViolation(
            operation="retrieval",
            metric="p95",
            measured=600.0,
            budget=500.0,
            excess=100.0,
            count=10
        )
        
        result = LatencyGateResult(
            passed=False,
            violations=[violation],
            warnings=[]
        )
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 1)
        
        msg = str(result)
        self.assertIn("violation", msg.lower())


class TestLatencyGate(unittest.TestCase):
    """Test latency gate validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.gate = LatencyGate()
    
    def test_retrieval_under_budget(self):
        """Test retrieval latencies under budget pass."""
        latencies = [200, 250, 300, 350, 400, 450, 480]
        result = self.gate.validate_retrieval(latencies)
        
        self.assertTrue(result.passed)
        self.assertEqual(len(result.violations), 0)
    
    def test_retrieval_over_budget(self):
        """Test retrieval latencies over budget fail."""
        # p95 will be ~700ms, over 500ms budget
        latencies = [400, 500, 550, 600, 650, 700, 750]
        result = self.gate.validate_retrieval(latencies)
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 1)
        
        violation = result.violations[0]
        self.assertEqual(violation.operation, "retrieval")
        self.assertGreater(violation.measured, 500)
    
    def test_packing_under_budget(self):
        """Test packing latencies under budget pass."""
        latencies = [100, 150, 200, 250, 300, 400, 500]
        result = self.gate.validate_packing(latencies)
        
        self.assertTrue(result.passed)
    
    def test_packing_over_budget(self):
        """Test packing latencies over budget fail."""
        # p95 will be ~800ms, over 550ms budget
        latencies = [500, 600, 650, 700, 750, 800, 850]
        result = self.gate.validate_packing(latencies)
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 1)
        
        violation = result.violations[0]
        self.assertEqual(violation.operation, "packing")
        self.assertGreater(violation.measured, 550)
    
    def test_internal_compare_under_budget(self):
        """Test internal compare under budget."""
        latencies = [100, 150, 200, 250, 300, 350, 380]
        result = self.gate.validate_internal_compare(latencies)
        
        self.assertTrue(result.passed)
    
    def test_internal_compare_over_budget(self):
        """Test internal compare over budget fails."""
        # p95 will be ~550ms, over 400ms budget
        latencies = [300, 400, 450, 500, 520, 540, 550]
        result = self.gate.validate_internal_compare(latencies)
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 1)
    
    def test_external_compare_under_budget(self):
        """Test external compare under budget."""
        latencies = [500, 800, 1000, 1200, 1500, 1800, 1900]
        result = self.gate.validate_external_compare(latencies)
        
        self.assertTrue(result.passed)
    
    def test_external_compare_over_budget(self):
        """Test external compare over budget fails."""
        # p95 will be ~2800ms, over 2000ms budget
        latencies = [1500, 2000, 2200, 2500, 2600, 2800, 3000]
        result = self.gate.validate_external_compare(latencies)
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 1)
    
    def test_custom_budget(self):
        """Test custom budget override."""
        latencies = [200, 250, 300, 350, 400]
        
        # Should pass with 500ms budget
        result = self.gate.validate_retrieval(latencies, budget=500)
        self.assertTrue(result.passed)
        
        # Should fail with 300ms budget
        result = self.gate.validate_retrieval(latencies, budget=300)
        self.assertFalse(result.passed)
    
    def test_empty_latencies(self):
        """Test validation with empty latencies."""
        result = self.gate.validate_retrieval([])
        
        self.assertTrue(result.passed)
        self.assertGreater(len(result.warnings), 0)
    
    def test_validate_all_operations(self):
        """Test validating all operations together."""
        retrieval_good = [200, 250, 300, 350, 400]
        packing_good = [100, 150, 200, 250, 300]
        internal_good = [150, 200, 250, 300, 350]
        
        result = self.gate.validate_all(
            retrieval_latencies=retrieval_good,
            packing_latencies=packing_good,
            internal_compare_latencies=internal_good,
            external_compare_latencies=None
        )
        
        self.assertTrue(result.passed)
        self.assertEqual(len(result.violations), 0)
    
    def test_validate_all_with_violations(self):
        """Test validating all with some violations."""
        retrieval_bad = [500, 600, 650, 700, 750]  # Over budget
        packing_good = [100, 150, 200, 250, 300]
        
        result = self.gate.validate_all(
            retrieval_latencies=retrieval_bad,
            packing_latencies=packing_good
        )
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].operation, "retrieval")


class TestSlowPathSimulation(unittest.TestCase):
    """Test simulated slow paths produce correct failures."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.gate = LatencyGate()
    
    def test_simulate_slow_retrieval(self):
        """Simulate slow retrieval path."""
        # Simulate 20 requests where 2 are very slow
        latencies = [200] * 18 + [800, 900]  # p95 will be 800+
        
        result = self.gate.validate_retrieval(latencies)
        
        self.assertFalse(result.passed, "Slow retrieval should fail")
        self.assertGreater(len(result.violations), 0)
        
        violation = result.violations[0]
        self.assertGreater(violation.measured, 500, "Measured should exceed 500ms")
        self.assertGreater(violation.excess, 0, "Should have positive excess")
    
    def test_simulate_slow_packing(self):
        """Simulate slow packing path."""
        # Simulate packing taking too long
        latencies = [300] * 18 + [700, 800]  # p95 will be 700+
        
        result = self.gate.validate_packing(latencies)
        
        self.assertFalse(result.passed, "Slow packing should fail")
        
        violation = result.violations[0]
        self.assertEqual(violation.operation, "packing")
        self.assertGreater(violation.measured, 550)
    
    def test_simulate_slow_internal_compare(self):
        """Simulate slow internal compare."""
        latencies = [200] * 18 + [500, 600]  # p95 will be 500+
        
        result = self.gate.validate_internal_compare(latencies)
        
        self.assertFalse(result.passed, "Slow internal compare should fail")
        
        violation = result.violations[0]
        self.assertEqual(violation.operation, "internal_compare")
        self.assertGreater(violation.measured, 400)
    
    def test_simulate_timeout_external_compare(self):
        """Simulate external compare timeout."""
        # Simulate some requests timing out at 2.5s
        latencies = [1000] * 18 + [2500, 2800]  # p95 will be 2500+
        
        result = self.gate.validate_external_compare(latencies)
        
        self.assertFalse(result.passed, "Timeout external compare should fail")
        
        violation = result.violations[0]
        self.assertGreater(violation.measured, 2000)
    
    def test_failure_message_format(self):
        """Test that failure messages are descriptive."""
        latencies = [600, 650, 700, 750, 800]
        result = self.gate.validate_retrieval(latencies)
        
        self.assertFalse(result.passed)
        
        violation = result.violations[0]
        message = str(violation)
        
        # Should contain key information
        self.assertIn("retrieval", message)
        self.assertIn("p95", message)
        self.assertIn("exceeds", message)
        self.assertIn("500", message)  # Budget
        self.assertIn(str(len(latencies)), message)  # Sample count


class TestAssertionHelpers(unittest.TestCase):
    """Test assertion helper functions."""
    
    def test_assert_retrieval_budget_passes(self):
        """Test assertion helper passes for good latencies."""
        latencies = [200, 250, 300, 350, 400]
        
        # Should not raise
        assert_retrieval_budget(latencies)
    
    def test_assert_retrieval_budget_fails(self):
        """Test assertion helper raises for bad latencies."""
        latencies = [500, 600, 650, 700, 750]
        
        with self.assertRaises(AssertionError) as cm:
            assert_retrieval_budget(latencies)
        
        # Check error message
        error_msg = str(cm.exception)
        self.assertIn("retrieval", error_msg.lower())
        self.assertIn("exceeds", error_msg.lower())
    
    def test_assert_packing_budget_fails(self):
        """Test packing assertion fails."""
        latencies = [600, 650, 700, 750, 800]
        
        with self.assertRaises(AssertionError):
            assert_packing_budget(latencies)
    
    def test_assert_internal_compare_budget_fails(self):
        """Test internal compare assertion fails."""
        latencies = [450, 500, 520, 540, 550]
        
        with self.assertRaises(AssertionError):
            assert_internal_compare_budget(latencies)
    
    def test_assert_external_compare_budget_fails(self):
        """Test external compare assertion fails."""
        latencies = [2200, 2400, 2500, 2600, 2800]
        
        with self.assertRaises(AssertionError):
            assert_external_compare_budget(latencies)


class TestCheckLatencyBudgets(unittest.TestCase):
    """Test check_latency_budgets helper."""
    
    def test_check_with_eval_results(self):
        """Test checking budgets from eval results."""
        # Create mock eval results
        results = []
        for i in range(10):
            result = Mock()
            result.retrieval_latency_ms = 200 + i * 10  # 200-290ms
            result.packing_latency_ms = 100 + i * 5  # 100-145ms
            result.category = "test"
            results.append(result)
        
        gate = LatencyGate()
        result = check_latency_budgets(results, gate)
        
        self.assertTrue(result.passed)
    
    def test_check_with_slow_results(self):
        """Test checking budgets with slow results."""
        # Create mock results with slow retrieval
        results = []
        for i in range(10):
            result = Mock()
            result.retrieval_latency_ms = 500 + i * 20  # 500-680ms
            result.packing_latency_ms = 100
            result.category = "test"
            results.append(result)
        
        result = check_latency_budgets(results)
        
        self.assertFalse(result.passed)
        self.assertGreater(len(result.violations), 0)


class TestFormatLatencyReport(unittest.TestCase):
    """Test latency report formatting."""
    
    def test_format_passed_report(self):
        """Test formatting passed result."""
        result = LatencyGateResult(passed=True, violations=[], warnings=[])
        report = format_latency_report(result)
        
        self.assertIn("PASSED", report)
        # Report contains success indicator
        self.assertTrue(len(report) > 0)
    
    def test_format_failed_report(self):
        """Test formatting failed result."""
        violation = LatencyViolation(
            operation="retrieval",
            metric="p95",
            measured=600.0,
            budget=500.0,
            excess=100.0,
            count=10
        )
        
        result = LatencyGateResult(
            passed=False,
            violations=[violation],
            warnings=["Test warning"]
        )
        
        report = format_latency_report(result)
        
        self.assertIn("FAILED", report)
        # Report contains failure content
        self.assertIn("retrieval", report)
        self.assertIn("600", report)
        self.assertIn("500", report)
        self.assertIn("Test warning", report)


class TestIntegrationWithHarness(unittest.TestCase):
    """Test integration with evaluation harness."""
    
    def test_harness_marks_suite_failed(self):
        """Test that harness marks suite failed on budget violation."""
        from evals.run import EvalRunner, EvalResult
        
        # Create runner (latency gates enabled by default)
        runner = EvalRunner()
        
        # Create mock slow results
        for i in range(10):
            result = EvalResult(
                case_id=f"test_{i}",
                prompt="Test",
                category="test",
                passed=True,
                latency_ms=600 + i * 10,  # 600-690ms
                retrieval_latency_ms=600 + i * 10,  # Over budget
                packing_latency_ms=100
            )
            runner.results.append(result)
        
        # Generate summary
        summary = runner.generate_summary()
        
        # Should have latency violations
        self.assertFalse(summary.latency_gate_passed,
                        "Suite should be marked as failed due to latency violations")
        self.assertGreater(len(summary.latency_violations), 0,
                          "Should have recorded violations")
    
    def test_harness_passes_with_good_latencies(self):
        """Test that harness passes with good latencies."""
        from evals.run import EvalRunner, EvalResult
        
        runner = EvalRunner()
        
        # Create results under budget
        for i in range(10):
            result = EvalResult(
                case_id=f"test_{i}",
                prompt="Test",
                category="test",
                passed=True,
                latency_ms=300,
                retrieval_latency_ms=300,
                packing_latency_ms=200
            )
            runner.results.append(result)
        
        summary = runner.generate_summary()
        
        self.assertTrue(summary.latency_gate_passed,
                       "Suite should pass with good latencies")


if __name__ == "__main__":
    unittest.main()
