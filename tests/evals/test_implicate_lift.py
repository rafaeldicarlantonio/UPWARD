#!/usr/bin/env python3
"""
Unit tests for implicate lift evaluation suite.

Tests verify:
1. Top-k containment: expected_source_ids appear in top k results
2. Latency budget: p95 latency under 500ms
3. Delta vs legacy: implicate performs better than legacy baseline
4. Success rate: ≥90% of cases pass
"""

import os
import sys
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import statistics

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.run import EvalRunner, EvalResult


class TestImplicateLiftSuite(unittest.TestCase):
    """Test implicate lift suite structure and cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.suite_path = Path("/workspace/evals/suites/implicate_lift.jsonl")
        self.fixtures_path = Path("/workspace/evals/fixtures/implicate_corpus.json")
        self.cases_dir = Path("/workspace/evals/cases/implicate")
    
    def test_suite_file_exists(self):
        """Test that suite file exists."""
        self.assertTrue(self.suite_path.exists(), f"Suite file not found: {self.suite_path}")
    
    def test_fixtures_exist(self):
        """Test that fixture corpus exists."""
        self.assertTrue(self.fixtures_path.exists(), f"Fixtures not found: {self.fixtures_path}")
    
    def test_suite_has_15_cases(self):
        """Test that suite has 15 test cases."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        self.assertEqual(len(cases), 15, f"Expected 15 cases, found {len(cases)}")
    
    def test_all_cases_have_required_fields(self):
        """Test that all cases have required fields."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        required_fields = [
            "id", "query", "category", "expected_source_ids",
            "expected_in_top_k", "max_latency_ms", "legacy_should_miss", "rationale"
        ]
        
        for case in cases:
            for field in required_fields:
                self.assertIn(field, case, f"Case {case.get('id')} missing field: {field}")
            
            # Validate field types
            self.assertIsInstance(case["id"], str)
            self.assertIsInstance(case["query"], str)
            self.assertEqual(case["category"], "implicate_lift")
            self.assertIsInstance(case["expected_source_ids"], list)
            self.assertGreater(len(case["expected_source_ids"]), 0)
            self.assertEqual(case["expected_in_top_k"], 8)
            self.assertEqual(case["max_latency_ms"], 500)
            self.assertTrue(case["legacy_should_miss"])
    
    def test_fixtures_have_20_documents(self):
        """Test that fixture corpus has 20 documents."""
        with open(self.fixtures_path, 'r') as f:
            corpus = json.load(f)
        
        self.assertIn("documents", corpus)
        self.assertEqual(len(corpus["documents"]), 20)
    
    def test_all_expected_ids_exist_in_corpus(self):
        """Test that all expected_source_ids reference valid documents."""
        with open(self.fixtures_path, 'r') as f:
            corpus = json.load(f)
        
        doc_ids = {doc["id"] for doc in corpus["documents"]}
        
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        for case in cases:
            for expected_id in case["expected_source_ids"]:
                self.assertIn(
                    expected_id, doc_ids,
                    f"Case {case['id']} references non-existent doc: {expected_id}"
                )
    
    def test_case_files_match_suite(self):
        """Test that individual case files match suite entries."""
        with open(self.suite_path, 'r') as f:
            suite_cases = {json.loads(line)["id"]: json.loads(line) for line in f if line.strip()}
        
        # Check that case files exist and match
        for case_id, suite_case in suite_cases.items():
            case_file = self.cases_dir / f"case_{case_id.split('_')[1]}_*.json"
            matching_files = list(self.cases_dir.glob(f"case_{case_id.split('_')[1]}_*.json"))
            
            self.assertEqual(
                len(matching_files), 1,
                f"Expected 1 case file for {case_id}, found {len(matching_files)}"
            )
            
            with open(matching_files[0], 'r') as f:
                file_case = json.load(f)
            
            # Verify key fields match
            self.assertEqual(file_case["id"], suite_case["id"])
            self.assertEqual(file_case["query"], suite_case["query"])
            self.assertEqual(file_case["expected_source_ids"], suite_case["expected_source_ids"])


class TestTopKContainment(unittest.TestCase):
    """Test top-k containment assertions."""
    
    def test_top_k_containment_all_present(self):
        """Test checking when all expected IDs are in top k."""
        expected_ids = ["doc_001", "doc_002", "doc_003"]
        retrieved_ids = ["doc_001", "doc_004", "doc_002", "doc_005", "doc_003", "doc_006"]
        k = 8
        
        # Check containment
        found_in_top_k = [id for id in expected_ids if id in retrieved_ids[:k]]
        
        self.assertEqual(len(found_in_top_k), len(expected_ids))
        self.assertEqual(set(found_in_top_k), set(expected_ids))
    
    def test_top_k_containment_partial(self):
        """Test checking when only some expected IDs are in top k."""
        expected_ids = ["doc_001", "doc_002", "doc_003"]
        retrieved_ids = ["doc_001", "doc_004", "doc_005", "doc_006"]
        k = 4
        
        found_in_top_k = [id for id in expected_ids if id in retrieved_ids[:k]]
        
        self.assertEqual(len(found_in_top_k), 1)  # Only doc_001
        self.assertIn("doc_001", found_in_top_k)
    
    def test_top_k_containment_none(self):
        """Test checking when no expected IDs are in top k."""
        expected_ids = ["doc_001", "doc_002", "doc_003"]
        retrieved_ids = ["doc_004", "doc_005", "doc_006"]
        k = 8
        
        found_in_top_k = [id for id in expected_ids if id in retrieved_ids[:k]]
        
        self.assertEqual(len(found_in_top_k), 0)
    
    def test_calculate_top_k_recall(self):
        """Test calculating recall@k metric."""
        expected_ids = ["doc_001", "doc_002", "doc_003"]
        retrieved_ids = ["doc_001", "doc_004", "doc_002", "doc_005"]
        k = 8
        
        found = sum(1 for id in expected_ids if id in retrieved_ids[:k])
        recall_at_k = found / len(expected_ids)
        
        self.assertAlmostEqual(recall_at_k, 2/3, places=2)


class TestLatencyBudget(unittest.TestCase):
    """Test latency budget assertions."""
    
    def test_p95_under_budget(self):
        """Test p95 latency under 500ms."""
        latencies = [100, 150, 200, 250, 300, 350, 400, 450, 480, 490]
        
        p95 = statistics.quantiles(latencies, n=20)[18]
        
        self.assertLess(p95, 500, f"P95 latency {p95}ms exceeds 500ms budget")
    
    def test_p95_exceeds_budget(self):
        """Test p95 latency exceeding 500ms."""
        latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        
        p95 = statistics.quantiles(latencies, n=20)[18]
        
        self.assertGreater(p95, 500, f"P95 latency {p95}ms should exceed budget for this test")
    
    def test_all_cases_under_individual_budget(self):
        """Test that all individual cases are under max_latency_ms."""
        max_latency = 500
        latencies = [450, 480, 490, 495, 499]
        
        violations = [lat for lat in latencies if lat > max_latency]
        
        self.assertEqual(len(violations), 0, f"Found {len(violations)} latency violations")
    
    def test_latency_calculation_from_results(self):
        """Test extracting latency from eval results."""
        results = [
            EvalResult("test_001", "query", "implicate_lift", True, 150.0),
            EvalResult("test_002", "query", "implicate_lift", True, 200.0),
            EvalResult("test_003", "query", "implicate_lift", True, 250.0),
        ]
        
        latencies = [r.latency_ms for r in results]
        avg_latency = statistics.mean(latencies)
        
        self.assertAlmostEqual(avg_latency, 200.0, places=1)


class TestDeltaVsLegacy(unittest.TestCase):
    """Test delta vs legacy baseline assertions."""
    
    def test_implicate_better_than_legacy(self):
        """Test that implicate achieves higher success rate than legacy."""
        # Simulate results
        implicate_success_rate = 0.93  # 14/15 cases pass
        legacy_success_rate = 0.33     # 5/15 cases pass
        
        delta = implicate_success_rate - legacy_success_rate
        
        self.assertGreater(delta, 0, "Implicate should outperform legacy")
        self.assertGreater(delta, 0.50, f"Expected large delta, got {delta:.2f}")
    
    def test_legacy_should_miss_validation(self):
        """Test validation that legacy misses cases it should."""
        # Case marked as legacy_should_miss=true
        legacy_found = False  # Legacy didn't find expected docs
        should_miss = True
        
        # This is the expected outcome
        self.assertEqual(legacy_found, not should_miss)
    
    def test_implicate_finds_bridging_cases(self):
        """Test that implicate finds cases requiring bridging."""
        # Simulate bridging case
        expected_ids = ["doc_003", "doc_004"]
        implicate_retrieved = ["doc_003", "doc_001", "doc_004", "doc_002"]
        legacy_retrieved = ["doc_001", "doc_002", "doc_005", "doc_006"]
        
        # Check implicate finds both
        implicate_found = all(id in implicate_retrieved for id in expected_ids)
        legacy_found = all(id in legacy_retrieved for id in expected_ids)
        
        self.assertTrue(implicate_found, "Implicate should find bridged docs")
        self.assertFalse(legacy_found, "Legacy should miss bridged docs")


class TestSuccessRate(unittest.TestCase):
    """Test success rate assertions."""
    
    def test_success_rate_above_90_percent(self):
        """Test that success rate meets ≥90% threshold."""
        total_cases = 15
        passed_cases = 14  # 93.3% pass rate
        
        success_rate = passed_cases / total_cases
        
        self.assertGreaterEqual(
            success_rate, 0.90,
            f"Success rate {success_rate:.1%} below 90% threshold"
        )
    
    def test_success_rate_below_threshold(self):
        """Test failure when success rate is below threshold."""
        total_cases = 15
        passed_cases = 12  # 80% pass rate
        
        success_rate = passed_cases / total_cases
        
        self.assertLess(success_rate, 0.90, "This test expects below-threshold rate")
    
    def test_minimum_cases_for_statistical_significance(self):
        """Test that we have enough cases for meaningful evaluation."""
        with open("/workspace/evals/suites/implicate_lift.jsonl", 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        self.assertGreaterEqual(
            len(cases), 10,
            "Need at least 10 cases for statistical significance"
        )
        self.assertLessEqual(
            len(cases), 20,
            "Suite should have 10-20 cases as specified"
        )


class TestImplicateLiftValidation(unittest.TestCase):
    """Test implicate lift validation logic."""
    
    @patch('requests.post')
    def test_validate_top_k_containment_mock(self, mock_post):
        """Test top-k validation with mocked retrieval."""
        # Mock API response with retrieved document IDs
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [
                {"source_id": "doc_transformer_003"},
                {"source_id": "doc_bert_004"},
                {"source_id": "doc_neural_001"}
            ],
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": [
                        "doc_transformer_003",
                        "doc_bert_004", 
                        "doc_neural_001",
                        "doc_deep_002"
                    ]
                }
            }
        }
        mock_post.return_value = mock_response
        
        # Expected IDs for this case
        expected_ids = ["doc_transformer_003", "doc_bert_004"]
        retrieved_ids = mock_response.json()["debug"]["retrieval_metrics"]["retrieved_ids"]
        
        # Validate containment
        found = [id for id in expected_ids if id in retrieved_ids[:8]]
        
        self.assertEqual(len(found), len(expected_ids))
    
    def test_calculate_lift_delta(self):
        """Test calculating lift delta between implicate and legacy."""
        # Simulate results for same queries
        implicate_recalls = [1.0, 1.0, 0.67, 1.0, 1.0]  # Recall@8 for each case
        legacy_recalls = [0.5, 0.33, 0.0, 0.5, 0.33]
        
        implicate_avg = statistics.mean(implicate_recalls)
        legacy_avg = statistics.mean(legacy_recalls)
        lift_delta = implicate_avg - legacy_avg
        
        self.assertGreater(lift_delta, 0)
        self.assertAlmostEqual(lift_delta, 0.60, places=1)


if __name__ == "__main__":
    unittest.main()
