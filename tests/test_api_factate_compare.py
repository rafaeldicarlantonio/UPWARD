# tests/test_api_factate_compare.py — Comprehensive tests for factate compare endpoint

import unittest
import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

try:
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None
    FastAPI = None

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
    # Mock the supabase dependency
    with patch('vendors.supabase_client.supabase', None):
        from api.factate import router, CompareRequest, CompareResponse
        from core.factare.service import get_factare_service, ComparisonOptions
        from core.factare.compare_internal import RetrievalCandidate
        from core.factare.summary import CompareSummary, EvidenceItem, Decision
        from adapters.web_external import MockWebExternalAdapter

# Create test app (only if FastAPI is available)
if FASTAPI_AVAILABLE:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
else:
    app = None
    client = None

@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestFactateCompareEndpoint(unittest.TestCase):
    """Test the POST /factate/compare endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now()
        
        # Sample retrieval candidates
        self.sample_candidates = [
            {
                'id': 'internal_001',
                'content': 'Internal research shows positive results for this approach.',
                'source': 'Internal Database',
                'score': 0.9,
                'timestamp': (self.now - timedelta(hours=1)).isoformat(),
                'metadata': {'department': 'R&D'}
            },
            {
                'id': 'internal_002',
                'content': 'Internal analysis indicates some concerns with this method.',
                'source': 'Internal Research',
                'score': 0.7,
                'timestamp': (self.now - timedelta(hours=2)).isoformat(),
                'metadata': {'department': 'Analytics'}
            }
        ]
        
        # Sample external URLs
        self.sample_external_urls = [
            'https://example.com/research',
            'https://test.org/analysis'
        ]
        
        # Sample user roles
        self.sample_user_roles = ['pro', 'analytics']
        
        # Sample request data
        self.sample_request = {
            'query': 'Should we adopt this new methodology?',
            'retrieval_candidates': self.sample_candidates,
            'external_urls': self.sample_external_urls,
            'user_roles': self.sample_user_roles,
            'options': {
                'allow_external': True,
                'max_external_snippets': 3,
                'max_snippet_length': 150,
                'timeout_seconds': 2,
                'enable_redaction': True
            }
        }
    
    def test_endpoint_exists(self):
        """Test that the endpoint exists and accepts POST requests."""
        response = client.post("/factate/compare", json=self.sample_request)
        # Should not be 404 (endpoint exists)
        self.assertNotEqual(response.status_code, 404)
    
    @patch('feature_flags.get_feature_flag')
    def test_factare_disabled_returns_404(self, mock_get_flag):
        """Test that 404 is returned when factare is disabled."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': False,
            'factare.allow_external': False
        }.get(flag, False)
        
        response = client.post("/factate/compare", json=self.sample_request)
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("not enabled", response.json()["error"])
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    def test_insufficient_permissions_returns_403(self, mock_can_access, mock_get_flag):
        """Test that 403 is returned when user lacks permissions."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': True
        }.get(flag, False)
        mock_can_access.return_value = False
        
        response = client.post("/factate/compare", json=self.sample_request)
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("Insufficient permissions", response.json()["error"])
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.factare.service.get_factare_service')
    def test_successful_internal_comparison(self, mock_get_service, mock_can_access, mock_get_flag):
        """Test successful internal-only comparison."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': False
        }.get(flag, False)
        mock_can_access.return_value = True
        
        # Mock service response
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.compare_summary = CompareSummary(
            query="Should we adopt this new methodology?",
            stance_a="Evidence supports adoption",
            stance_b="Evidence suggests caution",
            evidence=[],
            decision=Decision(
                verdict="inconclusive",
                confidence=0.6,
                rationale="Mixed evidence"
            ),
            created_at=datetime.now(),
            metadata={}
        )
        mock_result.contradictions = []
        mock_result.used_external = False
        mock_result.timings = {
            'internal_ms': 50.0,
            'external_ms': 0.0,
            'total_ms': 50.0,
            'redaction_ms': 0.0
        }
        mock_result.metadata = {}
        
        mock_service.compare = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service
        
        # Request with external disabled
        request_data = self.sample_request.copy()
        request_data['options']['allow_external'] = False
        
        response = client.post("/factate/compare", json=request_data)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('compare_summary', data)
        self.assertIn('contradictions', data)
        self.assertIn('used_external', data)
        self.assertIn('timings', data)
        self.assertIn('metadata', data)
        
        self.assertFalse(data['used_external'])
        self.assertEqual(data['timings']['internal_ms'], 50.0)
        self.assertEqual(data['timings']['external_ms'], 0.0)
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.policy.is_external_allowed')
    @patch('core.factare.service.get_factare_service')
    def test_successful_external_comparison(self, mock_get_service, mock_is_external, mock_can_access, mock_get_flag):
        """Test successful comparison with external sources."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': True
        }.get(flag, False)
        mock_can_access.return_value = True
        mock_is_external.return_value = True
        
        # Mock service response with external sources
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.compare_summary = CompareSummary(
            query="Should we adopt this new methodology?",
            stance_a="External evidence strongly supports adoption",
            stance_b="Some external sources raise concerns",
            evidence=[],
            decision=Decision(
                verdict="stance_a",
                confidence=0.8,
                rationale="Strong external evidence"
            ),
            created_at=datetime.now(),
            metadata={}
        )
        mock_result.contradictions = [
            {
                'claim_a': 'Method is effective',
                'claim_b': 'Method is ineffective',
                'evidence_a': 'Study shows 90% success',
                'evidence_b': 'Study shows 10% success',
                'confidence': 0.9,
                'contradiction_type': 'evaluative'
            }
        ]
        mock_result.used_external = True
        mock_result.timings = {
            'internal_ms': 50.0,
            'external_ms': 200.0,
            'total_ms': 250.0,
            'redaction_ms': 10.0
        }
        mock_result.metadata = {
            'external_sources_used': 2,
            'external_urls_provided': 2
        }
        
        mock_service.compare = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service
        
        response = client.post("/factate/compare", json=self.sample_request)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['used_external'])
        self.assertEqual(data['timings']['internal_ms'], 50.0)
        self.assertEqual(data['timings']['external_ms'], 200.0)
        self.assertEqual(len(data['contradictions']), 1)
        self.assertEqual(data['contradictions'][0]['contradiction_type'], 'evaluative')
    
    def test_validation_errors(self):
        """Test validation error handling."""
        # Test empty query
        invalid_request = self.sample_request.copy()
        invalid_request['query'] = ""
        
        response = client.post("/factate/compare", json=invalid_request)
        self.assertEqual(response.status_code, 422)  # Validation error
        
        # Test invalid score
        invalid_request = self.sample_request.copy()
        invalid_request['retrieval_candidates'][0]['score'] = 1.5  # Invalid score
        
        response = client.post("/factate/compare", json=invalid_request)
        self.assertEqual(response.status_code, 422)  # Validation error
        
        # Test too many external URLs
        invalid_request = self.sample_request.copy()
        invalid_request['external_urls'] = ['https://example.com'] * 15  # Too many
        
        response = client.post("/factate/compare", json=invalid_request)
        self.assertEqual(response.status_code, 422)  # Validation error
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.factare.service.get_factare_service')
    def test_timings_included(self, mock_get_service, mock_can_access, mock_get_flag):
        """Test that timings are included in response."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': False
        }.get(flag, False)
        mock_can_access.return_value = True
        
        # Mock service response
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.compare_summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.5, rationale="Test"),
            created_at=datetime.now(),
            metadata={}
        )
        mock_result.contradictions = []
        mock_result.used_external = False
        mock_result.timings = {
            'internal_ms': 75.5,
            'external_ms': 0.0,
            'total_ms': 75.5,
            'redaction_ms': 5.2
        }
        mock_result.metadata = {}
        
        mock_service.compare = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service
        
        response = client.post("/factate/compare", json=self.sample_request)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('timings', data)
        timings = data['timings']
        self.assertEqual(timings['internal_ms'], 75.5)
        self.assertEqual(timings['external_ms'], 0.0)
        self.assertEqual(timings['total_ms'], 75.5)
        self.assertEqual(timings['redaction_ms'], 5.2)
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.factare.service.get_factare_service')
    def test_metadata_included(self, mock_get_service, mock_can_access, mock_get_flag):
        """Test that metadata is included in response."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': False
        }.get(flag, False)
        mock_can_access.return_value = True
        
        # Mock service response
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.compare_summary = CompareSummary(
            query="Test query",
            stance_a="Stance A",
            stance_b="Stance B",
            evidence=[],
            decision=Decision(verdict="inconclusive", confidence=0.5, rationale="Test"),
            created_at=datetime.now(),
            metadata={}
        )
        mock_result.contradictions = []
        mock_result.used_external = False
        mock_result.timings = {'internal_ms': 50.0, 'external_ms': 0.0, 'total_ms': 50.0, 'redaction_ms': 0.0}
        mock_result.metadata = {
            'user_roles': ['pro'],
            'external_sources_used': 0,
            'contradictions_count': 0,
            'processing_timestamp': '2023-01-01T00:00:00'
        }
        
        mock_service.compare = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service
        
        response = client.post("/factate/compare", json=self.sample_request)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('metadata', data)
        metadata = data['metadata']
        self.assertEqual(metadata['user_roles'], ['pro'])
        self.assertEqual(metadata['external_sources_used'], 0)
        self.assertEqual(metadata['contradictions_count'], 0)
    
    def test_user_roles_from_header(self):
        """Test that user roles are extracted from headers."""
        headers = {'X-User-Roles': 'admin,pro,analytics'}
        
        with patch('feature_flags.get_feature_flag') as mock_get_flag, \
             patch('core.policy.can_access_factare') as mock_can_access, \
             patch('core.factare.service.get_factare_service') as mock_get_service:
            
            mock_get_flag.side_effect = lambda flag: {
                'factare.enabled': True,
                'factare.allow_external': False
            }.get(flag, False)
            mock_can_access.return_value = True
            
            # Mock service response
            mock_service = MagicMock()
            mock_result = MagicMock()
            mock_result.compare_summary = CompareSummary(
                query="Test query",
                stance_a="Stance A",
                stance_b="Stance B",
                evidence=[],
                decision=Decision(verdict="inconclusive", confidence=0.5, rationale="Test"),
                created_at=datetime.now(),
                metadata={}
            )
            mock_result.contradictions = []
            mock_result.used_external = False
            mock_result.timings = {'internal_ms': 50.0, 'external_ms': 0.0, 'total_ms': 50.0, 'redaction_ms': 0.0}
            mock_result.metadata = {}
            
            mock_service.compare = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service
            
            # Request without user_roles in body
            request_data = self.sample_request.copy()
            del request_data['user_roles']
            
            response = client.post("/factate/compare", json=request_data, headers=headers)
            
            self.assertEqual(response.status_code, 200)
            # Verify that the service was called with roles from header
            mock_service.compare.assert_called_once()
            call_args = mock_service.compare.call_args
            self.assertEqual(call_args[1]['user_roles'], ['admin', 'pro', 'analytics'])

@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestFactateStatusEndpoint(unittest.TestCase):
    """Test the GET /factate/status endpoint."""
    
    @patch('feature_flags.get_feature_flag')
    def test_status_when_factare_disabled(self, mock_get_flag):
        """Test status endpoint when factare is disabled."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': False,
            'factare.allow_external': False
        }.get(flag, False)
        
        response = client.get("/factate/status")
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("not enabled", response.json()["error"])
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.factare.service.get_factare_service')
    def test_status_when_factare_enabled(self, mock_get_service, mock_get_flag):
        """Test status endpoint when factare is enabled."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': True
        }.get(flag, False)
        
        mock_service = MagicMock()
        mock_service.get_service_status.return_value = {
            'factare_enabled': True,
            'external_allowed': True,
            'internal_comparator_available': True,
            'external_adapter_available': False
        }
        mock_get_service.return_value = mock_service
        
        response = client.get("/factate/status")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['factare_enabled'])
        self.assertTrue(data['external_allowed'])
        self.assertTrue(data['internal_comparator_available'])
        self.assertFalse(data['external_adapter_available'])

@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestFactateHealthEndpoint(unittest.TestCase):
    """Test the GET /factate/health endpoint."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/factate/health")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['service'], 'factate')
        self.assertIn('timestamp', data)

@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestRequestValidation(unittest.TestCase):
    """Test request validation and data conversion."""
    
    def test_retrieval_candidate_validation(self):
        """Test retrieval candidate data validation."""
        # Valid candidate
        valid_candidate = {
            'id': 'test_001',
            'content': 'Test content',
            'source': 'Test Source',
            'score': 0.8,
            'metadata': {'type': 'test'},
            'url': 'https://example.com',
            'timestamp': '2023-01-01T00:00:00'
        }
        
        # This should not raise validation error
        candidate_data = CompareRequest.RetrievalCandidateData(**valid_candidate)
        self.assertEqual(candidate_data.id, 'test_001')
        self.assertEqual(candidate_data.score, 0.8)
    
    def test_options_validation(self):
        """Test comparison options validation."""
        # Valid options
        valid_options = {
            'allow_external': True,
            'max_external_snippets': 5,
            'max_snippet_length': 200,
            'timeout_seconds': 2,
            'enable_redaction': True
        }
        
        options_data = CompareRequest.ComparisonOptionsData(**valid_options)
        self.assertTrue(options_data.allow_external)
        self.assertEqual(options_data.max_external_snippets, 5)
    
    def test_score_validation(self):
        """Test score validation (0.0 to 1.0)."""
        # Valid scores
        valid_scores = [0.0, 0.5, 1.0]
        for score in valid_scores:
            candidate_data = CompareRequest.RetrievalCandidateData(
                id='test',
                content='test',
                source='test',
                score=score
            )
            self.assertEqual(candidate_data.score, score)
        
        # Invalid scores should raise validation error
        invalid_scores = [-0.1, 1.1, 2.0]
        for score in invalid_scores:
            with self.assertRaises(ValueError):
                CompareRequest.RetrievalCandidateData(
                    id='test',
                    content='test',
                    source='test',
                    score=score
                )

@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestErrorHandling(unittest.TestCase):
    """Test error handling and responses."""
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.factare.service.get_factare_service')
    def test_service_exception_handling(self, mock_get_service, mock_can_access, mock_get_flag):
        """Test handling of service exceptions."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': False
        }.get(flag, False)
        mock_can_access.return_value = True
        
        # Mock service to raise exception
        mock_service = MagicMock()
        mock_service.compare = AsyncMock(side_effect=Exception("Service error"))
        mock_get_service.return_value = mock_service
        
        request_data = {
            'query': 'Test query',
            'retrieval_candidates': [],
            'external_urls': [],
            'user_roles': ['user'],
            'options': {'allow_external': False}
        }
        
        response = client.post("/factate/compare", json=request_data)
        
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('Internal server error', data['error'])
        self.assertIn('Service error', data['detail'])
    
    def test_malformed_json_handling(self):
        """Test handling of malformed JSON."""
        response = client.post(
            "/factate/compare",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        self.assertEqual(response.status_code, 422)  # Validation error

@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios."""
    
    @patch('feature_flags.get_feature_flag')
    @patch('core.policy.can_access_factare')
    @patch('core.policy.is_external_allowed')
    @patch('core.factare.service.get_factare_service')
    def test_full_workflow_with_external(self, mock_get_service, mock_is_external, mock_can_access, mock_get_flag):
        """Test full workflow with external sources enabled."""
        mock_get_flag.side_effect = lambda flag: {
            'factare.enabled': True,
            'factare.allow_external': True
        }.get(flag, False)
        mock_can_access.return_value = True
        mock_is_external.return_value = True
        
        # Mock service response
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.compare_summary = CompareSummary(
            query="Should we implement AI?",
            stance_a="AI implementation is beneficial",
            stance_b="AI implementation has risks",
            evidence=[],
            decision=Decision(
                verdict="stance_a",
                confidence=0.8,
                rationale="Strong evidence supports AI implementation"
            ),
            created_at=datetime.now(),
            metadata={}
        )
        mock_result.contradictions = [
            {
                'claim_a': 'AI is safe',
                'claim_b': 'AI is unsafe',
                'evidence_a': 'Studies show AI is safe',
                'evidence_b': 'Studies show AI is unsafe',
                'confidence': 0.7,
                'contradiction_type': 'evaluative'
            }
        ]
        mock_result.used_external = True
        mock_result.timings = {
            'internal_ms': 100.0,
            'external_ms': 300.0,
            'total_ms': 400.0,
            'redaction_ms': 20.0
        }
        mock_result.metadata = {
            'external_sources_used': 2,
            'external_urls_provided': 2,
            'contradictions_count': 1
        }
        
        mock_service.compare = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service
        
        request_data = {
            'query': 'Should we implement AI?',
            'retrieval_candidates': [
                {
                    'id': 'internal_001',
                    'content': 'Internal research supports AI',
                    'source': 'Internal DB',
                    'score': 0.9,
                    'timestamp': datetime.now().isoformat()
                }
            ],
            'external_urls': [
                'https://example.com/ai-benefits',
                'https://test.org/ai-risks'
            ],
            'user_roles': ['pro', 'analytics'],
            'options': {
                'allow_external': True,
                'max_external_snippets': 3,
                'max_snippet_length': 200,
                'timeout_seconds': 2,
                'enable_redaction': True
            }
        }
        
        response = client.post("/factate/compare", json=request_data)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure
        self.assertIn('compare_summary', data)
        self.assertIn('contradictions', data)
        self.assertIn('used_external', data)
        self.assertIn('timings', data)
        self.assertIn('metadata', data)
        
        # Verify external usage
        self.assertTrue(data['used_external'])
        self.assertEqual(data['timings']['external_ms'], 300.0)
        self.assertEqual(len(data['contradictions']), 1)
        self.assertEqual(data['contradictions'][0]['contradiction_type'], 'evaluative')
        
        # Verify metadata
        self.assertEqual(data['metadata']['external_sources_used'], 2)
        self.assertEqual(data['metadata']['contradictions_count'], 1)


def main():
    """Run all tests."""
    print("Running factate compare endpoint tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestFactateCompareEndpoint,
        TestFactateStatusEndpoint,
        TestFactateHealthEndpoint,
        TestRequestValidation,
        TestErrorHandling,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All factate compare endpoint tests passed!")
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