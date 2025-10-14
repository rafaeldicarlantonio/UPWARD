"""
Replay functionality for REDO orchestration traces.
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.orchestrator.redo import RedoOrchestrator
from core.types import QueryContext, OrchestrationConfig, OrchestrationResult
from core.ledger import write_ledger, LedgerOptions


@dataclass
class ReplayResult:
    """Result of a replay operation."""
    original_trace: Dict[str, Any]
    replayed_trace: OrchestrationResult
    timing_diff_ms: float
    success: bool
    warnings: List[str]
    errors: List[str]


class OrchestrationReplayer:
    """Replays orchestration traces with current code and configuration."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.orchestrator = RedoOrchestrator()
        self.config = config or {}
    
    def replay_trace(self, trace_data: Dict[str, Any], feature_flags: Optional[Dict[str, bool]] = None) -> ReplayResult:
        """
        Replay an orchestration trace with current code and configuration.
        
        Args:
            trace_data: Original trace data from the database
            feature_flags: Optional feature flags dictionary
            
        Returns:
            ReplayResult with comparison and timing information
        """
        start_time = time.time()
        warnings = []
        errors = []
        
        try:
            # Extract original timing for comparison
            original_timing = trace_data.get("timings", {})
            original_total_ms = original_timing.get("total_ms", 0.0)
            
            # Reconstruct query context from trace data
            query_context = self._reconstruct_query_context(trace_data)
            
            # Get feature flags with defaults
            flags = feature_flags or {}
            use_contradictions = flags.get("retrieval.contradictions_pack", False)
            use_dual_retrieval = flags.get("retrieval.dual_index", False)
            use_liftscore = flags.get("retrieval.liftscore", False)
            
            # Configure orchestrator with current settings
            orchestration_config = OrchestrationConfig(
                enable_contradiction_detection=use_contradictions,
                enable_redo=True,
                time_budget_ms=self.config.get("ORCHESTRATION_TIME_BUDGET_MS", 400),
                max_trace_bytes=self.config.get("LEDGER_MAX_TRACE_BYTES", 100_000),
                custom_knobs={
                    "retrieval_top_k": self.config.get("TOPK_PER_TYPE", 16),
                    "implicate_top_k": 8,
                    "use_dual_retrieval": use_dual_retrieval,
                    "use_liftscore": use_liftscore,
                    "use_contradictions": use_contradictions
                }
            )
            
            self.orchestrator.configure(orchestration_config)
            
            # Run orchestration with current code
            replayed_trace = self.orchestrator.run(query_context)
            
            # Calculate timing difference
            replay_time_ms = (time.time() - start_time) * 1000
            timing_diff_ms = replay_time_ms - original_total_ms
            
            # Generate warnings for significant differences
            if abs(timing_diff_ms) > 100:  # More than 100ms difference
                if timing_diff_ms > 0:
                    warnings.append(f"Replay was {timing_diff_ms:.1f}ms slower than original")
                else:
                    warnings.append(f"Replay was {abs(timing_diff_ms):.1f}ms faster than original")
            
            # Compare stage counts
            original_stages = len(trace_data.get("stages", []))
            replayed_stages = len(replayed_trace.stages)
            if original_stages != replayed_stages:
                warnings.append(f"Stage count changed: {original_stages} -> {replayed_stages}")
            
            # Compare contradiction counts
            original_contradictions = len(trace_data.get("contradictions", []))
            replayed_contradictions = len(replayed_trace.contradictions)
            if original_contradictions != replayed_contradictions:
                warnings.append(f"Contradiction count changed: {original_contradictions} -> {replayed_contradictions}")
            
            return ReplayResult(
                original_trace=trace_data,
                replayed_trace=replayed_trace,
                timing_diff_ms=timing_diff_ms,
                success=True,
                warnings=warnings,
                errors=[]
            )
            
        except Exception as e:
            errors.append(f"Replay failed: {str(e)}")
            return ReplayResult(
                original_trace=trace_data,
                replayed_trace=OrchestrationResult(),  # Empty result
                timing_diff_ms=0.0,
                success=False,
                warnings=warnings,
                errors=errors
            )
    
    def _reconstruct_query_context(self, trace_data: Dict[str, Any]) -> QueryContext:
        """Reconstruct QueryContext from trace data."""
        # Extract basic information
        query = trace_data.get("query", "")
        session_id = trace_data.get("session_id", "")
        role = trace_data.get("role", "user")
        
        # Extract metadata
        metadata = trace_data.get("metadata", {})
        
        # Extract user preferences (if available)
        preferences = trace_data.get("preferences", {})
        
        # Extract user ID (if available)
        user_id = trace_data.get("user_id", "")
        
        return QueryContext(
            query=query,
            session_id=session_id,
            user_id=user_id,
            role=role,
            preferences=preferences,
            metadata=metadata
        )
    
    def replay_with_ledger(self, trace_data: Dict[str, Any], session_id: str, message_id: str, feature_flags: Optional[Dict[str, bool]] = None) -> ReplayResult:
        """
        Replay a trace and optionally write to ledger.
        
        Args:
            trace_data: Original trace data
            session_id: Session ID for ledger entry
            message_id: Message ID for ledger entry
            feature_flags: Optional feature flags dictionary
            
        Returns:
            ReplayResult with ledger information
        """
        # Run the replay
        result = self.replay_trace(trace_data, feature_flags)
        
        # Write to ledger if enabled
        flags = feature_flags or {}
        if flags.get("ledger.enabled", False) and result.success:
            try:
                ledger_options = LedgerOptions(
                    max_trace_bytes=self.config.get("LEDGER_MAX_TRACE_BYTES", 100_000),
                    enable_hashing=True,
                    redact_large_fields=True,
                    hash_algorithm="sha256"
                )
                
                ledger_entry = write_ledger(
                    session_id=session_id,
                    message_id=f"{message_id}_replay",
                    trace=result.replayed_trace,
                    options=ledger_options
                )
                
                result.warnings.append(f"Replay written to ledger: {ledger_entry.stored_size} bytes")
                
            except Exception as e:
                result.warnings.append(f"Failed to write replay to ledger: {str(e)}")
        
        return result


def replay_trace(trace_data: Dict[str, Any], feature_flags: Optional[Dict[str, bool]] = None, config: Optional[Dict[str, Any]] = None) -> ReplayResult:
    """
    Convenience function to replay a trace.
    
    Args:
        trace_data: Original trace data from the database
        feature_flags: Optional feature flags dictionary
        config: Optional configuration dictionary
        
    Returns:
        ReplayResult with comparison and timing information
    """
    replayer = OrchestrationReplayer(config)
    return replayer.replay_trace(trace_data, feature_flags)


def replay_trace_with_ledger(trace_data: Dict[str, Any], session_id: str, message_id: str, feature_flags: Optional[Dict[str, bool]] = None, config: Optional[Dict[str, Any]] = None) -> ReplayResult:
    """
    Convenience function to replay a trace with ledger writing.
    
    Args:
        trace_data: Original trace data from the database
        session_id: Session ID for ledger entry
        message_id: Message ID for ledger entry
        feature_flags: Optional feature flags dictionary
        config: Optional configuration dictionary
        
    Returns:
        ReplayResult with ledger information
    """
    replayer = OrchestrationReplayer(config)
    return replayer.replay_with_ledger(trace_data, session_id, message_id, feature_flags)