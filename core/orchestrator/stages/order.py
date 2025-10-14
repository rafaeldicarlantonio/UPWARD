"""
Order stage: Organize and prioritize information for final response.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List

from core.types import StageInput, StageOutput, StageMetrics


def order_stage(input_data: StageInput) -> StageOutput:
    """
    Order stage: Organize and prioritize information for final response.
    
    This stage takes all the analyzed information and organizes it into
    a coherent structure for the final response, prioritizing the most
    relevant and reliable information.
    
    Args:
        input_data: Stage input containing query, context, and retrieval results
        
    Returns:
        StageOutput with ordered information, metrics, and reasoning
    """
    start_time = time.time()
    
    try:
        # Get previous stage outputs
        observe_output = input_data.previous_stage_output or {}
        expand_output = input_data.context.get("expanded_context", {})
        contrast_output = input_data.context.get("contrast_analysis", {})
        
        # Get all available information
        all_results = expand_output.get("expanded_sources", input_data.retrieval_results)
        contradictions = contrast_output.get("contradictions", [])
        query_analysis = observe_output.get("query_analysis", {})
        
        # Create priority ranking
        priority_ranking = _create_priority_ranking(all_results, contradictions, query_analysis)
        
        # Organize information by topic
        topic_organization = _organize_by_topic(priority_ranking, query_analysis)
        
        # Create response structure
        response_structure = _create_response_structure(topic_organization, query_analysis)
        
        # Generate final recommendations
        recommendations = _generate_recommendations(priority_ranking, contradictions, query_analysis)
        
        # Prepare ordered context
        ordered_context = {
            "priority_ranking": priority_ranking,
            "topic_organization": topic_organization,
            "response_structure": response_structure,
            "recommendations": recommendations,
            "total_sources": len(all_results),
            "prioritized_sources": len(priority_ranking),
            "contradictions_resolved": len([c for c in contradictions if c.get("severity") == "low"]),
        }
        
        # Calculate timing
        duration_ms = (time.time() - start_time) * 1000
        
        # Generate reasoning
        reason = _generate_reason(priority_ranking, topic_organization, contradictions)
        
        # Check for warnings
        warnings = _generate_warnings(priority_ranking, contradictions, response_structure)
        
        return StageOutput(
            result=ordered_context,
            metrics=StageMetrics(
                duration_ms=duration_ms,
                memory_usage_mb=len(str(all_results)) / 1024 / 1024,
                cache_hits=0,  # No caching in order stage
                cache_misses=0,
                tokens_processed=len(str(priority_ranking).split()),
                custom_metrics={
                    "sources_prioritized": len(priority_ranking),
                    "topics_organized": len(topic_organization),
                    "contradictions_resolved": ordered_context["contradictions_resolved"],
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
            reason=f"Order stage failed: {str(e)}",
            errors=[str(e)],
        )


def _create_priority_ranking(all_results: List[Dict[str, Any]], contradictions: List[Dict[str, Any]], query_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create a priority ranking of all sources."""
    priority_ranking = []
    
    # Get contradiction sources to deprioritize
    contradiction_sources = set()
    for contradiction in contradictions:
        if contradiction.get("severity") == "high":
            contradiction_sources.add(contradiction.get("source_a", ""))
            contradiction_sources.add(contradiction.get("source_b", ""))
    
    for result in all_results:
        # Calculate priority score
        priority_score = _calculate_priority_score(result, contradictions, query_analysis)
        
        # Adjust for contradictions
        if result.get("id", "") in contradiction_sources:
            priority_score *= 0.5  # Reduce priority for contradictory sources
        
        priority_ranking.append({
            "result": result,
            "priority_score": priority_score,
            "rank": 0,  # Will be set after sorting
        })
    
    # Sort by priority score
    priority_ranking.sort(key=lambda x: x["priority_score"], reverse=True)
    
    # Assign ranks
    for i, item in enumerate(priority_ranking):
        item["rank"] = i + 1
    
    return priority_ranking


def _calculate_priority_score(result: Dict[str, Any], contradictions: List[Dict[str, Any]], query_analysis: Dict[str, Any]) -> float:
    """Calculate priority score for a result."""
    score = 0.0
    
    # Base score from relevance
    base_score = result.get("score", 0.0)
    score += base_score * 0.4
    
    # Boost for high-quality sources
    source_type = result.get("type", "unknown")
    if source_type in ["semantic", "episodic"]:
        score += 0.2
    elif source_type == "procedural":
        score += 0.1
    
    # Boost for recent sources
    metadata = result.get("metadata", {})
    if "created_at" in metadata:
        # Simple recency boost (would need actual date parsing in real implementation)
        score += 0.1
    
    # Boost for query relevance
    query_keywords = query_analysis.get("keywords", [])
    title = result.get("title", "").lower()
    text = result.get("text", "").lower()
    
    keyword_matches = sum(1 for keyword in query_keywords if keyword.lower() in title or keyword.lower() in text)
    if keyword_matches > 0:
        score += min(0.3, keyword_matches * 0.1)
    
    # Boost for entities
    entities = query_analysis.get("entities", [])
    entity_matches = sum(1 for entity in entities if entity.lower() in title or entity.lower() in text)
    if entity_matches > 0:
        score += min(0.2, entity_matches * 0.1)
    
    # Penalty for contradictions
    result_id = result.get("id", "")
    for contradiction in contradictions:
        if contradiction.get("source_a") == result_id or contradiction.get("source_b") == result_id:
            if contradiction.get("severity") == "high":
                score *= 0.3
            elif contradiction.get("severity") == "medium":
                score *= 0.7
    
    return min(1.0, max(0.0, score))


def _organize_by_topic(priority_ranking: List[Dict[str, Any]], query_analysis: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Organize prioritized results by topic."""
    topic_organization = {}
    
    # Extract topics from query analysis
    entities = query_analysis.get("entities", [])
    keywords = query_analysis.get("keywords", [])
    question_type = query_analysis.get("question_type", "statement")
    
    # Create topic categories
    topics = {
        "primary": [],  # Most relevant to the query
        "supporting": [],  # Supporting information
        "background": [],  # Background context
        "contradictory": [],  # Contradictory information
    }
    
    for item in priority_ranking:
        result = item["result"]
        priority_score = item["priority_score"]
        
        # Categorize based on priority score and content
        if priority_score > 0.7:
            topics["primary"].append(item)
        elif priority_score > 0.4:
            topics["supporting"].append(item)
        elif priority_score > 0.2:
            topics["background"].append(item)
        else:
            topics["contradictory"].append(item)
    
    return topics


def _create_response_structure(topic_organization: Dict[str, List[Dict[str, Any]]], query_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Create a structure for the final response."""
    question_type = query_analysis.get("question_type", "statement")
    complexity = query_analysis.get("complexity", 0.5)
    
    # Determine response structure based on question type and complexity
    if question_type in ["what", "who"]:
        structure_type = "definitional"
    elif question_type in ["how"]:
        structure_type = "procedural"
    elif question_type in ["why"]:
        structure_type = "explanatory"
    elif question_type in ["when", "where"]:
        structure_type = "factual"
    else:
        structure_type = "general"
    
    # Create sections based on available topics
    sections = []
    
    if topic_organization["primary"]:
        sections.append({
            "type": "main_answer",
            "sources": topic_organization["primary"][:3],  # Top 3 primary sources
            "description": "Primary information directly answering the query",
        })
    
    if topic_organization["supporting"]:
        sections.append({
            "type": "supporting_evidence",
            "sources": topic_organization["supporting"][:5],  # Top 5 supporting sources
            "description": "Supporting evidence and additional context",
        })
    
    if topic_organization["background"]:
        sections.append({
            "type": "background_context",
            "sources": topic_organization["background"][:3],  # Top 3 background sources
            "description": "Background information and context",
        })
    
    if topic_organization["contradictory"]:
        sections.append({
            "type": "contradictory_information",
            "sources": topic_organization["contradictory"][:2],  # Top 2 contradictory sources
            "description": "Conflicting information that requires attention",
        })
    
    return {
        "structure_type": structure_type,
        "sections": sections,
        "total_sections": len(sections),
        "complexity_level": "high" if complexity > 0.7 else "medium" if complexity > 0.4 else "low",
    }


def _generate_recommendations(priority_ranking: List[Dict[str, Any]], contradictions: List[Dict[str, Any]], query_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate recommendations for the final response."""
    recommendations = []
    
    # Check for high-priority sources
    high_priority_count = len([item for item in priority_ranking if item["priority_score"] > 0.7])
    if high_priority_count > 0:
        recommendations.append({
            "type": "use_high_priority_sources",
            "description": f"Use {high_priority_count} high-priority sources for main answer",
            "priority": "high",
        })
    
    # Check for contradictions that need addressing
    high_severity_contradictions = [c for c in contradictions if c.get("severity") == "high"]
    if high_severity_contradictions:
        recommendations.append({
            "type": "address_contradictions",
            "description": f"Address {len(high_severity_contradictions)} high-severity contradictions",
            "priority": "high",
        })
    
    # Check for supporting evidence
    supporting_sources = len([item for item in priority_ranking if 0.4 < item["priority_score"] <= 0.7])
    if supporting_sources > 0:
        recommendations.append({
            "type": "include_supporting_evidence",
            "description": f"Include {supporting_sources} supporting sources for credibility",
            "priority": "medium",
        })
    
    # Check for background context
    background_sources = len([item for item in priority_ranking if 0.2 < item["priority_score"] <= 0.4])
    if background_sources > 0:
        recommendations.append({
            "type": "provide_background_context",
            "description": f"Provide background context from {background_sources} sources",
            "priority": "low",
        })
    
    # Check for query complexity
    complexity = query_analysis.get("complexity", 0.5)
    if complexity > 0.7:
        recommendations.append({
            "type": "simplify_explanation",
            "description": "Query is complex - provide clear, step-by-step explanation",
            "priority": "medium",
        })
    
    return recommendations


def _generate_reason(priority_ranking: List[Dict[str, Any]], topic_organization: Dict[str, List[Dict[str, Any]]], contradictions: List[Dict[str, Any]]) -> str:
    """Generate a terse reason for the order stage output."""
    total_sources = len(priority_ranking)
    primary_sources = len(topic_organization["primary"])
    supporting_sources = len(topic_organization["supporting"])
    contradiction_count = len(contradictions)
    
    if primary_sources > 0 and contradiction_count == 0:
        return f"Ordered {total_sources} sources: {primary_sources} primary, {supporting_sources} supporting, no contradictions"
    elif primary_sources > 0:
        return f"Ordered {total_sources} sources: {primary_sources} primary, {supporting_sources} supporting, {contradiction_count} contradictions"
    elif total_sources > 0:
        return f"Ordered {total_sources} sources: {supporting_sources} supporting, {contradiction_count} contradictions"
    else:
        return "No sources available for ordering"


def _generate_warnings(priority_ranking: List[Dict[str, Any]], contradictions: List[Dict[str, Any]], response_structure: Dict[str, Any]) -> List[str]:
    """Generate warnings based on ordering analysis."""
    warnings = []
    
    # Check for low-priority sources
    low_priority_count = len([item for item in priority_ranking if item["priority_score"] < 0.3])
    if low_priority_count > len(priority_ranking) * 0.5:
        warnings.append("Majority of sources have low priority scores")
    
    # Check for contradictions
    if contradictions:
        warnings.append(f"{len(contradictions)} contradictions need to be addressed")
    
    # Check for response structure
    if response_structure["total_sections"] < 2:
        warnings.append("Limited response structure - may need more diverse sources")
    
    # Check for high complexity
    if response_structure["complexity_level"] == "high":
        warnings.append("High complexity response structure - ensure clarity")
    
    return warnings