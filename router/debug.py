from __future__ import annotations
import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException, Query

from vendors.supabase_client import supabase
from schemas.api import DebugMemoriesResponse
from config import load_config
from feature_flags import get_all_flags

router = APIRouter(tags=["debug"])

def _require_key(x_api_key: Optional[str]):
    want = os.getenv("X_API_KEY") or os.getenv("ACTIONS_API_KEY")
    if os.getenv("DISABLE_AUTH","false").lower() == "true":
        return
    if not want:
        raise HTTPException(status_code=500, detail="Server missing X_API_KEY")
    if not x_api_key or x_api_key != want:
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/debug/memories", response_model=DebugMemoriesResponse)
def debug_memories(
    x_api_key: Optional[str] = Header(None),
    type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    _require_key(x_api_key)
    q = supabase.table("memories").select("id,type,title,created_at").order("created_at", desc=True).limit(limit)
    if type:
        q = q.eq("type", type)
    r = q.execute()
    out = [{"id": row["id"], "type": row.get("type"), "title": row.get("title"), "created_at": row.get("created_at")} for row in (r.data or [])]
    return {"items": out}

@router.get("/debug/config")
def debug_config(x_api_key: Optional[str] = Header(None)):
    """Show current configuration and feature flags."""
    _require_key(x_api_key)
    
    try:
        # Load configuration (this will fail if required env vars are missing)
        config = load_config()
        
        # Get feature flags
        flags = get_all_flags()
        
        # Return sanitized config (hide sensitive values)
        sanitized_config = {}
        for key, value in config.items():
            if any(sensitive in key.upper() for sensitive in ['KEY', 'SECRET', 'PASSWORD', 'TOKEN']):
                sanitized_config[key] = "***REDACTED***"
            else:
                sanitized_config[key] = value
        
        return {
            "config": sanitized_config,
            "feature_flags": flags,
            "status": "ok"
        }
    except Exception as e:
        return {
            "config": {},
            "feature_flags": {},
            "status": "error",
            "error": str(e)
        }
