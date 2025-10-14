# api/factate.py — Factare API endpoints

try:
    from fastapi import APIRouter, HTTPException, Depends, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Mock classes for when FastAPI is not available
    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass
        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def exception_handler(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def include_router(self, *args, **kwargs):
            pass
    
    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail
    
    class Depends:
        def __init__(self, func):
            self.func = func
    
    class Request:
        pass
    
    class JSONResponse:
        def __init__(self, *args, **kwargs):
            pass
    
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    def Field(*args, **kwargs):
        return None

from typing import List, Dict, Any, Optional
import time

from core.factare.service import (
    get_factare_service, 
    ComparisonOptions, 
    ComparisonResult,
    compare_factare
)
from core.factare.compare_internal import RetrievalCandidate
from core.policy import can_access_factare
from feature_flags import get_feature_flag

# Create router
router = APIRouter(prefix="/factate", tags=["factate"])

# Request/Response models
class RetrievalCandidateData(BaseModel):
    """Retrieval candidate data from request."""
    id: str
    content: str
    source: str
    score: float = Field(ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    timestamp: Optional[str] = None

class ComparisonOptionsData(BaseModel):
    """Comparison options from request."""
    allow_external: bool = False
    max_external_snippets: int = Field(default=5, ge=1, le=20)
    max_snippet_length: int = Field(default=200, ge=50, le=1000)
    timeout_seconds: int = Field(default=2, ge=1, le=30)
    enable_redaction: bool = True

class CompareRequest(BaseModel):
    """Request model for factare comparison."""
    query: str = Field(..., min_length=1, max_length=1000)
    retrieval_candidates: List[RetrievalCandidateData] = Field(default_factory=list)
    external_urls: List[str] = Field(default_factory=list, max_items=10)
    user_roles: List[str] = Field(default_factory=list)
    options: ComparisonOptionsData = Field(default_factory=ComparisonOptionsData)

class ContradictionData(BaseModel):
    """Contradiction data in response."""
    claim_a: str
    claim_b: str
    evidence_a: str
    evidence_b: str
    confidence: float = Field(ge=0.0, le=1.0)
    contradiction_type: str

class TimingsData(BaseModel):
    """Timing data in response."""
    internal_ms: float
    external_ms: float
    total_ms: float
    redaction_ms: float = 0.0

class CompareResponse(BaseModel):
    """Response model for factare comparison."""
    compare_summary: Dict[str, Any]
    contradictions: List[ContradictionData]
    used_external: bool
    timings: TimingsData
    metadata: Dict[str, Any]

class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

# Dependency functions
def get_user_roles_from_request(request: Request) -> List[str]:
    """Extract user roles from request headers or context."""
    # In a real implementation, this would extract from JWT token or session
    # For now, we'll use a header or default to a basic role
    roles_header = request.headers.get('X-User-Roles', 'user')
    if isinstance(roles_header, str):
        return [role.strip() for role in roles_header.split(',')]
    return ['user']

def validate_factare_access(user_roles: List[str]) -> bool:
    """Validate that user has access to factare."""
    if not get_feature_flag('factare.enabled'):
        return False
    return can_access_factare(user_roles, get_feature_flag('factare.enabled'))

# Endpoints
@router.post(
    "/compare",
    response_model=CompareResponse,
    responses={
        200: {"description": "Comparison completed successfully"},
        400: {"description": "Bad request", "model": ErrorResponse},
        403: {"description": "Forbidden - insufficient permissions", "model": ErrorResponse},
        404: {"description": "Not found - factare disabled", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def compare(
    request: CompareRequest,
    http_request: Request,
    user_roles: List[str] = Depends(get_user_roles_from_request)
):
    """
    Compare query using internal and optional external sources.
    
    Args:
        request: Comparison request with query, candidates, and options
        http_request: HTTP request object
        user_roles: User roles for access control
        
    Returns:
        CompareResponse with comparison results, contradictions, and timings
        
    Raises:
        HTTPException: 404 if factare disabled, 403 if insufficient permissions
    """
    start_time = time.time()
    
    try:
        # Check if factare is enabled
        if not get_feature_flag('factare.enabled'):
            raise HTTPException(
                status_code=404,
                detail="Factare service is not enabled"
            )
        
        # Validate user access
        if not validate_factare_access(user_roles):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to access factare"
            )
        
        # Convert request data to service objects
        retrieval_candidates = []
        for candidate_data in request.retrieval_candidates:
            candidate = RetrievalCandidate(
                id=candidate_data.id,
                content=candidate_data.content,
                source=candidate_data.source,
                score=candidate_data.score,
                metadata=candidate_data.metadata,
                url=candidate_data.url,
                timestamp=candidate_data.timestamp
            )
            retrieval_candidates.append(candidate)
        
        # Create comparison options
        options = ComparisonOptions(
            allow_external=request.options.allow_external,
            max_external_snippets=request.options.max_external_snippets,
            max_snippet_length=request.options.max_snippet_length,
            timeout_seconds=request.options.timeout_seconds,
            enable_redaction=request.options.enable_redaction
        )
        
        # Use user roles from request if provided, otherwise use extracted roles
        final_user_roles = request.user_roles if request.user_roles else user_roles
        
        # Perform comparison
        service = get_factare_service()
        result = await service.compare(
            query=request.query,
            retrieval_candidates=retrieval_candidates,
            external_urls=request.external_urls,
            user_roles=final_user_roles,
            options=options
        )
        
        # Convert contradictions to response format
        contradictions = [
            ContradictionData(
                claim_a=c['claim_a'],
                claim_b=c['claim_b'],
                evidence_a=c['evidence_a'],
                evidence_b=c['evidence_b'],
                confidence=c['confidence'],
                contradiction_type=c['contradiction_type']
            )
            for c in result.contradictions
        ]
        
        # Convert timings to response format
        timings = TimingsData(
            internal_ms=result.timings['internal_ms'],
            external_ms=result.timings['external_ms'],
            total_ms=result.timings['total_ms'],
            redaction_ms=result.timings['redaction_ms']
        )
        
        # Convert compare summary to dict
        compare_summary_dict = result.compare_summary.to_dict()
        
        # Add processing time to metadata
        result.metadata['api_processing_ms'] = (time.time() - start_time) * 1000
        
        return CompareResponse(
            compare_summary=compare_summary_dict,
            contradictions=contradictions,
            used_external=result.used_external,
            timings=timings,
            metadata=result.metadata
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get(
    "/status",
    response_model=Dict[str, Any],
    responses={
        200: {"description": "Service status retrieved successfully"},
        404: {"description": "Not found - factare disabled"}
    }
)
async def get_status():
    """
    Get factare service status and configuration.
    
    Returns:
        Dict with service status information
    """
    if not get_feature_flag('factare.enabled'):
        raise HTTPException(
            status_code=404,
            detail="Factare service is not enabled"
        )
    
    service = get_factare_service()
    return service.get_service_status()

@router.get(
    "/health",
    response_model=Dict[str, str],
    responses={
        200: {"description": "Health check successful"}
    }
)
async def health_check():
    """
    Health check endpoint for factare service.
    
    Returns:
        Dict with health status
    """
    return {
        "status": "healthy",
        "service": "factate",
        "timestamp": str(time.time())
    }

# Error handlers
@router.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": str(exc.status_code),
            "timestamp": str(time.time())
        }
    )

@router.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with proper error format."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "code": "500",
            "timestamp": str(time.time())
        }
    )