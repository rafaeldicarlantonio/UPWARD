"""
Capability constants and authorization functions.

Defines all system capabilities and provides functions to check
if a role has a specific capability.
"""

from typing import Set, List, Optional
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Capability Constants
# ============================================================================

CAP_READ_PUBLIC = "READ_PUBLIC"
"""Read publicly available content and memories."""

CAP_READ_LEDGER_FULL = "READ_LEDGER_FULL"
"""Read full ledger data including internal metadata."""

CAP_PROPOSE_HYPOTHESIS = "PROPOSE_HYPOTHESIS"
"""Propose new hypotheses for system consideration."""

CAP_PROPOSE_AURA = "PROPOSE_AURA"
"""Propose new aura entries."""

CAP_WRITE_GRAPH = "WRITE_GRAPH"
"""Write to the knowledge graph (entities, edges)."""

CAP_WRITE_CONTRADICTIONS = "WRITE_CONTRADICTIONS"
"""Write contradiction data to memories."""

CAP_MANAGE_ROLES = "MANAGE_ROLES"
"""Manage user roles and permissions."""

CAP_VIEW_DEBUG = "VIEW_DEBUG"
"""Access debug endpoints and metrics."""

# Complete set of all capabilities
ALL_CAPABILITIES = frozenset({
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_PROPOSE_AURA,
    CAP_WRITE_GRAPH,
    CAP_WRITE_CONTRADICTIONS,
    CAP_MANAGE_ROLES,
    CAP_VIEW_DEBUG,
})


# ============================================================================
# Authorization Functions
# ============================================================================

def has_capability(role: str, capability: str) -> bool:
    """
    Check if a role has a specific capability.
    
    Args:
        role: Role name (e.g., "general", "pro", "scholars", "analytics", "ops")
        capability: Capability constant (e.g., CAP_READ_PUBLIC)
        
    Returns:
        True if the role has the capability, False otherwise
        
    Examples:
        >>> has_capability("general", CAP_READ_PUBLIC)
        True
        >>> has_capability("general", CAP_WRITE_GRAPH)
        False
        >>> has_capability("pro", CAP_PROPOSE_HYPOTHESIS)
        True
        >>> has_capability("ops", CAP_VIEW_DEBUG)
        True
    """
    # Import here to avoid circular dependency
    from .roles import ROLE_CAPABILITIES
    
    if not role:
        logger.warning("has_capability called with empty role")
        return False
    
    if capability not in ALL_CAPABILITIES:
        logger.warning(f"Unknown capability: {capability}")
        return False
    
    # Normalize role name to lowercase
    normalized_role = role.lower()
    
    if normalized_role not in ROLE_CAPABILITIES:
        logger.warning(f"Unknown role: {role}")
        return False
    
    return capability in ROLE_CAPABILITIES[normalized_role]


def get_role_capabilities(role: str) -> Set[str]:
    """
    Get all capabilities for a role.
    
    Args:
        role: Role name
        
    Returns:
        Set of capability strings for the role, or empty set if role is unknown
        
    Examples:
        >>> sorted(get_role_capabilities("general"))
        ['READ_PUBLIC']
        >>> sorted(get_role_capabilities("ops"))
        ['READ_LEDGER_FULL', 'READ_PUBLIC', 'VIEW_DEBUG']
    """
    from .roles import ROLE_CAPABILITIES
    
    if not role:
        return set()
    
    normalized_role = role.lower()
    return set(ROLE_CAPABILITIES.get(normalized_role, set()))


def validate_role(role: str) -> bool:
    """
    Check if a role is valid.
    
    Args:
        role: Role name to validate
        
    Returns:
        True if the role exists in the system, False otherwise
        
    Examples:
        >>> validate_role("general")
        True
        >>> validate_role("unknown")
        False
        >>> validate_role("")
        False
    """
    from .roles import ALL_ROLES
    
    if not role:
        return False
    
    return role.lower() in ALL_ROLES


def has_any_capability(role: str, capabilities: List[str]) -> bool:
    """
    Check if a role has any of the specified capabilities.
    
    Args:
        role: Role name
        capabilities: List of capability constants
        
    Returns:
        True if the role has at least one of the capabilities, False otherwise
        
    Examples:
        >>> has_any_capability("general", [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])
        True
        >>> has_any_capability("general", [CAP_WRITE_GRAPH, CAP_MANAGE_ROLES])
        False
    """
    return any(has_capability(role, cap) for cap in capabilities)


def has_all_capabilities(role: str, capabilities: List[str]) -> bool:
    """
    Check if a role has all of the specified capabilities.
    
    Args:
        role: Role name
        capabilities: List of capability constants
        
    Returns:
        True if the role has all capabilities, False otherwise
        
    Examples:
        >>> has_all_capabilities("pro", [CAP_READ_PUBLIC, CAP_READ_LEDGER_FULL])
        True
        >>> has_all_capabilities("general", [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])
        False
    """
    return all(has_capability(role, cap) for cap in capabilities)


def get_missing_capabilities(role: str, required_capabilities: List[str]) -> Set[str]:
    """
    Get capabilities that a role is missing from a required set.
    
    Args:
        role: Role name
        required_capabilities: List of required capability constants
        
    Returns:
        Set of missing capabilities
        
    Examples:
        >>> sorted(get_missing_capabilities("general", [CAP_READ_PUBLIC, CAP_WRITE_GRAPH]))
        ['WRITE_GRAPH']
        >>> get_missing_capabilities("analytics", [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])
        set()
    """
    return {cap for cap in required_capabilities if not has_capability(role, cap)}
