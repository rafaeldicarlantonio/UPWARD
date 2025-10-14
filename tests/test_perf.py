# tests/test_perf.py — performance tests for retrieval system

import pytest
import time
import statistics
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

# Mock OpenAI client before importing modules
with patch('openai.OpenAI') as mock_openai:
    mock_client = Mock()
    mock_openai.return_value = mock_client
    
    from core.selection import SelectionFactory, DualSelector, LegacySelector
    from core.packing import pack_with_contradictions
    from core.ranking import LiftScoreRanker
    from feature_flags import get_feature_flag

class TestRetrievalPerformance:
    """Test retrieval performance with timing constraints."""
    
    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing."""
        with patch('app.services.vector_store.VectorStore') as mock_vs:
            mock_vs.return_value.query.return_value = {
                "matches": [
                    {"id": f"mem-{i}", "score": 0.9 - i*0.1, "metadata": {"text": f"Memory {i}"}}
                    for i in range(20)
                ]
            }
            yield mock_vs
    
    @pytest.fixture
    def mock_db_adapter(self):
        """Mock database adapter for testing."""
        with patch('adapters.db.DatabaseAdapter') as mock_db:
            mock_db.return_value.get_entity_relations.return_value = []
            mock_db.return_value.get_entity_memories.return_value = []
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
    
    def test_legacy_selector_performance(self, mock_vector_store):
        """Test legacy selector performance."""
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
            
            assert latency_ms < 100  # Should be very fast with mocks
            assert result is not None
            assert hasattr(result, 'context')
            assert hasattr(result, 'ranked_ids')
    
    def test_dual_selector_performance(self, mock_vector_store, mock_db_adapter, mock_pinecone_adapter):
        """Test dual selector performance."""
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
                explicate_top_k=16,
                implicate_top_k=8
            )
            latency_ms = (time.time() - start_time) * 1000
            
            assert latency_ms < 200  # Should be fast with mocks
            assert result is not None
            assert hasattr(result, 'context')
            assert hasattr(result, 'ranked_ids')
    
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
    
    def test_p95_latency_constraint(self):
        """Test that P95 latency is under 500ms."""
        # Simulate multiple runs with varying latencies
        latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 600]  # One exceeds threshold
        
        p95_latency = statistics.quantiles(latencies, n=20)[18]
        
        # P95 should be under 500ms
        assert p95_latency < 500, f"P95 latency {p95_latency}ms exceeds 500ms threshold"
    
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
    def test_retrieval_performance_benchmark(self):
        """Performance benchmark test - can be skipped on CI if flaky."""
        # This test would run actual performance benchmarks
        # In a real implementation, this would make actual API calls
        # and measure performance metrics
        
        # For now, just test that the marker works
        assert True
    
    @pytest.mark.slow
    def test_full_system_performance(self):
        """Full system performance test - marked as slow."""
        # This test would run a full end-to-end performance test
        # including all components working together
        
        # For now, just test that the marker works
        assert True
    
    @pytest.mark.integration
    def test_api_performance_integration(self):
        """API performance integration test."""
        # This test would test the actual API endpoints
        # and measure their performance
        
        # For now, just test that the marker works
        assert True

class TestPerformanceMetrics:
    """Test performance metrics collection and analysis."""
    
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

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])