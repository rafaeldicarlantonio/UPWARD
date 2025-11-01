# core/selection.py — pluggable selection strategies

from __future__ import annotations

import time
import math
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from feature_flags import get_feature_flag
from app.services.vector_store import VectorStore
from core.ranking import LiftScoreRanker
from core.metrics import RetrievalMetrics, time_operation, record_feature_flag_usage

# Import RBAC level filtering
try:
    from core.rbac.levels import (
        filter_memories_by_level,
        process_trace_summary,
        get_max_role_level,
    )
    RBAC_LEVELS_AVAILABLE = True
except ImportError:
    RBAC_LEVELS_AVAILABLE = False

MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))

@dataclass
class SelectionResult:
    """Result of a selection operation."""
    context: List[Dict[str, Any]]
    ranked_ids: List[str]
    reasons: List[str]
    strategy_used: str
    metadata: Dict[str, Any]

class SelectionStrategy(ABC):
    """Abstract base class for selection strategies."""
    
    @abstractmethod
    def select(self, 
               query: str, 
               embedding: List[float], 
               caller_role: Optional[str] = None,
               **kwargs) -> SelectionResult:
        """Select and rank relevant content."""
        pass

class LegacySelector(SelectionStrategy):
    """Legacy selection strategy - maintains existing behavior."""
    
    def __init__(self):
        self.vector_store = VectorStore()
    
    def select(self, 
               query: str, 
               embedding: List[float], 
               caller_role: Optional[str] = None,
               **kwargs) -> SelectionResult:
        """Legacy selection using single index."""
        
        # Record feature flag usage
        record_feature_flag_usage("retrieval.dual_index", False)
        
        caller_roles = kwargs.get('caller_roles', [caller_role] if caller_role else ['general'])
        
        with time_operation("legacy_query_total"):
            # Query the main index (explicate)
            hits = self.vector_store.query_explicit(
                embedding=embedding,
                top_k=kwargs.get('top_k', 16),
                filter=kwargs.get('filter'),
                caller_role=caller_role
            )
        
        # Convert hits to records format for compatibility
        records = []
        for hit in hits.matches:
            record = {
                "id": hit.id,
                "text": hit.metadata.get("text", ""),
                "title": hit.metadata.get("title", ""),
                "created_at": hit.metadata.get("created_at"),
                "type": hit.metadata.get("type", "semantic"),
                "score": hit.score,
                "metadata": hit.metadata,
                "role_view_level": hit.metadata.get("role_view_level", 0),
            }
            # Process trace summary based on caller level
            if "process_trace_summary" in hit.metadata and RBAC_LEVELS_AVAILABLE:
                record["process_trace_summary"] = process_trace_summary(
                    hit.metadata["process_trace_summary"],
                    caller_roles
                )
            records.append(record)
        
        # Filter by role visibility level
        if RBAC_LEVELS_AVAILABLE:
            records = filter_memories_by_level(records, caller_roles)
        
        # Record legacy query metrics
        RetrievalMetrics.record_legacy_query(0)  # Latency will be recorded by time_operation
        
        # Apply legacy ranking
        with time_operation("legacy_ranking"):
            ranked_result = self._legacy_rank_and_pack(records, query)
        
        # Generate reasons
        reasons = [f"Legacy ranking: score={hit.score:.3f}" for hit in hits.matches[:len(ranked_result["context"])]]
        
        return SelectionResult(
            context=ranked_result["context"],
            ranked_ids=ranked_result["ranked_ids"],
            reasons=reasons,
            strategy_used="legacy",
            metadata={"total_hits": len(hits.matches), "after_filter": len(records)}
        )
    
    def _legacy_rank_and_pack(self, records: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        """Legacy ranking and packing logic."""
        def _recency_score(created_at: Optional[str], half_life_days: int = int(os.getenv("RECENCY_HALFLIFE_DAYS", "90"))) -> float:
            if not created_at:
                return 0.5
            try:
                from datetime import datetime, timezone
                t = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                days = (datetime.now(timezone.utc) - t).total_seconds() / 86400.0
                return math.exp(-math.log(2) * (days / half_life_days))
            except Exception:
                return 0.5
        
        # Score records
        scored = []
        for rec in records:
            sem = rec.get("score", 0.0)
            recency = _recency_score(rec.get("created_at"))
            score = 0.7 * sem + 0.3 * recency
            scored.append((score, rec))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Build context
        ctx = []
        budget_chars = MAX_CONTEXT_TOKENS * 4
        used = 0
        for _, rec in scored:
            txt = (rec.get("text") or "")[:4000]
            if used + len(txt) > budget_chars:
                break
            ctx.append({
                "id": rec.get("id"), 
                "title": rec.get("title"), 
                "text": txt,
                "type": rec.get("type", "semantic")
            })
            used += len(txt)
        
        return {"context": ctx, "ranked_ids": [r.get("id") for _, r in scored]}

class DualSelector(SelectionStrategy):
    """Dual index selection strategy with graph expansion."""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.ranker = LiftScoreRanker()
        self._db_adapter = None  # Lazy load
    
    @property
    def db_adapter(self):
        """Lazy load database adapter."""
        if self._db_adapter is None:
            from adapters.db import DatabaseAdapter
            self._db_adapter = DatabaseAdapter()
        return self._db_adapter
    
    def select(self, 
               query: str, 
               embedding: List[float], 
               caller_role: Optional[str] = None,
               **kwargs) -> SelectionResult:
        """Dual index selection with graph expansion."""
        
        # Record feature flag usage
        record_feature_flag_usage("retrieval.dual_index", True)
        
        caller_roles = kwargs.get('caller_roles', [caller_role] if caller_role else ['general'])
        explicate_k = kwargs.get('explicate_top_k', 16)
        implicate_k = kwargs.get('implicate_top_k', 8)
        
        with time_operation("dual_query_total", labels={"explicate_k": str(explicate_k), "implicate_k": str(implicate_k)}):
            # Query both indices
            with time_operation("explicate_query"):
                explicate_hits = self.vector_store.query_explicit(
                    embedding=embedding,
                    top_k=explicate_k,
                    filter=kwargs.get('filter'),
                    caller_role=caller_role
                )
            
            with time_operation("implicate_query"):
                implicate_hits = self.vector_store.query_implicate(
                    embedding=embedding,
                    top_k=implicate_k,
                    filter=kwargs.get('filter'),
                    caller_role=caller_role
                )
        
        # Process explicate hits
        with time_operation("explicate_processing"):
            explicate_records = self._process_explicate_hits(explicate_hits.matches, caller_roles)
        
        # Process implicate hits with graph expansion
        with time_operation("implicate_processing"):
            implicate_records = self._process_implicate_hits(implicate_hits.matches, caller_role, caller_roles)
        
        # Record dual query metrics
        RetrievalMetrics.record_dual_query(explicate_k, implicate_k, 0)  # Latency recorded by time_operation
        
        # Combine and deduplicate
        with time_operation("record_deduplication"):
            all_records = self._deduplicate_records(explicate_records + implicate_records)
        
        # Filter by role visibility level
        if RBAC_LEVELS_AVAILABLE:
            original_count = len(all_records)
            all_records = filter_memories_by_level(all_records, caller_roles)
            filtered_count = original_count - len(all_records)
        else:
            filtered_count = 0
        
        # Rank using LiftScore
        with time_operation("liftscore_ranking"):
            ranked_result = self.ranker.rank_and_pack(
                records=all_records,
                query=query,
                caller_role=caller_role
            )
        
        # Generate reasons
        reasons = self._generate_reasons(ranked_result["context"], explicate_hits.matches, implicate_hits.matches)
        
        return SelectionResult(
            context=ranked_result["context"],
            ranked_ids=ranked_result["ranked_ids"],
            reasons=reasons,
            strategy_used="dual",
            metadata={
                "explicate_hits": len(explicate_hits.matches),
                "implicate_hits": len(implicate_hits.matches),
                "total_after_dedup": len(all_records) + filtered_count,
                "filtered_by_level": filtered_count
            }
        )
    
    def _process_explicate_hits(self, hits: List[Any], caller_roles: List[str]) -> List[Dict[str, Any]]:
        """Process explicate index hits."""
        records = []
        for hit in hits:
            record = {
                "id": hit.id,
                "text": hit.metadata.get("text", ""),
                "title": hit.metadata.get("title", ""),
                "created_at": hit.metadata.get("created_at"),
                "type": hit.metadata.get("type", "semantic"),
                "score": hit.score,
                "metadata": hit.metadata,
                "source": "explicate",
                "role_view_level": hit.metadata.get("role_view_level", 0),
            }
            # Process trace summary based on caller level
            if "process_trace_summary" in hit.metadata and RBAC_LEVELS_AVAILABLE:
                record["process_trace_summary"] = process_trace_summary(
                    hit.metadata["process_trace_summary"],
                    caller_roles
                )
            records.append(record)
        return records
    
    def _process_implicate_hits(self, hits: List[Any], caller_role: Optional[str], caller_roles: List[str]) -> List[Dict[str, Any]]:
        """Process implicate index hits with graph expansion."""
        records = []
        
        for hit in hits:
            # Extract entity information from implicate hit
            entity_id = hit.metadata.get("entity_id")
            if not entity_id:
                continue
            
            # Get expanded content via graph
            expanded_content = self._expand_implicate_content(entity_id, caller_role, caller_roles)
            
            if expanded_content:
                records.append({
                    "id": f"implicate:{entity_id}",
                    "text": expanded_content["summary"],
                    "title": f"Concept: {hit.metadata.get('entity_name', 'Unknown')}",
                    "created_at": hit.metadata.get("created_at"),
                    "type": "concept",
                    "score": hit.score,
                    "metadata": {
                        **hit.metadata,
                        "expanded_memories": expanded_content["memories"],
                        "relations": expanded_content["relations"]
                    },
                    "source": "implicate",
                    "role_view_level": hit.metadata.get("role_view_level", 0),
                })
        
        return records
    
    def _expand_implicate_content(self, entity_id: str, caller_role: Optional[str], caller_roles: List[str]) -> Optional[Dict[str, Any]]:
        """Expand implicate content via graph traversal."""
        try:
            with time_operation("entity_expansion", labels={"entity_id": entity_id}):
                # Get entity relations
                relations = self.db_adapter.get_entity_relations(entity_id, limit=5)
                
                # Get supporting memories
                memories = self.db_adapter.get_entity_memories(entity_id, limit=3)
                
                # Filter memories by role level if available
                if RBAC_LEVELS_AVAILABLE and caller_roles:
                    from core.rbac.levels import get_max_role_level
                    caller_level = get_max_role_level(caller_roles)
                    memories = [
                        m for m in memories
                        if getattr(m, 'role_view_level', 0) <= caller_level
                    ]
                elif caller_role:
                    # Fallback to old role access check
                    memories = [m for m in memories if self._check_memory_role_access(m, caller_role)]
                
                # Build summary from relations and memories
                summary_parts = []
                
                # Add relation context
                if relations:
                    rel_text = ", ".join([f"{rel[0]} {rel[1]}" for rel in relations[:3]])
                    summary_parts.append(f"Key relationships: {rel_text}")
                
                # Add memory context
                if memories:
                    memory_text = " ".join([m.content[:200] for m in memories[:2]])
                    summary_parts.append(f"Supporting evidence: {memory_text}")
                
                # Record entity expansion metrics
                RetrievalMetrics.record_entity_expansion(len(relations) + len(memories), 0)  # Latency recorded by time_operation
                
                return {
                    "summary": ". ".join(summary_parts) if summary_parts else "Concept information available",
                    "relations": relations,
                    "memories": [{"id": m.id, "title": m.title, "content": m.content[:100]} for m in memories]
                }
            
        except Exception as e:
            print(f"Error expanding implicate content for entity {entity_id}: {e}")
            return None
    
    def _check_memory_role_access(self, memory: Any, caller_role: str) -> bool:
        """Check if caller role has access to memory."""
        # Simple role check - can be enhanced based on actual role_view implementation
        role_view = getattr(memory, 'role_view', 'general')
        if isinstance(role_view, list):
            return caller_role in role_view or 'general' in role_view
        return role_view == caller_role or role_view == 'general'
    
    def _deduplicate_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate records by file/message."""
        seen = set()
        deduplicated = []
        
        for record in records:
            # Create dedup key from file_id or message_id
            dedup_key = (
                record.get("metadata", {}).get("file_id"),
                record.get("metadata", {}).get("message_id"),
                record.get("id")
            )
            
            if dedup_key not in seen:
                seen.add(dedup_key)
                deduplicated.append(record)
        
        return deduplicated
    
    def _generate_reasons(self, context: List[Dict[str, Any]], explicate_hits: List[Any], implicate_hits: List[Any]) -> List[str]:
        """Generate reason strings for each context item."""
        reasons = []
        
        for item in context:
            item_id = item.get("id", "")
            source = "unknown"
            
            # Determine source
            if item_id.startswith("implicate:"):
                source = "implicate"
            else:
                # Check if it came from explicate
                for hit in explicate_hits:
                    if hit.id == item_id:
                        source = "explicate"
                        break
            
            # Generate reason
            if source == "implicate":
                reasons.append(f"Concept expansion: {item.get('title', 'Unknown concept')}")
            elif source == "explicate":
                # Find the original hit for score
                for hit in explicate_hits:
                    if hit.id == item_id:
                        reasons.append(f"Direct match: score={hit.score:.3f}")
                        break
                else:
                    reasons.append("Direct match")
            else:
                reasons.append("Unknown source")
        
        return reasons

class SelectionFactory:
    """Factory for creating selection strategies."""
    
    @staticmethod
    def create_selector() -> SelectionStrategy:
        """Create appropriate selector based on feature flags."""
        if get_feature_flag("retrieval.dual_index", default=False):
            return DualSelector()
        else:
            return LegacySelector()

# Convenience function for backward compatibility
def select_content(query: str, 
                  embedding: List[float], 
                  caller_role: Optional[str] = None,
                  **kwargs) -> SelectionResult:
    """Select content using the appropriate strategy."""
    selector = SelectionFactory.create_selector()
    return selector.select(query, embedding, caller_role, **kwargs)