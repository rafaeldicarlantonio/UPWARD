# core/metrics.py — comprehensive metrics collection and reporting

import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from contextlib import contextmanager
import json

@dataclass
class MetricValue:
    """A single metric value with metadata."""
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)

@dataclass
class MetricCounter:
    """A counter metric that can only increase."""
    name: str
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

@dataclass
class MetricGauge:
    """A gauge metric that can increase or decrease."""
    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

@dataclass
class MetricHistogram:
    """A histogram metric for tracking distributions."""
    name: str
    buckets: List[float] = field(default_factory=lambda: [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0])
    counts: List[int] = field(default_factory=lambda: [0] * 12)
    sum: float = 0.0
    count: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

class MetricsCollector:
    """Thread-safe metrics collector."""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._counters: Dict[str, MetricCounter] = {}
        self._gauges: Dict[str, MetricGauge] = {}
        self._histograms: Dict[str, MetricHistogram] = {}
        self._start_time = time.time()
    
    def _get_metric_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Generate a unique key for a metric with labels."""
        if not labels:
            return name
        sorted_labels = sorted(labels.items())
        label_str = ",".join(f"{k}={v}" for k, v in sorted_labels)
        return f"{name}{{{label_str}}}"
    
    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            if key not in self._counters:
                self._counters[key] = MetricCounter(name=name, labels=labels or {})
            self._counters[key].value += value
            self._counters[key].last_updated = time.time()
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            if key not in self._gauges:
                self._gauges[key] = MetricGauge(name=name, labels=labels or {})
            self._gauges[key].value = value
            self._gauges[key].last_updated = time.time()
    
    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Observe a value in a histogram metric."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            if key not in self._histograms:
                self._histograms[key] = MetricHistogram(name=name, labels=labels or {})
            
            histogram = self._histograms[key]
            histogram.sum += value
            histogram.count += 1
            histogram.last_updated = time.time()
            
            # Update bucket counts
            for i, bucket in enumerate(histogram.buckets):
                if value <= bucket:
                    histogram.counts[i] += 1
                    break
            else:
                # Value exceeds all buckets, increment the last one
                histogram.counts[-1] += 1
    
    def get_counter(self, name: str, labels: Dict[str, str] = None) -> int:
        """Get the current value of a counter."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            return self._counters.get(key, MetricCounter(name=name, labels=labels or {})).value
    
    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get the current value of a gauge."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            return self._gauges.get(key, MetricGauge(name=name, labels=labels or {})).value
    
    def get_histogram_stats(self, name: str, labels: Dict[str, str] = None) -> Dict[str, Any]:
        """Get histogram statistics."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            histogram = self._histograms.get(key, MetricHistogram(name=name, labels=labels or {}))
            
            if histogram.count == 0:
                return {
                    "count": 0,
                    "sum": 0.0,
                    "avg": 0.0,
                    "buckets": dict(zip(histogram.buckets, histogram.counts))
                }
            
            return {
                "count": histogram.count,
                "sum": histogram.sum,
                "avg": histogram.sum / histogram.count,
                "buckets": dict(zip(histogram.buckets, histogram.counts))
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics in a structured format."""
        with self._lock:
            metrics = {
                "counters": {},
                "gauges": {},
                "histograms": {},
                "uptime_seconds": time.time() - self._start_time,
                "timestamp": time.time()
            }
            
            # Collect counters
            for key, counter in self._counters.items():
                if counter.name not in metrics["counters"]:
                    metrics["counters"][counter.name] = []
                metrics["counters"][counter.name].append({
                    "value": counter.value,
                    "labels": counter.labels,
                    "last_updated": counter.last_updated
                })
            
            # Collect gauges
            for key, gauge in self._gauges.items():
                if gauge.name not in metrics["gauges"]:
                    metrics["gauges"][gauge.name] = []
                metrics["gauges"][gauge.name].append({
                    "value": gauge.value,
                    "labels": gauge.labels,
                    "last_updated": gauge.last_updated
                })
            
            # Collect histograms
            for key, histogram in self._histograms.items():
                if histogram.name not in metrics["histograms"]:
                    metrics["histograms"][histogram.name] = []
                metrics["histograms"][histogram.name].append({
                    "stats": self.get_histogram_stats(histogram.name, histogram.labels),
                    "labels": histogram.labels,
                    "last_updated": histogram.last_updated
                })
            
            return metrics
    
    def reset_metrics(self):
        """Reset all metrics to zero."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._start_time = time.time()

# Global metrics collector instance
_metrics = MetricsCollector()

# Set up audit logger for RBAC
import logging
audit_logger = logging.getLogger("rbac.audit")

# Convenience functions for easy access
def increment_counter(name: str, value: int = 1, labels: Dict[str, str] = None):
    """Increment a counter metric."""
    _metrics.increment_counter(name, value, labels)

def set_gauge(name: str, value: float, labels: Dict[str, str] = None):
    """Set a gauge metric value."""
    _metrics.set_gauge(name, value, labels)

def observe_histogram(name: str, value: float, labels: Dict[str, str] = None):
    """Observe a value in a histogram metric."""
    _metrics.observe_histogram(name, value, labels)

def get_counter(name: str, labels: Dict[str, str] = None) -> int:
    """Get the current value of a counter."""
    return _metrics.get_counter(name, labels)

def get_gauge(name: str, labels: Dict[str, str] = None) -> float:
    """Get the current value of a gauge."""
    return _metrics.get_gauge(name, labels)

def get_histogram_stats(name: str, labels: Dict[str, str] = None) -> Dict[str, Any]:
    """Get histogram statistics."""
    return _metrics.get_histogram_stats(name, labels)

def get_all_metrics() -> Dict[str, Any]:
    """Get all metrics in a structured format."""
    return _metrics.get_all_metrics()

def reset_metrics():
    """Reset all metrics to zero."""
    _metrics.reset_metrics()

# Specific metrics for our use case
class OrchestratorMetrics:
    """Specific metrics for orchestrator system."""
    
    @staticmethod
    def record_redo_run(success: bool, total_time_ms: float, stages_count: int):
        """Record a REDO orchestration run."""
        increment_counter("redo.runs", labels={"success": str(success)})
        observe_histogram("redo.run_duration_ms", total_time_ms, labels={"success": str(success)})
        observe_histogram("redo.stages_count", stages_count)
    
    @staticmethod
    def record_stage_timing(stage_name: str, duration_ms: float, success: bool = True):
        """Record stage execution timing."""
        observe_histogram(f"redo.stage.{stage_name}_ms", duration_ms, labels={"success": str(success)})
        increment_counter(f"redo.stage.{stage_name}_total", labels={"success": str(success)})
    
    @staticmethod
    def record_budget_overrun(overrun_ms: float, stage_name: str = None):
        """Record when orchestration exceeds time budget."""
        increment_counter("redo.budget_overruns", labels={"stage": stage_name or "unknown"})
        observe_histogram("redo.budget_overrun_ms", overrun_ms, labels={"stage": stage_name or "unknown"})
    
    @staticmethod
    def record_orchestration_contradictions(contradictions_count: int):
        """Record contradictions found during orchestration."""
        observe_histogram("redo.contradictions_found", contradictions_count)
        increment_counter("redo.contradiction_detections", labels={"has_contradictions": str(contradictions_count > 0)})
    
    @staticmethod
    def record_context_selection(selected_count: int, total_available: int):
        """Record context selection metrics."""
        observe_histogram("redo.context_selected_count", selected_count)
        observe_histogram("redo.context_selection_ratio", selected_count / max(total_available, 1))
        increment_counter("redo.context_selections")

class LedgerMetrics:
    """Specific metrics for ledger system."""
    
    @staticmethod
    def record_bytes_written(bytes_written: int, is_truncated: bool = False):
        """Record bytes written to ledger."""
        increment_counter("ledger.bytes_written", value=bytes_written, labels={"truncated": str(is_truncated)})
        observe_histogram("ledger.write_size_bytes", bytes_written, labels={"truncated": str(is_truncated)})
    
    @staticmethod
    def record_ledger_entry(session_id: str, message_id: str, size_bytes: int, is_truncated: bool = False):
        """Record a ledger entry."""
        increment_counter("ledger.entries_written", labels={"truncated": str(is_truncated)})
        observe_histogram("ledger.entry_size_bytes", size_bytes, labels={"truncated": str(is_truncated)})
    
    @staticmethod
    def record_ledger_truncation(original_size: int, truncated_size: int, truncation_ratio: float):
        """Record ledger truncation events."""
        increment_counter("ledger.truncations")
        observe_histogram("ledger.truncation_ratio", truncation_ratio)
        observe_histogram("ledger.truncation_savings_bytes", original_size - truncated_size)
    
    @staticmethod
    def record_ledger_hash_generation(algorithm: str, size_bytes: int, latency_ms: float):
        """Record ledger hash generation."""
        increment_counter("ledger.hash_generations", labels={"algorithm": algorithm})
        observe_histogram("ledger.hash_generation_latency_ms", latency_ms, labels={"algorithm": algorithm})
        observe_histogram("ledger.hash_generation_size_bytes", size_bytes)

class RetrievalMetrics:
    """Specific metrics for retrieval system."""
    
    @staticmethod
    def record_dual_query(explicate_k: int, implicate_k: int, latency_ms: float):
        """Record a dual query execution."""
        increment_counter("dual_queries_total", labels={"explicate_k": str(explicate_k), "implicate_k": str(implicate_k)})
        observe_histogram("dual_query_latency_ms", latency_ms, labels={"explicate_k": str(explicate_k), "implicate_k": str(implicate_k)})
    
    @staticmethod
    def record_legacy_query(latency_ms: float):
        """Record a legacy query execution."""
        increment_counter("legacy_queries_total")
        observe_histogram("legacy_query_latency_ms", latency_ms)
    
    @staticmethod
    def record_cache_hit(cache_type: str):
        """Record a cache hit."""
        increment_counter("cache_hits_total", labels={"cache_type": cache_type})
    
    @staticmethod
    def record_cache_miss(cache_type: str):
        """Record a cache miss."""
        increment_counter("cache_misses_total", labels={"cache_type": cache_type})
    
    @staticmethod
    def record_contradiction_detection(contradictions_found: int, contradiction_score: float):
        """Record contradiction detection results."""
        increment_counter("contradiction_detections_total", labels={"has_contradictions": str(contradictions_found > 0)})
        observe_histogram("contradiction_score", contradiction_score)
        if contradictions_found > 0:
            observe_histogram("contradictions_found_count", contradictions_found)
    
    @staticmethod
    def record_lift_score_at_k(k: int, lift_score: float):
        """Record LiftScore at position k."""
        observe_histogram("liftscore_at_k", lift_score, labels={"k": str(k)})
        increment_counter("liftscore_calculations_total", labels={"k": str(k)})
    
    @staticmethod
    def record_implicate_rank(rank: int):
        """Record implicate ranking position."""
        observe_histogram("implicate_rank", rank)
        increment_counter("implicate_rankings_total", labels={"rank": str(rank)})
    
    @staticmethod
    def record_retrieval_phase(phase: str, latency_ms: float):
        """Record retrieval phase timing."""
        observe_histogram(f"retrieval_{phase}_latency_ms", latency_ms)
        increment_counter(f"retrieval_{phase}_total")
    
    @staticmethod
    def record_entity_expansion(entities_expanded: int, latency_ms: float):
        """Record entity expansion metrics."""
        observe_histogram("entity_expansion_count", entities_expanded)
        observe_histogram("entity_expansion_latency_ms", latency_ms)
        increment_counter("entity_expansions_total")

# Context manager for timing operations
@contextmanager
def time_operation(operation_name: str, labels: Dict[str, str] = None):
    """Context manager to time an operation and record it as a histogram."""
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        observe_histogram(f"{operation_name}_latency_ms", duration_ms, labels)

# Utility functions for common patterns
def record_api_call(endpoint: str, method: str, status_code: int, latency_ms: float):
    """Record an API call with timing and status."""
    increment_counter("api_calls_total", labels={"endpoint": endpoint, "method": method, "status": str(status_code)})
    observe_histogram("api_call_latency_ms", latency_ms, labels={"endpoint": endpoint, "method": method})

def record_error(error_type: str, error_message: str = None):
    """Record an error occurrence."""
    increment_counter("errors_total", labels={"error_type": error_type})
    if error_message:
        increment_counter("error_messages_total", labels={"error_type": error_type, "message_hash": str(hash(error_message))})

def record_feature_flag_usage(flag_name: str, enabled: bool):
    """Record feature flag usage."""
    increment_counter("feature_flag_usage_total", labels={"flag": flag_name, "enabled": str(enabled)})


class IngestMetrics:
    """Specific metrics for ingest analysis pipeline."""
    
    @staticmethod
    def record_chunk_analyzed(
        verbs_count: int,
        frames_count: int,
        concepts_count: int,
        contradictions_count: int,
        duration_ms: float,
        success: bool = True
    ):
        """Record a chunk analysis operation."""
        increment_counter("ingest.analysis.chunks_total", labels={"success": str(success)})
        observe_histogram("ingest.analysis.verbs_per_chunk", verbs_count)
        observe_histogram("ingest.analysis.frames_per_chunk", frames_count)
        observe_histogram("ingest.analysis.concepts_suggested", concepts_count)
        observe_histogram("ingest.analysis.contradictions_found", contradictions_count)
        observe_histogram("ingest.analysis.duration_ms", duration_ms, labels={"success": str(success)})
    
    @staticmethod
    def record_timeout():
        """Record when chunk analysis times out."""
        increment_counter("ingest.analysis.timeout_count")
    
    @staticmethod
    def record_analysis_error(error_type: str):
        """Record when chunk analysis fails."""
        increment_counter("ingest.analysis.errors_total", labels={"error_type": error_type})
    
    @staticmethod
    def record_entities_created(concepts_count: int, frames_count: int, edges_count: int):
        """Record entities and edges created during commit."""
        observe_histogram("ingest.commit.concepts_created", concepts_count)
        observe_histogram("ingest.commit.frames_created", frames_count)
        observe_histogram("ingest.commit.edges_created", edges_count)
        increment_counter("ingest.commit.total")
    
    @staticmethod
    def record_commit_errors(error_count: int):
        """Record errors during commit phase."""
        if error_count > 0:
            increment_counter("ingest.commit.errors_total", value=error_count)


class ImplicateRefreshMetrics:
    """Specific metrics for implicate refresh worker."""
    
    @staticmethod
    def record_job_enqueued(entity_ids_count: int):
        """Record when implicate_refresh job is enqueued."""
        increment_counter("implicate_refresh.enqueued")
        observe_histogram("implicate_refresh.entity_ids_per_job", entity_ids_count)
    
    @staticmethod
    def record_job_processed(
        entity_ids_count: int,
        processed_count: int,
        upserted_count: int,
        duration_s: float,
        success: bool = True
    ):
        """Record when implicate_refresh job is processed."""
        increment_counter("implicate_refresh.processed", labels={"success": str(success)})
        observe_histogram("implicate_refresh.entities_requested", entity_ids_count)
        observe_histogram("implicate_refresh.entities_processed", processed_count)
        observe_histogram("implicate_refresh.entities_upserted", upserted_count)
        observe_histogram("implicate_refresh.job_duration_seconds", duration_s, labels={"success": str(success)})
    
    @staticmethod
    def record_job_failed(error_type: str, retry_count: int):
        """Record when implicate_refresh job fails."""
        increment_counter("implicate_refresh.failed", labels={"error_type": error_type})
        observe_histogram("implicate_refresh.retry_count", retry_count)
    
    @staticmethod
    def record_worker_iteration(jobs_processed: int, duration_s: float):
        """Record a worker iteration (run_once)."""
        increment_counter("implicate_refresh.worker_iterations")
        observe_histogram("implicate_refresh.jobs_per_iteration", jobs_processed)
        observe_histogram("implicate_refresh.iteration_duration_seconds", duration_s)
    
    @staticmethod
    def record_deduplication(original_count: int, deduplicated_count: int):
        """Record entity ID deduplication."""
        if original_count > deduplicated_count:
            duplicates = original_count - deduplicated_count
            increment_counter("implicate_refresh.duplicates_removed", value=duplicates)
            observe_histogram("implicate_refresh.deduplication_ratio", duplicates / original_count)


# Export the main functions and classes
__all__ = [
    'MetricsCollector', 'MetricCounter', 'MetricGauge', 'MetricHistogram',
    'increment_counter', 'set_gauge', 'observe_histogram', 'get_counter', 
    'get_gauge', 'get_histogram_stats', 'get_all_metrics', 'reset_metrics',
    'OrchestratorMetrics', 'LedgerMetrics', 'RetrievalMetrics', 'IngestMetrics',
    'ImplicateRefreshMetrics', 'ExternalCompareMetrics', 'time_operation', 
    'record_api_call', 'record_error', 'record_feature_flag_usage',
    # RBAC metrics
    'record_rbac_resolution', 'record_rbac_check', 'record_role_distribution',
    'record_retrieval_filtered', 'audit_rbac_denial', 'get_rbac_metrics',
    'reset_rbac_metrics',
    # External comparison audit
    'audit_external_compare_denial', 'audit_external_compare_timeout'
]

# ============================================================================
# RBAC-Specific Metrics and Auditing
# ============================================================================

def record_rbac_resolution(success: bool = True, auth_method: str = "unknown"):
    """
    Record a role resolution attempt.
    
    Args:
        success: Whether resolution succeeded
        auth_method: Authentication method used
    """
    increment_counter("rbac.resolutions", labels={"success": str(success).lower()})
    increment_counter("rbac.resolutions.by_method", labels={"method": auth_method})


def record_rbac_check(allowed: bool, capability: str, roles: List[str], route: str = ""):
    """
    Record an RBAC authorization check.
    
    Args:
        allowed: Whether access was granted
        capability: Capability being checked
        roles: User's roles
        route: Route being accessed
    """
    if allowed:
        increment_counter("rbac.allowed")
        increment_counter("rbac.allowed.by_capability", labels={"capability": capability})
    else:
        increment_counter("rbac.denied")
        increment_counter("rbac.denied.by_capability", labels={"capability": capability})
        if route:
            increment_counter("rbac.denied.by_route", labels={"route": route})


def record_role_distribution(role: str):
    """
    Record role distribution (tracks which roles are being used).
    
    Args:
        role: Role name
    """
    increment_counter("rbac.role_distribution", labels={"role": role})


def record_retrieval_filtered(filtered_count: int, total_count: int, caller_roles: List[str] = None):
    """
    Record items filtered during retrieval.
    
    Args:
        filtered_count: Number of items filtered out
        total_count: Total items before filtering
        caller_roles: Roles of the caller
    """
    increment_counter("retrieval.filtered_items", value=filtered_count)
    increment_counter("retrieval.total_items", value=total_count)
    
    if caller_roles:
        for role in caller_roles:
            increment_counter("retrieval.filtered_by_role", value=filtered_count, labels={"role": role})


def audit_rbac_denial(
    capability: str,
    user_id: Optional[str],
    roles: List[str],
    route: str,
    method: str = "unknown",
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Emit audit log entry for RBAC denial.
    
    Creates structured log entry for security monitoring.
    
    Args:
        capability: Capability that was denied
        user_id: User ID who was denied (None for anonymous)
        roles: User's roles
        route: Route/endpoint being accessed
        method: HTTP method
        metadata: Additional context
    """
    audit_entry = {
        "event": "rbac_denial",
        "capability": capability,
        "user_id": user_id or "anonymous",
        "roles": roles,
        "route": route,
        "method": method,
        "timestamp": time.time(),
    }
    
    if metadata:
        audit_entry["metadata"] = metadata
    
    # Log to audit logger with structured data
    audit_logger.warning(
        f"RBAC_DENIAL capability={capability} user={user_id or 'anonymous'} "
        f"roles={','.join(roles)} route={method} {route}",
        extra={"audit": audit_entry}
    )
    
    # Increment audit denial counter
    increment_counter("rbac.audit.denials")
    increment_counter("rbac.audit.denials.by_capability", labels={"capability": capability})


def get_rbac_metrics() -> Dict[str, Any]:
    """
    Get all RBAC-related metrics.
    
    Returns:
        Dictionary of RBAC metrics with resolution, authorization, and filtering stats
    """
    all_metrics = _metrics.get_all_metrics()
    
    # Extract RBAC and retrieval metrics
    rbac_metrics = {
        "resolutions": {},
        "authorization": {},
        "role_distribution": {},
        "retrieval": {},
        "audit": {}
    }
    
    # Parse counters
    for metric_name, metric_data in all_metrics.get("counters", {}).items():
        if metric_name.startswith("rbac."):
            category = metric_name.split(".")[1] if "." in metric_name else "other"
            if category not in rbac_metrics:
                rbac_metrics[category] = {}
            rbac_metrics[category][metric_name] = metric_data
        elif metric_name.startswith("retrieval."):
            rbac_metrics["retrieval"][metric_name] = metric_data
    
    return rbac_metrics


def reset_rbac_metrics():
    """Reset all RBAC-related metrics (useful for testing)."""
    # Get all metric keys
    all_metrics = _metrics.get_all_metrics()
    
    # We can't selectively reset in the current implementation,
    # but we can reset all metrics
    # In production, you might want to keep this or make it more selective
    _metrics.reset_metrics()


# ============================================================================
# External Comparison Metrics and Auditing
# ============================================================================

class ExternalCompareMetrics:
    """Specific metrics for external source comparison."""
    
    @staticmethod
    def record_request(allowed: bool, user_roles: List[str] = None):
        """
        Record an external compare request.
        
        Args:
            allowed: Whether the request was allowed
            user_roles: User's roles
        """
        increment_counter("external.compare.requests")
        if allowed:
            increment_counter("external.compare.allowed")
        else:
            increment_counter("external.compare.denied")
            if user_roles:
                for role in user_roles:
                    increment_counter("external.compare.denied.by_role", labels={"role": role})
    
    @staticmethod
    def record_comparison(
        duration_ms: float,
        internal_count: int,
        external_count: int,
        used_external: bool,
        success: bool = True
    ):
        """
        Record a comparison operation.
        
        Args:
            duration_ms: Duration in milliseconds
            internal_count: Number of internal sources
            external_count: Number of external sources
            used_external: Whether external sources were actually used
            success: Whether the comparison succeeded
        """
        observe_histogram("external.compare.ms", duration_ms, labels={"success": str(success).lower()})
        observe_histogram("external.compare.internal_count", internal_count)
        observe_histogram("external.compare.external_count", external_count)
        
        if used_external:
            increment_counter("external.compare.with_externals")
        else:
            increment_counter("external.compare.internal_only")
    
    @staticmethod
    def record_timeout(url: str = None):
        """
        Record a timeout during external fetch.
        
        Args:
            url: URL that timed out (optional)
        """
        increment_counter("external.compare.timeouts")
        if url:
            increment_counter("external.compare.timeouts.by_domain", labels={"domain": _extract_domain(url)})
    
    @staticmethod
    def record_fallback(reason: str = "unknown"):
        """
        Record a fallback to internal-only.
        
        Args:
            reason: Reason for fallback (timeout, error, etc.)
        """
        increment_counter("external.compare.fallbacks", labels={"reason": reason})
    
    @staticmethod
    def record_external_fetch(
        url: str,
        success: bool,
        duration_ms: float,
        error_type: str = None
    ):
        """
        Record an external fetch attempt.
        
        Args:
            url: URL being fetched
            success: Whether fetch succeeded
            duration_ms: Fetch duration
            error_type: Type of error if failed
        """
        domain = _extract_domain(url)
        
        if success:
            increment_counter("external.compare.fetches.success", labels={"domain": domain})
            observe_histogram("external.compare.fetch.ms", duration_ms, labels={"success": "true", "domain": domain})
        else:
            increment_counter("external.compare.fetches.failed", labels={"domain": domain})
            if error_type:
                increment_counter("external.compare.fetch.errors", labels={"error_type": error_type, "domain": domain})
    
    @staticmethod
    def set_policy_max_sources(max_sources: int):
        """
        Set the configured maximum external sources.
        
        Args:
            max_sources: Maximum number of external sources allowed
        """
        set_gauge("external.policy.max_sources", float(max_sources))
    
    @staticmethod
    def set_policy_timeout(timeout_ms: int):
        """
        Set the configured timeout for external requests.
        
        Args:
            timeout_ms: Timeout in milliseconds
        """
        set_gauge("external.policy.timeout_ms", float(timeout_ms))


def _extract_domain(url: str) -> str:
    """Extract domain from URL for labeling."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "unknown"
    except Exception:
        return "unknown"


def audit_external_compare_denial(
    user_id: Optional[str],
    roles: List[str],
    reason: str = "insufficient_permissions",
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Emit audit log entry for external compare denial.
    
    Args:
        user_id: User ID who was denied
        roles: User's roles
        reason: Reason for denial
        metadata: Additional context
    """
    audit_entry = {
        "event": "external_compare_denial",
        "user_id": user_id or "anonymous",
        "roles": roles,
        "reason": reason,
        "timestamp": time.time(),
    }
    
    if metadata:
        audit_entry["metadata"] = metadata
    
    # Log to audit logger
    audit_logger.warning(
        f"EXTERNAL_COMPARE_DENIAL user={user_id or 'anonymous'} "
        f"roles={','.join(roles)} reason={reason}",
        extra={"audit": audit_entry}
    )
    
    # Increment audit counter
    increment_counter("external.compare.audit.denials", labels={"reason": reason})


def audit_external_compare_timeout(
    url: str,
    timeout_ms: int,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Emit audit log entry for external compare timeout.
    
    Args:
        url: URL that timed out
        timeout_ms: Timeout threshold
        user_id: User ID making the request
        metadata: Additional context
    """
    domain = _extract_domain(url)
    
    audit_entry = {
        "event": "external_compare_timeout",
        "url": url,
        "domain": domain,
        "timeout_ms": timeout_ms,
        "user_id": user_id or "anonymous",
        "timestamp": time.time(),
    }
    
    if metadata:
        audit_entry["metadata"] = metadata
    
    # Log to audit logger
    audit_logger.warning(
        f"EXTERNAL_COMPARE_TIMEOUT url={url} domain={domain} "
        f"timeout_ms={timeout_ms} user={user_id or 'anonymous'}",
        extra={"audit": audit_entry}
    )
    
    # Increment audit counter
    increment_counter("external.compare.audit.timeouts", labels={"domain": domain})
