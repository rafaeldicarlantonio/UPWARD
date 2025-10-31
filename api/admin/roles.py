"""
Role management API endpoints.

Admin-only endpoints for managing user roles, protected by MANAGE_ROLES capability.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field, validator

from api.guards import require
from api.middleware.roles import get_current_user
from core.rbac import ALL_ROLES, validate_role
from adapters.db import DatabaseAdapter


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/roles", tags=["admin", "roles"])


# ============================================================================
# Request/Response Models
# ============================================================================

class RoleAssignmentRequest(BaseModel):
    """Request to assign a role to a user."""
    user_id: str = Field(..., description="User UUID to assign role to")
    role_key: str = Field(..., description="Role key to assign (e.g., 'pro', 'analytics')")
    
    @validator('role_key')
    def validate_role_key(cls, v):
        """Ensure role key is valid."""
        if not validate_role(v):
            raise ValueError(f"Invalid role key: {v}. Must be one of: {', '.join(ALL_ROLES)}")
        return v.lower()
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "role_key": "pro"
            }
        }


class RoleAssignmentResponse(BaseModel):
    """Response after role assignment."""
    user_id: str
    role_key: str
    assigned: bool
    message: str
    audit_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "role_key": "pro",
                "assigned": True,
                "message": "Role 'pro' assigned to user",
                "audit_id": "audit_123"
            }
        }


class UserRolesResponse(BaseModel):
    """Response with user's roles."""
    user_id: str
    roles: List[str]
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "roles": ["general", "pro"]
            }
        }


class RoleRevocationRequest(BaseModel):
    """Request to revoke a role from a user."""
    user_id: str = Field(..., description="User UUID to revoke role from")
    role_key: str = Field(..., description="Role key to revoke")
    
    @validator('role_key')
    def validate_role_key(cls, v):
        """Ensure role key is valid."""
        if not validate_role(v):
            raise ValueError(f"Invalid role key: {v}")
        return v.lower()


class RoleRevocationResponse(BaseModel):
    """Response after role revocation."""
    user_id: str
    role_key: str
    revoked: bool
    message: str
    audit_id: Optional[str] = None


# ============================================================================
# Database Operations
# ============================================================================

class RoleManager:
    """Manages role assignments and persists to database."""
    
    def __init__(self, db: DatabaseAdapter):
        self.db = db
    
    def get_user_roles(self, user_id: str) -> List[str]:
        """
        Get all roles for a user.
        
        Args:
            user_id: User UUID
            
        Returns:
            List of role keys
        """
        try:
            # Query user_roles table
            result = self.db.execute(
                """
                SELECT role_key 
                FROM user_roles 
                WHERE user_id = %s AND deleted_at IS NULL
                ORDER BY created_at
                """,
                (user_id,)
            )
            
            roles = [row['role_key'] for row in result]
            
            # Always include general if no roles
            if not roles:
                roles = ['general']
            
            return roles
            
        except Exception as e:
            logger.error(f"Error getting roles for user {user_id}: {e}")
            return ['general']  # Safe default
    
    def assign_role(
        self,
        user_id: str,
        role_key: str,
        assigned_by: str,
        audit_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Assign a role to a user (idempotent).
        
        Args:
            user_id: User UUID to assign role to
            role_key: Role key to assign
            assigned_by: User ID of admin performing assignment
            audit_metadata: Additional audit metadata
            
        Returns:
            Result dict with assignment info and audit ID
        """
        role_key = role_key.lower()
        
        # Validate role
        if not validate_role(role_key):
            raise ValueError(f"Invalid role: {role_key}")
        
        try:
            # Check if role already assigned
            existing = self.db.execute(
                """
                SELECT id, deleted_at 
                FROM user_roles 
                WHERE user_id = %s AND role_key = %s
                """,
                (user_id, role_key)
            )
            
            if existing and existing[0].get('deleted_at') is None:
                # Already assigned - idempotent
                logger.info(f"Role {role_key} already assigned to user {user_id}")
                
                # Still log audit for idempotent call
                audit_id = self._log_audit(
                    action="role_assign_idempotent",
                    user_id=user_id,
                    role_key=role_key,
                    performed_by=assigned_by,
                    metadata=audit_metadata,
                    result="already_assigned"
                )
                
                return {
                    "assigned": False,
                    "message": f"Role '{role_key}' already assigned",
                    "audit_id": audit_id,
                    "idempotent": True
                }
            
            elif existing and existing[0].get('deleted_at') is not None:
                # Previously deleted - restore
                self.db.execute(
                    """
                    UPDATE user_roles 
                    SET deleted_at = NULL, updated_at = %s
                    WHERE user_id = %s AND role_key = %s
                    """,
                    (datetime.now(timezone.utc), user_id, role_key)
                )
                
                audit_id = self._log_audit(
                    action="role_assign_restore",
                    user_id=user_id,
                    role_key=role_key,
                    performed_by=assigned_by,
                    metadata=audit_metadata,
                    result="restored"
                )
                
                logger.info(f"Restored role {role_key} for user {user_id}")
                
                return {
                    "assigned": True,
                    "message": f"Role '{role_key}' restored",
                    "audit_id": audit_id,
                    "idempotent": False
                }
            
            else:
                # New assignment
                self.db.execute(
                    """
                    INSERT INTO user_roles (user_id, role_key, created_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, role_key, datetime.now(timezone.utc), datetime.now(timezone.utc))
                )
                
                audit_id = self._log_audit(
                    action="role_assign",
                    user_id=user_id,
                    role_key=role_key,
                    performed_by=assigned_by,
                    metadata=audit_metadata,
                    result="assigned"
                )
                
                logger.info(f"Assigned role {role_key} to user {user_id} by {assigned_by}")
                
                return {
                    "assigned": True,
                    "message": f"Role '{role_key}' assigned successfully",
                    "audit_id": audit_id,
                    "idempotent": False
                }
        
        except Exception as e:
            logger.error(f"Error assigning role {role_key} to user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to assign role: {str(e)}"
            )
    
    def revoke_role(
        self,
        user_id: str,
        role_key: str,
        revoked_by: str,
        audit_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Revoke a role from a user.
        
        Args:
            user_id: User UUID to revoke role from
            role_key: Role key to revoke
            revoked_by: User ID of admin performing revocation
            audit_metadata: Additional audit metadata
            
        Returns:
            Result dict with revocation info and audit ID
        """
        role_key = role_key.lower()
        
        # Prevent revoking general role
        if role_key == 'general':
            raise ValueError("Cannot revoke 'general' role - all users must have it")
        
        try:
            # Check if role exists and not already deleted
            existing = self.db.execute(
                """
                SELECT id, deleted_at 
                FROM user_roles 
                WHERE user_id = %s AND role_key = %s
                """,
                (user_id, role_key)
            )
            
            if not existing or existing[0].get('deleted_at') is not None:
                # Not assigned or already revoked - idempotent
                audit_id = self._log_audit(
                    action="role_revoke_idempotent",
                    user_id=user_id,
                    role_key=role_key,
                    performed_by=revoked_by,
                    metadata=audit_metadata,
                    result="not_assigned"
                )
                
                return {
                    "revoked": False,
                    "message": f"Role '{role_key}' not assigned to user",
                    "audit_id": audit_id,
                    "idempotent": True
                }
            
            # Soft delete the role
            self.db.execute(
                """
                UPDATE user_roles 
                SET deleted_at = %s, updated_at = %s
                WHERE user_id = %s AND role_key = %s
                """,
                (datetime.now(timezone.utc), datetime.now(timezone.utc), user_id, role_key)
            )
            
            audit_id = self._log_audit(
                action="role_revoke",
                user_id=user_id,
                role_key=role_key,
                performed_by=revoked_by,
                metadata=audit_metadata,
                result="revoked"
            )
            
            logger.info(f"Revoked role {role_key} from user {user_id} by {revoked_by}")
            
            return {
                "revoked": True,
                "message": f"Role '{role_key}' revoked successfully",
                "audit_id": audit_id,
                "idempotent": False
            }
        
        except Exception as e:
            logger.error(f"Error revoking role {role_key} from user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to revoke role: {str(e)}"
            )
    
    def _log_audit(
        self,
        action: str,
        user_id: str,
        role_key: str,
        performed_by: str,
        metadata: Optional[Dict[str, Any]],
        result: str
    ) -> str:
        """
        Log audit entry for role management action.
        
        Args:
            action: Action type (e.g., 'role_assign', 'role_revoke')
            user_id: Target user ID
            role_key: Role being managed
            performed_by: Admin user ID
            metadata: Additional metadata
            result: Result of action
            
        Returns:
            Audit entry ID
        """
        try:
            audit_entry = {
                "action": action,
                "target_user_id": user_id,
                "role_key": role_key,
                "performed_by": performed_by,
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {}
            }
            
            # Insert into audit log
            result = self.db.execute(
                """
                INSERT INTO role_audit_log 
                (action, target_user_id, role_key, performed_by, result, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    action,
                    user_id,
                    role_key,
                    performed_by,
                    result,
                    audit_entry,
                    datetime.now(timezone.utc)
                )
            )
            
            audit_id = result[0]['id'] if result else None
            
            logger.info(
                f"Audit log: {action} role={role_key} user={user_id} "
                f"by={performed_by} result={result} audit_id={audit_id}"
            )
            
            return audit_id
        
        except Exception as e:
            # Log error but don't fail the operation
            logger.error(f"Failed to log audit entry: {e}")
            return None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/assign", response_model=RoleAssignmentResponse)
@require("MANAGE_ROLES")
async def assign_role(request: Request, assignment: RoleAssignmentRequest):
    """
    Assign a role to a user.
    
    **Required Capability**: MANAGE_ROLES (ops role)
    
    This operation is idempotent - assigning the same role twice has no effect
    but still returns success.
    
    **Example**:
    ```
    POST /admin/roles/assign
    {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "role_key": "pro"
    }
    ```
    """
    # Get current admin user
    ctx = get_current_user(request)
    
    # Get database adapter
    db = DatabaseAdapter()
    manager = RoleManager(db)
    
    # Prepare audit metadata
    audit_metadata = {
        "admin_roles": ctx.roles,
        "admin_email": ctx.email,
        "request_ip": request.client.host if request.client else None,
    }
    
    # Assign role
    result = manager.assign_role(
        user_id=assignment.user_id,
        role_key=assignment.role_key,
        assigned_by=ctx.user_id,
        audit_metadata=audit_metadata
    )
    
    return RoleAssignmentResponse(
        user_id=assignment.user_id,
        role_key=assignment.role_key,
        assigned=result["assigned"],
        message=result["message"],
        audit_id=result.get("audit_id")
    )


@router.get("/{user_id}", response_model=UserRolesResponse)
@require("MANAGE_ROLES")
async def get_user_roles(request: Request, user_id: str):
    """
    Get all roles for a user.
    
    **Required Capability**: MANAGE_ROLES (ops role)
    
    **Example**:
    ```
    GET /admin/roles/123e4567-e89b-12d3-a456-426614174000
    ```
    """
    # Get database adapter
    db = DatabaseAdapter()
    manager = RoleManager(db)
    
    # Get roles
    roles = manager.get_user_roles(user_id)
    
    return UserRolesResponse(
        user_id=user_id,
        roles=roles
    )


@router.post("/revoke", response_model=RoleRevocationResponse)
@require("MANAGE_ROLES")
async def revoke_role(request: Request, revocation: RoleRevocationRequest):
    """
    Revoke a role from a user.
    
    **Required Capability**: MANAGE_ROLES (ops role)
    
    This operation is idempotent - revoking a role that's not assigned returns
    success.
    
    **Note**: Cannot revoke the 'general' role - all users must have it.
    
    **Example**:
    ```
    POST /admin/roles/revoke
    {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "role_key": "pro"
    }
    ```
    """
    # Get current admin user
    ctx = get_current_user(request)
    
    # Get database adapter
    db = DatabaseAdapter()
    manager = RoleManager(db)
    
    # Prepare audit metadata
    audit_metadata = {
        "admin_roles": ctx.roles,
        "admin_email": ctx.email,
        "request_ip": request.client.host if request.client else None,
    }
    
    # Revoke role
    result = manager.revoke_role(
        user_id=revocation.user_id,
        role_key=revocation.role_key,
        revoked_by=ctx.user_id,
        audit_metadata=audit_metadata
    )
    
    return RoleRevocationResponse(
        user_id=revocation.user_id,
        role_key=revocation.role_key,
        revoked=result["revoked"],
        message=result["message"],
        audit_id=result.get("audit_id")
    )


@router.get("/audit/{user_id}")
@require("MANAGE_ROLES")
async def get_audit_log(request: Request, user_id: str, limit: int = 50):
    """
    Get audit log for role changes for a user.
    
    **Required Capability**: MANAGE_ROLES (ops role)
    
    **Example**:
    ```
    GET /admin/roles/audit/123e4567-e89b-12d3-a456-426614174000?limit=20
    ```
    """
    db = DatabaseAdapter()
    
    try:
        entries = db.execute(
            """
            SELECT id, action, role_key, performed_by, result, metadata, created_at
            FROM role_audit_log
            WHERE target_user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        
        return {
            "user_id": user_id,
            "audit_entries": entries,
            "count": len(entries)
        }
    
    except Exception as e:
        logger.error(f"Error retrieving audit log for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit log"
        )
