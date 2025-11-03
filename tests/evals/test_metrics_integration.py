#!/usr/bin/env python3
"""
Unit tests for evaluation metrics integration.

Tests:
1. Metrics increment during test runs
2. Dashboard formatting
3. Quality score calculation
4. Suite-level metrics
5. Case-level metrics
6. Latency metrics
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.metrics import EvalMetrics, reset_metrics, get_counter, get_gauge, get_histogram_stats
from evals.run import EvalRunner, EvalResult, EvalSummary


class TestEvalMetricsBasic(unittest.TestCase):
    """Test basic metrics functionality."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_record_suite_run(self):
        """Test recording suite runs."""
        EvalMetrics.record_suite_run("test_suite", True, 1000.0, 10)
        
        runs = get_counter("eval.suite.runs", {"suite": "test_suite", "success": "true"})
        self.assertEqual(runs, 1)
    
    def test_record_suite_failure(self):
        """Test recording suite failures."""
        EvalMetrics.record_suite_failure("test_suite", "functional")
        
        failures = get_counter("eval.suite.failures", {"suite": "test_suite", "type": "functional"})
        self.assertEqual(failures, 1)
    
    def test_record_case_result_passed(self):
        """Test recording passed case."""
        EvalMetrics.record_case_result("test_suite", "case_001", True, "implicate_lift")
        
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "implicate_lift"})
        passed = get_counter("eval.cases.passed", {"suite": "test_suite", "category": "implicate_lift"})
        
        self.assertEqual(total, 1)
        self.assertEqual(passed, 1)
    
    def test_record_case_result_failed(self):
        """Test recording failed case."""
        EvalMetrics.record_case_result("test_suite", "case_001", False, "contradictions")
        
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "contradictions"})
        failed = get_counter("eval.cases.failed", {"suite": "test_suite", "category": "contradictions"})
        
        self.assertEqual(total, 1)
        self.assertEqual(failed, 1)
    
    def test_record_latency(self):
        """Test recording latency metrics."""
        EvalMetrics.record_latency("retrieval", 150.0, "test_suite", "implicate_lift")
        
        stats = get_histogram_stats("eval.latency.retrieval_ms", {"operation": "retrieval", "suite": "test_suite", "category": "implicate_lift"})
        
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["sum"], 150.0)
        self.assertEqual(stats["avg"], 150.0)
    
    def test_quality_score(self):
        """Test quality score setting and retrieval."""
        EvalMetrics.set_quality_score("test_suite", 0.95)
        
        score = EvalMetrics.get_suite_quality_score("test_suite")
        self.assertEqual(score, 0.95)
    
    def test_trace_replay_success(self):
        """Test recording trace replay success."""
        EvalMetrics.record_trace_replay(True, "trace_001")
        
        success = get_counter("eval.trace.replay_success", {"success": "true", "trace_id": "trace_001"})
        self.assertEqual(success, 1)
    
    def test_trace_replay_failure(self):
        """Test recording trace replay failure."""
        EvalMetrics.record_trace_replay(False, "trace_002")
        
        failure = get_counter("eval.trace.replay_failure", {"success": "false", "trace_id": "trace_002"})
        self.assertEqual(failure, 1)


class TestEvalRunnerMetricsIntegration(unittest.TestCase):
    """Test metrics integration with EvalRunner."""
    
    def setUp(self):
        """Reset metrics and create test environment."""
        reset_metrics()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_runner_records_case_metrics(self):
        """Test that runner records metrics for each case."""
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        # Create mock result
        result = EvalResult(
            case_id="test_001",
            prompt="Test query",
            category="implicate_lift",
            passed=True,
            latency_ms=100.0,
            retrieval_latency_ms=80.0,
            packing_latency_ms=20.0
        )
        
        # Record metrics
        runner._record_case_metrics(result)
        
        # Verify metrics were recorded
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "implicate_lift"})
        passed = get_counter("eval.cases.passed", {"suite": "test_suite", "category": "implicate_lift"})
        
        self.assertEqual(total, 1)
        self.assertEqual(passed, 1)
        
        # Verify latency metrics
        retrieval_stats = get_histogram_stats("eval.latency.retrieval_ms", {"operation": "retrieval", "suite": "test_suite", "category": "implicate_lift"})
        self.assertEqual(retrieval_stats["count"], 1)
        self.assertEqual(retrieval_stats["sum"], 80.0)
    
    @patch('requests.post')
    def test_run_single_case_records_metrics(self, mock_post):
        """Test that run_single_case records metrics."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [{"source_id": "src_001"}],
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["src_001", "src_002"],
                    "ranking_latency_ms": 10.0,
                    "packing_latency_ms": 5.0
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "test_001",
            "prompt": "Test query",
            "category": "implicate_lift",
            "expected_source_ids": ["src_001"],
            "expected_in_top_k": 8
        }
        
        result = runner.run_single_case(case)
        
        # Verify result
        self.assertTrue(result.passed)
        
        # Verify metrics were recorded
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "implicate_lift"})
        self.assertGreaterEqual(total, 1)


class TestDashboardFormatting(unittest.TestCase):
    """Test dashboard line formatting."""
    
    def test_dashboard_line_format(self):
        """Test dashboard line formatting."""
        runner = EvalRunner(suite_name="test_suite")
        
        summary = EvalSummary(
            total_cases=20,
            passed_cases=19,
            failed_cases=1,
            avg_latency_ms=200.0,
            p95_latency_ms=450.0,
            max_latency_ms=500.0,
            category_breakdown={},
            performance_issues=[],
            latency_distribution={"p50": 150.0, "p95": 450.0}
        )
        
        # Capture print output
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            runner.print_dashboard_line(summary, "test_suite")
        
        output = f.getvalue()
        
        # Verify format
        self.assertIn("[TEST_SUITE]", output)
        self.assertIn("Quality: 95.0%", output)
        self.assertIn("Pass: 19/20", output)
        self.assertIn("p50=150ms", output)
        self.assertIn("p95=450ms", output)
        # Status indicator (emoji or ?)
        self.assertTrue("?" in output or "✅" in output)
    
    def test_dashboard_line_warning(self):
        """Test dashboard shows warning for 70-90% quality."""
        runner = EvalRunner(suite_name="test_suite")
        
        summary = EvalSummary(
            total_cases=20,
            passed_cases=16,
            failed_cases=4,
            avg_latency_ms=200.0,
            p95_latency_ms=450.0,
            max_latency_ms=500.0,
            category_breakdown={},
            performance_issues=[],
            latency_distribution={"p50": 150.0, "p95": 450.0}
        )
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            runner.print_dashboard_line(summary)
        
        output = f.getvalue()
        
        self.assertIn("Quality: 80.0%", output)
        # Status indicator (emoji or ?)
        self.assertTrue("?" in output or "⚠️" in output)
    
    def test_dashboard_line_failure(self):
        """Test dashboard shows failure for <70% quality."""
        runner = EvalRunner(suite_name="test_suite")
        
        summary = EvalSummary(
            total_cases=20,
            passed_cases=10,
            failed_cases=10,
            avg_latency_ms=200.0,
            p95_latency_ms=450.0,
            max_latency_ms=500.0,
            category_breakdown={},
            performance_issues=[],
            latency_distribution={"p50": 150.0, "p95": 450.0}
        )
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            runner.print_dashboard_line(summary)
        
        output = f.getvalue()
        
        self.assertIn("Quality: 50.0%", output)
        # Status indicator (emoji or ?)
        self.assertTrue("?" in output or "❌" in output)


class TestMetricsIncrement(unittest.TestCase):
    """Test that metrics increment correctly during runs."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_multiple_cases_increment(self):
        """Test that metrics increment for multiple cases."""
        for i in range(5):
            EvalMetrics.record_case_result("test_suite", f"case_{i:03d}", True, "implicate_lift")
        
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "implicate_lift"})
        passed = get_counter("eval.cases.passed", {"suite": "test_suite", "category": "implicate_lift"})
        
        self.assertEqual(total, 5)
        self.assertEqual(passed, 5)
    
    def test_mixed_results_increment(self):
        """Test metrics with mixed pass/fail results."""
        for i in range(10):
            passed = i % 2 == 0
            EvalMetrics.record_case_result("test_suite", f"case_{i:03d}", passed, "contradictions")
        
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "contradictions"})
        passed = get_counter("eval.cases.passed", {"suite": "test_suite", "category": "contradictions"})
        failed = get_counter("eval.cases.failed", {"suite": "test_suite", "category": "contradictions"})
        
        self.assertEqual(total, 10)
        self.assertEqual(passed, 5)
        self.assertEqual(failed, 5)
    
    def test_latency_histogram_accumulates(self):
        """Test that latency histograms accumulate values."""
        latencies = [100.0, 150.0, 200.0, 250.0, 300.0]
        
        for lat in latencies:
            EvalMetrics.record_latency("retrieval", lat, "test_suite")
        
        stats = get_histogram_stats("eval.latency.retrieval_ms", {"operation": "retrieval", "suite": "test_suite"})
        
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["sum"], sum(latencies))
        self.assertEqual(stats["avg"], sum(latencies) / len(latencies))


class TestQualityScoreCalculation(unittest.TestCase):
    """Test quality score calculation."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_quality_score_perfect(self):
        """Test quality score for perfect run."""
        for i in range(10):
            EvalMetrics.record_case_result("test_suite", f"case_{i:03d}", True, "implicate_lift")
        
        # Calculate quality score
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "implicate_lift"})
        passed = get_counter("eval.cases.passed", {"suite": "test_suite", "category": "implicate_lift"})
        
        quality = passed / total if total > 0 else 0.0
        
        self.assertEqual(quality, 1.0)
        
        # Set and retrieve
        EvalMetrics.set_quality_score("test_suite", quality)
        retrieved = EvalMetrics.get_suite_quality_score("test_suite")
        
        self.assertEqual(retrieved, 1.0)
    
    def test_quality_score_partial(self):
        """Test quality score for partial success."""
        # Record 7 passed, 3 failed
        for i in range(7):
            EvalMetrics.record_case_result("test_suite", f"pass_{i:03d}", True, "implicate_lift")
        
        for i in range(3):
            EvalMetrics.record_case_result("test_suite", f"fail_{i:03d}", False, "implicate_lift")
        
        total = get_counter("eval.cases.total", {"suite": "test_suite", "category": "implicate_lift"})
        passed = get_counter("eval.cases.passed", {"suite": "test_suite", "category": "implicate_lift"})
        
        quality = passed / total if total > 0 else 0.0
        
        self.assertAlmostEqual(quality, 0.7, places=2)


class TestLatencyMetrics(unittest.TestCase):
    """Test latency-specific metrics."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_retrieval_latency(self):
        """Test retrieval latency recording."""
        EvalMetrics.record_latency("retrieval", 150.0, "test_suite", "implicate_lift")
        
        stats = get_histogram_stats("eval.latency.retrieval_ms", {"operation": "retrieval", "suite": "test_suite", "category": "implicate_lift"})
        
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["sum"], 150.0)
    
    def test_packing_latency(self):
        """Test packing latency recording."""
        EvalMetrics.record_latency("packing", 50.0, "test_suite", "contradictions")
        
        stats = get_histogram_stats("eval.latency.packing_ms", {"operation": "packing", "suite": "test_suite", "category": "contradictions"})
        
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["sum"], 50.0)
    
    def test_compare_latency(self):
        """Test compare latency recording."""
        EvalMetrics.record_latency("compare", 200.0, "test_suite", "external_compare")
        
        stats = get_histogram_stats("eval.latency.compare_ms", {"operation": "compare", "suite": "test_suite", "category": "external_compare"})
        
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["sum"], 200.0)
    
    def test_scoring_latency(self):
        """Test scoring latency recording (Pareto)."""
        EvalMetrics.record_latency("scoring", 25.0, "test_suite", "pareto_gate")
        
        stats = get_histogram_stats("eval.latency.scoring_ms", {"operation": "scoring", "suite": "test_suite", "category": "pareto_gate"})
        
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["sum"], 25.0)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_metrics_increment_during_runs(self):
        """Test that metrics increment during test runs."""
        # Simulate a suite run
        suite_name = "acceptance_test"
        
        # Record suite run
        EvalMetrics.record_suite_run(suite_name, True, 5000.0, 20)
        
        # Record case results
        for i in range(20):
            passed = i < 18  # 18 passed, 2 failed
            EvalMetrics.record_case_result(suite_name, f"case_{i:03d}", passed, "implicate_lift")
        
        # Verify increments
        runs = get_counter("eval.suite.runs", {"suite": suite_name, "success": "true"})
        total_cases = get_counter("eval.cases.total", {"suite": suite_name, "category": "implicate_lift"})
        passed_cases = get_counter("eval.cases.passed", {"suite": suite_name, "category": "implicate_lift"})
        
        self.assertEqual(runs, 1)
        self.assertEqual(total_cases, 20)
        self.assertEqual(passed_cases, 18)
    
    def test_summary_line_prints_quality_scores(self):
        """Test that summary line includes quality scores."""
        runner = EvalRunner(suite_name="acceptance_test")
        
        summary = EvalSummary(
            total_cases=20,
            passed_cases=18,
            failed_cases=2,
            avg_latency_ms=200.0,
            p95_latency_ms=450.0,
            max_latency_ms=500.0,
            category_breakdown={},
            performance_issues=[],
            latency_distribution={"p50": 150.0, "p95": 450.0}
        )
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            runner.print_dashboard_line(summary)
        
        output = f.getvalue()
        
        # Verify quality score is present
        self.assertIn("Quality: 90.0%", output)
    
    def test_formatting_is_compact(self):
        """Test that formatting is compact (single line)."""
        runner = EvalRunner(suite_name="acceptance_test")
        
        summary = EvalSummary(
            total_cases=20,
            passed_cases=19,
            failed_cases=1,
            avg_latency_ms=200.0,
            p95_latency_ms=450.0,
            max_latency_ms=500.0,
            category_breakdown={},
            performance_issues=[],
            latency_distribution={"p50": 150.0, "p95": 450.0}
        )
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            runner.print_dashboard_line(summary)
        
        output = f.getvalue()
        lines = [l for l in output.strip().split('\n') if l.strip() and not l.strip().startswith('=')]
        
        # Should have exactly one dashboard line (excluding separator lines)
        self.assertEqual(len(lines), 1)
        
        # Verify it contains all key info
        dashboard_line = lines[0]
        self.assertIn("[ACCEPTANCE_TEST]", dashboard_line)
        self.assertIn("Quality:", dashboard_line)
        self.assertIn("Pass:", dashboard_line)
        self.assertIn("Latency:", dashboard_line)


if __name__ == "__main__":
    unittest.main()
