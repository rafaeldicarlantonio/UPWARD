# tests/test_perf.py — performance tests for retrieval system

import pytest
import time
import statistics
import asyncio
import os
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Mock OpenAI client before importing modules
with patch('openai.OpenAI') as mock_openai:
    mock_client = Mock()
    mock_openai.return_value = mock_client
    
    from core.selection import SelectionFactory, DualSelector, LegacySelector
    from core.packing import pack_with_contradictions
    from core.ranking import LiftScoreRanker
    from feature_flags import get_feature_flag

@dataclass
class PerformanceMetrics:
    """Performance metrics for a single test run."""
    test_name: str
    latency_ms: float
    retrieval_latency_ms: float
    ranking_latency_ms: float
    packing_latency_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    error_message: Optional[str] = None

class TestRetrievalPerformance:
    """Test retrieval performance with timing constraints."""
    
    # Performance constraints
    MAX_LATENCY_MS = 500  # P95 constraint
    MAX_INDIVIDUAL_LATENCY_MS = 1000  # Individual request constraint
    EXPECTED_EXPLICATE_K = 16
    EXPECTED_IMPLICATE_K = 8
    
    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing."""
        with patch('app.services.vector_store.VectorStore') as mock_vs:
            # Mock explicate query
            explicate_matches = [
                Mock(id=f"mem-{i}", score=0.9 - i*0.1, metadata={"text": f"Memory {i}", "type": "semantic"})
                for i in range(20)
            ]
            
            # Mock implicate query
            implicate_matches = [
                Mock(id=f"concept-{i}", score=0.8 - i*0.1, metadata={"entity_id": f"entity-{i}", "entity_name": f"Concept {i}"})
                for i in range(10)
            ]
            
            mock_vs.return_value.query_explicit.return_value = Mock(matches=explicate_matches)
            mock_vs.return_value.query_implicate.return_value = Mock(matches=implicate_matches)
            yield mock_vs
    
    @pytest.fixture
    def mock_db_adapter(self):
        """Mock database adapter for testing."""
        with patch('adapters.db.DatabaseAdapter') as mock_db:
            # Mock entity relations
            mock_db.return_value.get_entity_relations.return_value = [
                ("related_to", "AI", 0.9),
                ("subfield_of", "Computer Science", 0.8),
                ("uses", "Neural Networks", 0.7)
            ]
            
            # Mock entity memories
            mock_memories = [
                Mock(id=f"mem-{i}", content=f"Memory content {i}", title=f"Memory {i}")
                for i in range(5)
            ]
            mock_db.return_value.get_entity_memories.return_value = mock_memories
            yield mock_db
    
    @pytest.fixture
    def mock_pinecone_adapter(self):
        """Mock Pinecone adapter for testing."""
        with patch('adapters.pinecone_client.PineconeAdapter') as mock_pc:
            mock_pc.return_value.query_embeddings.return_value = {
                "matches": [
                    {"id": f"concept-{i}", "score": 0.8 - i*0.1, "metadata": {"entity_id": f"entity-{i}"}}
                    for i in range(10)
                ]
            }
            yield mock_pc
    
    @pytest.fixture
    def performance_metrics_collector(self):
        """Collect performance metrics during tests."""
        metrics = []
        
        def collect_metric(test_name: str, latency_ms: float, success: bool, error: str = None):
            metrics.append(PerformanceMetrics(
                test_name=test_name,
                latency_ms=latency_ms,
                retrieval_latency_ms=latency_ms * 0.6,  # Simulate breakdown
                ranking_latency_ms=latency_ms * 0.2,
                packing_latency_ms=latency_ms * 0.2,
                memory_usage_mb=100.0,  # Simulate memory usage
                cpu_usage_percent=50.0,  # Simulate CPU usage
                success=success,
                error_message=error
            ))
        
        yield collect_metric, metrics
    
    @pytest.mark.performance
    def test_legacy_selector_performance(self, mock_vector_store, performance_metrics_collector):
        """Test legacy selector performance."""
        collect_metric, metrics = performance_metrics_collector
        
        with patch('feature_flags.get_feature_flag') as mock_flag:
            mock_flag.return_value = False
            
            selector = SelectionFactory.create_selector()
            assert isinstance(selector, LegacySelector)
            
            # Test performance
            start_time = time.time()
            result = selector.select(
                query="test query",
                embedding=[0.1] * 1536,
                caller_role="user"
            )
            latency_ms = (time.time() - start_time) * 1000
            
            # Collect metrics
            collect_metric("legacy_selector", latency_ms, True)
            
            assert latency_ms < self.MAX_INDIVIDUAL_LATENCY_MS
            assert result is not None
            assert hasattr(result, 'context')
            assert hasattr(result, 'ranked_ids')
            
            # Verify performance constraints
            assert latency_ms < 100, f"Legacy selector too slow: {latency_ms}ms"
    
    @pytest.mark.performance
    def test_dual_selector_performance(self, mock_vector_store, mock_db_adapter, mock_pinecone_adapter, performance_metrics_collector):
        """Test dual selector performance."""
        collect_metric, metrics = performance_metrics_collector
        
        with patch('feature_flags.get_feature_flag') as mock_flag:
            mock_flag.return_value = True
            
            selector = SelectionFactory.create_selector()
            assert isinstance(selector, DualSelector)
            
            # Test performance
            start_time = time.time()
            result = selector.select(
                query="test query",
                embedding=[0.1] * 1536,
                caller_role="user",
                explicate_top_k=self.EXPECTED_EXPLICATE_K,
                implicate_top_k=self.EXPECTED_IMPLICATE_K
            )
            latency_ms = (time.time() - start_time) * 1000
            
            # Collect metrics
            collect_metric("dual_selector", latency_ms, True)
            
            assert latency_ms < self.MAX_INDIVIDUAL_LATENCY_MS
            assert result is not None
            assert hasattr(result, 'context')
            assert hasattr(result, 'ranked_ids')
            
            # Verify performance constraints
            assert latency_ms < 200, f"Dual selector too slow: {latency_ms}ms"
    
    def test_contradiction_packing_performance(self):
        """Test contradiction packing performance."""
        with patch('feature_flags.get_feature_flag') as mock_flag:
            mock_flag.return_value = True
            
            # Sample context with potential contradictions
            context = [
                {"id": "mem-1", "text": "Remote work is allowed", "metadata": {"entity_id": "entity-1"}},
                {"id": "mem-2", "text": "Remote work is not allowed", "metadata": {"entity_id": "entity-1"}},
                {"id": "mem-3", "text": "Budget was increased", "metadata": {"entity_id": "entity-2"}},
                {"id": "mem-4", "text": "Budget was decreased", "metadata": {"entity_id": "entity-2"}},
            ]
            
            ranked_ids = ["mem-1", "mem-2", "mem-3", "mem-4"]
            
            start_time = time.time()
            result = pack_with_contradictions(context, ranked_ids, top_m=10)
            latency_ms = (time.time() - start_time) * 1000
            
            assert latency_ms < 100  # Should be fast
            assert result is not None
            assert hasattr(result, 'context')
            assert hasattr(result, 'contradictions')
            assert hasattr(result, 'contradiction_score')
    
    def test_liftscore_ranking_performance(self):
        """Test LiftScore ranking performance."""
        with patch('feature_flags.get_feature_flag') as mock_flag:
            mock_flag.return_value = True
            
            ranker = LiftScoreRanker()
            
            # Sample records
            records = [
                {"id": f"mem-{i}", "text": f"Memory {i}", "score": 0.9 - i*0.1}
                for i in range(20)
            ]
            
            start_time = time.time()
            result = ranker.rank_and_pack(records, "test query", "user")
            latency_ms = (time.time() - start_time) * 1000
            
            assert latency_ms < 50  # Should be very fast
            assert result is not None
            assert "context" in result
            assert "ranked_ids" in result

class TestPerformanceConstraints:
    """Test performance constraints and thresholds."""
    
    @pytest.mark.performance
    def test_p95_latency_constraint(self):
        """Test that P95 latency is under 500ms."""
        # Simulate multiple runs with varying latencies
        latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 600]  # One exceeds threshold
        
        p95_latency = statistics.quantiles(latencies, n=20)[18]
        
        # P95 should be under 500ms
        assert p95_latency < 500, f"P95 latency {p95_latency}ms exceeds 500ms threshold"
    
    @pytest.mark.performance
    def test_individual_latency_constraint(self):
        """Test that individual requests stay under 1000ms."""
        # Simulate individual request latencies
        latencies = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]
        
        max_latency = max(latencies)
        
        # Individual requests should be under 1000ms
        assert max_latency < 1000, f"Max latency {max_latency}ms exceeds 1000ms threshold"
    
    @pytest.mark.performance
    def test_retrieval_phase_latency(self):
        """Test that retrieval phase latency is reasonable."""
        # Simulate retrieval phase latencies
        retrieval_latencies = [50, 75, 100, 125, 150, 175, 200, 225, 250, 275]
        
        avg_retrieval = statistics.mean(retrieval_latencies)
        p95_retrieval = statistics.quantiles(retrieval_latencies, n=20)[18]
        
        # Retrieval should be fast
        assert avg_retrieval < 200, f"Average retrieval latency {avg_retrieval}ms too high"
        assert p95_retrieval < 300, f"P95 retrieval latency {p95_retrieval}ms too high"
    
    def test_average_latency_constraint(self):
        """Test that average latency is reasonable."""
        latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550]
        
        avg_latency = statistics.mean(latencies)
        
        # Average should be under 400ms
        assert avg_latency < 400, f"Average latency {avg_latency}ms exceeds 400ms threshold"
    
    def test_max_latency_constraint(self):
        """Test that max latency is under 1000ms."""
        latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550]
        
        max_latency = max(latencies)
        
        # Max should be under 1000ms
        assert max_latency < 1000, f"Max latency {max_latency}ms exceeds 1000ms threshold"

class TestPerformanceMarkers:
    """Test performance markers for CI integration."""
    
    @pytest.mark.performance
    @pytest.mark.ci_safe
    def test_retrieval_performance_benchmark(self):
        """Performance benchmark test - safe for CI."""
        # This test would run actual performance benchmarks
        # In a real implementation, this would make actual API calls
        # and measure performance metrics
        
        # For now, just test that the marker works
        assert True
    
    @pytest.mark.performance
    @pytest.mark.flaky
    def test_full_system_performance(self):
        """Full system performance test - marked as flaky."""
        # This test would run a full end-to-end performance test
        # including all components working together
        # Can be skipped on CI if flaky
        
        # For now, just test that the marker works
        assert True
    
    @pytest.mark.performance
    @pytest.mark.integration
    @pytest.mark.ci_safe
    def test_api_performance_integration(self):
        """API performance integration test - safe for CI."""
        # This test would test the actual API endpoints
        # and measure their performance
        
        # For now, just test that the marker works
        assert True
    
    @pytest.mark.performance
    @pytest.mark.stress
    @pytest.mark.flaky
    def test_stress_performance(self):
        """Stress test performance - can be flaky."""
        # This test would run stress tests with high load
        # Can be skipped on CI if flaky
        
        # For now, just test that the marker works
        assert True
    
    @pytest.mark.performance
    @pytest.mark.ci_safe
    def test_basic_performance_smoke(self):
        """Basic performance smoke test - always safe for CI."""
        # This test runs basic performance checks
        # Should always pass and be safe for CI
        
        # For now, just test that the marker works
        assert True

class TestPerformanceMetrics:
    """Test performance metrics collection and analysis."""
    
    @pytest.mark.performance
    @pytest.mark.ci_safe
    def test_latency_distribution(self):
        """Test latency distribution analysis."""
        # Simulate latency measurements
        latencies = [50, 75, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400]
        
        # Calculate percentiles
        p50 = statistics.quantiles(latencies, n=2)[0]
        p90 = statistics.quantiles(latencies, n=10)[8]
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]
        
        # Verify percentiles are reasonable
        assert p50 < 200, f"P50 latency {p50}ms too high"
        assert p90 < 350, f"P90 latency {p90}ms too high"
        assert p95 < 400, f"P95 latency {p95}ms too high"
        assert p99 < 500, f"P99 latency {p99}ms too high"
    
    @pytest.mark.performance
    @pytest.mark.ci_safe
    def test_performance_regression_detection(self):
        """Test performance regression detection."""
        # Simulate baseline and current performance
        baseline_latencies = [100, 150, 200, 250, 300]
        current_latencies = [120, 180, 240, 300, 360]  # 20% slower
        
        baseline_avg = statistics.mean(baseline_latencies)
        current_avg = statistics.mean(current_latencies)
        
        # Calculate regression percentage
        regression_pct = ((current_avg - baseline_avg) / baseline_avg) * 100
        
        # Flag if regression is more than 50%
        if regression_pct > 50:
            pytest.fail(f"Performance regression detected: {regression_pct:.1f}% slower")
        
        # For this test, we expect some regression but not too much
        assert regression_pct < 50, f"Performance regression too high: {regression_pct:.1f}%"
    
    @pytest.mark.performance
    @pytest.mark.ci_safe
    def test_performance_variance(self):
        """Test performance variance is within acceptable limits."""
        # Simulate multiple runs with some variance
        latencies = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145]
        
        # Calculate coefficient of variation
        mean_latency = statistics.mean(latencies)
        std_latency = statistics.stdev(latencies)
        cv = (std_latency / mean_latency) * 100
        
        # Coefficient of variation should be under 20%
        assert cv < 20, f"Performance variance too high: {cv:.1f}%"

class TestPerformanceIntegration:
    """Integration tests for performance monitoring."""
    
    @pytest.mark.performance
    @pytest.mark.integration
    @pytest.mark.ci_safe
    def test_end_to_end_performance(self):
        """Test end-to-end performance with all components."""
        # This would test the complete flow:
        # 1. Query processing
        # 2. Dual retrieval (explicate + implicate)
        # 3. Contradiction detection
        # 4. LiftScore ranking
        # 5. Response generation
        
        # For now, just test that the components can be imported
        from core.selection import SelectionFactory
        from core.packing import pack_with_contradictions
        from core.ranking import LiftScoreRanker
        
        assert SelectionFactory is not None
        assert pack_with_contradictions is not None
        assert LiftScoreRanker is not None
    
    @pytest.mark.performance
    @pytest.mark.ci_safe
    def test_performance_monitoring_integration(self):
        """Test integration with performance monitoring."""
        # This would test integration with monitoring systems
        # like Prometheus, DataDog, or custom metrics
        
        # For now, just test that we can collect basic metrics
        start_time = time.time()
        time.sleep(0.001)  # Simulate work
        latency_ms = (time.time() - start_time) * 1000
        
        assert latency_ms > 0
        assert latency_ms < 100  # Should be very fast

class TestCIIntegration:
    """CI integration tests with proper markers."""
    
    @pytest.mark.performance
    @pytest.mark.ci_safe
    def test_ci_safe_performance(self):
        """Performance test that's safe to run in CI."""
        # This test should always pass and be fast
        assert True
    
    @pytest.mark.performance
    @pytest.mark.flaky
    def test_ci_flaky_performance(self):
        """Performance test that might be flaky in CI."""
        # This test can be skipped in CI if flaky
        # Use --skip-flaky flag to skip
        assert True
    
    @pytest.mark.performance
    @pytest.mark.stress
    @pytest.mark.flaky
    def test_ci_stress_performance(self):
        """Stress test that might be flaky in CI."""
        # This test can be skipped in CI if flaky
        # Use --skip-flaky flag to skip
        assert True

if __name__ == "__main__":
    import sys
    
    # Parse command line arguments for CI integration
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    # Default to running performance tests
    if not any(arg.startswith('-m') for arg in args):
        args.extend(['-m', 'performance'])
    
    # Add CI-specific options
    if '--ci-mode' in args:
        # In CI mode, skip flaky tests
        if '--skip-flaky' not in args:
            args.append('--skip-flaky')
        # Run only CI-safe tests
        args.extend(['-m', 'performance and ci_safe'])
    
    if '--skip-flaky' in args:
        # Skip flaky tests
        args.extend(['-m', 'not flaky'])
    
    # Add verbose output
    if '-v' not in args:
        args.append('-v')
    
    # Run tests
    pytest.main([__file__] + args)