#!/usr/bin/env python3
"""
core/graph_expand.py — Bounded graph neighborhood expansion with budgets.

Provides controlled graph traversal with:
- Node budget (max_neighbors)
- Depth budget (max_depth)  
- Time budget (timeout_ms)
- Short-circuit logic when over budget
- Metrics for tracking truncation
"""

import time
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

from config import load_config
from core.metrics import increment_counter, observe_histogram


@dataclass
class GraphExpansionResult:
    """Result of a graph expansion operation."""
    relations: List[Tuple[str, str, float]]  # (relation_type, target_id, weight)
    memories: List[Dict[str, Any]]
    summary: str
    truncated: bool = False
    truncation_reason: Optional[str] = None
    nodes_visited: int = 0
    depth_reached: int = 0
    elapsed_ms: float = 0.0
    budget_exceeded: Dict[str, bool] = field(default_factory=dict)


class GraphExpander:
    """Bounded graph expansion with node/time caps."""
    
    def __init__(
        self,
        max_neighbors: int = 50,
        max_depth: int = 1,
        timeout_ms: Optional[float] = None
    ):
        """
        Initialize graph expander with budgets.
        
        Args:
            max_neighbors: Maximum number of neighbor nodes to expand
            max_depth: Maximum depth of graph traversal
            timeout_ms: Timeout in milliseconds (from config if None)
        """
        self.max_neighbors = max_neighbors
        self.max_depth = max_depth
        
        # Load timeout from config if not provided
        if timeout_ms is None:
            try:
                cfg = load_config()
                self.timeout_ms = cfg.get('PERF_GRAPH_TIMEOUT_MS', 150)
            except Exception:
                self.timeout_ms = 150  # Default 150ms
        else:
            self.timeout_ms = timeout_ms
    
    def expand_entity(
        self,
        entity_id: str,
        db_adapter: Any,
        caller_role: Optional[str] = None,
        caller_roles: Optional[List[str]] = None
    ) -> GraphExpansionResult:
        """
        Expand entity neighborhood with bounded search.
        
        Args:
            entity_id: Entity to expand
            db_adapter: Database adapter for queries
            caller_role: Single caller role (legacy)
            caller_roles: List of caller roles (RBAC)
            
        Returns:
            GraphExpansionResult with relations, memories, and budget info
        """
        start_time = time.time()
        timeout_sec = self.timeout_ms / 1000.0
        
        relations = []
        memories = []
        nodes_visited = 0
        truncated = False
        truncation_reason = None
        budget_exceeded = {}
        
        try:
            # Check time budget before starting
            if (time.time() - start_time) > timeout_sec:
                truncated = True
                truncation_reason = "timeout_before_start"
                budget_exceeded['time'] = True
                return self._build_result(
                    relations, memories, nodes_visited, 0,
                    truncated, truncation_reason, budget_exceeded,
                    start_time
                )
            
            # Get entity relations with node budget
            relations_limit = min(self.max_neighbors, 50)  # Cap at 50
            relations = db_adapter.get_entity_relations(entity_id, limit=relations_limit)
            nodes_visited += len(relations)
            
            # Check time budget after relations
            elapsed = time.time() - start_time
            if elapsed > timeout_sec:
                truncated = True
                truncation_reason = "timeout_after_relations"
                budget_exceeded['time'] = True
                
                # Record truncation metrics
                increment_counter("graph.expansion.truncated", labels={
                    "reason": truncation_reason,
                    "entity_id": entity_id[:16]
                })
                
                return self._build_result(
                    relations, memories, nodes_visited, 1,
                    truncated, truncation_reason, budget_exceeded,
                    start_time
                )
            
            # Check if relations exceed node budget
            if len(relations) >= self.max_neighbors:
                truncated = True
                truncation_reason = "node_budget_exceeded"
                budget_exceeded['nodes'] = True
                
                increment_counter("graph.expansion.truncated", labels={
                    "reason": truncation_reason,
                    "entity_id": entity_id[:16]
                })
            
            # Get supporting memories with remaining budget
            remaining_time = timeout_sec - elapsed
            if remaining_time > 0:
                # Calculate how many memories we can fetch
                memories_limit = min(
                    self.max_neighbors - len(relations),
                    10  # Cap at 10 memories
                )
                
                if memories_limit > 0:
                    memories_raw = db_adapter.get_entity_memories(entity_id, limit=memories_limit)
                    
                    # Filter by role if applicable
                    memories_filtered = self._filter_memories_by_role(
                        memories_raw, caller_role, caller_roles
                    )
                    
                    # Convert to dict format
                    memories = [
                        {
                            "id": getattr(m, 'id', None),
                            "title": getattr(m, 'title', ''),
                            "content": getattr(m, 'content', '')[:200]
                        }
                        for m in memories_filtered
                    ]
                    
                    nodes_visited += len(memories)
            
            # Check time budget after memories
            elapsed = time.time() - start_time
            if elapsed > timeout_sec:
                truncated = True
                if not truncation_reason:
                    truncation_reason = "timeout_after_memories"
                budget_exceeded['time'] = True
                
                increment_counter("graph.expansion.truncated", labels={
                    "reason": truncation_reason,
                    "entity_id": entity_id[:16]
                })
            
            # Check total nodes
            if nodes_visited >= self.max_neighbors:
                truncated = True
                if not truncation_reason:
                    truncation_reason = "total_nodes_exceeded"
                budget_exceeded['nodes'] = True
                
                increment_counter("graph.expansion.truncated", labels={
                    "reason": truncation_reason,
                    "entity_id": entity_id[:16]
                })
            
        except Exception as e:
            # On error, return what we have
            truncated = True
            truncation_reason = f"error: {str(e)}"
            budget_exceeded['error'] = True
            
            increment_counter("graph.expansion.error", labels={
                "entity_id": entity_id[:16]
            })
        
        # Build final result
        result = self._build_result(
            relations, memories, nodes_visited, 1,
            truncated, truncation_reason, budget_exceeded,
            start_time
        )
        
        # Record metrics
        self._record_metrics(result, entity_id)
        
        return result
    
    def _filter_memories_by_role(
        self,
        memories: List[Any],
        caller_role: Optional[str],
        caller_roles: Optional[List[str]]
    ) -> List[Any]:
        """Filter memories by role visibility."""
        try:
            # Try RBAC levels if available
            from core.rbac.levels import get_max_role_level
            if caller_roles:
                caller_level = get_max_role_level(caller_roles)
                return [
                    m for m in memories
                    if getattr(m, 'role_view_level', 0) <= caller_level
                ]
        except ImportError:
            pass
        
        # Fallback to simple role check
        if caller_role:
            filtered = []
            for m in memories:
                role_view = getattr(m, 'role_view', 'general')
                if isinstance(role_view, list):
                    if caller_role in role_view or 'general' in role_view:
                        filtered.append(m)
                elif role_view == caller_role or role_view == 'general':
                    filtered.append(m)
            return filtered
        
        return memories
    
    def _build_result(
        self,
        relations: List[Tuple[str, str, float]],
        memories: List[Dict[str, Any]],
        nodes_visited: int,
        depth_reached: int,
        truncated: bool,
        truncation_reason: Optional[str],
        budget_exceeded: Dict[str, bool],
        start_time: float
    ) -> GraphExpansionResult:
        """Build graph expansion result with summary."""
        # Build summary
        summary_parts = []
        
        if relations:
            rel_text = ", ".join([f"{rel[0]} {rel[1]}" for rel in relations[:3]])
            summary_parts.append(f"Key relationships: {rel_text}")
            if len(relations) > 3:
                summary_parts.append(f"... and {len(relations) - 3} more")
        
        if memories:
            memory_text = " ".join([m.get('content', '')[:100] for m in memories[:2]])
            summary_parts.append(f"Supporting evidence: {memory_text}")
            if len(memories) > 2:
                summary_parts.append(f"... and {len(memories) - 2} more")
        
        if truncated and truncation_reason:
            summary_parts.append(f"[Truncated: {truncation_reason}]")
        
        summary = ". ".join(summary_parts) if summary_parts else "Concept information available"
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return GraphExpansionResult(
            relations=relations,
            memories=memories,
            summary=summary,
            truncated=truncated,
            truncation_reason=truncation_reason,
            nodes_visited=nodes_visited,
            depth_reached=depth_reached,
            elapsed_ms=elapsed_ms,
            budget_exceeded=budget_exceeded
        )
    
    def _record_metrics(self, result: GraphExpansionResult, entity_id: str):
        """Record metrics for graph expansion."""
        # Record expansion
        increment_counter("graph.expansion.total", labels={
            "entity_id": entity_id[:16]
        })
        
        # Record latency
        observe_histogram("graph.expansion.latency_ms", result.elapsed_ms, labels={
            "truncated": str(result.truncated).lower()
        })
        
        # Record nodes visited
        observe_histogram("graph.expansion.nodes_visited", result.nodes_visited, labels={
            "entity_id": entity_id[:16]
        })
        
        # Record depth
        observe_histogram("graph.expansion.depth_reached", result.depth_reached)
        
        # Record budget exceeded flags
        if result.budget_exceeded.get('time'):
            increment_counter("graph.expansion.budget_exceeded", labels={"type": "time"})
        if result.budget_exceeded.get('nodes'):
            increment_counter("graph.expansion.budget_exceeded", labels={"type": "nodes"})
        if result.budget_exceeded.get('error'):
            increment_counter("graph.expansion.budget_exceeded", labels={"type": "error"})


# Convenience function for quick expansion
def expand_entity_bounded(
    entity_id: str,
    db_adapter: Any,
    caller_role: Optional[str] = None,
    caller_roles: Optional[List[str]] = None,
    max_neighbors: int = 50,
    max_depth: int = 1,
    timeout_ms: Optional[float] = None
) -> GraphExpansionResult:
    """
    Expand entity neighborhood with bounded search.
    
    Convenience function that creates an expander and runs expansion.
    """
    expander = GraphExpander(
        max_neighbors=max_neighbors,
        max_depth=max_depth,
        timeout_ms=timeout_ms
    )
    
    return expander.expand_entity(
        entity_id=entity_id,
        db_adapter=db_adapter,
        caller_role=caller_role,
        caller_roles=caller_roles
    )
