"""
Expand stage: Expand context by finding related concepts and entities.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List

from core.types import StageInput, StageOutput, StageMetrics


def expand_stage(input_data: StageInput) -> StageOutput:
    """
    Expand stage: Expand context by finding related concepts and entities.
    
    This stage takes the observed context and expands it by finding related
    concepts, entities, and additional context that might be relevant.
    
    Args:
        input_data: Stage input containing query, context, and retrieval results
        
    Returns:
        StageOutput with expanded context, metrics, and reasoning
    """
    start_time = time.time()
    
    try:
        # Get previous stage output (observe stage)
        observe_output = input_data.previous_stage_output or {}
        query_analysis = observe_output.get("query_analysis", {})
        retrieval_analysis = observe_output.get("retrieval_analysis", {})
        
        # Extract entities and concepts to expand
        entities = query_analysis.get("entities", [])
        keywords = query_analysis.get("keywords", [])
        
        # Find related concepts
        related_concepts = _find_related_concepts(entities, keywords, input_data.retrieval_results)
        
        # Expand retrieval results with related content
        expanded_results = _expand_retrieval_results(input_data.retrieval_results, related_concepts)
        
        # Identify gaps in coverage
        coverage_gaps = _identify_coverage_gaps(query_analysis, expanded_results)
        
        # Prepare expanded context
        expanded_context = {
            "original_results": len(input_data.retrieval_results),
            "expanded_results": len(expanded_results),
            "related_concepts": related_concepts,
            "coverage_gaps": coverage_gaps,
            "expansion_quality": _assess_expansion_quality(expanded_results, input_data.retrieval_results),
            "expanded_sources": expanded_results,
        }
        
        # Calculate timing
        duration_ms = (time.time() - start_time) * 1000
        
        # Generate reasoning
        reason = _generate_reason(expanded_context, related_concepts)
        
        # Check for warnings
        warnings = _generate_warnings(expanded_context, coverage_gaps)
        
        return StageOutput(
            result=expanded_context,
            metrics=StageMetrics(
                duration_ms=duration_ms,
                memory_usage_mb=len(str(expanded_results)) / 1024 / 1024,
                cache_hits=0,  # No caching in expand stage
                cache_misses=0,
                tokens_processed=len(str(related_concepts).split()),
                custom_metrics={
                    "concepts_found": len(related_concepts),
                    "expansion_ratio": len(expanded_results) / max(1, len(input_data.retrieval_results)),
                    "coverage_gaps": len(coverage_gaps),
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
            reason=f"Expand stage failed: {str(e)}",
            errors=[str(e)],
        )


def _find_related_concepts(entities: List[str], keywords: List[str], retrieval_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find related concepts based on entities and keywords."""
    related_concepts = []
    
    # Extract concepts from retrieval results
    for result in retrieval_results:
        # Look for related concepts in metadata
        metadata = result.get("metadata", {})
        title = result.get("title", "")
        content = result.get("text", "")
        
        # Simple concept extraction from title and content
        concepts = _extract_concepts_from_text(f"{title} {content}")
        
        for concept in concepts:
            if concept not in [c["name"] for c in related_concepts]:
                related_concepts.append({
                    "name": concept,
                    "source": result.get("id", "unknown"),
                    "relevance": result.get("score", 0.0),
                    "type": "concept",
                })
    
    # Add entity-based concepts
    for entity in entities:
        if entity not in [c["name"] for c in related_concepts]:
            related_concepts.append({
                "name": entity,
                "source": "query_entity",
                "relevance": 1.0,
                "type": "entity",
            })
    
    # Add keyword-based concepts
    for keyword in keywords:
        if keyword not in [c["name"] for c in related_concepts]:
            related_concepts.append({
                "name": keyword,
                "source": "query_keyword",
                "relevance": 0.8,
                "type": "keyword",
            })
    
    return related_concepts


def _expand_retrieval_results(original_results: List[Dict[str, Any]], related_concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Expand retrieval results with related content."""
    expanded_results = list(original_results)  # Start with original results
    
    # Add synthetic expanded results based on related concepts
    for concept in related_concepts:
        if concept["type"] == "concept" and concept["relevance"] > 0.5:
            # Create a synthetic expanded result
            expanded_result = {
                "id": f"expanded_{concept['name'].lower().replace(' ', '_')}",
                "title": f"Related to {concept['name']}",
                "text": f"Additional context related to {concept['name']}",
                "score": concept["relevance"] * 0.8,  # Slightly lower than original
                "type": "expanded",
                "source": concept["source"],
                "metadata": {
                    "concept": concept["name"],
                    "expansion_type": "related_concept",
                }
            }
            expanded_results.append(expanded_result)
    
    return expanded_results


def _identify_coverage_gaps(query_analysis: Dict[str, Any], expanded_results: List[Dict[str, Any]]) -> List[str]:
    """Identify gaps in coverage that might need additional expansion."""
    gaps = []
    
    # Check if we have results for different aspects
    question_type = query_analysis.get("question_type", "statement")
    entities = query_analysis.get("entities", [])
    keywords = query_analysis.get("keywords", [])
    
    # Check for entity coverage
    covered_entities = set()
    for result in expanded_results:
        metadata = result.get("metadata", {})
        if "concept" in metadata:
            covered_entities.add(metadata["concept"])
    
    for entity in entities:
        if entity not in covered_entities:
            gaps.append(f"Missing context for entity: {entity}")
    
    # Check for keyword coverage
    covered_keywords = set()
    for result in expanded_results:
        text = f"{result.get('title', '')} {result.get('text', '')}".lower()
        for keyword in keywords:
            if keyword.lower() in text:
                covered_keywords.add(keyword)
    
    for keyword in keywords:
        if keyword not in covered_keywords:
            gaps.append(f"Missing context for keyword: {keyword}")
    
    # Check for question type coverage
    if question_type in ["how", "why"] and len(expanded_results) < 5:
        gaps.append(f"Insufficient context for {question_type} question")
    
    return gaps


def _assess_expansion_quality(expanded_results: List[Dict[str, Any]], original_results: List[Dict[str, Any]]) -> str:
    """Assess the quality of the expansion."""
    expansion_ratio = len(expanded_results) / max(1, len(original_results))
    
    if expansion_ratio > 2.0:
        return "excellent"
    elif expansion_ratio > 1.5:
        return "good"
    elif expansion_ratio > 1.2:
        return "fair"
    else:
        return "poor"


def _extract_concepts_from_text(text: str) -> List[str]:
    """Extract concepts from text (simple implementation)."""
    # Simple concept extraction - look for capitalized words and common concepts
    words = text.split()
    concepts = []
    
    # Look for capitalized words that might be concepts
    for i, word in enumerate(words):
        clean_word = word.strip(".,!?;:\"'()[]{}")
        if clean_word and clean_word[0].isupper() and len(clean_word) > 3:
            # Check if it's part of a multi-word concept
            if i < len(words) - 1:
                next_word = words[i + 1].strip(".,!?;:\"'()[]{}")
                if next_word and next_word[0].isupper():
                    concepts.append(f"{clean_word} {next_word}")
                else:
                    concepts.append(clean_word)
            else:
                concepts.append(clean_word)
    
    # Remove duplicates and limit to reasonable number
    unique_concepts = list(set(concepts))[:10]
    return unique_concepts


def _generate_reason(expanded_context: Dict[str, Any], related_concepts: List[Dict[str, Any]]) -> str:
    """Generate a terse reason for the expand stage output."""
    original_count = expanded_context["original_results"]
    expanded_count = expanded_context["expanded_results"]
    concepts_found = len(related_concepts)
    expansion_ratio = expanded_count / max(1, original_count)
    
    if expansion_ratio > 2.0:
        return f"Excellent expansion: {expanded_count} results (+{expanded_count - original_count}) from {concepts_found} concepts"
    elif expansion_ratio > 1.5:
        return f"Good expansion: {expanded_count} results (+{expanded_count - original_count}) from {concepts_found} concepts"
    elif expansion_ratio > 1.0:
        return f"Modest expansion: {expanded_count} results (+{expanded_count - original_count}) from {concepts_found} concepts"
    else:
        return f"Limited expansion: {expanded_count} results from {concepts_found} concepts"


def _generate_warnings(expanded_context: Dict[str, Any], coverage_gaps: List[str]) -> List[str]:
    """Generate warnings based on expansion analysis."""
    warnings = []
    
    expansion_quality = expanded_context["expansion_quality"]
    if expansion_quality == "poor":
        warnings.append("Poor expansion quality - limited additional context found")
    
    if len(coverage_gaps) > 3:
        warnings.append("Multiple coverage gaps identified")
    elif len(coverage_gaps) > 0:
        warnings.append("Some coverage gaps identified")
    
    expansion_ratio = expanded_context["expanded_results"] / max(1, expanded_context["original_results"])
    if expansion_ratio < 1.1:
        warnings.append("Minimal expansion achieved")
    
    return warnings