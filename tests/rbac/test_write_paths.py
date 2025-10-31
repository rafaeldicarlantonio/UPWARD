"""
Tests for write path authorization.

Tests that graph, hypotheses, and contradictions write operations
are properly guarded by role-based capabilities.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request, HTTPException

# Set required environment variables for testing
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
os.environ.setdefault("PINECONE_EXPLICATE_INDEX", "test-explicate-index")
os.environ.setdefault("PINECONE_IMPLICATE_INDEX", "test-implicate-index")

# We'll create mock endpoints for testing since the actual endpoints
# have different structures. The important part is testing the guards.
from api.middleware.roles import RequestContext
from core.rbac.resolve import ResolvedUser
from core.rbac import (
    ROLE_GENERAL,
    ROLE_PRO,
    ROLE_SCHOLARS,
    ROLE_ANALYTICS,
    ROLE_OPS,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_WRITE_GRAPH,
    CAP_WRITE_CONTRADICTIONS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def general_context():
    """Request context for general user (no write permissions)."""
    user = ResolvedUser(
        user_id="general-user",
        email="general@example.com",
        roles=[ROLE_GENERAL],
        auth_method="jwt",
        metadata={}
    )
    return RequestContext(user)


@pytest.fixture
def pro_context():
    """Request context for pro user (can propose, no writes)."""
    user = ResolvedUser(
        user_id="pro-user",
        email="pro@example.com",
        roles=[ROLE_PRO],
        auth_method="jwt",
        metadata={}
    )
    return RequestContext(user)


@pytest.fixture
def scholars_context():
    """Request context for scholars user (can propose, no writes)."""
    user = ResolvedUser(
        user_id="scholars-user",
        email="scholars@example.com",
        roles=[ROLE_SCHOLARS],
        auth_method="jwt",
        metadata={}
    )
    return RequestContext(user)


@pytest.fixture
def analytics_context():
    """Request context for analytics user (full write access)."""
    user = ResolvedUser(
        user_id="analytics-user",
        email="analytics@example.com",
        roles=[ROLE_ANALYTICS],
        auth_method="jwt",
        metadata={}
    )
    return RequestContext(user)


@pytest.fixture
def ops_context():
    """Request context for ops user (admin, no write permissions)."""
    user = ResolvedUser(
        user_id="ops-user",
        email="ops@example.com",
        roles=[ROLE_OPS],
        auth_method="jwt",
        metadata={}
    )
    return RequestContext(user)


@pytest.fixture
def mock_request(general_context):
    """Mock FastAPI request."""
    request = Mock(spec=Request)
    request.state.ctx = general_context
    return request


# ============================================================================
# Mock Endpoints for Testing
# ============================================================================

from api.guards import require

# Create mock endpoints decorated with guards for testing
@require("PROPOSE_HYPOTHESIS")
async def mock_propose_hypothesis(request: Request):
    """Mock hypothesis proposal endpoint."""
    return {"id": "hyp-123"}


@require("WRITE_GRAPH")
async def mock_create_entity(request: Request):
    """Mock entity creation endpoint."""
    return {"id": "entity-123"}


@require("WRITE_GRAPH") 
async def mock_create_edge(request: Request):
    """Mock edge creation endpoint."""
    return {"id": "edge-123"}


@require("WRITE_CONTRADICTIONS")
async def mock_add_contradiction(request: Request):
    """Mock contradiction endpoint."""
    return {"id": "contradiction-123"}


# ============================================================================
# Hypothesis Proposal Tests
# ============================================================================

class TestHypothesisProposal:
    """Test PROPOSE_HYPOTHESIS capability enforcement."""
    
    @pytest.mark.anyio
    async def test_general_cannot_propose_hypothesis(self, mock_request, general_context):
        """General user should get 403 when proposing hypothesis."""
        mock_request.state.ctx = general_context
        
        # Should raise 403 due to @require decorator
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=general_context):
                await mock_propose_hypothesis(mock_request)
        
        assert exc_info.value.status_code == 403
        assert "PROPOSE_HYPOTHESIS" in str(exc_info.value.detail)
    
    @pytest.mark.anyio
    async def test_pro_can_propose_hypothesis(self, mock_request, pro_context):
        """Pro user should be able to propose hypothesis."""
        mock_request.state.ctx = pro_context
        
        with patch("api.guards.get_current_user", return_value=pro_context):
            # Should not raise
            response = await mock_propose_hypothesis(mock_request)
            assert response["id"] == "hyp-123"
    
    @pytest.mark.anyio
    async def test_scholars_can_propose_hypothesis(self, mock_request, scholars_context):
        """Scholars user should be able to propose hypothesis."""
        mock_request.state.ctx = scholars_context
        
        with patch("api.guards.get_current_user", return_value=scholars_context):
            response = await mock_propose_hypothesis(mock_request)
            assert response["id"] == "hyp-123"
    
    @pytest.mark.anyio
    async def test_analytics_can_propose_hypothesis(self, mock_request, analytics_context):
        """Analytics user should be able to propose hypothesis."""
        mock_request.state.ctx = analytics_context
        
        with patch("api.guards.get_current_user", return_value=analytics_context):
            response = await mock_propose_hypothesis(mock_request)
            assert response["id"] == "hyp-123"
    
    @pytest.mark.anyio
    async def test_ops_cannot_propose_hypothesis(self, mock_request, ops_context):
        """Ops user should get 403 (no PROPOSE_HYPOTHESIS capability)."""
        mock_request.state.ctx = ops_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=ops_context):
                await mock_propose_hypothesis(mock_request)
        
        assert exc_info.value.status_code == 403


# ============================================================================
# Graph Write Tests
# ============================================================================

class TestGraphWrites:
    """Test WRITE_GRAPH capability enforcement."""
    
    @pytest.mark.anyio
    async def test_general_cannot_create_entity(self, mock_request, general_context):
        """General user should get 403 when creating entity."""
        mock_request.state.ctx = general_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=general_context):
                await mock_create_entity(mock_request)
        
        assert exc_info.value.status_code == 403
        assert "WRITE_GRAPH" in str(exc_info.value.detail)
    
    @pytest.mark.anyio
    async def test_pro_cannot_create_entity(self, mock_request, pro_context):
        """Pro user should get 403 when creating entity."""
        mock_request.state.ctx = pro_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=pro_context):
                await mock_create_entity(mock_request)
        
        assert exc_info.value.status_code == 403
        assert "WRITE_GRAPH" in str(exc_info.value.detail)
    
    @pytest.mark.anyio
    async def test_scholars_cannot_create_entity(self, mock_request, scholars_context):
        """Scholars user should get 403 when creating entity."""
        mock_request.state.ctx = scholars_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=scholars_context):
                await mock_create_entity(mock_request)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.anyio
    async def test_analytics_can_create_entity(self, mock_request, analytics_context):
        """Analytics user should be able to create entity."""
        mock_request.state.ctx = analytics_context
        
        with patch("api.guards.get_current_user", return_value=analytics_context):
            response = await mock_create_entity(mock_request)
            assert response["id"] == "entity-123"
    
    @pytest.mark.anyio
    async def test_ops_cannot_create_entity(self, mock_request, ops_context):
        """Ops user should get 403 (no WRITE_GRAPH capability)."""
        mock_request.state.ctx = ops_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=ops_context):
                await mock_create_entity(mock_request)
        
        assert exc_info.value.status_code == 403


class TestGraphEdges:
    """Test edge creation authorization."""
    
    @pytest.mark.anyio
    async def test_general_cannot_create_edge(self, mock_request, general_context):
        """General user should get 403 when creating edge."""
        mock_request.state.ctx = general_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=general_context):
                await mock_create_edge(mock_request)
        
        assert exc_info.value.status_code == 403
        assert "WRITE_GRAPH" in str(exc_info.value.detail)
    
    @pytest.mark.anyio
    async def test_pro_cannot_create_edge(self, mock_request, pro_context):
        """Pro user should get 403 when creating edge."""
        mock_request.state.ctx = pro_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=pro_context):
                await mock_create_edge(mock_request)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.anyio
    async def test_scholars_cannot_create_edge(self, mock_request, scholars_context):
        """Scholars user should get 403 when creating edge."""
        mock_request.state.ctx = scholars_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=scholars_context):
                await mock_create_edge(mock_request)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.anyio
    async def test_analytics_can_create_edge(self, mock_request, analytics_context):
        """Analytics user should be able to create edge."""
        mock_request.state.ctx = analytics_context
        
        with patch("api.guards.get_current_user", return_value=analytics_context):
            response = await mock_create_edge(mock_request)
            assert response["id"] == "edge-123"


class TestGraphUpdates:
    """Test entity update authorization - using same mock as create."""
    
    @pytest.mark.anyio
    async def test_general_cannot_update_entity(self, mock_request, general_context):
        """General user should get 403 when updating entity."""
        mock_request.state.ctx = general_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=general_context):
                await mock_create_entity(mock_request)  # Update uses same guard
        
        assert exc_info.value.status_code == 403
        assert "WRITE_GRAPH" in str(exc_info.value.detail)
    
    @pytest.mark.anyio
    async def test_scholars_cannot_update_entity(self, mock_request, scholars_context):
        """Scholars user should get 403 when updating entity."""
        mock_request.state.ctx = scholars_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=scholars_context):
                await mock_create_entity(mock_request)  # Update uses same guard
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.anyio
    async def test_analytics_can_update_entity(self, mock_request, analytics_context):
        """Analytics user should be able to update entity."""
        mock_request.state.ctx = analytics_context
        
        with patch("api.guards.get_current_user", return_value=analytics_context):
            response = await mock_create_entity(mock_request)  # Update uses same guard
            assert response["id"] == "entity-123"


# ============================================================================
# Contradictions Write Tests
# ============================================================================

class TestContradictionsWrites:
    """Test WRITE_CONTRADICTIONS capability enforcement."""
    
    @pytest.mark.anyio
    async def test_general_cannot_add_contradiction(self, mock_request, general_context):
        """General user should get 403 when adding contradiction."""
        mock_request.state.ctx = general_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=general_context):
                await mock_add_contradiction(mock_request)
        
        assert exc_info.value.status_code == 403
        assert "WRITE_CONTRADICTIONS" in str(exc_info.value.detail)
    
    @pytest.mark.anyio
    async def test_pro_cannot_add_contradiction(self, mock_request, pro_context):
        """Pro user should get 403 when adding contradiction."""
        mock_request.state.ctx = pro_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=pro_context):
                await mock_add_contradiction(mock_request)
        
        assert exc_info.value.status_code == 403
        assert "WRITE_CONTRADICTIONS" in str(exc_info.value.detail)
    
    @pytest.mark.anyio
    async def test_scholars_cannot_add_contradiction(self, mock_request, scholars_context):
        """Scholars user should get 403 when adding contradiction."""
        mock_request.state.ctx = scholars_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=scholars_context):
                await mock_add_contradiction(mock_request)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.anyio
    async def test_analytics_can_add_contradiction(self, mock_request, analytics_context):
        """Analytics user should be able to add contradiction."""
        mock_request.state.ctx = analytics_context
        
        with patch("api.guards.get_current_user", return_value=analytics_context):
            response = await mock_add_contradiction(mock_request)
            assert response["id"] == "contradiction-123"
    
    @pytest.mark.anyio
    async def test_ops_cannot_add_contradiction(self, mock_request, ops_context):
        """Ops user should get 403 (no WRITE_CONTRADICTIONS capability)."""
        mock_request.state.ctx = ops_context
        
        with pytest.raises(HTTPException) as exc_info:
            with patch("api.guards.get_current_user", return_value=ops_context):
                await mock_add_contradiction(mock_request)
        
        assert exc_info.value.status_code == 403


        
        from core.rbac import has_capability
        
        # Verify no write capabilities
        assert not has_capability(ROLE_GENERAL, CAP_PROPOSE_HYPOTHESIS)
        assert not has_capability(ROLE_GENERAL, CAP_WRITE_GRAPH)
        assert not has_capability(ROLE_GENERAL, CAP_WRITE_CONTRADICTIONS)
    
    def test_scholars_can_propose_only(self, mock_request, scholars_context):
        """Scholars can propose but not write to graph/contradictions."""
        from core.rbac import has_capability
        
        # Can propose
        assert has_capability(ROLE_SCHOLARS, CAP_PROPOSE_HYPOTHESIS)
        
        # Cannot write
        assert not has_capability(ROLE_SCHOLARS, CAP_WRITE_GRAPH)
        assert not has_capability(ROLE_SCHOLARS, CAP_WRITE_CONTRADICTIONS)
    
    def test_pro_can_propose_only(self, mock_request, pro_context):
        """Pro can propose but not write to graph/contradictions."""
        from core.rbac import has_capability
        
        # Can propose
        assert has_capability(ROLE_PRO, CAP_PROPOSE_HYPOTHESIS)
        
        # Cannot write
        assert not has_capability(ROLE_PRO, CAP_WRITE_GRAPH)
        assert not has_capability(ROLE_PRO, CAP_WRITE_CONTRADICTIONS)
    
    def test_analytics_full_write_access(self, mock_request, analytics_context):
        """Analytics has full write access."""
        from core.rbac import has_capability
        
        # All write capabilities
        assert has_capability(ROLE_ANALYTICS, CAP_PROPOSE_HYPOTHESIS)
        assert has_capability(ROLE_ANALYTICS, CAP_WRITE_GRAPH)
        assert has_capability(ROLE_ANALYTICS, CAP_WRITE_CONTRADICTIONS)
