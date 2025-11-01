"""
Role resolution logic for user authentication and authorization.

Resolves user identity and roles from multiple sources:
- Supabase JWT tokens
- API key headers
- Anonymous fallback
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import jwt
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ResolvedUser:
    """Resolved user identity and roles."""
    user_id: Optional[str]
    email: Optional[str]
    roles: List[str]
    auth_method: str  # 'jwt', 'api_key', 'anonymous'
    metadata: Dict[str, Any]
    
    @property
    def is_anonymous(self) -> bool:
        """Check if this is an anonymous user."""
        return self.auth_method == 'anonymous'
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated (not anonymous)."""
        return not self.is_anonymous


# ============================================================================
# Role Resolver
# ============================================================================

class RoleResolver:
    """
    Resolves user identity and roles from various authentication sources.
    
    Supports:
    - Supabase JWT tokens (Authorization: Bearer <token>)
    - API keys (X-API-KEY header)
    - Anonymous fallback (default to 'general' role)
    """
    
    def __init__(
        self,
        supabase_jwt_secret: Optional[str] = None,
        api_key_to_user_map: Optional[Dict[str, Dict[str, Any]]] = None,
        default_anonymous_roles: Optional[List[str]] = None,
    ):
        """
        Initialize role resolver.
        
        Args:
            supabase_jwt_secret: Secret for verifying Supabase JWT tokens
            api_key_to_user_map: Mapping of API keys to user info
            default_anonymous_roles: Roles to assign to anonymous users
        """
        self.supabase_jwt_secret = supabase_jwt_secret
        self.api_key_to_user_map = api_key_to_user_map or {}
        self.default_anonymous_roles = default_anonymous_roles or ['general']
        
        # Request-level cache
        self._request_cache: Dict[str, ResolvedUser] = {}
    
    def resolve_from_request(
        self,
        authorization_header: Optional[str] = None,
        api_key_header: Optional[str] = None,
    ) -> ResolvedUser:
        """
        Resolve user identity and roles from request headers.
        
        Priority order:
        1. JWT token (Authorization header)
        2. API key (X-API-KEY header)
        3. Anonymous fallback
        
        Args:
            authorization_header: Authorization header value (e.g., "Bearer <token>")
            api_key_header: API key header value
            
        Returns:
            ResolvedUser with user_id, email, roles, and auth method
        """
        # Check cache first
        cache_key = f"{authorization_header}:{api_key_header}"
        if cache_key in self._request_cache:
            logger.debug("Returning cached user resolution")
            return self._request_cache[cache_key]
        
        # Try JWT first
        if authorization_header:
            logger.debug("Attempting JWT authentication")
            user = self._resolve_from_jwt(authorization_header)
            if user:
                self._request_cache[cache_key] = user
                return user
        
        # Try API key second
        if api_key_header:
            logger.debug("Attempting API key authentication")
            user = self._resolve_from_api_key(api_key_header)
            if user:
                self._request_cache[cache_key] = user
                return user
        
        # Fallback to anonymous
        logger.debug("Falling back to anonymous user")
        user = self._resolve_anonymous()
        self._request_cache[cache_key] = user
        return user
    
    def _resolve_from_jwt(self, authorization_header: str) -> Optional[ResolvedUser]:
        """
        Resolve user from Supabase JWT token.
        
        Args:
            authorization_header: Authorization header value
            
        Returns:
            ResolvedUser if JWT is valid, None otherwise
        """
        try:
            # Extract token from "Bearer <token>"
            if not authorization_header.startswith("Bearer "):
                logger.warning("Invalid Authorization header format (missing 'Bearer')")
                return None
            
            token = authorization_header[7:].strip()
            if not token:
                logger.warning("Empty JWT token")
                return None
            
            # Verify and decode JWT
            if not self.supabase_jwt_secret:
                logger.warning("No Supabase JWT secret configured, skipping JWT verification")
                return None
            
            try:
                payload = jwt.decode(
                    token,
                    self.supabase_jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_exp": True}
                )
            except jwt.ExpiredSignatureError:
                logger.warning("JWT token has expired")
                return None
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid JWT token: {e}")
                return None
            
            # Extract user information from payload
            user_id = payload.get("sub")
            email = payload.get("email")
            
            if not user_id:
                logger.warning("JWT token missing 'sub' claim")
                return None
            
            # Extract roles from JWT metadata or use default
            # Supabase can store custom claims in app_metadata or user_metadata
            roles = self._extract_roles_from_jwt_payload(payload)
            
            logger.info(f"Resolved user from JWT: user_id={user_id}, email={email}, roles={roles}")
            
            return ResolvedUser(
                user_id=user_id,
                email=email,
                roles=roles,
                auth_method='jwt',
                metadata={
                    'jwt_payload': payload,
                    'token_issued_at': payload.get('iat'),
                    'token_expires_at': payload.get('exp'),
                }
            )
            
        except Exception as e:
            logger.error(f"Error resolving user from JWT: {e}", exc_info=True)
            return None
    
    def _extract_roles_from_jwt_payload(self, payload: Dict[str, Any]) -> List[str]:
        """
        Extract roles from JWT payload.
        
        Checks multiple possible locations:
        1. payload['roles'] (direct)
        2. payload['app_metadata']['roles']
        3. payload['user_metadata']['roles']
        4. Falls back to ['pro'] for authenticated users
        
        Args:
            payload: Decoded JWT payload
            
        Returns:
            List of role names
        """
        # Check direct roles claim
        if 'roles' in payload and isinstance(payload['roles'], list):
            return payload['roles']
        
        # Check app_metadata
        app_metadata = payload.get('app_metadata', {})
        if isinstance(app_metadata, dict) and 'roles' in app_metadata:
            roles = app_metadata['roles']
            if isinstance(roles, list):
                return roles
        
        # Check user_metadata
        user_metadata = payload.get('user_metadata', {})
        if isinstance(user_metadata, dict) and 'roles' in user_metadata:
            roles = user_metadata['roles']
            if isinstance(roles, list):
                return roles
        
        # Default to 'pro' for authenticated users
        logger.debug("No roles found in JWT, defaulting to ['pro']")
        return ['pro']
    
    def _resolve_from_api_key(self, api_key: str) -> Optional[ResolvedUser]:
        """
        Resolve user from API key.
        
        Args:
            api_key: API key value
            
        Returns:
            ResolvedUser if API key is valid, None otherwise
        """
        if not api_key:
            return None
        
        # Look up API key in mapping
        user_info = self.api_key_to_user_map.get(api_key)
        
        if not user_info:
            logger.warning(f"Unknown API key: {api_key[:8]}...")
            return None
        
        user_id = user_info.get('user_id')
        email = user_info.get('email')
        roles = user_info.get('roles', ['pro'])  # Default to 'pro' for API keys
        
        if not isinstance(roles, list):
            roles = [roles]
        
        logger.info(f"Resolved user from API key: user_id={user_id}, roles={roles}")
        
        return ResolvedUser(
            user_id=user_id,
            email=email,
            roles=roles,
            auth_method='api_key',
            metadata={
                'api_key_prefix': api_key[:8] if len(api_key) >= 8 else api_key,
            }
        )
    
    def _resolve_anonymous(self) -> ResolvedUser:
        """
        Create anonymous user with default roles.
        
        Returns:
            ResolvedUser for anonymous user
        """
        logger.debug(f"Creating anonymous user with roles: {self.default_anonymous_roles}")
        
        return ResolvedUser(
            user_id=None,
            email=None,
            roles=self.default_anonymous_roles.copy(),
            auth_method='anonymous',
            metadata={}
        )
    
    def clear_cache(self):
        """Clear the request-level cache."""
        self._request_cache.clear()


# ============================================================================
# Global Resolver Instance
# ============================================================================

# Global resolver instance (can be configured at app startup)
_global_resolver: Optional[RoleResolver] = None


def get_resolver() -> RoleResolver:
    """
    Get the global role resolver instance.
    
    Returns:
        Global RoleResolver instance
        
    Raises:
        RuntimeError: If resolver has not been configured
    """
    global _global_resolver
    
    if _global_resolver is None:
        # Create default resolver
        logger.warning("Using default role resolver (not configured)")
        _global_resolver = RoleResolver()
    
    return _global_resolver


def configure_resolver(
    supabase_jwt_secret: Optional[str] = None,
    api_key_to_user_map: Optional[Dict[str, Dict[str, Any]]] = None,
    default_anonymous_roles: Optional[List[str]] = None,
) -> RoleResolver:
    """
    Configure the global role resolver.
    
    Args:
        supabase_jwt_secret: Secret for verifying Supabase JWT tokens
        api_key_to_user_map: Mapping of API keys to user info
        default_anonymous_roles: Roles to assign to anonymous users
        
    Returns:
        Configured RoleResolver instance
    """
    global _global_resolver
    
    _global_resolver = RoleResolver(
        supabase_jwt_secret=supabase_jwt_secret,
        api_key_to_user_map=api_key_to_user_map,
        default_anonymous_roles=default_anonymous_roles,
    )
    
    logger.info("Configured global role resolver")
    return _global_resolver


def reset_resolver():
    """Reset the global resolver (useful for testing)."""
    global _global_resolver
    _global_resolver = None
