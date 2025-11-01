"""
Role visibility levels for memory retrieval filtering.

Maps roles to numeric visibility levels and provides functions
to filter memories based on caller's access level.
"""

import logging
from typing import List, Dict, Any, Optional

from .roles import ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS

logger = logging.getLogger(__name__)


# ============================================================================
# Visibility Levels
# ============================================================================

# Role to visibility level mapping
# Higher levels can see memories from lower levels
ROLE_VISIBILITY_LEVELS = {
    ROLE_GENERAL: 0,      # Lowest - can only see level 0 memories
    ROLE_PRO: 1,          # Can see level 0 and 1
    ROLE_SCHOLARS: 1,     # Can see level 0 and 1
    ROLE_ANALYTICS: 2,    # Can see level 0, 1, and 2
    ROLE_OPS: 2,          # Can see level 0, 1, and 2
}

# Default level for unknown roles
DEFAULT_VISIBILITY_LEVEL = 0

# Trace summary configuration by level
TRACE_SUMMARY_MAX_LINES = {
    0: 4,    # General - cap at 4 lines
    1: None, # Pro/Scholars - full summary
    2: None, # Analytics/Ops - full summary
}


# ============================================================================
# Level Functions
# ============================================================================

def get_role_level(role: str) -> int:
    """
    Get visibility level for a role.
    
    Args:
        role: Role name (case-insensitive)
        
    Returns:
        Visibility level (0-2)
        
    Examples:
        >>> get_role_level("general")
        0
        >>> get_role_level("pro")
        1
        >>> get_role_level("analytics")
        2
    """
    if not role:
        return DEFAULT_VISIBILITY_LEVEL
    
    normalized_role = role.lower()
    return ROLE_VISIBILITY_LEVELS.get(normalized_role, DEFAULT_VISIBILITY_LEVEL)


def get_max_role_level(roles: List[str]) -> int:
    """
    Get maximum visibility level from a list of roles.
    
    User can see up to the highest level of any of their roles.
    
    Args:
        roles: List of role names
        
    Returns:
        Maximum visibility level
        
    Examples:
        >>> get_max_role_level(["general"])
        0
        >>> get_max_role_level(["general", "pro"])
        1
        >>> get_max_role_level(["pro", "analytics"])
        2
    """
    if not roles:
        return DEFAULT_VISIBILITY_LEVEL
    
    return max(get_role_level(role) for role in roles)


def can_view_memory(caller_roles: List[str], memory_level: int) -> bool:
    """
    Check if caller can view a memory based on its visibility level.
    
    Args:
        caller_roles: Caller's roles
        memory_level: Memory's role_view_level
        
    Returns:
        True if caller can view memory, False otherwise
        
    Examples:
        >>> can_view_memory(["general"], 0)
        True
        >>> can_view_memory(["general"], 1)
        False
        >>> can_view_memory(["pro"], 1)
        True
        >>> can_view_memory(["analytics"], 0)
        True
    """
    caller_level = get_max_role_level(caller_roles)
    return memory_level <= caller_level


def filter_memories_by_level(
    memories: List[Dict[str, Any]],
    caller_roles: List[str],
    level_field: str = "role_view_level"
) -> List[Dict[str, Any]]:
    """
    Filter memories by caller's visibility level.
    
    Only returns memories where role_view_level <= caller's max level.
    
    Args:
        memories: List of memory dictionaries
        caller_roles: Caller's roles
        level_field: Field name for memory visibility level
        
    Returns:
        Filtered list of memories
        
    Examples:
        >>> memories = [
        ...     {"id": "m1", "role_view_level": 0},
        ...     {"id": "m2", "role_view_level": 1},
        ...     {"id": "m3", "role_view_level": 2},
        ... ]
        >>> filtered = filter_memories_by_level(memories, ["general"])
        >>> len(filtered)
        1
        >>> filtered[0]["id"]
        'm1'
    """
    caller_level = get_max_role_level(caller_roles)
    
    filtered = []
    filtered_count = 0
    
    for memory in memories:
        memory_level = memory.get(level_field, 0)
        
        if memory_level <= caller_level:
            filtered.append(memory)
        else:
            filtered_count += 1
    
    if filtered_count > 0:
        logger.debug(
            f"Filtered {filtered_count} memories above caller level "
            f"(caller_level={caller_level}, roles={caller_roles})"
        )
    
    return filtered


def process_trace_summary(
    trace_summary: Optional[str],
    caller_roles: List[str],
    strip_provenance: bool = True
) -> Optional[str]:
    """
    Process trace summary based on caller's visibility level.
    
    For level 0 (general):
    - Cap to max 4 lines
    - Strip sensitive provenance if requested
    
    For level 1+ (pro, scholars, analytics, ops):
    - Return full summary
    
    Args:
        trace_summary: Original trace summary text
        caller_roles: Caller's roles
        strip_provenance: Whether to strip provenance for low-level users
        
    Returns:
        Processed trace summary
        
    Examples:
        >>> summary = "line1\\nline2\\nline3\\nline4\\nline5\\nline6"
        >>> processed = process_trace_summary(summary, ["general"])
        >>> len(processed.split("\\n"))
        4
        >>> processed = process_trace_summary(summary, ["pro"])
        >>> len(processed.split("\\n"))
        6
    """
    if not trace_summary:
        return trace_summary
    
    caller_level = get_max_role_level(caller_roles)
    max_lines = TRACE_SUMMARY_MAX_LINES.get(caller_level)
    
    # Full summary for higher levels
    if max_lines is None:
        return trace_summary
    
    # Cap to max lines for lower levels
    lines = trace_summary.split('\n')
    
    if len(lines) <= max_lines:
        processed = trace_summary
    else:
        processed = '\n'.join(lines[:max_lines])
        processed += f"\n... ({len(lines) - max_lines} more lines)"
    
    # Strip sensitive provenance for level 0
    if caller_level == 0 and strip_provenance:
        processed = strip_sensitive_provenance(processed)
    
    return processed


def strip_sensitive_provenance(text: str) -> str:
    """
    Strip sensitive provenance information from text.
    
    Removes patterns that might leak internal information:
    - Internal IDs (uuid format)
    - Database references
    - System paths
    
    Args:
        text: Text to process
        
    Returns:
        Text with sensitive information removed
    """
    import re
    
    # Remove UUID patterns
    text = re.sub(
        r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
        '[ID]',
        text,
        flags=re.IGNORECASE
    )
    
    # Remove common internal markers
    sensitive_patterns = [
        (r'\[internal\]', ''),
        (r'\[system\]', ''),
        (r'db\.', ''),
        (r'supabase\.', ''),
    ]
    
    for pattern, replacement in sensitive_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text.strip()


def get_level_description(level: int) -> str:
    """
    Get human-readable description of a visibility level.
    
    Args:
        level: Visibility level (0-2)
        
    Returns:
        Description string
    """
    descriptions = {
        0: "Public (general access)",
        1: "Professional (pro/scholars access)",
        2: "Internal (analytics/ops access)",
    }
    return descriptions.get(level, f"Level {level}")


def get_roles_with_level(level: int) -> List[str]:
    """
    Get all roles that have a specific visibility level.
    
    Args:
        level: Visibility level
        
    Returns:
        List of role names with that level
        
    Examples:
        >>> get_roles_with_level(0)
        ['general']
        >>> sorted(get_roles_with_level(1))
        ['pro', 'scholars']
    """
    return [
        role for role, role_level in ROLE_VISIBILITY_LEVELS.items()
        if role_level == level
    ]


def get_roles_with_min_level(min_level: int) -> List[str]:
    """
    Get all roles that have at least the specified visibility level.
    
    Args:
        min_level: Minimum visibility level
        
    Returns:
        List of role names with level >= min_level
        
    Examples:
        >>> sorted(get_roles_with_min_level(1))
        ['analytics', 'ops', 'pro', 'scholars']
        >>> sorted(get_roles_with_min_level(2))
        ['analytics', 'ops']
    """
    return [
        role for role, role_level in ROLE_VISIBILITY_LEVELS.items()
        if role_level >= min_level
    ]
