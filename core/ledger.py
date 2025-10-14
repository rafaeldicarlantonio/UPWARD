# core/ledger.py — rheomode_runs persistence and tracing

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from vendors.supabase_client import get_client
from feature_flags import get_feature_flag

@dataclass
class ProcessTrace:
    """Process trace data for rheomode_runs."""
    flags: Dict[str, bool]
    query: str
    candidates: List[Dict[str, Any]]
    contradictions: List[Dict[str, Any]]
    timing: Dict[str, float]
    strategy_used: str
    metadata: Dict[str, Any]

@dataclass
class RheomodeRun:
    """Rheomode run record."""
    id: Optional[str] = None
    session_id: str = ""
    message_id: Optional[str] = None
    role: str = "user"
    process_trace: Optional[ProcessTrace] = None
    process_trace_summary: Optional[str] = None
    lift_score: Optional[float] = None
    contradiction_score: Optional[float] = None
    created_at: Optional[datetime] = None

class RheomodeLedger:
    """Manages rheomode_runs persistence and tracing."""
    
    def __init__(self):
        self.client = get_client()
    
    def create_run(self, 
                   session_id: str,
                   message_id: Optional[str] = None,
                   role: str = "user",
                   process_trace: Optional[ProcessTrace] = None,
                   lift_score: Optional[float] = None,
                   contradiction_score: Optional[float] = None) -> RheomodeRun:
        """Create a new rheomode run record."""
        
        # Generate process trace summary
        process_trace_summary = None
        if process_trace:
            process_trace_summary = self._generate_trace_summary(process_trace)
        
        # Create the run record
        run = RheomodeRun(
            session_id=session_id,
            message_id=message_id,
            role=role,
            process_trace=process_trace,
            process_trace_summary=process_trace_summary,
            lift_score=lift_score,
            contradiction_score=contradiction_score,
            created_at=datetime.now(timezone.utc)
        )
        
        return run
    
    def persist_run(self, run: RheomodeRun) -> str:
        """Persist a rheomode run to the database."""
        try:
            # Convert process trace to dict for JSON serialization
            process_trace_dict = None
            if run.process_trace:
                process_trace_dict = asdict(run.process_trace)
            
            # Prepare data for insertion
            data = {
                "session_id": run.session_id,
                "message_id": run.message_id,
                "role": run.role,
                "process_trace": process_trace_dict or {},
                "process_trace_summary": run.process_trace_summary,
                "lift_score": run.lift_score,
                "contradiction_score": run.contradiction_score
            }
            
            # Insert into database
            result = self.client.table("rheomode_runs").insert(data).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            else:
                raise RuntimeError("Failed to insert rheomode run")
                
        except Exception as e:
            raise RuntimeError(f"Failed to persist rheomode run: {e}")
    
    def get_run_by_message_id(self, message_id: str) -> Optional[RheomodeRun]:
        """Get the last rheomode run for a given message ID."""
        try:
            result = self.client.table("rheomode_runs")\
                .select("*")\
                .eq("message_id", message_id)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            
            if result.data and len(result.data) > 0:
                row = result.data[0]
                return self._row_to_run(row)
            else:
                return None
                
        except Exception as e:
            print(f"Error fetching rheomode run: {e}")
            return None
    
    def get_runs_by_session(self, session_id: str, limit: int = 10) -> List[RheomodeRun]:
        """Get rheomode runs for a session."""
        try:
            result = self.client.table("rheomode_runs")\
                .select("*")\
                .eq("session_id", session_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            runs = []
            if result.data:
                for row in result.data:
                    runs.append(self._row_to_run(row))
            
            return runs
            
        except Exception as e:
            print(f"Error fetching session runs: {e}")
            return []
    
    def _generate_trace_summary(self, process_trace: ProcessTrace) -> str:
        """Generate a 2-4 line process trace summary."""
        lines = []
        
        # Line 1: Strategy and basic stats
        strategy = process_trace.strategy_used
        candidate_count = len(process_trace.candidates)
        contradiction_count = len(process_trace.contradictions)
        
        lines.append(f"Used {strategy} strategy with {candidate_count} candidates")
        
        # Line 2: Contradictions and scores
        if contradiction_count > 0:
            lines.append(f"Detected {contradiction_count} contradictions")
        else:
            lines.append("No contradictions detected")
        
        # Line 3: Timing information
        timing = process_trace.timing
        total_time = timing.get("total_ms", 0)
        retrieval_time = timing.get("retrieval_ms", 0)
        
        lines.append(f"Total: {total_time:.1f}ms, Retrieval: {retrieval_time:.1f}ms")
        
        # Line 4: Feature flags (if any are enabled)
        enabled_flags = [k for k, v in process_trace.flags.items() if v]
        if enabled_flags:
            lines.append(f"Flags: {', '.join(enabled_flags)}")
        
        # Ensure we have 2-4 lines
        if len(lines) < 2:
            lines.append("Process completed successfully")
        if len(lines) > 4:
            lines = lines[:4]
        
        return "\n".join(lines)
    
    def _row_to_run(self, row: Dict[str, Any]) -> RheomodeRun:
        """Convert database row to RheomodeRun object."""
        # Parse process trace
        process_trace = None
        if row.get("process_trace"):
            trace_data = row["process_trace"]
            if isinstance(trace_data, dict):
                process_trace = ProcessTrace(
                    flags=trace_data.get("flags", {}),
                    query=trace_data.get("query", ""),
                    candidates=trace_data.get("candidates", []),
                    contradictions=trace_data.get("contradictions", []),
                    timing=trace_data.get("timing", {}),
                    strategy_used=trace_data.get("strategy_used", "unknown"),
                    metadata=trace_data.get("metadata", {})
                )
        
        # Parse created_at
        created_at = None
        if row.get("created_at"):
            try:
                if isinstance(row["created_at"], str):
                    created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                else:
                    created_at = row["created_at"]
            except Exception:
                pass
        
        return RheomodeRun(
            id=row.get("id"),
            session_id=row.get("session_id", ""),
            message_id=row.get("message_id"),
            role=row.get("role", "user"),
            process_trace=process_trace,
            process_trace_summary=row.get("process_trace_summary"),
            lift_score=row.get("lift_score"),
            contradiction_score=row.get("contradiction_score"),
            created_at=created_at
        )

def create_process_trace(query: str,
                        selection_result: Any,
                        contradictions: List[Any],
                        timing: Dict[str, float],
                        **kwargs) -> ProcessTrace:
    """Create a process trace from selection results and other data."""
    
    # Get current feature flags
    flags = {
        "retrieval.dual_index": get_feature_flag("retrieval.dual_index", default=False),
        "retrieval.liftscore": get_feature_flag("retrieval.liftscore", default=False),
        "retrieval.contradictions_pack": get_feature_flag("retrieval.contradictions_pack", default=False)
    }
    
    # Extract candidates with scores and reasons
    candidates = []
    if hasattr(selection_result, 'context'):
        for i, item in enumerate(selection_result.context):
            candidate = {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "type": item.get("type", "semantic"),
                "source": item.get("source", "unknown"),
                "score": item.get("score", 0.0),
                "lift_score": item.get("lift_score", 0.0),
                "reason": selection_result.reasons[i] if i < len(selection_result.reasons) else "No reason provided",
                "has_contradictions": item.get("has_contradictions", False)
            }
            candidates.append(candidate)
    
    # Convert contradictions to dict format
    contradictions_dict = []
    for contradiction in contradictions:
        if hasattr(contradiction, '__dict__'):
            contradictions_dict.append(asdict(contradiction))
        elif isinstance(contradiction, dict):
            contradictions_dict.append(contradiction)
    
    # Extract metadata
    metadata = getattr(selection_result, 'metadata', {})
    
    return ProcessTrace(
        flags=flags,
        query=query,
        candidates=candidates,
        contradictions=contradictions_dict,
        timing=timing,
        strategy_used=getattr(selection_result, 'strategy_used', 'unknown'),
        metadata=metadata
    )

# Convenience functions
def log_chat_request(session_id: str,
                    message_id: Optional[str] = None,
                    role: str = "user",
                    query: str = "",
                    selection_result: Any = None,
                    contradictions: List[Any] = None,
                    timing: Dict[str, float] = None,
                    **kwargs) -> Optional[str]:
    """Log a chat request to rheomode_runs."""
    
    # Only log if dual_index is enabled
    if not get_feature_flag("retrieval.dual_index", default=False):
        return None
    
    try:
        ledger = RheomodeLedger()
        
        # Create process trace
        process_trace = None
        if selection_result and timing:
            process_trace = create_process_trace(
                query=query,
                selection_result=selection_result,
                contradictions=contradictions or [],
                timing=timing,
                **kwargs
            )
        
        # Create and persist run
        run = ledger.create_run(
            session_id=session_id,
            message_id=message_id,
            role=role,
            process_trace=process_trace,
            lift_score=kwargs.get('lift_score'),
            contradiction_score=kwargs.get('contradiction_score')
        )
        
        return ledger.persist_run(run)
        
    except Exception as e:
        print(f"Failed to log chat request: {e}")
        return None