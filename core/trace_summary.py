"""
Trace summary generator for creating concise summaries of orchestration traces.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Set
from core.types import OrchestrationResult


def summarize_trace(trace: OrchestrationResult, max_lines: int = 4) -> str:
    """
    Generate a concise summary of an orchestration trace.
    
    Args:
        trace: OrchestrationResult to summarize
        max_lines: Maximum number of lines in summary (2-4)
        
    Returns:
        Multi-line summary string
    """
    if max_lines < 2 or max_lines > 4:
        raise ValueError("max_lines must be between 2 and 4")
    
    # Extract key information
    stages = trace.stages
    contradictions = trace.contradictions
    selected_context_ids = trace.selected_context_ids
    warnings = trace.warnings
    timings = trace.timings
    
    # Count contradictions
    contradiction_count = len(contradictions)
    high_severity_contradictions = len([c for c in contradictions if c.get("severity") == "high"])
    
    # Get top evidence IDs (first 3 selected context IDs)
    top_evidence_ids = selected_context_ids[:3]
    
    # Calculate total duration
    total_duration_ms = timings.get("total_ms", 0.0)
    
    # Build summary lines
    summary_lines = []
    
    # Line 1: Basic info
    stage_count = len(stages)
    context_count = len(selected_context_ids)
    duration_sec = total_duration_ms / 1000.0
    
    line1 = f"Processed {stage_count} stages in {duration_sec:.1f}s, selected {context_count} context items"
    summary_lines.append(line1)
    
    # Line 2: Evidence IDs
    if top_evidence_ids:
        evidence_str = ", ".join(top_evidence_ids)
        if len(selected_context_ids) > 3:
            evidence_str += f" (+{len(selected_context_ids) - 3} more)"
        line2 = f"Top evidence: {evidence_str}"
    else:
        line2 = "No evidence selected"
    summary_lines.append(line2)
    
    # Line 3: Contradictions (if any)
    if contradiction_count > 0:
        if high_severity_contradictions > 0:
            line3 = f"Contradictions: {contradiction_count} total ({high_severity_contradictions} high-severity)"
        else:
            line3 = f"Contradictions: {contradiction_count}"
        summary_lines.append(line3)
    
    # Line 4: Warnings or additional info
    if warnings:
        warning_count = len(warnings)
        if warning_count == 1:
            line4 = f"Warning: {warnings[0]}"
        else:
            line4 = f"Warnings: {warning_count} issues detected"
        summary_lines.append(line4)
    elif not summary_lines:  # If no contradictions and no warnings
        # Add a generic completion line
        line4 = "Orchestration completed successfully"
        summary_lines.append(line4)
    
    # Ensure we don't exceed max_lines
    summary_lines = summary_lines[:max_lines]
    
    # Join lines with newlines
    return "\n".join(summary_lines)


def summarize_trace_from_dict(trace_data: Dict[str, Any], max_lines: int = 4) -> str:
    """
    Generate a summary from trace data dictionary.
    
    Args:
        trace_data: Trace data dictionary
        max_lines: Maximum number of lines in summary (2-4)
        
    Returns:
        Multi-line summary string
    """
    if max_lines < 2 or max_lines > 4:
        raise ValueError("max_lines must be between 2 and 4")
    
    # Extract key information
    stages = trace_data.get("stages", [])
    contradictions = trace_data.get("contradictions", [])
    selected_context_ids = trace_data.get("selected_context_ids", [])
    warnings = trace_data.get("warnings", [])
    timings = trace_data.get("timings", {})
    
    # Count contradictions
    contradiction_count = len(contradictions)
    high_severity_contradictions = len([c for c in contradictions if c.get("severity") == "high"])
    
    # Get top evidence IDs (first 3 selected context IDs)
    top_evidence_ids = selected_context_ids[:3]
    
    # Calculate total duration
    total_duration_ms = timings.get("total_ms", 0.0)
    
    # Build summary lines
    summary_lines = []
    
    # Line 1: Basic info
    stage_count = len(stages)
    context_count = len(selected_context_ids)
    duration_sec = total_duration_ms / 1000.0
    
    line1 = f"Processed {stage_count} stages in {duration_sec:.1f}s, selected {context_count} context items"
    summary_lines.append(line1)
    
    # Line 2: Evidence IDs
    if top_evidence_ids:
        evidence_str = ", ".join(top_evidence_ids)
        if len(selected_context_ids) > 3:
            evidence_str += f" (+{len(selected_context_ids) - 3} more)"
        line2 = f"Top evidence: {evidence_str}"
    else:
        line2 = "No evidence selected"
    summary_lines.append(line2)
    
    # Line 3: Contradictions (if any)
    if contradiction_count > 0:
        if high_severity_contradictions > 0:
            line3 = f"Contradictions: {contradiction_count} total ({high_severity_contradictions} high-severity)"
        else:
            line3 = f"Contradictions: {contradiction_count}"
        summary_lines.append(line3)
    
    # Line 4: Warnings or additional info
    if warnings:
        warning_count = len(warnings)
        if warning_count == 1:
            line4 = f"Warning: {warnings[0]}"
        else:
            line4 = f"Warnings: {warning_count} issues detected"
        summary_lines.append(line4)
    elif len(summary_lines) < max_lines:  # If we have room for more lines
        # Add additional info if available
        if trace_data.get("final_plan"):
            plan_type = trace_data["final_plan"].get("type", "unknown")
            line4 = f"Plan type: {plan_type}"
            summary_lines.append(line4)
        elif len(summary_lines) < max_lines:
            # Add a generic completion line
            line4 = "Orchestration completed successfully"
            summary_lines.append(line4)
    
    # Ensure we don't exceed max_lines
    summary_lines = summary_lines[:max_lines]
    
    # Join lines with newlines
    return "\n".join(summary_lines)


def get_summary_stats(trace: OrchestrationResult) -> Dict[str, Any]:
    """
    Get summary statistics for a trace.
    
    Args:
        trace: OrchestrationResult to analyze
        
    Returns:
        Dictionary with summary statistics
    """
    stages = trace.stages
    contradictions = trace.contradictions
    selected_context_ids = trace.selected_context_ids
    warnings = trace.warnings
    timings = trace.timings
    
    # Count contradictions by severity
    contradiction_counts = {
        "total": len(contradictions),
        "high": len([c for c in contradictions if c.get("severity") == "high"]),
        "medium": len([c for c in contradictions if c.get("severity") == "medium"]),
        "low": len([c for c in contradictions if c.get("severity") == "low"]),
    }
    
    # Count stages by type
    stage_types = {}
    for stage in stages:
        if hasattr(stage, 'name'):
            # StageTrace object
            stage_type = stage.name
        else:
            # Dictionary
            stage_type = stage.get("name", "unknown")
        stage_types[stage_type] = stage_types.get(stage_type, 0) + 1
    
    # Calculate timing breakdown
    timing_breakdown = {
        "total_ms": timings.get("total_ms", 0.0),
        "orchestration_ms": timings.get("orchestration_ms", 0.0),
        "planning_ms": timings.get("planning_ms", 0.0),
    }
    
    return {
        "stage_count": len(stages),
        "stage_types": stage_types,
        "contradiction_counts": contradiction_counts,
        "context_items_selected": len(selected_context_ids),
        "warning_count": len(warnings),
        "timing_breakdown": timing_breakdown,
        "has_high_severity_contradictions": contradiction_counts["high"] > 0,
        "has_warnings": len(warnings) > 0,
    }


def format_summary_for_display(summary: str, indent: str = "  ") -> str:
    """
    Format summary for display with proper indentation.
    
    Args:
        summary: Summary string
        indent: Indentation string
        
    Returns:
        Formatted summary string
    """
    lines = summary.split('\n')
    indented_lines = [f"{indent}{line}" for line in lines]
    return '\n'.join(indented_lines)


# Role-aware summarization constants
ROLE_LEVELS = {
    "general": 1,           # Minimal info, no raw text, no PII
    "pro": 2,               # Full summary, some technical details
    "scholars": 2,          # Full summary, academic focus
    "analytics": 2,         # Full summary, data focus
    "ops": 3,               # Full details, all information
}

# PII patterns for redaction
PII_PATTERNS = [
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
    r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
    r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email (duplicate)
    r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',  # IP address
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email (duplicate)
]

# Source text patterns that should be redacted for general role
SOURCE_TEXT_PATTERNS = [
    r'"[^"]{50,}"',  # Long quoted text
    r'```[\s\S]*?```',  # Code blocks
    r'`[^`]{20,}`',  # Long inline code
]


def summarize_for_role(trace: OrchestrationResult, role_key: str, max_lines: Optional[int] = None) -> str:
    """
    Generate a role-aware summary of an orchestration trace.
    
    Args:
        trace: OrchestrationResult to summarize
        role_key: Role key ('general', 'pro', 'scholars', 'analytics', 'ops')
        max_lines: Override max lines (uses role default if None)
        
    Returns:
        Role-appropriate summary string
    """
    if role_key not in ROLE_LEVELS:
        raise ValueError(f"Invalid role_key: {role_key}. Must be one of {list(ROLE_LEVELS.keys())}")
    
    # Set max_lines based on role if not specified
    if max_lines is None:
        if role_key == "general":
            max_lines = 2
        elif role_key in ["pro", "scholars", "analytics"]:
            max_lines = 4
        else:  # ops
            max_lines = 6
    
    # Generate base summary
    if role_key == "general":
        summary = _generate_general_summary(trace, max_lines)
    elif role_key in ["pro", "scholars", "analytics"]:
        summary = _generate_professional_summary(trace, role_key, max_lines)
    else:  # ops
        summary = _generate_ops_summary(trace, max_lines)
    
    return summary


def _generate_general_summary(trace: OrchestrationResult, max_lines: int) -> str:
    """Generate a general user summary with redacted content."""
    stages = trace.stages
    contradictions = trace.contradictions
    selected_context_ids = trace.selected_context_ids
    warnings = trace.warnings
    timings = trace.timings
    
    # Count contradictions
    contradiction_count = len(contradictions)
    high_severity_contradictions = len([c for c in contradictions if c.get("severity") == "high"])
    
    # Get top evidence IDs (first 2 for general)
    top_evidence_ids = selected_context_ids[:2]
    
    # Calculate total duration
    total_duration_ms = timings.get("total_ms", 0.0)
    
    # Build summary lines
    summary_lines = []
    
    # Line 1: Basic info (redacted)
    stage_count = len(stages)
    context_count = len(selected_context_ids)
    duration_sec = total_duration_ms / 1000.0
    
    line1 = f"Processed {stage_count} steps in {duration_sec:.1f}s, found {context_count} relevant sources"
    summary_lines.append(line1)
    
    # Line 2: Evidence IDs (redacted)
    if top_evidence_ids:
        evidence_str = ", ".join([f"Source-{i+1}" for i in range(len(top_evidence_ids))])
        if len(selected_context_ids) > 2:
            evidence_str += f" (+{len(selected_context_ids) - 2} more)"
        line2 = f"Key sources: {evidence_str}"
    else:
        line2 = "No sources selected"
    summary_lines.append(line2)
    
    # Line 3: Contradictions (if any and we have room)
    if contradiction_count > 0 and len(summary_lines) < max_lines:
        if high_severity_contradictions > 0:
            line3 = f"Found {contradiction_count} conflicting information points ({high_severity_contradictions} significant)"
        else:
            line3 = f"Found {contradiction_count} conflicting information points"
        summary_lines.append(line3)
    
    # Line 4: Warnings or completion (if we have room)
    if warnings and len(summary_lines) < max_lines:
        warning_count = len(warnings)
        if warning_count == 1:
            line4 = f"Note: {_redact_warning_text(warnings[0])}"
        else:
            line4 = f"Note: {warning_count} processing issues detected"
        summary_lines.append(line4)
    elif len(summary_lines) < max_lines:
        line4 = "Analysis completed successfully"
        summary_lines.append(line4)
    
    # Ensure we don't exceed max_lines
    summary_lines = summary_lines[:max_lines]
    
    return "\n".join(summary_lines)


def _generate_professional_summary(trace: OrchestrationResult, role_key: str, max_lines: int) -> str:
    """Generate a professional summary with technical details."""
    stages = trace.stages
    contradictions = trace.contradictions
    selected_context_ids = trace.selected_context_ids
    warnings = trace.warnings
    timings = trace.timings
    
    # Count contradictions
    contradiction_count = len(contradictions)
    high_severity_contradictions = len([c for c in contradictions if c.get("severity") == "high"])
    
    # Get top evidence IDs (first 3)
    top_evidence_ids = selected_context_ids[:3]
    
    # Calculate total duration
    total_duration_ms = timings.get("total_ms", 0.0)
    
    # Build summary lines
    summary_lines = []
    
    # Line 1: Basic info with technical details
    stage_count = len(stages)
    context_count = len(selected_context_ids)
    duration_sec = total_duration_ms / 1000.0
    
    # Add role-specific context
    if role_key == "scholars":
        line1 = f"Processed {stage_count} orchestration stages in {duration_sec:.1f}s, selected {context_count} context items"
    elif role_key == "analytics":
        line1 = f"Executed {stage_count} processing stages in {duration_sec:.1f}s, retrieved {context_count} data points"
    else:  # pro
        line1 = f"Processed {stage_count} stages in {duration_sec:.1f}s, selected {context_count} context items"
    
    summary_lines.append(line1)
    
    # Line 2: Evidence IDs
    if top_evidence_ids:
        evidence_str = ", ".join(top_evidence_ids)
        if len(selected_context_ids) > 3:
            evidence_str += f" (+{len(selected_context_ids) - 3} more)"
        line2 = f"Top evidence: {evidence_str}"
    else:
        line2 = "No evidence selected"
    summary_lines.append(line2)
    
    # Line 3: Contradictions (if any)
    if contradiction_count > 0:
        if high_severity_contradictions > 0:
            line3 = f"Contradictions: {contradiction_count} total ({high_severity_contradictions} high-severity)"
        else:
            line3 = f"Contradictions: {contradiction_count}"
        summary_lines.append(line3)
    
    # Line 4: Warnings or additional info
    if warnings:
        warning_count = len(warnings)
        if warning_count == 1:
            line4 = f"Warning: {warnings[0]}"
        else:
            line4 = f"Warnings: {warning_count} issues detected"
        summary_lines.append(line4)
    elif len(summary_lines) < max_lines:
        # Add role-specific additional info
        if role_key == "scholars":
            line4 = "Academic analysis completed"
        elif role_key == "analytics":
            line4 = "Data processing completed"
        else:  # pro
            line4 = "Professional analysis completed"
        summary_lines.append(line4)
    
    # Ensure we don't exceed max_lines
    summary_lines = summary_lines[:max_lines]
    
    return "\n".join(summary_lines)


def _generate_ops_summary(trace: OrchestrationResult, max_lines: int) -> str:
    """Generate an operations summary with full details."""
    stages = trace.stages
    contradictions = trace.contradictions
    selected_context_ids = trace.selected_context_ids
    warnings = trace.warnings
    timings = trace.timings
    
    # Count contradictions
    contradiction_count = len(contradictions)
    high_severity_contradictions = len([c for c in contradictions if c.get("severity") == "high"])
    
    # Get all evidence IDs
    top_evidence_ids = selected_context_ids[:5]  # Show more for ops
    
    # Calculate timing breakdown
    total_duration_ms = timings.get("total_ms", 0.0)
    orchestration_ms = timings.get("orchestration_ms", 0.0)
    planning_ms = timings.get("planning_ms", 0.0)
    
    # Build summary lines
    summary_lines = []
    
    # Line 1: Detailed timing info
    stage_count = len(stages)
    context_count = len(selected_context_ids)
    duration_sec = total_duration_ms / 1000.0
    
    line1 = f"Processed {stage_count} stages in {duration_sec:.1f}s (orchestration: {orchestration_ms/1000:.1f}s, planning: {planning_ms/1000:.1f}s), selected {context_count} context items"
    summary_lines.append(line1)
    
    # Line 2: Evidence IDs (more for ops)
    if top_evidence_ids:
        evidence_str = ", ".join(top_evidence_ids)
        if len(selected_context_ids) > 5:
            evidence_str += f" (+{len(selected_context_ids) - 5} more)"
        line2 = f"Evidence IDs: {evidence_str}"
    else:
        line2 = "No evidence selected"
    summary_lines.append(line2)
    
    # Line 3: Contradictions with details
    if contradiction_count > 0:
        if high_severity_contradictions > 0:
            line3 = f"Contradictions: {contradiction_count} total ({high_severity_contradictions} high-severity) - {_get_contradiction_types(contradictions)}"
        else:
            line3 = f"Contradictions: {contradiction_count} - {_get_contradiction_types(contradictions)}"
        summary_lines.append(line3)
    
    # Line 4: Warnings with details
    if warnings:
        warning_count = len(warnings)
        if warning_count == 1:
            line4 = f"Warning: {warnings[0]}"
        else:
            line4 = f"Warnings: {warning_count} issues - {', '.join(warnings[:2])}{'...' if len(warnings) > 2 else ''}"
        summary_lines.append(line4)
    
    # Line 5: Stage details
    if len(summary_lines) < max_lines:
        stage_names = [stage.name if hasattr(stage, 'name') else stage.get('name', 'unknown') for stage in stages]
        line5 = f"Stages: {', '.join(stage_names)}"
        summary_lines.append(line5)
    
    # Line 6: Performance metrics
    if len(summary_lines) < max_lines:
        line6 = f"Performance: {_get_performance_summary(timings)}"
        summary_lines.append(line6)
    
    # Ensure we don't exceed max_lines
    summary_lines = summary_lines[:max_lines]
    
    return "\n".join(summary_lines)


def _redact_warning_text(warning: str) -> str:
    """Redact sensitive information from warning text."""
    redacted = warning
    
    # Redact PII patterns
    for pattern in PII_PATTERNS:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    
    # Redact source text patterns
    for pattern in SOURCE_TEXT_PATTERNS:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    
    # Redact long quoted text
    redacted = re.sub(r'"[^"]{30,}"', '"[REDACTED]"', redacted)
    
    return redacted


def _get_contradiction_types(contradictions: List[Dict[str, Any]]) -> str:
    """Get a summary of contradiction types."""
    types = set()
    for contradiction in contradictions:
        contradiction_type = contradiction.get("type", "unknown")
        types.add(contradiction_type)
    
    if not types:
        return "none"
    
    return ", ".join(sorted(types))


def _get_performance_summary(timings: Dict[str, Any]) -> str:
    """Get a performance summary from timings."""
    total_ms = timings.get("total_ms", 0.0)
    orchestration_ms = timings.get("orchestration_ms", 0.0)
    planning_ms = timings.get("planning_ms", 0.0)
    
    if total_ms > 0:
        orchestration_pct = (orchestration_ms / total_ms) * 100
        planning_pct = (planning_ms / total_ms) * 100
        return f"orchestration {orchestration_pct:.0f}%, planning {planning_pct:.0f}%"
    else:
        return "no timing data"


def get_role_summary_stats(trace: OrchestrationResult, role_key: str) -> Dict[str, Any]:
    """
    Get role-specific summary statistics for a trace.
    
    Args:
        trace: OrchestrationResult to analyze
        role_key: Role key ('general', 'pro', 'scholars', 'analytics', 'ops')
        
    Returns:
        Dictionary with role-specific summary statistics
    """
    if role_key not in ROLE_LEVELS:
        raise ValueError(f"Invalid role_key: {role_key}. Must be one of {list(ROLE_LEVELS.keys())}")
    
    # Get base stats
    base_stats = get_summary_stats(trace)
    
    # Add role-specific stats
    role_stats = base_stats.copy()
    role_stats["role_key"] = role_key
    role_stats["role_level"] = ROLE_LEVELS[role_key]
    role_stats["max_lines"] = 2 if role_key == "general" else (4 if role_key in ["pro", "scholars", "analytics"] else 6)
    role_stats["includes_raw_text"] = role_key != "general"
    role_stats["includes_pii"] = role_key == "ops"
    role_stats["includes_technical_details"] = role_key in ["pro", "scholars", "analytics", "ops"]
    role_stats["includes_performance_metrics"] = role_key == "ops"
    
    return role_stats