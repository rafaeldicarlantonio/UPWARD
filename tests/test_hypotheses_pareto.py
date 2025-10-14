# tests/test_hypotheses_pareto.py — Comprehensive tests for hypotheses Pareto gating

import unittest
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add workspace to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the config loading before importing
with patch.dict(os.environ, {
    'OPENAI_API_KEY': 'test-key',
    'SUPABASE_URL': 'https://test.supabase.co',
    'PINECONE_API_KEY': 'test-pinecone-key',
    'PINECONE_INDEX': 'test-index',
    'PINECONE_EXPLICATE_INDEX': 'test-explicate',
    'PINECONE_IMPLICATE_INDEX': 'test-implicate',
}):
    from core.hypotheses.propose import (
        HypothesisProposal,
        ParetoScorer,
        HypothesisProposer,
        ProposalResult,
        HypothesisStatus,
        ParetoScoreComponents,
        propose_hypothesis
    )
    from core.factare.summary import CompareSummary, EvidenceItem, Decision

class TestParetoScorer(unittest.TestCase):
    """Test Pareto score calculation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.scorer = ParetoScorer()
        self.now = datetime.now()
        
        # Sample compare summary
        self.sample_compare_summary = CompareSummary(
            query="Should we adopt this method?",
            stance_a="Evidence supports adoption",
            stance_b="Evidence suggests caution",
            evidence=[
                EvidenceItem(
                    id="ev_001",
                    snippet="Study shows 90% success rate",
                    source="Research Journal",
                    score=0.9,
                    is_external=False
                ),
                EvidenceItem(
                    id="ev_002",
                    snippet="Study shows 10% success rate",
                    source="Alternative Journal",
                    score=0.1,
                    is_external=False
                )
            ],
            decision=Decision(
                verdict="inconclusive",
                confidence=0.6,
                rationale="Mixed evidence"
            ),
            created_at=self.now,
            metadata={}
        )
    
    def test_calculate_pareto_score_with_compare_summary(self):
        """Test Pareto score calculation with compare summary."""
        components = self.scorer.calculate_pareto_score(
            compare_summary=self.sample_compare_summary,
            lift_scores=[0.8, 0.7, 0.6, 0.5, 0.4],
            k=3
        )
        
        self.assertIsInstance(components, ParetoScoreComponents)
        self.assertGreaterEqual(components.blended_score, 0.0)
        self.assertLessEqual(components.blended_score, 1.0)
        self.assertGreater(components.lift_score_at_k, 0.0)
        self.assertGreater(components.contradiction_score_inverse, 0.0)
        self.assertGreater(components.evidence_diversity, 0.0)
    
    def test_calculate_pareto_score_without_compare_summary(self):
        """Test Pareto score calculation without compare summary."""
        components = self.scorer.calculate_pareto_score(
            compare_summary=None,
            lift_scores=[0.8, 0.7, 0.6],
            k=2
        )
        
        self.assertIsInstance(components, ParetoScoreComponents)
        self.assertGreaterEqual(components.blended_score, 0.0)
        self.assertLessEqual(components.blended_score, 1.0)
        self.assertEqual(components.contradiction_score_inverse, 0.5)  # Default neutral
        self.assertEqual(components.evidence_diversity, 0.5)  # Default neutral
    
    def test_calculate_pareto_score_without_lift_scores(self):
        """Test Pareto score calculation without lift scores."""
        components = self.scorer.calculate_pareto_score(
            compare_summary=self.sample_compare_summary,
            lift_scores=None,
            k=3
        )
        
        self.assertIsInstance(components, ParetoScoreComponents)
        self.assertGreaterEqual(components.blended_score, 0.0)
        self.assertLessEqual(components.blended_score, 1.0)
        self.assertEqual(components.lift_score_at_k, 0.5)  # Default neutral
    
    def test_lift_score_at_k_calculation(self):
        """Test LiftScore@k calculation."""
        lift_scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
        
        # Test with k=3
        score_k3 = self.scorer._calculate_lift_score_at_k(lift_scores, 3)
        expected_k3 = (0.9 + 0.8 + 0.7) / 3  # 0.8
        self.assertAlmostEqual(score_k3, expected_k3, places=6)
        
        # Test with k=5
        score_k5 = self.scorer._calculate_lift_score_at_k(lift_scores, 5)
        expected_k5 = (0.9 + 0.8 + 0.7 + 0.6 + 0.5) / 5  # 0.7
        self.assertAlmostEqual(score_k5, expected_k5, places=6)
    
    def test_contradiction_score_inverse(self):
        """Test contradiction score inverse calculation."""
        # Test with contradictions
        score_with_contradictions = self.scorer._calculate_contradiction_score_inverse(
            self.sample_compare_summary
        )
        self.assertGreaterEqual(score_with_contradictions, 0.0)
        self.assertLessEqual(score_with_contradictions, 1.0)
        
        # Test without compare summary
        score_without_summary = self.scorer._calculate_contradiction_score_inverse(None)
        self.assertEqual(score_without_summary, 0.5)  # Default neutral
    
    def test_evidence_diversity_calculation(self):
        """Test evidence diversity calculation."""
        # Test with diverse evidence
        score_diverse = self.scorer._calculate_evidence_diversity(self.sample_compare_summary)
        self.assertGreaterEqual(score_diverse, 0.0)
        self.assertLessEqual(score_diverse, 1.0)
        
        # Test without compare summary
        score_without_summary = self.scorer._calculate_evidence_diversity(None)
        self.assertEqual(score_without_summary, 0.5)  # Default neutral

class TestHypothesisProposer(unittest.TestCase):
    """Test hypothesis proposer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.proposer = HypothesisProposer()
        self.now = datetime.now()
        
        # Sample compare summary
        self.sample_compare_summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.6, rationale="Test"),
            created_at=self.now,
            metadata={}
        )
    
    def test_propose_hypothesis_above_threshold(self):
        """Test hypothesis proposal above Pareto threshold."""
        with patch('core.policy.get_pareto_threshold', return_value=0.5):
            response = self.proposer.propose_hypothesis(
                title="Test Hypothesis",
                description="Test description",
                source_message_id="msg_001",
                compare_summary=self.sample_compare_summary,
                pareto_score=0.8,  # Above threshold
                user_roles=['user'],
                created_by="test_user"
            )
        
        self.assertEqual(response.result, ProposalResult.PERSISTED)
        self.assertIsNotNone(response.hypothesis_id)
        self.assertEqual(response.pareto_score, 0.8)
        self.assertIsNotNone(response.persisted_at)
        self.assertIsNone(response.override_reason)
    
    def test_propose_hypothesis_below_threshold(self):
        """Test hypothesis proposal below Pareto threshold."""
        with patch('core.policy.get_pareto_threshold', return_value=0.7):
            response = self.proposer.propose_hypothesis(
                title="Test Hypothesis",
                description="Test description",
                source_message_id="msg_001",
                compare_summary=self.sample_compare_summary,
                pareto_score=0.5,  # Below threshold
                user_roles=['user'],
                created_by="test_user"
            )
        
        self.assertEqual(response.result, ProposalResult.NOT_PERSISTED)
        self.assertIsNone(response.hypothesis_id)
        self.assertEqual(response.pareto_score, 0.5)
        self.assertIsNone(response.persisted_at)
        self.assertIsNone(response.override_reason)
    
    def test_propose_hypothesis_with_override(self):
        """Test hypothesis proposal with analytics override."""
        with patch('core.policy.get_pareto_threshold', return_value=0.7):
            response = self.proposer.propose_hypothesis(
                title="Test Hypothesis",
                description="Test description",
                source_message_id="msg_001",
                compare_summary=self.sample_compare_summary,
                pareto_score=0.5,  # Below threshold
                user_roles=['analytics'],  # Can override
                override_reason="Important for research",
                created_by="analytics_user"
            )
        
        self.assertEqual(response.result, ProposalResult.OVERRIDE)
        self.assertIsNotNone(response.hypothesis_id)
        self.assertEqual(response.pareto_score, 0.5)
        self.assertIsNotNone(response.persisted_at)
        self.assertEqual(response.override_reason, "Important for research")
    
    def test_propose_hypothesis_override_without_reason(self):
        """Test hypothesis proposal with analytics role but no override reason."""
        with patch('core.policy.get_pareto_threshold', return_value=0.7):
            response = self.proposer.propose_hypothesis(
                title="Test Hypothesis",
                description="Test description",
                source_message_id="msg_001",
                compare_summary=self.sample_compare_summary,
                pareto_score=0.5,  # Below threshold
                user_roles=['analytics'],  # Can override
                override_reason=None,  # No reason provided
                created_by="analytics_user"
            )
        
        self.assertEqual(response.result, ProposalResult.NOT_PERSISTED)
        self.assertIsNone(response.hypothesis_id)
        self.assertEqual(response.pareto_score, 0.5)
        self.assertIsNone(response.persisted_at)
        self.assertIsNone(response.override_reason)
    
    def test_propose_hypothesis_auto_calculate_score(self):
        """Test hypothesis proposal with automatic score calculation."""
        with patch('core.policy.get_pareto_threshold', return_value=0.5):
            response = self.proposer.propose_hypothesis(
                title="Test Hypothesis",
                description="Test description",
                source_message_id="msg_001",
                compare_summary=self.sample_compare_summary,
                pareto_score=None,  # Auto-calculate
                user_roles=['user'],
                created_by="test_user"
            )
        
        self.assertIsNotNone(response.pareto_score)
        self.assertIsNotNone(response.pareto_components)
        self.assertGreaterEqual(response.pareto_score, 0.0)
        self.assertLessEqual(response.pareto_score, 1.0)
    
    def test_get_hypothesis(self):
        """Test retrieving hypothesis by ID."""
        # First create a hypothesis
        with patch('core.policy.get_pareto_threshold', return_value=0.5):
            response = self.proposer.propose_hypothesis(
                title="Test Hypothesis",
                description="Test description",
                source_message_id="msg_001",
                pareto_score=0.8,
                user_roles=['user'],
                created_by="test_user"
            )
        
        hypothesis_id = response.hypothesis_id
        self.assertIsNotNone(hypothesis_id)
        
        # Retrieve the hypothesis
        hypothesis = self.proposer.get_hypothesis(hypothesis_id)
        self.assertIsNotNone(hypothesis)
        self.assertEqual(hypothesis.title, "Test Hypothesis")
        self.assertEqual(hypothesis.description, "Test description")
        self.assertEqual(hypothesis.pareto_score, 0.8)
    
    def test_list_hypotheses(self):
        """Test listing hypotheses."""
        # Create multiple hypotheses
        with patch('core.policy.get_pareto_threshold', return_value=0.5):
            for i in range(3):
                self.proposer.propose_hypothesis(
                    title=f"Test Hypothesis {i}",
                    description=f"Test description {i}",
                    source_message_id=f"msg_{i:03d}",
                    pareto_score=0.8,
                    user_roles=['user'],
                    created_by="test_user"
                )
        
        # List all hypotheses
        hypotheses = self.proposer.list_hypotheses()
        self.assertEqual(len(hypotheses), 3)
        
        # Test with limit
        hypotheses_limited = self.proposer.list_hypotheses(limit=2)
        self.assertEqual(len(hypotheses_limited), 2)
        
        # Test with offset
        hypotheses_offset = self.proposer.list_hypotheses(offset=1)
        self.assertEqual(len(hypotheses_offset), 2)
    
    def test_get_stats(self):
        """Test getting statistics."""
        # Create some hypotheses
        with patch('core.policy.get_pareto_threshold', return_value=0.5):
            # Above threshold
            self.proposer.propose_hypothesis(
                title="High Score Hypothesis",
                description="High score description",
                source_message_id="msg_001",
                pareto_score=0.8,
                user_roles=['user'],
                created_by="test_user"
            )
            
            # Below threshold
            self.proposer.propose_hypothesis(
                title="Low Score Hypothesis",
                description="Low score description",
                source_message_id="msg_002",
                pareto_score=0.3,
                user_roles=['user'],
                created_by="test_user"
            )
            
            # Override
            self.proposer.propose_hypothesis(
                title="Override Hypothesis",
                description="Override description",
                source_message_id="msg_003",
                pareto_score=0.3,
                user_roles=['analytics'],
                override_reason="Important research",
                created_by="analytics_user"
            )
        
        stats = self.proposer.get_stats()
        
        self.assertEqual(stats['total_hypotheses'], 3)
        self.assertIn('by_status', stats)
        self.assertEqual(stats['overrides'], 1)
        self.assertAlmostEqual(stats['override_rate'], 1/3, places=6)

class TestHypothesisProposal(unittest.TestCase):
    """Test HypothesisProposal dataclass."""
    
    def test_hypothesis_proposal_creation(self):
        """Test creating a hypothesis proposal."""
        now = datetime.now()
        
        proposal = HypothesisProposal(
            title="Test Hypothesis",
            description="Test description",
            source_message_id="msg_001",
            pareto_score=0.8,
            created_at=now,
            created_by="test_user",
            status=HypothesisStatus.PENDING,
            metadata={"test": "value"}
        )
        
        self.assertEqual(proposal.title, "Test Hypothesis")
        self.assertEqual(proposal.description, "Test description")
        self.assertEqual(proposal.source_message_id, "msg_001")
        self.assertEqual(proposal.pareto_score, 0.8)
        self.assertEqual(proposal.created_at, now)
        self.assertEqual(proposal.created_by, "test_user")
        self.assertEqual(proposal.status, HypothesisStatus.PENDING)
        self.assertEqual(proposal.metadata["test"], "value")
    
    def test_hypothesis_proposal_to_dict(self):
        """Test converting proposal to dictionary."""
        now = datetime.now()
        
        proposal = HypothesisProposal(
            title="Test Hypothesis",
            description="Test description",
            source_message_id="msg_001",
            pareto_score=0.8,
            created_at=now,
            created_by="test_user",
            status=HypothesisStatus.PENDING,
            metadata={"test": "value"}
        )
        
        data = proposal.to_dict()
        
        self.assertEqual(data['title'], "Test Hypothesis")
        self.assertEqual(data['description'], "Test description")
        self.assertEqual(data['source_message_id'], "msg_001")
        self.assertEqual(data['pareto_score'], 0.8)
        self.assertEqual(data['created_at'], now.isoformat())
        self.assertEqual(data['created_by'], "test_user")
        self.assertEqual(data['status'], "pending")
        self.assertEqual(data['metadata']['test'], "value")
    
    def test_hypothesis_proposal_from_dict(self):
        """Test creating proposal from dictionary."""
        now = datetime.now()
        
        data = {
            'title': 'Test Hypothesis',
            'description': 'Test description',
            'source_message_id': 'msg_001',
            'pareto_score': 0.8,
            'created_at': now.isoformat(),
            'created_by': 'test_user',
            'status': 'pending',
            'metadata': {'test': 'value'}
        }
        
        proposal = HypothesisProposal.from_dict(data)
        
        self.assertEqual(proposal.title, "Test Hypothesis")
        self.assertEqual(proposal.description, "Test description")
        self.assertEqual(proposal.source_message_id, "msg_001")
        self.assertEqual(proposal.pareto_score, 0.8)
        self.assertEqual(proposal.created_at, now)
        self.assertEqual(proposal.created_by, "test_user")
        self.assertEqual(proposal.status, HypothesisStatus.PENDING)
        self.assertEqual(proposal.metadata['test'], "value")

class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function for proposing hypotheses."""
    
    def test_propose_hypothesis_convenience(self):
        """Test the convenience function for proposing hypotheses."""
        with patch('core.policy.get_pareto_threshold', return_value=0.5):
            response = propose_hypothesis(
                title="Convenience Test",
                description="Convenience description",
                source_message_id="msg_001",
                pareto_score=0.8,
                user_roles=['user'],
                created_by="test_user"
            )
        
        self.assertIsInstance(response, ProposalResult)
        self.assertEqual(response, ProposalResult.PERSISTED)

class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.proposer = HypothesisProposer()
        self.now = datetime.now()
    
    def test_full_workflow_above_threshold(self):
        """Test full workflow with score above threshold."""
        with patch('core.policy.get_pareto_threshold', return_value=0.6):
            # Propose hypothesis
            response = self.proposer.propose_hypothesis(
                title="High Quality Hypothesis",
                description="This hypothesis has strong evidence and should be persisted",
                source_message_id="msg_001",
                pareto_score=0.8,
                user_roles=['user'],
                created_by="researcher"
            )
            
            # Verify response
            self.assertEqual(response.result, ProposalResult.PERSISTED)
            self.assertIsNotNone(response.hypothesis_id)
            self.assertEqual(response.pareto_score, 0.8)
            self.assertIsNotNone(response.persisted_at)
            
            # Verify persistence
            hypothesis = self.proposer.get_hypothesis(response.hypothesis_id)
            self.assertIsNotNone(hypothesis)
            self.assertEqual(hypothesis.title, "High Quality Hypothesis")
            self.assertEqual(hypothesis.pareto_score, 0.8)
            self.assertEqual(hypothesis.status, HypothesisStatus.PENDING)
    
    def test_full_workflow_below_threshold(self):
        """Test full workflow with score below threshold."""
        with patch('core.policy.get_pareto_threshold', return_value=0.7):
            # Propose hypothesis
            response = self.proposer.propose_hypothesis(
                title="Low Quality Hypothesis",
                description="This hypothesis has weak evidence and should not be persisted",
                source_message_id="msg_002",
                pareto_score=0.4,
                user_roles=['user'],
                created_by="researcher"
            )
            
            # Verify response
            self.assertEqual(response.result, ProposalResult.NOT_PERSISTED)
            self.assertIsNone(response.hypothesis_id)
            self.assertEqual(response.pareto_score, 0.4)
            self.assertIsNone(response.persisted_at)
            
            # Verify not persisted
            self.assertEqual(len(self.proposer.list_hypotheses()), 0)
    
    def test_full_workflow_with_override(self):
        """Test full workflow with analytics override."""
        with patch('core.policy.get_pareto_threshold', return_value=0.7):
            # Propose hypothesis with override
            response = self.proposer.propose_hypothesis(
                title="Important Research Hypothesis",
                description="This hypothesis is important for research despite low score",
                source_message_id="msg_003",
                pareto_score=0.4,
                user_roles=['analytics'],
                override_reason="Critical for ongoing research project",
                created_by="analytics_user"
            )
            
            # Verify response
            self.assertEqual(response.result, ProposalResult.OVERRIDE)
            self.assertIsNotNone(response.hypothesis_id)
            self.assertEqual(response.pareto_score, 0.4)
            self.assertIsNotNone(response.persisted_at)
            self.assertEqual(response.override_reason, "Critical for ongoing research project")
            
            # Verify persistence
            hypothesis = self.proposer.get_hypothesis(response.hypothesis_id)
            self.assertIsNotNone(hypothesis)
            self.assertEqual(hypothesis.title, "Important Research Hypothesis")
            self.assertEqual(hypothesis.pareto_score, 0.4)
            self.assertEqual(hypothesis.status, HypothesisStatus.PENDING)
            self.assertTrue(hypothesis.metadata.get('override', False))
            self.assertEqual(hypothesis.metadata.get('override_reason'), "Critical for ongoing research project")
    
    def test_auto_score_calculation_workflow(self):
        """Test workflow with automatic score calculation."""
        # Create a compare summary for scoring
        compare_summary = CompareSummary(
            query="Should we adopt this method?",
            stance_a="Evidence supports adoption",
            stance_b="Evidence suggests caution",
            evidence=[
                EvidenceItem(
                    id="ev_001",
                    snippet="Study shows 90% success rate",
                    source="Research Journal",
                    score=0.9,
                    is_external=False
                ),
                EvidenceItem(
                    id="ev_002",
                    snippet="Study shows 10% success rate",
                    source="Alternative Journal",
                    score=0.1,
                    is_external=False
                )
            ],
            decision=Decision(
                verdict="inconclusive",
                confidence=0.6,
                rationale="Mixed evidence"
            ),
            created_at=self.now,
            metadata={}
        )
        
        with patch('core.policy.get_pareto_threshold', return_value=0.5):
            # Propose hypothesis with auto-calculation
            response = self.proposer.propose_hypothesis(
                title="Auto-Scored Hypothesis",
                description="This hypothesis will be automatically scored",
                source_message_id="msg_004",
                compare_summary=compare_summary,
                pareto_score=None,  # Auto-calculate
                user_roles=['user'],
                created_by="researcher"
            )
            
            # Verify response
            self.assertIsNotNone(response.pareto_score)
            self.assertIsNotNone(response.pareto_components)
            self.assertGreaterEqual(response.pareto_score, 0.0)
            self.assertLessEqual(response.pareto_score, 1.0)
            
            # Verify components
            components = response.pareto_components
            self.assertGreaterEqual(components.lift_score_at_k, 0.0)
            self.assertGreaterEqual(components.contradiction_score_inverse, 0.0)
            self.assertGreaterEqual(components.evidence_diversity, 0.0)


def main():
    """Run all tests."""
    print("Running hypotheses Pareto gating tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestParetoScorer,
        TestHypothesisProposer,
        TestHypothesisProposal,
        TestConvenienceFunction,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All hypotheses Pareto gating tests passed!")
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