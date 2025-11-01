"""
Tests for external comparison metrics and audit logging.

Verifies:
- All counters increment correctly
- Histogram records values
- Gauge tracks policy values
- Audit logs emitted for denials and timeouts
"""

import pytest
import os
import logging
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from typing import Dict, Any, List

# Set environment variables before imports
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_KEY', 'test-key')
os.environ.setdefault('PINECONE_API_KEY', 'test-key')
os.environ.setdefault('PINECONE_INDEX', 'test-index')
os.environ.setdefault('PINECONE_EXPLICATE_INDEX', 'test-explicate')
os.environ.setdefault('PINECONE_IMPLICATE_INDEX', 'test-implicate')

# Import API components
try:
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None
    FastAPI = None

from core.metrics import (
    ExternalCompareMetrics,
    get_counter,
    get_gauge,
    get_histogram_stats,
    reset_metrics,
    audit_external_compare_denial,
    audit_external_compare_timeout,
    audit_logger
)
from api.factate import router
from core.factare.service import ComparisonResult, ComparisonOptions
from core.factare.summary import CompareSummary

# Skip all tests if FastAPI not available
pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI not installed"
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_test_metrics():
    """Reset metrics before each test."""
    reset_metrics()
    yield
    reset_metrics()


@pytest.fixture
def app():
    """Create FastAPI test app."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not available")
    
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_comparison_result():
    """Mock ComparisonResult."""
    result = Mock(spec=ComparisonResult)
    
    summary = Mock(spec=CompareSummary)
    summary.to_dict.return_value = {
        "query": "test query",
        "internal_sources": [{"id": "mem_1"}],
        "summary_text": "Test summary"
    }
    
    result.compare_summary = summary
    result.contradictions = []
    result.used_external = False
    result.timings = {
        "internal_ms": 100.0,
        "external_ms": 0.0,
        "total_ms": 100.0,
        "redaction_ms": 0.0
    }
    result.metadata = {
        "user_roles": ["pro"],
        "internal_candidates_count": 1,
        "external_urls_provided": 0
    }
    
    return result


@pytest.fixture
def mock_comparison_result_with_external():
    """Mock ComparisonResult with external sources."""
    result = Mock(spec=ComparisonResult)
    
    summary = Mock(spec=CompareSummary)
    summary.to_dict.return_value = {
        "query": "test query",
        "internal_sources": [{"id": "mem_1"}],
        "external_sources": {
            "heading": "External sources",
            "items": [
                {
                    "url": "https://en.wikipedia.org/wiki/Test",
                    "snippet": "Test content",
                    "provenance": {"url": "https://en.wikipedia.org/wiki/Test"}
                }
            ]
        },
        "summary_text": "Test summary"
    }
    
    result.compare_summary = summary
    result.contradictions = []
    result.used_external = True
    result.timings = {
        "internal_ms": 100.0,
        "external_ms": 500.0,
        "total_ms": 600.0,
        "redaction_ms": 10.0
    }
    result.metadata = {
        "user_roles": ["pro"],
        "internal_candidates_count": 1,
        "external_urls_provided": 1,
        "external_urls_used": 1,
        "timeout_count": 0
    }
    
    return result


@pytest.fixture
def mock_factare_service():
    """Mock FactareService."""
    service = Mock()
    return service


# ============================================================================
# Test: Counter Metrics
# ============================================================================

class TestCounterMetrics:
    """Test counter metrics increment correctly."""
    
    def test_record_request_allowed(self):
        """Test external.compare.requests and external.compare.allowed."""
        ExternalCompareMetrics.record_request(allowed=True, user_roles=["pro"])
        
        assert get_counter("external.compare.requests") == 1
        assert get_counter("external.compare.allowed") == 1
        assert get_counter("external.compare.denied") == 0
    
    def test_record_request_denied(self):
        """Test external.compare.denied and per-role tracking."""
        ExternalCompareMetrics.record_request(allowed=False, user_roles=["general"])
        
        assert get_counter("external.compare.requests") == 1
        assert get_counter("external.compare.denied") == 1
        assert get_counter("external.compare.allowed") == 0
        assert get_counter("external.compare.denied.by_role", labels={"role": "general"}) == 1
    
    def test_record_multiple_requests(self):
        """Test multiple requests increment correctly."""
        ExternalCompareMetrics.record_request(allowed=True, user_roles=["pro"])
        ExternalCompareMetrics.record_request(allowed=False, user_roles=["general"])
        ExternalCompareMetrics.record_request(allowed=True, user_roles=["analytics"])
        
        assert get_counter("external.compare.requests") == 3
        assert get_counter("external.compare.allowed") == 2
        assert get_counter("external.compare.denied") == 1
    
    def test_record_timeout(self):
        """Test external.compare.timeouts counter."""
        ExternalCompareMetrics.record_timeout(url="https://example.com/page")
        ExternalCompareMetrics.record_timeout(url="https://example.com/other")
        
        assert get_counter("external.compare.timeouts") == 2
        assert get_counter("external.compare.timeouts.by_domain", labels={"domain": "example.com"}) == 2
    
    def test_record_fallback(self):
        """Test external.compare.fallbacks counter."""
        ExternalCompareMetrics.record_fallback(reason="timeout")
        ExternalCompareMetrics.record_fallback(reason="error")
        
        assert get_counter("external.compare.fallbacks", labels={"reason": "timeout"}) == 1
        assert get_counter("external.compare.fallbacks", labels={"reason": "error"}) == 1
    
    def test_record_comparison_with_externals(self):
        """Test external.compare.with_externals counter."""
        ExternalCompareMetrics.record_comparison(
            duration_ms=500.0,
            internal_count=2,
            external_count=1,
            used_external=True,
            success=True
        )
        
        assert get_counter("external.compare.with_externals") == 1
        assert get_counter("external.compare.internal_only") == 0
    
    def test_record_comparison_internal_only(self):
        """Test external.compare.internal_only counter."""
        ExternalCompareMetrics.record_comparison(
            duration_ms=200.0,
            internal_count=2,
            external_count=0,
            used_external=False,
            success=True
        )
        
        assert get_counter("external.compare.internal_only") == 1
        assert get_counter("external.compare.with_externals") == 0
    
    def test_record_external_fetch_success(self):
        """Test external.compare.fetches.success counter."""
        ExternalCompareMetrics.record_external_fetch(
            url="https://en.wikipedia.org/wiki/Test",
            success=True,
            duration_ms=300.0
        )
        
        assert get_counter("external.compare.fetches.success", labels={"domain": "en.wikipedia.org"}) == 1
        assert get_counter("external.compare.fetches.failed", labels={"domain": "en.wikipedia.org"}) == 0
    
    def test_record_external_fetch_failed(self):
        """Test external.compare.fetches.failed counter."""
        ExternalCompareMetrics.record_external_fetch(
            url="https://example.com/page",
            success=False,
            duration_ms=50.0,
            error_type="timeout"
        )
        
        assert get_counter("external.compare.fetches.failed", labels={"domain": "example.com"}) == 1
        assert get_counter("external.compare.fetch.errors", labels={"error_type": "timeout", "domain": "example.com"}) == 1


# ============================================================================
# Test: Histogram Metrics
# ============================================================================

class TestHistogramMetrics:
    """Test histogram metrics record values correctly."""
    
    def test_record_comparison_duration(self):
        """Test external.compare.ms histogram."""
        ExternalCompareMetrics.record_comparison(
            duration_ms=250.5,
            internal_count=2,
            external_count=1,
            used_external=True,
            success=True
        )
        
        stats = get_histogram_stats("external.compare.ms", labels={"success": "true"})
        assert stats["count"] == 1
        assert stats["sum"] == 250.5
        assert stats["avg"] == 250.5
    
    def test_record_comparison_counts(self):
        """Test internal_count and external_count histograms."""
        ExternalCompareMetrics.record_comparison(
            duration_ms=200.0,
            internal_count=5,
            external_count=3,
            used_external=True,
            success=True
        )
        
        internal_stats = get_histogram_stats("external.compare.internal_count")
        assert internal_stats["count"] == 1
        assert internal_stats["sum"] == 5.0
        
        external_stats = get_histogram_stats("external.compare.external_count")
        assert external_stats["count"] == 1
        assert external_stats["sum"] == 3.0
    
    def test_record_multiple_comparisons(self):
        """Test histogram aggregation over multiple calls."""
        ExternalCompareMetrics.record_comparison(100.0, 2, 1, True, True)
        ExternalCompareMetrics.record_comparison(200.0, 3, 2, True, True)
        ExternalCompareMetrics.record_comparison(300.0, 1, 0, False, True)
        
        stats = get_histogram_stats("external.compare.ms", labels={"success": "true"})
        assert stats["count"] == 3
        assert stats["sum"] == 600.0
        assert abs(stats["avg"] - 200.0) < 0.01
    
    def test_record_fetch_duration(self):
        """Test external.compare.fetch.ms histogram."""
        ExternalCompareMetrics.record_external_fetch(
            url="https://example.com",
            success=True,
            duration_ms=150.0
        )
        
        stats = get_histogram_stats("external.compare.fetch.ms", labels={"success": "true", "domain": "example.com"})
        assert stats["count"] == 1
        assert stats["sum"] == 150.0


# ============================================================================
# Test: Gauge Metrics
# ============================================================================

class TestGaugeMetrics:
    """Test gauge metrics track policy values."""
    
    def test_set_policy_max_sources(self):
        """Test external.policy.max_sources gauge."""
        ExternalCompareMetrics.set_policy_max_sources(5)
        assert get_gauge("external.policy.max_sources") == 5.0
        
        ExternalCompareMetrics.set_policy_max_sources(10)
        assert get_gauge("external.policy.max_sources") == 10.0
    
    def test_set_policy_timeout(self):
        """Test external.policy.timeout_ms gauge."""
        ExternalCompareMetrics.set_policy_timeout(2000)
        assert get_gauge("external.policy.timeout_ms") == 2000.0
        
        ExternalCompareMetrics.set_policy_timeout(5000)
        assert get_gauge("external.policy.timeout_ms") == 5000.0


# ============================================================================
# Test: Audit Logging
# ============================================================================

class TestAuditLogging:
    """Test audit log entries are emitted correctly."""
    
    def test_audit_external_compare_denial(self, caplog):
        """Test denial audit log entry."""
        with caplog.at_level(logging.WARNING, logger="rbac.audit"):
            audit_external_compare_denial(
                user_id="user_123",
                roles=["general"],
                reason="insufficient_permissions",
                metadata={"query": "test query"}
            )
        
        # Check audit log was emitted
        assert len(caplog.records) > 0
        record = caplog.records[0]
        assert "EXTERNAL_COMPARE_DENIAL" in record.message
        assert "user=user_123" in record.message
        assert "roles=general" in record.message
        
        # Check audit entry structure
        assert hasattr(record, 'audit')
        audit_entry = record.audit
        assert audit_entry["event"] == "external_compare_denial"
        assert audit_entry["user_id"] == "user_123"
        assert audit_entry["roles"] == ["general"]
        assert audit_entry["reason"] == "insufficient_permissions"
        assert audit_entry["metadata"]["query"] == "test query"
        
        # Check counter incremented
        assert get_counter("external.compare.audit.denials", labels={"reason": "insufficient_permissions"}) == 1
    
    def test_audit_external_compare_timeout(self, caplog):
        """Test timeout audit log entry."""
        with caplog.at_level(logging.WARNING, logger="rbac.audit"):
            audit_external_compare_timeout(
                url="https://slow.example.com/page",
                timeout_ms=2000,
                user_id="user_456",
                metadata={"query": "test query"}
            )
        
        # Check audit log was emitted
        assert len(caplog.records) > 0
        record = caplog.records[0]
        assert "EXTERNAL_COMPARE_TIMEOUT" in record.message
        assert "url=https://slow.example.com/page" in record.message
        assert "timeout_ms=2000" in record.message
        
        # Check audit entry structure
        assert hasattr(record, 'audit')
        audit_entry = record.audit
        assert audit_entry["event"] == "external_compare_timeout"
        assert audit_entry["url"] == "https://slow.example.com/page"
        assert audit_entry["domain"] == "slow.example.com"
        assert audit_entry["timeout_ms"] == 2000
        
        # Check counter incremented
        assert get_counter("external.compare.audit.timeouts", labels={"domain": "slow.example.com"}) == 1
    
    def test_audit_anonymous_user(self, caplog):
        """Test audit log for anonymous user."""
        with caplog.at_level(logging.WARNING, logger="rbac.audit"):
            audit_external_compare_denial(
                user_id=None,
                roles=["general"],
                reason="insufficient_permissions"
            )
        
        record = caplog.records[0]
        assert "user=anonymous" in record.message
        assert record.audit["user_id"] == "anonymous"


# ============================================================================
# Test: API Integration
# ============================================================================

@pytest.mark.anyio
class TestAPIIntegration:
    """Test metrics and audit logging in API endpoint."""
    
    async def test_successful_comparison_increments_metrics(
        self,
        client,
        mock_comparison_result,
        mock_factare_service
    ):
        """Test successful comparison records metrics."""
        mock_factare_service.compare = AsyncMock(return_value=mock_comparison_result)
        
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "test query",
                    "retrieval_candidates": [
                        {
                            "id": "mem_1",
                            "content": "test",
                            "source": "internal",
                            "score": 0.9
                        }
                    ],
                    "user_roles": ["pro"]
                }
            )
        
        assert response.status_code == 200
        
        # Check metrics were recorded
        assert get_counter("external.compare.internal_only") == 1
        assert get_gauge("external.policy.max_sources") == 5.0  # default
    
    async def test_external_comparison_increments_metrics(
        self,
        client,
        mock_comparison_result_with_external,
        mock_factare_service
    ):
        """Test external comparison records all metrics."""
        mock_factare_service.compare = AsyncMock(return_value=mock_comparison_result_with_external)
        
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "test query",
                    "retrieval_candidates": [{"id": "mem_1", "content": "test", "source": "internal", "score": 0.9}],
                    "external_urls": ["https://en.wikipedia.org/wiki/Test"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
        
        assert response.status_code == 200
        
        # Check metrics were recorded
        assert get_counter("external.compare.requests") == 1
        assert get_counter("external.compare.allowed") == 1
        assert get_counter("external.compare.with_externals") == 1
    
    async def test_denied_request_audited(
        self,
        client,
        caplog
    ):
        """Test denied external compare request is audited."""
        with patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=False), \
             caplog.at_level(logging.WARNING, logger="rbac.audit"):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "test query",
                    "retrieval_candidates": [{"id": "mem_1", "content": "test", "source": "internal", "score": 0.9}],
                    "external_urls": ["https://example.com"],
                    "user_roles": ["general"],
                    "options": {"allow_external": True}
                },
                headers={"X-User-ID": "user_789"}
            )
        
        assert response.status_code == 403
        
        # Check metrics
        assert get_counter("external.compare.denied") == 1
        
        # Check audit log
        assert any("EXTERNAL_COMPARE_DENIAL" in record.message for record in caplog.records)
    
    async def test_timeout_audited(
        self,
        client,
        mock_factare_service,
        caplog
    ):
        """Test timeout is audited."""
        # Mock result with timeout
        result = Mock(spec=ComparisonResult)
        summary = Mock(spec=CompareSummary)
        summary.to_dict.return_value = {"query": "test", "internal_sources": []}
        result.compare_summary = summary
        result.contradictions = []
        result.used_external = False
        result.timings = {"internal_ms": 100.0, "external_ms": 0.0, "total_ms": 100.0, "redaction_ms": 0.0}
        result.metadata = {
            "external_urls_provided": 1,
            "timeout_count": 1,
            "internal_candidates_count": 1
        }
        
        mock_factare_service.compare = AsyncMock(return_value=result)
        
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True), \
             caplog.at_level(logging.WARNING, logger="rbac.audit"):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "test query",
                    "retrieval_candidates": [{"id": "mem_1", "content": "test", "source": "internal", "score": 0.9}],
                    "external_urls": ["https://slow.example.com/page"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True, "timeout_seconds": 2}
                },
                headers={"X-User-ID": "user_999"}
            )
        
        assert response.status_code == 200
        
        # Check timeout metrics
        assert get_counter("external.compare.timeouts") == 1
        
        # Check audit log
        assert any("EXTERNAL_COMPARE_TIMEOUT" in record.message for record in caplog.records)
    
    async def test_fallback_recorded(
        self,
        client,
        mock_comparison_result,
        mock_factare_service
    ):
        """Test fallback is recorded when external requested but not used."""
        mock_factare_service.compare = AsyncMock(return_value=mock_comparison_result)
        
        with patch('api.factate.get_factare_service', return_value=mock_factare_service), \
             patch('api.factate.get_feature_flag', return_value=True), \
             patch('api.factate.validate_factare_access', return_value=True):
            
            response = client.post(
                "/factate/compare",
                json={
                    "query": "test query",
                    "retrieval_candidates": [{"id": "mem_1", "content": "test", "source": "internal", "score": 0.9}],
                    "external_urls": ["https://example.com"],
                    "user_roles": ["pro"],
                    "options": {"allow_external": True}
                }
            )
        
        assert response.status_code == 200
        
        # Check fallback recorded
        assert get_counter("external.compare.fallbacks", labels={"reason": "service_denied_or_failed"}) == 1


# ============================================================================
# Test: Acceptance Criteria
# ============================================================================

class TestAcceptanceCriteria:
    """Direct verification of all acceptance criteria."""
    
    def test_acceptance_all_counters_present(self):
        """
        Acceptance: Counters for requests, allowed, denied, timeouts, fallbacks.
        """
        # Exercise all counters
        ExternalCompareMetrics.record_request(allowed=True)
        ExternalCompareMetrics.record_request(allowed=False)
        ExternalCompareMetrics.record_timeout()
        ExternalCompareMetrics.record_fallback(reason="test")
        
        # Verify all counters increment
        assert get_counter("external.compare.requests") >= 1
        assert get_counter("external.compare.allowed") >= 1
        assert get_counter("external.compare.denied") >= 1
        assert get_counter("external.compare.timeouts") >= 1
        assert get_counter("external.compare.fallbacks", labels={"reason": "test"}) >= 1
    
    def test_acceptance_histogram_records_duration(self):
        """
        Acceptance: Histogram external.compare.ms records duration.
        """
        ExternalCompareMetrics.record_comparison(
            duration_ms=123.45,
            internal_count=2,
            external_count=1,
            used_external=True,
            success=True
        )
        
        stats = get_histogram_stats("external.compare.ms", labels={"success": "true"})
        assert stats["count"] == 1
        assert stats["sum"] == 123.45
    
    def test_acceptance_gauge_tracks_policy(self):
        """
        Acceptance: Gauge external.policy.max_sources tracks policy value.
        """
        ExternalCompareMetrics.set_policy_max_sources(7)
        assert get_gauge("external.policy.max_sources") == 7.0
    
    def test_acceptance_audit_denial(self, caplog):
        """
        Acceptance: Audit log entry when user without access requests external compare.
        """
        with caplog.at_level(logging.WARNING, logger="rbac.audit"):
            audit_external_compare_denial(
                user_id="test_user",
                roles=["general"],
                reason="insufficient_permissions"
            )
        
        assert len(caplog.records) > 0
        assert "EXTERNAL_COMPARE_DENIAL" in caplog.records[0].message
        assert get_counter("external.compare.audit.denials", labels={"reason": "insufficient_permissions"}) >= 1
    
    def test_acceptance_audit_timeout(self, caplog):
        """
        Acceptance: Audit log entry for timeouts.
        """
        with caplog.at_level(logging.WARNING, logger="rbac.audit"):
            audit_external_compare_timeout(
                url="https://example.com",
                timeout_ms=2000,
                user_id="test_user"
            )
        
        assert len(caplog.records) > 0
        assert "EXTERNAL_COMPARE_TIMEOUT" in caplog.records[0].message
        assert get_counter("external.compare.audit.timeouts", labels={"domain": "example.com"}) >= 1
