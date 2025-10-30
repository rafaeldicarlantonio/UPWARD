"""
Role-Based Access Control (RBAC) module.

Provides role definitions, capability constants, and authorization logic.
"""

from .roles import (
    ROLE_GENERAL,
    ROLE_PRO,
    ROLE_SCHOLARS,
    ROLE_ANALYTICS,
    ROLE_OPS,
    ALL_ROLES,
    ROLE_CAPABILITIES,
)

from .capabilities import (
    # Capability constants
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_PROPOSE_AURA,
    CAP_WRITE_GRAPH,
    CAP_WRITE_CONTRADICTIONS,
    CAP_MANAGE_ROLES,
    CAP_VIEW_DEBUG,
    ALL_CAPABILITIES,
    # Functions
    has_capability,
    get_role_capabilities,
    validate_role,
)

__all__ = [
    # Roles
    "ROLE_GENERAL",
    "ROLE_PRO",
    "ROLE_SCHOLARS",
    "ROLE_ANALYTICS",
    "ROLE_OPS",
    "ALL_ROLES",
    "ROLE_CAPABILITIES",
    # Capabilities
    "CAP_READ_PUBLIC",
    "CAP_READ_LEDGER_FULL",
    "CAP_PROPOSE_HYPOTHESIS",
    "CAP_PROPOSE_AURA",
    "CAP_WRITE_GRAPH",
    "CAP_WRITE_CONTRADICTIONS",
    "CAP_MANAGE_ROLES",
    "CAP_VIEW_DEBUG",
    "ALL_CAPABILITIES",
    # Functions
    "has_capability",
    "get_role_capabilities",
    "validate_role",
]
