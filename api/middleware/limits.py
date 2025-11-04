#!/usr/bin/env python3
"""
api/middleware/limits.py — FastAPI middleware for resource limits.

Integrates ResourceLimiter with FastAPI to provide per-user concurrency
limits and queue management. Returns 429 responses with Retry-After headers
when limits are exceeded.

Usage:
    from fastapi import FastAPI
    from api.middleware.limits import LimiterMiddleware, get_user_id_from_request
    
    app = FastAPI()
    app.add_middleware(LimiterMiddleware)
"""

import time
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.limits import (
    get_limiter,
    OverloadError,
    LimitConfig,
    create_429_response
)
from core.metrics import increment_counter, observe_histogram


def get_user_id_from_request(request: Request) -> str:
    """
    Extract user ID from request.
    
    Tries multiple sources in order:
    1. Authenticated user from request.state.user
    2. API key from headers
    3. Session cookie
    4. Client IP address (fallback)
    
    Args:
        request: FastAPI Request object
        
    Returns:
        User identifier string
    """
    # Try authenticated user first
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        if hasattr(user, "id"):
            return f"user:{user.id}"
        elif isinstance(user, dict) and "id" in user:
            return f"user:{user['id']}"
    
    # Try API key
    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
    if api_key:
        # Use hash of API key as identifier
        import hashlib
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return f"apikey:{key_hash}"
    
    # Try session cookie
    session_id = request.cookies.get("session_id") or request.cookies.get("sessionid")
    if session_id:
        return f"session:{session_id}"
    
    # Fallback to IP address
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


def get_session_id_from_request(request: Request) -> Optional[str]:
    """
    Extract session ID from request.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Session ID if available, None otherwise
    """
    return request.cookies.get("session_id") or request.cookies.get("sessionid")


class LimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware for per-user concurrency limits.
    
    Intercepts requests and applies rate limiting based on user identity.
    Returns 429 responses with Retry-After headers when limits are exceeded.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        config: Optional[LimitConfig] = None,
        enabled: bool = True,
        exempt_paths: Optional[list] = None
    ):
        """
        Initialize limiter middleware.
        
        Args:
            app: ASGI application
            config: Optional limit configuration
            enabled: Whether middleware is enabled
            exempt_paths: List of paths to exempt from limiting (e.g., /health)
        """
        super().__init__(app)
        self.limiter = get_limiter(config)
        self.enabled = enabled
        self.exempt_paths = exempt_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting.
        
        Args:
            request: Incoming request
            call_next: Next handler in chain
            
        Returns:
            Response from handler or 429 if rate limited
        """
        # Skip if not enabled
        if not self.enabled:
            return await call_next(request)
        
        # Skip exempt paths
        path = request.url.path
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)
        
        # Extract user and session IDs
        user_id = get_user_id_from_request(request)
        session_id = get_session_id_from_request(request)
        request_id = f"{user_id}_{time.time_ns()}"
        
        start_time = time.time()
        
        try:
            # Acquire rate limit slot
            with self.limiter.limit(user_id, session_id, request_id):
                # Record queue time if any
                queue_time_ms = (time.time() - start_time) * 1000
                if queue_time_ms > 1.0:  # Only record if significant
                    observe_histogram("request_queue_time_ms", queue_time_ms)
                
                # Process request
                response = await call_next(request)
                
                # Record success
                increment_counter("limiter.requests.allowed", labels={
                    "path": path,
                    "method": request.method
                })
                
                return response
        
        except OverloadError as e:
            # Rate limit exceeded - return 429
            latency_ms = (time.time() - start_time) * 1000
            observe_histogram("limiter.overload_latency_ms", latency_ms)
            
            increment_counter("limiter.requests.rejected", labels={
                "path": path,
                "method": request.method,
                "reason": "overload"
            })
            
            # Create 429 response
            response_data = create_429_response(e)
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=response_data,
                headers={
                    "Retry-After": str(e.retry_after),
                    "X-RateLimit-Limit": str(self.limiter.config.max_concurrent_per_user),
                    "X-RateLimit-Reset": str(int(time.time()) + e.retry_after)
                }
            )
        
        except TimeoutError as e:
            # Request timed out in queue
            latency_ms = (time.time() - start_time) * 1000
            observe_histogram("limiter.timeout_latency_ms", latency_ms)
            
            increment_counter("limiter.requests.timeout", labels={
                "path": path,
                "method": request.method
            })
            
            return JSONResponse(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                content={
                    "error": "request_timeout",
                    "message": str(e),
                    "status": 408
                }
            )
        
        except Exception as e:
            # Unexpected error - let it propagate
            increment_counter("limiter.errors", labels={
                "path": path,
                "error_type": type(e).__name__
            })
            raise


# FastAPI dependency for manual rate limiting
async def check_rate_limit(request: Request):
    """
    FastAPI dependency to manually check rate limits.
    
    Usage:
        @app.post("/expensive-operation")
        async def expensive_op(
            request: Request,
            _: None = Depends(check_rate_limit)
        ):
            # This endpoint will be rate-limited
            ...
    
    Args:
        request: FastAPI Request object
        
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    limiter = get_limiter()
    user_id = get_user_id_from_request(request)
    session_id = get_session_id_from_request(request)
    
    try:
        ctx = limiter.check_limits(user_id, session_id)
        # Store context in request state for cleanup
        request.state.limiter_context = ctx
    except OverloadError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=create_429_response(e),
            headers={
                "Retry-After": str(e.retry_after)
            }
        )


async def release_rate_limit(request: Request):
    """
    FastAPI dependency to release rate limit slot.
    
    Should be called in a finally block or at end of request.
    
    Usage:
        @app.post("/expensive-operation")
        async def expensive_op(request: Request):
            await check_rate_limit(request)
            try:
                # Process request
                ...
            finally:
                await release_rate_limit(request)
    
    Args:
        request: FastAPI Request object
    """
    if hasattr(request.state, "limiter_context"):
        limiter = get_limiter()
        limiter.release(request.state.limiter_context)
        delattr(request.state, "limiter_context")


def create_rate_limit_response(retry_after: int, message: str) -> JSONResponse:
    """
    Create a 429 rate limit response.
    
    Args:
        retry_after: Seconds to wait before retrying
        message: Error message
        
    Returns:
        JSONResponse with 429 status
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "too_many_requests",
            "message": message,
            "retry_after": retry_after,
            "status": 429
        },
        headers={
            "Retry-After": str(retry_after)
        }
    )


# Utility to get current limiter stats (for debug endpoints)
def get_limiter_stats():
    """
    Get current limiter statistics.
    
    Returns:
        Dict with limiter stats
    """
    limiter = get_limiter()
    return limiter.get_stats()
