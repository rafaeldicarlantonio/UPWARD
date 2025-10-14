# feature_flags.py — feature flag management

import os
from typing import Dict, Any, Optional
from vendors.supabase_client import supabase

# Default feature flags - all disabled by default
DEFAULT_FLAGS = {
    "retrieval.dual_index": False,
    "retrieval.liftscore": False,
    "retrieval.contradictions_pack": False,
    
    # REDO/ledger feature flags
    "orchestrator.redo_enabled": False,
    "ledger.enabled": False,
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