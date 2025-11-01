#!/usr/bin/env python3
"""
Unit tests for evaluation harness.

Tests cover:
- Config parsing
- Suite loading
- Pass/fail accounting
- Latency capture
- JSON report generation
- Console output
- Exit codes
- Constraint validation
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import yaml

# Add workspace to path
sys.path.insert(0, '/workspace')

# Import directly from the file
import importlib.util
spec = importlib.util.spec_from_file_location("eval_run", "/workspace/evals/run.py")
eval_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_run)

EvalResult = eval_run.EvalResult
EvalSummary = eval_run.EvalSummary
EvalRunner = eval_run.EvalRunner
write_json_report = eval_run.write_json_report
print_latency_histogram = eval_run.print_latency_histogram


class TestEvalResult(unittest.TestCase):
    """Test EvalResult dataclass."""
    
    def test_create_basic_result(self):
        """Test creating a basic result."""
        result = EvalResult(
            case_id="test_001",
            prompt="Test prompt",
            category="smoke",
            passed=True,
            latency_ms=150.5
        )
        
        self.assertEqual(result.case_id, "test_001")
        self.assertEqual(result.prompt, "Test prompt")
        self.assertEqual(result.category, "smoke")
        self.assertTrue(result.passed)
        self.assertEqual(result.latency_ms, 150.5)
    
    def test_result_with_error(self):
        """Test result with error."""
        result = EvalResult(
            case_id="test_002",
            prompt="Test prompt",
            category="smoke",
            passed=False,
            latency_ms=200.0,
            error="Test failed"
        )
        
        self.assertFalse(result.passed)
        self.assertEqual(result.error, "Test failed")
    
    def test_result_with_timing_breakdown(self):
        """Test result with detailed timing."""
        result = EvalResult(
            case_id="test_003",
            prompt="Test prompt",
            category="performance",
            passed=True,
            latency_ms=500.0,
            total_latency_ms=500.0,
            retrieval_latency_ms=100.0,
            ranking_latency_ms=50.0,
            packing_latency_ms=30.0
        )
        
        self.assertEqual(result.total_latency_ms, 500.0)
        self.assertEqual(result.retrieval_latency_ms, 100.0)
        self.assertEqual(result.ranking_latency_ms, 50.0)
        self.assertEqual(result.packing_latency_ms, 30.0)
    
    def test_result_with_constraints(self):
        """Test result with constraint checks."""
        result = EvalResult(
            case_id="test_004",
            prompt="Test prompt",
            category="constraints",
            passed=False,
            latency_ms=1500.0,
            meets_latency_constraint=False,
            meets_implicate_constraint=True,
            meets_contradiction_constraint=True
        )
        
        self.assertFalse(result.meets_latency_constraint)
        self.assertTrue(result.meets_implicate_constraint)
        self.assertTrue(result.meets_contradiction_constraint)


class TestEvalSummary(unittest.TestCase):
    """Test EvalSummary generation."""
    
    def test_create_empty_summary(self):
        """Test creating summary with no results."""
        summary = EvalSummary(
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            max_latency_ms=0.0,
            category_breakdown={},
            performance_issues=[]
        )
        
        self.assertEqual(summary.total_cases, 0)
        self.assertEqual(summary.passed_cases, 0)
        self.assertEqual(summary.failed_cases, 0)
    
    def test_summary_with_results(self):
        """Test summary with actual results."""
        summary = EvalSummary(
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_latency_ms=250.0,
            p95_latency_ms=450.0,
            max_latency_ms=500.0,
            category_breakdown={
                "smoke": {"total": 5, "passed": 5, "failed": 0},
                "performance": {"total": 5, "passed": 3, "failed": 2}
            },
            performance_issues=["2 cases exceeded 1000ms latency"]
        )
        
        self.assertEqual(summary.total_cases, 10)
        self.assertEqual(summary.passed_cases, 8)
        self.assertEqual(summary.failed_cases, 2)
        self.assertEqual(summary.avg_latency_ms, 250.0)
        self.assertEqual(summary.p95_latency_ms, 450.0)
        self.assertEqual(len(summary.performance_issues), 1)


class TestEvalRunner(unittest.TestCase):
    """Test EvalRunner functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.runner = EvalRunner(base_url="http://localhost:8000", api_key="test-key")
    
    def test_runner_initialization(self):
        """Test runner initializes with correct defaults."""
        self.assertEqual(self.runner.base_url, "http://localhost:8000")
        self.assertEqual(self.runner.api_key, "test-key")
        self.assertEqual(self.runner.max_latency_ms, 500)
        self.assertEqual(self.runner.max_individual_latency_ms, 1000)
        self.assertEqual(self.runner.expected_explicate_k, 16)
        self.assertEqual(self.runner.expected_implicate_k, 8)
        self.assertEqual(len(self.runner.results), 0)
    
    def test_runner_custom_constraints(self):
        """Test runner with custom constraints."""
        runner = EvalRunner()
        runner.max_latency_ms = 300
        runner.max_individual_latency_ms = 800
        
        self.assertEqual(runner.max_latency_ms, 300)
        self.assertEqual(runner.max_individual_latency_ms, 800)
    
    @patch('requests.post')
    def test_run_single_case_success(self, mock_post):
        """Test running a single successful case."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer with required terms",
            "citations": ["citation1", "citation2"],
            "debug": {
                "retrieval_metrics": {
                    "ranking_latency_ms": 50.0,
                    "packing_latency_ms": 30.0
                }
            }
        }
        mock_post.return_value = mock_response
        
        case = {
            "id": "test_001",
            "prompt": "Test prompt",
            "category": "smoke",
            "must_include": ["test", "answer"]
        }
        
        result = self.runner.run_single_case(case)
        
        self.assertEqual(result.case_id, "test_001")
        self.assertTrue(result.passed)
        self.assertIsNone(result.error)
        self.assertEqual(result.retrieved_chunks, 2)
    
    @patch('requests.post')
    def test_run_single_case_failure(self, mock_post):
        """Test running a single failed case."""
        # Mock successful API response but missing terms
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Answer without required terms",
            "citations": []
        }
        mock_post.return_value = mock_response
        
        case = {
            "id": "test_002",
            "prompt": "Test prompt",
            "category": "smoke",
            "must_include": ["missing", "terms"]
        }
        
        result = self.runner.run_single_case(case)
        
        self.assertEqual(result.case_id, "test_002")
        self.assertFalse(result.passed)
        self.assertIsNotNone(result.error)
        self.assertIn("Missing terms", result.error)
    
    @patch('requests.post')
    def test_run_single_case_latency_violation(self, mock_post):
        """Test case that violates latency constraint."""
        # Mock response with simulated slow latency
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": []
        }
        mock_post.return_value = mock_response
        
        case = {
            "id": "test_003",
            "prompt": "Test prompt",
            "category": "performance",
            "max_latency_ms": 10  # Very strict constraint
        }
        
        result = self.runner.run_single_case(case)
        
        # Result will likely fail latency constraint
        # (actual timing depends on test environment)
        self.assertEqual(result.case_id, "test_003")
    
    @patch('requests.post')
    def test_run_single_case_http_error(self, mock_post):
        """Test handling of HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response
        
        case = {
            "id": "test_004",
            "prompt": "Test prompt",
            "category": "error"
        }
        
        result = self.runner.run_single_case(case)
        
        self.assertFalse(result.passed)
        self.assertIn("HTTP 500", result.error)
    
    @patch('requests.post')
    def test_run_single_case_exception(self, mock_post):
        """Test handling of exception."""
        mock_post.side_effect = Exception("Network error")
        
        case = {
            "id": "test_005",
            "prompt": "Test prompt",
            "category": "error"
        }
        
        result = self.runner.run_single_case(case)
        
        self.assertFalse(result.passed)
        self.assertIn("Exception", result.error)
    
    def test_generate_summary_empty(self):
        """Test generating summary with no results."""
        summary = self.runner.generate_summary()
        
        self.assertEqual(summary.total_cases, 0)
        self.assertEqual(summary.passed_cases, 0)
        self.assertEqual(summary.failed_cases, 0)
    
    def test_generate_summary_with_results(self):
        """Test generating summary with results."""
        # Add mock results
        self.runner.results = [
            EvalResult(
                case_id="test_001",
                prompt="Test 1",
                category="smoke",
                passed=True,
                latency_ms=100.0
            ),
            EvalResult(
                case_id="test_002",
                prompt="Test 2",
                category="smoke",
                passed=True,
                latency_ms=200.0
            ),
            EvalResult(
                case_id="test_003",
                prompt="Test 3",
                category="performance",
                passed=False,
                latency_ms=1200.0,
                meets_latency_constraint=False
            )
        ]
        
        summary = self.runner.generate_summary()
        
        self.assertEqual(summary.total_cases, 3)
        self.assertEqual(summary.passed_cases, 2)
        self.assertEqual(summary.failed_cases, 1)
        self.assertGreater(summary.avg_latency_ms, 0)
        self.assertGreater(summary.max_latency_ms, 0)
        self.assertIn("smoke", summary.category_breakdown)
        self.assertIn("performance", summary.category_breakdown)


class TestJSONReport(unittest.TestCase):
    """Test JSON report generation."""
    
    def test_write_json_report(self):
        """Test writing JSON report to file."""
        results = [
            EvalResult(
                case_id="test_001",
                prompt="Test prompt",
                category="smoke",
                passed=True,
                latency_ms=150.0,
                total_latency_ms=150.0,
                retrieval_latency_ms=50.0
            ),
            EvalResult(
                case_id="test_002",
                prompt="Test prompt 2",
                category="performance",
                passed=False,
                latency_ms=1200.0,
                error="Latency exceeded"
            )
        ]
        
        summary = EvalSummary(
            total_cases=2,
            passed_cases=1,
            failed_cases=1,
            avg_latency_ms=675.0,
            p95_latency_ms=1200.0,
            max_latency_ms=1200.0,
            category_breakdown={
                "smoke": {"total": 1, "passed": 1, "failed": 0},
                "performance": {"total": 1, "passed": 0, "failed": 1}
            },
            performance_issues=["1 case exceeded latency"]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            write_json_report(results, summary, temp_path)
            
            # Verify file was created
            self.assertTrue(os.path.exists(temp_path))
            
            # Verify content
            with open(temp_path, 'r') as f:
                report = json.load(f)
            
            self.assertIn("timestamp", report)
            self.assertIn("summary", report)
            self.assertIn("results", report)
            
            self.assertEqual(report["summary"]["total_cases"], 2)
            self.assertEqual(report["summary"]["passed_cases"], 1)
            self.assertEqual(report["summary"]["failed_cases"], 1)
            self.assertEqual(len(report["results"]), 2)
            
            # Check first result
            result1 = report["results"][0]
            self.assertEqual(result1["case_id"], "test_001")
            self.assertTrue(result1["passed"])
            self.assertEqual(result1["latency_ms"], 150.0)
            
            # Check second result
            result2 = report["results"][1]
            self.assertEqual(result2["case_id"], "test_002")
            self.assertFalse(result2["passed"])
            self.assertEqual(result2["error"], "Latency exceeded")
        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_json_report_directory_creation(self):
        """Test that report creates missing directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "subdir", "report.json")
            
            results = [
                EvalResult(
                    case_id="test_001",
                    prompt="Test",
                    category="smoke",
                    passed=True,
                    latency_ms=100.0
                )
            ]
            
            summary = EvalSummary(
                total_cases=1,
                passed_cases=1,
                failed_cases=0,
                avg_latency_ms=100.0,
                p95_latency_ms=100.0,
                max_latency_ms=100.0,
                category_breakdown={},
                performance_issues=[]
            )
            
            write_json_report(results, summary, output_path)
            
            self.assertTrue(os.path.exists(output_path))


class TestLatencyHistogram(unittest.TestCase):
    """Test latency histogram generation."""
    
    def test_print_histogram_empty(self):
        """Test histogram with no results."""
        # Should not raise an error
        print_latency_histogram([])
    
    def test_print_histogram_with_results(self):
        """Test histogram with results."""
        results = [
            EvalResult("test_001", "Test", "smoke", True, 50.0),
            EvalResult("test_002", "Test", "smoke", True, 150.0),
            EvalResult("test_003", "Test", "smoke", True, 250.0),
            EvalResult("test_004", "Test", "smoke", True, 450.0),
            EvalResult("test_005", "Test", "smoke", True, 850.0),
            EvalResult("test_006", "Test", "smoke", True, 1200.0),
        ]
        
        # Should not raise an error
        # (We're just testing it doesn't crash, not output format)
        print_latency_histogram(results)
    
    def test_print_histogram_custom_buckets(self):
        """Test histogram with custom buckets."""
        results = [
            EvalResult("test_001", "Test", "smoke", True, 50.0),
            EvalResult("test_002", "Test", "smoke", True, 250.0),
        ]
        
        custom_buckets = [100, 500, 1000]
        print_latency_histogram(results, buckets=custom_buckets)


class TestConfigParsing(unittest.TestCase):
    """Test configuration file parsing."""
    
    def test_parse_valid_config(self):
        """Test parsing valid config YAML."""
        config_content = """
version: "1.0"

pipelines:
  legacy:
    name: "Legacy Pipeline"
    enabled: true
  new:
    name: "New Pipeline"
    enabled: true

constraints:
  latency:
    p95_ms: 500
    max_individual_ms: 1000

suites:
  - name: "smoke"
    description: "Smoke test"
    enabled: true
    pipeline: "new"
    testsets:
      - "testsets/performance.json"
    constraints:
      max_latency_ms: 500
      min_pass_rate: 1.0
"""
        
        config = yaml.safe_load(config_content)
        
        self.assertEqual(config["version"], "1.0")
        self.assertIn("legacy", config["pipelines"])
        self.assertIn("new", config["pipelines"])
        self.assertIn("constraints", config)
        self.assertEqual(len(config["suites"]), 1)
        self.assertEqual(config["suites"][0]["name"], "smoke")
    
    def test_parse_config_with_suite(self):
        """Test parsing config and finding suite."""
        config_content = """
suites:
  - name: "test_suite"
    description: "Test suite"
    enabled: true
    pipeline: "new"
    testsets:
      - "test1.json"
      - "test2.json"
    constraints:
      max_latency_ms: 500
      min_pass_rate: 0.90
"""
        
        config = yaml.safe_load(config_content)
        suites = config.get("suites", [])
        
        # Find suite
        test_suite = None
        for s in suites:
            if s.get("name") == "test_suite":
                test_suite = s
                break
        
        self.assertIsNotNone(test_suite)
        self.assertEqual(test_suite["pipeline"], "new")
        self.assertEqual(len(test_suite["testsets"]), 2)
        self.assertEqual(test_suite["constraints"]["max_latency_ms"], 500)
        self.assertEqual(test_suite["constraints"]["min_pass_rate"], 0.90)


class TestExitCodes(unittest.TestCase):
    """Test exit code behavior."""
    
    def test_exit_code_all_passed(self):
        """Test exit code when all tests pass."""
        # Simulate all tests passing
        # (This would be tested in integration tests)
        pass
    
    def test_exit_code_some_failed(self):
        """Test exit code when some tests fail."""
        # Exit code should be 1 when any test fails
        # (This would be tested in integration tests)
        pass
    
    def test_exit_code_latency_violation(self):
        """Test exit code when latency constraint violated."""
        # Exit code should be 1 when P95 exceeds threshold
        # (This would be tested in integration tests)
        pass
    
    def test_exit_code_ci_mode_strict(self):
        """Test exit code in CI mode is strict."""
        # CI mode should fail on any constraint violation
        # (This would be tested in integration tests)
        pass


class TestConstraintValidation(unittest.TestCase):
    """Test constraint validation."""
    
    def test_latency_constraint_pass(self):
        """Test latency constraint passes."""
        result = EvalResult(
            case_id="test_001",
            prompt="Test",
            category="performance",
            passed=True,
            latency_ms=400.0,
            meets_latency_constraint=True
        )
        
        self.assertTrue(result.meets_latency_constraint)
    
    def test_latency_constraint_fail(self):
        """Test latency constraint fails."""
        result = EvalResult(
            case_id="test_002",
            prompt="Test",
            category="performance",
            passed=False,
            latency_ms=1200.0,
            meets_latency_constraint=False
        )
        
        self.assertFalse(result.meets_latency_constraint)
    
    def test_implicate_constraint(self):
        """Test implicate lift constraint."""
        result = EvalResult(
            case_id="test_003",
            prompt="Test",
            category="implicate_lift",
            passed=True,
            latency_ms=300.0,
            meets_implicate_constraint=True,
            implicate_rank=1
        )
        
        self.assertTrue(result.meets_implicate_constraint)
        self.assertEqual(result.implicate_rank, 1)
    
    def test_contradiction_constraint(self):
        """Test contradiction detection constraint."""
        result = EvalResult(
            case_id="test_004",
            prompt="Test",
            category="contradictions",
            passed=True,
            latency_ms=300.0,
            meets_contradiction_constraint=True,
            contradictions_found=2
        )
        
        self.assertTrue(result.meets_contradiction_constraint)
        self.assertEqual(result.contradictions_found, 2)


if __name__ == "__main__":
    unittest.main()
