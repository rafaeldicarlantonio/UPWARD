# core/policy.py — Factare policy helpers and access control

import re
from typing import List, Set, Dict, Any
from urllib.parse import urlparse
from config import load_config

# Load configuration once at module level
_config = load_config()

# External source whitelist patterns
EXTERNAL_WHITELIST_PATTERNS = [
    # Academic and research sources
    r"^https?://(www\.)?(arxiv\.org|pubmed\.ncbi\.nlm\.nih\.gov|scholar\.google\.com|researchgate\.net)",
    r"^https?://(www\.)?(nature\.com|science\.org|cell\.com|springer\.com|wiley\.com)",
    r"^https?://(www\.)?(ieee\.org|acm\.org|dl\.acm\.org|ieeexplore\.ieee\.org)",
    
    # Government and official sources
    r"^https?://(www\.)?(gov\.uk|gov\.au|gov\.ca|europa\.eu|who\.int|cdc\.gov|fda\.gov)",
    r"^https?://(www\.)?(un\.org|unicef\.org|worldbank\.org|imf\.org)",
    
    # News and media (reputable sources)
    r"^https?://(www\.)?(bbc\.com|reuters\.com|ap\.org|npr\.org|pbs\.org)",
    r"^https?://(www\.)?(nytimes\.com|washingtonpost\.com|theguardian\.com|economist\.com)",
    
    # Technical documentation
    r"^https?://(www\.)?(docs\.python\.org|developer\.mozilla\.org|stackoverflow\.com)",
    r"^https?://(www\.)?(github\.com|gitlab\.com|bitbucket\.org)",
    
    # Educational institutions
    r"^https?://(www\.)?([a-z0-9-]+\.)?(edu|ac\.uk|ac\.au|ac\.ca)",
]

# Compile patterns for performance
_compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in EXTERNAL_WHITELIST_PATTERNS]

# Role-based access control
ROLE_PERMISSIONS = {
    "admin": {
        "factare_enabled": True,
        "external_allowed": True,
        "bypass_whitelist": True,
    },
    "ops": {
        "factare_enabled": True,
        "external_allowed": True,
        "bypass_whitelist": False,
    },
    "pro": {
        "factare_enabled": True,
        "external_allowed": True,
        "bypass_whitelist": False,
    },
    "scholars": {
        "factare_enabled": True,
        "external_allowed": True,
        "bypass_whitelist": False,
    },
    "analytics": {
        "factare_enabled": True,
        "external_allowed": False,  # Internal only
        "bypass_whitelist": False,
    },
    "general": {
        "factare_enabled": False,  # No access
        "external_allowed": False,
        "bypass_whitelist": False,
    },
    "user": {
        "factare_enabled": False,  # No access
        "external_allowed": False,
        "bypass_whitelist": False,
    },
}

def is_external_allowed(user_roles: List[str], factare_allow_external: bool) -> bool:
    """
    Check if external sources are allowed for the given user roles and feature flag.
    
    Args:
        user_roles: List of user roles (e.g., ["pro", "analytics"])
        factare_allow_external: Current value of factare.allow_external feature flag
        
    Returns:
        bool: True if external sources are allowed, False otherwise
    """
    # Feature flag must be enabled
    if not factare_allow_external:
        return False
    
    # Check if any role allows external access
    for role in user_roles:
        role_perms = ROLE_PERMISSIONS.get(role, {})
        if role_perms.get("external_allowed", False):
            return True
    
    return False

def is_source_whitelisted(url: str) -> bool:
    """
    Check if a URL is whitelisted for external access.
    
    Args:
        url: The URL to check
        
    Returns:
        bool: True if the URL is whitelisted, False otherwise
    """
    if not url:
        return False
    
    try:
        # Parse the URL to validate it
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Check against compiled patterns
        for pattern in _compiled_patterns:
            if pattern.match(url):
                return True
        
        return False
    except Exception:
        # If URL parsing fails, reject it
        return False

def can_access_factare(user_roles: List[str], factare_enabled: bool) -> bool:
    """
    Check if a user can access Factare functionality.
    
    Args:
        user_roles: List of user roles
        factare_enabled: Current value of factare.enabled feature flag
        
    Returns:
        bool: True if user can access Factare, False otherwise
    """
    # Feature flag must be enabled
    if not factare_enabled:
        return False
    
    # Check if any role allows Factare access
    for role in user_roles:
        role_perms = ROLE_PERMISSIONS.get(role, {})
        if role_perms.get("factare_enabled", False):
            return True
    
    return False

def get_max_sources(user_roles: List[str], is_external: bool) -> int:
    """
    Get the maximum number of sources allowed for a user based on their roles.
    
    Args:
        user_roles: List of user roles
        is_external: Whether the sources are external (True) or internal (False)
        
    Returns:
        int: Maximum number of sources allowed
    """
    # Check if user has admin privileges (highest limits)
    if "admin" in user_roles:
        return _config.get("FACTARE_MAX_SOURCES_EXTERNAL", 8) if is_external else _config.get("FACTARE_MAX_SOURCES_INTERNAL", 24)
    
    # Check if user has ops privileges (high limits)
    if "ops" in user_roles:
        return _config.get("FACTARE_MAX_SOURCES_EXTERNAL", 8) if is_external else _config.get("FACTARE_MAX_SOURCES_INTERNAL", 24)
    
    # Check if user has pro/scholars privileges (standard limits)
    if any(role in ["pro", "scholars"] for role in user_roles):
        return _config.get("FACTARE_MAX_SOURCES_EXTERNAL", 8) if is_external else _config.get("FACTARE_MAX_SOURCES_INTERNAL", 24)
    
    # Check if user has analytics privileges (internal only)
    if "analytics" in user_roles:
        return 0 if is_external else _config.get("FACTARE_MAX_SOURCES_INTERNAL", 24)
    
    # Default: no access
    return 0

def get_external_timeout_ms() -> int:
    """
    Get the external source timeout in milliseconds from configuration.
    
    Returns:
        int: Timeout in milliseconds
    """
    return _config.get("FACTARE_EXTERNAL_TIMEOUT_MS", 2000)

def get_pareto_threshold() -> float:
    """
    Get the Pareto threshold for hypotheses from configuration.
    
    Returns:
        float: Pareto threshold (0.0 to 1.0)
    """
    return _config.get("HYPOTHESES_PARETO_THRESHOLD", 0.65)

def validate_source_url(url: str) -> Dict[str, Any]:
    """
    Validate a source URL and return detailed information about its status.
    
    Args:
        url: The URL to validate
        
    Returns:
        Dict containing validation results:
        - valid: bool - Whether the URL is valid
        - whitelisted: bool - Whether the URL is whitelisted
        - domain: str - The domain of the URL
        - error: str - Error message if validation failed
    """
    result = {
        "valid": False,
        "whitelisted": False,
        "domain": "",
        "error": ""
    }
    
    if not url:
        result["error"] = "URL is empty"
        return result
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            result["error"] = "Invalid URL format"
            return result
        
        result["valid"] = True
        result["domain"] = parsed.netloc
        result["whitelisted"] = is_source_whitelisted(url)
        
    except Exception as e:
        result["error"] = f"URL parsing error: {str(e)}"
    
    return result

def get_user_policy_summary(user_roles: List[str], factare_enabled: bool, factare_allow_external: bool) -> Dict[str, Any]:
    """
    Get a comprehensive policy summary for a user.
    
    Args:
        user_roles: List of user roles
        factare_enabled: Current value of factare.enabled feature flag
        factare_allow_external: Current value of factare.allow_external feature flag
        
    Returns:
        Dict containing policy summary:
        - can_access_factare: bool
        - external_allowed: bool
        - max_internal_sources: int
        - max_external_sources: int
        - external_timeout_ms: int
        - pareto_threshold: float
        - roles: List[str]
        - permissions: Dict[str, bool]
    """
    can_access = can_access_factare(user_roles, factare_enabled)
    external_allowed = is_external_allowed(user_roles, factare_allow_external)
    
    # Get permissions for each role
    permissions = {}
    for role in user_roles:
        role_perms = ROLE_PERMISSIONS.get(role, {})
        permissions[role] = {
            "factare_enabled": role_perms.get("factare_enabled", False),
            "external_allowed": role_perms.get("external_allowed", False),
            "bypass_whitelist": role_perms.get("bypass_whitelist", False),
        }
    
    return {
        "can_access_factare": can_access,
        "external_allowed": external_allowed,
        "max_internal_sources": get_max_sources(user_roles, False) if can_access else 0,
        "max_external_sources": get_max_sources(user_roles, True) if can_access and external_allowed else 0,
        "external_timeout_ms": get_external_timeout_ms(),
        "pareto_threshold": get_pareto_threshold(),
        "roles": user_roles,
        "permissions": permissions,
    }