#!/usr/bin/env python3
"""Tests for ingest and refresh worker metrics instrumentation."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from core.metrics import (
    IngestMetrics,
    ImplicateRefreshMetrics,
    get_counter,
    get_histogram_stats,
    get_all_metrics,
    reset_metrics,
)


class TestIngestMetrics:
    """Tests for IngestMetrics instrumentation."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_record_chunk_analyzed_increments_counter(self):
        """Test that recording chunk analysis increments the counter."""
        IngestMetrics.record_chunk_analyzed(
            verbs_count=5,
            frames_count=3,
            concepts_count=2,
            contradictions_count=0,
            duration_ms=25.5,
            success=True
        )
        
        # Check counter was incremented
        count = get_counter("ingest.analysis.chunks_total", labels={"success": "True"})
        assert count == 1
        
        # Check another one
        IngestMetrics.record_chunk_analyzed(
            verbs_count=3,
            frames_count=2,
            concepts_count=1,
            contradictions_count=1,
            duration_ms=30.0,
            success=True
        )
        
        count = get_counter("ingest.analysis.chunks_total", labels={"success": "True"})
        assert count == 2
    
    def test_record_chunk_analyzed_records_histograms(self):
        """Test that chunk analysis records histogram values."""
        IngestMetrics.record_chunk_analyzed(
            verbs_count=10,
            frames_count=5,
            concepts_count=3,
            contradictions_count=2,
            duration_ms=45.0,
            success=True
        )
        
        # Check histograms
        verbs_stats = get_histogram_stats("ingest.analysis.verbs_per_chunk")
        assert verbs_stats["count"] == 1
        assert verbs_stats["sum"] == 10
        assert verbs_stats["avg"] == 10.0
        
        frames_stats = get_histogram_stats("ingest.analysis.frames_per_chunk")
        assert frames_stats["count"] == 1
        assert frames_stats["avg"] == 5.0
        
        concepts_stats = get_histogram_stats("ingest.analysis.concepts_suggested")
        assert concepts_stats["count"] == 1
        assert concepts_stats["avg"] == 3.0
        
        contradictions_stats = get_histogram_stats("ingest.analysis.contradictions_found")
        assert contradictions_stats["count"] == 1
        assert contradictions_stats["avg"] == 2.0
    
    def test_record_timeout_increments_counter(self):
        """Test that recording timeouts increments the counter."""
        IngestMetrics.record_timeout()
        IngestMetrics.record_timeout()
        IngestMetrics.record_timeout()
        
        count = get_counter("ingest.analysis.timeout_count")
        assert count == 3
    
    def test_record_analysis_error_increments_counter(self):
        """Test that recording errors increments the counter."""
        IngestMetrics.record_analysis_error("ValueError")
        IngestMetrics.record_analysis_error("ValueError")
        IngestMetrics.record_analysis_error("RuntimeError")
        
        value_errors = get_counter("ingest.analysis.errors_total", labels={"error_type": "ValueError"})
        runtime_errors = get_counter("ingest.analysis.errors_total", labels={"error_type": "RuntimeError"})
        
        assert value_errors == 2
        assert runtime_errors == 1
    
    def test_record_entities_created_records_histograms(self):
        """Test that entity creation records histogram values."""
        IngestMetrics.record_entities_created(
            concepts_count=5,
            frames_count=3,
            edges_count=8
        )
        
        concepts_stats = get_histogram_stats("ingest.commit.concepts_created")
        assert concepts_stats["count"] == 1
        assert concepts_stats["avg"] == 5.0
        
        frames_stats = get_histogram_stats("ingest.commit.frames_created")
        assert frames_stats["avg"] == 3.0
        
        edges_stats = get_histogram_stats("ingest.commit.edges_created")
        assert edges_stats["avg"] == 8.0
        
        # Check commit counter
        commit_count = get_counter("ingest.commit.total")
        assert commit_count == 1
    
    def test_record_commit_errors_increments_counter(self):
        """Test that commit errors are recorded."""
        IngestMetrics.record_commit_errors(3)
        
        error_count = get_counter("ingest.commit.errors_total")
        assert error_count == 3


class TestImplicateRefreshMetrics:
    """Tests for ImplicateRefreshMetrics instrumentation."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_record_job_enqueued_increments_counter(self):
        """Test that enqueueing jobs increments the counter."""
        ImplicateRefreshMetrics.record_job_enqueued(5)
        ImplicateRefreshMetrics.record_job_enqueued(3)
        
        count = get_counter("implicate_refresh.enqueued")
        assert count == 2
        
        # Check histogram
        stats = get_histogram_stats("implicate_refresh.entity_ids_per_job")
        assert stats["count"] == 2
        assert stats["sum"] == 8.0
        assert stats["avg"] == 4.0
    
    def test_record_job_processed_increments_counter(self):
        """Test that processing jobs increments the counter."""
        ImplicateRefreshMetrics.record_job_processed(
            entity_ids_count=10,
            processed_count=10,
            upserted_count=10,
            duration_s=2.5,
            success=True
        )
        
        count = get_counter("implicate_refresh.processed", labels={"success": "True"})
        assert count == 1
        
        # Check histograms
        requested_stats = get_histogram_stats("implicate_refresh.entities_requested")
        assert requested_stats["avg"] == 10.0
        
        processed_stats = get_histogram_stats("implicate_refresh.entities_processed")
        assert processed_stats["avg"] == 10.0
        
        upserted_stats = get_histogram_stats("implicate_refresh.entities_upserted")
        assert upserted_stats["avg"] == 10.0
        
        duration_stats = get_histogram_stats("implicate_refresh.job_duration_seconds", labels={"success": "True"})
        assert duration_stats["avg"] == 2.5
    
    def test_record_job_failed_increments_counter(self):
        """Test that job failures are recorded."""
        ImplicateRefreshMetrics.record_job_failed("ConnectionError", retry_count=1)
        ImplicateRefreshMetrics.record_job_failed("TimeoutError", retry_count=2)
        
        connection_errors = get_counter("implicate_refresh.failed", labels={"error_type": "ConnectionError"})
        timeout_errors = get_counter("implicate_refresh.failed", labels={"error_type": "TimeoutError"})
        
        assert connection_errors == 1
        assert timeout_errors == 1
        
        # Check retry count histogram
        retry_stats = get_histogram_stats("implicate_refresh.retry_count")
        assert retry_stats["count"] == 2
        assert retry_stats["sum"] == 3.0
    
    def test_record_worker_iteration_increments_counter(self):
        """Test that worker iterations are recorded."""
        ImplicateRefreshMetrics.record_worker_iteration(jobs_processed=5, duration_s=10.5)
        ImplicateRefreshMetrics.record_worker_iteration(jobs_processed=3, duration_s=7.2)
        
        count = get_counter("implicate_refresh.worker_iterations")
        assert count == 2
        
        # Check histograms
        jobs_stats = get_histogram_stats("implicate_refresh.jobs_per_iteration")
        assert jobs_stats["count"] == 2
        assert jobs_stats["sum"] == 8.0
        
        duration_stats = get_histogram_stats("implicate_refresh.iteration_duration_seconds")
        assert duration_stats["count"] == 2
        assert duration_stats["sum"] == 17.7
    
    def test_record_deduplication_increments_counter(self):
        """Test that deduplication is recorded."""
        ImplicateRefreshMetrics.record_deduplication(original_count=10, deduplicated_count=7)
        
        duplicates_removed = get_counter("implicate_refresh.duplicates_removed")
        assert duplicates_removed == 3
        
        # Check deduplication ratio
        ratio_stats = get_histogram_stats("implicate_refresh.deduplication_ratio")
        assert ratio_stats["count"] == 1
        assert abs(ratio_stats["avg"] - 0.3) < 0.01  # 3/10 = 0.3


class TestMetricsIntegration:
    """Integration tests for metrics with actual code paths."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.commit_analysis")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    def test_ingest_with_analysis_records_metrics(
        self,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_commit,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test that batch ingest with analysis records metrics."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        from ingest.pipeline import AnalysisResult
        from ingest.commit import CommitResult
        from nlp.verbs import PredicateFrame
        from nlp.frames import EventFrame
        
        # Setup mocks
        mock_get_flag.return_value = True
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 100,
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert response
        mock_upsert.return_value = {
            "upserted": [{"idx": 0, "memory_id": "memory-1"}],
            "updated": [],
            "skipped": [],
        }
        
        # Mock analysis with actual counts
        mock_analysis = AnalysisResult(
            predicates=[
                PredicateFrame(
                    verb_lemma="support",
                    subject_entity="network",
                    object_entity="concept",
                    modifiers=[],
                    polarity="positive",
                )
            ],
            frames=[
                EventFrame(
                    frame_id="frame-1",
                    type="claim",
                    roles={},
                )
            ],
            concepts=[
                {"name": "Neural Network", "rationale": "test"},
                {"name": "Deep Learning", "rationale": "test"},
            ],
            contradictions=[],
        )
        mock_analyze.return_value = mock_analysis
        
        # Mock commit
        mock_commit_result = CommitResult(
            concept_entity_ids=["concept-1", "concept-2"],
            frame_entity_ids=["frame-1"],
            edge_ids=["edge-1", "edge-2"],
        )
        mock_commit.return_value = mock_commit_result
        
        # Create request
        request = IngestBatchRequest(
            items=[IngestItem(text="Test text", type="semantic")]
        )
        
        # Reset metrics
        reset_metrics()
        
        # Call endpoint
        response = ingest_batch_ingest_batch_post(request)
        
        # Verify metrics were recorded
        chunks_analyzed = get_counter("ingest.analysis.chunks_total", labels={"success": "True"})
        assert chunks_analyzed == 1
        
        # Check histograms
        verbs_stats = get_histogram_stats("ingest.analysis.verbs_per_chunk")
        assert verbs_stats["count"] == 1
        assert verbs_stats["avg"] == 1.0
        
        frames_stats = get_histogram_stats("ingest.analysis.frames_per_chunk")
        assert frames_stats["avg"] == 1.0
        
        concepts_stats = get_histogram_stats("ingest.analysis.concepts_suggested")
        assert concepts_stats["avg"] == 2.0
        
        contradictions_stats = get_histogram_stats("ingest.analysis.contradictions_found")
        assert contradictions_stats["avg"] == 0.0
        
        # Check commit metrics
        commit_count = get_counter("ingest.commit.total")
        assert commit_count == 1
        
        concepts_created_stats = get_histogram_stats("ingest.commit.concepts_created")
        assert concepts_created_stats["avg"] == 2.0
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    @patch("router.ingest.time")
    def test_ingest_timeout_records_metric(
        self,
        mock_time_module,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test that timeouts are recorded in metrics."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        from ingest.pipeline import AnalysisResult
        
        # Setup mocks
        mock_get_flag.return_value = True
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 50,  # 50ms timeout
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert
        mock_upsert.return_value = {
            "upserted": [{"idx": 0, "memory_id": "memory-1"}],
            "updated": [],
            "skipped": [],
        }
        
        # Simulate timeout: 100ms elapsed
        mock_time_module.perf_counter.side_effect = [0.0, 0.100]
        
        # Mock analysis
        mock_analyze.return_value = AnalysisResult(
            predicates=[], frames=[], concepts=[], contradictions=[]
        )
        
        # Reset metrics
        reset_metrics()
        
        # Create request
        request = IngestBatchRequest(
            items=[IngestItem(text="Slow chunk", type="semantic")]
        )
        
        # Call endpoint
        response = ingest_batch_ingest_batch_post(request)
        
        # Verify timeout was recorded
        timeout_count = get_counter("ingest.analysis.timeout_count")
        assert timeout_count == 1
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    def test_ingest_error_records_metric(
        self,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test that analysis errors are recorded in metrics."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        
        # Setup mocks
        mock_get_flag.return_value = True
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 100,
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert
        mock_upsert.return_value = {
            "upserted": [{"idx": 0, "memory_id": "memory-1"}],
            "updated": [],
            "skipped": [],
        }
        
        # Mock analysis to raise error
        mock_analyze.side_effect = ValueError("Analysis failed")
        
        # Reset metrics
        reset_metrics()
        
        # Create request
        request = IngestBatchRequest(
            items=[IngestItem(text="Error chunk", type="semantic")]
        )
        
        # Call endpoint
        response = ingest_batch_ingest_batch_post(request)
        
        # Verify error was recorded
        error_count = get_counter("ingest.analysis.errors_total", labels={"error_type": "ValueError"})
        assert error_count == 1


class TestImplicateRefreshWorkerMetrics:
    """Tests for refresh worker metrics."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_process_job_records_metrics(self):
        """Test that processing a job records metrics."""
        from jobs.implicate_refresh import ImplicateRefreshWorker
        from adapters.queue import Job
        from datetime import datetime, timezone
        
        mock_queue = Mock()
        mock_builder = Mock()
        
        # Mock builder result
        mock_builder.build_incremental.return_value = {
            "success": True,
            "processed_count": 5,
            "upserted_count": 5,
            "errors": [],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={"entity_ids": [f"entity-{i}" for i in range(5)]},
            status="processing",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Reset metrics
        reset_metrics()
        
        # Process job
        metrics = worker.process_job(job)
        
        # Verify metrics were recorded
        processed_count = get_counter("implicate_refresh.processed", labels={"success": "True"})
        assert processed_count == 1
        
        # Check histograms
        entities_requested = get_histogram_stats("implicate_refresh.entities_requested")
        assert entities_requested["avg"] == 5.0
        
        entities_processed = get_histogram_stats("implicate_refresh.entities_processed")
        assert entities_processed["avg"] == 5.0
    
    def test_process_job_with_duplicates_records_deduplication(self):
        """Test that deduplication is recorded in metrics."""
        from jobs.implicate_refresh import ImplicateRefreshWorker
        from adapters.queue import Job
        from datetime import datetime, timezone
        
        mock_queue = Mock()
        mock_builder = Mock()
        
        mock_builder.build_incremental.return_value = {
            "success": True,
            "processed_count": 3,
            "upserted_count": 3,
            "errors": [],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={
                "entity_ids": ["entity-1", "entity-2", "entity-3", "entity-1", "entity-2"]  # 5 -> 3 unique
            },
            status="processing",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Reset metrics
        reset_metrics()
        
        # Process job
        metrics = worker.process_job(job)
        
        # Verify deduplication was recorded
        duplicates_removed = get_counter("implicate_refresh.duplicates_removed")
        assert duplicates_removed == 2  # 5 - 3 = 2 duplicates
        
        dedup_ratio_stats = get_histogram_stats("implicate_refresh.deduplication_ratio")
        assert dedup_ratio_stats["count"] == 1
        assert abs(dedup_ratio_stats["avg"] - 0.4) < 0.01  # 2/5 = 0.4
    
    def test_run_once_records_iteration_metrics(self):
        """Test that run_once records iteration metrics."""
        from jobs.implicate_refresh import ImplicateRefreshWorker
        from adapters.queue import Job
        from datetime import datetime, timezone
        
        mock_queue = Mock()
        mock_builder = Mock()
        
        # Mock dequeue with 2 jobs
        jobs = [
            Job(
                id=f"job-{i}",
                job_type="implicate_refresh",
                payload={"entity_ids": [f"entity-{i}"]},
                status="processing",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            for i in range(2)
        ]
        mock_queue.dequeue.return_value = jobs
        
        # Mock builder
        mock_builder.build_incremental.return_value = {
            "success": True,
            "processed_count": 1,
            "upserted_count": 1,
            "errors": [],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        # Reset metrics
        reset_metrics()
        
        # Run once
        summary = worker.run_once()
        
        # Verify iteration metrics were recorded
        iterations = get_counter("implicate_refresh.worker_iterations")
        assert iterations == 1
        
        jobs_per_iteration = get_histogram_stats("implicate_refresh.jobs_per_iteration")
        assert jobs_per_iteration["avg"] == 2.0


class TestDebugMetricsEndpoint:
    """Tests for /debug/metrics endpoint."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_metrics_endpoint_includes_ingest_metrics(self):
        """Test that /debug/metrics endpoint includes ingest metrics."""
        # Mock the missing import in router.debug
        with patch.dict('sys.modules', {'core.ledger': Mock(RheomodeLedger=Mock)}):
            from router.debug import debug_metrics
        
            # Record some metrics
            IngestMetrics.record_chunk_analyzed(
                verbs_count=5,
                frames_count=3,
                concepts_count=2,
                contradictions_count=1,
                duration_ms=30.0,
                success=True
            )
            IngestMetrics.record_timeout()
            
            # Call endpoint (mock auth)
            with patch('router.debug._require_key', return_value=None):
                response = debug_metrics(x_api_key="test-key")
                
                # Verify metrics are in response
                assert "detailed_metrics" in response or "metrics" in response
                assert "key_metrics" in response
                
                # Check key metrics
                assert response["key_metrics"]["ingest_chunks_analyzed_total"] == 1
                assert response["key_metrics"]["ingest_analysis_timeouts"] == 1
                
                # Check full metrics structure
                metrics_key = "detailed_metrics" if "detailed_metrics" in response else "metrics"
                assert "ingest.analysis.chunks_total" in response[metrics_key]["counters"]
                assert "ingest.analysis.timeout_count" in response[metrics_key]["counters"]
                assert "ingest.analysis.verbs_per_chunk" in response[metrics_key]["histograms"]
    
    def test_metrics_endpoint_includes_refresh_metrics(self):
        """Test that /debug/metrics endpoint includes refresh metrics."""
        # Mock the missing import in router.debug
        with patch.dict('sys.modules', {'core.ledger': Mock(RheomodeLedger=Mock)}):
            from router.debug import debug_metrics
        
            # Record some metrics
            ImplicateRefreshMetrics.record_job_enqueued(5)
            ImplicateRefreshMetrics.record_job_processed(
                entity_ids_count=5,
                processed_count=5,
                upserted_count=5,
                duration_s=2.5,
                success=True
            )
            
            # Call endpoint (mock auth)
            with patch('router.debug._require_key', return_value=None):
                response = debug_metrics(x_api_key="test-key")
                
                # Verify metrics are in response
                assert "key_metrics" in response
                assert response["key_metrics"]["implicate_refresh_enqueued_total"] == 1
                assert response["key_metrics"]["implicate_refresh_processed_total"] == 1
                
                # Check full metrics
                metrics_key = "detailed_metrics" if "detailed_metrics" in response else "metrics"
                assert "implicate_refresh.enqueued" in response[metrics_key]["counters"]
                assert "implicate_refresh.processed" in response[metrics_key]["counters"]
    
    def test_metrics_endpoint_reset_parameter(self):
        """Test that reset parameter clears metrics."""
        # Mock the missing import in router.debug
        with patch.dict('sys.modules', {'core.ledger': Mock(RheomodeLedger=Mock)}):
            from router.debug import debug_metrics
        
            # Record some metrics
            IngestMetrics.record_chunk_analyzed(
                verbs_count=5,
                frames_count=3,
                concepts_count=2,
                contradictions_count=0,
                duration_ms=30.0,
                success=True
            )
            
            # Call endpoint with reset=True (mock auth)
            with patch('router.debug._require_key', return_value=None):
                response = debug_metrics(x_api_key="test-key", reset=True)
                
                # Metrics should be returned
                assert response["key_metrics"]["ingest_chunks_analyzed_total"] == 1
                
                # After reset, metrics should be zero
                count = get_counter("ingest.analysis.chunks_total", labels={"success": "True"})
                assert count == 0


class TestMetricsHistogramDistributions:
    """Tests for histogram bucket distributions."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()
    
    def test_verbs_per_chunk_distribution(self):
        """Test verbs_per_chunk histogram distribution."""
        # Record various values
        for count in [1, 3, 5, 7, 10, 15, 20]:
            IngestMetrics.record_chunk_analyzed(
                verbs_count=count,
                frames_count=0,
                concepts_count=0,
                contradictions_count=0,
                duration_ms=10.0,
                success=True
            )
        
        stats = get_histogram_stats("ingest.analysis.verbs_per_chunk")
        assert stats["count"] == 7
        assert stats["sum"] == 61.0
        assert abs(stats["avg"] - 8.71) < 0.1
        
        # Check buckets (values go into FIRST bucket where value <= bucket)
        buckets = stats["buckets"]
        assert buckets[0.1] == 0  # Nothing <= 0.1
        assert buckets[0.5] == 0  # Nothing <= 0.5
        assert buckets[1.0] == 1  # 1 value (1) goes into this bucket
        assert buckets[2.5] == 0  # No values between 1.0 and 2.5
        assert buckets[5.0] == 2  # 2 values (3, 5) go into this bucket
    
    def test_duration_histogram_buckets(self):
        """Test that duration values go into correct buckets."""
        # Record different durations
        durations = [5.0, 15.0, 35.0, 75.0, 150.0]
        for duration in durations:
            IngestMetrics.record_chunk_analyzed(
                verbs_count=1,
                frames_count=1,
                concepts_count=1,
                contradictions_count=0,
                duration_ms=duration,
                success=True
            )
        
        stats = get_histogram_stats("ingest.analysis.duration_ms", labels={"success": "True"})
        assert stats["count"] == 5
        assert stats["sum"] == 280.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
