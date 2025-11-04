#!/usr/bin/env python3
"""
Unit tests for reviewer budget enforcement.

Tests:
1. Budget enforcement and timeout
2. Circuit breaker integration
3. Skip annotation with reasons
4. Optional score fields
5. Fast path includes review
6. Slow path skips review
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.reviewer import (
    AnswerReviewer,
    ReviewResult,
    get_reviewer,
    review_answer_with_budget
)
from core.circuit import CircuitState, reset_all_circuit_breakers


class TestReviewResult(unittest.TestCase):
    """Test ReviewResult dataclass."""
    
    def test_review_result_not_skipped(self):
        """Test ReviewResult when review completed."""
        result = ReviewResult(
            skipped=False,
            score=0.85,
            confidence=0.9,
            flags={"quality": "high"},
            details={"answer_length": 150},
            latency_ms=120.0
        )
        
        self.assertFalse(result.skipped)
        self.assertEqual(result.score, 0.85)
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.flags["quality"], "high")
        self.assertEqual(result.latency_ms, 120.0)
    
    def test_review_result_skipped(self):
        """Test ReviewResult when review skipped."""
        result = ReviewResult(
            skipped=True,
            skip_reason="timeout_exceeded: 500ms",
            latency_ms=520.0
        )
        
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "timeout_exceeded: 500ms")
        self.assertIsNone(result.score)
        self.assertIsNone(result.confidence)
    
    def test_to_dict_with_scores(self):
        """Test to_dict includes scores when not skipped."""
        result = ReviewResult(
            skipped=False,
            score=0.75,
            confidence=0.85,
            latency_ms=100.0
        )
        
        d = result.to_dict()
        
        self.assertFalse(d["skipped"])
        self.assertEqual(d["score"], 0.75)
        self.assertEqual(d["confidence"], 0.85)
        self.assertEqual(d["latency_ms"], 100.0)
    
    def test_to_dict_skipped_excludes_scores(self):
        """Test to_dict excludes scores when skipped."""
        result = ReviewResult(
            skipped=True,
            skip_reason="timeout",
            score=0.5,  # Should be excluded
            latency_ms=100.0
        )
        
        d = result.to_dict()
        
        self.assertTrue(d["skipped"])
        self.assertEqual(d["skip_reason"], "timeout")
        self.assertNotIn("score", d)
        self.assertNotIn("confidence", d)


class TestReviewerConfiguration(unittest.TestCase):
    """Test reviewer configuration."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_reviewer_enabled_by_default(self):
        """Test reviewer is enabled by default."""
        config = {"PERF_REVIEWER_ENABLED": True}
        
        reviewer = AnswerReviewer(config=config)
        self.assertTrue(reviewer.is_enabled())
    
    def test_reviewer_can_be_disabled(self):
        """Test reviewer can be disabled."""
        config = {"PERF_REVIEWER_ENABLED": False}
        
        reviewer = AnswerReviewer(config=config)
        self.assertFalse(reviewer.is_enabled())
    
    def test_default_budget_is_500ms(self):
        """Test default budget is 500ms."""
        config = {}
        
        reviewer = AnswerReviewer(config=config)
        self.assertEqual(reviewer.get_budget_ms(), 500.0)
    
    def test_custom_budget(self):
        """Test custom budget can be set."""
        config = {"PERF_REVIEWER_BUDGET_MS": 300}
        
        reviewer = AnswerReviewer(config=config)
        self.assertEqual(reviewer.get_budget_ms(), 300.0)


class TestReviewerSkipping(unittest.TestCase):
    """Test reviewer skip conditions."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_skips_when_disabled(self):
        """Test reviewer skips when disabled."""
        config = {"PERF_REVIEWER_ENABLED": False}
        
        reviewer = AnswerReviewer(config=config)
        result = reviewer.review_answer("Test answer")
        
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "reviewer_disabled")
        self.assertIsNone(result.score)
    
    def test_skips_when_circuit_breaker_open(self):
        """Test reviewer skips when circuit breaker is open."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 500
        }
        
        reviewer = AnswerReviewer(config=config)
        
        # Open the circuit breaker by failing multiple times
        def failing_review(*args, **kwargs):
            raise Exception("Service unavailable")
        
        with patch.object(reviewer, '_perform_review', side_effect=failing_review):
            for i in range(5):
                try:
                    reviewer.review_answer("Test")
                except:
                    pass
        
        # Circuit should be open now
        self.assertEqual(reviewer.circuit_breaker.get_state(), CircuitState.OPEN)
        
        # Next call should skip
        result = reviewer.review_answer("Test answer")
        
        self.assertTrue(result.skipped)
        self.assertIn("circuit_breaker_open", result.skip_reason)
    
    def test_skips_on_timeout(self):
        """Test reviewer skips when timeout exceeded."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 100  # Very short budget
        }
        
        reviewer = AnswerReviewer(config=config)
        
        # Mock slow review
        def slow_review(*args, **kwargs):
            time.sleep(0.2)  # Exceed budget
            return ReviewResult(score=0.8)
        
        with patch.object(reviewer, '_perform_review', side_effect=slow_review):
            result = reviewer.review_answer("Test answer")
        
        # Should skip due to timeout
        self.assertTrue(result.skipped)
        self.assertIn("timeout", result.skip_reason.lower())


class TestReviewerBudget(unittest.TestCase):
    """Test budget enforcement."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_fast_review_completes_within_budget(self):
        """Test fast review completes within budget."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 500
        }
        
        reviewer = AnswerReviewer(config=config)
        
        # Mock fast review
        def fast_review(*args, **kwargs):
            return ReviewResult(
                skipped=False,
                score=0.85,
                confidence=0.9
            )
        
        with patch.object(reviewer, '_perform_review', return_value=fast_review()):
            result = reviewer.review_answer("Test answer with good content")
        
        self.assertFalse(result.skipped)
        self.assertEqual(result.score, 0.85)
        self.assertLess(result.latency_ms, 500)
    
    def test_slow_review_returns_within_overall_budget(self):
        """Test slow review returns quickly with skip annotation."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 100
        }
        
        reviewer = AnswerReviewer(config=config)
        
        # Mock slow review
        def slow_review(*args, **kwargs):
            time.sleep(0.2)  # Would exceed budget
            return ReviewResult(score=0.8)
        
        start = time.time()
        
        with patch.object(reviewer, '_perform_review', side_effect=slow_review):
            result = reviewer.review_answer("Test answer")
        
        elapsed = (time.time() - start) * 1000
        
        # Should return quickly with skip
        self.assertTrue(result.skipped)
        self.assertIn("timeout", result.skip_reason.lower())
        # Should be close to budget, not 200ms+
        self.assertLess(elapsed, 300)


class TestReviewerScoring(unittest.TestCase):
    """Test review scoring logic."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_reviews_normal_answer(self):
        """Test reviewing normal answer."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 500
        }
        
        reviewer = AnswerReviewer(config=config)
        result = reviewer.review_answer(
            "This is a good answer with sufficient detail.",
            context={"source": "test"},
            query="What is the answer?"
        )
        
        self.assertFalse(result.skipped)
        self.assertIsNotNone(result.score)
        self.assertGreater(result.score, 0.5)
    
    def test_flags_short_answer(self):
        """Test flagging short answers."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 500
        }
        
        reviewer = AnswerReviewer(config=config)
        result = reviewer.review_answer("Short")
        
        self.assertFalse(result.skipped)
        self.assertTrue(result.flags.get("too_short", False))
        self.assertLess(result.score, 0.5)
    
    def test_flags_uncertain_answer(self):
        """Test flagging uncertain answers."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 500
        }
        
        reviewer = AnswerReviewer(config=config)
        result = reviewer.review_answer("I don't know the answer to that question.")
        
        self.assertFalse(result.skipped)
        self.assertTrue(result.flags.get("uncertain", False))


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience functions."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_get_reviewer_returns_singleton(self):
        """Test get_reviewer returns singleton instance."""
        reviewer1 = get_reviewer()
        reviewer2 = get_reviewer()
        
        self.assertIs(reviewer1, reviewer2)
    
    @patch('core.reviewer._reviewer_instance', None)
    def test_review_answer_with_budget_convenience(self):
        """Test convenience function works."""
        # Create instance with config for this test
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 500
        }
        
        from core import reviewer as reviewer_module
        reviewer_module._reviewer_instance = AnswerReviewer(config=config)
        
        result = review_answer_with_budget("Test answer")
        
        self.assertIsInstance(result, ReviewResult)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def setUp(self):
        """Reset circuit breakers before each test."""
        reset_all_circuit_breakers()
    
    def test_slow_reviewer_returns_within_budget_and_marks_skipped(self):
        """Test: slow reviewer test path returns within overall budget and marks skipped."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 200  # 200ms budget
        }
        
        reviewer = AnswerReviewer(config=config)
        
        # Mock very slow review (would take 500ms)
        def very_slow_review(*args, **kwargs):
            time.sleep(0.5)
            return ReviewResult(score=0.8)
        
        start = time.time()
        
        with patch.object(reviewer, '_perform_review', side_effect=very_slow_review):
            result = reviewer.review_answer("Test answer")
        
        elapsed_ms = (time.time() - start) * 1000
        
        # ? Returns within overall budget (not 500ms)
        self.assertLess(elapsed_ms, 400, "Should timeout before slow review completes")
        
        # ? Marks skipped
        self.assertTrue(result.skipped, "Should be marked as skipped")
        
        # ? Has skip reason
        self.assertIsNotNone(result.skip_reason)
        self.assertIn("timeout", result.skip_reason.lower())
        
        # ? Score fields are None
        self.assertIsNone(result.score)
        self.assertIsNone(result.confidence)
    
    def test_fast_path_includes_review(self):
        """Test: fast path includes review with scores."""
        config = {
            "PERF_REVIEWER_ENABLED": True,
            "PERF_REVIEWER_BUDGET_MS": 500
        }
        
        reviewer = AnswerReviewer(config=config)
        
        # Mock fast review (completes quickly)
        def fast_review(*args, **kwargs):
            time.sleep(0.05)  # 50ms - well within budget
            return ReviewResult(
                skipped=False,
                score=0.88,
                confidence=0.92,
                flags={"quality": "high"}
            )
        
        with patch.object(reviewer, '_perform_review', side_effect=fast_review):
            result = reviewer.review_answer("High quality answer with details")
        
        # ? Not skipped
        self.assertFalse(result.skipped)
        
        # ? Includes review scores
        self.assertIsNotNone(result.score)
        self.assertEqual(result.score, 0.88)
        self.assertIsNotNone(result.confidence)
        self.assertEqual(result.confidence, 0.92)
        
        # ? Has flags
        self.assertIn("quality", result.flags)
        
        # ? No skip reason
        self.assertIsNone(result.skip_reason)
    
    def test_optional_score_fields_when_skipped(self):
        """Test: score fields are optional and excluded when skipped."""
        config = {
            "PERF_REVIEWER_ENABLED": False
        }
        
        reviewer = AnswerReviewer(config=config)
        result = reviewer.review_answer("Test")
        
        # ? Skipped
        self.assertTrue(result.skipped)
        
        # ? Score fields are None (optional)
        self.assertIsNone(result.score)
        self.assertIsNone(result.confidence)
        
        # ? to_dict excludes score fields
        d = result.to_dict()
        self.assertNotIn("score", d)
        self.assertNotIn("confidence", d)
        self.assertIn("skipped", d)
        self.assertTrue(d["skipped"])


if __name__ == "__main__":
    unittest.main()
