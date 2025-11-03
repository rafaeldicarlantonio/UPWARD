#!/usr/bin/env python3
"""
Unit tests for role variant evaluation cases.

Tests:
1. Role variants load correctly
2. General role applies redaction expectations
3. Pro role has no redaction expectations
4. Both roles produce correct verdicts
5. Differences are documented and expected
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.run import EvalRunner, EvalResult


class TestRoleVariantCases(unittest.TestCase):
    """Test role variant test case structure."""
    
    def test_implicate_general_case_loads(self):
        """Test that general role implicate case loads correctly."""
        case_path = Path("/workspace/evals/cases/implicate_general/case_001_attention_to_bert_general.json")
        
        self.assertTrue(case_path.exists())
        
        with open(case_path) as f:
            case = json.load(f)
        
        self.assertEqual(case["id"], "implicate_001_general")
        self.assertEqual(case["role"], "general")
        self.assertTrue(case["redaction_expected"])
        self.assertEqual(case["category"], "implicate_lift")
    
    def test_implicate_pro_case_loads(self):
        """Test that pro role implicate case loads correctly."""
        case_path = Path("/workspace/evals/cases/implicate_pro/case_001_attention_to_bert_pro.json")
        
        self.assertTrue(case_path.exists())
        
        with open(case_path) as f:
            case = json.load(f)
        
        self.assertEqual(case["id"], "implicate_001_pro")
        self.assertEqual(case["role"], "researcher")
        self.assertFalse(case["redaction_expected"])
        self.assertEqual(case["category"], "implicate_lift")
    
    def test_contradiction_general_case_loads(self):
        """Test that general role contradiction case loads correctly."""
        case_path = Path("/workspace/evals/cases/contradictions_general/case_001_climate_trends_general.json")
        
        self.assertTrue(case_path.exists())
        
        with open(case_path) as f:
            case = json.load(f)
        
        self.assertEqual(case["id"], "contradiction_001_general")
        self.assertEqual(case["role"], "general")
        self.assertTrue(case["redaction_expected"])
        self.assertEqual(case["category"], "contradictions")
    
    def test_contradiction_pro_case_loads(self):
        """Test that pro role contradiction case loads correctly."""
        case_path = Path("/workspace/evals/cases/contradictions_pro/case_001_climate_trends_pro.json")
        
        self.assertTrue(case_path.exists())
        
        with open(case_path) as f:
            case = json.load(f)
        
        self.assertEqual(case["id"], "contradiction_001_pro")
        self.assertEqual(case["role"], "researcher")
        self.assertFalse(case["redaction_expected"])
        self.assertEqual(case["category"], "contradictions")
    
    def test_role_variant_suite_exists(self):
        """Test that role variants suite file exists."""
        suite_path = Path("/workspace/evals/suites/role_variants.jsonl")
        
        self.assertTrue(suite_path.exists())
        
        # Count entries
        with open(suite_path) as f:
            lines = [line for line in f if line.strip()]
        
        # Should have 10 entries (5 pairs)
        self.assertEqual(len(lines), 10)


class TestRoleInEvalRunner(unittest.TestCase):
    """Test role parameter handling in EvalRunner."""
    
    @patch('requests.post')
    def test_runner_uses_role_from_case(self, mock_post):
        """Test that runner uses role from test case."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [{"source_id": "doc_001"}],
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001", "doc_002"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "test_001",
            "query": "Test query",
            "category": "implicate_lift",
            "role": "general",  # Explicit role
            "expected_source_ids": ["doc_001"],
            "expected_in_top_k": 8
        }
        
        result = runner.run_single_case(case)
        
        # Verify role was passed to API
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["role"], "general")
        
        # Verify role stored in result
        self.assertEqual(result.role, "general")
    
    @patch('requests.post')
    def test_runner_defaults_to_researcher(self, mock_post):
        """Test that runner defaults to researcher role if not specified."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [{"source_id": "doc_001"}],
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001", "doc_002"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "test_001",
            "query": "Test query",
            "category": "implicate_lift",
            # No role specified
            "expected_source_ids": ["doc_001"],
            "expected_in_top_k": 8
        }
        
        result = runner.run_single_case(case)
        
        # Verify defaults to researcher
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["role"], "researcher")
        
        # Verify role stored in result
        self.assertEqual(result.role, "researcher")


class TestRedactionExpectations(unittest.TestCase):
    """Test redaction expectation handling."""
    
    @patch('requests.post')
    def test_general_role_expects_redaction(self, mock_post):
        """Test that general role cases expect redaction."""
        # Mock API response with redaction
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [{"source_id": "doc_001"}],
            "redacted": True,  # Indicates redaction occurred
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001", "doc_002"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "test_general_001",
            "query": "Test query",
            "category": "implicate_lift",
            "role": "general",
            "redaction_expected": True,
            "expected_source_ids": ["doc_001"],
            "expected_in_top_k": 8
        }
        
        result = runner.run_single_case(case)
        
        # Verify redaction expectations
        self.assertTrue(result.redaction_expected)
        self.assertTrue(result.redaction_detected)
    
    @patch('requests.post')
    def test_pro_role_no_redaction(self, mock_post):
        """Test that pro role cases don't expect redaction."""
        # Mock API response without redaction
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer with full context",
            "citations": [{"source_id": "doc_001"}],
            "redacted": False,  # No redaction
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001", "doc_002"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "test_pro_001",
            "query": "Test query",
            "category": "implicate_lift",
            "role": "researcher",
            "redaction_expected": False,
            "expected_source_ids": ["doc_001"],
            "expected_in_top_k": 8
        }
        
        result = runner.run_single_case(case)
        
        # Verify no redaction expectations
        self.assertFalse(result.redaction_expected)
        self.assertFalse(result.redaction_detected)


class TestRoleVariantCorrectness(unittest.TestCase):
    """Test that both roles produce correct verdicts."""
    
    @patch('requests.post')
    def test_both_roles_retrieve_same_docs(self, mock_post):
        """Test that general and pro roles retrieve same documents."""
        # Same response for both roles
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [{"source_id": "doc_001"}, {"source_id": "doc_002"}],
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001", "doc_002", "doc_003"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        # General role case
        general_case = {
            "id": "test_general",
            "query": "Test query",
            "category": "implicate_lift",
            "role": "general",
            "redaction_expected": True,
            "expected_source_ids": ["doc_001", "doc_002"],
            "expected_in_top_k": 8
        }
        
        # Pro role case (same query)
        pro_case = {
            "id": "test_pro",
            "query": "Test query",
            "category": "implicate_lift",
            "role": "researcher",
            "redaction_expected": False,
            "expected_source_ids": ["doc_001", "doc_002"],
            "expected_in_top_k": 8
        }
        
        general_result = runner.run_single_case(general_case)
        pro_result = runner.run_single_case(pro_case)
        
        # Both should pass with same docs
        self.assertTrue(general_result.passed)
        self.assertTrue(pro_result.passed)
        
        # Should retrieve same docs
        self.assertEqual(general_result.retrieved_source_ids, pro_result.retrieved_source_ids)
    
    @patch('requests.post')
    def test_both_roles_detect_contradictions(self, mock_post):
        """Test that both roles detect same contradictions."""
        # Mock response with contradiction
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [{"source_id": "doc_001"}],
            "contradictions": [
                {
                    "subject": "test_subject",
                    "claim_a": {"source_id": "doc_001", "text": "claim A"},
                    "claim_b": {"source_id": "doc_002", "text": "claim B"}
                }
            ],
            "badge": {"type": "contradiction"},
            "debug": {
                "retrieval_metrics": {}
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        # General role case
        general_case = {
            "id": "test_general",
            "query": "Test query",
            "category": "contradictions",
            "role": "general",
            "redaction_expected": True,
            "expected_contradictions": [],  # Don't require specific contradictions for this test
            "expected_badge": True,
            "max_packing_latency_ms": 550
        }
        
        # Pro role case
        pro_case = {
            "id": "test_pro",
            "query": "Test query",
            "category": "contradictions",
            "role": "researcher",
            "redaction_expected": False,
            "expected_contradictions": [],  # Don't require specific contradictions for this test
            "expected_badge": True,
            "max_packing_latency_ms": 550
        }
        
        general_result = runner.run_single_case(general_case)
        pro_result = runner.run_single_case(pro_case)
        
        # Both should pass
        self.assertTrue(general_result.passed)
        self.assertTrue(pro_result.passed)
        
        # Should detect same contradictions
        self.assertEqual(general_result.contradictions_found, pro_result.contradictions_found)
        self.assertEqual(general_result.has_badge, pro_result.has_badge)


class TestRolePrintOutput(unittest.TestCase):
    """Test that role is displayed in output."""
    
    @patch('requests.post')
    def test_role_printed_in_output(self, mock_post):
        """Test that role is shown in run output."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "citations": [{"source_id": "doc_001"}],
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "test_001",
            "query": "Test query with specific role",
            "category": "implicate_lift",
            "role": "general",
            "expected_source_ids": ["doc_001"],
            "expected_in_top_k": 8
        }
        
        # Capture print output
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            result = runner.run_single_case(case)
        
        output = f.getvalue()
        
        # Verify role is in output
        self.assertIn("[role=general]", output)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria for role variants."""
    
    @patch('requests.post')
    def test_general_runs_pass_with_redaction(self, mock_post):
        """Test that general role runs pass with redactions applied."""
        # Mock response with redaction but correct results
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer [REDACTED]",
            "citations": [{"source_id": "doc_001"}],
            "redacted": True,
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001", "doc_002"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "general_acceptance",
            "query": "Test query",
            "category": "implicate_lift",
            "role": "general",
            "redaction_expected": True,
            "expected_source_ids": ["doc_001"],
            "expected_in_top_k": 8
        }
        
        result = runner.run_single_case(case)
        
        # General role should pass with redaction
        self.assertTrue(result.passed)
        self.assertTrue(result.redaction_expected)
        self.assertTrue(result.redaction_detected)
    
    @patch('requests.post')
    def test_pro_runs_pass_with_full_context(self, mock_post):
        """Test that pro role runs pass with full context."""
        # Mock response with full context
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer with full proprietary details",
            "citations": [{"source_id": "doc_001"}],
            "redacted": False,
            "debug": {
                "retrieval_metrics": {
                    "retrieved_ids": ["doc_001", "doc_002"]
                }
            }
        }
        mock_post.return_value = mock_response
        
        runner = EvalRunner(suite_name="test_suite", enforce_latency_budgets=False)
        
        case = {
            "id": "pro_acceptance",
            "query": "Test query",
            "category": "implicate_lift",
            "role": "researcher",
            "redaction_expected": False,
            "expected_source_ids": ["doc_001"],
            "expected_in_top_k": 8
        }
        
        result = runner.run_single_case(case)
        
        # Pro role should pass with full context
        self.assertTrue(result.passed)
        self.assertFalse(result.redaction_expected)
        self.assertFalse(result.redaction_detected)
    
    def test_differences_are_expected(self):
        """Test that redaction differences are expected and documented."""
        # Load general and pro variants
        with open("/workspace/evals/cases/implicate_general/case_001_attention_to_bert_general.json") as f:
            general_case = json.load(f)
        
        with open("/workspace/evals/cases/implicate_pro/case_001_attention_to_bert_pro.json") as f:
            pro_case = json.load(f)
        
        # Verify expected differences
        self.assertNotEqual(general_case["id"], pro_case["id"])
        self.assertNotEqual(general_case["role"], pro_case["role"])
        self.assertNotEqual(general_case["redaction_expected"], pro_case["redaction_expected"])
        
        # Verify same query/expectations
        self.assertEqual(general_case["query"], pro_case["query"])
        self.assertEqual(general_case["expected_source_ids"], pro_case["expected_source_ids"])
        
        # Verify both have rationale documenting the difference
        self.assertIn("rationale", general_case)
        self.assertIn("rationale", pro_case)
        self.assertIn("redaction", general_case["rationale"].lower())


if __name__ == "__main__":
    unittest.main()
