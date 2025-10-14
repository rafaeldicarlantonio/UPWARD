# api/hypotheses.py — Hypotheses API endpoints

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

from core.hypotheses.propose import (
    get_hypothesis_proposer,
    propose_hypothesis,
    HypothesisProposal,
    ProposalResult,
    HypothesisStatus
)
from core.factare.summary import CompareSummary
from core.policy import get_pareto_threshold
from feature_flags import get_feature_flag

# Create router
router = APIRouter(prefix="/hypotheses", tags=["hypotheses"])

# Request/Response models
class CompareSummaryData(BaseModel):
    """Compare summary data from request."""
    query: str
    stance_a: str
    stance_b: str
    evidence: List[Dict[str, Any]]
    decision: Dict[str, Any]
    created_at: str
    metadata: Optional[Dict[str, Any]] = None

class ProposeRequest(BaseModel):
    """Request model for hypothesis proposal."""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    source_message_id: str = Field(..., min_length=1, max_length=100)
    compare_summary: Optional[CompareSummaryData] = None
    pareto_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    override_reason: Optional[str] = Field(None, max_length=500)

class ProposeResponse(BaseModel):
    """Response model for hypothesis proposal."""
    result: str
    hypothesis_id: Optional[str] = None
    pareto_score: Optional[float] = None
    pareto_components: Optional[Dict[str, Any]] = None
    threshold: Optional[float] = None
    override_reason: Optional[str] = None
    persisted_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class HypothesisResponse(BaseModel):
    """Response model for individual hypothesis."""
    id: str
    title: str
    description: str
    source_message_id: str
    pareto_score: Optional[float] = None
    status: str
    created_at: str
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

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

def get_user_id_from_request(request: Request) -> Optional[str]:
    """Extract user ID from request headers or context."""
    # In a real implementation, this would extract from JWT token or session
    return request.headers.get('X-User-ID')

# Endpoints
@router.post(
    "/propose",
    response_model=ProposeResponse,
    responses={
        201: {"description": "Hypothesis persisted successfully"},
        202: {"description": "Hypothesis not persisted due to low score"},
        400: {"description": "Bad request", "model": ErrorResponse},
        403: {"description": "Forbidden - insufficient permissions", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def propose(
    request: ProposeRequest,
    http_request: Request,
    user_roles: List[str] = Depends(get_user_roles_from_request)
):
    """
    Propose a hypothesis with Pareto gating.
    
    Args:
        request: Hypothesis proposal request
        http_request: HTTP request object
        user_roles: User roles for access control
        
    Returns:
        ProposeResponse with result and metadata
        
    Raises:
        HTTPException: 400 for validation errors, 403 for insufficient permissions
    """
    start_time = time.time()
    
    try:
        # Check if hypotheses feature is enabled
        if not get_feature_flag('hypotheses.enabled'):
            raise HTTPException(
                status_code=404,
                detail="Hypotheses feature is not enabled"
            )
        
        # Convert compare_summary if provided
        compare_summary = None
        if request.compare_summary:
            compare_summary = CompareSummary.from_dict(request.compare_summary.__dict__)
        
        # Get user ID
        user_id = get_user_id_from_request(http_request)
        
        # Propose hypothesis
        proposer = get_hypothesis_proposer()
        response = proposer.propose_hypothesis(
            title=request.title,
            description=request.description,
            source_message_id=request.source_message_id,
            compare_summary=compare_summary,
            pareto_score=request.pareto_score,
            user_roles=user_roles,
            override_reason=request.override_reason,
            created_by=user_id
        )
        
        # Convert response to API format
        api_response = ProposeResponse(
            result=response.result.value,
            hypothesis_id=response.hypothesis_id,
            pareto_score=response.pareto_score,
            pareto_components=response.pareto_components.__dict__ if response.pareto_components else None,
            threshold=response.threshold,
            override_reason=response.override_reason,
            persisted_at=response.persisted_at.isoformat() if response.persisted_at else None,
            metadata=response.metadata
        )
        
        # Add processing time to metadata
        if api_response.metadata:
            api_response.metadata['api_processing_ms'] = (time.time() - start_time) * 1000
        
        # Determine HTTP status code based on result
        if response.result == ProposalResult.PERSISTED:
            status_code = 201
        elif response.result == ProposalResult.NOT_PERSISTED:
            status_code = 202
        elif response.result == ProposalResult.OVERRIDE:
            status_code = 201
        else:
            status_code = 200
        
        return JSONResponse(
            status_code=status_code,
            content=api_response.__dict__
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
    "/{hypothesis_id}",
    response_model=HypothesisResponse,
    responses={
        200: {"description": "Hypothesis retrieved successfully"},
        404: {"description": "Hypothesis not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_hypothesis(hypothesis_id: str):
    """
    Get a hypothesis by ID.
    
    Args:
        hypothesis_id: Hypothesis ID
        
    Returns:
        HypothesisResponse with hypothesis data
    """
    try:
        proposer = get_hypothesis_proposer()
        hypothesis = proposer.get_hypothesis(hypothesis_id)
        
        if not hypothesis:
            raise HTTPException(
                status_code=404,
                detail=f"Hypothesis {hypothesis_id} not found"
            )
        
        # Convert to API response
        response = HypothesisResponse(
            id=hypothesis_id,
            title=hypothesis.title,
            description=hypothesis.description,
            source_message_id=hypothesis.source_message_id,
            pareto_score=hypothesis.pareto_score,
            status=hypothesis.status.value,
            created_at=hypothesis.created_at.isoformat() if hypothesis.created_at else None,
            created_by=hypothesis.created_by,
            metadata=hypothesis.metadata
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get(
    "/",
    response_model=List[HypothesisResponse],
    responses={
        200: {"description": "Hypotheses retrieved successfully"},
        500: {"description": "Internal server error"}
    }
)
async def list_hypotheses(
    status: Optional[str] = None,
    limit: int = Field(100, ge=1, le=1000),
    offset: int = Field(0, ge=0)
):
    """
    List hypotheses with optional filtering.
    
    Args:
        status: Optional status filter
        limit: Maximum number of results
        offset: Number of results to skip
        
    Returns:
        List of HypothesisResponse objects
    """
    try:
        proposer = get_hypothesis_proposer()
        
        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = HypothesisStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}"
                )
        
        # Get hypotheses
        hypotheses = proposer.list_hypotheses(
            status=status_filter,
            limit=limit,
            offset=offset
        )
        
        # Convert to API responses
        responses = []
        for hypothesis in hypotheses:
            response = HypothesisResponse(
                id=f"hyp_{hypothesis.title[:10]}",  # Simplified ID for demo
                title=hypothesis.title,
                description=hypothesis.description,
                source_message_id=hypothesis.source_message_id,
                pareto_score=hypothesis.pareto_score,
                status=hypothesis.status.value,
                created_at=hypothesis.created_at.isoformat() if hypothesis.created_at else None,
                created_by=hypothesis.created_by,
                metadata=hypothesis.metadata
            )
            responses.append(response)
        
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get(
    "/stats",
    response_model=Dict[str, Any],
    responses={
        200: {"description": "Statistics retrieved successfully"},
        500: {"description": "Internal server error"}
    }
)
async def get_stats():
    """
    Get statistics about stored hypotheses.
    
    Returns:
        Dict with hypothesis statistics
    """
    try:
        proposer = get_hypothesis_proposer()
        stats = proposer.get_stats()
        
        # Add additional metadata
        stats['pareto_threshold'] = get_pareto_threshold()
        stats['feature_enabled'] = get_feature_flag('hypotheses.enabled')
        stats['timestamp'] = time.time()
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

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