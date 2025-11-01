"""
Tests for API endpoint guards.

Tests the @require decorator and variants for capability-based route protection.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from core.rbac import (
    CAP_READ_PUBLIC,
    CAP_WRITE_GRAPH,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_VIEW_DEBUG,
    CAP_WRITE_CONTRADICTIONS,
    configure_resolver,
    reset_resolver,
)
from api.middleware import RoleResolutionMiddleware
from api.guards import require, require_any, require_all


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_global_resolver():
    """Reset global resolver before each test."""
    reset_resolver()
    yield
    reset_resolver()


@pytest.fixture
def app():
    """Create test FastAPI app with middleware and guarded routes."""
    app = FastAPI()
    
    # Configure resolver
    configure_resolver(
        api_key_to_user_map={
            "general-key": {
                "user_id": "user-general",
                "roles": ["general"],
            },
            "pro-key": {
                "user_id": "user-pro",
                "roles": ["pro"],
            },
            "analytics-key": {
                "user_id": "user-analytics",
                "roles": ["analytics"],
            },
            "ops-key": {
                "user_id": "user-ops",
                "roles": ["ops"],
            },
            "multi-role-key": {
                "user_id": "user-multi",
                "roles": ["pro", "scholars"],
            },
        },
        default_anonymous_roles=['general'],
    )
    
    # Add middleware
    app.add_middleware(RoleResolutionMiddleware)
    
    # Public route (no guard)
    @app.get("/public")
    def public_route(request: Request):
        from api.middleware import get_current_user
        ctx = get_current_user(request)
        return {
            "message": "public",
            "user_id": ctx.user_id,
            "roles": ctx.roles,
        }
    
    # Guarded routes
    @app.post("/graph/entities")
    @require(CAP_WRITE_GRAPH)
    def create_entity(request: Request):
        from api.middleware import get_current_user
        ctx = get_current_user(request)
        return {
            "message": "entity created",
            "user_id": ctx.user_id,
        }
    
    @app.post("/hypotheses")
    @require(CAP_PROPOSE_HYPOTHESIS)
    def propose_hypothesis(request: Request):
        from api.middleware import get_current_user
        ctx = get_current_user(request)
        return {
            "message": "hypothesis proposed",
            "user_id": ctx.user_id,
        }
    
    @app.get("/debug/metrics")
    @require(CAP_VIEW_DEBUG)
    def debug_metrics(request: Request):
        return {"metrics": "data"}
    
    # Route with require_any
    @app.post("/content")
    @require_any(CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS)
    def create_content(request: Request):
        return {"message": "content created"}
    
    # Route with require_all
    @app.post("/admin/action")
    @require_all(CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS)
    def admin_action(request: Request):
        return {"message": "admin action completed"}
    
    # Async route
    @app.get("/async-protected")
    @require(CAP_WRITE_GRAPH)
    async def async_protected_route(request: Request):
        return {"message": "async protected"}
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# ============================================================================
# Test Basic Guard Functionality
# ============================================================================

class TestBasicGuard:
    """Test basic @require decorator functionality."""
    
    def test_public_route_no_guard(self, client):
        """Public routes without guards should work for anyone."""
        # Anonymous
        response = client.get("/public")
        assert response.status_code == 200
        assert response.json()["roles"] == ["general"]
        
        # Authenticated
        response = client.get("/public", headers={"X-API-KEY": "pro-key"})
        assert response.status_code == 200
        assert response.json()["roles"] == ["pro"]
    
    def test_guarded_route_with_sufficient_capability(self, client):
        """Users with required capability should access guarded routes."""
        # Analytics role has WRITE_GRAPH capability
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "analytics-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "entity created"
        assert data["user_id"] == "user-analytics"
    
    def test_guarded_route_without_capability_returns_403(self, client):
        """Users without required capability should get 403."""
        # General role does not have WRITE_GRAPH capability
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "general-key"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "forbidden"
        assert data["detail"]["capability"] == CAP_WRITE_GRAPH
    
    def test_anonymous_user_gets_403_on_guarded_route(self, client):
        """Anonymous users should get 403 on guarded routes."""
        # No API key - anonymous with 'general' role
        response = client.post("/graph/entities")
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "forbidden"
        assert data["detail"]["capability"] == CAP_WRITE_GRAPH


# ============================================================================
# Test Different Capabilities
# ============================================================================

class TestDifferentCapabilities:
    """Test guards with different capabilities."""
    
    def test_write_graph_capability(self, client):
        """Test WRITE_GRAPH capability check."""
        # Analytics has WRITE_GRAPH
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "analytics-key"}
        )
        assert response.status_code == 200
        
        # Pro does not have WRITE_GRAPH
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "pro-key"}
        )
        assert response.status_code == 403
    
    def test_propose_hypothesis_capability(self, client):
        """Test PROPOSE_HYPOTHESIS capability check."""
        # Pro has PROPOSE_HYPOTHESIS
        response = client.post(
            "/hypotheses",
            headers={"X-API-KEY": "pro-key"}
        )
        assert response.status_code == 200
        
        # General does not have PROPOSE_HYPOTHESIS
        response = client.post(
            "/hypotheses",
            headers={"X-API-KEY": "general-key"}
        )
        assert response.status_code == 403
    
    def test_view_debug_capability(self, client):
        """Test VIEW_DEBUG capability check."""
        # Ops has VIEW_DEBUG
        response = client.get(
            "/debug/metrics",
            headers={"X-API-KEY": "ops-key"}
        )
        assert response.status_code == 200
        
        # Pro does not have VIEW_DEBUG
        response = client.get(
            "/debug/metrics",
            headers={"X-API-KEY": "pro-key"}
        )
        assert response.status_code == 403


# ============================================================================
# Test Multiple Roles
# ============================================================================

class TestMultipleRoles:
    """Test guards with users having multiple roles."""
    
    def test_user_with_multiple_roles(self, client):
        """User with multiple roles should pass if any role has capability."""
        # User has pro + scholars roles
        response = client.post(
            "/hypotheses",
            headers={"X-API-KEY": "multi-role-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user-multi"
    
    def test_multi_role_user_still_blocked_without_capability(self, client):
        """User with multiple roles still blocked if none have capability."""
        # User has pro + scholars, but neither has WRITE_GRAPH
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "multi-role-key"}
        )
        
        assert response.status_code == 403


# ============================================================================
# Test Async Routes
# ============================================================================

class TestAsyncRoutes:
    """Test guards on async route handlers."""
    
    def test_async_route_with_capability(self, client):
        """Async routes with guard should work for authorized users."""
        response = client.get(
            "/async-protected",
            headers={"X-API-KEY": "analytics-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "async protected"
    
    def test_async_route_without_capability(self, client):
        """Async routes should return 403 for unauthorized users."""
        response = client.get(
            "/async-protected",
            headers={"X-API-KEY": "pro-key"}
        )
        
        assert response.status_code == 403


# ============================================================================
# Test require_any Decorator
# ============================================================================

class TestRequireAny:
    """Test @require_any decorator."""
    
    def test_require_any_with_first_capability(self, client):
        """User with first capability should pass require_any."""
        # Analytics has WRITE_GRAPH (first capability)
        response = client.post(
            "/content",
            headers={"X-API-KEY": "analytics-key"}
        )
        
        assert response.status_code == 200
    
    def test_require_any_with_second_capability(self, client):
        """User with second capability should pass require_any."""
        # Analytics also has WRITE_CONTRADICTIONS (second capability)
        response = client.post(
            "/content",
            headers={"X-API-KEY": "analytics-key"}
        )
        
        assert response.status_code == 200
    
    def test_require_any_without_any_capability(self, client):
        """User without any required capability should get 403."""
        # Pro has neither WRITE_GRAPH nor WRITE_CONTRADICTIONS
        response = client.post(
            "/content",
            headers={"X-API-KEY": "pro-key"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "forbidden"
        assert CAP_WRITE_GRAPH in data["detail"]["capabilities"]
        assert CAP_WRITE_CONTRADICTIONS in data["detail"]["capabilities"]


# ============================================================================
# Test require_all Decorator
# ============================================================================

class TestRequireAll:
    """Test @require_all decorator."""
    
    def test_require_all_with_all_capabilities(self, client):
        """User with all capabilities should pass require_all."""
        # Analytics has both WRITE_GRAPH and WRITE_CONTRADICTIONS
        response = client.post(
            "/admin/action",
            headers={"X-API-KEY": "analytics-key"}
        )
        
        assert response.status_code == 200
    
    def test_require_all_missing_one_capability(self, client):
        """User missing one capability should get 403."""
        # Pro has PROPOSE_HYPOTHESIS but not WRITE_GRAPH or WRITE_CONTRADICTIONS
        response = client.post(
            "/admin/action",
            headers={"X-API-KEY": "pro-key"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "forbidden"
        assert "missing" in data["detail"]


# ============================================================================
# Test Error Cases
# ============================================================================

class TestErrorCases:
    """Test error handling in guards."""
    
    def test_guard_without_middleware(self):
        """Guard should fail gracefully if middleware not configured."""
        app_no_middleware = FastAPI()
        
        @app_no_middleware.get("/protected")
        @require(CAP_WRITE_GRAPH)
        def protected_route(request: Request):
            return {"message": "protected"}
        
        client = TestClient(app_no_middleware)
        
        # Should get 500 because middleware not configured
        response = client.get("/protected")
        assert response.status_code == 500


# ============================================================================
# Test Response Format
# ============================================================================

class TestResponseFormat:
    """Test the format of 403 responses."""
    
    def test_403_response_structure(self, client):
        """403 response should have correct structure."""
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "general-key"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        # Check structure
        assert "detail" in data
        assert "error" in data["detail"]
        assert "capability" in data["detail"]
        assert "message" in data["detail"]
        
        # Check values
        assert data["detail"]["error"] == "forbidden"
        assert data["detail"]["capability"] == CAP_WRITE_GRAPH
        assert "required" in data["detail"]["message"].lower()
    
    def test_403_response_includes_capability_name(self, client):
        """403 response should include the required capability."""
        response = client.post(
            "/hypotheses",
            headers={"X-API-KEY": "general-key"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["capability"] == CAP_PROPOSE_HYPOTHESIS


# ============================================================================
# Test Different HTTP Methods
# ============================================================================

class TestHTTPMethods:
    """Test guards work with different HTTP methods."""
    
    def test_post_with_guard(self, client):
        """POST routes with guards should work."""
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "analytics-key"}
        )
        assert response.status_code == 200
    
    def test_get_with_guard(self, client):
        """GET routes with guards should work."""
        response = client.get(
            "/debug/metrics",
            headers={"X-API-KEY": "ops-key"}
        )
        assert response.status_code == 200


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for guards with full system."""
    
    def test_complete_workflow(self, client):
        """Test complete workflow with multiple requests."""
        # Step 1: Anonymous user tries protected route - denied
        response = client.post("/graph/entities")
        assert response.status_code == 403
        
        # Step 2: User with insufficient capability tries - denied
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "pro-key"}
        )
        assert response.status_code == 403
        
        # Step 3: User with correct capability succeeds
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "analytics-key"}
        )
        assert response.status_code == 200
        
        # Step 4: Same user tries different protected route
        response = client.post(
            "/hypotheses",
            headers={"X-API-KEY": "analytics-key"}
        )
        assert response.status_code == 200
    
    def test_different_users_different_capabilities(self, client):
        """Test that different users have access to different routes."""
        # Pro user can propose hypotheses
        response = client.post(
            "/hypotheses",
            headers={"X-API-KEY": "pro-key"}
        )
        assert response.status_code == 200
        
        # But cannot write to graph
        response = client.post(
            "/graph/entities",
            headers={"X-API-KEY": "pro-key"}
        )
        assert response.status_code == 403
        
        # Ops user can view debug
        response = client.get(
            "/debug/metrics",
            headers={"X-API-KEY": "ops-key"}
        )
        assert response.status_code == 200
        
        # But cannot propose hypotheses
        response = client.post(
            "/hypotheses",
            headers={"X-API-KEY": "ops-key"}
        )
        assert response.status_code == 403
    
    def test_public_routes_always_accessible(self, client):
        """Public routes should be accessible by all users."""
        # Anonymous
        response = client.get("/public")
        assert response.status_code == 200
        
        # General
        response = client.get("/public", headers={"X-API-KEY": "general-key"})
        assert response.status_code == 200
        
        # Pro
        response = client.get("/public", headers={"X-API-KEY": "pro-key"})
        assert response.status_code == 200
        
        # Analytics
        response = client.get("/public", headers={"X-API-KEY": "analytics-key"})
        assert response.status_code == 200
        
        # Ops
        response = client.get("/public", headers={"X-API-KEY": "ops-key"})
        assert response.status_code == 200


# ============================================================================
# Summary Test
# ============================================================================

class TestCompleteCoverage:
    """Comprehensive test to verify all guard scenarios."""
    
    def test_all_capability_combinations(self, client):
        """Test that guards correctly enforce all capability combinations."""
        test_cases = [
            # (route, method, api_key, expected_status)
            ("/public", "get", None, 200),  # Public route
            ("/public", "get", "general-key", 200),  # Public with auth
            ("/graph/entities", "post", None, 403),  # Anonymous blocked
            ("/graph/entities", "post", "general-key", 403),  # General blocked
            ("/graph/entities", "post", "pro-key", 403),  # Pro blocked
            ("/graph/entities", "post", "analytics-key", 200),  # Analytics allowed
            ("/hypotheses", "post", "general-key", 403),  # General blocked
            ("/hypotheses", "post", "pro-key", 200),  # Pro allowed
            ("/hypotheses", "post", "analytics-key", 200),  # Analytics allowed
            ("/debug/metrics", "get", "pro-key", 403),  # Pro blocked
            ("/debug/metrics", "get", "ops-key", 200),  # Ops allowed
        ]
        
        for route, method, api_key, expected_status in test_cases:
            headers = {"X-API-KEY": api_key} if api_key else {}
            
            if method == "get":
                response = client.get(route, headers=headers)
            elif method == "post":
                response = client.post(route, headers=headers)
            
            assert response.status_code == expected_status, (
                f"Failed: {method.upper()} {route} with api_key={api_key} "
                f"expected {expected_status}, got {response.status_code}"
            )
