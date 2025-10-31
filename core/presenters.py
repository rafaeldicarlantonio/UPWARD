"""
Role-aware data presentation and redaction.

Redacts sensitive information from API responses based on user roles.
"""

from typing import Any, Dict, List, Optional, Union
import re
from copy import deepcopy

from core.rbac import ROLE_GENERAL
from core.rbac.levels import get_max_role_level, ROLE_VISIBILITY_LEVELS


# Patterns to redact from provenance/ledger data
SENSITIVE_PATTERNS = [
    r'id:[a-f0-9-]+',  # Database IDs
    r'uuid:[a-f0-9-]+',  # UUIDs
    r'ref:[a-zA-Z0-9_-]+',  # Internal references
    r'db\.[a-zA-Z0-9_]+',  # Database references
    r'internal:[a-zA-Z0-9_/-]+',  # Internal paths
    r'__[a-zA-Z0-9_]+__',  # Internal markers
]


def get_max_ledger_lines(roles: List[str]) -> int:
    """
    Get maximum ledger lines to show based on role level.
    
    Args:
        roles: List of user roles
        
    Returns:
        Maximum number of ledger lines (0 = redacted, -1 = unlimited)
    """
    # get_max_role_level takes a list of roles and returns the maximum level
    max_level = get_max_role_level(roles) if roles else 0
    
    if max_level == 0:  # general
        return 0  # Redact completely
    elif max_level == 1:  # pro, scholars
        return 10  # Limited view
    else:  # analytics, ops (level 2)
        return -1  # Unlimited


def should_show_provenance(roles: List[str]) -> bool:
    """
    Determine if provenance should be shown based on roles.
    
    Args:
        roles: List of user roles
        
    Returns:
        True if provenance should be shown, False if redacted
    """
    # get_max_role_level takes a list of roles and returns the maximum level
    max_level = get_max_role_level(roles) if roles else 0
    return max_level >= 1  # Show for pro, scholars, analytics, ops


def redact_sensitive_text(text: str) -> str:
    """
    Redact sensitive patterns from text.
    
    Args:
        text: Text to redact
        
    Returns:
        Text with sensitive patterns replaced with [REDACTED]
    """
    if not text:
        return text
    
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = re.sub(pattern, '[REDACTED]', redacted, flags=re.IGNORECASE)
    
    return redacted


def redact_ledger(ledger: Union[str, List[str], None], roles: List[str]) -> Optional[Union[str, List[str]]]:
    """
    Redact ledger data based on user roles.
    
    Args:
        ledger: Ledger data (string or list of strings)
        roles: User roles
        
    Returns:
        Redacted ledger or None
    """
    if ledger is None:
        return None
    
    max_lines = get_max_ledger_lines(roles)
    
    # Complete redaction for general users
    if max_lines == 0:
        return "[REDACTED - Upgrade to Pro for detailed processing logs]"
    
    # Process list of ledger entries
    if isinstance(ledger, list):
        if max_lines == -1:
            # Unlimited for high-level users
            return ledger
        else:
            # Limited lines for mid-level users
            if len(ledger) <= max_lines:
                return ledger
            else:
                truncated = ledger[:max_lines]
                truncated.append(f"... ({len(ledger) - max_lines} more entries)")
                return truncated
    
    # Process string ledger
    if isinstance(ledger, str):
        if max_lines == -1:
            return ledger
        
        lines = ledger.split('\n')
        if len(lines) <= max_lines:
            return ledger
        else:
            truncated_lines = lines[:max_lines]
            remaining = len(lines) - max_lines
            truncated_lines.append(f"... ({remaining} more lines)")
            return '\n'.join(truncated_lines)
    
    return ledger


def redact_provenance(provenance: Optional[Dict[str, Any]], roles: List[str]) -> Optional[Dict[str, Any]]:
    """
    Redact provenance data based on user roles.
    
    Args:
        provenance: Provenance dictionary
        roles: User roles
        
    Returns:
        Redacted provenance or None
    """
    if provenance is None:
        return None
    
    if not should_show_provenance(roles):
        # Complete redaction for general users
        return {
            "redacted": True,
            "message": "Upgrade to Pro for source attribution and processing details"
        }
    
    # For higher roles, return full provenance
    # Could add additional filtering here if needed
    return deepcopy(provenance)


def redact_message(message: Dict[str, Any], roles: List[str]) -> Dict[str, Any]:
    """
    Redact a single message based on user roles.
    
    Args:
        message: Message dictionary
        roles: User roles
        
    Returns:
        Redacted message with role_applied field
    """
    redacted = deepcopy(message)
    
    # Find role with highest level for audit field
    max_role = ROLE_GENERAL
    if roles:
        max_level = 0
        for role in roles:
            level = ROLE_VISIBILITY_LEVELS.get(role.lower(), 0)
            if level > max_level:
                max_level = level
                max_role = role
    
    # Add audit field
    redacted['role_applied'] = max_role
    
    # Redact ledger
    if 'ledger' in redacted:
        redacted['ledger'] = redact_ledger(redacted['ledger'], roles)
    
    if 'process_trace' in redacted:
        redacted['process_trace'] = redact_ledger(redacted['process_trace'], roles)
    
    # Redact provenance
    if 'provenance' in redacted:
        redacted['provenance'] = redact_provenance(redacted['provenance'], roles)
    
    if 'source' in redacted and isinstance(redacted['source'], dict):
        redacted['source'] = redact_provenance(redacted['source'], roles)
    
    # Redact sensitive text in content for general users
    max_level = get_max_role_level(roles) if roles else 0
    if max_level == 0 and 'content' in redacted:
        # Only redact technical markers, not the actual content
        if isinstance(redacted['content'], str):
            redacted['content'] = redact_sensitive_text(redacted['content'])
    
    # Redact metadata that might contain sensitive info
    if 'metadata' in redacted and isinstance(redacted['metadata'], dict):
        if max_level == 0:
            # Remove sensitive metadata for general users
            safe_metadata = {}
            for key, value in redacted['metadata'].items():
                if key not in ['internal_id', 'db_ref', 'processing_id', 'trace_id']:
                    safe_metadata[key] = value
            redacted['metadata'] = safe_metadata
    
    return redacted


def redact_chat_response(response: Dict[str, Any], roles: List[str]) -> Dict[str, Any]:
    """
    Redact entire chat response based on user roles.
    
    Args:
        response: Chat response dictionary
        roles: User roles
        
    Returns:
        Redacted response with role_applied field
    """
    redacted = deepcopy(response)
    
    # Find role with highest level for audit field
    max_role = ROLE_GENERAL
    if roles:
        max_level = 0
        for role in roles:
            level = ROLE_VISIBILITY_LEVELS.get(role.lower(), 0)
            if level > max_level:
                max_level = level
                max_role = role
    
    # Add top-level audit field
    redacted['role_applied'] = max_role
    
    # Redact messages if present
    if 'messages' in redacted and isinstance(redacted['messages'], list):
        redacted['messages'] = [
            redact_message(msg, roles) for msg in redacted['messages']
        ]
    
    # Redact single message if present
    if 'message' in redacted and isinstance(redacted['message'], dict):
        redacted['message'] = redact_message(redacted['message'], roles)
    
    # Redact response content if present
    if 'response' in redacted and isinstance(redacted['response'], dict):
        redacted['response'] = redact_message(redacted['response'], roles)
    
    # Redact context/memories
    if 'context' in redacted and isinstance(redacted['context'], list):
        redacted['context'] = [
            redact_message(ctx, roles) for ctx in redacted['context']
        ]
    
    if 'memories' in redacted and isinstance(redacted['memories'], list):
        redacted['memories'] = [
            redact_message(mem, roles) for mem in redacted['memories']
        ]
    
    return redacted


def redact_search_results(results: List[Dict[str, Any]], roles: List[str]) -> List[Dict[str, Any]]:
    """
    Redact search results based on user roles.
    
    Args:
        results: List of search result dictionaries
        roles: User roles
        
    Returns:
        List of redacted results
    """
    return [redact_message(result, roles) for result in results]
