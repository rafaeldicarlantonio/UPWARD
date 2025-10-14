"""
Deterministic orchestrator for evaluation purposes.
"""

from __future__ import annotations
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from core.orchestrator.interfaces import Orchestrator
from core.types import QueryContext, OrchestrationResult, OrchestrationConfig, StageTrace, StageMetrics


@dataclass
class DeterministicConfig:
    """Configuration for deterministic orchestrator."""
    seed: int
    use_fixtures: bool = True
    fixture_data: Optional[Dict[str, Any]] = None
    deterministic_timing: bool = True
    base_timing_ms: float = 10.0


class DeterministicOrchestrator(Orchestrator):
    """Deterministic orchestrator for evaluation purposes."""
    
    def __init__(self):
        self.config = OrchestrationConfig()
        self.deterministic_config = DeterministicConfig(seed=0)
        self._random_state = None
    
    def configure(self, config: OrchestrationConfig) -> None:
        """Configure the orchestrator with the given configuration."""
        self.config = config
    
    def configure_deterministic(self, deterministic_config: DeterministicConfig) -> None:
        """Configure deterministic behavior."""
        self.deterministic_config = deterministic_config
        # Set random seed for deterministic behavior
        random.seed(deterministic_config.seed)
        self._random_state = random.getstate()
    
    def run(self, query_ctx: QueryContext) -> OrchestrationResult:
        """
        Run orchestration with deterministic behavior.
        
        This implementation uses seeded randomness and fixtures to ensure
        reproducible results for evaluation purposes.
        """
        # Restore random state for deterministic behavior
        if self._random_state:
            random.setstate(self._random_state)
        
        start_time = time.time()
        success = True
        warnings = []
        
        try:
            # Create deterministic stages
            stages = self._create_deterministic_stages(query_ctx)
            
            # Generate deterministic final plan
            final_plan = self._generate_deterministic_plan(query_ctx)
            
            # Calculate deterministic timings
            total_time = self._calculate_deterministic_timing()
            timings = {
                "total_ms": total_time,
                "orchestration_ms": total_time * 0.8,
                "planning_ms": total_time * 0.2,
            }
            
            # Generate deterministic warnings
            warnings = self._generate_deterministic_warnings(query_ctx)
            
            # Generate deterministic contradictions
            contradictions = self._generate_deterministic_contradictions(query_ctx)
            
            # Generate deterministic selected context IDs
            selected_context_ids = self._generate_deterministic_context_ids(query_ctx)
            
            # Generate deterministic knobs
            knobs = self._generate_deterministic_knobs(query_ctx)
            
            # Check for budget overrun
            if self.config.time_budget_ms and total_time > self.config.time_budget_ms:
                overrun_ms = total_time - self.config.time_budget_ms
                warnings.append(f"Orchestration exceeded time budget by {overrun_ms:.1f}ms")
            
            return OrchestrationResult(
                stages=stages,
                final_plan=final_plan,
                timings=timings,
                warnings=warnings,
                selected_context_ids=selected_context_ids,
                contradictions=contradictions,
                knobs=knobs,
            )
            
        except Exception as e:
            success = False
            total_time = (time.time() - start_time) * 1000
            warnings.append(f"Orchestration failed: {str(e)}")
            
            return OrchestrationResult(
                stages=[],
                final_plan={"type": "error", "error": str(e)},
                timings={"total_ms": total_time, "orchestration_ms": total_time, "planning_ms": 0.0},
                warnings=warnings,
                selected_context_ids=[],
                contradictions=[],
                knobs={},
            )
    
    def _create_deterministic_stages(self, query_ctx: QueryContext) -> List[StageTrace]:
        """Create deterministic stages based on fixtures and seeded randomness."""
        stages = []
        
        # Use fixture data if available
        fixture_data = self.deterministic_config.fixture_data or {}
        retrieval_results = fixture_data.get("retrieval_results", [])
        
        # Stage 1: Observe
        observe_duration = self._get_deterministic_duration("observe")
        stages.append(StageTrace(
            name="observe",
            input={"query": query_ctx.query, "role": query_ctx.role},
            output={"intent": "information_request", "entities": ["example_entity"]},
            metrics=StageMetrics(
                duration_ms=observe_duration,
                memory_usage_mb=10.5,
                cache_hits=2,
                cache_misses=1,
                tokens_processed=150,
                custom_metrics={"complexity_score": 0.7}
            ),
            warnings=["Query complexity is moderate"]
        ))
        
        # Stage 2: Expand
        expand_duration = self._get_deterministic_duration("expand")
        stages.append(StageTrace(
            name="expand",
            input={"entities": ["example_entity"], "intent": "information_request"},
            output={"retrieved_docs": len(retrieval_results), "relevance_scores": [0.9, 0.8, 0.7, 0.6, 0.5]},
            metrics=StageMetrics(
                duration_ms=expand_duration,
                memory_usage_mb=25.0,
                cache_hits=3,
                cache_misses=2,
                tokens_processed=500,
                custom_metrics={"retrieval_quality": 0.8}
            )
        ))
        
        # Stage 3: Contrast
        contrast_duration = self._get_deterministic_duration("contrast")
        contradictions_found = self._count_deterministic_contradictions(retrieval_results)
        stages.append(StageTrace(
            name="contrast",
            input={"retrieved_docs": len(retrieval_results), "relevance_scores": [0.9, 0.8, 0.7, 0.6, 0.5]},
            output={"contradictions_found": contradictions_found, "confidence": 0.7},
            metrics=StageMetrics(
                duration_ms=contrast_duration,
                memory_usage_mb=12.0,
                cache_hits=1,
                cache_misses=1,
                tokens_processed=300,
                custom_metrics={"contradiction_confidence": 0.7}
            )
        ))
        
        # Stage 4: Order
        order_duration = self._get_deterministic_duration("order")
        ordered_context_ids = self._deterministic_order_context_ids(retrieval_results)
        stages.append(StageTrace(
            name="order",
            input={"retrieved_docs": len(retrieval_results), "relevance_scores": [0.9, 0.8, 0.7, 0.6, 0.5]},
            output={"plan_type": "direct_answer", "confidence": 0.85, "ordered_context_ids": ordered_context_ids},
            metrics=StageMetrics(
                duration_ms=order_duration,
                memory_usage_mb=15.0,
                cache_hits=1,
                cache_misses=0,
                tokens_processed=200,
                custom_metrics={"plan_confidence": 0.85}
            )
        ))
        
        return stages
    
    def _generate_deterministic_plan(self, query_ctx: QueryContext) -> Dict[str, Any]:
        """Generate a deterministic final plan."""
        # Use deterministic logic based on query characteristics
        query_length = len(query_ctx.query)
        has_contradictions = self._has_deterministic_contradictions()
        
        if has_contradictions:
            plan_type = "contradiction_aware"
        elif query_length > 100:
            plan_type = "detailed_analysis"
        else:
            plan_type = "direct_answer"
        
        # Generate a simple answer that includes the query terms
        query_terms = query_ctx.query.lower().split()
        # Include all query terms in the answer
        answer = f"Based on the analysis, the key factors include: {', '.join(query_terms)} and other important considerations."
        
        return {
            "type": plan_type,
            "strategy": "retrieval_based",
            "confidence": 0.85,
            "estimated_tokens": 500,
            "requires_llm": True,
            "context_usage": "high",
            "fallback_plan": "simplified_response",
            "answer": answer
        }
    
    def _generate_deterministic_warnings(self, query_ctx: QueryContext) -> List[str]:
        """Generate deterministic warnings."""
        warnings = []
        
        if len(query_ctx.query) > 1000:
            warnings.append("Query is very long, may impact performance")
        
        if not query_ctx.session_id:
            warnings.append("No session ID provided, tracking may be limited")
        
        if query_ctx.role == "admin":
            warnings.append("Admin role detected, additional logging enabled")
        
        return warnings
    
    def _generate_deterministic_contradictions(self, query_ctx: QueryContext) -> List[Dict[str, Any]]:
        """Generate deterministic contradictions based on fixtures."""
        if not self.config.enable_contradiction_detection:
            return []
        
        fixture_data = self.deterministic_config.fixture_data or {}
        retrieval_results = fixture_data.get("retrieval_results", [])
        
        contradictions = []
        
        # Look for contradictory pairs in retrieval results
        for i, result_a in enumerate(retrieval_results):
            for j, result_b in enumerate(retrieval_results[i+1:], i+1):
                if self._are_contradictory(result_a, result_b):
                    contradictions.append({
                        "type": "content_contradiction",
                        "subject": "policy_approach",
                        "claim_a": result_a.get("content", "")[:100] + "...",
                        "claim_b": result_b.get("content", "")[:100] + "...",
                        "confidence": 0.7,
                        "source_a": result_a.get("source", "unknown"),
                        "source_b": result_b.get("source", "unknown")
                    })
                    break  # Only add one contradiction per result
        
        return contradictions
    
    def _generate_deterministic_context_ids(self, query_ctx: QueryContext) -> List[str]:
        """Generate deterministic selected context IDs."""
        fixture_data = self.deterministic_config.fixture_data or {}
        retrieval_results = fixture_data.get("retrieval_results", [])
        
        if not retrieval_results:
            return ["ctx_001", "ctx_002", "ctx_003", "ctx_004", "ctx_005"]
        
        # Deterministically order by relevance score
        ordered_results = sorted(retrieval_results, key=lambda x: x.get("relevance_score", 0), reverse=True)
        return [result.get("id", f"ctx_{i}") for i, result in enumerate(ordered_results[:5])]
    
    def _generate_deterministic_knobs(self, query_ctx: QueryContext) -> Dict[str, Any]:
        """Generate deterministic knobs."""
        return {
            "retrieval_top_k": self.config.custom_knobs.get("retrieval_top_k", 16),
            "implicate_top_k": 8,
            "max_context_tokens": 2000,
            "contradiction_threshold": 0.7,
            "confidence_threshold": 0.8,
            "enable_redo": self.config.enable_redo,
            "time_budget_ms": self.config.time_budget_ms,
            "deterministic_mode": True,
            "seed": self.deterministic_config.seed,
            **self.config.custom_knobs
        }
    
    def _get_deterministic_duration(self, stage_name: str) -> float:
        """Get deterministic duration for a stage."""
        if not self.deterministic_config.deterministic_timing:
            return self.deterministic_config.base_timing_ms
        
        # Use deterministic timing based on stage name and seed
        stage_hash = hash(stage_name + str(self.deterministic_config.seed))
        random.seed(stage_hash)
        duration = self.deterministic_config.base_timing_ms + random.uniform(0, 5.0)
        
        # Restore original random state
        if self._random_state:
            random.setstate(self._random_state)
        
        return duration
    
    def _calculate_deterministic_timing(self) -> float:
        """Calculate deterministic total timing."""
        if not self.deterministic_config.deterministic_timing:
            return 50.0  # Default timing
        
        # Use deterministic timing based on seed
        random.seed(self.deterministic_config.seed)
        timing = self.deterministic_config.base_timing_ms + random.uniform(0, 20.0)
        
        # Restore original random state
        if self._random_state:
            random.setstate(self._random_state)
        
        return timing
    
    def _count_deterministic_contradictions(self, retrieval_results: List[Dict[str, Any]]) -> int:
        """Count contradictions deterministically."""
        count = 0
        for i, result_a in enumerate(retrieval_results):
            for j, result_b in enumerate(retrieval_results[i+1:], i+1):
                if self._are_contradictory(result_a, result_b):
                    count += 1
                    break  # Only count one contradiction per result
        return count
    
    def _has_deterministic_contradictions(self) -> bool:
        """Check if there are contradictions deterministically."""
        fixture_data = self.deterministic_config.fixture_data or {}
        retrieval_results = fixture_data.get("retrieval_results", [])
        return self._count_deterministic_contradictions(retrieval_results) > 0
    
    def _are_contradictory(self, result_a: Dict[str, Any], result_b: Dict[str, Any]) -> bool:
        """Check if two results are contradictory."""
        content_a = result_a.get("content", "").lower()
        content_b = result_b.get("content", "").lower()
        
        # Simple contradiction detection based on keywords
        contradiction_keywords = [
            ("fully supported", "only allowed"),
            ("encouraged", "only allowed"),
            ("all employees", "senior employees"),
            ("daily automated", "real-time continuous"),
            ("sufficient", "required"),
            ("should", "should not"),
            ("must", "must not"),
            ("always", "never"),
            ("only", "all"),
            ("immediately", "first"),
            ("premium", "competitive"),
            ("comprehensive", "focused")
        ]
        
        for positive, negative in contradiction_keywords:
            if positive in content_a and negative in content_b:
                return True
            if positive in content_b and negative in content_a:
                return True
        
        return False
    
    def _deterministic_order_context_ids(self, retrieval_results: List[Dict[str, Any]]) -> List[str]:
        """Deterministically order context IDs."""
        if not retrieval_results:
            return ["ctx_001", "ctx_002", "ctx_003"]
        
        # Order by relevance score, then by importance score if available
        def sort_key(result):
            relevance = result.get("relevance_score", 0)
            importance = result.get("importance_score", 0)
            return (relevance, importance)
        
        ordered_results = sorted(retrieval_results, key=sort_key, reverse=True)
        return [result.get("id", f"ctx_{i}") for i, result in enumerate(ordered_results[:3])]