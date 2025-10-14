# api/aura.py — Aura API endpoints

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

from core.aura.bridge import (
    get_aura_bridge,
    create_project_from_hypothesis,
    AuraProject,
    AuraTask,
    ProjectStatus,
    TaskStatus,
    TaskPriority,
    ProjectCreationResult
)
from core.hypotheses.propose import get_hypothesis_proposer, HypothesisStatus
from feature_flags import get_feature_flag

# Create router
router = APIRouter(prefix="/aura", tags=["aura"])

# Request/Response models
class ProposeProjectRequest(BaseModel):
    """Request model for project proposal."""
    hypothesis_id: str = Field(..., min_length=1, max_length=100)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)

class TaskResponse(BaseModel):
    """Response model for individual task."""
    id: str
    project_id: str
    title: str
    description: str
    status: str
    priority: str
    evidence_id: Optional[str] = None
    evidence_source: Optional[str] = None
    created_at: str
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ProjectResponse(BaseModel):
    """Response model for individual project."""
    id: str
    title: str
    description: str
    hypothesis_id: str
    status: str
    created_at: str
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ProposeProjectResponse(BaseModel):
    """Response model for project proposal."""
    project: ProjectResponse
    tasks: List[TaskResponse]
    hypothesis_used: Dict[str, Any]
    created_at: str
    metadata: Dict[str, Any]

class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

# Dependency functions
def get_user_id_from_request(request: Request) -> Optional[str]:
    """Extract user ID from request headers or context."""
    # In a real implementation, this would extract from JWT token or session
    return request.headers.get('X-User-ID')

# Endpoints
@router.post(
    "/projects/propose",
    response_model=ProposeProjectResponse,
    responses={
        201: {"description": "Project created successfully"},
        400: {"description": "Bad request", "model": ErrorResponse},
        404: {"description": "Hypothesis not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def propose_project(
    request: ProposeProjectRequest,
    http_request: Request,
    user_id: Optional[str] = Depends(get_user_id_from_request)
):
    """
    Create an Aura project from a hypothesis.
    
    Args:
        request: Project proposal request
        http_request: HTTP request object
        user_id: User ID for audit trail
        
    Returns:
        ProposeProjectResponse with project, tasks, and metadata
        
    Raises:
        HTTPException: 400 for validation errors, 404 for missing hypothesis
    """
    start_time = time.time()
    
    try:
        # Check if Aura feature is enabled
        if not get_feature_flag('aura.enabled'):
            raise HTTPException(
                status_code=404,
                detail="Aura feature is not enabled"
            )
        
        # Get hypothesis from hypotheses proposer
        hypothesis_proposer = get_hypothesis_proposer()
        hypothesis = hypothesis_proposer.get_hypothesis(request.hypothesis_id)
        
        if not hypothesis:
            raise HTTPException(
                status_code=404,
                detail=f"Hypothesis {request.hypothesis_id} not found"
            )
        
        # Validate hypothesis status
        if hypothesis.status not in [HypothesisStatus.PENDING, HypothesisStatus.APPROVED]:
            raise HTTPException(
                status_code=400,
                detail=f"Hypothesis status '{hypothesis.status.value}' is not valid for project creation. Must be 'pending' or 'approved'."
            )
        
        # Create project from hypothesis
        bridge = get_aura_bridge()
        result = bridge.create_project_from_hypothesis(
            hypothesis_id=request.hypothesis_id,
            hypothesis=hypothesis,
            title=request.title,
            description=request.description,
            created_by=user_id
        )
        
        # Convert to API response format
        project_response = ProjectResponse(
            id=result.project.id,
            title=result.project.title,
            description=result.project.description,
            hypothesis_id=result.project.hypothesis_id,
            status=result.project.status.value,
            created_at=result.project.created_at.isoformat(),
            created_by=result.project.created_by,
            metadata=result.project.metadata
        )
        
        tasks_response = []
        for task in result.tasks:
            task_response = TaskResponse(
                id=task.id,
                project_id=task.project_id,
                title=task.title,
                description=task.description,
                status=task.status.value,
                priority=task.priority.value,
                evidence_id=task.evidence_id,
                evidence_source=task.evidence_source,
                created_at=task.created_at.isoformat() if task.created_at else None,
                created_by=task.created_by,
                metadata=task.metadata
            )
            tasks_response.append(task_response)
        
        # Convert hypothesis to dict
        hypothesis_dict = {
            'id': request.hypothesis_id,
            'title': hypothesis.title,
            'description': hypothesis.description,
            'status': hypothesis.status.value,
            'pareto_score': hypothesis.pareto_score,
            'created_at': hypothesis.created_at.isoformat() if hypothesis.created_at else None,
            'created_by': hypothesis.created_by
        }
        
        # Add processing time to metadata
        result.metadata['api_processing_ms'] = (time.time() - start_time) * 1000
        
        response = ProposeProjectResponse(
            project=project_response,
            tasks=tasks_response,
            hypothesis_used=hypothesis_dict,
            created_at=result.created_at.isoformat(),
            metadata=result.metadata
        )
        
        return JSONResponse(
            status_code=201,
            content=response.__dict__
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
    "/projects/{project_id}",
    response_model=ProjectResponse,
    responses={
        200: {"description": "Project retrieved successfully"},
        404: {"description": "Project not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_project(project_id: str):
    """
    Get a project by ID.
    
    Args:
        project_id: Project ID
        
    Returns:
        ProjectResponse with project data
    """
    try:
        bridge = get_aura_bridge()
        project = bridge.get_project(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        response = ProjectResponse(
            id=project.id,
            title=project.title,
            description=project.description,
            hypothesis_id=project.hypothesis_id,
            status=project.status.value,
            created_at=project.created_at.isoformat(),
            created_by=project.created_by,
            metadata=project.metadata
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
    "/projects/{project_id}/tasks",
    response_model=List[TaskResponse],
    responses={
        200: {"description": "Project tasks retrieved successfully"},
        404: {"description": "Project not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_project_tasks(project_id: str):
    """
    Get all tasks for a project.
    
    Args:
        project_id: Project ID
        
    Returns:
        List of TaskResponse objects
    """
    try:
        bridge = get_aura_bridge()
        
        # Check if project exists
        project = bridge.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get tasks
        tasks = bridge.get_project_tasks(project_id)
        
        # Convert to API response format
        tasks_response = []
        for task in tasks:
            task_response = TaskResponse(
                id=task.id,
                project_id=task.project_id,
                title=task.title,
                description=task.description,
                status=task.status.value,
                priority=task.priority.value,
                evidence_id=task.evidence_id,
                evidence_source=task.evidence_source,
                created_at=task.created_at.isoformat() if task.created_at else None,
                created_by=task.created_by,
                metadata=task.metadata
            )
            tasks_response.append(task_response)
        
        return tasks_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get(
    "/projects/",
    response_model=List[ProjectResponse],
    responses={
        200: {"description": "Projects retrieved successfully"},
        500: {"description": "Internal server error"}
    }
)
async def list_projects(
    status: Optional[str] = None,
    limit: int = Field(100, ge=1, le=1000),
    offset: int = Field(0, ge=0)
):
    """
    List projects with optional filtering.
    
    Args:
        status: Optional status filter
        limit: Maximum number of results
        offset: Number of results to skip
        
    Returns:
        List of ProjectResponse objects
    """
    try:
        bridge = get_aura_bridge()
        
        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = ProjectStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}"
                )
        
        # Get projects
        projects = bridge.list_projects(
            status=status_filter,
            limit=limit,
            offset=offset
        )
        
        # Convert to API responses
        projects_response = []
        for project in projects:
            project_response = ProjectResponse(
                id=project.id,
                title=project.title,
                description=project.description,
                hypothesis_id=project.hypothesis_id,
                status=project.status.value,
                created_at=project.created_at.isoformat(),
                created_by=project.created_by,
                metadata=project.metadata
            )
            projects_response.append(project_response)
        
        return projects_response
        
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
    Get statistics about projects and tasks.
    
    Returns:
        Dict with project and task statistics
    """
    try:
        bridge = get_aura_bridge()
        stats = bridge.get_stats()
        
        # Add additional metadata
        stats['feature_enabled'] = get_feature_flag('aura.enabled')
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