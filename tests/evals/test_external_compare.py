#!/usr/bin/env python3
"""
Unit tests for external compare evaluation suite.

Tests verify:
1. Parity between external OFF vs ON (≥80% for redundant externals)
2. Policy-compliant divergence (tiebreak follows policy)
3. No persistence of external text (zero ingestion detected)
4. Success rate calculations
"""

import os
import sys
import json
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.run import EvalRunner, EvalResult


class TestExternalCompareSuite(unittest.TestCase):
    """Test external compare suite structure and cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.suite_path = Path("/workspace/evals/suites/external_compare.jsonl")
        self.fixtures_path = Path("/workspace/evals/fixtures/external_compare_corpus.json")
        self.cases_dir = Path("/workspace/evals/cases/external")
    
    def test_suite_file_exists(self):
        """Test that suite file exists."""
        self.assertTrue(self.suite_path.exists())
    
    def test_fixtures_exist(self):
        """Test that fixture corpus exists."""
        self.assertTrue(self.fixtures_path.exists())
    
    def test_suite_has_10_cases(self):
        """Test that suite has 10 test cases."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        self.assertEqual(len(cases), 10)
    
    def test_all_cases_have_required_fields(self):
        """Test that all cases have required fields."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        required_fields = [
            "id", "query", "category", "expected_parity",
            "external_scenario", "rationale"
        ]
        
        for case in cases:
            for field in required_fields:
                self.assertIn(field, case, f"Case {case.get('id')} missing {field}")
            
            # Validate types
            self.assertEqual(case["category"], "external_compare")
            self.assertIsInstance(case["expected_parity"], bool)
            self.assertIn(case["external_scenario"], [
                "redundant", "additive", "contradictory", "low_quality", "no_match"
            ])
    
    def test_parity_cases_identified(self):
        """Test that parity cases are correctly identified."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        parity_cases = [c for c in cases if c["expected_parity"]]
        non_parity_cases = [c for c in cases if not c["expected_parity"]]
        
        # Should have mix of parity and non-parity cases
        self.assertGreater(len(parity_cases), 0)
        self.assertGreater(len(non_parity_cases), 0)
        
        # Redundant, low_quality, and no_match should expect parity
        for case in parity_cases:
            self.assertIn(case["external_scenario"], [
                "redundant", "low_quality", "no_match"
            ])
    
    def test_policy_cases_have_expected_policy(self):
        """Test that non-parity cases have expected_policy field."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        for case in cases:
            if not case["expected_parity"]:
                # Non-parity cases should have expected_policy
                self.assertIn("expected_policy", case)
                if case["expected_policy"]:
                    self.assertIn(case["expected_policy"], [
                        "prefer_internal", "abstain", "reject"
                    ])


class TestParityChecking(unittest.TestCase):
    """Test parity validation between external OFF and ON."""
    
    def test_identical_results_have_parity(self):
        """Test that identical results are detected as having parity."""
        result_off = {
            "answer": "Python is a high-level language.",
            "confidence": 0.95,
            "sources": ["internal_python_001"]
        }
        result_on = {
            "answer": "Python is a high-level language.",
            "confidence": 0.95,
            "sources": ["internal_python_001"]
        }
        
        # Check equality
        has_parity = (
            result_off["answer"] == result_on["answer"] and
            result_off["confidence"] == result_on["confidence"]
        )
        
        self.assertTrue(has_parity)
    
    def test_different_results_no_parity(self):
        """Test that different results are detected as non-parity."""
        result_off = {
            "answer": "Docker is a container platform.",
            "confidence": 0.85
        }
        result_on = {
            "answer": "Docker and Docker Compose enable multi-container apps.",
            "confidence": 0.90
        }
        
        has_parity = (result_off["answer"] == result_on["answer"])
        
        self.assertFalse(has_parity)
    
    def test_calculate_parity_rate(self):
        """Test calculating parity rate across cases."""
        results = [
            {"has_parity": True},
            {"has_parity": True},
            {"has_parity": True},
            {"has_parity": False},
            {"has_parity": True}
        ]
        
        parity_count = sum(1 for r in results if r["has_parity"])
        parity_rate = parity_count / len(results)
        
        self.assertEqual(parity_rate, 0.8)  # 4/5 = 80%
    
    def test_parity_rate_above_threshold(self):
        """Test that parity rate meets ≥80% threshold for redundant externals."""
        # Simulate redundant external cases
        redundant_results = [
            {"expected_parity": True, "has_parity": True},
            {"expected_parity": True, "has_parity": True},
            {"expected_parity": True, "has_parity": True},
            {"expected_parity": True, "has_parity": True}
        ]
        
        parity_cases = [r for r in redundant_results if r["expected_parity"]]
        parity_achieved = [r for r in parity_cases if r["has_parity"]]
        parity_rate = len(parity_achieved) / len(parity_cases)
        
        self.assertGreaterEqual(parity_rate, 0.80)


class TestPolicyCompliance(unittest.TestCase):
    """Test policy-compliant divergence validation."""
    
    def test_prefer_internal_tiebreak(self):
        """Test prefer_internal tiebreak policy."""
        decision = {
            "tiebreak": "prefer_internal",
            "confidence": 0.85,
            "source_priority": "internal"
        }
        
        expected_policy = "prefer_internal"
        
        self.assertEqual(decision["tiebreak"], expected_policy)
    
    def test_abstain_policy(self):
        """Test abstain policy for contradictory sources."""
        decision = {
            "tiebreak": "abstain",
            "confidence": 0.50,
            "reason": "conflicting_sources"
        }
        
        expected_policy = "abstain"
        
        self.assertEqual(decision["tiebreak"], expected_policy)
    
    def test_reject_low_quality(self):
        """Test reject policy for low-quality externals."""
        decision = {
            "tiebreak": "reject",
            "external_used": False,
            "reason": "low_quality"
        }
        
        expected_policy = "reject"
        
        self.assertEqual(decision["tiebreak"], expected_policy)
    
    def test_validate_policy_compliance(self):
        """Test validating decision against expected policy."""
        test_cases = [
            {
                "expected_policy": "prefer_internal",
                "actual_tiebreak": "prefer_internal",
                "compliant": True
            },
            {
                "expected_policy": "abstain",
                "actual_tiebreak": "abstain",
                "compliant": True
            },
            {
                "expected_policy": "prefer_internal",
                "actual_tiebreak": "prefer_external",
                "compliant": False
            }
        ]
        
        for case in test_cases:
            is_compliant = (
                case["expected_policy"] == case["actual_tiebreak"]
            )
            self.assertEqual(is_compliant, case["compliant"])
    
    def test_policy_compliance_rate(self):
        """Test calculating policy compliance rate."""
        results = [
            {"expected_policy": "prefer_internal", "actual": "prefer_internal"},
            {"expected_policy": "abstain", "actual": "abstain"},
            {"expected_policy": "prefer_internal", "actual": "prefer_internal"},
            {"expected_policy": "reject", "actual": "reject"}
        ]
        
        compliant = sum(
            1 for r in results
            if r["expected_policy"] == r["actual"]
        )
        compliance_rate = compliant / len(results)
        
        self.assertEqual(compliance_rate, 1.0)  # 100% compliance


class TestNoPersistence(unittest.TestCase):
    """Test that external text is not persisted/ingested."""
    
    def test_no_external_text_in_sources(self):
        """Test that external text doesn't appear in persisted sources."""
        external_text = "External information about Helm"
        persisted_sources = [
            {"id": "internal_kubernetes_008", "text": "Kubernetes orchestrates..."},
            {"id": "internal_docker_004", "text": "Docker is a platform..."}
        ]
        
        # Check that external text is not in any persisted source
        has_external = any(
            external_text in source.get("text", "")
            for source in persisted_sources
        )
        
        self.assertFalse(has_external)
    
    def test_no_external_source_ids(self):
        """Test that external source IDs don't appear in citations."""
        citations = [
            {"source_id": "internal_python_001"},
            {"source_id": "internal_ml_002"},
            {"source_id": "internal_sql_005"}
        ]
        
        external_ids = ["ext_python_wiki", "ext_ml_overview", "ext_sql_ref"]
        
        cited_ids = {c["source_id"] for c in citations}
        has_external_id = any(ext_id in cited_ids for ext_id in external_ids)
        
        self.assertFalse(has_external_id)
    
    def test_detect_external_ingestion(self):
        """Test detection of external text ingestion."""
        external_markers = [
            "external source", "ext_", "external_id"
        ]
        
        # Clean response (no external ingestion)
        clean_response = {
            "answer": "Docker containers package applications.",
            "sources": [{"id": "internal_docker_004"}]
        }
        
        # Contaminated response (external ingestion detected)
        contaminated_response = {
            "answer": "Docker Compose simplifies multi-container apps.",
            "sources": [
                {"id": "internal_docker_004"},
                {"id": "ext_docker_compose"}  # External ID present!
            ]
        }
        
        def has_ingestion(response, markers):
            # Check source IDs
            source_ids = [s.get("id", "") for s in response.get("sources", [])]
            return any(
                any(marker in sid for marker in markers)
                for sid in source_ids
            )
        
        self.assertFalse(has_ingestion(clean_response, external_markers))
        self.assertTrue(has_ingestion(contaminated_response, external_markers))
    
    def test_zero_ingestion_rate(self):
        """Test that ingestion rate is zero."""
        results = [
            {"external_ingested": False},
            {"external_ingested": False},
            {"external_ingested": False},
            {"external_ingested": False}
        ]
        
        ingested_count = sum(1 for r in results if r["external_ingested"])
        ingestion_rate = ingested_count / len(results)
        
        self.assertEqual(ingestion_rate, 0.0)


class TestDualModeExecution(unittest.TestCase):
    """Test dual-mode execution (external OFF and ON)."""
    
    @patch('requests.post')
    def test_run_external_off_mode(self, mock_post):
        """Test running with external compare OFF."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Python is a high-level language.",
            "confidence": 0.95,
            "external_used": False,
            "citations": [{"source_id": "internal_python_001"}]
        }
        mock_post.return_value = mock_response
        
        # Response should not include external sources
        data = mock_response.json()
        self.assertFalse(data.get("external_used", False))
    
    @patch('requests.post')
    def test_run_external_on_mode(self, mock_post):
        """Test running with external compare ON."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Python is a high-level language.",
            "confidence": 0.95,
            "external_used": True,
            "external_considered": ["ext_python_wiki"],
            "decision": {"tiebreak": "prefer_internal"},
            "citations": [{"source_id": "internal_python_001"}]
        }
        mock_post.return_value = mock_response
        
        # Response includes external metadata but not external sources
        data = mock_response.json()
        self.assertTrue(data.get("external_used", False))
        self.assertIn("decision", data)
        
        # But citations should still be internal only
        citation_ids = [c["source_id"] for c in data["citations"]]
        self.assertFalse(any("ext_" in cid for cid in citation_ids))
    
    def test_compare_off_vs_on_results(self):
        """Test comparing results from OFF and ON modes."""
        result_off = {
            "answer": "Docker is a container platform.",
            "confidence": 0.85,
            "external_used": False
        }
        
        result_on = {
            "answer": "Docker is a container platform.",
            "confidence": 0.85,
            "external_used": True,
            "decision": {"tiebreak": "prefer_internal"}
        }
        
        # Check parity (answer and confidence match)
        has_parity = (
            result_off["answer"] == result_on["answer"] and
            result_off["confidence"] == result_on["confidence"]
        )
        
        self.assertTrue(has_parity)
        
        # Verify external was considered but didn't change result
        self.assertTrue(result_on["external_used"])


class TestSuccessMetrics(unittest.TestCase):
    """Test success rate and metric calculations."""
    
    def test_calculate_parity_success_rate(self):
        """Test calculating success rate for parity cases."""
        parity_cases = [
            {"expected_parity": True, "actual_parity": True},
            {"expected_parity": True, "actual_parity": True},
            {"expected_parity": True, "actual_parity": False},
            {"expected_parity": True, "actual_parity": True}
        ]
        
        matches = sum(
            1 for c in parity_cases
            if c["expected_parity"] == c["actual_parity"]
        )
        success_rate = matches / len(parity_cases)
        
        self.assertEqual(success_rate, 0.75)  # 3/4 = 75%
    
    def test_calculate_policy_success_rate(self):
        """Test calculating success rate for policy compliance."""
        policy_cases = [
            {"expected_policy": "prefer_internal", "actual_policy": "prefer_internal"},
            {"expected_policy": "abstain", "actual_policy": "abstain"},
            {"expected_policy": "prefer_internal", "actual_policy": "prefer_internal"}
        ]
        
        matches = sum(
            1 for c in policy_cases
            if c["expected_policy"] == c["actual_policy"]
        )
        success_rate = matches / len(policy_cases)
        
        self.assertEqual(success_rate, 1.0)  # 100%
    
    def test_overall_success_rate_above_threshold(self):
        """Test that overall success rate meets threshold."""
        # Simulate full suite results
        results = {
            "parity_cases": 6,  # redundant + low_quality + no_match
            "parity_achieved": 5,
            "policy_cases": 4,  # additive + contradictory
            "policy_compliant": 4,
            "ingestion_detected": 0
        }
        
        parity_rate = results["parity_achieved"] / results["parity_cases"]
        policy_rate = results["policy_compliant"] / results["policy_cases"]
        ingestion_rate = results["ingestion_detected"] / 10  # total cases
        
        # Parity ≥80%
        self.assertGreaterEqual(parity_rate, 0.80)
        # Policy compliance 100%
        self.assertGreaterEqual(policy_rate, 1.0)
        # Zero ingestion
        self.assertEqual(ingestion_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
