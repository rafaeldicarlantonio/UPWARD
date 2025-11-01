# core/policy.py — Factare policy helpers and access control

import re
import os
import yaml
import logging
from typing import List, Set, Dict, Any, Optional
from urllib.parse import urlparse
from dataclasses import dataclass, field
from config import load_config

logger = logging.getLogger(__name__)

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


# ============================================================================
# Ingest Policy Configuration
# ============================================================================

@dataclass
class IngestPolicy:
    """Policy for ingestion operations."""
    max_concepts_per_file: int
    max_frames_per_chunk: int
    write_contradictions_to_memories: bool
    allowed_frame_types: List[str]
    contradiction_tolerance: float
    role: str = "default"
    
    def validate(self, global_limits: Dict[str, Any]) -> 'IngestPolicy':
        """
        Validate and clamp policy values to global limits.
        
        Args:
            global_limits: Global limits that cannot be exceeded
            
        Returns:
            Self (for chaining)
        """
        # Clamp to global absolute limits
        self.max_concepts_per_file = min(
            self.max_concepts_per_file,
            global_limits.get("max_concepts_per_file_absolute", 1000)
        )
        self.max_frames_per_chunk = min(
            self.max_frames_per_chunk,
            global_limits.get("max_frames_per_chunk_absolute", 100)
        )
        
        # Clamp contradiction tolerance
        min_tol = global_limits.get("min_contradiction_tolerance", 0.05)
        max_tol = global_limits.get("max_contradiction_tolerance", 0.9)
        self.contradiction_tolerance = max(min_tol, min(max_tol, self.contradiction_tolerance))
        
        return self


class IngestPolicyManager:
    """Manager for loading and accessing ingest policies."""
    
    def __init__(self, policy_path: Optional[str] = None):
        """
        Initialize the policy manager.
        
        Args:
            policy_path: Path to the policy YAML file. If None, uses default location.
        """
        self.policy_path = policy_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "ingest_policy.yaml"
        )
        self._policies: Dict[str, IngestPolicy] = {}
        self._default_policy: Optional[IngestPolicy] = None
        self._global_limits: Dict[str, Any] = {}
        self._valid_frame_types: List[str] = []
        self._load_policy()
    
    def _get_safe_default_policy(self) -> IngestPolicy:
        """Get a safe default policy when loading fails."""
        return IngestPolicy(
            max_concepts_per_file=20,
            max_frames_per_chunk=5,
            write_contradictions_to_memories=False,
            allowed_frame_types=["claim"],
            contradiction_tolerance=0.5,
            role="default"
        )
    
    def _load_policy(self):
        """Load policy from YAML file with safe fallback."""
        try:
            if not os.path.exists(self.policy_path):
                logger.warning(f"Policy file not found at {self.policy_path}, using safe defaults")
                self._default_policy = self._get_safe_default_policy()
                self._global_limits = {
                    "max_concepts_per_file_absolute": 1000,
                    "max_frames_per_chunk_absolute": 100,
                    "max_edges_per_commit_absolute": 5000,
                    "min_contradiction_tolerance": 0.05,
                    "max_contradiction_tolerance": 0.9,
                }
                self._valid_frame_types = ["claim", "evidence", "observation"]
                return
            
            with open(self.policy_path, 'r') as f:
                policy_data = yaml.safe_load(f)
            
            if not policy_data:
                raise ValueError("Policy file is empty")
            
            # Load global limits
            self._global_limits = policy_data.get("global_limits", {})
            
            # Load valid frame types
            self._valid_frame_types = policy_data.get("valid_frame_types", [])
            
            # Load role-specific policies
            roles = policy_data.get("roles", {})
            for role_name, role_policy in roles.items():
                try:
                    policy = IngestPolicy(
                        max_concepts_per_file=role_policy.get("max_concepts_per_file", 20),
                        max_frames_per_chunk=role_policy.get("max_frames_per_chunk", 5),
                        write_contradictions_to_memories=role_policy.get("write_contradictions_to_memories", False),
                        allowed_frame_types=role_policy.get("allowed_frame_types", ["claim"]),
                        contradiction_tolerance=role_policy.get("contradiction_tolerance", 0.5),
                        role=role_name
                    )
                    policy.validate(self._global_limits)
                    self._policies[role_name] = policy
                except Exception as e:
                    logger.error(f"Failed to load policy for role '{role_name}': {e}")
            
            # Load default policy
            default_data = policy_data.get("default", {})
            self._default_policy = IngestPolicy(
                max_concepts_per_file=default_data.get("max_concepts_per_file", 20),
                max_frames_per_chunk=default_data.get("max_frames_per_chunk", 5),
                write_contradictions_to_memories=default_data.get("write_contradictions_to_memories", False),
                allowed_frame_types=default_data.get("allowed_frame_types", ["claim"]),
                contradiction_tolerance=default_data.get("contradiction_tolerance", 0.5),
                role="default"
            )
            self._default_policy.validate(self._global_limits)
            
            logger.info(f"Loaded ingest policies for {len(self._policies)} roles from {self.policy_path}")
            
        except Exception as e:
            logger.error(f"Failed to load policy from {self.policy_path}: {e}, using safe defaults")
            self._default_policy = self._get_safe_default_policy()
            self._global_limits = {
                "max_concepts_per_file_absolute": 1000,
                "max_frames_per_chunk_absolute": 100,
                "max_edges_per_commit_absolute": 5000,
                "min_contradiction_tolerance": 0.05,
                "max_contradiction_tolerance": 0.9,
            }
            self._valid_frame_types = ["claim", "evidence", "observation"]
    
    def get_policy(self, roles: Optional[List[str]] = None) -> IngestPolicy:
        """
        Get the policy for the given roles.
        
        Uses the most permissive policy if multiple roles are provided.
        Falls back to default policy if no matching role is found.
        
        Args:
            roles: List of user roles. If None or empty, returns default policy.
            
        Returns:
            IngestPolicy for the user
        """
        if not roles:
            return self._default_policy or self._get_safe_default_policy()
        
        # Find the most permissive policy among the user's roles
        best_policy = None
        max_concepts = 0
        
        for role in roles:
            policy = self._policies.get(role)
            if policy and policy.max_concepts_per_file > max_concepts:
                best_policy = policy
                max_concepts = policy.max_concepts_per_file
        
        return best_policy or self._default_policy or self._get_safe_default_policy()
    
    def get_global_limits(self) -> Dict[str, Any]:
        """Get global limits."""
        return self._global_limits.copy()
    
    def get_valid_frame_types(self) -> List[str]:
        """Get list of valid frame types."""
        return self._valid_frame_types.copy()
    
    def validate_frame_type(self, frame_type: str) -> bool:
        """
        Check if a frame type is valid.
        
        Args:
            frame_type: The frame type to validate
            
        Returns:
            True if valid, False otherwise
        """
        return frame_type in self._valid_frame_types
    
    def enforce_caps(
        self,
        concepts: List[Any],
        frames: List[Any],
        contradictions: List[Any],
        policy: IngestPolicy
    ) -> Dict[str, Any]:
        """
        Enforce policy caps on the analysis results.
        
        Args:
            concepts: List of concepts to cap
            frames: List of frames to cap
            contradictions: List of contradictions
            policy: Policy to enforce
            
        Returns:
            Dict with capped results:
            - concepts: Capped concepts list
            - frames: Capped frames list
            - contradictions: Filtered contradictions
            - frames_filtered: List of filtered frame types
            - caps_applied: Dict of applied caps
        """
        capped_concepts = concepts[:policy.max_concepts_per_file]
        
        # Filter frames by allowed types and cap
        allowed_frames = []
        filtered_frames = []
        
        for frame in frames:
            frame_type = getattr(frame, 'type', None) or (frame.get('type') if isinstance(frame, dict) else None)
            if frame_type in policy.allowed_frame_types:
                allowed_frames.append(frame)
            else:
                filtered_frames.append(frame_type or 'unknown')
        
        capped_frames = allowed_frames[:policy.max_frames_per_chunk]
        
        # Apply contradiction tolerance
        filtered_contradictions = []
        if contradictions:
            for contradiction in contradictions:
                # Assume contradictions have a 'score' or 'confidence' field
                score = getattr(contradiction, 'score', None) or (
                    contradiction.get('score') if isinstance(contradiction, dict) else 1.0
                )
                if score is None:
                    score = 1.0
                
                if score >= policy.contradiction_tolerance:
                    filtered_contradictions.append(contradiction)
        
        return {
            "concepts": capped_concepts,
            "frames": capped_frames,
            "contradictions": filtered_contradictions if policy.write_contradictions_to_memories else [],
            "frames_filtered": filtered_frames,
            "caps_applied": {
                "concepts_before": len(concepts),
                "concepts_after": len(capped_concepts),
                "frames_before": len(frames),
                "frames_after": len(capped_frames),
                "frames_filtered_count": len(filtered_frames),
                "contradictions_before": len(contradictions) if contradictions else 0,
                "contradictions_after": len(filtered_contradictions),
                "write_contradictions": policy.write_contradictions_to_memories,
            }
        }


# Global policy manager instance
_policy_manager: Optional[IngestPolicyManager] = None


def get_ingest_policy_manager() -> IngestPolicyManager:
    """Get or create the global policy manager instance."""
    global _policy_manager
    if _policy_manager is None:
        _policy_manager = IngestPolicyManager()
    return _policy_manager


def get_ingest_policy(roles: Optional[List[str]] = None) -> IngestPolicy:
    """
    Convenience function to get ingest policy for roles.
    
    Args:
        roles: List of user roles
        
    Returns:
        IngestPolicy for the user
    """
    manager = get_ingest_policy_manager()
    return manager.get_policy(roles)


# ============================================================================
# External Source Role Gating
# ============================================================================

def can_use_external_compare(user_roles: List[str]) -> bool:
    """
    Check if user can use external source comparison.
    
    Returns True only if:
    1. external_compare feature flag is enabled
    2. User has at least one role in allowed_roles_for_external from policy
    
    Args:
        user_roles: List of user's role names
        
    Returns:
        True if user can access external comparison, False otherwise
        
    Examples:
        >>> can_use_external_compare(["general"])
        False  # General not in allowed_roles
        
        >>> can_use_external_compare(["pro"])
        True  # If flag is on and pro is in policy.allowed_roles_for_external
        
        >>> can_use_external_compare(["analytics", "general"])
        True  # Has at least one allowed role
    """
    # Import here to avoid circular dependency
    from feature_flags import get_feature_flag, DEFAULT_FLAGS
    from core.config_loader import get_loader
    
    # Check feature flag first
    flag_enabled = get_feature_flag("external_compare", DEFAULT_FLAGS.get("external_compare", False))
    if not flag_enabled:
        logger.debug("External compare disabled by feature flag")
        return False
    
    # Get allowed roles from policy
    try:
        loader = get_loader()
        policy = loader.get_compare_policy()
        allowed_roles = policy.allowed_roles_for_external
    except Exception as e:
        logger.error(f"Failed to load external compare policy: {e}")
        return False
    
    # Check if user has any allowed role
    has_allowed_role = any(role in allowed_roles for role in user_roles)
    
    if not has_allowed_role:
        logger.debug(
            f"User roles {user_roles} not in allowed_roles_for_external {allowed_roles}"
        )
    
    return has_allowed_role
