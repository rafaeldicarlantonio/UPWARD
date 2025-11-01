"""
Tests for RBAC metrics and audit logging.

Verifies that RBAC operations are properly instrumented with counters
and that denials generate audit log entries.
"""

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request, HTTPException

from core.metrics import (
    record_rbac_resolution,
    record_rbac_check,
    record_role_distribution,
    record_retrieval_filtered,
    audit_rbac_denial,
    get_rbac_metrics,
    reset_rbac_metrics,
    get_counter,
)
from core.rbac import (
    ROLE_GENERAL,
    ROLE_PRO,
    ROLE_SCHOLARS,
    ROLE_ANALYTICS,
    ROLE_OPS,
    CAP_WRITE_GRAPH,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_WRITE_CONTRADICTIONS,
)
from api.middleware.roles import RequestContext
from core.rbac.resolve import ResolvedUser


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before each test."""
    reset_rbac_metrics()
    yield
    reset_rbac_metrics()


@pytest.fixture
def mock_logger():
    """Mock audit logger."""
    with patch('core.metrics.audit_logger') as mock_log:
        yield mock_log


# ============================================================================
# Resolution Metrics Tests
# ============================================================================

class TestResolutionMetrics:
    """Test role resolution metrics."""
    
    def test_successful_resolution_increments_counter(self):
        """Test that successful resolution increments counter."""
        # Record successful resolution
        record_rbac_resolution(success=True, auth_method="jwt")
        
        # Verify counter incremented
        resolutions = get_counter("rbac.resolutions", labels={"success": "true"})
        assert resolutions == 1
    
    def test_failed_resolution_increments_counter(self):
        """Test that failed resolution increments counter."""
        record_rbac_resolution(success=False, auth_method="error")
        
        resolutions = get_counter("rbac.resolutions", labels={"success": "false"})
        assert resolutions == 1
    
    def test_multiple_resolutions(self):
        """Test multiple resolutions increment correctly."""
        record_rbac_resolution(success=True, auth_method="jwt")
        record_rbac_resolution(success=True, auth_method="api_key")
        record_rbac_resolution(success=False, auth_method="error")
        
        success_count = get_counter("rbac.resolutions", labels={"success": "true"})
        assert success_count == 2
        
        fail_count = get_counter("rbac.resolutions", labels={"success": "false"})
        assert fail_count == 1
    
    def test_resolution_by_auth_method(self):
        """Test resolution tracking by auth method."""
        record_rbac_resolution(success=True, auth_method="jwt")
        record_rbac_resolution(success=True, auth_method="jwt")
        record_rbac_resolution(success=True, auth_method="api_key")
        
        jwt_count = get_counter("rbac.resolutions.by_method", labels={"method": "jwt"})
        assert jwt_count == 2
        
        api_key_count = get_counter("rbac.resolutions.by_method", labels={"method": "api_key"})
        assert api_key_count == 1


# ============================================================================
# Authorization Check Metrics Tests
# ============================================================================

class TestAuthorizationMetrics:
    """Test authorization check metrics."""
    
    def test_allowed_check_increments_counter(self):
        """Test that allowed checks increment counter."""
        record_rbac_check(
            allowed=True,
            capability=CAP_WRITE_GRAPH,
            roles=[ROLE_ANALYTICS],
            route="/entities"
        )
        
        allowed_count = get_counter("rbac.allowed")
        assert allowed_count == 1
    
    def test_denied_check_increments_counter(self):
        """Test that denied checks increment counter."""
        record_rbac_check(
            allowed=False,
            capability=CAP_WRITE_GRAPH,
            roles=[ROLE_GENERAL],
            route="/entities"
        )
        
        denied_count = get_counter("rbac.denied")
        assert denied_count == 1
    
    def test_multiple_checks(self):
        """Test multiple authorization checks."""
        # Some allowed
        record_rbac_check(True, CAP_WRITE_GRAPH, [ROLE_ANALYTICS], "/entities")
        record_rbac_check(True, CAP_PROPOSE_HYPOTHESIS, [ROLE_PRO], "/hypotheses")
        
        # Some denied
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_GENERAL], "/entities")
        record_rbac_check(False, CAP_WRITE_CONTRADICTIONS, [ROLE_PRO], "/memories")
        
        assert get_counter("rbac.allowed") == 2
        assert get_counter("rbac.denied") == 2
    
    def test_checks_by_capability(self):
        """Test authorization tracking by capability."""
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_GENERAL], "/entities")
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_PRO], "/entities")
        record_rbac_check(True, CAP_WRITE_GRAPH, [ROLE_ANALYTICS], "/entities")
        
        denied_write_graph = get_counter(
            "rbac.denied.by_capability",
            labels={"capability": CAP_WRITE_GRAPH}
        )
        assert denied_write_graph == 2
        
        allowed_write_graph = get_counter(
            "rbac.allowed.by_capability",
            labels={"capability": CAP_WRITE_GRAPH}
        )
        assert allowed_write_graph == 1
    
    def test_denials_by_route(self):
        """Test denial tracking by route."""
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_GENERAL], "/entities")
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_GENERAL], "/entities")
        record_rbac_check(False, CAP_WRITE_CONTRADICTIONS, [ROLE_PRO], "/memories")
        
        entities_denials = get_counter("rbac.denied.by_route", labels={"route": "/entities"})
        assert entities_denials == 2
        
        memories_denials = get_counter("rbac.denied.by_route", labels={"route": "/memories"})
        assert memories_denials == 1


# ============================================================================
# Role Distribution Metrics Tests
# ============================================================================

class TestRoleDistribution:
    """Test role distribution tracking."""
    
    def test_single_role_distribution(self):
        """Test tracking single role."""
        record_role_distribution(ROLE_GENERAL)
        
        count = get_counter("rbac.role_distribution", labels={"role": ROLE_GENERAL})
        assert count == 1
    
    def test_multiple_roles_distribution(self):
        """Test tracking multiple roles."""
        record_role_distribution(ROLE_PRO)
        record_role_distribution(ROLE_PRO)
        record_role_distribution(ROLE_ANALYTICS)
        record_role_distribution(ROLE_GENERAL)
        record_role_distribution(ROLE_GENERAL)
        record_role_distribution(ROLE_GENERAL)
        
        assert get_counter("rbac.role_distribution", labels={"role": ROLE_PRO}) == 2
        assert get_counter("rbac.role_distribution", labels={"role": ROLE_ANALYTICS}) == 1
        assert get_counter("rbac.role_distribution", labels={"role": ROLE_GENERAL}) == 3
    
    def test_all_roles_tracked(self):
        """Test that all roles can be tracked."""
        roles = [ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS]
        
        for role in roles:
            record_role_distribution(role)
        
        for role in roles:
            count = get_counter("rbac.role_distribution", labels={"role": role})
            assert count == 1


# ============================================================================
# Retrieval Filtering Metrics Tests
# ============================================================================

class TestRetrievalFilteringMetrics:
    """Test retrieval filtering metrics."""
    
    def test_filtered_items_tracking(self):
        """Test tracking of filtered items."""
        record_retrieval_filtered(
            filtered_count=5,
            total_count=10,
            caller_roles=[ROLE_GENERAL]
        )
        
        filtered = get_counter("retrieval.filtered_items")
        assert filtered == 5
        
        total = get_counter("retrieval.total_items")
        assert total == 10
    
    def test_multiple_filtering_operations(self):
        """Test multiple filtering operations accumulate."""
        record_retrieval_filtered(5, 10, [ROLE_GENERAL])
        record_retrieval_filtered(3, 8, [ROLE_PRO])
        record_retrieval_filtered(0, 5, [ROLE_ANALYTICS])
        
        total_filtered = get_counter("retrieval.filtered_items")
        assert total_filtered == 8  # 5 + 3 + 0
        
        total_items = get_counter("retrieval.total_items")
        assert total_items == 23  # 10 + 8 + 5
    
    def test_filtering_by_role(self):
        """Test filtering tracking per role."""
        record_retrieval_filtered(5, 10, [ROLE_GENERAL])
        record_retrieval_filtered(2, 8, [ROLE_PRO])
        
        general_filtered = get_counter(
            "retrieval.filtered_by_role",
            labels={"role": ROLE_GENERAL}
        )
        assert general_filtered == 5
        
        pro_filtered = get_counter(
            "retrieval.filtered_by_role",
            labels={"role": ROLE_PRO}
        )
        assert pro_filtered == 2


# ============================================================================
# Audit Logging Tests
# ============================================================================

class TestAuditLogging:
    """Test audit log generation for denials."""
    
    def test_denial_audit_logs(self, mock_logger):
        """Test that denials generate audit log entries."""
        audit_rbac_denial(
            capability=CAP_WRITE_GRAPH,
            user_id="user-123",
            roles=[ROLE_GENERAL],
            route="/entities",
            method="POST"
        )
        
        # Verify logger was called
        assert mock_logger.warning.called
        
        # Check log message
        call_args = mock_logger.warning.call_args
        log_message = call_args[0][0]
        assert "RBAC_DENIAL" in log_message
        assert CAP_WRITE_GRAPH in log_message
        assert "user-123" in log_message
    
    def test_audit_includes_all_fields(self, mock_logger):
        """Test that audit entry includes all required fields."""
        audit_rbac_denial(
            capability=CAP_PROPOSE_HYPOTHESIS,
            user_id="user-456",
            roles=[ROLE_GENERAL],
            route="/hypotheses/propose",
            method="POST",
            metadata={"ip": "192.168.1.1"}
        )
        
        # Get the extra data passed to logger
        call_args = mock_logger.warning.call_args
        extra_data = call_args[1].get("extra", {}).get("audit", {})
        
        assert extra_data["event"] == "rbac_denial"
        assert extra_data["capability"] == CAP_PROPOSE_HYPOTHESIS
        assert extra_data["user_id"] == "user-456"
        assert extra_data["roles"] == [ROLE_GENERAL]
        assert extra_data["route"] == "/hypotheses/propose"
        assert extra_data["method"] == "POST"
        assert "timestamp" in extra_data
        assert extra_data["metadata"]["ip"] == "192.168.1.1"
    
    def test_audit_increments_counter(self):
        """Test that audit logging increments denial counter."""
        audit_rbac_denial(
            capability=CAP_WRITE_GRAPH,
            user_id="user-789",
            roles=[ROLE_PRO],
            route="/entities"
        )
        
        audit_count = get_counter("rbac.audit.denials")
        assert audit_count == 1
        
        capability_count = get_counter(
            "rbac.audit.denials.by_capability",
            labels={"capability": CAP_WRITE_GRAPH}
        )
        assert capability_count == 1
    
    def test_multiple_denials_tracked(self, mock_logger):
        """Test that multiple denials are tracked."""
        audit_rbac_denial(CAP_WRITE_GRAPH, "user-1", [ROLE_GENERAL], "/entities")
        audit_rbac_denial(CAP_WRITE_GRAPH, "user-2", [ROLE_PRO], "/entities")
        audit_rbac_denial(CAP_PROPOSE_HYPOTHESIS, "user-3", [ROLE_GENERAL], "/hypotheses")
        
        assert mock_logger.warning.call_count == 3
        assert get_counter("rbac.audit.denials") == 3
    
    def test_anonymous_user_audit(self, mock_logger):
        """Test audit logging for anonymous users."""
        audit_rbac_denial(
            capability=CAP_WRITE_GRAPH,
            user_id=None,  # Anonymous
            roles=[ROLE_GENERAL],
            route="/entities"
        )
        
        call_args = mock_logger.warning.call_args
        log_message = call_args[0][0]
        assert "anonymous" in log_message
        
        extra_data = call_args[1].get("extra", {}).get("audit", {})
        assert extra_data["user_id"] == "anonymous"


# ============================================================================
# Integration Tests
# ============================================================================

class TestMetricsIntegration:
    """Test metrics integration with RBAC components."""
    
    def test_complete_authorization_flow(self):
        """Test complete flow from resolution to authorization."""
        # Resolution
        record_rbac_resolution(success=True, auth_method="jwt")
        record_role_distribution(ROLE_PRO)
        
        # Authorization check - allowed
        record_rbac_check(True, CAP_PROPOSE_HYPOTHESIS, [ROLE_PRO], "/hypotheses")
        
        # Authorization check - denied
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_PRO], "/entities")
        
        # Verify metrics
        assert get_counter("rbac.resolutions", labels={"success": "true"}) == 1
        assert get_counter("rbac.role_distribution", labels={"role": ROLE_PRO}) == 1
        assert get_counter("rbac.allowed") == 1
        assert get_counter("rbac.denied") == 1
    
    def test_retrieval_with_filtering(self):
        """Test retrieval metrics with filtering."""
        # Simulate retrieval operation
        record_retrieval_filtered(
            filtered_count=3,
            total_count=10,
            caller_roles=[ROLE_GENERAL]
        )
        
        assert get_counter("retrieval.filtered_items") == 3
        assert get_counter("retrieval.total_items") == 10
        assert get_counter("retrieval.filtered_by_role", labels={"role": ROLE_GENERAL}) == 3
    
    def test_denial_with_audit(self, mock_logger):
        """Test that denial triggers both metrics and audit."""
        # Deny access
        record_rbac_check(False, CAP_WRITE_CONTRADICTIONS, [ROLE_SCHOLARS], "/memories")
        audit_rbac_denial(
            CAP_WRITE_CONTRADICTIONS,
            "scholar-user",
            [ROLE_SCHOLARS],
            "/memories/123/contradictions",
            "POST"
        )
        
        # Verify metrics
        assert get_counter("rbac.denied") == 1
        assert get_counter("rbac.audit.denials") == 1
        
        # Verify audit log
        assert mock_logger.warning.called


# ============================================================================
# Middleware Integration Tests
# ============================================================================

class TestMiddlewareMetrics:
    """Test that middleware properly records metrics."""
    
    @pytest.mark.anyio(backends=["asyncio"])
    @patch('api.middleware.roles.get_resolver')
    async def test_middleware_records_resolution(self, mock_get_resolver):
        """Test that middleware records resolution metrics."""
        # Setup mock resolver
        mock_resolver = Mock()
        mock_user = ResolvedUser(
            user_id="user-123",
            email="user@example.com",
            roles=[ROLE_PRO],
            auth_method="jwt",
            metadata={}
        )
        mock_resolver.resolve_from_request.return_value = mock_user
        mock_get_resolver.return_value = mock_resolver
        
        # Create middleware
        from api.middleware.roles import RoleResolutionMiddleware
        
        # Mock request and response
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer token"}
        mock_request.method = "POST"
        mock_request.url.path = "/test"
        mock_request.state = Mock()
        
        async def mock_call_next(request):
            return Mock()
        
        middleware = RoleResolutionMiddleware(app=Mock())
        
        # Process request
        await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify metrics recorded
        assert get_counter("rbac.resolutions", labels={"success": "true"}) >= 1
        assert get_counter("rbac.role_distribution", labels={"role": ROLE_PRO}) >= 1


# ============================================================================
# Guard Integration Tests
# ============================================================================

class TestGuardMetrics:
    """Test that guards properly record metrics."""
    
    @pytest.mark.anyio(backends=["asyncio"])
    async def test_guard_records_denial_metrics(self):
        """Test that @require decorator records denial metrics."""
        from api.guards import require
        
        # Create test endpoint
        @require(CAP_WRITE_GRAPH)
        async def test_endpoint(request: Request):
            return {"success": True}
        
        # Create mock request with general user
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/test"
        
        general_user = ResolvedUser(
            user_id="user-123",
            email="test@example.com",
            roles=[ROLE_GENERAL],
            auth_method="jwt",
            metadata={}
        )
        mock_request.state.ctx = RequestContext(general_user)
        
        # Get initial counts
        initial_denied = get_counter("rbac.denied")
        initial_audit = get_counter("rbac.audit.denials")
        
        # Attempt to call (should be denied)
        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint(mock_request)
        
        assert exc_info.value.status_code == 403
        
        # Verify metrics were incremented
        assert get_counter("rbac.denied") == initial_denied + 1
        assert get_counter("rbac.audit.denials") == initial_audit + 1
    
    @pytest.mark.anyio(backends=["asyncio"])
    async def test_guard_records_allowed_metrics(self):
        """Test that @require decorator records allowed metrics."""
        from api.guards import require
        
        @require(CAP_WRITE_GRAPH)
        async def test_endpoint(request: Request):
            return {"success": True}
        
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/test"
        
        analytics_user = ResolvedUser(
            user_id="user-456",
            email="analytics@example.com",
            roles=[ROLE_ANALYTICS],
            auth_method="jwt",
            metadata={}
        )
        mock_request.state.ctx = RequestContext(analytics_user)
        
        # Get initial count
        initial_allowed = get_counter("rbac.allowed")
        
        result = await test_endpoint(mock_request)
        
        assert result["success"] is True
        assert get_counter("rbac.allowed") == initial_allowed + 1


# ============================================================================
# Metrics Retrieval Tests
# ============================================================================

class TestMetricsRetrieval:
    """Test RBAC metrics retrieval."""
    
    def test_get_rbac_metrics(self):
        """Test getting all RBAC metrics."""
        # Generate some metrics
        record_rbac_resolution(True, "jwt")
        record_role_distribution(ROLE_PRO)
        record_rbac_check(True, CAP_PROPOSE_HYPOTHESIS, [ROLE_PRO], "/hypotheses")
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_PRO], "/entities")
        audit_rbac_denial(CAP_WRITE_GRAPH, "user-123", [ROLE_PRO], "/entities")
        
        # Get metrics
        metrics = get_rbac_metrics()
        
        # Verify structure
        assert "resolutions" in metrics or "authorization" in metrics
        # Metrics should be present (exact structure may vary)
    
    def test_metrics_reset(self):
        """Test that metrics can be reset."""
        # Generate metrics
        record_rbac_check(True, CAP_WRITE_GRAPH, [ROLE_ANALYTICS], "/entities")
        assert get_counter("rbac.allowed") >= 1
        
        # Reset
        reset_rbac_metrics()
        
        # Verify reset
        assert get_counter("rbac.allowed") == 0


# ============================================================================
# Summary Test
# ============================================================================

class TestRBACMetricsSummary:
    """Summary test verifying all acceptance criteria."""
    
    def test_all_required_counters_work(self):
        """Verify all required counters can be incremented."""
        # rbac.resolutions
        record_rbac_resolution(True, "jwt")
        assert get_counter("rbac.resolutions", labels={"success": "true"}) == 1
        
        # rbac.denied
        record_rbac_check(False, CAP_WRITE_GRAPH, [ROLE_GENERAL], "/test")
        assert get_counter("rbac.denied") == 1
        
        # rbac.allowed
        record_rbac_check(True, CAP_WRITE_GRAPH, [ROLE_ANALYTICS], "/test")
        assert get_counter("rbac.allowed") == 1
        
        # rbac.role_distribution{role}
        record_role_distribution(ROLE_PRO)
        assert get_counter("rbac.role_distribution", labels={"role": ROLE_PRO}) == 1
        
        # retrieval.filtered_items
        record_retrieval_filtered(3, 10, [ROLE_GENERAL])
        assert get_counter("retrieval.filtered_items") == 3
    
    def test_audit_entries_appear(self, mock_logger):
        """Verify audit entries appear when denials happen."""
        audit_rbac_denial(
            capability=CAP_WRITE_GRAPH,
            user_id="test-user",
            roles=[ROLE_GENERAL],
            route="/entities",
            method="POST"
        )
        
        # Verify audit logger was called
        assert mock_logger.warning.called
        
        # Verify audit entry structure
        call_args = mock_logger.warning.call_args
        extra_data = call_args[1].get("extra", {}).get("audit", {})
        
        assert extra_data["event"] == "rbac_denial"
        assert extra_data["capability"] == CAP_WRITE_GRAPH
        assert extra_data["user_id"] == "test-user"
        assert extra_data["roles"] == [ROLE_GENERAL]
        assert extra_data["route"] == "/entities"
        assert extra_data["method"] == "POST"
