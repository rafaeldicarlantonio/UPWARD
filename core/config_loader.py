"""
Configuration loader for external sources and comparison policies.

Loads and validates configuration files for external source whitelisting
and comparison policies with safe defaults and error handling.
"""

import json
import yaml
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ExternalSource:
    """Configuration for a whitelisted external source."""
    source_id: str
    label: str
    priority: int
    url_pattern: str
    max_snippet_chars: int
    enabled: bool = True
    
    def __post_init__(self):
        """Validate field values."""
        if not self.source_id:
            raise ValueError("source_id cannot be empty")
        if not isinstance(self.priority, int) or self.priority < 0:
            raise ValueError(f"priority must be non-negative integer, got {self.priority}")
        if not isinstance(self.max_snippet_chars, int) or self.max_snippet_chars <= 0:
            raise ValueError(f"max_snippet_chars must be positive integer, got {self.max_snippet_chars}")
        if not self.url_pattern:
            raise ValueError("url_pattern cannot be empty")
        
        # Validate regex pattern
        try:
            re.compile(self.url_pattern)
        except re.error as e:
            raise ValueError(f"Invalid url_pattern regex: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ComparePolicy:
    """Policy configuration for external source comparison."""
    max_external_sources_per_run: int = 6
    max_total_external_chars: int = 2400
    allowed_roles_for_external: List[str] = field(default_factory=lambda: ["pro", "scholars", "analytics"])
    timeout_ms_per_request: int = 2000
    rate_limit_per_domain_per_min: int = 6
    tie_break: str = "prefer_internal"
    redact_patterns: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate field values."""
        if not isinstance(self.max_external_sources_per_run, int) or self.max_external_sources_per_run < 1:
            raise ValueError(f"max_external_sources_per_run must be positive integer, got {self.max_external_sources_per_run}")
        
        if not isinstance(self.max_total_external_chars, int) or self.max_total_external_chars < 1:
            raise ValueError(f"max_total_external_chars must be positive integer, got {self.max_total_external_chars}")
        
        if not isinstance(self.timeout_ms_per_request, int) or self.timeout_ms_per_request < 1:
            raise ValueError(f"timeout_ms_per_request must be positive integer, got {self.timeout_ms_per_request}")
        
        if not isinstance(self.rate_limit_per_domain_per_min, int) or self.rate_limit_per_domain_per_min < 1:
            raise ValueError(f"rate_limit_per_domain_per_min must be positive integer, got {self.rate_limit_per_domain_per_min}")
        
        valid_tie_breaks = ["prefer_internal", "prefer_external", "abstain"]
        if self.tie_break not in valid_tie_breaks:
            raise ValueError(f"tie_break must be one of {valid_tie_breaks}, got {self.tie_break}")
        
        if not isinstance(self.allowed_roles_for_external, list):
            raise ValueError(f"allowed_roles_for_external must be a list, got {type(self.allowed_roles_for_external)}")
        
        # Validate redact patterns are valid regexes
        for pattern in self.redact_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid redact_pattern regex '{pattern}': {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# ============================================================================
# Default Configurations
# ============================================================================

DEFAULT_WHITELIST: List[Dict[str, Any]] = [
    {
        "source_id": "wikipedia",
        "label": "Wikipedia",
        "priority": 10,
        "url_pattern": "https://.*\\.wikipedia\\.org/.*",
        "max_snippet_chars": 480,
        "enabled": True
    }
]

DEFAULT_COMPARE_POLICY = {
    "max_external_sources_per_run": 3,
    "max_total_external_chars": 1200,
    "allowed_roles_for_external": ["pro", "scholars", "analytics"],
    "timeout_ms_per_request": 2000,
    "rate_limit_per_domain_per_min": 6,
    "tie_break": "prefer_internal",
    "redact_patterns": [
        "Authorization:\\s+\\S+",
        "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*"
    ]
}


# ============================================================================
# Configuration Loader
# ============================================================================

class ConfigLoader:
    """
    Loads and validates external source configurations.
    
    Provides safe defaults and error handling for missing or invalid configs.
    """
    
    def __init__(
        self,
        whitelist_path: Optional[str] = None,
        policy_path: Optional[str] = None,
        workspace_root: Optional[str] = None
    ):
        """
        Initialize the configuration loader.
        
        Args:
            whitelist_path: Path to external sources whitelist JSON file
            policy_path: Path to compare policy YAML file
            workspace_root: Root directory for resolving relative paths
        """
        # Determine workspace root
        if workspace_root:
            self.workspace_root = Path(workspace_root)
        else:
            # Default to /workspace or current directory
            self.workspace_root = Path("/workspace") if Path("/workspace").exists() else Path.cwd()
        
        # Set config paths
        self.whitelist_path = Path(whitelist_path) if whitelist_path else self.workspace_root / "config" / "external_sources_whitelist.json"
        self.policy_path = Path(policy_path) if policy_path else self.workspace_root / "config" / "compare_policy.yaml"
        
        # Loaded configurations
        self._whitelist: List[ExternalSource] = []
        self._policy: Optional[ComparePolicy] = None
        
        # Load configurations
        self._load_whitelist()
        self._load_policy()
    
    def _load_whitelist(self) -> None:
        """Load and validate external sources whitelist."""
        try:
            if not self.whitelist_path.exists():
                logger.warning(
                    f"Whitelist file not found at {self.whitelist_path}. "
                    f"Using default whitelist."
                )
                self._whitelist = self._parse_whitelist(DEFAULT_WHITELIST)
                return
            
            with open(self.whitelist_path, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logger.error(
                    f"Whitelist must be a JSON array, got {type(data).__name__}. "
                    f"Using default whitelist."
                )
                self._whitelist = self._parse_whitelist(DEFAULT_WHITELIST)
                return
            
            self._whitelist = self._parse_whitelist(data)
            logger.info(f"Loaded {len(self._whitelist)} external sources from {self.whitelist_path}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse whitelist JSON at {self.whitelist_path}: {e}. Using defaults.")
            self._whitelist = self._parse_whitelist(DEFAULT_WHITELIST)
        except Exception as e:
            logger.error(f"Unexpected error loading whitelist: {e}. Using defaults.")
            self._whitelist = self._parse_whitelist(DEFAULT_WHITELIST)
    
    def _parse_whitelist(self, data: List[Dict[str, Any]]) -> List[ExternalSource]:
        """
        Parse and validate whitelist entries.
        
        Args:
            data: List of source dictionaries
            
        Returns:
            List of validated ExternalSource objects, sorted by priority
        """
        sources = []
        
        for i, item in enumerate(data):
            try:
                # Validate required fields
                required_fields = ["source_id", "label", "priority", "url_pattern", "max_snippet_chars"]
                missing_fields = [f for f in required_fields if f not in item]
                
                if missing_fields:
                    logger.warning(
                        f"Whitelist entry {i} missing required fields {missing_fields}. Skipping."
                    )
                    continue
                
                # Create ExternalSource (will validate in __post_init__)
                source = ExternalSource(
                    source_id=item["source_id"],
                    label=item["label"],
                    priority=item["priority"],
                    url_pattern=item["url_pattern"],
                    max_snippet_chars=item["max_snippet_chars"],
                    enabled=item.get("enabled", True)
                )
                sources.append(source)
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid whitelist entry {i}: {e}. Skipping.")
                continue
        
        if not sources:
            logger.warning("No valid sources in whitelist. Using minimal defaults.")
            sources = self._parse_whitelist(DEFAULT_WHITELIST)
        
        # Sort by priority (highest first)
        sources.sort(key=lambda s: s.priority, reverse=True)
        
        return sources
    
    def _load_policy(self) -> None:
        """Load and validate compare policy."""
        try:
            if not self.policy_path.exists():
                logger.warning(
                    f"Policy file not found at {self.policy_path}. "
                    f"Using default policy."
                )
                self._policy = ComparePolicy(**DEFAULT_COMPARE_POLICY)
                return
            
            with open(self.policy_path, 'r') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                logger.error(
                    f"Policy must be a YAML mapping, got {type(data).__name__}. "
                    f"Using default policy."
                )
                self._policy = ComparePolicy(**DEFAULT_COMPARE_POLICY)
                return
            
            # Merge with defaults (use provided values, fall back to defaults)
            policy_data = {**DEFAULT_COMPARE_POLICY, **data}
            
            # Create and validate policy
            self._policy = ComparePolicy(**policy_data)
            logger.info(f"Loaded compare policy from {self.policy_path}")
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse policy YAML at {self.policy_path}: {e}. Using defaults.")
            self._policy = ComparePolicy(**DEFAULT_COMPARE_POLICY)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid policy configuration: {e}. Using defaults.")
            self._policy = ComparePolicy(**DEFAULT_COMPARE_POLICY)
        except Exception as e:
            logger.error(f"Unexpected error loading policy: {e}. Using defaults.")
            self._policy = ComparePolicy(**DEFAULT_COMPARE_POLICY)
    
    def get_whitelist(self, enabled_only: bool = True) -> List[ExternalSource]:
        """
        Get list of external sources.
        
        Args:
            enabled_only: If True, return only enabled sources
            
        Returns:
            List of ExternalSource objects, sorted by priority (highest first)
        """
        if enabled_only:
            return [s for s in self._whitelist if s.enabled]
        return self._whitelist.copy()
    
    def get_compare_policy(self) -> ComparePolicy:
        """
        Get compare policy configuration.
        
        Returns:
            ComparePolicy object
        """
        return self._policy
    
    def get_source_by_id(self, source_id: str) -> Optional[ExternalSource]:
        """
        Get a specific external source by ID.
        
        Args:
            source_id: Source identifier
            
        Returns:
            ExternalSource if found, None otherwise
        """
        for source in self._whitelist:
            if source.source_id == source_id:
                return source
        return None
    
    def reload(self) -> None:
        """Reload configurations from disk."""
        logger.info("Reloading external source configurations")
        self._load_whitelist()
        self._load_policy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Export configurations as dictionary.
        
        Returns:
            Dictionary with whitelist and policy
        """
        return {
            "whitelist": [s.to_dict() for s in self._whitelist],
            "policy": self._policy.to_dict() if self._policy else None
        }


# ============================================================================
# Global Loader Instance
# ============================================================================

_loader: Optional[ConfigLoader] = None


def get_loader(
    whitelist_path: Optional[str] = None,
    policy_path: Optional[str] = None,
    workspace_root: Optional[str] = None,
    force_reload: bool = False
) -> ConfigLoader:
    """
    Get global ConfigLoader instance (singleton pattern).
    
    Args:
        whitelist_path: Path to whitelist JSON (only used on first call)
        policy_path: Path to policy YAML (only used on first call)
        workspace_root: Workspace root directory (only used on first call)
        force_reload: Force recreation of loader
        
    Returns:
        ConfigLoader instance
    """
    global _loader
    
    if _loader is None or force_reload:
        _loader = ConfigLoader(
            whitelist_path=whitelist_path,
            policy_path=policy_path,
            workspace_root=workspace_root
        )
    
    return _loader


def reset_loader() -> None:
    """Reset global loader instance (useful for testing)."""
    global _loader
    _loader = None
