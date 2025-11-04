#!/usr/bin/env python3
"""
core/reviewer.py — Answer reviewer with time budget and circuit breaker.

Provides answer review functionality with:
- Time budget enforcement (PERF_REVIEWER_BUDGET_MS)
- Circuit breaker integration
- Graceful skip on timeout or breaker open
- Optional score fields
- Result annotation with skip reason
"""

import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from config import load_config
from core.metrics import increment_counter, observe_histogram, time_operation
from core.circuit import get_circuit_breaker, CircuitBreakerConfig, CircuitBreakerOpenError


@dataclass
class ReviewResult:
    """Result of answer review."""
    skipped: bool = False
    skip_reason: Optional[str] = None
    score: Optional[float] = None
    confidence: Optional[float] = None
    flags: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "skipped": self.skipped,
            "latency_ms": self.latency_ms
        }
        
        if self.skip_reason:
            result["skip_reason"] = self.skip_reason
        
        # Only include score fields if not skipped
        if not self.skipped:
            if self.score is not None:
                result["score"] = self.score
            if self.confidence is not None:
                result["confidence"] = self.confidence
            if self.flags:
                result["flags"] = self.flags
            if self.details:
                result["details"] = self.details
        
        return result


class AnswerReviewer:
    """
    Answer reviewer with budget enforcement and circuit breaker.
    
    Features:
    - Enforces PERF_REVIEWER_BUDGET_MS timeout
    - Integrates with circuit breaker
    - Gracefully skips on timeout or breaker open
    - Annotates results with skip reason
    - Optional score fields
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize reviewer with config and circuit breaker.
        
        Args:
            config: Optional config dict (for testing). If None, loads from load_config()
        """
        self._circuit_breaker = None
        self._config = config
    
    @property
    def config(self):
        """Lazy load configuration."""
        if self._config is None:
            self._config = load_config()
        return self._config
    
    @property
    def circuit_breaker(self):
        """Lazy load reviewer circuit breaker."""
        if self._circuit_breaker is None:
            self._circuit_breaker = get_circuit_breaker(
                "reviewer",
                CircuitBreakerConfig(
                    name="reviewer",
                    failure_threshold=5,
                    cooldown_seconds=60.0,
                    success_threshold=2
                )
            )
        return self._circuit_breaker
    
    def is_enabled(self) -> bool:
        """Check if reviewer is enabled."""
        return self.config.get("PERF_REVIEWER_ENABLED", True)
    
    def get_budget_ms(self) -> float:
        """Get reviewer time budget in milliseconds."""
        return float(self.config.get("PERF_REVIEWER_BUDGET_MS", 500))
    
    def review_answer(
        self,
        answer: str,
        context: Optional[Dict[str, Any]] = None,
        query: Optional[str] = None
    ) -> ReviewResult:
        """
        Review answer with budget enforcement.
        
        Args:
            answer: Answer text to review
            context: Optional context information
            query: Optional original query
            
        Returns:
            ReviewResult with scores or skip annotation
        """
        start_time = time.time()
        
        # Check if reviewer is enabled
        if not self.is_enabled():
            elapsed_ms = (time.time() - start_time) * 1000
            increment_counter("reviewer.skipped", labels={"reason": "disabled"})
            return ReviewResult(
                skipped=True,
                skip_reason="reviewer_disabled",
                latency_ms=elapsed_ms
            )
        
        # Check circuit breaker state
        if not self.circuit_breaker.can_execute():
            elapsed_ms = (time.time() - start_time) * 1000
            increment_counter("reviewer.skipped", labels={"reason": "circuit_breaker_open"})
            return ReviewResult(
                skipped=True,
                skip_reason="circuit_breaker_open",
                latency_ms=elapsed_ms
            )
        
        # Get budget
        budget_ms = self.get_budget_ms()
        budget_seconds = budget_ms / 1000.0
        
        # Execute review with circuit breaker and timeout
        try:
            with time_operation("reviewer.call", labels={"budgeted": "true"}):
                result = self.circuit_breaker.call(
                    self._execute_review,
                    answer=answer,
                    context=context,
                    query=query,
                    timeout=budget_seconds
                )
            
            elapsed_ms = (time.time() - start_time) * 1000
            result.latency_ms = elapsed_ms
            
            # Record success metrics
            increment_counter("reviewer.success", labels={"within_budget": str(elapsed_ms <= budget_ms)})
            observe_histogram("reviewer.latency_ms", elapsed_ms, labels={"result": "success"})
            
            return result
            
        except CircuitBreakerOpenError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            increment_counter("reviewer.skipped", labels={"reason": "circuit_breaker_rejected"})
            return ReviewResult(
                skipped=True,
                skip_reason=f"circuit_breaker_open: {str(e)}",
                latency_ms=elapsed_ms
            )
        
        except TimeoutError:
            elapsed_ms = (time.time() - start_time) * 1000
            increment_counter("reviewer.skipped", labels={"reason": "timeout"})
            observe_histogram("reviewer.latency_ms", elapsed_ms, labels={"result": "timeout"})
            return ReviewResult(
                skipped=True,
                skip_reason=f"timeout_exceeded: {budget_ms}ms",
                latency_ms=elapsed_ms
            )
        
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            increment_counter("reviewer.error", labels={"error_type": type(e).__name__})
            observe_histogram("reviewer.latency_ms", elapsed_ms, labels={"result": "error"})
            
            # Skip on error but log it
            return ReviewResult(
                skipped=True,
                skip_reason=f"error: {type(e).__name__}",
                latency_ms=elapsed_ms,
                details={"error": str(e)}
            )
    
    def _execute_review(
        self,
        answer: str,
        context: Optional[Dict[str, Any]],
        query: Optional[str],
        timeout: float
    ) -> ReviewResult:
        """
        Execute the actual review logic.
        
        Args:
            answer: Answer text
            context: Context information
            query: Original query
            timeout: Timeout in seconds
            
        Returns:
            ReviewResult with scores
        """
        import signal
        
        # Set timeout using signal (Unix only) or threading
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Review exceeded {timeout}s timeout")
        
        try:
            # Try signal-based timeout (Unix)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout)
            
            try:
                result = self._perform_review(answer, context, query)
                signal.setitimer(signal.ITIMER_REAL, 0)  # Cancel timeout
                return result
            except TimeoutError:
                signal.setitimer(signal.ITIMER_REAL, 0)
                raise
        except (AttributeError, ValueError):
            # Signal not available (Windows) - use simpler approach
            return self._perform_review(answer, context, query)
    
    def _perform_review(
        self,
        answer: str,
        context: Optional[Dict[str, Any]],
        query: Optional[str]
    ) -> ReviewResult:
        """
        Perform the actual review logic.
        
        This is a placeholder for the actual review implementation.
        In production, this would call an LLM or other review service.
        
        Args:
            answer: Answer text
            context: Context information
            query: Original query
            
        Returns:
            ReviewResult with scores
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Call LLM for review
        # 2. Extract scores and flags
        # 3. Return structured result
        
        # Simple heuristic review for now
        score = 0.8  # Default score
        confidence = 0.9
        flags = {}
        
        # Check for problematic patterns
        if len(answer) < 10:
            flags["too_short"] = True
            score = 0.3
        
        if "don't know" in answer.lower() or "i don't know" in answer.lower():
            flags["uncertain"] = True
            score = 0.5
        
        if len(answer) > 5000:
            flags["too_long"] = True
            score = 0.6
        
        return ReviewResult(
            skipped=False,
            score=score,
            confidence=confidence,
            flags=flags,
            details={
                "answer_length": len(answer),
                "has_context": context is not None,
                "has_query": query is not None
            }
        )


# Global reviewer instance
_reviewer_instance = None


def get_reviewer() -> AnswerReviewer:
    """Get or create global reviewer instance."""
    global _reviewer_instance
    if _reviewer_instance is None:
        _reviewer_instance = AnswerReviewer()
    return _reviewer_instance


def review_answer_with_budget(
    answer: str,
    context: Optional[Dict[str, Any]] = None,
    query: Optional[str] = None
) -> ReviewResult:
    """
    Review answer with budget enforcement.
    
    Convenience function that uses global reviewer instance.
    
    Args:
        answer: Answer text
        context: Optional context
        query: Optional query
        
    Returns:
        ReviewResult with scores or skip annotation
    """
    reviewer = get_reviewer()
    return reviewer.review_answer(answer, context, query)
