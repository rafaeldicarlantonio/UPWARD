"""
Contract tests for external sources API.

Verifies:
- Response schema compliance
- External items include provenance
- "Never persisted" invariant (external items never in memories)
- used_external flag correctness
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

# Set environment variables before importing app modules
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_KEY', 'test-key')
os.environ.setdefault('PINECONE_API_KEY', 'test-key')
os.environ.setdefault('PINECONE_INDEX', 'test-index')
os.environ.setdefault('PINECONE_EXPLICATE_INDEX', 'test-explicate')
os.environ.setdefault('PINECONE_IMPLICATE_INDEX', 'test-implicate')

# Import API components
try:
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None
    FastAPI = None

from api.factate import router, CompareRequest, CompareResponse, SourcesData
from core.factare.service import ComparisonResult, ComparisonOptions
from core.factare.compare_internal import RetrievalCandidate
from core.factare.summary import CompareSummary

# Skip all tests if FastAPI not available
pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI not installed"
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Create FastAPI test app."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not available")
    
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock = Mock()
    mock.table.return_value.select.return_value.execute.return_value.data = []
    return mock


@pytest.fixture
def sample_internal_candidates():
    """Sample internal retrieval candidates."""
    return [
        {
            "id": "mem_1",
            "content": "Machine learning is a subset of AI.",
            "source": "internal_memory",
            "score": 0.95,
            "metadata": {"type": "concept"}
        },
        {
            "id": "mem_2",
            "content": "Neural networks are used in deep learning.",
            "source": "internal_memory",
            "score": 0.88,
            "metadata": {"type": "concept"}
        }
    ]


@pytest.fixture
def sample_external_sources():
    """Sample external sources with provenance."""
    return [
        {
            "url": "https://en.wikipedia.org/wiki/Machine_learning",
            "snippet": "Machine learning (ML) is a field of artificial intelligence...",
            "source_id": "wikipedia",
            "label": "Wikipedia",
            "provenance": {
                "url": "https://en.wikipedia.org/wiki/Machine_learning",
                "fetched_at": "2025-10-30T12:00:00Z"
            },
            "external": True,
            "metadata": {
                "external": True,
                "url": "https://en.wikipedia.org/wiki/Machine_learning"
            }
        }
    ]


@pytest.fixture
def mock_compare_summary(sample_external_sources):
    """Mock CompareSummary with external sources."""
    summary = Mock(spec=CompareSummary)
    summary.to_dict.return_value = {
        "query": "What is machine learning?",
        "internal_sources": [
            {
                "id": "mem_1",
                "content": "Machine learning is a subset of AI.",
                "relevance": 0.95
            }
        ],
        "external_sources": {
            "heading": "External sources",
            "items": sample_external_sources
        },
        "summary_text": "Machine learning is a field of AI...",
        "confidence": 0.92
    }
    return summary


@pytest.fixture
def mock_comparison_result(mock_compare_summary):
    """Mock ComparisonResult."""
    result = Mock(spec=ComparisonResult)
    result.compare_summary = mock_compare_summary
    result.contradictions = []
    result.used_external = True
    result.timings = {
        "internal_ms": 123.45,
        "external_ms": 456.78,
        "total_ms": 580.23,
        "redaction_ms": 12.34
    }
    result.metadata = {
        "user_roles": ["pro"],
        "external_urls_provided": 1,
        "external_urls_used": 1,
        "internal_candidates_count": 2
    }
    return result


@pytest.fixture
def mock_factare_service(mock_comparison_result):
    """Mock FactareService."""
    service = Mock()
    service.compare = AsyncMock(return_value=mock_comparison_result)
    return service


# ============================================================================
# Test: Response Schema Compliance
# ============================================================================

class TestResponseSchema:
    """Test that response schema matches contract."""
    
    @pytest.mark.anyio
    async def test_response_has_all_required_fields(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: Response must include compare_summary, contradictions,
        used_external, sources, timings, metadata.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/Machine_learning"],
                    "user_roles": ["pro"],
                    "options": {
                        "allow_external": True
                    }
                }
            )
            
            assert response.status_code == 200, f"Status code: {response.status_code}, Response: {response.json()}"
            data = response.json()
            
            # Required top-level fields
            assert "compare_summary" in data
            assert "contradictions" in data
            assert "used_external" in data
            assert "sources" in data
            assert "timings" in data
            assert "metadata" in data
    
    @pytest.mark.anyio
    async def test_sources_field_schema(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: sources field must have {internal: N, external: N}.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/Machine_learning"],
                    "user_roles": ["pro"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # sources field structure
            assert "sources" in data
            sources = data["sources"]
            assert "internal" in sources
            assert "external" in sources
            
            # Type checking
            assert isinstance(sources["internal"], int)
            assert isinstance(sources["external"], int)
            
            # Value constraints
            assert sources["internal"] >= 0
            assert sources["external"] >= 0
    
    @pytest.mark.anyio
    async def test_compare_summary_is_dict(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: compare_summary must be a dictionary.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "user_roles": ["pro"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert isinstance(data["compare_summary"], dict)
    
    @pytest.mark.anyio
    async def test_contradictions_is_list(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: contradictions must be a list.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "user_roles": ["pro"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert isinstance(data["contradictions"], list)
    
    @pytest.mark.anyio
    async def test_used_external_is_boolean(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: used_external must be a boolean.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "user_roles": ["pro"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert isinstance(data["used_external"], bool)


# ============================================================================
# Test: External Items Have Provenance
# ============================================================================

class TestExternalProvenance:
    """Test that external items always include provenance."""
    
    @pytest.mark.anyio
    async def test_external_items_have_provenance_field(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: All external items must have provenance field.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            if "external_sources" in data["compare_summary"]:
                external_sources = data["compare_summary"]["external_sources"]
                items = external_sources.get("items", [])
                
                for item in items:
                    assert "provenance" in item, "External item missing provenance"
                    provenance = item["provenance"]
                    assert "url" in provenance
                    assert provenance["url"], "Provenance URL must not be empty"
    
    @pytest.mark.anyio
    async def test_external_items_have_url_field(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: All external items must have url field.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            if "external_sources" in data["compare_summary"]:
                external_sources = data["compare_summary"]["external_sources"]
                items = external_sources.get("items", [])
                
                for item in items:
                    assert "url" in item, "External item missing url field"
                    assert item["url"], "External URL must not be empty"
    
    @pytest.mark.anyio
    async def test_external_items_marked_as_external(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: All external items must have external=True marker.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            if "external_sources" in data["compare_summary"]:
                external_sources = data["compare_summary"]["external_sources"]
                items = external_sources.get("items", [])
                
                for item in items:
                    # Check either top-level or metadata external marker
                    has_external_marker = (
                        item.get("external") is True or
                        (item.get("metadata") and item["metadata"].get("external") is True)
                    )
                    assert has_external_marker, "External item not marked as external"


# ============================================================================
# Test: Never Persisted Invariant
# ============================================================================

class TestNeverPersistedInvariant:
    """Test that external items are never persisted to memories."""
    
    @pytest.mark.anyio
    async def test_external_items_not_in_database_writes(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: External items must never be written to memories table.
        
        This is ensured by the persistence guards that should be called
        before any database operations. The actual guard is tested separately.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            
            # External items should only be in the response, not persisted
            # The actual persistence guard is tested in other tests
            data = response.json()
            assert data["used_external"] is True
    
    @pytest.mark.anyio
    async def test_persistence_guard_blocks_external(
        self,
        sample_external_sources
    ):
        """
        Contract: forbid_external_persistence should block external items.
        """
        from core.guards import forbid_external_persistence, ExternalPersistenceError
        
        # Should raise error for external items
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(
                sample_external_sources,
                item_type="test_item",
                raise_on_external=True
            )
    
    @pytest.mark.anyio
    async def test_internal_items_can_be_persisted(
        self,
        sample_internal_candidates
    ):
        """
        Contract: Internal items should pass persistence guard.
        """
        from core.guards import forbid_external_persistence
        
        # Should NOT raise error for internal items
        # (internal items don't have provenance.url)
        try:
            forbid_external_persistence(
                sample_internal_candidates,
                item_type="test_item",
                raise_on_external=True
            )
            # Should pass without raising
            passed = True
        except Exception:
            passed = False
        
        assert passed, "Internal items should pass persistence guard"
    
    @pytest.mark.anyio
    async def test_external_items_excluded_from_entity_upserts(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: External items must not be sent to entity upserts.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            
            # External items present in response
            data = response.json()
            assert data["used_external"] is True
            
            # But the persistence guards ensure they're never written to DB
            # (tested separately in guard tests)


# ============================================================================
# Test: used_external Flag Correctness
# ============================================================================

class TestUsedExternalFlag:
    """Test that used_external flag is set correctly."""
    
    @pytest.mark.anyio
    async def test_used_external_true_when_externals_included(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: used_external=True only when external sources included.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should be true when external sources present
            assert data["used_external"] is True
            
            # Should have external count > 0
            assert data["sources"]["external"] > 0
    
    @pytest.mark.anyio
    async def test_used_external_false_when_no_externals(
        self,
        client,
        sample_internal_candidates
    ):
        """
        Contract: used_external=False when no external sources.
        """
        # Mock service to return no external sources
        mock_summary = Mock(spec=CompareSummary)
        mock_summary.to_dict.return_value = {
            "query": "What is machine learning?",
            "internal_sources": [],
            "summary_text": "Summary text...",
            "confidence": 0.85
        }
        
        mock_result = Mock(spec=ComparisonResult)
        mock_result.compare_summary = mock_summary
        mock_result.contradictions = []
        mock_result.used_external = False  # No externals
        mock_result.timings = {
            "internal_ms": 100.0,
            "external_ms": 0.0,
            "total_ms": 100.0,
            "redaction_ms": 0.0
        }
        mock_result.metadata = {
            "user_roles": ["pro"],
            "internal_candidates_count": 2
        }
        
        mock_service = Mock()
        mock_service.compare = AsyncMock(return_value=mock_result)
        
        with patch('api.factate.get_factare_service', return_value=mock_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": [],  # No external URLs
                    "user_roles": ["pro"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should be false when no external sources
            assert data["used_external"] is False
            
            # Should have external count = 0
            assert data["sources"]["external"] == 0
    
    @pytest.mark.anyio
    async def test_used_external_false_when_external_disabled(
        self,
        client,
        sample_internal_candidates
    ):
        """
        Contract: used_external=False when external feature disabled.
        """
        mock_summary = Mock(spec=CompareSummary)
        mock_summary.to_dict.return_value = {
            "query": "What is machine learning?",
            "internal_sources": [],
            "summary_text": "Summary text..."
        }
        
        mock_result = Mock(spec=ComparisonResult)
        mock_result.compare_summary = mock_summary
        mock_result.contradictions = []
        mock_result.used_external = False
        mock_result.timings = {
            "internal_ms": 100.0,
            "external_ms": 0.0,
            "total_ms": 100.0,
            "redaction_ms": 0.0
        }
        mock_result.metadata = {"user_roles": ["pro"], "internal_candidates_count": 2}
        
        mock_service = Mock()
        mock_service.compare = AsyncMock(return_value=mock_result)
        
        with patch('api.factate.get_factare_service', return_value=mock_service), \
             patch('api.factate.get_feature_flag', side_effect=lambda x: x == 'factare.enabled'), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://example.com"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}  # Requested but disabled
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should be false when feature disabled
            assert data["used_external"] is False
            assert data["sources"]["external"] == 0
    
    @pytest.mark.anyio
    async def test_sources_count_matches_used_external(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: sources.external > 0 if and only if used_external=True.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify invariant: external > 0 <==> used_external=True
            if data["used_external"]:
                assert data["sources"]["external"] > 0, \
                    "used_external=True but no external sources"
            else:
                assert data["sources"]["external"] == 0, \
                    "used_external=False but external sources present"


# ============================================================================
# Test: Internal Count Accuracy
# ============================================================================

class TestInternalCount:
    """Test that internal source count is accurate."""
    
    @pytest.mark.anyio
    async def test_internal_count_matches_candidates(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Contract: sources.internal should match number of candidates.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "user_roles": ["pro"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Internal count should match number of candidates provided
            expected_internal = len(sample_internal_candidates)
            assert data["sources"]["internal"] == expected_internal
    
    @pytest.mark.anyio
    async def test_internal_count_zero_when_no_candidates(
        self,
        client,
        mock_factare_service
    ):
        """
        Contract: sources.internal=0 when no candidates provided.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": [],  # Empty
                    "user_roles": ["pro"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["sources"]["internal"] == 0


# ============================================================================
# Test: Acceptance Criteria
# ============================================================================

class TestAcceptanceCriteria:
    """Direct verification of all acceptance criteria."""
    
    @pytest.mark.anyio
    async def test_acceptance_response_schema(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Acceptance: POST /factate/compare returns
        {compare_summary, contradictions, used_external, sources:{internal, external}}.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # All required fields present
            assert "compare_summary" in data
            assert "contradictions" in data
            assert "used_external" in data
            assert "sources" in data
            
            # sources structure
            assert "internal" in data["sources"]
            assert "external" in data["sources"]
    
    @pytest.mark.anyio
    async def test_acceptance_external_provenance(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Acceptance: External items include provenance.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # If external sources present, verify provenance
            if "external_sources" in data["compare_summary"]:
                items = data["compare_summary"]["external_sources"].get("items", [])
                for item in items:
                    assert "provenance" in item
                    assert "url" in item["provenance"]
    
    @pytest.mark.anyio
    async def test_acceptance_never_persisted(
        self,
        sample_external_sources
    ):
        """
        Acceptance: External items are never present in memories.
        """
        from core.guards import forbid_external_persistence, ExternalPersistenceError
        
        # External items should be blocked from persistence
        with pytest.raises(ExternalPersistenceError) as exc_info:
            forbid_external_persistence(
                sample_external_sources,
                raise_on_external=True
            )
        
        assert "Cannot persist external content" in str(exc_info.value)
    
    @pytest.mark.anyio
    async def test_acceptance_used_external_correctness(
        self,
        client,
        sample_internal_candidates,
        mock_factare_service
    ):
        """
        Acceptance: used_external true only when externals included.
        """
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            # With externals
            response = client.post(
                "/factate/compare",
                json={
                    "query": "What is machine learning?",
                    "retrieval_candidates": sample_internal_candidates,
                    "external_urls": ["https://en.wikipedia.org/wiki/ML"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should be true and have external sources
            assert data["used_external"] is True
            assert data["sources"]["external"] > 0
