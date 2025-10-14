from __future__ import annotations
import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException, Query

from vendors.supabase_client import supabase
from schemas.api import DebugMemoriesResponse
from config import load_config
from feature_flags import get_all_flags
from core.ledger import RheomodeLedger
from core.metrics import get_all_metrics, reset_metrics
from core.orchestrator.replay import replay_trace, replay_trace_with_ledger
from core.types import OrchestrationResult

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

@router.get("/debug/retrieval_trace")
def debug_retrieval_trace(
    message_id: str = Query(..., description="Message ID to get trace for"),
    x_api_key: Optional[str] = Header(None)
):
    """Get the last rheomode run trace for a given message ID."""
    _require_key(x_api_key)
    
    try:
        ledger = RheomodeLedger()
        run = ledger.get_run_by_message_id(message_id)
        
        if not run:
            raise HTTPException(status_code=404, detail="No trace found for message ID")
        
        # Convert to response format
        response = {
            "id": run.id,
            "session_id": run.session_id,
            "message_id": run.message_id,
            "role": run.role,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "lift_score": run.lift_score,
            "contradiction_score": run.contradiction_score,
            "process_trace_summary": run.process_trace_summary
        }
        
        # Add full process trace if available
        if run.process_trace:
            from dataclasses import asdict
            response["process_trace"] = asdict(run.process_trace)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trace: {str(e)}")

@router.get("/debug/metrics")
def debug_metrics(
    x_api_key: Optional[str] = Header(None),
    reset: bool = Query(False, description="Reset metrics after returning them")
):
    """Get current metrics for debugging and monitoring."""
    _require_key(x_api_key)
    
    try:
        # Get all metrics
        metrics = get_all_metrics()
        
        # Add summary statistics
        summary = {
            "total_counters": sum(len(counters) for counters in metrics["counters"].values()),
            "total_gauges": sum(len(gauges) for gauges in metrics["gauges"].values()),
            "total_histograms": sum(len(histograms) for histograms in metrics["histograms"].values()),
            "uptime_seconds": metrics["uptime_seconds"],
            "timestamp": metrics["timestamp"]
        }
        
        # Add key metrics summary
        key_metrics = {}
        
        # Dual queries
        dual_queries = metrics["counters"].get("dual_queries_total", [])
        if dual_queries:
            key_metrics["dual_queries_total"] = sum(c["value"] for c in dual_queries)
        
        # Legacy queries
        legacy_queries = metrics["counters"].get("legacy_queries_total", [])
        if legacy_queries:
            key_metrics["legacy_queries_total"] = sum(c["value"] for c in legacy_queries)
        
        # Cache hits/misses
        cache_hits = metrics["counters"].get("cache_hits_total", [])
        cache_misses = metrics["counters"].get("cache_misses_total", [])
        if cache_hits or cache_misses:
            total_hits = sum(c["value"] for c in cache_hits)
            total_misses = sum(c["value"] for c in cache_misses)
            key_metrics["cache_hit_rate"] = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0.0
            key_metrics["cache_hits_total"] = total_hits
            key_metrics["cache_misses_total"] = total_misses
        
        # Contradiction detection
        contradiction_detections = metrics["counters"].get("contradiction_detections_total", [])
        if contradiction_detections:
            key_metrics["contradiction_detections_total"] = sum(c["value"] for c in contradiction_detections)
        
        # LiftScore calculations
        liftscore_calculations = metrics["counters"].get("liftscore_calculations_total", [])
        if liftscore_calculations:
            key_metrics["liftscore_calculations_total"] = sum(c["value"] for c in liftscore_calculations)
        
        # Implicate rankings
        implicate_rankings = metrics["counters"].get("implicate_rankings_total", [])
        if implicate_rankings:
            key_metrics["implicate_rankings_total"] = sum(c["value"] for c in implicate_rankings)
        
        # Feature flag usage
        feature_flag_usage = metrics["counters"].get("feature_flag_usage_total", [])
        if feature_flag_usage:
            key_metrics["feature_flag_usage"] = {c["labels"].get("flag", "unknown"): c["value"] for c in feature_flag_usage}
        
        response = {
            "summary": summary,
            "key_metrics": key_metrics,
            "detailed_metrics": metrics,
            "status": "ok"
        }
        
        # Reset metrics if requested
        if reset:
            reset_metrics()
            response["reset"] = True
        
        return response
        
    except Exception as e:
        return {
            "summary": {},
            "key_metrics": {},
            "detailed_metrics": {},
            "status": "error",
            "error": str(e)
        }

@router.get("/debug/redo_trace")
def debug_redo_trace(
    message_id: str = Query(..., description="Message ID to get REDO trace for"),
    x_api_key: Optional[str] = Header(None)
):
    """Get the last REDO orchestration trace for a given message ID."""
    _require_key(x_api_key)
    
    try:
        # Query the rheomode_runs table for the trace
        result = supabase.table("rheomode_runs").select("*").eq("message_id", message_id).order("created_at", desc=True).limit(1).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="No REDO trace found for message ID")
        
        trace_row = result.data[0]
        
        # Parse the trace data
        trace_data = trace_row.get("trace_data", {})
        
        # Build response
        response = {
            "id": trace_row.get("id"),
            "session_id": trace_row.get("session_id"),
            "message_id": trace_row.get("message_id"),
            "created_at": trace_row.get("created_at"),
            "trace_hash": trace_row.get("trace_hash"),
            "is_truncated": trace_row.get("is_truncated", False),
            "original_size": trace_row.get("original_size", 0),
            "stored_size": trace_row.get("stored_size", 0),
            "trace_data": trace_data,
            "status": "ok"
        }
        
        # Add trace summary if available
        if trace_data:
            stages = trace_data.get("stages", [])
            contradictions = trace_data.get("contradictions", [])
            selected_context_ids = trace_data.get("selected_context_ids", [])
            timings = trace_data.get("timings", {})
            
            response["summary"] = {
                "stages_count": len(stages),
                "contradictions_count": len(contradictions),
                "selected_context_count": len(selected_context_ids),
                "total_time_ms": timings.get("total_ms", 0.0),
                "orchestration_time_ms": timings.get("orchestration_ms", 0.0),
                "planning_time_ms": timings.get("planning_ms", 0.0)
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching REDO trace: {str(e)}")

@router.post("/debug/redo_replay")
def debug_redo_replay(
    message_id: str = Query(..., description="Message ID to replay"),
    write_to_ledger: bool = Query(False, description="Write replay result to ledger"),
    x_api_key: Optional[str] = Header(None)
):
    """Replay a REDO orchestration trace with current code and configuration."""
    _require_key(x_api_key)
    
    try:
        # First, get the original trace
        trace_result = supabase.table("rheomode_runs").select("*").eq("message_id", message_id).order("created_at", desc=True).limit(1).execute()
        
        if not trace_result.data or len(trace_result.data) == 0:
            raise HTTPException(status_code=404, detail="No REDO trace found for message ID")
        
        trace_row = trace_result.data[0]
        trace_data = trace_row.get("trace_data", {})
        
        if not trace_data:
            raise HTTPException(status_code=400, detail="Trace data is empty or invalid")
        
        # Get current feature flags and config
        feature_flags = get_all_flags()
        config = load_config()
        
        # Replay the trace
        if write_to_ledger:
            replay_result = replay_trace_with_ledger(
                trace_data=trace_data,
                session_id=trace_row.get("session_id", ""),
                message_id=message_id,
                feature_flags=feature_flags,
                config=config
            )
        else:
            replay_result = replay_trace(trace_data, feature_flags, config)
        
        # Build response
        response = {
            "message_id": message_id,
            "replay_success": replay_result.success,
            "timing_diff_ms": replay_result.timing_diff_ms,
            "warnings": replay_result.warnings,
            "errors": replay_result.errors,
            "original_trace": {
                "stages_count": len(trace_data.get("stages", [])),
                "contradictions_count": len(trace_data.get("contradictions", [])),
                "selected_context_count": len(trace_data.get("selected_context_ids", [])),
                "total_time_ms": trace_data.get("timings", {}).get("total_ms", 0.0)
            },
            "replayed_trace": {
                "stages_count": len(replay_result.replayed_trace.stages),
                "contradictions_count": len(replay_result.replayed_trace.contradictions),
                "selected_context_count": len(replay_result.replayed_trace.selected_context_ids),
                "total_time_ms": replay_result.replayed_trace.timings.get("total_ms", 0.0),
                "warnings_count": len(replay_result.replayed_trace.warnings)
            },
            "status": "ok"
        }
        
        # Add detailed trace data if requested
        if replay_result.success:
            response["replayed_trace_data"] = replay_result.replayed_trace.to_trace_schema()
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error replaying REDO trace: {str(e)}")

@router.get("/debug/redo_traces")
def debug_redo_traces(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    limit: int = Query(10, ge=1, le=100, description="Number of traces to return"),
    x_api_key: Optional[str] = Header(None)
):
    """Get a list of REDO orchestration traces."""
    _require_key(x_api_key)
    
    try:
        # Build query
        query = supabase.table("rheomode_runs").select("id,session_id,message_id,created_at,is_truncated,original_size,stored_size").order("created_at", desc=True).limit(limit)
        
        if session_id:
            query = query.eq("session_id", session_id)
        
        result = query.execute()
        
        if not result.data:
            return {
                "traces": [],
                "count": 0,
                "status": "ok"
            }
        
        # Format response
        traces = []
        for row in result.data:
            traces.append({
                "id": row.get("id"),
                "session_id": row.get("session_id"),
                "message_id": row.get("message_id"),
                "created_at": row.get("created_at"),
                "is_truncated": row.get("is_truncated", False),
                "original_size": row.get("original_size", 0),
                "stored_size": row.get("stored_size", 0)
            })
        
        return {
            "traces": traces,
            "count": len(traces),
            "status": "ok"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching REDO traces: {str(e)}")
