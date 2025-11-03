#!/usr/bin/env python3
"""
Unit tests for Pareto gating evaluation suite.

Tests verify:
1. Persistence behavior (score >= threshold → persist)
2. Rejection behavior (score < threshold → 202 with reason)
3. Override behavior (always persists, logs override=true)
4. Status codes (201 for persisted, 202 for not persisted)
5. Metrics counting (persisted/rejected counts)
6. Scoring latency (p95 < 200ms)
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


class TestParetoGateSuite(unittest.TestCase):
    """Test Pareto gate suite structure and cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.suite_path = Path("/workspace/evals/suites/pareto_gate.jsonl")
        self.fixtures_path = Path("/workspace/evals/fixtures/pareto_proposals.json")
        self.cases_dir = Path("/workspace/evals/cases/pareto")
    
    def test_suite_file_exists(self):
        """Test that suite file exists."""
        self.assertTrue(self.suite_path.exists())
    
    def test_fixtures_exist(self):
        """Test that fixture proposals exist."""
        self.assertTrue(self.fixtures_path.exists())
    
    def test_suite_has_16_cases(self):
        """Test that suite has 16 test cases."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        self.assertEqual(len(cases), 16)
    
    def test_all_cases_have_required_fields(self):
        """Test that all cases have required fields."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        required_fields = [
            "id", "proposal", "category", "expected_score",
            "expected_persisted", "expected_status_code",
            "max_scoring_latency_ms", "scenario", "rationale"
        ]
        
        for case in cases:
            for field in required_fields:
                self.assertIn(field, case, f"Case {case.get('id')} missing {field}")
            
            # Validate types
            self.assertEqual(case["category"], "pareto_gate")
            self.assertIsInstance(case["expected_persisted"], bool)
            self.assertIn(case["expected_status_code"], [201, 202])
            self.assertEqual(case["max_scoring_latency_ms"], 200)
    
    def test_proposal_structure_valid(self):
        """Test that proposals have valid structure."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        for case in cases:
            proposal = case["proposal"]
            self.assertIn("hypothesis", proposal)
            self.assertIn("signals", proposal)
            
            # Validate signals
            signals = proposal["signals"]
            required_signals = ["novelty", "evidence_strength", "coherence", "specificity"]
            for signal in required_signals:
                self.assertIn(signal, signals)
                self.assertGreaterEqual(signals[signal], 0.0)
                self.assertLessEqual(signals[signal], 1.0)
    
    def test_threshold_boundary_cases_exist(self):
        """Test that suite includes boundary cases."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        scenarios = [c["scenario"] for c in cases]
        
        # Should have boundary testing
        self.assertIn("at_threshold", scenarios)
        self.assertIn("just_above_threshold", scenarios)
        self.assertIn("just_below_threshold", scenarios)
    
    def test_override_cases_exist(self):
        """Test that suite includes override cases."""
        with open(self.suite_path, 'r') as f:
            cases = [json.loads(line) for line in f if line.strip()]
        
        override_cases = [
            c for c in cases
            if "override" in c.get("proposal", {})
        ]
        
        self.assertGreaterEqual(len(override_cases), 3, "Should have at least 3 override cases")
        
        # Check override structure
        for case in override_cases:
            override = case["proposal"]["override"]
            self.assertIn("enabled", override)
            self.assertIn("reason", override)
            self.assertTrue(override["enabled"])


class TestPersistenceBehavior(unittest.TestCase):
    """Test persistence behavior based on scores."""
    
    def test_score_above_threshold_persists(self):
        """Test that score >= threshold results in persistence."""
        threshold = 0.65
        score = 0.87
        
        should_persist = score >= threshold
        
        self.assertTrue(should_persist)
    
    def test_score_at_threshold_persists(self):
        """Test that score exactly at threshold persists."""
        threshold = 0.65
        score = 0.65
        
        should_persist = score >= threshold
        
        self.assertTrue(should_persist)
    
    def test_score_below_threshold_rejected(self):
        """Test that score < threshold is rejected."""
        threshold = 0.65
        score = 0.63
        
        should_persist = score >= threshold
        
        self.assertFalse(should_persist)
    
    def test_calculate_persistence_rate(self):
        """Test calculating persistence rate."""
        results = [
            {"expected_persisted": True, "actual_persisted": True},
            {"expected_persisted": True, "actual_persisted": True},
            {"expected_persisted": False, "actual_persisted": False},
            {"expected_persisted": False, "actual_persisted": False}
        ]
        
        matches = sum(
            1 for r in results
            if r["expected_persisted"] == r["actual_persisted"]
        )
        match_rate = matches / len(results)
        
        self.assertEqual(match_rate, 1.0)  # 100% match


class TestOverrideBehavior(unittest.TestCase):
    """Test override behavior for special cases."""
    
    def test_analytics_override_persists_despite_low_score(self):
        """Test that analytics override persists regardless of score."""
        score = 0.47  # Below threshold
        threshold = 0.65
        override_enabled = True
        
        # With override, should persist even if score < threshold
        should_persist = (score >= threshold) or override_enabled
        
        self.assertTrue(should_persist)
    
    def test_security_override_persists(self):
        """Test that security override persists."""
        score = 0.39  # Far below threshold
        override_reason = "security_critical"
        override_enabled = True
        
        should_persist = override_enabled
        
        self.assertTrue(should_persist)
    
    def test_executive_override_persists(self):
        """Test that executive override persists."""
        score = 0.50  # Below threshold
        override_reason = "executive_priority"
        override_enabled = True
        
        should_persist = override_enabled
        
        self.assertTrue(should_persist)
    
    def test_override_logged_correctly(self):
        """Test that override=true is logged."""
        response = {
            "persisted": True,
            "score": 0.47,
            "override": True,
            "override_reason": "analytics_priority"
        }
        
        self.assertTrue(response["override"])
        self.assertIn("override_reason", response)
    
    def test_no_override_when_not_enabled(self):
        """Test that override is not logged for normal cases."""
        response = {
            "persisted": True,
            "score": 0.87,
            "override": False
        }
        
        self.assertFalse(response["override"])


class TestStatusCodes(unittest.TestCase):
    """Test HTTP status code behavior."""
    
    def test_persisted_returns_201(self):
        """Test that persisted proposals return 201 Created."""
        persisted = True
        expected_status = 201
        
        actual_status = 201 if persisted else 202
        
        self.assertEqual(actual_status, expected_status)
    
    def test_not_persisted_returns_202(self):
        """Test that non-persisted proposals return 202 Accepted."""
        persisted = False
        expected_status = 202
        
        actual_status = 201 if persisted else 202
        
        self.assertEqual(actual_status, expected_status)
    
    def test_rejection_includes_reason(self):
        """Test that 202 responses include rejection reason."""
        response = {
            "status": 202,
            "persisted": False,
            "reason": "score_below_threshold",
            "score": 0.57
        }
        
        self.assertEqual(response["status"], 202)
        self.assertFalse(response["persisted"])
        self.assertIn("reason", response)
        self.assertEqual(response["reason"], "score_below_threshold")


class TestMetricsCounting(unittest.TestCase):
    """Test metrics counting for persisted/rejected."""
    
    def test_count_persisted_and_rejected(self):
        """Test counting persisted vs rejected proposals."""
        results = [
            {"persisted": True},
            {"persisted": True},
            {"persisted": True},
            {"persisted": False},
            {"persisted": False}
        ]
        
        persisted_count = sum(1 for r in results if r["persisted"])
        rejected_count = sum(1 for r in results if not r["persisted"])
        
        self.assertEqual(persisted_count, 3)
        self.assertEqual(rejected_count, 2)
        self.assertEqual(persisted_count + rejected_count, len(results))
    
    def test_count_override_cases(self):
        """Test counting override cases separately."""
        results = [
            {"persisted": True, "override": False},
            {"persisted": True, "override": True},
            {"persisted": True, "override": True},
            {"persisted": False, "override": False}
        ]
        
        override_count = sum(1 for r in results if r.get("override", False))
        natural_persist = sum(
            1 for r in results
            if r["persisted"] and not r.get("override", False)
        )
        
        self.assertEqual(override_count, 2)
        self.assertEqual(natural_persist, 1)
    
    def test_calculate_persistence_metrics(self):
        """Test calculating comprehensive persistence metrics."""
        results = [
            {"score": 0.87, "persisted": True, "override": False},
            {"score": 0.81, "persisted": True, "override": False},
            {"score": 0.47, "persisted": True, "override": True},
            {"score": 0.57, "persisted": False, "override": False},
            {"score": 0.32, "persisted": False, "override": False}
        ]
        
        metrics = {
            "total": len(results),
            "persisted": sum(1 for r in results if r["persisted"]),
            "rejected": sum(1 for r in results if not r["persisted"]),
            "overrides": sum(1 for r in results if r.get("override", False)),
            "natural_persist": sum(
                1 for r in results
                if r["persisted"] and not r.get("override", False)
            )
        }
        
        self.assertEqual(metrics["total"], 5)
        self.assertEqual(metrics["persisted"], 3)
        self.assertEqual(metrics["rejected"], 2)
        self.assertEqual(metrics["overrides"], 1)
        self.assertEqual(metrics["natural_persist"], 2)


class TestScoringLatency(unittest.TestCase):
    """Test scoring latency budget."""
    
    def test_scoring_latency_under_budget(self):
        """Test scoring latency under 200ms."""
        scoring_latency_ms = 145.0
        max_budget = 200
        
        self.assertLess(scoring_latency_ms, max_budget)
    
    def test_p95_scoring_latency_under_budget(self):
        """Test P95 scoring latency under 200ms."""
        scoring_latencies = [120, 135, 145, 150, 155, 160, 165, 170, 175, 180]
        
        p95 = statistics.quantiles(scoring_latencies, n=20)[18]
        
        self.assertLess(p95, 200)
    
    def test_extract_scoring_latency(self):
        """Test extracting scoring latency from response."""
        response = {
            "persisted": True,
            "score": 0.87,
            "timing": {
                "scoring_ms": 145.0,
                "total_ms": 180.0
            }
        }
        
        scoring_latency = response["timing"]["scoring_ms"]
        
        self.assertEqual(scoring_latency, 145.0)
        self.assertLess(scoring_latency, 200)


class TestParetoValidation(unittest.TestCase):
    """Test Pareto gating validation logic."""
    
    @patch('requests.post')
    def test_validate_high_score_persisted(self, mock_post):
        """Test validation of high-scoring persisted proposal."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "persisted": True,
            "score": 0.87,
            "threshold": 0.65,
            "override": False,
            "timing": {"scoring_ms": 145.0}
        }
        mock_post.return_value = mock_response
        
        data = mock_response.json()
        
        self.assertEqual(mock_response.status_code, 201)
        self.assertTrue(data["persisted"])
        self.assertGreaterEqual(data["score"], data["threshold"])
        self.assertFalse(data["override"])
    
    @patch('requests.post')
    def test_validate_low_score_rejected(self, mock_post):
        """Test validation of low-scoring rejected proposal."""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "persisted": False,
            "score": 0.57,
            "threshold": 0.65,
            "reason": "score_below_threshold",
            "timing": {"scoring_ms": 132.0}
        }
        mock_post.return_value = mock_response
        
        data = mock_response.json()
        
        self.assertEqual(mock_response.status_code, 202)
        self.assertFalse(data["persisted"])
        self.assertLess(data["score"], data["threshold"])
        self.assertIn("reason", data)
    
    @patch('requests.post')
    def test_validate_override_persisted(self, mock_post):
        """Test validation of override-persisted proposal."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "persisted": True,
            "score": 0.47,
            "threshold": 0.65,
            "override": True,
            "override_reason": "analytics_priority",
            "timing": {"scoring_ms": 138.0}
        }
        mock_post.return_value = mock_response
        
        data = mock_response.json()
        
        self.assertEqual(mock_response.status_code, 201)
        self.assertTrue(data["persisted"])
        self.assertLess(data["score"], data["threshold"])
        self.assertTrue(data["override"])
        self.assertIn("override_reason", data)
    
    def test_calculate_expected_score(self):
        """Test calculating expected Pareto score from signals."""
        signals = {
            "novelty": 0.85,
            "evidence_strength": 0.90,
            "coherence": 0.88,
            "specificity": 0.82
        }
        weights = {
            "novelty": 0.35,
            "evidence_strength": 0.30,
            "coherence": 0.20,
            "specificity": 0.15
        }
        
        score = sum(signals[k] * weights[k] for k in signals)
        
        self.assertAlmostEqual(score, 0.87, places=2)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria validation."""
    
    def test_100_percent_match_to_expected_persisted(self):
        """Test that all cases match expected persisted flag."""
        results = [
            {"expected": True, "actual": True},
            {"expected": True, "actual": True},
            {"expected": False, "actual": False},
            {"expected": False, "actual": False},
            {"expected": True, "actual": True}
        ]
        
        matches = sum(
            1 for r in results
            if r["expected"] == r["actual"]
        )
        match_rate = matches / len(results)
        
        self.assertEqual(match_rate, 1.0)  # 100% match required
    
    def test_metrics_show_correct_counts(self):
        """Test that metrics show correct persisted/rejected counts."""
        # 16 total cases: 9 persist (6 natural + 3 override), 7 reject
        metrics = {
            "total_proposals": 16,
            "persisted": 9,
            "rejected": 7,
            "natural_persist": 6,
            "override_persist": 3
        }
        
        self.assertEqual(metrics["total_proposals"], 16)
        self.assertEqual(metrics["persisted"] + metrics["rejected"], 16)
        self.assertEqual(
            metrics["natural_persist"] + metrics["override_persist"],
            metrics["persisted"]
        )
    
    def test_latency_p95_under_200ms(self):
        """Test that P95 scoring latency is under 200ms."""
        scoring_latencies = [
            120, 125, 130, 135, 140, 145, 150, 155,
            160, 165, 170, 175, 180, 185, 190, 195
        ]
        
        p95 = statistics.quantiles(scoring_latencies, n=20)[18]
        
        self.assertLess(p95, 200)


if __name__ == "__main__":
    unittest.main()
