"""
Ledger writer for storing orchestration traces with size enforcement.
"""

from __future__ import annotations
import hashlib
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from core.types import OrchestrationResult
from core.metrics import LedgerMetrics, time_operation


@dataclass
class LedgerOptions:
    """Options for ledger writing."""
    max_trace_bytes: int = 100_000
    enable_hashing: bool = True
    redact_large_fields: bool = True
    hash_algorithm: str = "sha256"


@dataclass
class LedgerEntry:
    """A ledger entry for storage."""
    session_id: str
    message_id: str
    trace_data: Dict[str, Any]
    trace_hash: Optional[str] = None
    is_truncated: bool = False
    original_size: int = 0
    stored_size: int = 0
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


def write_ledger(
    session_id: str,
    message_id: str, 
    trace: OrchestrationResult,
    options: Optional[LedgerOptions] = None
) -> LedgerEntry:
    """
    Write orchestration trace to ledger with size enforcement.
    
    Args:
        session_id: Session identifier
        message_id: Message identifier
        trace: OrchestrationResult to store
        options: Ledger options for size limits and behavior
        
    Returns:
        LedgerEntry with trace data and metadata
    """
    if options is None:
        options = LedgerOptions()
    
    with time_operation("ledger_write", {"session_id": session_id}):
        # Convert trace to JSON-serializable format
        trace_data = trace.to_trace_schema()
        original_size = len(json.dumps(trace_data, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
        
        # Check if trace exceeds size limit
        if original_size > options.max_trace_bytes:
            trace_data, is_truncated = _truncate_trace(trace_data, options.max_trace_bytes)
            stored_size = len(json.dumps(trace_data, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
            
            # Record truncation metrics
            truncation_ratio = stored_size / max(original_size, 1)
            LedgerMetrics.record_ledger_truncation(original_size, stored_size, truncation_ratio)
        else:
            is_truncated = False
            stored_size = original_size
        
        # Generate hash if enabled
        trace_hash = None
        if options.enable_hashing:
            hash_start = time.time()
            trace_hash = _generate_trace_hash(trace_data, options.hash_algorithm)
            hash_latency = (time.time() - hash_start) * 1000
            LedgerMetrics.record_ledger_hash_generation(options.hash_algorithm, stored_size, hash_latency)
        
        # Create ledger entry
        entry = LedgerEntry(
            session_id=session_id,
            message_id=message_id,
            trace_data=trace_data,
            trace_hash=trace_hash,
            is_truncated=is_truncated,
            original_size=original_size,
            stored_size=stored_size,
        )
        
        # Record ledger metrics
        LedgerMetrics.record_bytes_written(stored_size, is_truncated)
        LedgerMetrics.record_ledger_entry(session_id, message_id, stored_size, is_truncated)
        
        # In a real implementation, this would insert into the database
        # For now, we'll simulate the database operation
        _simulate_db_insert(entry)
        
        return entry


def _truncate_trace(trace_data: Dict[str, Any], max_bytes: int) -> tuple[Dict[str, Any], bool]:
    """
    Truncate trace data to fit within size limit.
    
    Args:
        trace_data: Original trace data
        max_bytes: Maximum allowed size in bytes
        
    Returns:
        Tuple of (truncated_trace_data, was_truncated)
    """
    # Start with minimal structure
    minimal_data = {
        "version": trace_data.get("version", "1.0"),
        "stages": [],
        "knobs": trace_data.get("knobs", {}),
        "contradictions": trace_data.get("contradictions", []),
        "selected_context_ids": trace_data.get("selected_context_ids", []),
        "final_plan": trace_data.get("final_plan", {}),
        "timings": trace_data.get("timings", {}),
        "warnings": trace_data.get("warnings", []),
        "timestamp": trace_data.get("timestamp", datetime.utcnow().isoformat()),
    }
    
    # Calculate base size
    base_json = json.dumps(minimal_data, separators=(',', ':'), ensure_ascii=False)
    base_size = len(base_json.encode('utf-8'))
    
    if base_size > max_bytes:
        # If base structure is too large, create minimal version
        minimal_data = {
            "version": "1.0",
            "stages": [],
            "knobs": {},
            "contradictions": [],
            "selected_context_ids": [],
            "final_plan": {},
            "timings": {},
            "warnings": [],
            "timestamp": datetime.utcnow().isoformat(),
        }
        # Add truncation metadata for extreme truncation
        minimal_data["_truncation"] = {
            "original_stages_count": len(trace_data.get("stages", [])),
            "truncated_stages_count": 0,
            "truncated_at": datetime.utcnow().isoformat(),
            "reason": "base_structure_too_large"
        }
        return minimal_data, True
    
    # Add stages until we hit the limit
    truncated_stages = []
    current_size = base_size
    
    for stage in trace_data.get("stages", []):
        # Create a compact stage representation
        compact_stage = _create_compact_stage(stage)
        stage_json = json.dumps(compact_stage, separators=(',', ':'), ensure_ascii=False)
        stage_size = len(stage_json.encode('utf-8'))
        
        # Add space for array separators
        if len(truncated_stages) > 0:
            stage_size += 1  # comma before stage
        
        if current_size + stage_size <= max_bytes:
            truncated_stages.append(compact_stage)
            current_size += stage_size
        else:
            break
    
    minimal_data["stages"] = truncated_stages
    
    # Add truncation metadata if truncation occurred
    was_truncated = len(truncated_stages) < len(trace_data.get("stages", []))
    if was_truncated:
        minimal_data["_truncation"] = {
            "original_stages_count": len(trace_data.get("stages", [])),
            "truncated_stages_count": len(truncated_stages),
            "truncated_at": datetime.utcnow().isoformat(),
        }
    
    return minimal_data, was_truncated


def _create_compact_stage(stage: Dict[str, Any]) -> Dict[str, Any]:
    """Create a compact representation of a stage."""
    return {
        "name": stage.get("name", ""),
        "input": _truncate_dict(stage.get("input", {}), 100),
        "output": _truncate_dict(stage.get("output", {}), 100),
        "metrics": {
            "duration_ms": stage.get("metrics", {}).get("duration_ms", 0.0),
            "tokens_processed": stage.get("metrics", {}).get("tokens_processed"),
        },
        "error": stage.get("error"),
        "warnings": stage.get("warnings", [])[:3],  # Limit warnings
    }


def _truncate_dict(data: Dict[str, Any], max_length: int) -> Dict[str, Any]:
    """Truncate string values in a dictionary."""
    truncated = {}
    for key, value in data.items():
        if isinstance(value, str) and len(value) > max_length:
            truncated[key] = value[:max_length] + "..."
        elif isinstance(value, dict):
            truncated[key] = _truncate_dict(value, max_length)
        elif isinstance(value, list):
            truncated[key] = [_truncate_dict(item, max_length) if isinstance(item, dict) else item for item in value[:5]]  # Limit list items
        else:
            truncated[key] = value
    return truncated


def _generate_trace_hash(trace_data: Dict[str, Any], algorithm: str = "sha256") -> str:
    """Generate hash for trace data."""
    trace_json = json.dumps(trace_data, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
    
    if algorithm == "sha256":
        return hashlib.sha256(trace_json.encode('utf-8')).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(trace_json.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def _simulate_db_insert(entry: LedgerEntry) -> None:
    """
    Simulate database insert operation.
    
    In a real implementation, this would insert into the rheomode_runs table.
    """
    # Simulate database insert
    print(f"Simulated DB insert: session_id={entry.session_id}, message_id={entry.message_id}, size={entry.stored_size} bytes")
    
    # In a real implementation, this would be:
    # supabase.table("rheomode_runs").insert({
    #     "session_id": entry.session_id,
    #     "message_id": entry.message_id,
    #     "trace_data": entry.trace_data,
    #     "trace_hash": entry.trace_hash,
    #     "is_truncated": entry.is_truncated,
    #     "original_size": entry.original_size,
    #     "stored_size": entry.stored_size,
    #     "created_at": entry.created_at.isoformat(),
    # }).execute()


def get_ledger_entry(session_id: str, message_id: str) -> Optional[LedgerEntry]:
    """
    Retrieve a ledger entry by session_id and message_id.
    
    Args:
        session_id: Session identifier
        message_id: Message identifier
        
    Returns:
        LedgerEntry if found, None otherwise
    """
    # In a real implementation, this would query the database
    # For now, return None as we don't have persistent storage
    return None


def list_ledger_entries(session_id: Optional[str] = None, limit: int = 100) -> List[LedgerEntry]:
    """
    List ledger entries with optional filtering.
    
    Args:
        session_id: Optional session filter
        limit: Maximum number of entries to return
        
    Returns:
        List of LedgerEntry objects
    """
    # In a real implementation, this would query the database
    # For now, return empty list as we don't have persistent storage
    return []


def delete_ledger_entry(session_id: str, message_id: str) -> bool:
    """
    Delete a ledger entry.
    
    Args:
        session_id: Session identifier
        message_id: Message identifier
        
    Returns:
        True if deleted, False if not found
    """
    # In a real implementation, this would delete from the database
    # For now, return False as we don't have persistent storage
    return False


def log_chat_request(
    session_id: str,
    message_id: str,
    role: str,
    query: str,
    selection_result: Any,
    contradictions: List[Dict[str, Any]],
    timing: Dict[str, float],
    lift_score: Optional[float] = None,
    contradiction_score: float = 0.0
) -> None:
    """
    Log a chat request with retrieval metadata to rheomode_runs table.
    
    Args:
        session_id: Session identifier
        message_id: Message identifier
        role: User role
        query: User query
        selection_result: Selection result from retrieval
        contradictions: List of contradictions found
        timing: Timing metrics dictionary
        lift_score: Optional lift score
        contradiction_score: Contradiction score
    """
    # Create log entry
    log_entry = {
        "session_id": session_id,
        "message_id": message_id,
        "role": role,
        "query": query[:1000],  # Truncate query
        "selection_metadata": {
            "context_count": len(selection_result.context) if hasattr(selection_result, 'context') else 0,
            "ranked_ids_count": len(selection_result.ranked_ids) if hasattr(selection_result, 'ranked_ids') else 0,
        },
        "contradictions_count": len(contradictions),
        "contradiction_score": contradiction_score,
        "lift_score": lift_score,
        "timing": timing,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # In a real implementation, this would insert into the rheomode_runs table
    # For now, just log it
    print(f"Logged chat request: session_id={session_id}, message_id={message_id}, timing={timing}")
    
    # In a real implementation, this would be:
    # supabase.table("rheomode_runs").insert(log_entry).execute()