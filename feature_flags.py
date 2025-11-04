# feature_flags.py — feature flag management

import os
from typing import Dict, Any, Optional
from vendors.supabase_client import supabase

# Default feature flags - all disabled by default
DEFAULT_FLAGS = {
    "retrieval.dual_index": False,
    "retrieval.liftscore": False,
    "retrieval.contradictions_pack": False,

    # Ingest feature flags
    "ingest.analysis.enabled": False,
    "ingest.contradictions.enabled": False,
    "ingest.implicate.refresh_enabled": False,
    
    # REDO/ledger feature flags
    "orchestrator.redo_enabled": False,
    "ledger.enabled": False,
    
    # Factare feature flags
    "factare.enabled": False,
    "factare.allow_external": False,
    
    # External comparison feature flag
    "external_compare": False,
}

def get_feature_flag(flag_name: str, default: bool = False) -> bool:
    """
    Get a feature flag value from the database.
    Falls back to default if not found or if database is unavailable.
    """
    try:
        result = supabase.table("feature_flags").select("value").eq("key", flag_name).execute()
        if result.data and len(result.data) > 0:
            flag_data = result.data[0].get("value", {})
            return flag_data.get("enabled", default)
    except Exception:
        # If database is unavailable, fall back to default
        pass
    
    return default

def set_feature_flag(flag_name: str, enabled: bool) -> None:
    """
    Set a feature flag value in the database.
    """
    try:
        supabase.table("feature_flags").upsert({
            "key": flag_name,
            "value": {"enabled": enabled}
        }).execute()
    except Exception as e:
        raise RuntimeError(f"Failed to set feature flag {flag_name}: {e}")

def get_all_flags() -> Dict[str, bool]:
    """
    Get all feature flags with their current values.
    Returns a dict of flag_name -> enabled_status.
    """
    flags = {}
    
    # Get flags from database
    try:
        result = supabase.table("feature_flags").select("key, value").execute()
        if result.data:
            for row in result.data:
                key = row.get("key")
                value = row.get("value", {})
                if key:
                    flags[key] = value.get("enabled", False)
    except Exception:
        # If database is unavailable, use defaults
        pass
    
    # Ensure all default flags are present
    for flag_name, default_value in DEFAULT_FLAGS.items():
        if flag_name not in flags:
            flags[flag_name] = default_value
    
    return flags

def initialize_default_flags() -> None:
    """
    Initialize default flags in the database if they don't exist.
    """
    try:
        for flag_name, default_value in DEFAULT_FLAGS.items():
            # Check if flag exists
            result = supabase.table("feature_flags").select("key").eq("key", flag_name).execute()
            if not result.data or len(result.data) == 0:
                # Flag doesn't exist, create it
                set_feature_flag(flag_name, default_value)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize default flags: {e}")

# ============================================================================
# Feature Flag Accessor Class
# ============================================================================

class FeatureFlags:
    """
    Simple accessor for feature flags using get_feature_flag.
    
    Provides attribute-style access to feature flags for convenience.
    """
    
    @property
    def external_compare(self) -> bool:
        """Check if external comparison is enabled."""
        return get_feature_flag("external_compare", DEFAULT_FLAGS.get("external_compare", False))
    
    def __repr__(self):
        return f"<FeatureFlags external_compare={self.external_compare}>"


# Global flags instance
flags = FeatureFlags()


# ============================================================================
# Performance Flags and Budgets
# ============================================================================

def get_perf_flags() -> Dict[str, Any]:
    """
    Get all performance flags and budgets from config.
    
    Returns a dict with:
    - flags: Boolean feature flags (parallel, enabled, etc.)
    - budgets: Timeout/budget values in milliseconds
    
    Example:
        {
            "flags": {
                "retrieval_parallel": True,
                "reviewer_enabled": True,
                "pgvector_enabled": True,
                "fallbacks_enabled": True
            },
            "budgets": {
                "retrieval_timeout_ms": 450,
                "graph_timeout_ms": 150,
                "compare_timeout_ms": 400,
                "reviewer_budget_ms": 500
            }
        }
    """
    from config import load_config
    
    try:
        cfg = load_config()
        
        return {
            "flags": {
                "retrieval_parallel": cfg.get("PERF_RETRIEVAL_PARALLEL", True),
                "reviewer_enabled": cfg.get("PERF_REVIEWER_ENABLED", True),
                "pgvector_enabled": cfg.get("PERF_PGVECTOR_ENABLED", True),
                "fallbacks_enabled": cfg.get("PERF_FALLBACKS_ENABLED", True),
            },
            "budgets": {
                "retrieval_timeout_ms": cfg.get("PERF_RETRIEVAL_TIMEOUT_MS", 450),
                "graph_timeout_ms": cfg.get("PERF_GRAPH_TIMEOUT_MS", 150),
                "compare_timeout_ms": cfg.get("PERF_COMPARE_TIMEOUT_MS", 400),
                "reviewer_budget_ms": cfg.get("PERF_REVIEWER_BUDGET_MS", 500),
            }
        }
    except Exception as e:
        # Return defaults if config can't be loaded
        return {
            "flags": {
                "retrieval_parallel": True,
                "reviewer_enabled": True,
                "pgvector_enabled": True,
                "fallbacks_enabled": True,
            },
            "budgets": {
                "retrieval_timeout_ms": 450,
                "graph_timeout_ms": 150,
                "compare_timeout_ms": 400,
                "reviewer_budget_ms": 500,
            },
            "error": str(e)
        }
