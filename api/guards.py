"""
API endpoint guards for capability-based authorization.

Provides decorators to protect FastAPI routes based on RBAC capabilities.
"""

import logging
from functools import wraps
from typing import Callable, Any
from fastapi import Request, HTTPException, status

from core.rbac import has_capability
from api.middleware.roles import get_current_user
from core.metrics import record_rbac_check, audit_rbac_denial

logger = logging.getLogger(__name__)


# ============================================================================
# Guard Decorator
# ============================================================================

def require(capability: str) -> Callable:
    """
    Decorator to require a specific capability for a FastAPI route.
    
    Checks if any of the user's roles (from request.state.ctx) have the
    required capability. If not, raises HTTPException with 403 status.
    
    Args:
        capability: Capability constant (e.g., CAP_WRITE_GRAPH)
        
    Returns:
        Decorator function
        
    Raises:
        HTTPException: 403 if user lacks required capability
        
    Examples:
        >>> from api.guards import require
        >>> from core.rbac import CAP_WRITE_GRAPH
        >>> 
        >>> @app.post("/graph/entities")
        >>> @require(CAP_WRITE_GRAPH)
        >>> def create_entity(request: Request, data: dict):
        >>>     # Only users with WRITE_GRAPH capability can access
        >>>     return {"status": "created"}
        
        >>> @app.post("/hypotheses")
        >>> @require(CAP_PROPOSE_HYPOTHESIS)
        >>> def propose_hypothesis(request: Request, data: dict):
        >>>     # Only users with PROPOSE_HYPOTHESIS capability can access
        >>>     return {"status": "submitted"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Extract request from arguments
            request = _extract_request_from_args(args, kwargs)
            
            if request is None:
                logger.error(
                    f"@require({capability}) decorator requires Request parameter"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: Request not found"
                )
            
            # Get user context
            try:
                ctx = get_current_user(request)
            except AttributeError:
                logger.error("Request context not available. Is RoleResolutionMiddleware configured?")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: User context not available"
                )
            
            # Check if any of the user's roles have the required capability
            has_required_capability = any(
                has_capability(role, capability) 
                for role in ctx.roles
            )
            
            # Record metrics
            record_rbac_check(
                allowed=has_required_capability,
                capability=capability,
                roles=ctx.roles,
                route=str(request.url.path)
            )
            
            if not has_required_capability:
                # Audit the denial
                audit_rbac_denial(
                    capability=capability,
                    user_id=ctx.user_id,
                    roles=ctx.roles,
                    route=str(request.url.path),
                    method=request.method,
                    metadata={"is_authenticated": ctx.is_authenticated}
                )
                
                logger.warning(
                    f"Access denied: user_id={ctx.user_id}, "
                    f"roles={ctx.roles}, required_capability={capability}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "forbidden",
                        "capability": capability,
                        "message": f"Capability '{capability}' required",
                    }
                )
            
            # User has required capability - proceed with request
            logger.debug(
                f"Access granted: user_id={ctx.user_id}, "
                f"roles={ctx.roles}, capability={capability}"
            )
            
            # Call the original function
            if isinstance(func, type) and hasattr(func, '__call__'):
                # Handle class-based views
                return await func(*args, **kwargs)
            else:
                # Handle regular async functions
                result = func(*args, **kwargs)
                # If result is a coroutine, await it
                if hasattr(result, '__await__'):
                    return await result
                return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Extract request from arguments
            request = _extract_request_from_args(args, kwargs)
            
            if request is None:
                logger.error(
                    f"@require({capability}) decorator requires Request parameter"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: Request not found"
                )
            
            # Get user context
            try:
                ctx = get_current_user(request)
            except AttributeError:
                logger.error("Request context not available. Is RoleResolutionMiddleware configured?")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: User context not available"
                )
            
            # Check if any of the user's roles have the required capability
            has_required_capability = any(
                has_capability(role, capability) 
                for role in ctx.roles
            )
            
            if not has_required_capability:
                logger.warning(
                    f"Access denied: user_id={ctx.user_id}, "
                    f"roles={ctx.roles}, required_capability={capability}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "forbidden",
                        "capability": capability,
                        "message": f"Capability '{capability}' required",
                    }
                )
            
            # User has required capability - proceed with request
            logger.debug(
                f"Access granted: user_id={ctx.user_id}, "
                f"roles={ctx.roles}, capability={capability}"
            )
            
            # Call the original function
            return func(*args, **kwargs)
        
        # Determine if function is async or sync
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_any(*capabilities: str) -> Callable:
    """
    Decorator to require ANY of the specified capabilities.
    
    User must have at least one of the listed capabilities.
    
    Args:
        *capabilities: One or more capability constants
        
    Returns:
        Decorator function
        
    Raises:
        HTTPException: 403 if user lacks all required capabilities
        
    Examples:
        >>> @app.post("/content")
        >>> @require_any(CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS)
        >>> def create_content(request: Request, data: dict):
        >>>     # User needs either WRITE_GRAPH or WRITE_CONTRADICTIONS
        >>>     return {"status": "created"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            request = _extract_request_from_args(args, kwargs)
            
            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: Request not found"
                )
            
            try:
                ctx = get_current_user(request)
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: User context not available"
                )
            
            # Check if user has ANY of the required capabilities
            has_any_capability = any(
                has_capability(role, cap)
                for role in ctx.roles
                for cap in capabilities
            )
            
            if not has_any_capability:
                logger.warning(
                    f"Access denied: user_id={ctx.user_id}, "
                    f"roles={ctx.roles}, required_any_of={capabilities}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "forbidden",
                        "capabilities": list(capabilities),
                        "message": f"One of {capabilities} capabilities required",
                    }
                )
            
            logger.debug(
                f"Access granted: user_id={ctx.user_id}, "
                f"roles={ctx.roles}, required_any_of={capabilities}"
            )
            
            result = func(*args, **kwargs)
            if hasattr(result, '__await__'):
                return await result
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            request = _extract_request_from_args(args, kwargs)
            
            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: Request not found"
                )
            
            try:
                ctx = get_current_user(request)
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: User context not available"
                )
            
            # Check if user has ANY of the required capabilities
            has_any_capability = any(
                has_capability(role, cap)
                for role in ctx.roles
                for cap in capabilities
            )
            
            if not has_any_capability:
                logger.warning(
                    f"Access denied: user_id={ctx.user_id}, "
                    f"roles={ctx.roles}, required_any_of={capabilities}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "forbidden",
                        "capabilities": list(capabilities),
                        "message": f"One of {capabilities} capabilities required",
                    }
                )
            
            logger.debug(
                f"Access granted: user_id={ctx.user_id}, "
                f"roles={ctx.roles}, required_any_of={capabilities}"
            )
            
            return func(*args, **kwargs)
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_all(*capabilities: str) -> Callable:
    """
    Decorator to require ALL of the specified capabilities.
    
    User must have all of the listed capabilities.
    
    Args:
        *capabilities: One or more capability constants
        
    Returns:
        Decorator function
        
    Raises:
        HTTPException: 403 if user lacks any required capability
        
    Examples:
        >>> @app.post("/admin/action")
        >>> @require_all(CAP_WRITE_GRAPH, CAP_MANAGE_ROLES)
        >>> def admin_action(request: Request, data: dict):
        >>>     # User needs both WRITE_GRAPH and MANAGE_ROLES
        >>>     return {"status": "done"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            request = _extract_request_from_args(args, kwargs)
            
            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: Request not found"
                )
            
            try:
                ctx = get_current_user(request)
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: User context not available"
                )
            
            # Check if user has ALL of the required capabilities
            for cap in capabilities:
                has_cap = any(has_capability(role, cap) for role in ctx.roles)
                if not has_cap:
                    logger.warning(
                        f"Access denied: user_id={ctx.user_id}, "
                        f"roles={ctx.roles}, missing_capability={cap}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "forbidden",
                            "capabilities": list(capabilities),
                            "missing": cap,
                            "message": f"All of {capabilities} capabilities required",
                        }
                    )
            
            logger.debug(
                f"Access granted: user_id={ctx.user_id}, "
                f"roles={ctx.roles}, required_all_of={capabilities}"
            )
            
            result = func(*args, **kwargs)
            if hasattr(result, '__await__'):
                return await result
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            request = _extract_request_from_args(args, kwargs)
            
            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: Request not found"
                )
            
            try:
                ctx = get_current_user(request)
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error: User context not available"
                )
            
            # Check if user has ALL of the required capabilities
            for cap in capabilities:
                has_cap = any(has_capability(role, cap) for role in ctx.roles)
                if not has_cap:
                    logger.warning(
                        f"Access denied: user_id={ctx.user_id}, "
                        f"roles={ctx.roles}, missing_capability={cap}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "forbidden",
                            "capabilities": list(capabilities),
                            "missing": cap,
                            "message": f"All of {capabilities} capabilities required",
                        }
                    )
            
            logger.debug(
                f"Access granted: user_id={ctx.user_id}, "
                f"roles={ctx.roles}, required_all_of={capabilities}"
            )
            
            return func(*args, **kwargs)
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_request_from_args(args: tuple, kwargs: dict) -> Request:
    """
    Extract Request object from function arguments.
    
    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        Request object if found, None otherwise
    """
    # Check kwargs first
    if 'request' in kwargs:
        return kwargs['request']
    
    # Check positional args
    for arg in args:
        if isinstance(arg, Request):
            return arg
    
    return None
