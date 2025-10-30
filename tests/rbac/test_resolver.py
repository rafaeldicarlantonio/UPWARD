"""
Tests for role resolution and middleware.

Tests JWT authentication, API key authentication, and anonymous fallback.
"""

import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from core.rbac.resolve import (
    RoleResolver,
    ResolvedUser,
    configure_resolver,
    get_resolver,
    reset_resolver,
)
from api.middleware.roles import (
    RoleResolutionMiddleware,
    RequestContext,
    get_current_user,
    require_authenticated,
    get_user_id,
    get_user_roles,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def jwt_secret():
    """JWT secret for testing."""
    return "test-secret-key-12345"


@pytest.fixture
def api_key_map():
    """API key to user mapping for testing."""
    return {
        "test-api-key-123": {
            "user_id": "api-user-1",
            "email": "apiuser@example.com",
            "roles": ["analytics", "pro"],
        },
        "ops-key-456": {
            "user_id": "ops-user-1",
            "email": "ops@example.com",
            "roles": ["ops"],
        },
        "single-role-key": {
            "user_id": "user-2",
            "email": "user2@example.com",
            "roles": "pro",  # Test single role (not a list)
        },
    }


@pytest.fixture
def resolver(jwt_secret, api_key_map):
    """Create a configured role resolver for testing."""
    return RoleResolver(
        supabase_jwt_secret=jwt_secret,
        api_key_to_user_map=api_key_map,
        default_anonymous_roles=['general'],
    )


@pytest.fixture
def valid_jwt_token(jwt_secret):
    """Create a valid JWT token for testing."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "roles": ["pro", "scholars"],
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def expired_jwt_token(jwt_secret):
    """Create an expired JWT token for testing."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def jwt_with_app_metadata(jwt_secret):
    """Create JWT with roles in app_metadata."""
    payload = {
        "sub": "user-456",
        "email": "admin@example.com",
        "app_metadata": {
            "roles": ["analytics", "ops"],
        },
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def jwt_with_user_metadata(jwt_secret):
    """Create JWT with roles in user_metadata."""
    payload = {
        "sub": "user-789",
        "email": "user@example.com",
        "user_metadata": {
            "roles": ["scholars"],
        },
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def jwt_without_roles(jwt_secret):
    """Create JWT without any roles (should default to 'pro')."""
    payload = {
        "sub": "user-999",
        "email": "noroles@example.com",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def reset_global_resolver():
    """Reset global resolver before each test."""
    reset_resolver()
    yield
    reset_resolver()


# ============================================================================
# Test RoleResolver - JWT Authentication
# ============================================================================

class TestJWTAuthentication:
    """Test JWT token authentication."""
    
    def test_valid_jwt_with_bearer_prefix(self, resolver, valid_jwt_token):
        """Valid JWT with Bearer prefix should resolve user."""
        auth_header = f"Bearer {valid_jwt_token}"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user is not None
        assert user.user_id == "user-123"
        assert user.email == "test@example.com"
        assert "pro" in user.roles
        assert "scholars" in user.roles
        assert user.auth_method == "jwt"
        assert user.is_authenticated
        assert not user.is_anonymous
    
    def test_jwt_without_bearer_prefix(self, resolver, valid_jwt_token):
        """JWT without Bearer prefix should fail."""
        auth_header = valid_jwt_token  # Missing "Bearer "
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        # Should fall back to anonymous
        assert user.auth_method == "anonymous"
        assert user.roles == ["general"]
    
    def test_expired_jwt_token(self, resolver, expired_jwt_token):
        """Expired JWT should fall back to anonymous."""
        auth_header = f"Bearer {expired_jwt_token}"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user.auth_method == "anonymous"
        assert user.roles == ["general"]
    
    def test_invalid_jwt_token(self, resolver):
        """Invalid JWT should fall back to anonymous."""
        auth_header = "Bearer invalid-token-123"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user.auth_method == "anonymous"
        assert user.roles == ["general"]
    
    def test_jwt_with_wrong_secret(self, valid_jwt_token):
        """JWT with wrong secret should fail."""
        wrong_secret_resolver = RoleResolver(
            supabase_jwt_secret="wrong-secret",
            default_anonymous_roles=['general'],
        )
        
        auth_header = f"Bearer {valid_jwt_token}"
        user = wrong_secret_resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user.auth_method == "anonymous"
    
    def test_jwt_roles_in_app_metadata(self, resolver, jwt_with_app_metadata):
        """JWT with roles in app_metadata should extract them."""
        auth_header = f"Bearer {jwt_with_app_metadata}"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user.user_id == "user-456"
        assert user.email == "admin@example.com"
        assert "analytics" in user.roles
        assert "ops" in user.roles
        assert user.auth_method == "jwt"
    
    def test_jwt_roles_in_user_metadata(self, resolver, jwt_with_user_metadata):
        """JWT with roles in user_metadata should extract them."""
        auth_header = f"Bearer {jwt_with_user_metadata}"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user.user_id == "user-789"
        assert "scholars" in user.roles
        assert user.auth_method == "jwt"
    
    def test_jwt_without_roles_defaults_to_pro(self, resolver, jwt_without_roles):
        """JWT without roles should default to 'pro'."""
        auth_header = f"Bearer {jwt_without_roles}"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user.user_id == "user-999"
        assert user.roles == ["pro"]
        assert user.auth_method == "jwt"
    
    def test_jwt_missing_sub_claim(self, resolver, jwt_secret):
        """JWT without 'sub' claim should fail."""
        payload = {
            "email": "test@example.com",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        auth_header = f"Bearer {token}"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert user.auth_method == "anonymous"
    
    def test_jwt_metadata_preserved(self, resolver, valid_jwt_token):
        """JWT metadata should be preserved in resolved user."""
        auth_header = f"Bearer {valid_jwt_token}"
        
        user = resolver.resolve_from_request(authorization_header=auth_header)
        
        assert "jwt_payload" in user.metadata
        assert "token_issued_at" in user.metadata
        assert "token_expires_at" in user.metadata


# ============================================================================
# Test RoleResolver - API Key Authentication
# ============================================================================

class TestAPIKeyAuthentication:
    """Test API key authentication."""
    
    def test_valid_api_key(self, resolver):
        """Valid API key should resolve user."""
        user = resolver.resolve_from_request(api_key_header="test-api-key-123")
        
        assert user.user_id == "api-user-1"
        assert user.email == "apiuser@example.com"
        assert "analytics" in user.roles
        assert "pro" in user.roles
        assert user.auth_method == "api_key"
        assert user.is_authenticated
    
    def test_valid_api_key_ops_role(self, resolver):
        """API key with ops role should work."""
        user = resolver.resolve_from_request(api_key_header="ops-key-456")
        
        assert user.user_id == "ops-user-1"
        assert user.roles == ["ops"]
        assert user.auth_method == "api_key"
    
    def test_invalid_api_key(self, resolver):
        """Invalid API key should fall back to anonymous."""
        user = resolver.resolve_from_request(api_key_header="invalid-key")
        
        assert user.auth_method == "anonymous"
        assert user.roles == ["general"]
    
    def test_empty_api_key(self, resolver):
        """Empty API key should fall back to anonymous."""
        user = resolver.resolve_from_request(api_key_header="")
        
        assert user.auth_method == "anonymous"
    
    def test_api_key_with_single_role_string(self, resolver):
        """API key with single role as string (not list) should work."""
        user = resolver.resolve_from_request(api_key_header="single-role-key")
        
        assert user.user_id == "user-2"
        assert user.roles == ["pro"]
        assert user.auth_method == "api_key"
    
    def test_api_key_metadata(self, resolver):
        """API key metadata should include key prefix."""
        user = resolver.resolve_from_request(api_key_header="test-api-key-123")
        
        assert "api_key_prefix" in user.metadata
        assert user.metadata["api_key_prefix"] == "test-api"


# ============================================================================
# Test RoleResolver - Anonymous Fallback
# ============================================================================

class TestAnonymousFallback:
    """Test anonymous user fallback."""
    
    def test_no_credentials(self, resolver):
        """No credentials should result in anonymous user."""
        user = resolver.resolve_from_request()
        
        assert user.user_id is None
        assert user.email is None
        assert user.roles == ["general"]
        assert user.auth_method == "anonymous"
        assert user.is_anonymous
        assert not user.is_authenticated
    
    def test_custom_anonymous_roles(self):
        """Custom anonymous roles should be used."""
        resolver = RoleResolver(default_anonymous_roles=['guest', 'reader'])
        
        user = resolver.resolve_from_request()
        
        assert user.roles == ['guest', 'reader']
    
    def test_anonymous_metadata_empty(self, resolver):
        """Anonymous user should have empty metadata."""
        user = resolver.resolve_from_request()
        
        assert user.metadata == {}


# ============================================================================
# Test RoleResolver - Priority and Caching
# ============================================================================

class TestAuthenticationPriority:
    """Test authentication method priority."""
    
    def test_jwt_takes_priority_over_api_key(self, resolver, valid_jwt_token):
        """JWT should take priority over API key."""
        auth_header = f"Bearer {valid_jwt_token}"
        api_key = "test-api-key-123"
        
        user = resolver.resolve_from_request(
            authorization_header=auth_header,
            api_key_header=api_key,
        )
        
        # Should use JWT, not API key
        assert user.auth_method == "jwt"
        assert user.user_id == "user-123"  # From JWT
        assert user.email == "test@example.com"  # From JWT
    
    def test_api_key_used_when_jwt_invalid(self, resolver):
        """API key should be used when JWT is invalid."""
        auth_header = "Bearer invalid-token"
        api_key = "test-api-key-123"
        
        user = resolver.resolve_from_request(
            authorization_header=auth_header,
            api_key_header=api_key,
        )
        
        # Should fall back to API key
        assert user.auth_method == "api_key"
        assert user.user_id == "api-user-1"


class TestCaching:
    """Test request-level caching."""
    
    def test_same_credentials_cached(self, resolver, valid_jwt_token):
        """Same credentials should return cached result."""
        auth_header = f"Bearer {valid_jwt_token}"
        
        user1 = resolver.resolve_from_request(authorization_header=auth_header)
        user2 = resolver.resolve_from_request(authorization_header=auth_header)
        
        # Should be the same object (cached)
        assert user1 is user2
    
    def test_different_credentials_not_cached(self, resolver, valid_jwt_token):
        """Different credentials should not return cached result."""
        auth_header1 = f"Bearer {valid_jwt_token}"
        auth_header2 = None
        
        user1 = resolver.resolve_from_request(authorization_header=auth_header1)
        user2 = resolver.resolve_from_request(authorization_header=auth_header2)
        
        assert user1.auth_method == "jwt"
        assert user2.auth_method == "anonymous"
    
    def test_clear_cache(self, resolver, valid_jwt_token):
        """Clearing cache should remove cached entries."""
        auth_header = f"Bearer {valid_jwt_token}"
        
        user1 = resolver.resolve_from_request(authorization_header=auth_header)
        resolver.clear_cache()
        user2 = resolver.resolve_from_request(authorization_header=auth_header)
        
        # Should not be the same object after cache clear
        assert user1 is not user2
        # But should have same values
        assert user1.user_id == user2.user_id


# ============================================================================
# Test Global Resolver Configuration
# ============================================================================

class TestGlobalResolver:
    """Test global resolver configuration."""
    
    def test_configure_global_resolver(self, jwt_secret, api_key_map):
        """Configuring global resolver should work."""
        resolver = configure_resolver(
            supabase_jwt_secret=jwt_secret,
            api_key_to_user_map=api_key_map,
        )
        
        assert resolver is not None
        assert get_resolver() is resolver
    
    def test_get_resolver_returns_default_if_not_configured(self):
        """Getting resolver without configuration should return default."""
        resolver = get_resolver()
        
        assert resolver is not None
        assert isinstance(resolver, RoleResolver)
    
    def test_reset_resolver(self, jwt_secret):
        """Resetting resolver should clear configuration."""
        configure_resolver(supabase_jwt_secret=jwt_secret)
        reset_resolver()
        
        # Should get a new default resolver
        resolver = get_resolver()
        assert resolver is not None


# ============================================================================
# Test Middleware
# ============================================================================

class TestRoleResolutionMiddleware:
    """Test FastAPI middleware."""
    
    @pytest.fixture
    def app(self, jwt_secret, api_key_map):
        """Create test FastAPI app with middleware."""
        app = FastAPI()
        
        # Configure global resolver
        configure_resolver(
            supabase_jwt_secret=jwt_secret,
            api_key_to_user_map=api_key_map,
        )
        
        # Add middleware
        app.add_middleware(RoleResolutionMiddleware)
        
        # Add test routes
        @app.get("/test")
        def test_route(request: Request):
            ctx = get_current_user(request)
            return {
                "user_id": ctx.user_id,
                "email": ctx.email,
                "roles": ctx.roles,
                "auth_method": ctx.auth_method,
                "is_authenticated": ctx.is_authenticated,
            }
        
        @app.get("/user-id")
        def user_id_route(request: Request):
            return {"user_id": get_user_id(request)}
        
        @app.get("/roles")
        def roles_route(request: Request):
            return {"roles": get_user_roles(request)}
        
        @app.get("/protected")
        def protected_route(request: Request):
            ctx = require_authenticated(request)
            return {"message": "success", "user_id": ctx.user_id}
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)
    
    def test_middleware_with_jwt(self, client, valid_jwt_token):
        """Middleware should resolve JWT authentication."""
        response = client.get(
            "/test",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user-123"
        assert data["email"] == "test@example.com"
        assert "pro" in data["roles"]
        assert data["auth_method"] == "jwt"
        assert data["is_authenticated"] is True
    
    def test_middleware_with_api_key(self, client):
        """Middleware should resolve API key authentication."""
        response = client.get(
            "/test",
            headers={"X-API-KEY": "test-api-key-123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "api-user-1"
        assert "analytics" in data["roles"]
        assert data["auth_method"] == "api_key"
        assert data["is_authenticated"] is True
    
    def test_middleware_anonymous_fallback(self, client):
        """Middleware should fall back to anonymous."""
        response = client.get("/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] is None
        assert data["email"] is None
        assert data["roles"] == ["general"]
        assert data["auth_method"] == "anonymous"
        assert data["is_authenticated"] is False
    
    def test_middleware_with_invalid_jwt(self, client):
        """Middleware should handle invalid JWT gracefully."""
        response = client.get(
            "/test",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["auth_method"] == "anonymous"
        assert data["roles"] == ["general"]
    
    def test_helper_get_user_id(self, client, valid_jwt_token):
        """get_user_id helper should work."""
        response = client.get(
            "/user-id",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["user_id"] == "user-123"
    
    def test_helper_get_user_roles(self, client, valid_jwt_token):
        """get_user_roles helper should work."""
        response = client.get(
            "/roles",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        
        assert response.status_code == 200
        assert "pro" in response.json()["roles"]
    
    def test_require_authenticated_with_jwt(self, client, valid_jwt_token):
        """require_authenticated should allow authenticated users."""
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "success"
        assert data["user_id"] == "user-123"
    
    def test_require_authenticated_with_anonymous(self, client):
        """require_authenticated should raise error for anonymous."""
        # PermissionError should be raised but not handled by default
        # FastAPI will return 500 for unhandled exceptions
        with pytest.raises(PermissionError, match="Authentication required"):
            client.get("/protected")
    
    def test_case_insensitive_api_key_header(self, client):
        """API key header should be case-insensitive."""
        # Test with X-Api-Key instead of X-API-KEY
        response = client.get(
            "/test",
            headers={"X-Api-Key": "test-api-key-123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["auth_method"] == "api_key"


# ============================================================================
# Test ResolvedUser Data Class
# ============================================================================

class TestResolvedUser:
    """Test ResolvedUser data class."""
    
    def test_is_anonymous_property(self):
        """is_anonymous property should work correctly."""
        anonymous = ResolvedUser(
            user_id=None,
            email=None,
            roles=['general'],
            auth_method='anonymous',
            metadata={}
        )
        
        assert anonymous.is_anonymous is True
        assert anonymous.is_authenticated is False
    
    def test_is_authenticated_property(self):
        """is_authenticated property should work correctly."""
        authenticated = ResolvedUser(
            user_id="user-123",
            email="test@example.com",
            roles=['pro'],
            auth_method='jwt',
            metadata={}
        )
        
        assert authenticated.is_authenticated is True
        assert authenticated.is_anonymous is False


# ============================================================================
# Summary Test
# ============================================================================

class TestCompleteCoverage:
    """Comprehensive test to verify all authentication paths."""
    
    def test_all_authentication_paths(self, resolver, valid_jwt_token):
        """Test all three authentication paths work."""
        # Path 1: JWT
        jwt_user = resolver.resolve_from_request(
            authorization_header=f"Bearer {valid_jwt_token}"
        )
        assert jwt_user.auth_method == "jwt"
        assert jwt_user.is_authenticated
        
        # Path 2: API Key
        api_key_user = resolver.resolve_from_request(
            api_key_header="test-api-key-123"
        )
        assert api_key_user.auth_method == "api_key"
        assert api_key_user.is_authenticated
        
        # Path 3: Anonymous
        anon_user = resolver.resolve_from_request()
        assert anon_user.auth_method == "anonymous"
        assert not anon_user.is_authenticated
        assert anon_user.roles == ["general"]
    
    def test_all_invalid_credential_fallbacks(self, resolver):
        """Test that all invalid credentials fall back to general role."""
        test_cases = [
            {"authorization_header": "Bearer invalid"},
            {"authorization_header": "Invalid format"},
            {"api_key_header": "unknown-key"},
            {"authorization_header": "", "api_key_header": ""},
        ]
        
        for kwargs in test_cases:
            user = resolver.resolve_from_request(**kwargs)
            assert user.roles == ["general"], f"Failed for {kwargs}"
            assert user.auth_method == "anonymous"
