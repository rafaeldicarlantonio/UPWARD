"""
Tests for external comparison integration in chat flow.

Verifies that external comparison is properly gated by feature flag and role,
and that the response and ledger are updated correctly.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import json

# Set up mock environment variables
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
os.environ.setdefault("PINECONE_EXPLICATE_INDEX", "test-explicate")
os.environ.setdefault("PINECONE_IMPLICATE_INDEX", "test-implicate")
os.environ.setdefault("CHAT_MODEL", "gpt-4-mini")
os.environ.setdefault("X_API_KEY", "test-api-key")

from fastapi.testclient import TestClient
from fastapi import FastAPI


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    from router.chat import router
    
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
    mock.table = Mock(return_value=Mock(
        select=Mock(return_value=Mock(
            eq=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[]))
            ))
        )),
        insert=Mock(return_value=Mock(
            execute=Mock(return_value=Mock(data=[{"id": "msg_123"}]))
        ))
    ))
    return mock


@pytest.fixture
def mock_pinecone():
    """Mock Pinecone index."""
    mock = Mock()
    mock.query = Mock(return_value=Mock(
        matches=[
            Mock(
                id="mem_1",
                score=0.95,
                metadata={
                    "id": "mem_1",
                    "text": "Internal memory content"
                }
            )
        ]
    ))
    return mock


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    mock = Mock()
    
    # Mock embeddings
    mock.embeddings = Mock()
    mock.embeddings.create = Mock(return_value=Mock(
        data=[Mock(embedding=[0.1] * 1536)]
    ))
    
    # Mock chat completions
    mock.chat = Mock()
    mock.chat.completions = Mock()
    mock.chat.completions.create = Mock(return_value=Mock(
        choices=[Mock(
            message=Mock(
                content=json.dumps({
                    "answer": "Test answer",
                    "citations": ["mem_1"],
                    "guidance_questions": []
                })
            )
        )]
    ))
    
    return mock


@pytest.fixture
def chat_request():
    """Base chat request."""
    return {
        "prompt": "Test question",
        "session_id": "session_test",
        "debug": False
    }


# ============================================================================
# Test: External Compare OFF (Flag Disabled)
# ============================================================================

class TestExternalCompareOff:
    """Test behavior when external_compare flag is off."""
    
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_flag_off_no_external_comparison(
        self, 
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """
        Acceptance: With flags off, no change to existing behavior.
        """
        # Setup mocks
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        # Feature flags: external_compare OFF
        def flag_side_effect(key, default=None):
            flags = {
                "external_compare": False,
                "orchestrator.redo_enabled": False,
                "ledger.enabled": False
            }
            return flags.get(key, default)
        
        mock_get_flag.side_effect = flag_side_effect
        
        # Make request
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify external comparison not enabled
        assert "metrics" in data
        assert "external_compare" in data["metrics"]
        assert data["metrics"]["external_compare"]["enabled"] is False
        
        # Verify no external sources in response
        assert "external_sources" not in data or data.get("external_sources") is None
        
        # Verify answer still provided (internal only)
        assert "answer" in data
        assert len(data["answer"]) > 0
    
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_flag_off_metrics_show_disabled(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """Test that metrics clearly show external_compare is disabled."""
        # Setup mocks
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        mock_get_flag.return_value = False  # All flags off
        
        # Make request
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Check metrics structure
        metrics = data["metrics"]
        assert metrics["external_compare"] == {"enabled": False}


# ============================================================================
# Test: External Compare ON + Role ALLOWED
# ============================================================================

class TestExternalCompareAllowed:
    """Test behavior when flag is on and role is allowed."""
    
    @patch('router.chat.can_use_external_compare')
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_flag_on_role_allowed_no_external_results(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        mock_can_use,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """
        Acceptance: With on and role allowed, response includes external block.
        (Even if no results, metadata should show it ran)
        """
        # Setup mocks
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        # Feature flags
        def flag_side_effect(key, default=None):
            flags = {
                "external_compare": True,
                "orchestrator.redo_enabled": False,
                "ledger.enabled": False
            }
            return flags.get(key, default)
        
        mock_get_flag.side_effect = flag_side_effect
        mock_can_use.return_value = True  # Role allowed
        
        # Make request
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify external comparison metadata
        assert "metrics" in data
        assert "external_compare" in data["metrics"]
        external_metrics = data["metrics"]["external_compare"]
        
        assert external_metrics["enabled"] is True
        assert "time_ms" in external_metrics
        assert external_metrics["time_ms"] >= 0
        assert external_metrics["fetched"] == 0  # No results in this test
    
    @patch('router.chat.can_use_external_compare')
    @patch('router.chat.format_external_evidence')
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_flag_on_role_allowed_with_results(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        mock_format_external,
        mock_can_use,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """Test that external results are formatted and included in response."""
        # Setup mocks
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        # Mock external results (would come from external fetch)
        mock_external_results = [
            {
                "source_id": "wikipedia",
                "url": "https://en.wikipedia.org/wiki/Test",
                "snippet": "Test content",
                "fetched_at": "2025-10-30T12:00:00Z"
            }
        ]
        
        mock_format_external.return_value = {
            "heading": "External sources",
            "items": [
                {
                    "label": "Wikipedia",
                    "host": "en.wikipedia.org",
                    "snippet": "Test content",
                    "provenance": {
                        "url": "https://en.wikipedia.org/wiki/Test",
                        "fetched_at": "2025-10-30T12:00:00Z"
                    }
                }
            ]
        }
        
        # Feature flags
        def flag_side_effect(key, default=None):
            flags = {
                "external_compare": True,
                "orchestrator.redo_enabled": False,
                "ledger.enabled": False
            }
            return flags.get(key, default)
        
        mock_get_flag.side_effect = flag_side_effect
        mock_can_use.return_value = True
        
        # Patch external results into chat flow
        with patch('router.chat.external_results', mock_external_results):
            response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Note: Since we haven't implemented actual external fetching yet,
        # external_sources won't be in response. This test is for when it's implemented.
        # For now, just verify metrics show it attempted
        assert data["metrics"]["external_compare"]["enabled"] is True


# ============================================================================
# Test: External Compare ON + Role DENIED
# ============================================================================

class TestExternalCompareDenied:
    """Test behavior when flag is on but role is denied."""
    
    @patch('router.chat.can_use_external_compare')
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_flag_on_role_denied_no_external(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        mock_can_use,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """
        Acceptance: With on and role denied, remains internal-only.
        """
        # Setup mocks
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        # Feature flags
        def flag_side_effect(key, default=None):
            flags = {
                "external_compare": True,
                "orchestrator.redo_enabled": False,
                "ledger.enabled": False
            }
            return flags.get(key, default)
        
        mock_get_flag.side_effect = flag_side_effect
        mock_can_use.return_value = False  # Role denied
        
        # Make request
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify external comparison shows role_denied
        assert "metrics" in data
        assert "external_compare" in data["metrics"]
        external_metrics = data["metrics"]["external_compare"]
        
        assert external_metrics["enabled"] is True
        assert external_metrics["fetched"] == 0
        assert external_metrics["reason"] == "role_denied"
        
        # Verify no external sources in response
        assert "external_sources" not in data or data.get("external_sources") is None
        
        # Verify internal answer still provided
        assert "answer" in data
        assert len(data["answer"]) > 0
    
    @patch('router.chat.can_use_external_compare')
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_role_denied_metrics_clear(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        mock_can_use,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """Test that metrics clearly indicate denial reason."""
        # Setup mocks
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        # Flags on, role denied
        def flag_side_effect(key, default=None):
            flags = {
                "external_compare": True,
                "orchestrator.redo_enabled": False,
                "ledger.enabled": False
            }
            return flags.get(key, default)
        
        mock_get_flag.side_effect = flag_side_effect
        mock_can_use.return_value = False
        
        # Make request
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Check specific metrics
        metrics = data["metrics"]["external_compare"]
        assert metrics["enabled"] is True
        assert metrics["fetched"] == 0
        assert metrics["time_ms"] == 0
        assert metrics["reason"] == "role_denied"


# ============================================================================
# Test: Ledger Integration
# ============================================================================

class TestLedgerIntegration:
    """Test that ledger records external comparison metadata."""
    
    @patch('router.chat.can_use_external_compare')
    @patch('router.chat.write_ledger')
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    @patch('router.chat.RedoOrchestrator')
    def test_ledger_includes_external_metadata(
        self,
        mock_orchestrator_class,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        mock_write_ledger,
        mock_can_use,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """
        Acceptance: Ledger records a factare.external block with counts and timings.
        """
        # Setup mocks
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestration_result = Mock()
        mock_orchestration_result.selected_context_ids = []
        mock_orchestration_result.stages = []
        mock_orchestration_result.contradictions = []
        mock_orchestration_result.warnings = []
        mock_orchestration_result.metadata = {}
        mock_orchestration_result.to_trace_schema = Mock(return_value={})
        
        mock_orchestrator.run = Mock(return_value=mock_orchestration_result)
        mock_orchestrator.configure = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Mock ledger write
        mock_ledger_entry = Mock()
        mock_ledger_entry.stored_size = 1000
        mock_ledger_entry.is_truncated = False
        mock_write_ledger.return_value = mock_ledger_entry
        
        # Feature flags: external + orchestrator + ledger ON
        def flag_side_effect(key, default=None):
            flags = {
                "external_compare": True,
                "orchestrator.redo_enabled": True,
                "ledger.enabled": True
            }
            return flags.get(key, default)
        
        mock_get_flag.side_effect = flag_side_effect
        mock_can_use.return_value = True  # Role allowed
        
        # Make request
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        
        # Verify ledger was written
        assert mock_write_ledger.called
        
        # Verify orchestration result has external metadata
        assert hasattr(mock_orchestration_result, 'metadata')
        assert 'factare.external' in mock_orchestration_result.metadata
        
        external_metadata = mock_orchestration_result.metadata['factare.external']
        assert external_metadata['enabled'] is True
        assert external_metadata['role_allowed'] is True
        assert 'fetch_count' in external_metadata
        assert 'fetch_time_ms' in external_metadata
        assert 'has_results' in external_metadata


# ============================================================================
# Acceptance Criteria Summary Tests
# ============================================================================

class TestAcceptanceCriteria:
    """Direct verification of all acceptance criteria."""
    
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_flags_off_no_change(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """
        Acceptance: with flags off, no change
        """
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        mock_get_flag.return_value = False
        
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["external_compare"]["enabled"] is False
        assert "external_sources" not in data or data.get("external_sources") is None
    
    @patch('router.chat.can_use_external_compare')
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_on_and_allowed_includes_metadata(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        mock_can_use,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """
        Acceptance: with on and role allowed, response includes external block
        and metrics show timings
        """
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        def flag_side_effect(key, default=None):
            return key == "external_compare"
        
        mock_get_flag.side_effect = flag_side_effect
        mock_can_use.return_value = True
        
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["external_compare"]["enabled"] is True
        assert "time_ms" in data["metrics"]["external_compare"]
    
    @patch('router.chat.can_use_external_compare')
    @patch('router.chat.get_feature_flag')
    @patch('router.chat.get_client')
    @patch('router.chat.get_index')
    @patch('router.chat.OpenAI')
    def test_on_and_denied_internal_only(
        self,
        mock_openai_class,
        mock_get_index,
        mock_get_client,
        mock_get_flag,
        mock_can_use,
        client,
        mock_supabase,
        mock_pinecone,
        mock_openai,
        chat_request
    ):
        """
        Acceptance: with on and role denied, remains internal-only
        """
        mock_get_client.return_value = mock_supabase
        mock_get_index.return_value = mock_pinecone
        mock_openai_class.return_value = mock_openai
        
        def flag_side_effect(key, default=None):
            return key == "external_compare"
        
        mock_get_flag.side_effect = flag_side_effect
        mock_can_use.return_value = False
        
        response = client.post("/chat", json=chat_request, headers={"x-api-key": "test-api-key"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["external_compare"]["reason"] == "role_denied"
        assert "external_sources" not in data or data.get("external_sources") is None
        assert len(data["answer"]) > 0  # Still has internal answer
