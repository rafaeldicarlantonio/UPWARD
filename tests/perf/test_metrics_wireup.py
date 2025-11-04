#!/usr/bin/env python3
"""
Unit tests for performance metrics instrumentation.

Tests:
1. Histogram recording and percentile calculation
2. Performance metrics (retrieval, graph_expand, packing, reviewer)
3. Counter increments (timeouts, fallbacks, circuit opens)
4. Error rate calculation
5. Metrics endpoint exposure
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

# Add workspace to path
sys.path.insert(0, '/workspace')

# Mock external dependencies for endpoint tests
mock_fastapi = Mock()
mock_fastapi.APIRouter = Mock()
mock_fastapi.Request = Mock()
mock_fastapi.HTTPException = Mock()
mock_fastapi.status = Mock()
sys.modules['fastapi'] = mock_fastapi
sys.modules['fastapi.routing'] = Mock()

mock_starlette = Mock()
mock_starlette.middleware = Mock()
mock_starlette.middleware.base = Mock()
mock_starlette.middleware.base.BaseHTTPMiddleware = Mock()
mock_starlette.types = Mock()
mock_starlette.types.ASGIApp = Mock()
sys.modules['starlette'] = mock_starlette
sys.modules['starlette.middleware'] = mock_starlette.middleware
sys.modules['starlette.middleware.base'] = mock_starlette.middleware.base
sys.modules['starlette.types'] = mock_starlette.types

sys.modules['supabase'] = Mock()
sys.modules['pinecone'] = Mock()
sys.modules['openai'] = Mock()

from core.metrics import (
    MetricsCollector,
    MetricHistogram,
    PerformanceMetrics,
    increment_counter,
    observe_histogram,
    get_counter,
    get_histogram_stats,
    reset_metrics,
)


class TestHistogramPercentiles(unittest.TestCase):
    """Test histogram with percentile calculation."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_percentile_calculation(self):
        """Test percentile calculation from histogram values."""
        collector = MetricsCollector()
        
        # Record values: 1, 2, 3, ..., 100
        for i in range(1, 101):
            collector.observe_histogram("test_metric", float(i))
        
        stats = collector.get_histogram_stats("test_metric")
        
        # Verify percentiles
        self.assertEqual(stats["count"], 100)
        self.assertAlmostEqual(stats["p50"], 50.5, delta=1.0)  # Median
        self.assertAlmostEqual(stats["p95"], 95.5, delta=1.0)  # 95th percentile
        self.assertAlmostEqual(stats["p99"], 99.1, delta=1.0)  # 99th percentile
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 100.0)
    
    def test_empty_histogram_percentiles(self):
        """Test percentiles with no data."""
        collector = MetricsCollector()
        stats = collector.get_histogram_stats("empty_metric")
        
        self.assertEqual(stats["count"], 0)
        self.assertEqual(stats["p50"], 0.0)
        self.assertEqual(stats["p95"], 0.0)
        self.assertEqual(stats["p99"], 0.0)
    
    def test_single_value_percentiles(self):
        """Test percentiles with single value."""
        collector = MetricsCollector()
        collector.observe_histogram("single_metric", 42.0)
        
        stats = collector.get_histogram_stats("single_metric")
        
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["p50"], 42.0)
        self.assertEqual(stats["p95"], 42.0)
        self.assertEqual(stats["min"], 42.0)
        self.assertEqual(stats["max"], 42.0)
    
    def test_histogram_value_limit(self):
        """Test histogram keeps only recent 10k values."""
        collector = MetricsCollector()
        
        # Record 11k values
        for i in range(11000):
            collector.observe_histogram("large_metric", float(i))
        
        # Check that only 10k values are kept
        key = collector._get_metric_key("large_metric")
        histogram = collector._histograms[key]
        
        self.assertLessEqual(len(histogram.values), 10000)
        self.assertEqual(histogram.count, 11000)  # Count should still be accurate


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metrics recording."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_record_retrieval(self):
        """Test retrieval metrics recording."""
        # Record successful retrieval
        PerformanceMetrics.record_retrieval(450.0, success=True, method="dual")
        
        # Verify histogram
        stats = get_histogram_stats("retrieval_ms", labels={"success": "true", "method": "dual"})
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["p50"], 450.0)
        
        # Verify counter
        count = get_counter("retrieval_total", labels={"success": "true", "method": "dual"})
        self.assertEqual(count, 1)
    
    def test_record_graph_expand(self):
        """Test graph expansion metrics recording."""
        PerformanceMetrics.record_graph_expand(150.0, entities_expanded=5)
        
        stats = get_histogram_stats("graph_expand_ms", labels={"entities": "5"})
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["p50"], 150.0)
        
        count = get_counter("graph_expand_total")
        self.assertEqual(count, 1)
    
    def test_record_packing(self):
        """Test packing metrics recording."""
        PerformanceMetrics.record_packing(200.0, items_packed=10)
        
        stats = get_histogram_stats("packing_ms", labels={"items": "10"})
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["p50"], 200.0)
    
    def test_record_reviewer(self):
        """Test reviewer metrics recording."""
        # Normal review
        PerformanceMetrics.record_reviewer(500.0, skipped=False)
        
        stats = get_histogram_stats("reviewer_ms", labels={"skipped": "false"})
        self.assertEqual(stats["count"], 1)
        
        # Skipped review
        PerformanceMetrics.record_reviewer(50.0, skipped=True, reason="timeout")
        
        skips = get_counter("reviewer_skips")
        self.assertEqual(skips, 1)


class TestCounterMetrics(unittest.TestCase):
    """Test counter metrics for failures and fallbacks."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_pinecone_timeouts(self):
        """Test Pinecone timeout counter."""
        PerformanceMetrics.record_pinecone_timeout("query")
        PerformanceMetrics.record_pinecone_timeout("query")
        PerformanceMetrics.record_pinecone_timeout("upsert")
        
        # Check base counter
        total_timeouts = get_counter("pinecone_timeouts")
        self.assertEqual(total_timeouts, 3)
        
        # Check labeled counters
        query_timeouts = get_counter("pinecone_timeouts_by_operation", labels={"operation": "query"})
        upsert_timeouts = get_counter("pinecone_timeouts_by_operation", labels={"operation": "upsert"})
        
        self.assertEqual(query_timeouts, 2)
        self.assertEqual(upsert_timeouts, 1)
    
    def test_pgvector_fallbacks(self):
        """Test pgvector fallback counter."""
        PerformanceMetrics.record_pgvector_fallback("timeout")
        PerformanceMetrics.record_pgvector_fallback("error")
        PerformanceMetrics.record_pgvector_fallback("timeout")
        
        # Check base counter
        total_fallbacks = get_counter("pgvector_fallbacks")
        self.assertEqual(total_fallbacks, 3)
        
        # Check labeled counters
        timeout_fallbacks = get_counter("pgvector_fallbacks_by_reason", labels={"reason": "timeout"})
        error_fallbacks = get_counter("pgvector_fallbacks_by_reason", labels={"reason": "error"})
        
        self.assertEqual(timeout_fallbacks, 2)
        self.assertEqual(error_fallbacks, 1)
    
    def test_circuit_opens(self):
        """Test circuit breaker open counter."""
        PerformanceMetrics.record_circuit_open("pinecone")
        PerformanceMetrics.record_circuit_open("pinecone")
        PerformanceMetrics.record_circuit_open("reviewer")
        
        # Check base counter
        total_opens = get_counter("circuit_opens")
        self.assertEqual(total_opens, 3)
        
        # Check labeled counters
        pinecone_opens = get_counter("circuit_opens_by_service", labels={"service": "pinecone"})
        reviewer_opens = get_counter("circuit_opens_by_service", labels={"service": "reviewer"})
        
        self.assertEqual(pinecone_opens, 2)
        self.assertEqual(reviewer_opens, 1)
    
    def test_reviewer_skips(self):
        """Test reviewer skip counter."""
        PerformanceMetrics.record_reviewer(10.0, skipped=True, reason="timeout")
        PerformanceMetrics.record_reviewer(15.0, skipped=True, reason="circuit_open")
        PerformanceMetrics.record_reviewer(20.0, skipped=True, reason="timeout")
        
        total_skips = get_counter("reviewer_skips")
        timeout_skips = get_counter("reviewer_skips_by_reason", labels={"reason": "timeout"})
        circuit_skips = get_counter("reviewer_skips_by_reason", labels={"reason": "circuit_open"})
        
        self.assertEqual(total_skips, 3)
        self.assertEqual(timeout_skips, 2)
        self.assertEqual(circuit_skips, 1)


class TestRateCalculations(unittest.TestCase):
    """Test rate calculation functions."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        # Record successes and failures
        for _ in range(8):
            increment_counter("retrieval_total", labels={"success": "true"})
        for _ in range(2):
            increment_counter("retrieval_total", labels={"success": "false"})
        
        error_rate = PerformanceMetrics.get_error_rate("retrieval")
        
        self.assertAlmostEqual(error_rate, 0.2, delta=0.01)  # 2/10 = 20%
    
    def test_error_rate_no_data(self):
        """Test error rate with no data."""
        error_rate = PerformanceMetrics.get_error_rate("retrieval")
        self.assertEqual(error_rate, 0.0)
    
    def test_fallback_rate_calculation(self):
        """Test fallback rate calculation."""
        # Record retrievals and fallbacks
        for _ in range(10):
            increment_counter("retrieval_total")
        for _ in range(3):
            increment_counter("pgvector_fallbacks")
        
        fallback_rate = PerformanceMetrics.get_fallback_rate()
        
        self.assertAlmostEqual(fallback_rate, 0.3, delta=0.01)  # 3/10 = 30%
    
    def test_fallback_rate_no_retrievals(self):
        """Test fallback rate with no retrievals."""
        fallback_rate = PerformanceMetrics.get_fallback_rate()
        self.assertEqual(fallback_rate, 0.0)


class TestMetricsWithLabels(unittest.TestCase):
    """Test metrics with different label combinations."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_histogram_with_different_labels(self):
        """Test histogram tracks different label combinations separately."""
        observe_histogram("retrieval_ms", 100.0, labels={"method": "dual"})
        observe_histogram("retrieval_ms", 200.0, labels={"method": "legacy"})
        observe_histogram("retrieval_ms", 150.0, labels={"method": "dual"})
        
        dual_stats = get_histogram_stats("retrieval_ms", labels={"method": "dual"})
        legacy_stats = get_histogram_stats("retrieval_ms", labels={"method": "legacy"})
        
        self.assertEqual(dual_stats["count"], 2)
        self.assertAlmostEqual(dual_stats["p50"], 125.0, delta=5.0)
        
        self.assertEqual(legacy_stats["count"], 1)
        self.assertEqual(legacy_stats["p50"], 200.0)
    
    def test_counter_with_different_labels(self):
        """Test counter tracks different label combinations separately."""
        increment_counter("errors", value=5, labels={"type": "timeout"})
        increment_counter("errors", value=3, labels={"type": "auth"})
        increment_counter("errors", value=2, labels={"type": "timeout"})
        
        timeout_errors = get_counter("errors", labels={"type": "timeout"})
        auth_errors = get_counter("errors", labels={"type": "auth"})
        
        self.assertEqual(timeout_errors, 7)
        self.assertEqual(auth_errors, 3)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_metrics_increment_in_tests(self):
        """Test: metrics increment in tests."""
        # Record various metrics
        PerformanceMetrics.record_retrieval(450.0, success=True)
        PerformanceMetrics.record_graph_expand(150.0, entities_expanded=5)
        PerformanceMetrics.record_packing(200.0, items_packed=10)
        PerformanceMetrics.record_reviewer(500.0, skipped=False)
        PerformanceMetrics.record_pinecone_timeout("query")
        PerformanceMetrics.record_pgvector_fallback("timeout")
        PerformanceMetrics.record_circuit_open("pinecone")
        
        # ? Verify all metrics incremented
        self.assertEqual(get_counter("retrieval_total", labels={"success": "true", "method": "dual"}), 1)
        self.assertEqual(get_counter("graph_expand_total"), 1)
        self.assertEqual(get_counter("packing_total"), 1)
        self.assertEqual(get_counter("reviewer_total", labels={"skipped": "false"}), 1)
        self.assertEqual(get_counter("pinecone_timeouts"), 1)
        self.assertEqual(get_counter("pgvector_fallbacks"), 1)
        self.assertEqual(get_counter("circuit_opens"), 1)
    
    def test_p95_computed_and_exposed(self):
        """Test: p95 computed and exposed."""
        # Record 100 values with known distribution
        for i in range(1, 101):
            observe_histogram("test_latency_ms", float(i))
        
        # ? Get stats and verify p95 is computed
        stats = get_histogram_stats("test_latency_ms")
        
        self.assertIn("p95", stats)
        self.assertIn("p50", stats)
        self.assertIn("p99", stats)
        
        # ? Verify p95 is approximately correct
        self.assertGreater(stats["p95"], 90.0)
        self.assertLess(stats["p95"], 100.0)
        
        # ? Verify p50 (median) is approximately 50
        self.assertGreater(stats["p50"], 45.0)
        self.assertLess(stats["p50"], 55.0)
    
    def test_performance_histograms_tracked(self):
        """Test: performance histograms are tracked."""
        # Record each type of performance metric
        PerformanceMetrics.record_retrieval(450.0)
        PerformanceMetrics.record_graph_expand(150.0)
        PerformanceMetrics.record_packing(200.0)
        PerformanceMetrics.record_reviewer(500.0)
        
        # ? Verify histograms exist and have data (with correct labels)
        retrieval_stats = get_histogram_stats("retrieval_ms", labels={"success": "true", "method": "dual"})
        graph_stats = get_histogram_stats("graph_expand_ms", labels={"entities": "0"})
        packing_stats = get_histogram_stats("packing_ms", labels={"items": "0"})
        reviewer_stats = get_histogram_stats("reviewer_ms", labels={"skipped": "false"})
        
        self.assertGreater(retrieval_stats["count"], 0)
        self.assertGreater(graph_stats["count"], 0)
        self.assertGreater(packing_stats["count"], 0)
        self.assertGreater(reviewer_stats["count"], 0)
        
        # ? Verify values are correct
        self.assertEqual(retrieval_stats["p50"], 450.0)
        self.assertEqual(graph_stats["p50"], 150.0)
        self.assertEqual(packing_stats["p50"], 200.0)
        self.assertEqual(reviewer_stats["p50"], 500.0)
    
    def test_counters_tracked(self):
        """Test: all required counters are tracked."""
        # Record each type of counter
        PerformanceMetrics.record_pinecone_timeout("query")
        PerformanceMetrics.record_pinecone_timeout("upsert")
        PerformanceMetrics.record_pgvector_fallback("timeout")
        PerformanceMetrics.record_pgvector_fallback("error")
        PerformanceMetrics.record_reviewer(10.0, skipped=True, reason="timeout")
        PerformanceMetrics.record_circuit_open("pinecone")
        PerformanceMetrics.record_circuit_open("reviewer")
        
        # ? Verify all counters tracked
        self.assertGreater(get_counter("pinecone_timeouts"), 0)
        self.assertGreater(get_counter("pgvector_fallbacks"), 0)
        self.assertGreater(get_counter("reviewer_skips"), 0)
        self.assertGreater(get_counter("circuit_opens"), 0)
        
        # ? Verify specific counts
        self.assertEqual(get_counter("pinecone_timeouts"), 2)
        self.assertEqual(get_counter("pgvector_fallbacks"), 2)
        self.assertEqual(get_counter("reviewer_skips"), 1)
        self.assertEqual(get_counter("circuit_opens"), 2)
    
    def test_rates_computed(self):
        """Test: error rate and fallback rate computed."""
        # Set up data for rate calculation
        for _ in range(7):
            increment_counter("retrieval_total", labels={"success": "true"})
        for _ in range(3):
            increment_counter("retrieval_total", labels={"success": "false"})
        
        for _ in range(10):
            increment_counter("retrieval_total")
        for _ in range(2):
            increment_counter("pgvector_fallbacks")
        
        # ? Compute rates
        error_rate = PerformanceMetrics.get_error_rate("retrieval")
        fallback_rate = PerformanceMetrics.get_fallback_rate()
        
        # ? Verify rates are computed correctly
        self.assertAlmostEqual(error_rate, 0.3, delta=0.01)  # 3/10 = 30%
        self.assertAlmostEqual(fallback_rate, 0.2, delta=0.01)  # 2/10 = 20%


class TestMetricsEndpoint(unittest.TestCase):
    """Test metrics exposure via get_all_metrics."""
    
    def setUp(self):
        """Reset metrics before each test."""
        reset_metrics()
        from core.metrics import get_all_metrics
        self.get_all_metrics = get_all_metrics
    
    def test_all_metrics_structure(self):
        """Test get_all_metrics returns expected structure."""
        # Record some metrics
        PerformanceMetrics.record_retrieval(450.0)
        PerformanceMetrics.record_graph_expand(150.0)
        PerformanceMetrics.record_packing(200.0)
        PerformanceMetrics.record_reviewer(500.0)
        
        # Get all metrics
        all_metrics = self.get_all_metrics()
        
        # ✅ Verify structure
        self.assertIn("timestamp", all_metrics)
        self.assertIn("uptime_seconds", all_metrics)
        self.assertIn("counters", all_metrics)
        self.assertIn("histograms", all_metrics)
        
        # ✅ Verify histograms exist
        histograms = all_metrics["histograms"]
        self.assertIn("retrieval_ms", histograms)
        self.assertIn("graph_expand_ms", histograms)
        self.assertIn("packing_ms", histograms)
        self.assertIn("reviewer_ms", histograms)
        
        # ✅ Verify each histogram has stats with p50/p95
        for hist_name in ["retrieval_ms", "graph_expand_ms", "packing_ms", "reviewer_ms"]:
            hist_data = histograms[hist_name]
            self.assertIsInstance(hist_data, list)
            self.assertGreater(len(hist_data), 0)
            stats = hist_data[0]["stats"]
            self.assertIn("p50", stats)
            self.assertIn("p95", stats)
            self.assertIn("count", stats)
    
    def test_performance_histograms_exposed(self):
        """Test performance histograms are exposed with percentiles."""
        # Record diverse metrics
        for i in range(10):
            PerformanceMetrics.record_retrieval(400.0 + i * 10)
            PerformanceMetrics.record_graph_expand(100.0 + i * 5)
        
        # Get specific histogram stats
        retrieval_stats = get_histogram_stats("retrieval_ms", labels={"success": "true", "method": "dual"})
        graph_stats = get_histogram_stats("graph_expand_ms", labels={"entities": "0"})
        
        # ✅ Verify p95 is exposed
        self.assertIn("p95", retrieval_stats)
        self.assertIn("p95", graph_stats)
        
        # ✅ Verify p95 values are reasonable
        self.assertGreater(retrieval_stats["p95"], retrieval_stats["p50"])
        self.assertGreater(graph_stats["p95"], graph_stats["p50"])
        
        # ✅ Verify counts
        self.assertEqual(retrieval_stats["count"], 10)
        self.assertEqual(graph_stats["count"], 10)


if __name__ == "__main__":
    unittest.main()
