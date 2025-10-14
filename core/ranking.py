# core/ranking.py — LiftScore ranking implementation

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from feature_flags import get_feature_flag
from core.metrics import RetrievalMetrics, time_operation

MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))

@dataclass
class LiftScoreWeights:
    """Configuration for LiftScore weights."""
    alpha: float = 0.15  # recency weight
    beta: float = 0.25   # graph coherence weight
    gamma: float = 0.35  # contradiction penalty weight
    delta: float = 0.25  # role fit weight

class LiftScoreRanker:
    """Ranker implementing LiftScore algorithm."""
    
    def __init__(self, weights: Optional[LiftScoreWeights] = None):
        self.weights = weights or LiftScoreWeights()
        self._load_weights_from_config()
    
    def _load_weights_from_config(self):
        """Load weights from configuration if available."""
        # Try to load from environment variables
        self.weights.alpha = float(os.getenv("LIFTSCORE_ALPHA", self.weights.alpha))
        self.weights.beta = float(os.getenv("LIFTSCORE_BETA", self.weights.beta))
        self.weights.gamma = float(os.getenv("LIFTSCORE_GAMMA", self.weights.gamma))
        self.weights.delta = float(os.getenv("LIFTSCORE_DELTA", self.weights.delta))
    
    def rank_and_pack(self, 
                     records: List[Dict[str, Any]], 
                     query: str,
                     caller_role: Optional[str] = None) -> Dict[str, Any]:
        """
        Rank records using LiftScore and pack into context.
        
        LiftScore = base_cosine + α*recency + β*graph_coherence - γ*contradiction_penalty + δ*role_fit
        """
        with time_operation("liftscore_calculation"):
            scored_records = []
            
            for record in records:
                # Base cosine similarity (from vector search)
                base_cosine = record.get("score", 0.0)
                
                # Recency score
                recency = self._calculate_recency_score(record.get("created_at"))
                
                # Graph coherence (for implicate records)
                graph_coherence = self._calculate_graph_coherence(record)
                
                # Contradiction penalty
                contradiction_penalty = self._calculate_contradiction_penalty(record)
                
                # Role fit
                role_fit = self._calculate_role_fit(record, caller_role)
                
                # Calculate LiftScore
                lift_score = (
                    base_cosine +
                    self.weights.alpha * recency +
                    self.weights.beta * graph_coherence -
                    self.weights.gamma * contradiction_penalty +
                    self.weights.delta * role_fit
                )
                
                # Store scoring breakdown for debugging
                record["_scoring"] = {
                    "base_cosine": base_cosine,
                    "recency": recency,
                    "graph_coherence": graph_coherence,
                    "contradiction_penalty": contradiction_penalty,
                    "role_fit": role_fit,
                    "lift_score": lift_score
                }
                
                scored_records.append((lift_score, record))
        
        # Sort by LiftScore descending
        scored_records.sort(key=lambda x: x[0], reverse=True)
        
        # Record LiftScore metrics at different positions
        for k, (score, record) in enumerate(scored_records[:10], 1):  # Record top 10
            RetrievalMetrics.record_lift_score_at_k(k, score)
            
            # Record implicate rank if this is an implicate record
            if record.get("source") == "implicate":
                RetrievalMetrics.record_implicate_rank(k)
        
        # Pack into context
        context = []
        budget_chars = MAX_CONTEXT_TOKENS * 4
        used = 0
        
        for score, record in scored_records:
            txt = (record.get("text") or "")[:4000]
            if used + len(txt) > budget_chars:
                break
            
            context.append({
                "id": record.get("id"),
                "title": record.get("title"),
                "text": txt,
                "type": record.get("type", "semantic"),
                "source": record.get("source", "unknown"),
                "lift_score": score,
                "scoring": record.get("_scoring", {})
            })
            used += len(txt)
        
        return {
            "context": context,
            "ranked_ids": [r.get("id") for _, r in scored_records]
        }
    
    def _calculate_recency_score(self, created_at: Optional[str]) -> float:
        """Calculate recency score using exponential decay."""
        if not created_at:
            return 0.5
        
        try:
            from datetime import datetime, timezone
            half_life_days = int(os.getenv("RECENCY_HALFLIFE_DAYS", "90"))
            
            t = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - t).total_seconds() / 86400.0
            return math.exp(-math.log(2) * (days / half_life_days))
        except Exception:
            return 0.5
    
    def _calculate_graph_coherence(self, record: Dict[str, Any]) -> float:
        """Calculate graph coherence score for implicate records."""
        if record.get("source") != "implicate":
            return 0.0
        
        metadata = record.get("metadata", {})
        
        # Score based on number of relations and supporting memories
        relations = metadata.get("relations", [])
        memories = metadata.get("expanded_memories", [])
        
        # Normalize to 0-1 range
        relation_score = min(len(relations) / 5.0, 1.0)  # Max 5 relations
        memory_score = min(len(memories) / 3.0, 1.0)     # Max 3 memories
        
        # Weighted combination
        return 0.6 * relation_score + 0.4 * memory_score
    
    def _calculate_contradiction_penalty(self, record: Dict[str, Any]) -> float:
        """Calculate contradiction penalty based on contradictions in metadata."""
        if not get_feature_flag("retrieval.contradictions_pack", default=False):
            return 0.0
        
        metadata = record.get("metadata", {})
        contradictions = metadata.get("contradictions", [])
        
        if not contradictions:
            return 0.0
        
        # Penalty increases with number of contradictions
        return min(len(contradictions) * 0.1, 1.0)
    
    def _calculate_role_fit(self, record: Dict[str, Any], caller_role: Optional[str]) -> float:
        """Calculate role fit score based on caller role and record visibility."""
        if not caller_role:
            return 0.5  # Neutral score if no role specified
        
        metadata = record.get("metadata", {})
        role_view = metadata.get("role_view", "general")
        
        # Role hierarchy (higher number = more privileged)
        role_hierarchy = {
            "general": 1,
            "pro": 2,
            "scholar": 3,
            "analytics": 4,
            "operations": 5
        }
        
        caller_rank = role_hierarchy.get(caller_role.lower(), 1)
        
        if isinstance(role_view, list):
            # If role_view is a list, check if caller role is in it
            if caller_role in role_view or "general" in role_view:
                return 1.0
            else:
                return 0.0
        else:
            # If role_view is a single role, check hierarchy
            record_rank = role_hierarchy.get(role_view.lower(), 1)
            if caller_rank >= record_rank:
                return 1.0
            else:
                return 0.0

class LegacyRanker:
    """Legacy ranking implementation for backward compatibility."""
    
    def rank_and_pack(self, 
                     records: List[Dict[str, Any]], 
                     query: str,
                     caller_role: Optional[str] = None) -> Dict[str, Any]:
        """Legacy ranking using simple semantic + recency scoring."""
        
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

def get_ranker() -> LiftScoreRanker:
    """Get the appropriate ranker based on feature flags."""
    if get_feature_flag("retrieval.liftscore", default=False):
        return LiftScoreRanker()
    else:
        return LegacyRanker()