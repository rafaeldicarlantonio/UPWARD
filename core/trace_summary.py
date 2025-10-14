"""
Trace summary generator for creating concise summaries of orchestration traces.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
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