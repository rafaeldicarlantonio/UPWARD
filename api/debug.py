#!/usr/bin/env python3
"""
api/debug.py — Debug and observability endpoints.

Provides:
- /debug/metrics - Performance metrics with p50/p95
- /debug/config - Configuration inspection
- /debug/health - Health checks
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import time

from core.metrics import (
    get_all_metrics,
    get_histogram_stats,
    get_counter,
    PerformanceMetrics
)
from config import load_config
from feature_flags import get_perf_flags, get_all_flags

router = APIRouter()


@router.get("/debug/metrics")
def get_metrics() -> Dict[str, Any]:
    """
    Get all performance metrics with p50/p95 percentiles.
    
    Returns metrics for:
    - retrieval_ms (p50, p95)
    - graph_expand_ms (p50, p95)
    - packing_ms (p50, p95)
    - reviewer_ms (p50, p95)
    - Error rates
    - Fallback rates
    - Circuit breaker events
    """
    all_metrics = get_all_metrics()
    
    # Get performance histograms with percentiles
    performance = {
        "retrieval": get_histogram_stats("retrieval_ms"),
        "graph_expand": get_histogram_stats("graph_expand_ms"),
        "packing": get_histogram_stats("packing_ms"),
        "reviewer": get_histogram_stats("reviewer_ms"),
    }
    
    # Get specific counters
    counters = {
        "pinecone_timeouts": get_counter("pinecone_timeouts"),
        "pgvector_fallbacks": get_counter("pgvector_fallbacks"),
        "reviewer_skips": get_counter("reviewer_skips"),
        "circuit_opens": get_counter("circuit_opens"),
        "circuit_closes": get_counter("circuit_closes"),
    }
    
    # Calculate rates
    rates = {
        "retrieval_error_rate": PerformanceMetrics.get_error_rate("retrieval"),
        "pgvector_fallback_rate": PerformanceMetrics.get_fallback_rate(),
    }
    
    return {
        "timestamp": time.time(),
        "performance": performance,
        "counters": counters,
        "rates": rates,
        "all_metrics": all_metrics
    }


@router.get("/debug/metrics/summary")
def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a compact metrics summary with only key stats.
    
    Returns:
    - p50/p95 for each operation
    - Error rate
    - Fallback rate
    - Recent counter values
    """
    return {
        "timestamp": time.time(),
        "retrieval": {
            "p50": get_histogram_stats("retrieval_ms").get("p50", 0),
            "p95": get_histogram_stats("retrieval_ms").get("p95", 0),
            "count": get_histogram_stats("retrieval_ms").get("count", 0),
        },
        "graph_expand": {
            "p50": get_histogram_stats("graph_expand_ms").get("p50", 0),
            "p95": get_histogram_stats("graph_expand_ms").get("p95", 0),
            "count": get_histogram_stats("graph_expand_ms").get("count", 0),
        },
        "packing": {
            "p50": get_histogram_stats("packing_ms").get("p50", 0),
            "p95": get_histogram_stats("packing_ms").get("p95", 0),
            "count": get_histogram_stats("packing_ms").get("count", 0),
        },
        "reviewer": {
            "p50": get_histogram_stats("reviewer_ms").get("p50", 0),
            "p95": get_histogram_stats("reviewer_ms").get("p95", 0),
            "count": get_histogram_stats("reviewer_ms").get("count", 0),
            "skipped": get_counter("reviewer_skips"),
        },
        "errors": {
            "retrieval_error_rate": PerformanceMetrics.get_error_rate("retrieval"),
            "pinecone_timeouts": get_counter("pinecone_timeouts"),
        },
        "fallbacks": {
            "pgvector_fallback_rate": PerformanceMetrics.get_fallback_rate(),
            "pgvector_fallbacks": get_counter("pgvector_fallbacks"),
        },
        "circuit_breakers": {
            "opens": get_counter("circuit_opens"),
            "closes": get_counter("circuit_closes"),
        }
    }


@router.get("/debug/config")
def get_debug_config() -> Dict[str, Any]:
    """
    Get current configuration (safe subset).
    
    Returns configuration without sensitive values, with special
    sections for performance flags and feature flags.
    """
    try:
        config = load_config()
        
        # Filter out sensitive keys
        safe_config = {}
        perf_config = {}
        limit_config = {}
        
        for key, value in config.items():
            if any(sensitive in key.upper() for sensitive in ['KEY', 'SECRET', 'PASSWORD', 'TOKEN']):
                safe_config[key] = "***REDACTED***"
            elif key.startswith('PERF_'):
                perf_config[key] = value
            elif key.startswith('LIMITS_'):
                limit_config[key] = value
            else:
                safe_config[key] = value
        
        # Get performance flags in structured format
        perf_flags = get_perf_flags()
        
        # Get feature flags
        try:
            feature_flags = get_all_flags()
        except Exception:
            feature_flags = {}
        
        return {
            "performance": {
                "flags": perf_flags.get("flags", {}),
                "budgets": perf_flags.get("budgets", {}),
                "raw_config": perf_config
            },
            "resource_limits": limit_config,
            "feature_flags": feature_flags,
            "config": safe_config,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")


@router.get("/debug/health")
def get_health() -> Dict[str, Any]:
    """
    Get basic health status.
    
    Returns:
    - Service uptime
    - Recent error rate
    - Circuit breaker status
    """
    all_metrics = get_all_metrics()
    uptime = all_metrics.get("uptime_seconds", 0)
    
    # Check for concerning metrics
    health_status = "healthy"
    warnings = []
    
    error_rate = PerformanceMetrics.get_error_rate("retrieval")
    if error_rate > 0.1:  # More than 10% errors
        health_status = "degraded"
        warnings.append(f"High error rate: {error_rate:.1%}")
    
    circuit_opens = get_counter("circuit_opens")
    circuit_closes = get_counter("circuit_closes")
    open_circuits = circuit_opens - circuit_closes
    if open_circuits > 0:
        health_status = "degraded"
        warnings.append(f"Open circuits: {open_circuits}")
    
    fallback_rate = PerformanceMetrics.get_fallback_rate()
    if fallback_rate > 0.2:  # More than 20% fallbacks
        health_status = "degraded"
        warnings.append(f"High fallback rate: {fallback_rate:.1%}")
    
    return {
        "status": health_status,
        "uptime_seconds": uptime,
        "warnings": warnings,
        "metrics_summary": {
            "error_rate": error_rate,
            "fallback_rate": fallback_rate,
            "open_circuits": open_circuits,
        },
        "timestamp": time.time()
    }
