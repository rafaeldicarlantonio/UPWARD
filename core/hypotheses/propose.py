# core/hypotheses/propose.py — Hypotheses proposal logic with Pareto scoring

import time
import hashlib
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

from core.factare.summary import CompareSummary
from core.policy import get_pareto_threshold
from feature_flags import get_feature_flag

class HypothesisStatus(Enum):
    """Status of a hypothesis proposal."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class ProposalResult(Enum):
    """Result of a hypothesis proposal."""
    PERSISTED = "persisted"
    NOT_PERSISTED = "not_persisted"
    OVERRIDE = "override"

@dataclass
class HypothesisProposal:
    """A hypothesis proposal with metadata."""
    title: str
    description: str
    source_message_id: str
    compare_summary: Optional[CompareSummary] = None
    pareto_score: Optional[float] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    status: HypothesisStatus = HypothesisStatus.PENDING
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.compare_summary:
            data['compare_summary'] = self.compare_summary.to_dict()
        if self.status:
            data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HypothesisProposal':
        """Create from dictionary."""
        # Parse datetime
        created_at = None
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'])
        
        # Parse compare_summary
        compare_summary = None
        if data.get('compare_summary'):
            compare_summary = CompareSummary.from_dict(data['compare_summary'])
        
        # Parse status
        status = HypothesisStatus.PENDING
        if data.get('status'):
            status = HypothesisStatus(data['status'])
        
        return cls(
            title=data['title'],
            description=data['description'],
            source_message_id=data['source_message_id'],
            compare_summary=compare_summary,
            pareto_score=data.get('pareto_score'),
            created_at=created_at,
            created_by=data.get('created_by'),
            status=status,
            metadata=data.get('metadata')
        )

@dataclass
class ParetoScoreComponents:
    """Components of the Pareto score calculation."""
    lift_score_at_k: float
    contradiction_score_inverse: float
    evidence_diversity: float
    blended_score: float
    metadata: Dict[str, Any]

@dataclass
class ProposalResponse:
    """Response from hypothesis proposal."""
    result: ProposalResult
    hypothesis_id: Optional[str] = None
    pareto_score: Optional[float] = None
    pareto_components: Optional[ParetoScoreComponents] = None
    threshold: Optional[float] = None
    override_reason: Optional[str] = None
    persisted_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class ParetoScorer:
    """Calculates Pareto scores for hypothesis proposals."""
    
    def __init__(self):
        self.lift_score_weight = 0.4
        self.contradiction_weight = 0.3
        self.diversity_weight = 0.3
    
    def calculate_pareto_score(
        self,
        compare_summary: Optional[CompareSummary],
        lift_scores: Optional[List[float]] = None,
        k: int = 5
    ) -> ParetoScoreComponents:
        """
        Calculate Pareto score using blended signals.
        
        Args:
            compare_summary: Optional compare summary for contradiction and diversity analysis
            lift_scores: Optional list of lift scores for @k calculation
            k: Number of top scores to consider for LiftScore@k
            
        Returns:
            ParetoScoreComponents with individual scores and blended result
        """
        # Calculate LiftScore@k
        lift_score_at_k = self._calculate_lift_score_at_k(lift_scores, k)
        
        # Calculate contradiction score inverse
        contradiction_score_inverse = self._calculate_contradiction_score_inverse(compare_summary)
        
        # Calculate evidence diversity
        evidence_diversity = self._calculate_evidence_diversity(compare_summary)
        
        # Calculate blended score
        blended_score = (
            self.lift_score_weight * lift_score_at_k +
            self.contradiction_weight * contradiction_score_inverse +
            self.diversity_weight * evidence_diversity
        )
        
        # Ensure score is between 0 and 1
        blended_score = max(0.0, min(1.0, blended_score))
        
        return ParetoScoreComponents(
            lift_score_at_k=lift_score_at_k,
            contradiction_score_inverse=contradiction_score_inverse,
            evidence_diversity=evidence_diversity,
            blended_score=blended_score,
            metadata={
                'lift_score_weight': self.lift_score_weight,
                'contradiction_weight': self.contradiction_weight,
                'diversity_weight': self.diversity_weight,
                'k': k,
                'lift_scores_provided': lift_scores is not None,
                'compare_summary_provided': compare_summary is not None
            }
        )
    
    def _calculate_lift_score_at_k(self, lift_scores: Optional[List[float]], k: int) -> float:
        """Calculate LiftScore@k from provided scores."""
        if not lift_scores:
            return 0.5  # Default neutral score when no lift scores provided
        
        # Sort scores in descending order and take top k
        sorted_scores = sorted(lift_scores, reverse=True)
        top_k_scores = sorted_scores[:k]
        
        if not top_k_scores:
            return 0.0
        
        # Calculate average of top k scores
        return sum(top_k_scores) / len(top_k_scores)
    
    def _calculate_contradiction_score_inverse(self, compare_summary: Optional[CompareSummary]) -> float:
        """Calculate inverse of contradiction score (higher contradictions = lower score)."""
        if not compare_summary:
            return 0.5  # Default neutral score when no compare summary
        
        # Count contradictions from compare summary
        contradictions = getattr(compare_summary, 'contradictions', [])
        contradiction_count = len(contradictions)
        
        # Calculate average confidence of contradictions
        if contradiction_count > 0:
            avg_confidence = sum(c.get('confidence', 0.5) for c in contradictions) / contradiction_count
        else:
            avg_confidence = 0.0
        
        # Inverse score: fewer contradictions and lower confidence = higher score
        # Scale based on contradiction count and confidence
        contradiction_penalty = (contradiction_count * 0.1) + (avg_confidence * 0.2)
        inverse_score = max(0.0, 1.0 - contradiction_penalty)
        
        return inverse_score
    
    def _calculate_evidence_diversity(self, compare_summary: Optional[CompareSummary]) -> float:
        """Calculate evidence diversity score."""
        if not compare_summary:
            return 0.5  # Default neutral score when no compare summary
        
        evidence = getattr(compare_summary, 'evidence', [])
        if not evidence:
            return 0.0
        
        # Calculate diversity based on source variety and score distribution
        sources = set(item.get('source', '') for item in evidence)
        source_diversity = len(sources) / max(1, len(evidence))
        
        # Calculate score variance (higher variance = more diverse)
        scores = [item.get('score', 0.0) for item in evidence]
        if len(scores) > 1:
            mean_score = sum(scores) / len(scores)
            variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
            score_diversity = min(1.0, variance * 4)  # Scale variance to 0-1
        else:
            score_diversity = 0.0
        
        # Combine source and score diversity
        diversity_score = (source_diversity * 0.6) + (score_diversity * 0.4)
        
        return diversity_score

class HypothesisProposer:
    """Main class for proposing hypotheses with Pareto gating."""
    
    def __init__(self):
        self.pareto_scorer = ParetoScorer()
        self._hypotheses_db = {}  # Simulated database
        self._next_id = 1
    
    def propose_hypothesis(
        self,
        title: str,
        description: str,
        source_message_id: str,
        compare_summary: Optional[CompareSummary] = None,
        pareto_score: Optional[float] = None,
        user_roles: List[str] = None,
        override_reason: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> ProposalResponse:
        """
        Propose a hypothesis with Pareto gating.
        
        Args:
            title: Hypothesis title
            description: Hypothesis description
            source_message_id: Source message ID
            compare_summary: Optional compare summary for scoring
            pareto_score: Optional pre-calculated Pareto score
            user_roles: User roles for override permissions
            override_reason: Reason for override (if applicable)
            created_by: User who created the hypothesis
            
        Returns:
            ProposalResponse with result and metadata
        """
        user_roles = user_roles or []
        
        # Calculate Pareto score if not provided
        if pareto_score is None:
            pareto_components = self.pareto_scorer.calculate_pareto_score(compare_summary)
            pareto_score = pareto_components.blended_score
        else:
            pareto_components = None
        
        # Get Pareto threshold
        threshold = get_pareto_threshold()
        
        # Check if user can override (analytics role)
        can_override = 'analytics' in user_roles
        
        # Determine if hypothesis should be persisted
        should_persist = False
        result = ProposalResult.NOT_PERSISTED
        hypothesis_id = None
        persisted_at = None
        final_override_reason = None
        
        if pareto_score >= threshold:
            # Above threshold - persist normally
            should_persist = True
            result = ProposalResult.PERSISTED
        elif can_override and override_reason:
            # Below threshold but user can override
            should_persist = True
            result = ProposalResult.OVERRIDE
            final_override_reason = override_reason
        
        # Persist hypothesis if conditions are met
        if should_persist:
            hypothesis_id = self._persist_hypothesis(
                title=title,
                description=description,
                source_message_id=source_message_id,
                compare_summary=compare_summary,
                pareto_score=pareto_score,
                created_by=created_by,
                override_reason=final_override_reason
            )
            persisted_at = datetime.now()
        
        # Create response
        response = ProposalResponse(
            result=result,
            hypothesis_id=hypothesis_id,
            pareto_score=pareto_score,
            pareto_components=pareto_components,
            threshold=threshold,
            override_reason=final_override_reason,
            persisted_at=persisted_at,
            metadata={
                'can_override': can_override,
                'user_roles': user_roles,
                'processing_timestamp': datetime.now().isoformat(),
                'pareto_threshold': threshold,
                'score_above_threshold': pareto_score >= threshold
            }
        )
        
        return response
    
    def _persist_hypothesis(
        self,
        title: str,
        description: str,
        source_message_id: str,
        compare_summary: Optional[CompareSummary],
        pareto_score: float,
        created_by: Optional[str],
        override_reason: Optional[str]
    ) -> str:
        """Persist hypothesis to database (simulated)."""
        hypothesis_id = f"hyp_{self._next_id:06d}"
        self._next_id += 1
        
        # Create hypothesis proposal
        proposal = HypothesisProposal(
            title=title,
            description=description,
            source_message_id=source_message_id,
            compare_summary=compare_summary,
            pareto_score=pareto_score,
            created_at=datetime.now(),
            created_by=created_by,
            status=HypothesisStatus.PENDING,
            metadata={
                'override_reason': override_reason,
                'override': override_reason is not None,
                'persisted_at': datetime.now().isoformat()
            }
        )
        
        # Store in simulated database
        self._hypotheses_db[hypothesis_id] = proposal
        
        # Log override if applicable
        if override_reason:
            print(f"Override: true - Hypothesis {hypothesis_id} saved with reason: {override_reason}")
        
        return hypothesis_id
    
    def get_hypothesis(self, hypothesis_id: str) -> Optional[HypothesisProposal]:
        """Get hypothesis by ID."""
        return self._hypotheses_db.get(hypothesis_id)
    
    def list_hypotheses(
        self,
        status: Optional[HypothesisStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[HypothesisProposal]:
        """List hypotheses with optional filtering."""
        hypotheses = list(self._hypotheses_db.values())
        
        if status:
            hypotheses = [h for h in hypotheses if h.status == status]
        
        # Sort by created_at descending
        hypotheses.sort(key=lambda h: h.created_at or datetime.min, reverse=True)
        
        return hypotheses[offset:offset + limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored hypotheses."""
        total = len(self._hypotheses_db)
        by_status = {}
        
        for proposal in self._hypotheses_db.values():
            status = proposal.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        overrides = sum(1 for p in self._hypotheses_db.values() 
                       if p.metadata and p.metadata.get('override', False))
        
        return {
            'total_hypotheses': total,
            'by_status': by_status,
            'overrides': overrides,
            'override_rate': overrides / max(1, total)
        }

# Global proposer instance
_hypothesis_proposer = None

def get_hypothesis_proposer() -> HypothesisProposer:
    """Get the global hypothesis proposer instance."""
    global _hypothesis_proposer
    if _hypothesis_proposer is None:
        _hypothesis_proposer = HypothesisProposer()
    return _hypothesis_proposer

# Convenience function for direct proposal
def propose_hypothesis(
    title: str,
    description: str,
    source_message_id: str,
    compare_summary: Optional[CompareSummary] = None,
    pareto_score: Optional[float] = None,
    user_roles: List[str] = None,
    override_reason: Optional[str] = None,
    created_by: Optional[str] = None
) -> ProposalResponse:
    """
    Convenience function for proposing a hypothesis.
    
    Args:
        title: Hypothesis title
        description: Hypothesis description
        source_message_id: Source message ID
        compare_summary: Optional compare summary for scoring
        pareto_score: Optional pre-calculated Pareto score
        user_roles: User roles for override permissions
        override_reason: Reason for override (if applicable)
        created_by: User who created the hypothesis
        
    Returns:
        ProposalResponse with result and metadata
    """
    proposer = get_hypothesis_proposer()
    return proposer.propose_hypothesis(
        title=title,
        description=description,
        source_message_id=source_message_id,
        compare_summary=compare_summary,
        pareto_score=pareto_score,
        user_roles=user_roles,
        override_reason=override_reason,
        created_by=created_by
    )