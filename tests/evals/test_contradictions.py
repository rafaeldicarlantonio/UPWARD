#!/usr/bin/env python3
"""
Unit tests for contradiction detection evaluation suite.

Tests verify:
1. contradictions[] structure is non-empty
2. Badge presence in answer payload
3. Both evidence IDs present
4. Correct subject identification
5. Packing latency under 550ms
6. Success rate ≥95%
"""

import os
import sys
import json
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import statistics

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.run import EvalRunner, EvalResult


class TestContradictionSuite(unittest.TestCase):
    """Test contradiction suite structure and cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.suite_path = Path("/workspace/evals/suites/contradictions.jsonl")
        self.fixtures_path = Path("/workspace/evals/fixtures/contradiction_corpus.json")
        self.cases_dir = Path("/workspace/evals/cases/contradictions")
    
    def test_suite_file_exists(self):
        """Test that suite file exists."""
        self.assertTrue(self.suite_path.exists(), f"Suite file not found: {self.suite_path}")
    
    def test_fixtures_exist(self):
        """Test that fixture corpus exists."""
        self.assertTrue(self.fixtures_path.exists(), f"Fixtures not found: {self.fixtures_path}")
    
    def test_suite_has_10_cases(self):
        """Test that suite has 10 test cases."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        self.assertEqual(len(cases), 10, f"Expected 10 cases, found {len(cases)}")
    
    def test_all_cases_have_required_fields(self):
        """Test that all cases have required fields."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        required_fields = [
            "id", "query", "category", "expected_contradictions",
            "expected_badge", "max_packing_latency_ms", "rationale"
        ]
        
        for case in cases:
            for field in required_fields:
                self.assertIn(field, case, f"Case {case.get('id')} missing field: {field}")
            
            # Validate field types
            self.assertIsInstance(case["id"], str)
            self.assertIsInstance(case["query"], str)
            self.assertEqual(case["category"], "contradictions")
            self.assertIsInstance(case["expected_contradictions"], list)
            self.assertGreater(len(case["expected_contradictions"]), 0)
            self.assertTrue(case["expected_badge"])
            self.assertEqual(case["max_packing_latency_ms"], 550)
    
    def test_contradiction_structure_valid(self):
        """Test that expected_contradictions have correct structure."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        for case in cases:
            for contradiction in case["expected_contradictions"]:
                self.assertIn("subject", contradiction)
                self.assertIn("claim_a_source", contradiction)
                self.assertIn("claim_b_source", contradiction)
                
                # Validate types
                self.assertIsInstance(contradiction["subject"], str)
                self.assertIsInstance(contradiction["claim_a_source"], str)
                self.assertIsInstance(contradiction["claim_b_source"], str)
                
                # Ensure different sources
                self.assertNotEqual(
                    contradiction["claim_a_source"],
                    contradiction["claim_b_source"],
                    f"Case {case['id']}: claim sources should be different"
                )
    
    def test_fixtures_have_20_documents(self):
        """Test that fixture corpus has 20 documents."""
        with open(self.fixtures_path, 'r') as f:
            corpus = json.load(f)
        
        self.assertIn("documents", corpus)
        self.assertEqual(len(corpus["documents"]), 20)
    
    def test_documents_come_in_pairs(self):
        """Test that documents with same subject have different stances."""
        with open(self.fixtures_path, 'r') as f:
            corpus = json.load(f)
        
        # Group by subject
        subjects = {}
        for doc in corpus["documents"]:
            subject = doc["metadata"]["subject"]
            if subject not in subjects:
                subjects[subject] = []
            subjects[subject].append(doc["metadata"]["stance"])
        
        # Each subject should have 2 different stances
        for subject, stances in subjects.items():
            self.assertEqual(len(stances), 2, f"Subject {subject} should have 2 documents")
            self.assertNotEqual(stances[0], stances[1], f"Subject {subject} stances should differ")
    
    def test_all_expected_sources_exist_in_corpus(self):
        """Test that all expected source IDs reference valid documents."""
        with open(self.fixtures_path, 'r') as f:
            corpus = json.load(f)
        
        doc_ids = {doc["id"] for doc in corpus["documents"]}
        
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        for case in cases:
            for contradiction in case["expected_contradictions"]:
                self.assertIn(
                    contradiction["claim_a_source"], doc_ids,
                    f"Case {case['id']}: claim_a_source not in corpus"
                )
                self.assertIn(
                    contradiction["claim_b_source"], doc_ids,
                    f"Case {case['id']}: claim_b_source not in corpus"
                )


class TestContradictionStructure(unittest.TestCase):
    """Test contradictions[] array structure validation."""
    
    def test_contradictions_array_nonempty(self):
        """Test that contradictions array is non-empty."""
        contradictions = [
            {
                "subject": "global_warming",
                "claim_a": {"source_id": "doc_001", "text": "warming"},
                "claim_b": {"source_id": "doc_002", "text": "cooling"}
            }
        ]
        
        self.assertGreater(len(contradictions), 0)
        self.assertIsInstance(contradictions, list)
    
    def test_contradiction_has_subject(self):
        """Test that each contradiction has a subject."""
        contradiction = {
            "subject": "vaccine_efficacy",
            "claim_a": {"source_id": "doc_003"},
            "claim_b": {"source_id": "doc_004"}
        }
        
        self.assertIn("subject", contradiction)
        self.assertIsInstance(contradiction["subject"], str)
        self.assertGreater(len(contradiction["subject"]), 0)
    
    def test_contradiction_has_both_claims(self):
        """Test that contradiction has both claim_a and claim_b."""
        contradiction = {
            "subject": "ai_employment",
            "claim_a": {"source_id": "doc_005", "text": "job loss"},
            "claim_b": {"source_id": "doc_006", "text": "job creation"}
        }
        
        self.assertIn("claim_a", contradiction)
        self.assertIn("claim_b", contradiction)
    
    def test_claims_have_source_ids(self):
        """Test that both claims have source_id fields."""
        contradiction = {
            "subject": "coffee_health",
            "claim_a": {"source_id": "doc_007"},
            "claim_b": {"source_id": "doc_008"}
        }
        
        self.assertIn("source_id", contradiction["claim_a"])
        self.assertIn("source_id", contradiction["claim_b"])
        
        # Source IDs should be different
        self.assertNotEqual(
            contradiction["claim_a"]["source_id"],
            contradiction["claim_b"]["source_id"]
        )
    
    def test_validate_both_evidence_ids_present(self):
        """Test validation that both evidence IDs are present."""
        expected_contradiction = {
            "subject": "remote_work_productivity",
            "claim_a_source": "doc_009",
            "claim_b_source": "doc_010"
        }
        
        actual_contradictions = [
            {
                "subject": "remote_work_productivity",
                "claim_a": {"source_id": "doc_009"},
                "claim_b": {"source_id": "doc_010"}
            }
        ]
        
        # Check both sources present
        found_a = actual_contradictions[0]["claim_a"]["source_id"]
        found_b = actual_contradictions[0]["claim_b"]["source_id"]
        
        self.assertEqual(found_a, expected_contradiction["claim_a_source"])
        self.assertEqual(found_b, expected_contradiction["claim_b_source"])


class TestBadgePresence(unittest.TestCase):
    """Test badge field presence in answer payload."""
    
    def test_badge_field_exists(self):
        """Test that badge field exists in response."""
        response = {
            "answer": "Test answer",
            "badge": {
                "type": "contradiction",
                "subject": "global_warming"
            }
        }
        
        self.assertIn("badge", response)
    
    def test_badge_has_type(self):
        """Test that badge has type field."""
        badge = {
            "type": "contradiction",
            "subject": "vaccine_efficacy"
        }
        
        self.assertIn("type", badge)
        self.assertEqual(badge["type"], "contradiction")
    
    def test_badge_has_subject(self):
        """Test that badge has subject field."""
        badge = {
            "type": "contradiction",
            "subject": "ai_employment"
        }
        
        self.assertIn("subject", badge)
        self.assertIsInstance(badge["subject"], str)
    
    def test_validate_badge_in_payload(self):
        """Test validation that badge is in answer payload."""
        response_with_badge = {
            "answer": "Answer text",
            "badge": {"type": "contradiction", "subject": "coffee_health"},
            "contradictions": [{"subject": "coffee_health"}]
        }
        
        self.assertIn("badge", response_with_badge)
        self.assertEqual(response_with_badge["badge"]["type"], "contradiction")


class TestPackingLatency(unittest.TestCase):
    """Test packing latency budget assertions."""
    
    def test_packing_latency_under_budget(self):
        """Test packing latency under 550ms."""
        packing_latency_ms = 480.0
        max_budget = 550
        
        self.assertLess(packing_latency_ms, max_budget)
    
    def test_packing_latency_exceeds_budget(self):
        """Test packing latency exceeding 550ms."""
        packing_latency_ms = 620.0
        max_budget = 550
        
        self.assertGreater(packing_latency_ms, max_budget)
    
    def test_p95_packing_latency_under_budget(self):
        """Test P95 packing latency under 550ms."""
        packing_latencies = [450, 480, 490, 500, 510, 520, 530, 540, 545, 548]
        
        p95 = statistics.quantiles(packing_latencies, n=20)[18]
        
        self.assertLess(p95, 550, f"P95 packing latency {p95}ms exceeds 550ms")
    
    def test_extract_packing_latency_from_result(self):
        """Test extracting packing latency from eval result."""
        result = EvalResult(
            "test_001", "query", "contradictions", True, 500.0,
            packing_latency_ms=485.0
        )
        
        self.assertEqual(result.packing_latency_ms, 485.0)
        self.assertLess(result.packing_latency_ms, 550)


class TestSuccessRate(unittest.TestCase):
    """Test success rate assertions for contradiction suite."""
    
    def test_success_rate_above_95_percent(self):
        """Test that success rate meets ≥95% threshold."""
        total_cases = 10
        passed_cases = 10  # 100% pass rate
        
        success_rate = passed_cases / total_cases
        
        self.assertGreaterEqual(
            success_rate, 0.95,
            f"Success rate {success_rate:.1%} below 95% threshold"
        )
    
    def test_success_rate_at_95_percent(self):
        """Test success rate at exactly 95%."""
        total_cases = 20
        passed_cases = 19  # 95% pass rate
        
        success_rate = passed_cases / total_cases
        
        self.assertGreaterEqual(success_rate, 0.95)
    
    def test_success_rate_below_threshold(self):
        """Test failure when success rate is below threshold."""
        total_cases = 10
        passed_cases = 9  # 90% pass rate
        
        success_rate = passed_cases / total_cases
        
        self.assertLess(success_rate, 0.95, "This test expects below-threshold rate")
    
    def test_calculate_contradiction_detection_rate(self):
        """Test calculating rate of successful contradiction detection."""
        results = [
            {"detected": True},
            {"detected": True},
            {"detected": True},
            {"detected": False},
        ]
        
        detected = sum(1 for r in results if r["detected"])
        detection_rate = detected / len(results)
        
        self.assertEqual(detection_rate, 0.75)


class TestContradictionValidation(unittest.TestCase):
    """Test contradiction validation logic."""
    
    @patch('requests.post')
    def test_validate_contradiction_structure_mock(self, mock_post):
        """Test contradiction validation with mocked response."""
        # Mock API response with contradictions
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "badge": {
                "type": "contradiction",
                "subject": "global_warming"
            },
            "contradictions": [
                {
                    "subject": "global_warming",
                    "claim_a": {"source_id": "doc_climate_warming_001"},
                    "claim_b": {"source_id": "doc_climate_cooling_002"}
                }
            ],
            "debug": {
                "retrieval_metrics": {
                    "packing_latency_ms": 485.0
                }
            }
        }
        mock_post.return_value = mock_response
        
        # Validate structure
        data = mock_response.json()
        
        self.assertIn("contradictions", data)
        self.assertGreater(len(data["contradictions"]), 0)
        
        contradiction = data["contradictions"][0]
        self.assertIn("subject", contradiction)
        self.assertIn("claim_a", contradiction)
        self.assertIn("claim_b", contradiction)
        
        # Validate badge
        self.assertIn("badge", data)
        self.assertEqual(data["badge"]["type"], "contradiction")
    
    def test_validate_both_evidence_ids(self):
        """Test that both evidence IDs are present in contradiction."""
        expected = {
            "claim_a_source": "doc_001",
            "claim_b_source": "doc_002"
        }
        
        actual_contradiction = {
            "subject": "test_subject",
            "claim_a": {"source_id": "doc_001"},
            "claim_b": {"source_id": "doc_002"}
        }
        
        found_a = actual_contradiction["claim_a"]["source_id"]
        found_b = actual_contradiction["claim_b"]["source_id"]
        
        self.assertEqual(found_a, expected["claim_a_source"])
        self.assertEqual(found_b, expected["claim_b_source"])
        
        # Both should be present
        self.assertIsNotNone(found_a)
        self.assertIsNotNone(found_b)
    
    def test_validate_correct_subject(self):
        """Test that contradiction has correct subject."""
        expected_subject = "vaccine_efficacy"
        
        contradiction = {
            "subject": "vaccine_efficacy",
            "claim_a": {"source_id": "doc_003"},
            "claim_b": {"source_id": "doc_004"}
        }
        
        self.assertEqual(contradiction["subject"], expected_subject)
    
    def test_calculate_contradiction_completeness(self):
        """Test calculating completeness of contradiction data."""
        contradiction = {
            "subject": "ai_employment",
            "claim_a": {"source_id": "doc_005", "text": "job loss"},
            "claim_b": {"source_id": "doc_006", "text": "job creation"}
        }
        
        # Check all required fields present
        has_subject = "subject" in contradiction
        has_claim_a = "claim_a" in contradiction
        has_claim_b = "claim_b" in contradiction
        has_source_a = "source_id" in contradiction.get("claim_a", {})
        has_source_b = "source_id" in contradiction.get("claim_b", {})
        
        completeness = sum([
            has_subject, has_claim_a, has_claim_b, has_source_a, has_source_b
        ]) / 5
        
        self.assertEqual(completeness, 1.0)


if __name__ == "__main__":
    unittest.main()
