"""
FastAPI middleware for role resolution and request context population.

Extracts user identity and roles from JWT tokens or API keys,
and attaches them to the request state for use in route handlers.
"""

import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.rbac.resolve import get_resolver, ResolvedUser

logger = logging.getLogger(__name__)


# ============================================================================
# Request State Extensions
# ============================================================================

class RequestContext:
    """
    Request context for user identity and roles.
    
    Attached to request.state by the RoleResolutionMiddleware.
    """
    
    def __init__(self, user: ResolvedUser):
        self.user_id: Optional[str] = user.user_id
        self.email: Optional[str] = user.email
        self.roles: list[str] = user.roles
        self.auth_method: str = user.auth_method
        self.is_authenticated: bool = user.is_authenticated
        self.metadata: dict = user.metadata
    
    def __repr__(self) -> str:
        return (
            f"RequestContext(user_id={self.user_id}, "
            f"roles={self.roles}, auth_method={self.auth_method})"
        )


# ============================================================================
# Middleware
# ============================================================================

class RoleResolutionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve user identity and roles from request headers.
    
    Extracts authentication from:
    1. Authorization header (JWT token)
    2. X-API-KEY header (API key)
    3. Falls back to anonymous user with 'general' role
    
    Attaches the following to request.state:
    - user_id: User ID (or None for anonymous)
    - email: User email (or None)
    - roles: List of role names
    - auth_method: 'jwt', 'api_key', or 'anonymous'
    - is_authenticated: Boolean
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Process request to resolve user roles.
        
        Args:
            request: Incoming request
            call_next: Next middleware/route handler
            
        Returns:
            Response from downstream handlers
        """
        try:
            # Extract authentication headers
            authorization = request.headers.get("Authorization")
            api_key = request.headers.get("X-API-KEY") or request.headers.get("X-Api-Key")
            
            # Resolve user and roles
            resolver = get_resolver()
            user = resolver.resolve_from_request(
                authorization_header=authorization,
                api_key_header=api_key,
            )
            
            # Attach to request state
            request.state.ctx = RequestContext(user)
            
            # Log authentication
            logger.debug(
                f"Resolved user for {request.method} {request.url.path}: "
                f"user_id={user.user_id}, roles={user.roles}, method={user.auth_method}"
            )
            
        except Exception as e:
            # On error during role resolution, create anonymous user as fallback
            logger.error(f"Error resolving user roles: {e}", exc_info=True)
            
            from core.rbac.resolve import ResolvedUser
            anonymous_user = ResolvedUser(
                user_id=None,
                email=None,
                roles=['general'],
                auth_method='anonymous',
                metadata={'error': str(e)}
            )
            request.state.ctx = RequestContext(anonymous_user)
        
        # Continue to next handler (exceptions from here should propagate)
        response = await call_next(request)
        return response


# ============================================================================
# Helper Functions
# ============================================================================

def get_current_user(request: Request) -> RequestContext:
    """
    Get current user context from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        RequestContext with user_id, roles, etc.
        
    Raises:
        AttributeError: If middleware has not been applied
    """
    if not hasattr(request.state, "ctx"):
        raise AttributeError(
            "Request state does not have 'ctx' attribute. "
            "Ensure RoleResolutionMiddleware is configured."
        )
    
    return request.state.ctx


def require_authenticated(request: Request) -> RequestContext:
    """
    Require that the request is from an authenticated user.
    
    Args:
        request: FastAPI request object
        
    Returns:
        RequestContext for authenticated user
        
    Raises:
        PermissionError: If user is not authenticated
    """
    ctx = get_current_user(request)
    
    if not ctx.is_authenticated:
        raise PermissionError("Authentication required")
    
    return ctx


def get_user_id(request: Request) -> Optional[str]:
    """
    Get user ID from request context.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User ID or None if anonymous
    """
    ctx = get_current_user(request)
    return ctx.user_id


def get_user_roles(request: Request) -> list[str]:
    """
    Get user roles from request context.
    
    Args:
        request: FastAPI request object
        
    Returns:
        List of role names
    """
    ctx = get_current_user(request)
    return ctx.roles
