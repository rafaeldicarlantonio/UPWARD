#!/usr/bin/env python3
"""
core/health.py — Health probes for external services.

Provides health check functions for:
- Pinecone vector store
- Reviewer LLM
- Other external dependencies
"""

import time
from typing import Tuple, Optional, Dict, Any

from core.metrics import increment_counter, observe_histogram


class HealthCheckResult:
    """Result of a health check."""
    
    def __init__(
        self,
        service: str,
        is_healthy: bool,
        latency_ms: float,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.service = service
        self.is_healthy = is_healthy
        self.latency_ms = latency_ms
        self.error = error
        self.details = details or {}
        self.timestamp = time.time()
    
    def __repr__(self):
        status = "healthy" if self.is_healthy else "unhealthy"
        return f"<HealthCheck {self.service}: {status} ({self.latency_ms:.1f}ms)>"


def check_pinecone_health() -> HealthCheckResult:
    """
    Check Pinecone vector store health.
    
    Returns:
        HealthCheckResult with status and latency
    """
    start_time = time.time()
    service = "pinecone"
    
    try:
        # Try to import and access Pinecone
        from vendors.pinecone_client import get_index
        
        # Get index and try a lightweight operation
        index = get_index()
        stats = index.describe_index_stats()
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Record success
        increment_counter("health_check.success", labels={"service": service})
        observe_histogram("health_check.latency_ms", latency_ms, labels={"service": service})
        
        return HealthCheckResult(
            service=service,
            is_healthy=True,
            latency_ms=latency_ms,
            details={
                "total_vectors": stats.get("total_vector_count", 0) if stats else 0
            }
        )
        
    except ImportError as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = f"Import failed: {str(e)}"
        
        increment_counter("health_check.failure", labels={
            "service": service,
            "error_type": "ImportError"
        })
        
        return HealthCheckResult(
            service=service,
            is_healthy=False,
            latency_ms=latency_ms,
            error=error_msg
        )
        
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = f"{type(e).__name__}: {str(e)}"
        
        increment_counter("health_check.failure", labels={
            "service": service,
            "error_type": type(e).__name__
        })
        
        return HealthCheckResult(
            service=service,
            is_healthy=False,
            latency_ms=latency_ms,
            error=error_msg
        )


def check_reviewer_health() -> HealthCheckResult:
    """
    Check reviewer LLM health.
    
    Returns:
        HealthCheckResult with status and latency
    """
    start_time = time.time()
    service = "reviewer"
    
    try:
        # Check if reviewer is enabled
        from config import load_config
        cfg = load_config()
        
        if not cfg.get("PERF_REVIEWER_ENABLED", True):
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service=service,
                is_healthy=True,
                latency_ms=latency_ms,
                details={"status": "disabled"}
            )
        
        # Try to import and access LLM client
        try:
            from vendors.openai_client import get_client
            client = get_client()
            
            # Simple health check - verify client is initialized
            if client is None:
                raise Exception("Client not initialized")
            
            latency_ms = (time.time() - start_time) * 1000
            
            increment_counter("health_check.success", labels={"service": service})
            observe_histogram("health_check.latency_ms", latency_ms, labels={"service": service})
            
            return HealthCheckResult(
                service=service,
                is_healthy=True,
                latency_ms=latency_ms,
                details={"status": "ready"}
            )
            
        except ImportError as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"Import failed: {str(e)}"
            
            increment_counter("health_check.failure", labels={
                "service": service,
                "error_type": "ImportError"
            })
            
            return HealthCheckResult(
                service=service,
                is_healthy=False,
                latency_ms=latency_ms,
                error=error_msg
            )
    
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = f"{type(e).__name__}: {str(e)}"
        
        increment_counter("health_check.failure", labels={
            "service": service,
            "error_type": type(e).__name__
        })
        
        return HealthCheckResult(
            service=service,
            is_healthy=False,
            latency_ms=latency_ms,
            error=error_msg
        )


def check_all_services() -> Dict[str, HealthCheckResult]:
    """
    Check health of all external services.
    
    Returns:
        Dictionary mapping service name to HealthCheckResult
    """
    results = {}
    
    # Check Pinecone
    results["pinecone"] = check_pinecone_health()
    
    # Check reviewer
    results["reviewer"] = check_reviewer_health()
    
    return results


def is_service_healthy(service: str) -> bool:
    """
    Quick health check for a specific service.
    
    Args:
        service: Service name ("pinecone" or "reviewer")
        
    Returns:
        True if healthy, False otherwise
    """
    if service == "pinecone":
        result = check_pinecone_health()
    elif service == "reviewer":
        result = check_reviewer_health()
    else:
        return False
    
    return result.is_healthy
