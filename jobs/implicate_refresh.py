# jobs/implicate_refresh.py — Worker for refreshing implicate index

import os
import sys
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from jobs.implicate_builder import ImplicateBuilder
from adapters.queue import QueueAdapter, Job
from vendors.supabase_client import get_client
from core.metrics import ImplicateRefreshMetrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RefreshMetrics:
    """Metrics for a refresh operation."""
    job_id: str
    entity_ids_requested: int
    entity_ids_found: int
    entity_ids_processed: int
    entity_ids_upserted: int
    duration_seconds: float
    errors: List[str]
    success: bool


class ImplicateRefreshWorker:
    """Worker that processes implicate_refresh jobs."""
    
    def __init__(
        self,
        queue: Optional[QueueAdapter] = None,
        builder: Optional[ImplicateBuilder] = None,
    ):
        """
        Initialize the worker.
        
        Args:
            queue: Optional queue adapter (creates one if not provided)
            builder: Optional implicate builder (creates one if not provided)
        """
        self.queue = queue or QueueAdapter()
        self.builder = builder or ImplicateBuilder()
        self.metrics: List[RefreshMetrics] = []
    
    def process_job(self, job: Job) -> RefreshMetrics:
        """
        Process a single implicate_refresh job.
        
        The job payload should contain:
        - entity_ids: List[str] - Entity IDs to refresh
        
        Args:
            job: Job to process
        
        Returns:
            RefreshMetrics with processing results
        """
        start_time = time.time()
        
        # Extract entity IDs from payload
        entity_ids = job.payload.get("entity_ids", [])
        
        if not entity_ids:
            error_msg = "No entity_ids in job payload"
            logger.error(f"Job {job.id}: {error_msg}")
            return RefreshMetrics(
                job_id=job.id,
                entity_ids_requested=0,
                entity_ids_found=0,
                entity_ids_processed=0,
                entity_ids_upserted=0,
                duration_seconds=time.time() - start_time,
                errors=[error_msg],
                success=False,
            )
        
        logger.info(f"Job {job.id}: Processing {len(entity_ids)} entity IDs")
        
        # Remove duplicates to ensure idempotency (sorted for determinism)
        original_count = len(entity_ids)
        entity_ids = sorted(list(set(entity_ids)))
        deduplicated_count = len(entity_ids)
        
        # Record deduplication metrics
        if original_count > deduplicated_count:
            ImplicateRefreshMetrics.record_deduplication(original_count, deduplicated_count)
        
        # Call implicate builder in incremental mode
        try:
            result = self.builder.build_incremental(entity_ids)
            
            duration = time.time() - start_time
            
            metrics = RefreshMetrics(
                job_id=job.id,
                entity_ids_requested=len(entity_ids),
                entity_ids_found=result.get("processed_count", 0),
                entity_ids_processed=result.get("processed_count", 0),
                entity_ids_upserted=result.get("upserted_count", 0),
                duration_seconds=duration,
                errors=result.get("errors", []),
                success=result.get("success", False),
            )
            
            logger.info(
                f"Job {job.id}: Completed in {duration:.2f}s - "
                f"Processed: {metrics.entity_ids_processed}, "
                f"Upserted: {metrics.entity_ids_upserted}, "
                f"Errors: {len(metrics.errors)}"
            )
            
            # Record job processing metrics
            ImplicateRefreshMetrics.record_job_processed(
                entity_ids_count=metrics.entity_ids_requested,
                processed_count=metrics.entity_ids_processed,
                upserted_count=metrics.entity_ids_upserted,
                duration_s=duration,
                success=metrics.success
            )
            
            return metrics
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Job {job.id}: {error_msg}", exc_info=True)
            
            # Record job failure metrics
            ImplicateRefreshMetrics.record_job_failed(
                error_type=type(e).__name__,
                retry_count=job.retry_count
            )
            
            return RefreshMetrics(
                job_id=job.id,
                entity_ids_requested=len(entity_ids),
                entity_ids_found=0,
                entity_ids_processed=0,
                entity_ids_upserted=0,
                duration_seconds=time.time() - start_time,
                errors=[error_msg],
                success=False,
            )
    
    def run_once(self, job_limit: int = 10) -> Dict[str, Any]:
        """
        Process a batch of jobs (single run).
        
        Args:
            job_limit: Maximum number of jobs to process in this run
        
        Returns:
            Summary statistics
        """
        iteration_start = time.time()
        logger.info(f"Checking for pending implicate_refresh jobs (limit: {job_limit})")
        
        # Dequeue pending jobs
        jobs = self.queue.dequeue(job_type="implicate_refresh", limit=job_limit)
        
        if not jobs:
            logger.info("No pending jobs found")
            return {
                "jobs_processed": 0,
                "total_entities_processed": 0,
                "total_entities_upserted": 0,
                "total_errors": 0,
            }
        
        logger.info(f"Processing {len(jobs)} jobs")
        
        total_entities_processed = 0
        total_entities_upserted = 0
        total_errors = 0
        
        for job in jobs:
            try:
                # Process the job
                metrics = self.process_job(job)
                
                # Store metrics
                self.metrics.append(metrics)
                
                # Update counters
                total_entities_processed += metrics.entity_ids_processed
                total_entities_upserted += metrics.entity_ids_upserted
                total_errors += len(metrics.errors)
                
                # Mark job status
                if metrics.success:
                    self.queue.mark_completed(
                        job.id,
                        result={
                            "processed": metrics.entity_ids_processed,
                            "upserted": metrics.entity_ids_upserted,
                            "duration": metrics.duration_seconds,
                        }
                    )
                else:
                    # Mark as failed, will retry if retries available
                    error_summary = "; ".join(metrics.errors[:3])  # First 3 errors
                    self.queue.mark_failed(job.id, error_summary, retry=True)
                
            except Exception as e:
                logger.error(f"Error processing job {job.id}: {e}", exc_info=True)
                self.queue.mark_failed(job.id, str(e), retry=True)
                total_errors += 1
        
        summary = {
            "jobs_processed": len(jobs),
            "total_entities_processed": total_entities_processed,
            "total_entities_upserted": total_entities_upserted,
            "total_errors": total_errors,
        }
        
        logger.info(
            f"Batch complete: {summary['jobs_processed']} jobs, "
            f"{summary['total_entities_processed']} entities processed, "
            f"{summary['total_entities_upserted']} upserted"
        )
        
        # Record worker iteration metrics
        iteration_duration = time.time() - iteration_start
        ImplicateRefreshMetrics.record_worker_iteration(
            jobs_processed=len(jobs),
            duration_s=iteration_duration
        )
        
        return summary
    
    def run_forever(self, poll_interval: int = 10, job_limit: int = 10):
        """
        Run the worker in a continuous loop.
        
        Args:
            poll_interval: Seconds to wait between polling for jobs
            job_limit: Maximum number of jobs to process per iteration
        """
        logger.info(
            f"Starting implicate_refresh worker "
            f"(poll_interval={poll_interval}s, job_limit={job_limit})"
        )
        
        try:
            while True:
                try:
                    self.run_once(job_limit=job_limit)
                except Exception as e:
                    logger.error(f"Error in worker loop: {e}", exc_info=True)
                
                # Wait before next iteration
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary metrics for all processed jobs.
        
        Returns:
            Dictionary with aggregated metrics
        """
        if not self.metrics:
            return {
                "total_jobs": 0,
                "total_entities_requested": 0,
                "total_entities_processed": 0,
                "total_entities_upserted": 0,
                "total_errors": 0,
                "success_rate": 0.0,
            }
        
        total_jobs = len(self.metrics)
        successful_jobs = sum(1 for m in self.metrics if m.success)
        
        return {
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "failed_jobs": total_jobs - successful_jobs,
            "success_rate": successful_jobs / total_jobs if total_jobs > 0 else 0.0,
            "total_entities_requested": sum(m.entity_ids_requested for m in self.metrics),
            "total_entities_processed": sum(m.entity_ids_processed for m in self.metrics),
            "total_entities_upserted": sum(m.entity_ids_upserted for m in self.metrics),
            "total_errors": sum(len(m.errors) for m in self.metrics),
            "average_duration": sum(m.duration_seconds for m in self.metrics) / total_jobs if total_jobs > 0 else 0.0,
        }


def main():
    """Main entry point for the worker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process implicate_refresh jobs")
    parser.add_argument(
        "--mode",
        choices=["once", "forever"],
        default="once",
        help="Run mode: process once and exit, or run forever",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds to wait between polling (forever mode only)",
    )
    parser.add_argument(
        "--job-limit",
        type=int,
        default=10,
        help="Maximum number of jobs to process per iteration",
    )
    
    args = parser.parse_args()
    
    try:
        worker = ImplicateRefreshWorker()
        
        if args.mode == "once":
            summary = worker.run_once(job_limit=args.job_limit)
            
            print("\n" + "="*50)
            print("WORKER SUMMARY")
            print("="*50)
            print(f"Jobs processed: {summary['jobs_processed']}")
            print(f"Entities processed: {summary['total_entities_processed']}")
            print(f"Entities upserted: {summary['total_entities_upserted']}")
            print(f"Errors: {summary['total_errors']}")
            
            # Print detailed metrics
            metrics_summary = worker.get_metrics_summary()
            print("\nDetailed Metrics:")
            print(f"  Success rate: {metrics_summary['success_rate']*100:.1f}%")
            print(f"  Average duration: {metrics_summary.get('average_duration', 0):.2f}s")
            
            return 0 if summary['total_errors'] == 0 else 1
        
        else:  # forever
            worker.run_forever(
                poll_interval=args.poll_interval,
                job_limit=args.job_limit,
            )
            return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
