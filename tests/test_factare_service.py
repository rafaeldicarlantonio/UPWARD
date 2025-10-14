# tests/test_factare_service.py — Tests for factare service layer

import unittest
import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

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
    from core.factare.service import (
        FactareService, 
        ComparisonOptions, 
        ComparisonResult,
        get_factare_service,
        compare_factare
    )
    from core.factare.compare_internal import RetrievalCandidate
    from core.factare.summary import CompareSummary, Decision
    from adapters.web_external import MockWebExternalAdapter

class TestComparisonOptions(unittest.TestCase):
    """Test ComparisonOptions dataclass."""
    
    def test_default_options(self):
        """Test default comparison options."""
        options = ComparisonOptions()
        
        self.assertFalse(options.allow_external)
        self.assertEqual(options.max_external_snippets, 5)
        self.assertEqual(options.max_snippet_length, 200)
        self.assertEqual(options.timeout_seconds, 2)
        self.assertTrue(options.enable_redaction)
    
    def test_custom_options(self):
        """Test custom comparison options."""
        options = ComparisonOptions(
            allow_external=True,
            max_external_snippets=10,
            max_snippet_length=300,
            timeout_seconds=5,
            enable_redaction=False
        )
        
        self.assertTrue(options.allow_external)
        self.assertEqual(options.max_external_snippets, 10)
        self.assertEqual(options.max_snippet_length, 300)
        self.assertEqual(options.timeout_seconds, 5)
        self.assertFalse(options.enable_redaction)

class TestFactareService(unittest.TestCase):
    """Test FactareService functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = FactareService()
        self.now = datetime.now()
        
        # Sample retrieval candidates
        self.sample_candidates = [
            RetrievalCandidate(
                id='internal_001',
                content='Internal research shows positive results',
                source='Internal Database',
                score=0.9,
                timestamp=self.now - timedelta(hours=1)
            ),
            RetrievalCandidate(
                id='internal_002',
                content='Internal analysis indicates some concerns',
                source='Internal Research',
                score=0.7,
                timestamp=self.now - timedelta(hours=2)
            )
        ]
        
        # Sample external URLs
        self.sample_external_urls = [
            'https://example.com/research',
            'https://test.org/analysis'
        ]
        
        # Sample user roles
        self.sample_user_roles = ['pro', 'analytics']
        
        # Sample options
        self.sample_options = ComparisonOptions(
            allow_external=True,
            max_external_snippets=3,
            max_snippet_length=150,
            timeout_seconds=2,
            enable_redaction=True
        )
    
    def test_service_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service.internal_comparator)
        self.assertIsNone(self.service.external_adapter)
        self.assertIsNone(self.service._external_config)
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    async def test_compare_factare_disabled(self, mock_can_access, mock_get_flag):
        """Test comparison when factare is disabled."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': False,
            'factare.allow_external': False
        }.get(flag, False)
        mock_can_access.return_value = True
        
        with self.assertRaises(ValueError) as context:
            await self.service.compare(
                query="Test query",
                retrieval_candidates=self.sample_candidates,
                external_urls=self.sample_external_urls,
                user_roles=self.sample_user_roles,
                options=self.sample_options
            )
        
        self.assertIn("not enabled", str(context.exception))
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    async def test_compare_insufficient_permissions(self, mock_can_access, mock_get_flag):
        """Test comparison when user lacks permissions."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': True
        }.get(flag, False)
        mock_can_access.return_value = False
        
        with self.assertRaises(ValueError) as context:
            await self.service.compare(
                query="Test query",
                retrieval_candidates=self.sample_candidates,
                external_urls=self.sample_external_urls,
                user_roles=self.sample_user_roles,
                options=self.sample_options
            )
        
        self.assertIn("permission", str(context.exception))
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.policy.is_external_allowed')
    async def test_compare_internal_only(self, mock_is_external, mock_can_access, mock_get_flag):
        """Test internal-only comparison."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': False
        }.get(flag, False)
        mock_can_access.return_value = True
        mock_is_external.return_value = False
        
        # Mock internal comparator
        mock_internal_result = MagicMock()
        mock_internal_result.contradictions = []
        mock_internal_result.has_binary_contrast = True
        mock_internal_result.stance_a = "Stance A"
        mock_internal_result.stance_b = "Stance B"
        mock_internal_result.decision = Decision(
            verdict="inconclusive",
            confidence=0.6,
            rationale="Test rationale"
        )
        mock_internal_result.evidence_items = []
        mock_internal_result.metadata = {}
        
        self.service.internal_comparator.compare = MagicMock(return_value=mock_internal_result)
        self.service.internal_comparator.create_compare_summary = MagicMock(return_value=CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.6, rationale="Test"),
            created_at=datetime.now(),
            metadata={}
        ))
        
        result = await self.service.compare(
            query="Test query",
            retrieval_candidates=self.sample_candidates,
            external_urls=self.sample_external_urls,
            user_roles=self.sample_user_roles,
            options=self.sample_options
        )
        
        self.assertIsInstance(result, ComparisonResult)
        self.assertFalse(result.used_external)
        self.assertIn('internal_ms', result.timings)
        self.assertEqual(result.timings['external_ms'], 0.0)
        self.assertEqual(len(result.contradictions), 0)
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.policy.is_external_allowed')
    async def test_compare_with_external(self, mock_is_external, mock_can_access, mock_get_flag):
        """Test comparison with external sources."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': True
        }.get(flag, False)
        mock_can_access.return_value = True
        mock_is_external.return_value = True
        
        # Mock internal comparator
        mock_internal_result = MagicMock()
        mock_internal_result.contradictions = []
        mock_internal_result.has_binary_contrast = True
        mock_internal_result.stance_a = "Stance A"
        mock_internal_result.stance_b = "Stance B"
        mock_internal_result.decision = Decision(
            verdict="inconclusive",
            confidence=0.6,
            rationale="Test rationale"
        )
        mock_internal_result.evidence_items = []
        mock_internal_result.metadata = {}
        
        self.service.internal_comparator.compare = MagicMock(return_value=mock_internal_result)
        self.service.internal_comparator.create_compare_summary = MagicMock(return_value=CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.6, rationale="Test"),
            created_at=datetime.now(),
            metadata={}
        ))
        
        # Mock external adapter
        mock_external_adapter = MagicMock()
        mock_external_result = MagicMock()
        mock_external_result.contradictions = [
            MagicMock(
                claim_a="Claim A",
                claim_b="Claim B",
                evidence_a="Evidence A",
                evidence_b="Evidence B",
                confidence=0.8,
                contradiction_type="evaluative"
            )
        ]
        mock_external_result.used_external = True
        mock_external_result.timings = {
            'internal_ms': 50.0,
            'external_ms': 200.0,
            'total_ms': 250.0,
            'redaction_ms': 10.0
        }
        mock_external_result.metadata = {
            'external_sources_used': 2,
            'external_urls_provided': 2
        }
        
        mock_external_adapter.create_compare_summary_with_external = AsyncMock(return_value=CompareSummary(
            query="Test query",
            stance_a="External Stance A",
            stance_b="External Stance B",
            evidence=[],
            decision=Decision(verdict="stance_a", confidence=0.8, rationale="External"),
            created_at=datetime.now(),
            metadata={}
        ))
        mock_external_adapter.compare_with_external = AsyncMock(return_value=mock_external_result)
        
        # Mock the external adapter creation
        with patch.object(self.service, '_get_external_adapter', return_value=mock_external_adapter):
            result = await self.service.compare(
                query="Test query",
                retrieval_candidates=self.sample_candidates,
                external_urls=self.sample_external_urls,
                user_roles=self.sample_user_roles,
                options=self.sample_options
            )
        
        self.assertIsInstance(result, ComparisonResult)
        self.assertTrue(result.used_external)
        self.assertGreater(result.timings['external_ms'], 0.0)
        self.assertEqual(len(result.contradictions), 1)
        self.assertEqual(result.contradictions[0]['contradiction_type'], 'evaluative')
    
    def test_create_retrieval_candidates_from_dicts(self):
        """Test creating retrieval candidates from dictionary data."""
        candidates_data = [
            {
                'id': 'test_001',
                'content': 'Test content',
                'source': 'Test Source',
                'score': 0.8,
                'metadata': {'type': 'test'},
                'url': 'https://example.com',
                'timestamp': '2023-01-01T00:00:00'
            }
        ]
        
        candidates = self.service.create_retrieval_candidates_from_dicts(candidates_data)
        
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].id, 'test_001')
        self.assertEqual(candidates[0].content, 'Test content')
        self.assertEqual(candidates[0].score, 0.8)
        self.assertEqual(candidates[0].metadata['type'], 'test')
    
    def test_validate_options(self):
        """Test options validation."""
        options_data = {
            'allow_external': True,
            'max_external_snippets': 10,
            'max_snippet_length': 300,
            'timeout_seconds': 5,
            'enable_redaction': False
        }
        
        options = self.service.validate_options(options_data)
        
        self.assertIsInstance(options, ComparisonOptions)
        self.assertTrue(options.allow_external)
        self.assertEqual(options.max_external_snippets, 10)
        self.assertEqual(options.max_snippet_length, 300)
        self.assertEqual(options.timeout_seconds, 5)
        self.assertFalse(options.enable_redaction)
    
    def test_get_service_status(self):
        """Test getting service status."""
        with patch('feature_flags.get_feature_flag') as mock_get_flag:
            mock_get_flag.side_effect = lambda flag: {
                'factare.enabled': True,
                'factare.allow_external': True
            }.get(flag, False)
            
            status = self.service.get_service_status()
            
            self.assertIn('factare_enabled', status)
            self.assertIn('external_allowed', status)
            self.assertIn('internal_comparator_available', status)
            self.assertIn('external_adapter_available', status)
            self.assertTrue(status['factare_enabled'])
            self.assertTrue(status['external_allowed'])
            self.assertTrue(status['internal_comparator_available'])

class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    def test_get_factare_service(self):
        """Test getting the global factare service."""
        service = get_factare_service()
        
        self.assertIsInstance(service, FactareService)
        
        # Should return the same instance
        service2 = get_factare_service()
        self.assertIs(service, service2)
    
    @patch('core.factare.service.get_factare_service')
    async def test_compare_factare_convenience(self, mock_get_service):
        """Test compare_factare convenience function."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.compare_summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.6, rationale="Test"),
            created_at=datetime.now(),
            metadata={}
        )
        mock_result.contradictions = []
        mock_result.used_external = False
        mock_result.timings = {'internal_ms': 50.0, 'external_ms': 0.0, 'total_ms': 50.0, 'redaction_ms': 0.0}
        mock_result.metadata = {}
        
        mock_service.compare = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service
        
        result = await compare_factare(
            query="Test query",
            retrieval_candidates=[],
            external_urls=[],
            user_roles=['user'],
            options=ComparisonOptions()
        )
        
        self.assertIsInstance(result, ComparisonResult)
        mock_service.compare.assert_called_once()

class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios."""
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.policy.is_external_allowed')
    async def test_full_workflow_internal_only(self, mock_is_external, mock_can_access, mock_get_flag):
        """Test full workflow with internal-only comparison."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': False
        }.get(flag, False)
        mock_can_access.return_value = True
        mock_is_external.return_value = False
        
        service = FactareService()
        
        # Mock internal comparator
        mock_internal_result = MagicMock()
        mock_internal_result.contradictions = [
            MagicMock(
                claim_a="Method is effective",
                claim_b="Method is ineffective",
                evidence_a="Study shows 90% success",
                evidence_b="Study shows 10% success",
                confidence=0.9,
                contradiction_type="evaluative"
            )
        ]
        mock_internal_result.has_binary_contrast = True
        mock_internal_result.stance_a = "Evidence supports the method"
        mock_internal_result.stance_b = "Evidence questions the method"
        mock_internal_result.decision = Decision(
            verdict="inconclusive",
            confidence=0.6,
            rationale="Mixed evidence with contradictions"
        )
        mock_internal_result.evidence_items = []
        mock_internal_result.metadata = {}
        
        service.internal_comparator.compare = MagicMock(return_value=mock_internal_result)
        service.internal_comparator.create_compare_summary = MagicMock(return_value=CompareSummary(
            query="Should we adopt this method?",
            stance_a="Evidence supports the method",
            stance_b="Evidence questions the method",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.6, rationale="Mixed evidence"),
            created_at=datetime.now(),
            metadata={}
        ))
        
        candidates = [
            RetrievalCandidate(
                id='internal_001',
                content='Internal research shows positive results',
                source='Internal Database',
                score=0.9,
                timestamp=datetime.now()
            )
        ]
        
        options = ComparisonOptions(allow_external=False)
        
        result = await service.compare(
            query="Should we adopt this method?",
            retrieval_candidates=candidates,
            external_urls=[],
            user_roles=['pro'],
            options=options
        )
        
        self.assertIsInstance(result, ComparisonResult)
        self.assertFalse(result.used_external)
        self.assertEqual(len(result.contradictions), 1)
        self.assertEqual(result.contradictions[0]['contradiction_type'], 'evaluative')
        self.assertGreater(result.timings['internal_ms'], 0.0)
        self.assertEqual(result.timings['external_ms'], 0.0)
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.policy.is_external_allowed')
    async def test_external_fallback_on_error(self, mock_is_external, mock_can_access, mock_get_flag):
        """Test fallback to internal-only when external fails."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': True
        }.get(flag, False)
        mock_can_access.return_value = True
        mock_is_external.return_value = True
        
        service = FactareService()
        
        # Mock internal comparator
        mock_internal_result = MagicMock()
        mock_internal_result.contradictions = []
        mock_internal_result.has_binary_contrast = True
        mock_internal_result.stance_a = "Stance A"
        mock_internal_result.stance_b = "Stance B"
        mock_internal_result.decision = Decision(
            verdict="inconclusive",
            confidence=0.6,
            rationale="Test rationale"
        )
        mock_internal_result.evidence_items = []
        mock_internal_result.metadata = {}
        
        service.internal_comparator.compare = MagicMock(return_value=mock_internal_result)
        service.internal_comparator.create_compare_summary = MagicMock(return_value=CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.6, rationale="Test"),
            created_at=datetime.now(),
            metadata={}
        ))
        
        # Mock external adapter to raise exception
        mock_external_adapter = MagicMock()
        mock_external_adapter.create_compare_summary_with_external = AsyncMock(
            side_effect=Exception("External service error")
        )
        
        with patch.object(service, '_get_external_adapter', return_value=mock_external_adapter):
            result = await service.compare(
                query="Test query",
                retrieval_candidates=[],
                external_urls=['https://example.com'],
                user_roles=['pro'],
                options=ComparisonOptions(allow_external=True)
            )
        
        self.assertIsInstance(result, ComparisonResult)
        # Should fall back to internal-only
        self.assertFalse(result.used_external)


def main():
    """Run all tests."""
    print("Running factare service tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestComparisonOptions,
        TestFactareService,
        TestConvenienceFunctions,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All factare service tests passed!")
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