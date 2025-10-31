"""
Role definitions and role-to-capability mappings.

Defines all system roles and their associated capabilities.
"""

from typing import Dict, Set
from .capabilities import (
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_PROPOSE_AURA,
    CAP_WRITE_GRAPH,
    CAP_WRITE_CONTRADICTIONS,
    CAP_MANAGE_ROLES,
    CAP_VIEW_DEBUG,
)


# ============================================================================
# Role Constants
# ============================================================================

ROLE_GENERAL = "general"
"""Basic role with minimal permissions - read-only access to public content."""

ROLE_PRO = "pro"
"""Professional role with full read access and proposal capabilities."""

ROLE_SCHOLARS = "scholars"
"""Academic role with full read and proposal capabilities but no write access."""

ROLE_ANALYTICS = "analytics"
"""Analytics role with read, propose, and write capabilities."""

ROLE_OPS = "ops"
"""Operations role with read access and debug capabilities."""

# Complete set of all roles
ALL_ROLES = frozenset({
    ROLE_GENERAL,
    ROLE_PRO,
    ROLE_SCHOLARS,
    ROLE_ANALYTICS,
    ROLE_OPS,
})


# ============================================================================
# Role-to-Capability Mapping
# ============================================================================

ROLE_CAPABILITIES: Dict[str, Set[str]] = {
    # General: Basic read-only access to public content
    ROLE_GENERAL: {
        CAP_READ_PUBLIC,
    },
    
    # Pro: Full read access + proposal capabilities
    # Can read everything, propose hypotheses and auras, but no direct writes
    ROLE_PRO: {
        CAP_READ_PUBLIC,
        CAP_READ_LEDGER_FULL,
        CAP_PROPOSE_HYPOTHESIS,
        CAP_PROPOSE_AURA,
    },
    
    # Scholars: Same as Pro but explicitly no write capabilities
    # "Suggest-only" role - can read and propose but not modify graph/contradictions
    ROLE_SCHOLARS: {
        CAP_READ_PUBLIC,
        CAP_READ_LEDGER_FULL,
        CAP_PROPOSE_HYPOTHESIS,
        CAP_PROPOSE_AURA,
        # Explicitly NO: CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS
    },
    
    # Analytics: Full read + propose + write capabilities
    # Can modify the knowledge graph and contradiction data
    ROLE_ANALYTICS: {
        CAP_READ_PUBLIC,
        CAP_READ_LEDGER_FULL,
        CAP_PROPOSE_HYPOTHESIS,
        CAP_PROPOSE_AURA,
        CAP_WRITE_GRAPH,
        CAP_WRITE_CONTRADICTIONS,
    },
    
    # Ops: Read access + debug/monitoring + role management capabilities
    # For operations and monitoring, no proposal or write access
    ROLE_OPS: {
        CAP_READ_PUBLIC,
        CAP_READ_LEDGER_FULL,
        CAP_VIEW_DEBUG,
        CAP_MANAGE_ROLES,
    },
}


# ============================================================================
# Role Metadata
# ============================================================================

ROLE_DESCRIPTIONS: Dict[str, str] = {
    ROLE_GENERAL: "Basic role with read-only access to public content",
    ROLE_PRO: "Professional role with full read access and proposal capabilities",
    ROLE_SCHOLARS: "Academic role with read and proposal access but no write permissions",
    ROLE_ANALYTICS: "Analytics role with read, propose, and write capabilities",
    ROLE_OPS: "Operations role with read access and debug/monitoring capabilities",
}


def get_role_description(role: str) -> str:
    """
    Get human-readable description of a role.
    
    Args:
        role: Role name
        
    Returns:
        Role description or empty string if role is unknown
    """
    return ROLE_DESCRIPTIONS.get(role.lower(), "")


def list_all_roles() -> Dict[str, Dict[str, any]]:
    """
    List all roles with their capabilities and descriptions.
    
    Returns:
        Dictionary mapping role names to their metadata
    """
    return {
        role: {
            "description": ROLE_DESCRIPTIONS.get(role, ""),
            "capabilities": sorted(list(ROLE_CAPABILITIES.get(role, set()))),
        }
        for role in ALL_ROLES
    }
