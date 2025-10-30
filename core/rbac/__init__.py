"""
Role-Based Access Control (RBAC) module.

Provides role definitions, capability constants, authorization logic,
and role resolution from JWT/API keys.
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

from .resolve import (
    # Data classes
    ResolvedUser,
    RoleResolver,
    # Functions
    configure_resolver,
    get_resolver,
    reset_resolver,
)

from .levels import (
    # Level constants
    ROLE_VISIBILITY_LEVELS,
    DEFAULT_VISIBILITY_LEVEL,
    TRACE_SUMMARY_MAX_LINES,
    # Level functions
    get_role_level,
    get_max_role_level,
    can_view_memory,
    filter_memories_by_level,
    process_trace_summary,
    get_level_description,
    get_roles_with_level,
    get_roles_with_min_level,
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
    # Capability Functions
    "has_capability",
    "get_role_capabilities",
    "validate_role",
    # Resolver Classes
    "ResolvedUser",
    "RoleResolver",
    # Resolver Functions
    "configure_resolver",
    "get_resolver",
    "reset_resolver",
    # Level Constants
    "ROLE_VISIBILITY_LEVELS",
    "DEFAULT_VISIBILITY_LEVEL",
    "TRACE_SUMMARY_MAX_LINES",
    # Level Functions
    "get_role_level",
    "get_max_role_level",
    "can_view_memory",
    "filter_memories_by_level",
    "process_trace_summary",
    "get_level_description",
    "get_roles_with_level",
    "get_roles_with_min_level",
]
