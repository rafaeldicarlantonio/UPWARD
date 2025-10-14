"""
Observe stage: Analyze query and retrieval results to understand intent and context.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List

from core.types import StageInput, StageOutput, StageMetrics


def observe_stage(input_data: StageInput) -> StageOutput:
    """
    Observe stage: Analyze query and retrieval results to understand intent and context.
    
    This stage performs initial analysis of the query and available retrieval results
    to understand the user's intent and prepare context for subsequent stages.
    
    Args:
        input_data: Stage input containing query, context, and retrieval results
        
    Returns:
        StageOutput with analysis results, metrics, and reasoning
    """
    start_time = time.time()
    
    try:
        # Analyze query characteristics
        query_analysis = _analyze_query(input_data.query)
        
        # Analyze retrieval results
        retrieval_analysis = _analyze_retrieval_results(input_data.retrieval_results)
        
        # Determine intent and context
        intent_analysis = _determine_intent(query_analysis, retrieval_analysis)
        
        # Prepare context for next stages
        context = {
            "query_analysis": query_analysis,
            "retrieval_analysis": retrieval_analysis,
            "intent_analysis": intent_analysis,
            "available_sources": len(input_data.retrieval_results),
            "context_quality": _assess_context_quality(retrieval_analysis),
        }
        
        # Calculate timing
        duration_ms = (time.time() - start_time) * 1000
        
        # Generate reasoning
        reason = _generate_reason(query_analysis, retrieval_analysis, intent_analysis)
        
        # Check for warnings
        warnings = _generate_warnings(query_analysis, retrieval_analysis)
        
        return StageOutput(
            result=context,
            metrics=StageMetrics(
                duration_ms=duration_ms,
                memory_usage_mb=len(str(input_data.retrieval_results)) / 1024 / 1024,
                cache_hits=0,  # No caching in observe stage
                cache_misses=0,
                tokens_processed=len(input_data.query.split()),
                custom_metrics={
                    "query_complexity": query_analysis["complexity"],
                    "retrieval_quality": retrieval_analysis["quality_score"],
                    "intent_confidence": intent_analysis["confidence"],
                }
            ),
            reason=reason,
            warnings=warnings,
        )
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return StageOutput(
            result={"error": str(e)},
            metrics=StageMetrics(duration_ms=duration_ms),
            reason=f"Observe stage failed: {str(e)}",
            errors=[str(e)],
        )


def _analyze_query(query: str) -> Dict[str, Any]:
    """Analyze query characteristics."""
    words = query.split()
    
    # Basic query analysis
    analysis = {
        "length": len(query),
        "word_count": len(words),
        "complexity": _calculate_complexity(query),
        "question_type": _detect_question_type(query),
        "entities": _extract_entities(query),
        "keywords": _extract_keywords(query),
    }
    
    return analysis


def _analyze_retrieval_results(retrieval_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze retrieval results quality and characteristics."""
    if not retrieval_results:
        return {
            "count": 0,
            "quality_score": 0.0,
            "coverage": 0.0,
            "relevance_scores": [],
            "source_types": [],
        }
    
    # Extract relevance scores
    relevance_scores = [r.get("score", 0.0) for r in retrieval_results if "score" in r]
    
    # Calculate quality metrics
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    max_relevance = max(relevance_scores) if relevance_scores else 0.0
    
    # Extract source types
    source_types = list(set(r.get("type", "unknown") for r in retrieval_results))
    
    return {
        "count": len(retrieval_results),
        "quality_score": avg_relevance,
        "coverage": min(1.0, len(retrieval_results) / 10.0),  # Assume 10 is good coverage
        "relevance_scores": relevance_scores,
        "source_types": source_types,
        "max_relevance": max_relevance,
        "min_relevance": min(relevance_scores) if relevance_scores else 0.0,
    }


def _determine_intent(query_analysis: Dict[str, Any], retrieval_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Determine user intent based on query and retrieval analysis."""
    question_type = query_analysis["question_type"]
    complexity = query_analysis["complexity"]
    quality_score = retrieval_analysis["quality_score"]
    
    # Determine intent confidence
    confidence = 0.5  # Base confidence
    
    if quality_score > 0.7:
        confidence += 0.2
    if complexity > 0.7:
        confidence += 0.1
    if question_type in ["what", "how", "why"]:
        confidence += 0.1
    
    confidence = min(1.0, confidence)
    
    return {
        "type": question_type,
        "confidence": confidence,
        "requires_detailed_answer": complexity > 0.6,
        "requires_sources": question_type in ["what", "how", "why"],
        "urgency": "low" if complexity < 0.3 else "medium" if complexity < 0.7 else "high",
    }


def _assess_context_quality(retrieval_analysis: Dict[str, Any]) -> str:
    """Assess the quality of available context."""
    quality_score = retrieval_analysis["quality_score"]
    count = retrieval_analysis["count"]
    
    if quality_score > 0.8 and count >= 5:
        return "excellent"
    elif quality_score > 0.6 and count >= 3:
        return "good"
    elif quality_score > 0.4 and count >= 2:
        return "fair"
    else:
        return "poor"


def _calculate_complexity(query: str) -> float:
    """Calculate query complexity score (0.0 to 1.0)."""
    words = query.split()
    
    # Base complexity on length and word variety
    length_factor = min(1.0, len(query) / 200.0)  # Normalize to 200 chars
    word_variety = len(set(word.lower() for word in words)) / len(words) if words else 0.0
    
    # Check for complex patterns
    complex_patterns = ["explain", "analyze", "compare", "contrast", "evaluate", "synthesize"]
    pattern_factor = sum(1 for pattern in complex_patterns if pattern in query.lower()) / len(complex_patterns)
    
    # Check for question words
    question_words = ["what", "how", "why", "when", "where", "who", "which"]
    question_factor = sum(1 for qw in question_words if qw in query.lower()) / len(question_words)
    
    complexity = (length_factor * 0.4 + word_variety * 0.3 + pattern_factor * 0.2 + question_factor * 0.1)
    return min(1.0, complexity)


def _detect_question_type(query: str) -> str:
    """Detect the type of question being asked."""
    query_lower = query.lower()
    
    if query_lower.startswith("what"):
        return "what"
    elif query_lower.startswith("how"):
        return "how"
    elif query_lower.startswith("why"):
        return "why"
    elif query_lower.startswith("when"):
        return "when"
    elif query_lower.startswith("where"):
        return "where"
    elif query_lower.startswith("who"):
        return "who"
    elif query_lower.startswith("which"):
        return "which"
    elif "?" in query:
        return "question"
    else:
        return "statement"


def _extract_entities(query: str) -> List[str]:
    """Extract potential entities from the query (simple implementation)."""
    # Simple entity extraction - look for capitalized words and common entities
    words = query.split()
    entities = []
    
    for word in words:
        # Remove punctuation
        clean_word = word.strip(".,!?;:")
        if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
            entities.append(clean_word)
    
    return entities


def _extract_keywords(query: str) -> List[str]:
    """Extract keywords from the query."""
    # Simple keyword extraction - remove stop words
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "this", "that", "these", "those"}
    
    words = query.lower().split()
    keywords = [word.strip(".,!?;:") for word in words if word.strip(".,!?;:") not in stop_words and len(word.strip(".,!?;:")) > 2]
    
    return keywords


def _generate_reason(query_analysis: Dict[str, Any], retrieval_analysis: Dict[str, Any], intent_analysis: Dict[str, Any]) -> str:
    """Generate a terse reason for the observe stage output."""
    quality = retrieval_analysis["quality_score"]
    count = retrieval_analysis["count"]
    intent_type = intent_analysis["type"]
    confidence = intent_analysis["confidence"]
    
    if quality > 0.7 and count >= 5:
        return f"High-quality context ({count} sources, {quality:.2f} avg relevance) for {intent_type} query"
    elif quality > 0.5 and count >= 3:
        return f"Good context ({count} sources, {quality:.2f} avg relevance) for {intent_type} query"
    elif count > 0:
        return f"Limited context ({count} sources, {quality:.2f} avg relevance) for {intent_type} query"
    else:
        return f"No retrieval results for {intent_type} query"


def _generate_warnings(query_analysis: Dict[str, Any], retrieval_analysis: Dict[str, Any]) -> List[str]:
    """Generate warnings based on analysis."""
    warnings = []
    
    if retrieval_analysis["count"] == 0:
        warnings.append("No retrieval results available")
    elif retrieval_analysis["count"] < 3:
        warnings.append("Limited retrieval results")
    
    if retrieval_analysis["quality_score"] < 0.3:
        warnings.append("Low relevance scores in retrieval results")
    
    if query_analysis["complexity"] > 0.8:
        warnings.append("High complexity query may require additional processing")
    
    if len(query_analysis["entities"]) == 0:
        warnings.append("No clear entities identified in query")
    
    return warnings