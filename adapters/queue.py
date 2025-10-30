# adapters/queue.py — Simple database-backed job queue adapter

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from vendors.supabase_client import get_client


@dataclass
class Job:
    """Represents a job in the queue."""
    id: str
    job_type: str
    payload: Dict[str, Any]
    status: str  # pending, processing, completed, failed
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class QueueAdapter:
    """Simple database-backed job queue for background tasks."""
    
    def __init__(self, sb=None):
        """
        Initialize the queue adapter.
        
        Args:
            sb: Optional Supabase client. If not provided, will use get_client()
        """
        self.sb = sb or get_client()
    
    def enqueue(self, job_type: str, payload: Dict[str, Any], max_retries: int = 3) -> Optional[str]:
        """
        Enqueue a new job.
        
        Args:
            job_type: Type of job (e.g., 'implicate_refresh')
            payload: Job payload data
            max_retries: Maximum number of retry attempts
        
        Returns:
            Job ID if successful, None otherwise
        """
        try:
            job_data = {
                "job_type": job_type,
                "payload": payload,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "retry_count": 0,
                "max_retries": max_retries,
            }
            
            result = self.sb.table("jobs").insert(job_data).execute()
            data = result.data if hasattr(result, "data") else result.get("data")
            
            if data and len(data) > 0:
                return data[0]["id"]
            
            return None
            
        except Exception as e:
            print(f"Error enqueueing job: {e}")
            return None
    
    def dequeue(self, job_type: Optional[str] = None, limit: int = 1) -> List[Job]:
        """
        Dequeue pending jobs and mark them as processing.
        
        This operation is atomic - it fetches pending jobs and immediately
        marks them as processing to prevent duplicate processing.
        
        Args:
            job_type: Optional job type filter
            limit: Maximum number of jobs to dequeue
        
        Returns:
            List of Job objects
        """
        try:
            # Build query for pending jobs
            query = self.sb.table("jobs").select("*").eq("status", "pending")
            
            if job_type:
                query = query.eq("job_type", job_type)
            
            query = query.order("created_at").limit(limit)
            
            result = query.execute()
            data = result.data if hasattr(result, "data") else result.get("data")
            
            if not data:
                return []
            
            jobs = []
            for row in data:
                # Mark as processing immediately (simple locking mechanism)
                try:
                    update_result = (
                        self.sb.table("jobs")
                        .update({
                            "status": "processing",
                            "started_at": datetime.utcnow().isoformat()
                        })
                        .eq("id", row["id"])
                        .eq("status", "pending")  # Only update if still pending
                        .execute()
                    )
                    
                    update_data = update_result.data if hasattr(update_result, "data") else update_result.get("data")
                    
                    if update_data and len(update_data) > 0:
                        # Successfully claimed the job
                        jobs.append(Job(
                            id=row["id"],
                            job_type=row["job_type"],
                            payload=row["payload"],
                            status="processing",
                            created_at=row["created_at"],
                            started_at=datetime.utcnow().isoformat(),
                            completed_at=row.get("completed_at"),
                            error=row.get("error"),
                            retry_count=row.get("retry_count", 0),
                            max_retries=row.get("max_retries", 3),
                        ))
                except Exception as e:
                    # Job was likely claimed by another worker
                    print(f"Could not claim job {row['id']}: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            print(f"Error dequeuing jobs: {e}")
            return []
    
    def mark_completed(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a job as completed.
        
        Args:
            job_id: Job ID
            result: Optional result data to store
        
        Returns:
            True if successful, False otherwise
        """
        try:
            update_data = {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
            }
            
            if result:
                # Store result in payload
                current = self.sb.table("jobs").select("payload").eq("id", job_id).execute()
                current_data = current.data if hasattr(current, "data") else current.get("data")
                
                if current_data and len(current_data) > 0:
                    payload = current_data[0].get("payload", {})
                    payload["result"] = result
                    update_data["payload"] = payload
            
            self.sb.table("jobs").update(update_data).eq("id", job_id).execute()
            return True
            
        except Exception as e:
            print(f"Error marking job completed: {e}")
            return False
    
    def mark_failed(self, job_id: str, error: str, retry: bool = True) -> bool:
        """
        Mark a job as failed.
        
        If retry is True and max_retries not reached, job will be retried.
        Otherwise, job is marked as permanently failed.
        
        Args:
            job_id: Job ID
            error: Error message
            retry: Whether to retry the job
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current job state
            result = self.sb.table("jobs").select("retry_count, max_retries").eq("id", job_id).execute()
            data = result.data if hasattr(result, "data") else result.get("data")
            
            if not data or len(data) == 0:
                return False
            
            retry_count = data[0].get("retry_count", 0)
            max_retries = data[0].get("max_retries", 3)
            
            update_data = {
                "retry_count": retry_count + 1,
                "error": error,
            }
            
            # Decide whether to retry or fail permanently
            if retry and retry_count < max_retries:
                update_data["status"] = "pending"  # Retry
            else:
                update_data["status"] = "failed"  # Permanent failure
                update_data["completed_at"] = datetime.utcnow().isoformat()
            
            self.sb.table("jobs").update(update_data).eq("id", job_id).execute()
            return True
            
        except Exception as e:
            print(f"Error marking job failed: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by ID.
        
        Args:
            job_id: Job ID
        
        Returns:
            Job object if found, None otherwise
        """
        try:
            result = self.sb.table("jobs").select("*").eq("id", job_id).execute()
            data = result.data if hasattr(result, "data") else result.get("data")
            
            if not data or len(data) == 0:
                return None
            
            row = data[0]
            return Job(
                id=row["id"],
                job_type=row["job_type"],
                payload=row["payload"],
                status=row["status"],
                created_at=row["created_at"],
                started_at=row.get("started_at"),
                completed_at=row.get("completed_at"),
                error=row.get("error"),
                retry_count=row.get("retry_count", 0),
                max_retries=row.get("max_retries", 3),
            )
            
        except Exception as e:
            print(f"Error getting job: {e}")
            return None
    
    def get_stats(self, job_type: Optional[str] = None) -> Dict[str, int]:
        """
        Get statistics about jobs in the queue.
        
        Args:
            job_type: Optional job type filter
        
        Returns:
            Dictionary with counts by status
        """
        try:
            stats = {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "total": 0,
            }
            
            query = self.sb.table("jobs").select("status", count="exact")
            
            if job_type:
                query = query.eq("job_type", job_type)
            
            # Count by status
            for status in ["pending", "processing", "completed", "failed"]:
                result = query.eq("status", status).execute()
                count = result.count if hasattr(result, "count") else 0
                stats[status] = count
                stats["total"] += count
            
            return stats
            
        except Exception as e:
            print(f"Error getting job stats: {e}")
            return {"error": str(e)}
    
    def cleanup_old_jobs(self, days: int = 7, status: str = "completed") -> int:
        """
        Clean up old jobs to prevent table bloat.
        
        Args:
            days: Delete jobs older than this many days
            status: Only delete jobs with this status
        
        Returns:
            Number of jobs deleted
        """
        try:
            from datetime import timedelta
            
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            result = (
                self.sb.table("jobs")
                .delete()
                .eq("status", status)
                .lt("created_at", cutoff_date)
                .execute()
            )
            
            data = result.data if hasattr(result, "data") else result.get("data")
            return len(data) if data else 0
            
        except Exception as e:
            print(f"Error cleaning up jobs: {e}")
            return 0
