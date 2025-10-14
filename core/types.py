"""
Core type definitions for the REDO orchestrator system.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import json


@dataclass
class StageMetrics:
    """Metrics for a single orchestration stage."""
    duration_ms: float
    memory_usage_mb: Optional[float] = None
    cache_hits: int = 0
    cache_misses: int = 0
    tokens_processed: Optional[int] = None
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageTrace:
    """Trace information for a single orchestration stage."""
    name: str
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    metrics: StageMetrics = field(default_factory=StageMetrics)
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    """Result of an orchestration run."""
    stages: List[StageTrace] = field(default_factory=list)
    final_plan: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    selected_context_ids: List[str] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    knobs: Dict[str, Any] = field(default_factory=dict)
    
    def to_trace_schema(self) -> Dict[str, Any]:
        """Convert to JSON-serializable trace schema."""
        return {
            "version": "1.0",
            "stages": [
                {
                    "name": stage.name,
                    "input": stage.input,
                    "output": stage.output,
                    "metrics": {
                        "duration_ms": stage.metrics.duration_ms,
                        "memory_usage_mb": stage.metrics.memory_usage_mb,
                        "cache_hits": stage.metrics.cache_hits,
                        "cache_misses": stage.metrics.cache_misses,
                        "tokens_processed": stage.metrics.tokens_processed,
                        "custom_metrics": stage.metrics.custom_metrics,
                    },
                    "error": stage.error,
                    "warnings": stage.warnings,
                }
                for stage in self.stages
            ],
            "knobs": self.knobs,
            "contradictions": self.contradictions,
            "selected_context_ids": self.selected_context_ids,
            "final_plan": self.final_plan,
            "timings": self.timings,
            "warnings": self.warnings,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def to_json(self, max_bytes: Optional[int] = None) -> str:
        """Convert to JSON string with optional size limit."""
        if not max_bytes:
            trace_data = self.to_trace_schema()
            return json.dumps(trace_data, separators=(',', ':'), ensure_ascii=False)
        
        # Start with minimal structure
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
        
        # Add non-stage data first
        minimal_data["knobs"] = self.knobs
        minimal_data["contradictions"] = self.contradictions
        minimal_data["selected_context_ids"] = self.selected_context_ids
        minimal_data["final_plan"] = self.final_plan
        minimal_data["timings"] = self.timings
        minimal_data["warnings"] = self.warnings
        
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
            return json.dumps(minimal_data, separators=(',', ':'), ensure_ascii=False)
        
        # Add stages until we hit the limit
        remaining_bytes = max_bytes - base_size
        truncated_stages = []
        
        for stage in self.stages:
            stage_data = {
                "name": stage.name,
                "input": stage.input,
                "output": stage.output,
                "metrics": {
                    "duration_ms": stage.metrics.duration_ms,
                    "memory_usage_mb": stage.metrics.memory_usage_mb,
                    "cache_hits": stage.metrics.cache_hits,
                    "cache_misses": stage.metrics.cache_misses,
                    "tokens_processed": stage.metrics.tokens_processed,
                    "custom_metrics": stage.metrics.custom_metrics,
                },
                "error": stage.error,
                "warnings": stage.warnings,
            }
            
            stage_json = json.dumps(stage_data, separators=(',', ':'), ensure_ascii=False)
            stage_size = len(stage_json.encode('utf-8'))
            
            # Add space for array separators and commas
            if len(truncated_stages) > 0:
                stage_size += 1  # comma before stage
            
            if base_size + stage_size <= max_bytes:
                truncated_stages.append(stage_data)
                base_size += stage_size
            else:
                break
        
        minimal_data["stages"] = truncated_stages
        return json.dumps(minimal_data, separators=(',', ':'), ensure_ascii=False)


@dataclass
class QueryContext:
    """Context for a query to be orchestrated."""
    query: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationConfig:
    """Configuration for orchestration runs."""
    max_trace_bytes: int = 100_000
    enable_contradiction_detection: bool = False
    enable_redo: bool = False
    time_budget_ms: int = 400
    max_stages: int = 10
    custom_knobs: Dict[str, Any] = field(default_factory=dict)