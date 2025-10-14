# tests/test_compare_internal.py — Comprehensive tests for internal comparator

import unittest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch

# Add workspace to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.factare.compare_internal import (
    InternalComparator,
    RetrievalCandidate,
    ContradictionPair,
    ComparisonResult,
    create_retrieval_candidates_from_dicts
)

class TestRetrievalCandidate(unittest.TestCase):
    """Test RetrievalCandidate dataclass."""
    
    def test_retrieval_candidate_creation(self):
        """Test creating RetrievalCandidate with all fields."""
        candidate = RetrievalCandidate(
            id="test_001",
            content="This is test content",
            source="Test Source",
            score=0.85,
            metadata={"type": "research"},
            url="https://example.com",
            timestamp=datetime.now()
        )
        
        self.assertEqual(candidate.id, "test_001")
        self.assertEqual(candidate.content, "This is test content")
        self.assertEqual(candidate.source, "Test Source")
        self.assertEqual(candidate.score, 0.85)
        self.assertEqual(candidate.metadata["type"], "research")
        self.assertEqual(candidate.url, "https://example.com")
        self.assertIsInstance(candidate.timestamp, datetime)
    
    def test_retrieval_candidate_minimal(self):
        """Test creating RetrievalCandidate with minimal fields."""
        candidate = RetrievalCandidate(
            id="test_002",
            content="Minimal content",
            source="Minimal Source",
            score=0.5
        )
        
        self.assertEqual(candidate.id, "test_002")
        self.assertEqual(candidate.content, "Minimal content")
        self.assertEqual(candidate.source, "Minimal Source")
        self.assertEqual(candidate.score, 0.5)
        self.assertIsNone(candidate.metadata)
        self.assertIsNone(candidate.url)
        self.assertIsNone(candidate.timestamp)

class TestContradictionPair(unittest.TestCase):
    """Test ContradictionPair dataclass."""
    
    def test_contradiction_pair_creation(self):
        """Test creating ContradictionPair with all fields."""
        contradiction = ContradictionPair(
            claim_a="Method A is effective",
            claim_b="Method A is ineffective",
            evidence_a="Study shows 90% success rate",
            evidence_b="Study shows 10% success rate",
            confidence=0.9,
            contradiction_type="evaluative"
        )
        
        self.assertEqual(contradiction.claim_a, "Method A is effective")
        self.assertEqual(contradiction.claim_b, "Method A is ineffective")
        self.assertEqual(contradiction.evidence_a, "Study shows 90% success rate")
        self.assertEqual(contradiction.evidence_b, "Study shows 10% success rate")
        self.assertEqual(contradiction.confidence, 0.9)
        self.assertEqual(contradiction.contradiction_type, "evaluative")

class TestInternalComparator(unittest.TestCase):
    """Test InternalComparator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.comparator = InternalComparator()
        self.now = datetime.now()
        
        # Create test retrieval candidates
        self.test_candidates = [
            RetrievalCandidate(
                id="pos_001",
                content="The new methodology is highly effective and shows significant improvements in performance. Studies demonstrate 40% better results.",
                source="Internal Research",
                score=0.9,
                timestamp=self.now - timedelta(hours=1)
            ),
            RetrievalCandidate(
                id="neg_001",
                content="The new methodology has serious limitations and fails to deliver promised results. Multiple studies show it is ineffective.",
                source="External Review",
                score=0.8,
                url="https://example.com/review",
                timestamp=self.now - timedelta(hours=2)
            ),
            RetrievalCandidate(
                id="neutral_001",
                content="The methodology shows mixed results with some benefits but also some drawbacks. Further research is needed.",
                source="Neutral Analysis",
                score=0.6,
                timestamp=self.now - timedelta(hours=3)
            )
        ]
    
    def test_detect_binary_contrast_should_question(self):
        """Test binary contrast detection with 'should' questions."""
        query = "Should we adopt the new methodology?"
        result = self.comparator._detect_binary_contrast(query)
        self.assertTrue(result)
    
    def test_detect_binary_contrast_pros_cons(self):
        """Test binary contrast detection with pros/cons."""
        query = "What are the pros and cons of the new approach?"
        result = self.comparator._detect_binary_contrast(query)
        self.assertTrue(result)
    
    def test_detect_binary_contrast_advantages_disadvantages(self):
        """Test binary contrast detection with advantages/disadvantages."""
        query = "What are the advantages and disadvantages of this method?"
        result = self.comparator._detect_binary_contrast(query)
        self.assertTrue(result)
    
    def test_detect_binary_contrast_support_oppose(self):
        """Test binary contrast detection with support/oppose."""
        query = "Do you support or oppose this policy?"
        result = self.comparator._detect_binary_contrast(query)
        self.assertTrue(result)
    
    def test_detect_binary_contrast_no_contrast(self):
        """Test binary contrast detection with non-contrast queries."""
        query = "What is the current status of the project?"
        result = self.comparator._detect_binary_contrast(query)
        self.assertFalse(result)
    
    def test_extract_entities(self):
        """Test entity extraction from text."""
        text = "The new methodology developed by Dr. Smith at MIT shows promising results."
        entities = self.comparator._extract_entities(text)
        
        # Check that key entities are found (may be part of longer phrases)
        self.assertTrue(any("Dr. Smith" in entity for entity in entities))
        self.assertIn("MIT", entities)
        self.assertTrue(any("new methodology" in entity for entity in entities))
    
    def test_extract_predicates(self):
        """Test predicate extraction from text."""
        text = "The system is effective and has been proven to work in multiple environments."
        predicates = self.comparator._extract_predicates(text)
        
        self.assertTrue(any("is effective" in pred for pred in predicates))
        self.assertTrue(any("has been proven" in pred for pred in predicates))
    
    def test_classify_sentiment_positive(self):
        """Test sentiment classification for positive text."""
        text = "This is a beneficial and effective approach that improves performance significantly."
        sentiment = self.comparator._classify_sentiment(text)
        self.assertGreater(sentiment, 0.1)
    
    def test_classify_sentiment_negative(self):
        """Test sentiment classification for negative text."""
        text = "This is a harmful and ineffective approach that worsens performance significantly."
        sentiment = self.comparator._classify_sentiment(text)
        self.assertLess(sentiment, -0.1)
    
    def test_classify_sentiment_neutral(self):
        """Test sentiment classification for neutral text."""
        text = "This is a standard approach with typical results."
        sentiment = self.comparator._classify_sentiment(text)
        self.assertGreaterEqual(sentiment, -0.1)
        self.assertLessEqual(sentiment, 0.1)
    
    def test_is_external_source_url(self):
        """Test external source detection with URL."""
        self.assertTrue(self.comparator._is_external_source("https://example.com"))
        self.assertTrue(self.comparator._is_external_source("http://arxiv.org"))
        self.assertFalse(self.comparator._is_external_source("Internal Database"))
    
    def test_is_external_source_name(self):
        """Test external source detection with source name."""
        self.assertTrue(self.comparator._is_external_source("Nature Medicine"))
        self.assertTrue(self.comparator._is_external_source("IEEE Transactions"))
        self.assertFalse(self.comparator._is_external_source("Internal Research"))
    
    def test_find_contradiction_keywords(self):
        """Test contradiction detection with keyword pairs."""
        candidate_a = RetrievalCandidate(
            id="a",
            content="The method is effective and supports the hypothesis.",
            source="Source A",
            score=0.8
        )
        candidate_b = RetrievalCandidate(
            id="b",
            content="The method is ineffective and opposes the hypothesis.",
            source="Source B",
            score=0.7
        )
        
        contradiction = self.comparator._find_contradiction(candidate_a, candidate_b)
        self.assertIsNotNone(contradiction)
        self.assertEqual(contradiction.contradiction_type, "evaluative")
        self.assertIn("effective", contradiction.claim_a.lower())
        self.assertIn("ineffective", contradiction.claim_b.lower())
    
    def test_find_contradiction_no_contradiction(self):
        """Test contradiction detection with no contradictions."""
        candidate_a = RetrievalCandidate(
            id="a",
            content="The method shows good results.",
            source="Source A",
            score=0.8
        )
        candidate_b = RetrievalCandidate(
            id="b",
            content="The method shows excellent results.",
            source="Source B",
            score=0.7
        )
        
        contradiction = self.comparator._find_contradiction(candidate_a, candidate_b)
        self.assertIsNone(contradiction)
    
    def test_create_evidence_items(self):
        """Test creating evidence items from retrieval candidates."""
        evidence_items = self.comparator._create_evidence_items(self.test_candidates)
        
        self.assertEqual(len(evidence_items), 3)
        
        # Check first item
        self.assertEqual(evidence_items[0].id, "pos_001")
        self.assertEqual(evidence_items[0].source, "Internal Research")
        self.assertEqual(evidence_items[0].score, 0.9)
        self.assertFalse(evidence_items[0].is_external)  # No URL
        
        # Check second item
        self.assertEqual(evidence_items[1].id, "neg_001")
        self.assertEqual(evidence_items[1].source, "External Review")
        self.assertEqual(evidence_items[1].score, 0.8)
        self.assertTrue(evidence_items[1].is_external)  # Has URL
    
    def test_compare_binary_contrast(self):
        """Test comparison with binary contrast query."""
        query = "Should we adopt the new methodology?"
        result = self.comparator.compare(query, self.test_candidates)
        
        self.assertTrue(result.has_binary_contrast)
        self.assertIsNotNone(result.stance_a)
        self.assertIsNotNone(result.stance_b)
        self.assertEqual(len(result.evidence_items), 3)
        self.assertGreater(len(result.contradictions), 0)
        self.assertIsInstance(result.decision, type(result.decision))
    
    def test_compare_no_binary_contrast(self):
        """Test comparison with non-binary contrast query."""
        query = "What is the current status of the project?"
        result = self.comparator.compare(query, self.test_candidates)
        
        self.assertFalse(result.has_binary_contrast)
        self.assertIsNone(result.stance_a)
        self.assertIsNone(result.stance_b)
        self.assertEqual(len(result.evidence_items), 3)
        self.assertEqual(result.decision.verdict, "insufficient_evidence")
    
    def test_compare_empty_candidates(self):
        """Test comparison with empty candidates list."""
        query = "Should we adopt the new methodology?"
        result = self.comparator.compare(query, [])
        
        self.assertTrue(result.has_binary_contrast)
        self.assertIsNone(result.stance_a)
        self.assertIsNone(result.stance_b)
        self.assertEqual(len(result.evidence_items), 0)
        self.assertEqual(len(result.contradictions), 0)
        self.assertEqual(result.decision.verdict, "insufficient_evidence")
    
    def test_create_compare_summary_binary_contrast(self):
        """Test creating CompareSummary with binary contrast."""
        query = "Should we adopt the new methodology?"
        summary = self.comparator.create_compare_summary(query, self.test_candidates)
        
        self.assertEqual(summary.query, query)
        self.assertNotEqual(summary.stance_a, "No clear stance A identified")
        self.assertNotEqual(summary.stance_b, "No clear stance B identified")
        self.assertEqual(len(summary.evidence), 3)
        self.assertIn(summary.decision.verdict, ["stance_a", "stance_b", "inconclusive"])
    
    def test_create_compare_summary_no_contrast(self):
        """Test creating CompareSummary without binary contrast."""
        query = "What is the current status of the project?"
        summary = self.comparator.create_compare_summary(query, self.test_candidates)
        
        self.assertEqual(summary.query, query)
        self.assertEqual(summary.stance_a, "No clear stance A identified")
        self.assertEqual(summary.stance_b, "No clear stance B identified")
        self.assertEqual(summary.decision.verdict, "insufficient_evidence")

class TestSyntheticFixtures(unittest.TestCase):
    """Test with synthetic retrieval fixtures."""
    
    def setUp(self):
        """Set up test fixtures with synthetic data."""
        self.comparator = InternalComparator()
        self.now = datetime.now()
        
        # Synthetic retrieval candidates for methodology comparison
        self.methodology_candidates = [
            {
                'id': 'method_pos_001',
                'content': 'The new agile methodology is highly effective and significantly improves team productivity by 40%. Studies confirm it is beneficial and successful.',
                'source': 'Internal Research Database',
                'score': 0.95,
                'timestamp': (self.now - timedelta(hours=1)).isoformat(),
                'metadata': {'department': 'R&D', 'study_type': 'controlled_trial'}
            },
            {
                'id': 'method_neg_001',
                'content': 'The new agile methodology is ineffective and often leads to project failures. Industry reports show it is harmful and unsuccessful.',
                'source': 'External Industry Report',
                'score': 0.88,
                'url': 'https://example.com/industry-report',
                'timestamp': (self.now - timedelta(days=1)).isoformat(),
                'metadata': {'organization': 'Industry Group', 'report_type': 'survey'}
            },
            {
                'id': 'method_contradict_001',
                'content': 'While the methodology shows promise in controlled environments, real-world implementation faces significant challenges.',
                'source': 'Mixed Analysis',
                'score': 0.75,
                'timestamp': (self.now - timedelta(hours=6)).isoformat(),
                'metadata': {'analysis_type': 'mixed', 'status': 'preliminary'}
            }
        ]
        
        # Synthetic retrieval candidates for policy comparison
        self.policy_candidates = [
            {
                'id': 'policy_support_001',
                'content': 'The new remote work policy increases employee satisfaction by 35% and reduces operational costs. Survey data from 1000+ employees confirms these benefits.',
                'source': 'HR Analytics',
                'score': 0.92,
                'timestamp': (self.now - timedelta(hours=2)).isoformat(),
                'metadata': {'department': 'HR', 'survey_size': 1000}
            },
            {
                'id': 'policy_oppose_001',
                'content': 'The remote work policy decreases team collaboration and reduces productivity. Studies show 25% drop in team performance metrics.',
                'source': 'Management Research',
                'score': 0.85,
                'url': 'https://example.com/management-study',
                'timestamp': (self.now - timedelta(days=2)).isoformat(),
                'metadata': {'journal': 'Management Science', 'study_type': 'longitudinal'}
            },
            {
                'id': 'policy_neutral_001',
                'content': 'The policy shows mixed results depending on team composition and work type. Some teams benefit while others struggle.',
                'source': 'Neutral Analysis',
                'score': 0.70,
                'timestamp': (self.now - timedelta(hours=4)).isoformat(),
                'metadata': {'analysis_type': 'neutral', 'scope': 'comprehensive'}
            }
        ]
        
        # Synthetic retrieval candidates for technology adoption
        self.tech_candidates = [
            {
                'id': 'tech_pro_001',
                'content': 'AI-powered analytics is highly effective and enables real-time decision making. The technology is proven, beneficial, and ready for deployment.',
                'source': 'Technology Research',
                'score': 0.90,
                'timestamp': (self.now - timedelta(hours=3)).isoformat(),
                'metadata': {'technology': 'AI', 'improvement': '50%'}
            },
            {
                'id': 'tech_con_001',
                'content': 'AI analytics systems are ineffective and unreliable. They often produce incorrect results and are harmful to business operations.',
                'source': 'Technology Review',
                'score': 0.87,
                'url': 'https://example.com/tech-review',
                'timestamp': (self.now - timedelta(days=3)).isoformat(),
                'metadata': {'technology': 'AI', 'reliability': 'low'}
            }
        ]
    
    def test_methodology_comparison(self):
        """Test methodology comparison with synthetic data."""
        query = "Should we adopt the new agile methodology?"
        candidates = create_retrieval_candidates_from_dicts(self.methodology_candidates)
        
        result = self.comparator.compare(query, candidates)
        
        # Should detect binary contrast
        self.assertTrue(result.has_binary_contrast)
        
        # Should have stances
        self.assertIsNotNone(result.stance_a)
        self.assertIsNotNone(result.stance_b)
        
        # Should have evidence items
        self.assertEqual(len(result.evidence_items), 3)
        
        # Should detect contradictions
        self.assertGreater(len(result.contradictions), 0)
        
        # Check evidence ordering by score
        scores = [item.score for item in result.evidence_items]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # Check decision
        self.assertIn(result.decision.verdict, ["stance_a", "stance_b", "inconclusive"])
        self.assertGreaterEqual(result.decision.confidence, 0.0)
        self.assertLessEqual(result.decision.confidence, 1.0)
    
    def test_policy_comparison(self):
        """Test policy comparison with synthetic data."""
        query = "Do you support or oppose the new remote work policy?"
        candidates = create_retrieval_candidates_from_dicts(self.policy_candidates)
        
        result = self.comparator.compare(query, candidates)
        
        # Should detect binary contrast
        self.assertTrue(result.has_binary_contrast)
        
        # Should have stances
        self.assertIsNotNone(result.stance_a)
        self.assertIsNotNone(result.stance_b)
        
        # Should have evidence items
        self.assertEqual(len(result.evidence_items), 3)
        
        # Check external/internal detection
        external_items = [item for item in result.evidence_items if item.is_external]
        internal_items = [item for item in result.evidence_items if not item.is_external]
        
        self.assertEqual(len(external_items), 1)  # Only one has URL
        self.assertEqual(len(internal_items), 2)
    
    def test_tech_adoption_comparison(self):
        """Test technology adoption comparison with synthetic data."""
        query = "Should we implement AI-powered analytics?"
        candidates = create_retrieval_candidates_from_dicts(self.tech_candidates)
        
        result = self.comparator.compare(query, candidates)
        
        # Should detect binary contrast
        self.assertTrue(result.has_binary_contrast)
        
        # Should have stances
        self.assertIsNotNone(result.stance_a)
        self.assertIsNotNone(result.stance_b)
        
        # Should have evidence items
        self.assertEqual(len(result.evidence_items), 2)
        
        # Should detect contradictions
        self.assertGreater(len(result.contradictions), 0)
        
        # Check contradiction details
        for contradiction in result.contradictions:
            self.assertIn(contradiction.contradiction_type, ["temporal", "causal", "factual", "evaluative"])
            self.assertGreater(contradiction.confidence, 0.0)
            self.assertLessEqual(contradiction.confidence, 1.0)
    
    def test_consistency_across_runs(self):
        """Test that results are consistent across multiple runs."""
        query = "Should we adopt the new methodology?"
        candidates = create_retrieval_candidates_from_dicts(self.methodology_candidates)
        
        # Run comparison multiple times
        results = []
        for _ in range(5):
            result = self.comparator.compare(query, candidates)
            results.append(result)
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(result.has_binary_contrast, first_result.has_binary_contrast)
            self.assertEqual(result.stance_a, first_result.stance_a)
            self.assertEqual(result.stance_b, first_result.stance_b)
            self.assertEqual(len(result.evidence_items), len(first_result.evidence_items))
            self.assertEqual(len(result.contradictions), len(first_result.contradictions))
            self.assertEqual(result.decision.verdict, first_result.decision.verdict)
            self.assertEqual(result.decision.confidence, first_result.decision.confidence)
    
    def test_evidence_ordering_deterministic(self):
        """Test that evidence ordering is deterministic."""
        query = "Should we adopt the new methodology?"
        candidates = create_retrieval_candidates_from_dicts(self.methodology_candidates)
        
        result = self.comparator.compare(query, candidates)
        
        # Evidence should be ordered by score (descending)
        scores = [item.score for item in result.evidence_items]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # Check specific ordering
        expected_order = ["method_pos_001", "method_neg_001", "method_contradict_001"]
        actual_order = [item.id for item in result.evidence_items]
        self.assertEqual(actual_order, expected_order)
    
    def test_contradiction_detection_comprehensive(self):
        """Test comprehensive contradiction detection."""
        # Create candidates with various contradiction types
        contradiction_candidates = [
            {
                'id': 'temp_001',
                'content': 'The system always works correctly in all scenarios.',
                'source': 'Source A',
                'score': 0.8,
                'timestamp': (self.now - timedelta(hours=1)).isoformat()
            },
            {
                'id': 'temp_002',
                'content': 'The system never works correctly in any scenario.',
                'source': 'Source B',
                'score': 0.7,
                'timestamp': (self.now - timedelta(hours=2)).isoformat()
            },
            {
                'id': 'eval_001',
                'content': 'The approach is highly beneficial and effective.',
                'source': 'Source C',
                'score': 0.9,
                'timestamp': (self.now - timedelta(hours=3)).isoformat()
            },
            {
                'id': 'eval_002',
                'content': 'The approach is highly harmful and ineffective.',
                'source': 'Source D',
                'score': 0.6,
                'timestamp': (self.now - timedelta(hours=4)).isoformat()
            }
        ]
        
        query = "Is the system reliable?"
        candidates = create_retrieval_candidates_from_dicts(contradiction_candidates)
        
        result = self.comparator.compare(query, candidates)
        
        # Should detect multiple contradictions
        self.assertGreaterEqual(len(result.contradictions), 2)
        
        # Check contradiction types
        contradiction_types = [c.contradiction_type for c in result.contradictions]
        self.assertIn("temporal", contradiction_types)
        self.assertIn("evaluative", contradiction_types)
    
    def test_create_compare_summary_integration(self):
        """Test full integration with CompareSummary creation."""
        query = "Should we implement the new policy?"
        candidates = create_retrieval_candidates_from_dicts(self.policy_candidates)
        
        summary = self.comparator.create_compare_summary(query, candidates)
        
        # Check summary structure
        self.assertEqual(summary.query, query)
        self.assertIsNotNone(summary.stance_a)
        self.assertIsNotNone(summary.stance_b)
        self.assertEqual(len(summary.evidence), 3)
        self.assertIn(summary.decision.verdict, ["stance_a", "stance_b", "inconclusive", "insufficient_evidence"])
        self.assertGreaterEqual(summary.decision.confidence, 0.0)
        self.assertLessEqual(summary.decision.confidence, 1.0)
        self.assertIsNotNone(summary.decision.rationale)
        
        # Check evidence items
        for item in summary.evidence:
            self.assertIsNotNone(item.id)
            self.assertIsNotNone(item.snippet)
            self.assertIsNotNone(item.source)
            self.assertGreaterEqual(item.score, 0.0)
            self.assertLessEqual(item.score, 1.0)

class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.comparator = InternalComparator()
    
    def test_empty_query(self):
        """Test with empty query."""
        candidates = [RetrievalCandidate(id="1", content="test", source="test", score=0.5)]
        result = self.comparator.compare("", candidates)
        
        self.assertFalse(result.has_binary_contrast)
        self.assertEqual(result.decision.verdict, "insufficient_evidence")
    
    def test_single_candidate(self):
        """Test with single candidate."""
        query = "Should we adopt this approach?"
        candidates = [RetrievalCandidate(id="1", content="This approach is effective", source="test", score=0.8)]
        
        result = self.comparator.compare(query, candidates)
        
        self.assertTrue(result.has_binary_contrast)
        self.assertEqual(len(result.evidence_items), 1)
        self.assertEqual(len(result.contradictions), 0)  # No contradictions with single item
    
    def test_identical_candidates(self):
        """Test with identical candidates."""
        query = "Should we adopt this approach?"
        candidates = [
            RetrievalCandidate(id="1", content="This approach is effective", source="test", score=0.8),
            RetrievalCandidate(id="2", content="This approach is effective", source="test", score=0.8)
        ]
        
        result = self.comparator.compare(query, candidates)
        
        self.assertTrue(result.has_binary_contrast)
        self.assertEqual(len(result.evidence_items), 2)
        self.assertEqual(len(result.contradictions), 0)  # No contradictions with identical content
    
    def test_very_long_content(self):
        """Test with very long content."""
        long_content = "This is a very long piece of content. " * 100
        query = "Should we adopt this approach?"
        candidates = [RetrievalCandidate(id="1", content=long_content, source="test", score=0.8)]
        
        result = self.comparator.compare(query, candidates)
        
        self.assertTrue(result.has_binary_contrast)
        self.assertEqual(len(result.evidence_items), 1)
        # Content should be truncated in evidence items
        self.assertLess(len(result.evidence_items[0].snippet), len(long_content))
    
    def test_special_characters(self):
        """Test with special characters in content."""
        query = "Should we adopt this approach?"
        candidates = [
            RetrievalCandidate(
                id="1", 
                content="This approach is 100% effective! It's amazing & works great.",
                source="test", 
                score=0.8
            )
        ]
        
        result = self.comparator.compare(query, candidates)
        
        self.assertTrue(result.has_binary_contrast)
        self.assertEqual(len(result.evidence_items), 1)
        self.assertIn("100%", result.evidence_items[0].snippet)
    
    def test_unicode_content(self):
        """Test with unicode content."""
        query = "Should we adopt this approach?"
        candidates = [
            RetrievalCandidate(
                id="1", 
                content="This approach is très efficace and shows excellent résultats.",
                source="test", 
                score=0.8
            )
        ]
        
        result = self.comparator.compare(query, candidates)
        
        self.assertTrue(result.has_binary_contrast)
        self.assertEqual(len(result.evidence_items), 1)
        self.assertIn("très", result.evidence_items[0].snippet)


def main():
    """Run all tests."""
    print("Running internal comparator tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestRetrievalCandidate,
        TestContradictionPair,
        TestInternalComparator,
        TestSyntheticFixtures,
        TestEdgeCases
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All internal comparator tests passed!")
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        for failure in result.failures:
            print(f"FAIL: {failure[0]}")
            print(failure[1])
        for error in result.errors:
            print(f"ERROR: {error[0]}")
            print(error[1])
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)