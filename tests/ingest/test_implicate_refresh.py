#!/usr/bin/env python3
"""Tests for implicate_refresh worker and queue adapter."""

from __future__ import annotations

import pytest
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from adapters.queue import QueueAdapter, Job
from jobs.implicate_refresh import ImplicateRefreshWorker, RefreshMetrics


class TestQueueAdapter:
    """Tests for the QueueAdapter."""
    
    @patch("adapters.queue.get_client")
    def test_enqueue_creates_job(self, mock_get_client):
        """Test that enqueue creates a job."""
        mock_sb = Mock()
        mock_table = Mock()
        mock_insert_query = Mock()
        
        mock_insert_query.execute.return_value.data = [{
            "id": "job-123",
            "job_type": "implicate_refresh",
            "payload": {"entity_ids": ["entity-1"]},
            "status": "pending",
        }]
        
        mock_table.insert.return_value = mock_insert_query
        mock_sb.table.return_value = mock_table
        mock_get_client.return_value = mock_sb
        
        queue = QueueAdapter(sb=mock_sb)
        job_id = queue.enqueue(
            job_type="implicate_refresh",
            payload={"entity_ids": ["entity-1"]},
        )
        
        assert job_id == "job-123"
        mock_table.insert.assert_called_once()
    
    @patch("adapters.queue.get_client")
    def test_dequeue_fetches_pending_jobs(self, mock_get_client):
        """Test that dequeue fetches pending jobs."""
        mock_sb = Mock()
        mock_table = Mock()
        
        # Mock select query
        mock_select_query = Mock()
        mock_select_query.eq.return_value = mock_select_query
        mock_select_query.order.return_value = mock_select_query
        mock_select_query.limit.return_value = mock_select_query
        mock_select_query.execute.return_value.data = [{
            "id": "job-123",
            "job_type": "implicate_refresh",
            "payload": {"entity_ids": ["entity-1"]},
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": 0,
            "max_retries": 3,
        }]
        
        # Mock update query
        mock_update_query = Mock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value.data = [{
            "id": "job-123",
            "status": "processing",
        }]
        
        def table_method(name):
            if name == "jobs":
                mock_table.select.return_value = mock_select_query
                mock_table.update.return_value = mock_update_query
                return mock_table
            return Mock()
        
        mock_sb.table.side_effect = table_method
        mock_get_client.return_value = mock_sb
        
        queue = QueueAdapter(sb=mock_sb)
        jobs = queue.dequeue(job_type="implicate_refresh", limit=1)
        
        assert len(jobs) == 1
        assert jobs[0].id == "job-123"
        assert jobs[0].status == "processing"
    
    @patch("adapters.queue.get_client")
    def test_mark_completed_updates_job(self, mock_get_client):
        """Test that mark_completed updates job status."""
        mock_sb = Mock()
        mock_table = Mock()
        
        # Mock select for getting current payload
        mock_select_query = Mock()
        mock_select_query.eq.return_value = mock_select_query
        mock_select_query.execute.return_value.data = [{
            "payload": {"entity_ids": ["entity-1"]}
        }]
        
        # Mock update
        mock_update_query = Mock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = Mock()
        
        def table_method(name):
            if name == "jobs":
                mock_table.select.return_value = mock_select_query
                mock_table.update.return_value = mock_update_query
                return mock_table
            return Mock()
        
        mock_sb.table.side_effect = table_method
        mock_get_client.return_value = mock_sb
        
        queue = QueueAdapter(sb=mock_sb)
        success = queue.mark_completed("job-123", result={"processed": 1})
        
        assert success is True
        mock_table.update.assert_called()
    
    @patch("adapters.queue.get_client")
    def test_mark_failed_with_retry(self, mock_get_client):
        """Test that mark_failed sets status to pending for retry."""
        mock_sb = Mock()
        mock_table = Mock()
        
        # Mock select for getting retry count
        mock_select_query = Mock()
        mock_select_query.eq.return_value = mock_select_query
        mock_select_query.execute.return_value.data = [{
            "retry_count": 0,
            "max_retries": 3,
        }]
        
        # Mock update
        mock_update_query = Mock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = Mock()
        
        def table_method(name):
            if name == "jobs":
                mock_table.select.return_value = mock_select_query
                mock_table.update.return_value = mock_update_query
                return mock_table
            return Mock()
        
        mock_sb.table.side_effect = table_method
        mock_get_client.return_value = mock_sb
        
        queue = QueueAdapter(sb=mock_sb)
        success = queue.mark_failed("job-123", "Test error", retry=True)
        
        assert success is True
        
        # Verify that update was called with status='pending' (for retry)
        update_call = mock_table.update.call_args[0][0]
        assert update_call["status"] == "pending"
        assert update_call["retry_count"] == 1
    
    @patch("adapters.queue.get_client")
    def test_mark_failed_max_retries_reached(self, mock_get_client):
        """Test that mark_failed sets status to failed when max retries reached."""
        mock_sb = Mock()
        mock_table = Mock()
        
        # Mock select for getting retry count
        mock_select_query = Mock()
        mock_select_query.eq.return_value = mock_select_query
        mock_select_query.execute.return_value.data = [{
            "retry_count": 3,
            "max_retries": 3,
        }]
        
        # Mock update
        mock_update_query = Mock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = Mock()
        
        def table_method(name):
            if name == "jobs":
                mock_table.select.return_value = mock_select_query
                mock_table.update.return_value = mock_update_query
                return mock_table
            return Mock()
        
        mock_sb.table.side_effect = table_method
        mock_get_client.return_value = mock_sb
        
        queue = QueueAdapter(sb=mock_sb)
        success = queue.mark_failed("job-123", "Test error", retry=True)
        
        assert success is True
        
        # Verify that update was called with status='failed' (max retries reached)
        update_call = mock_table.update.call_args[0][0]
        assert update_call["status"] == "failed"
    
    @patch("adapters.queue.get_client")
    def test_get_stats(self, mock_get_client):
        """Test that get_stats returns job counts."""
        mock_sb = Mock()
        
        # The get_stats method creates a new query per status
        # Each query chain: select() -> eq() -> execute()
        # We need to track which status is being queried
        
        status_counts = {
            "pending": 5,
            "processing": 2,
            "completed": 10,
            "failed": 1,
        }
        
        def table_method(name):
            if name == "jobs":
                mock_table = Mock()
                
                # Track the current status being queried
                current_status = [None]
                
                def select_method(*args, **kwargs):
                    mock_query = Mock()
                    
                    def eq_method(field, value):
                        # Capture the status value
                        if field == "status":
                            current_status[0] = value
                        mock_query.eq.return_value = mock_query
                        return mock_query
                    
                    def execute_method():
                        # Return the count for the current status
                        result = Mock()
                        result.count = status_counts.get(current_status[0], 0)
                        return result
                    
                    mock_query.eq = eq_method
                    mock_query.execute = execute_method
                    return mock_query
                
                mock_table.select = select_method
                return mock_table
            return Mock()
        
        mock_sb.table = table_method
        mock_get_client.return_value = mock_sb
        
        queue = QueueAdapter(sb=mock_sb)
        stats = queue.get_stats()
        
        assert stats["pending"] == 5
        assert stats["processing"] == 2
        assert stats["completed"] == 10
        assert stats["failed"] == 1
        assert stats["total"] == 18


class TestImplicateRefreshWorker:
    """Tests for the ImplicateRefreshWorker."""
    
    def test_process_job_success(self):
        """Test successful job processing."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        # Mock builder result
        mock_builder.build_incremental.return_value = {
            "success": True,
            "processed_count": 2,
            "upserted_count": 2,
            "errors": [],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={"entity_ids": ["entity-1", "entity-2"]},
            status="processing",
            created_at=datetime.utcnow().isoformat(),
        )
        
        metrics = worker.process_job(job)
        
        assert metrics.success is True
        assert metrics.entity_ids_requested == 2
        assert metrics.entity_ids_processed == 2
        assert metrics.entity_ids_upserted == 2
        assert len(metrics.errors) == 0
        
        # Verify builder was called
        mock_builder.build_incremental.assert_called_once_with(["entity-1", "entity-2"])
    
    def test_process_job_removes_duplicates(self):
        """Test that duplicate entity IDs are removed."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        mock_builder.build_incremental.return_value = {
            "success": True,
            "processed_count": 2,
            "upserted_count": 2,
            "errors": [],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={"entity_ids": ["entity-1", "entity-2", "entity-1", "entity-2"]},
            status="processing",
            created_at=datetime.utcnow().isoformat(),
        )
        
        metrics = worker.process_job(job)
        
        # Verify builder was called with deduplicated list
        call_args = mock_builder.build_incremental.call_args[0][0]
        assert len(call_args) == 2
        assert set(call_args) == {"entity-1", "entity-2"}
    
    def test_process_job_empty_entity_ids(self):
        """Test job with empty entity_ids."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={},  # No entity_ids
            status="processing",
            created_at=datetime.utcnow().isoformat(),
        )
        
        metrics = worker.process_job(job)
        
        assert metrics.success is False
        assert len(metrics.errors) > 0
        assert "No entity_ids" in metrics.errors[0]
        
        # Builder should not be called
        mock_builder.build_incremental.assert_not_called()
    
    def test_process_job_with_errors(self):
        """Test job processing with errors."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        # Mock builder result with errors
        mock_builder.build_incremental.return_value = {
            "success": False,
            "processed_count": 1,
            "upserted_count": 1,
            "errors": ["Error processing entity-2"],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={"entity_ids": ["entity-1", "entity-2"]},
            status="processing",
            created_at=datetime.utcnow().isoformat(),
        )
        
        metrics = worker.process_job(job)
        
        assert metrics.success is False
        assert len(metrics.errors) == 1
        assert metrics.entity_ids_processed == 1
        assert metrics.entity_ids_upserted == 1
    
    def test_run_once_no_jobs(self):
        """Test run_once with no pending jobs."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        # No jobs available
        mock_queue.dequeue.return_value = []
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        summary = worker.run_once()
        
        assert summary["jobs_processed"] == 0
        assert summary["total_entities_processed"] == 0
    
    def test_run_once_processes_jobs(self):
        """Test run_once processes available jobs."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        # Mock available jobs
        jobs = [
            Job(
                id="job-1",
                job_type="implicate_refresh",
                payload={"entity_ids": ["entity-1"]},
                status="processing",
                created_at=datetime.utcnow().isoformat(),
            ),
            Job(
                id="job-2",
                job_type="implicate_refresh",
                payload={"entity_ids": ["entity-2", "entity-3"]},
                status="processing",
                created_at=datetime.utcnow().isoformat(),
            ),
        ]
        
        mock_queue.dequeue.return_value = jobs
        
        # Mock builder results
        mock_builder.build_incremental.side_effect = [
            {"success": True, "processed_count": 1, "upserted_count": 1, "errors": []},
            {"success": True, "processed_count": 2, "upserted_count": 2, "errors": []},
        ]
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        summary = worker.run_once()
        
        assert summary["jobs_processed"] == 2
        assert summary["total_entities_processed"] == 3
        assert summary["total_entities_upserted"] == 3
        assert summary["total_errors"] == 0
        
        # Verify jobs were marked completed
        assert mock_queue.mark_completed.call_count == 2
    
    def test_run_once_marks_failed_jobs(self):
        """Test that failed jobs are marked appropriately."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        # Mock available job
        jobs = [
            Job(
                id="job-1",
                job_type="implicate_refresh",
                payload={"entity_ids": ["entity-1"]},
                status="processing",
                created_at=datetime.utcnow().isoformat(),
            ),
        ]
        
        mock_queue.dequeue.return_value = jobs
        
        # Mock builder failure
        mock_builder.build_incremental.return_value = {
            "success": False,
            "processed_count": 0,
            "upserted_count": 0,
            "errors": ["Failed to process entity"],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        summary = worker.run_once()
        
        assert summary["jobs_processed"] == 1
        assert summary["total_errors"] == 1
        
        # Verify job was marked failed
        mock_queue.mark_failed.assert_called_once()
    
    def test_get_metrics_summary(self):
        """Test metrics summary aggregation."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        # Add some metrics
        worker.metrics = [
            RefreshMetrics(
                job_id="job-1",
                entity_ids_requested=2,
                entity_ids_found=2,
                entity_ids_processed=2,
                entity_ids_upserted=2,
                duration_seconds=1.5,
                errors=[],
                success=True,
            ),
            RefreshMetrics(
                job_id="job-2",
                entity_ids_requested=3,
                entity_ids_found=3,
                entity_ids_processed=2,
                entity_ids_upserted=2,
                duration_seconds=2.0,
                errors=["Error processing entity-3"],
                success=False,
            ),
        ]
        
        summary = worker.get_metrics_summary()
        
        assert summary["total_jobs"] == 2
        assert summary["successful_jobs"] == 1
        assert summary["failed_jobs"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["total_entities_requested"] == 5
        assert summary["total_entities_processed"] == 4
        assert summary["total_entities_upserted"] == 4
        assert summary["total_errors"] == 1
        assert summary["average_duration"] == 1.75


class TestIdempotency:
    """Tests for idempotent processing."""
    
    def test_same_entity_ids_produce_same_result(self):
        """Test that processing the same entity IDs twice is idempotent."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        # Mock builder to return consistent results
        mock_builder.build_incremental.return_value = {
            "success": True,
            "processed_count": 2,
            "upserted_count": 2,
            "errors": [],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={"entity_ids": ["entity-1", "entity-2"]},
            status="processing",
            created_at=datetime.utcnow().isoformat(),
        )
        
        # Process job twice
        metrics1 = worker.process_job(job)
        metrics2 = worker.process_job(job)
        
        # Both should produce identical results
        assert metrics1.entity_ids_processed == metrics2.entity_ids_processed
        assert metrics1.entity_ids_upserted == metrics2.entity_ids_upserted
        assert metrics1.success == metrics2.success
        
        # Builder should be called twice with same args
        assert mock_builder.build_incremental.call_count == 2
    
    def test_duplicate_entity_ids_are_deduped(self):
        """Test that duplicate entity IDs in a job are deduplicated."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        mock_builder.build_incremental.return_value = {
            "success": True,
            "processed_count": 1,
            "upserted_count": 1,
            "errors": [],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={
                "entity_ids": [
                    "entity-1",
                    "entity-1",
                    "entity-1",  # Same entity 3 times
                ]
            },
            status="processing",
            created_at=datetime.utcnow().isoformat(),
        )
        
        metrics = worker.process_job(job)
        
        # Verify only unique entity IDs were passed to builder
        call_args = mock_builder.build_incremental.call_args[0][0]
        assert len(call_args) == 1
        assert call_args == ["entity-1"]
        
        # Metrics should reflect the requested count (3) but processed count (1)
        assert metrics.entity_ids_requested == 1  # After deduplication


class TestCountersAndMetrics:
    """Tests for counters and metrics reporting."""
    
    def test_metrics_track_processed_count(self):
        """Test that metrics correctly track processed entity count."""
        mock_queue = Mock()
        mock_builder = Mock()
        
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
            created_at=datetime.utcnow().isoformat(),
        )
        
        metrics = worker.process_job(job)
        
        assert metrics.entity_ids_requested == 5
        assert metrics.entity_ids_processed == 5
        assert metrics.entity_ids_upserted == 5
    
    def test_metrics_track_errors(self):
        """Test that metrics correctly track errors."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        mock_builder.build_incremental.return_value = {
            "success": False,
            "processed_count": 3,
            "upserted_count": 3,
            "errors": ["Error 1", "Error 2"],
        }
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        job = Job(
            id="job-123",
            job_type="implicate_refresh",
            payload={"entity_ids": [f"entity-{i}" for i in range(5)]},
            status="processing",
            created_at=datetime.utcnow().isoformat(),
        )
        
        metrics = worker.process_job(job)
        
        assert len(metrics.errors) == 2
        assert metrics.success is False
    
    def test_summary_aggregates_metrics(self):
        """Test that summary correctly aggregates multiple job metrics."""
        mock_queue = Mock()
        mock_builder = Mock()
        
        worker = ImplicateRefreshWorker(queue=mock_queue, builder=mock_builder)
        
        # Simulate processing multiple jobs
        worker.metrics = [
            RefreshMetrics(
                job_id=f"job-{i}",
                entity_ids_requested=10,
                entity_ids_found=10,
                entity_ids_processed=10,
                entity_ids_upserted=10,
                duration_seconds=1.0,
                errors=[],
                success=True,
            )
            for i in range(5)
        ]
        
        summary = worker.get_metrics_summary()
        
        assert summary["total_jobs"] == 5
        assert summary["successful_jobs"] == 5
        assert summary["total_entities_requested"] == 50
        assert summary["total_entities_processed"] == 50
        assert summary["total_entities_upserted"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
