"""
Contrast stage: Identify contradictions and conflicting information.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List

from core.types import StageInput, StageOutput, StageMetrics


def contrast_stage(input_data: StageInput) -> StageOutput:
    """
    Contrast stage: Identify contradictions and conflicting information.
    
    This stage analyzes the expanded context to identify contradictions,
    conflicting information, and inconsistencies that need to be resolved.
    
    Args:
        input_data: Stage input containing query, context, and retrieval results
        
    Returns:
        StageOutput with contradiction analysis, metrics, and reasoning
    """
    start_time = time.time()
    
    try:
        # Get previous stage outputs
        observe_output = input_data.previous_stage_output or {}
        expand_output = input_data.context.get("expanded_context", {})
        
        # Get expanded results for analysis
        expanded_results = expand_output.get("expanded_sources", input_data.retrieval_results)
        
        # Detect contradictions
        contradictions = _detect_contradictions(expanded_results, input_data.query)
        
        # Analyze conflict patterns
        conflict_patterns = _analyze_conflict_patterns(contradictions)
        
        # Assess contradiction severity
        severity_assessment = _assess_contradiction_severity(contradictions)
        
        # Prepare contrast analysis
        contrast_analysis = {
            "contradictions": contradictions,
            "conflict_patterns": conflict_patterns,
            "severity_assessment": severity_assessment,
            "total_contradictions": len(contradictions),
            "high_severity_count": len([c for c in contradictions if c.get("severity", "low") == "high"]),
            "resolution_suggestions": _generate_resolution_suggestions(contradictions),
        }
        
        # Calculate timing
        duration_ms = (time.time() - start_time) * 1000
        
        # Generate reasoning
        reason = _generate_reason(contradictions, severity_assessment)
        
        # Check for warnings
        warnings = _generate_warnings(contradictions, severity_assessment)
        
        return StageOutput(
            result=contrast_analysis,
            metrics=StageMetrics(
                duration_ms=duration_ms,
                memory_usage_mb=len(str(expanded_results)) / 1024 / 1024,
                cache_hits=0,  # No caching in contrast stage
                cache_misses=0,
                tokens_processed=len(str(contradictions).split()),
                custom_metrics={
                    "contradictions_found": len(contradictions),
                    "high_severity_count": contrast_analysis["high_severity_count"],
                    "conflict_patterns": len(conflict_patterns),
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
            reason=f"Contrast stage failed: {str(e)}",
            errors=[str(e)],
        )


def _detect_contradictions(expanded_results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Detect contradictions in the expanded results."""
    contradictions = []
    
    # Group results by potential subject/entity
    subject_groups = _group_results_by_subject(expanded_results)
    
    # Look for contradictions within each subject group
    for subject, results in subject_groups.items():
        if len(results) < 2:
            continue  # Need at least 2 results to find contradictions
        
        # Check for temporal contradictions
        temporal_contradictions = _find_temporal_contradictions(subject, results)
        contradictions.extend(temporal_contradictions)
        
        # Check for factual contradictions
        factual_contradictions = _find_factual_contradictions(subject, results)
        contradictions.extend(factual_contradictions)
        
        # Check for numerical contradictions
        numerical_contradictions = _find_numerical_contradictions(subject, results)
        contradictions.extend(numerical_contradictions)
    
    return contradictions


def _group_results_by_subject(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group results by potential subject/entity."""
    subject_groups = {}
    
    for result in results:
        # Extract potential subjects from title and text
        title = result.get("title", "")
        text = result.get("text", "")
        
        # Simple subject extraction
        subjects = _extract_subjects_from_text(f"{title} {text}")
        
        for subject in subjects:
            if subject not in subject_groups:
                subject_groups[subject] = []
            subject_groups[subject].append(result)
    
    return subject_groups


def _find_temporal_contradictions(subject: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find temporal contradictions (different time references)."""
    contradictions = []
    
    # Look for time-related information
    time_claims = []
    for result in results:
        text = f"{result.get('title', '')} {result.get('text', '')}"
        time_info = _extract_time_info(text)
        if time_info:
            time_claims.append({
                "result": result,
                "time_info": time_info,
            })
    
    # Check for conflicting time claims
    if len(time_claims) >= 2:
        for i, claim1 in enumerate(time_claims):
            for claim2 in time_claims[i+1:]:
                if _are_temporal_contradictions(claim1["time_info"], claim2["time_info"]):
                    contradictions.append({
                        "type": "temporal_contradiction",
                        "subject": subject,
                        "claim_a": claim1["time_info"]["text"],
                        "claim_b": claim2["time_info"]["text"],
                        "source_a": claim1["result"].get("id", "unknown"),
                        "source_b": claim2["result"].get("id", "unknown"),
                        "severity": "medium",
                        "confidence": 0.7,
                    })
    
    return contradictions


def _find_factual_contradictions(subject: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find factual contradictions (opposing statements)."""
    contradictions = []
    
    # Look for opposing statements
    statements = []
    for result in results:
        text = f"{result.get('title', '')} {result.get('text', '')}"
        # Simple statement extraction
        if len(text) > 20:  # Only consider substantial text
            statements.append({
                "result": result,
                "text": text,
            })
    
    # Check for opposing statements
    if len(statements) >= 2:
        for i, stmt1 in enumerate(statements):
            for stmt2 in statements[i+1:]:
                if _are_factual_contradictions(stmt1["text"], stmt2["text"]):
                    contradictions.append({
                        "type": "factual_contradiction",
                        "subject": subject,
                        "claim_a": stmt1["text"][:100] + "...",
                        "claim_b": stmt2["text"][:100] + "...",
                        "source_a": stmt1["result"].get("id", "unknown"),
                        "source_b": stmt2["result"].get("id", "unknown"),
                        "severity": "high",
                        "confidence": 0.6,
                    })
    
    return contradictions


def _find_numerical_contradictions(subject: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find numerical contradictions (different numbers for same metric)."""
    contradictions = []
    
    # Look for numerical information
    numerical_claims = []
    for result in results:
        text = f"{result.get('title', '')} {result.get('text', '')}"
        numbers = _extract_numbers(text)
        if numbers:
            numerical_claims.append({
                "result": result,
                "numbers": numbers,
            })
    
    # Check for conflicting numerical claims
    if len(numerical_claims) >= 2:
        for i, claim1 in enumerate(numerical_claims):
            for claim2 in numerical_claims[i+1:]:
                conflicts = _find_numerical_conflicts(claim1["numbers"], claim2["numbers"])
                for conflict in conflicts:
                    contradictions.append({
                        "type": "numerical_contradiction",
                        "subject": subject,
                        "claim_a": f"{conflict['metric']}: {conflict['value_a']}",
                        "claim_b": f"{conflict['metric']}: {conflict['value_b']}",
                        "source_a": claim1["result"].get("id", "unknown"),
                        "source_b": claim2["result"].get("id", "unknown"),
                        "severity": "medium",
                        "confidence": 0.8,
                    })
    
    return contradictions


def _analyze_conflict_patterns(contradictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze patterns in the detected contradictions."""
    patterns = []
    
    if not contradictions:
        return patterns
    
    # Group by type
    type_counts = {}
    for contradiction in contradictions:
        contradiction_type = contradiction.get("type", "unknown")
        type_counts[contradiction_type] = type_counts.get(contradiction_type, 0) + 1
    
    # Identify dominant patterns
    for contradiction_type, count in type_counts.items():
        if count > 1:
            patterns.append({
                "type": f"repeated_{contradiction_type}",
                "count": count,
                "description": f"Multiple {contradiction_type} detected",
            })
    
    # Check for severity patterns
    high_severity_count = len([c for c in contradictions if c.get("severity") == "high"])
    if high_severity_count > 0:
        patterns.append({
            "type": "high_severity_contradictions",
            "count": high_severity_count,
            "description": f"{high_severity_count} high-severity contradictions detected",
        })
    
    return patterns


def _assess_contradiction_severity(contradictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assess the overall severity of contradictions."""
    if not contradictions:
        return {
            "overall_severity": "none",
            "confidence": 1.0,
            "requires_attention": False,
        }
    
    high_severity = len([c for c in contradictions if c.get("severity") == "high"])
    medium_severity = len([c for c in contradictions if c.get("severity") == "medium"])
    low_severity = len([c for c in contradictions if c.get("severity") == "low"])
    
    total = len(contradictions)
    
    if high_severity > 0:
        overall_severity = "high"
        requires_attention = True
    elif medium_severity > 2:
        overall_severity = "medium"
        requires_attention = True
    elif total > 0:
        overall_severity = "low"
        requires_attention = False
    else:
        overall_severity = "none"
        requires_attention = False
    
    return {
        "overall_severity": overall_severity,
        "high_severity_count": high_severity,
        "medium_severity_count": medium_severity,
        "low_severity_count": low_severity,
        "total_count": total,
        "requires_attention": requires_attention,
        "confidence": min(1.0, total / 10.0),  # Confidence based on sample size
    }


def _generate_resolution_suggestions(contradictions: List[Dict[str, Any]]) -> List[str]:
    """Generate suggestions for resolving contradictions."""
    suggestions = []
    
    if not contradictions:
        return suggestions
    
    # Group by type
    type_counts = {}
    for contradiction in contradictions:
        contradiction_type = contradiction.get("type", "unknown")
        type_counts[contradiction_type] = type_counts.get(contradiction_type, 0) + 1
    
    # Generate type-specific suggestions
    for contradiction_type, count in type_counts.items():
        if contradiction_type == "temporal_contradiction":
            suggestions.append(f"Verify timeline information from {count} conflicting sources")
        elif contradiction_type == "factual_contradiction":
            suggestions.append(f"Cross-reference factual claims from {count} conflicting sources")
        elif contradiction_type == "numerical_contradiction":
            suggestions.append(f"Validate numerical data from {count} conflicting sources")
    
    # General suggestions
    if len(contradictions) > 5:
        suggestions.append("Consider prioritizing sources by reliability and recency")
    
    if any(c.get("severity") == "high" for c in contradictions):
        suggestions.append("High-severity contradictions require immediate attention")
    
    return suggestions


def _extract_subjects_from_text(text: str) -> List[str]:
    """Extract potential subjects from text."""
    # Simple subject extraction - look for capitalized words
    words = text.split()
    subjects = []
    
    for word in words:
        clean_word = word.strip(".,!?;:\"'()[]{}")
        if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
            subjects.append(clean_word)
    
    # Return unique subjects, limited to reasonable number
    return list(set(subjects))[:5]


def _extract_time_info(text: str) -> Optional[Dict[str, Any]]:
    """Extract time-related information from text."""
    # Simple time extraction - look for year patterns
    import re
    
    year_pattern = r'\b(19|20)\d{2}\b'
    years = re.findall(year_pattern, text)
    
    if years:
        return {
            "text": text[:100] + "..." if len(text) > 100 else text,
            "years": years,
        }
    
    return None


def _are_temporal_contradictions(time_info1: Dict[str, Any], time_info2: Dict[str, Any]) -> bool:
    """Check if two time claims are contradictory."""
    years1 = set(time_info1.get("years", []))
    years2 = set(time_info2.get("years", []))
    
    # If they have different years, they might be contradictory
    if years1 and years2 and not years1.intersection(years2):
        return True
    
    return False


def _are_factual_contradictions(text1: str, text2: str) -> bool:
    """Check if two texts contain factual contradictions."""
    # Simple contradiction detection - look for opposing words
    opposing_pairs = [
        ("is", "is not"), ("are", "are not"), ("was", "was not"),
        ("true", "false"), ("correct", "incorrect"), ("right", "wrong"),
        ("yes", "no"), ("positive", "negative"), ("good", "bad"),
    ]
    
    text1_lower = text1.lower()
    text2_lower = text2.lower()
    
    for positive, negative in opposing_pairs:
        if positive in text1_lower and negative in text2_lower:
            return True
        if negative in text1_lower and positive in text2_lower:
            return True
    
    return False


def _extract_numbers(text: str) -> List[Dict[str, Any]]:
    """Extract numerical information from text."""
    import re
    
    # Look for numbers with units or context
    number_pattern = r'\b(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?\b'
    matches = re.findall(number_pattern, text)
    
    numbers = []
    for match in matches:
        value = float(match[0])
        unit = match[1] if match[1] else "unitless"
        numbers.append({
            "value": value,
            "unit": unit,
            "text": match[0] + (" " + match[1] if match[1] else ""),
        })
    
    return numbers


def _find_numerical_conflicts(numbers1: List[Dict[str, Any]], numbers2: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find numerical conflicts between two sets of numbers."""
    conflicts = []
    
    # Group by unit
    units1 = {}
    units2 = {}
    
    for num in numbers1:
        unit = num["unit"]
        if unit not in units1:
            units1[unit] = []
        units1[unit].append(num)
    
    for num in numbers2:
        unit = num["unit"]
        if unit not in units2:
            units2[unit] = []
        units2[unit].append(num)
    
    # Check for conflicts within same units
    for unit in units1:
        if unit in units2:
            values1 = [n["value"] for n in units1[unit]]
            values2 = [n["value"] for n in units2[unit]]
            
            # If values are significantly different, it's a conflict
            for v1 in values1:
                for v2 in values2:
                    if abs(v1 - v2) > max(v1, v2) * 0.1:  # 10% difference threshold
                        conflicts.append({
                            "metric": unit,
                            "value_a": v1,
                            "value_b": v2,
                        })
    
    return conflicts


def _generate_reason(contradictions: List[Dict[str, Any]], severity_assessment: Dict[str, Any]) -> str:
    """Generate a terse reason for the contrast stage output."""
    total = len(contradictions)
    severity = severity_assessment["overall_severity"]
    
    if total == 0:
        return "No contradictions detected in expanded context"
    elif severity == "high":
        return f"High-severity contradictions detected: {total} total, {severity_assessment['high_severity_count']} high-severity"
    elif severity == "medium":
        return f"Medium-severity contradictions detected: {total} total contradictions"
    else:
        return f"Low-severity contradictions detected: {total} total contradictions"


def _generate_warnings(contradictions: List[Dict[str, Any]], severity_assessment: Dict[str, Any]) -> List[str]:
    """Generate warnings based on contradiction analysis."""
    warnings = []
    
    if severity_assessment["requires_attention"]:
        warnings.append("Contradictions require attention before proceeding")
    
    if severity_assessment["overall_severity"] == "high":
        warnings.append("High-severity contradictions detected")
    
    if len(contradictions) > 10:
        warnings.append("Large number of contradictions detected")
    
    if severity_assessment["confidence"] < 0.5:
        warnings.append("Low confidence in contradiction detection")
    
    return warnings