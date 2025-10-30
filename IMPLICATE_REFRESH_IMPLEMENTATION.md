# Implicate Refresh Worker Implementation

## Overview
Created a complete implicate_refresh worker system with idempotent processing, metrics tracking, and comprehensive job queue management.

## Files Created/Modified

### 1. `adapters/queue.py` (323 lines) - NEW
Database-backed job queue adapter for background tasks.

#### Key Features
- **Job Management**: Enqueue, dequeue, mark completed/failed
- **Atomic Operations**: Dequeue uses optimistic locking (update WHERE status='pending')
- **Retry Logic**: Automatic retry up to max_retries
- **Statistics**: Get job counts by status
- **Cleanup**: Remove old completed jobs

#### Core Methods

##### `enqueue(job_type, payload, max_retries=3)`
Creates a new job:
```python
job_id = queue.enqueue(
    job_type="implicate_refresh",
    payload={"entity_ids": ["entity-1", "entity-2"]},
    max_retries=3
)
```

##### `dequeue(job_type=None, limit=1)`
Atomically claims pending jobs:
- Fetches pending jobs
- Updates status to 'processing' (only if still pending)
- Returns claimed jobs
- **Idempotent**: Multiple workers won't claim the same job

##### `mark_completed(job_id, result=None)`
Marks job as completed with optional result data

##### `mark_failed(job_id, error, retry=True)`
Marks job as failed:
- **Retry=True**: Sets status back to 'pending' if retries available
- **Max retries reached**: Sets status to 'failed' permanently

##### `get_stats(job_type=None)`
Returns job counts:
```python
{
    "pending": 5,
    "processing": 2,
    "completed": 10,
    "failed": 1,
    "total": 18
}
```

### 2. `jobs/implicate_refresh.py` (268 lines) - NEW
Worker that processes implicate_refresh jobs by calling the implicate builder.

#### Key Features
- **Idempotent Processing**: Deduplicates entity IDs
- **Metrics Tracking**: Detailed metrics for each job
- **Error Handling**: Graceful failure with retry support
- **Logging**: Comprehensive logging at all levels
- **CLI Interface**: Run once or forever modes

#### Core Classes

##### `RefreshMetrics`
Tracks metrics for a single job:
```python
@dataclass
class RefreshMetrics:
    job_id: str
    entity_ids_requested: int
    entity_ids_found: int
    entity_ids_processed: int
    entity_ids_upserted: int
    duration_seconds: float
    errors: List[str]
    success: bool
```

##### `ImplicateRefreshWorker`
Main worker class:

**`process_job(job)`**:
1. Extracts entity_ids from payload
2. **Deduplicates IDs** for idempotency
3. Calls `builder.build_incremental(entity_ids)`
4. Returns metrics

**`run_once(job_limit=10)`**:
1. Dequeues pending jobs
2. Processes each job
3. Marks completed/failed
4. Returns summary stats

**`run_forever(poll_interval=10)`**:
- Continuous loop calling `run_once()`
- Polls every `poll_interval` seconds
- Catches errors, never crashes

**`get_metrics_summary()`**:
Returns aggregated metrics:
```python
{
    "total_jobs": 10,
    "successful_jobs": 8,
    "failed_jobs": 2,
    "success_rate": 0.8,
    "total_entities_processed": 50,
    "total_entities_upserted": 48,
    "total_errors": 2,
    "average_duration": 2.5
}
```

#### CLI Usage

**Run once (process pending jobs and exit)**:
```bash
python jobs/implicate_refresh.py --mode once --job-limit 10
```

**Run forever (daemon mode)**:
```bash
python jobs/implicate_refresh.py --mode forever --poll-interval 10 --job-limit 10
```

### 3. `migrations/110_jobs_queue.sql` - NEW
Database schema for jobs table:

```sql
create table if not exists public.jobs (
  id           uuid primary key default gen_random_uuid(),
  job_type     text not null,
  payload      jsonb not null default '{}'::jsonb,
  status       text not null check (status in ('pending','processing','completed','failed')),
  created_at   timestamptz not null default now(),
  started_at   timestamptz,
  completed_at timestamptz,
  error        text,
  retry_count  int not null default 0,
  max_retries  int not null default 3
);
```

**Indexes for Performance**:
- `ix_jobs_status_type`: Query by status and job_type
- `ix_jobs_created_at`: Sort by creation time
- `ix_jobs_status_created`: Optimized for pending job queries

### 4. `ingest/commit.py` (Modified)
Updated `enqueue_implicate_refresh()` to use QueueAdapter:

```python
def enqueue_implicate_refresh(sb, entity_ids: List[str]) -> int:
    """Enqueue implicate_refresh job using QueueAdapter."""
    if not get_feature_flag("ingest.implicate.refresh_enabled", False):
        return 0
    
    queue = QueueAdapter(sb=sb)
    job_id = queue.enqueue(
        job_type="implicate_refresh",
        payload={"entity_ids": entity_ids},
        max_retries=3,
    )
    return 1 if job_id else 0
```

### 5. `tests/ingest/test_implicate_refresh.py` (677 lines) - NEW
Comprehensive test suite with **19 tests**.

#### Test Coverage

##### `TestQueueAdapter` (6 tests)
- ✅ Enqueue creates job
- ✅ Dequeue fetches pending jobs
- ✅ Mark completed updates job
- ✅ Mark failed with retry
- ✅ Mark failed when max retries reached
- ✅ Get stats returns job counts

##### `TestImplicateRefreshWorker` (8 tests)
- ✅ Process job success
- ✅ Process job removes duplicates (idempotency)
- ✅ Process job with empty entity_ids
- ✅ Process job with errors
- ✅ Run once with no jobs
- ✅ Run once processes jobs
- ✅ Run once marks failed jobs
- ✅ Get metrics summary

##### `TestIdempotency` (2 tests)
- ✅ Same entity IDs produce same result
- ✅ Duplicate entity IDs are deduped

##### `TestCountersAndMetrics` (3 tests)
- ✅ Metrics track processed count
- ✅ Metrics track errors
- ✅ Summary aggregates metrics

## Key Features Implemented

### 1. Idempotent Processing ✅

#### Entity ID Deduplication
```python
# Remove duplicates to ensure idempotency
entity_ids = list(set(entity_ids))
```

Even if the same entity IDs are enqueued multiple times, they're processed once.

#### Atomic Job Claiming
```python
# Only claim job if still pending (prevents duplicate processing)
update_result = (
    sb.table("jobs")
    .update({"status": "processing"})
    .eq("id", job_id)
    .eq("status", "pending")  # Critical: only if still pending
    .execute()
)
```

Multiple workers can safely dequeue without conflicts.

#### Implicate Builder Idempotency
The `build_incremental()` method upserts entities to Pinecone, so:
- **Same entity → Same vector ID → Upsert (no duplicate)**
- **Re-processing job → Same embeddings → Idempotent**

### 2. Retry Logic ✅

```python
def mark_failed(job_id, error, retry=True):
    if retry and retry_count < max_retries:
        # Retry: set status back to 'pending'
        update_data["status"] = "pending"
    else:
        # Permanent failure
        update_data["status"] = "failed"
```

**Retry Behavior**:
- Failed jobs automatically retry (up to 3 attempts by default)
- Each retry increments `retry_count`
- After max retries, marked as permanently failed

### 3. Metrics and Counters ✅

#### Per-Job Metrics
```python
RefreshMetrics(
    job_id="job-123",
    entity_ids_requested=10,      # Total requested
    entity_ids_processed=9,       # Successfully processed
    entity_ids_upserted=9,        # Upserted to Pinecone
    duration_seconds=2.5,         # Processing time
    errors=["Error msg"],         # Any errors
    success=True/False            # Overall success
)
```

#### Aggregated Metrics
```python
worker.get_metrics_summary()
{
    "total_jobs": 10,
    "successful_jobs": 8,
    "failed_jobs": 2,
    "success_rate": 0.8,
    "total_entities_requested": 100,
    "total_entities_processed": 95,
    "total_entities_upserted": 95,
    "total_errors": 5,
    "average_duration": 2.3
}
```

#### Job Queue Stats
```python
queue.get_stats()
{
    "pending": 5,
    "processing": 2,
    "completed": 10,
    "failed": 1,
    "total": 18
}
```

### 4. Integration with Ingest Pipeline ✅

When analysis creates new entities:
```python
# In commit_analysis()
result = commit_analysis(sb, analysis, memory_id, file_id, chunk_idx)

# Automatically enqueues job if flag enabled
result.jobs_enqueued  # 1 if successful, 0 if not
```

When `ingest.implicate.refresh_enabled=true`:
1. New concept/frame entities are created
2. Job is enqueued with entity IDs
3. Worker processes job asynchronously
4. Entities are added to implicate index

## Test Results

```bash
19 passed in 0.44s - 100% success rate
```

### Test Breakdown
- **Queue Adapter**: 6 tests (enqueue, dequeue, mark operations, stats)
- **Worker**: 8 tests (job processing, error handling, metrics)
- **Idempotency**: 2 tests (duplicate detection, consistent results)
- **Metrics**: 3 tests (tracking, aggregation)

## Usage Examples

### 1. Start Worker (Daemon Mode)
```bash
# Run worker continuously
python jobs/implicate_refresh.py \
  --mode forever \
  --poll-interval 10 \
  --job-limit 10
```

### 2. Process Jobs Once (Cron Mode)
```bash
# Process pending jobs and exit (good for cron jobs)
python jobs/implicate_refresh.py \
  --mode once \
  --job-limit 50
```

### 3. Enqueue Jobs Programmatically
```python
from adapters.queue import QueueAdapter

queue = QueueAdapter()

# Enqueue a job
job_id = queue.enqueue(
    job_type="implicate_refresh",
    payload={"entity_ids": ["entity-1", "entity-2", "entity-3"]},
    max_retries=3
)

print(f"Enqueued job: {job_id}")
```

### 4. Monitor Queue
```python
queue = QueueAdapter()
stats = queue.get_stats(job_type="implicate_refresh")

print(f"Pending: {stats['pending']}")
print(f"Processing: {stats['processing']}")
print(f"Completed: {stats['completed']}")
print(f"Failed: {stats['failed']}")
```

### 5. View Worker Metrics
```python
worker = ImplicateRefreshWorker()
worker.run_once()

metrics = worker.get_metrics_summary()
print(f"Success rate: {metrics['success_rate']*100:.1f}%")
print(f"Entities processed: {metrics['total_entities_processed']}")
```

## Architecture

```
┌─────────────────┐
│ Ingest Pipeline │
│  (commit.py)    │
└────────┬────────┘
         │ enqueue_implicate_refresh()
         ▼
┌─────────────────┐
│   QueueAdapter  │
│   (queue.py)    │
│  ┌───────────┐  │
│  │ jobs      │  │
│  │ table     │  │
│  └───────────┘  │
└────────┬────────┘
         │ dequeue()
         ▼
┌─────────────────┐
│ RefreshWorker   │
│(implicate_      │
│ refresh.py)     │
└────────┬────────┘
         │ build_incremental()
         ▼
┌─────────────────┐
│ ImplicateBuilder│
│ (implicate_     │
│ builder.py)     │
└────────┬────────┘
         │ upsert_embeddings()
         ▼
┌─────────────────┐
│ Pinecone Index  │
│ (implicate idx) │
└─────────────────┘
```

## Acceptance Criteria Met ✅

✅ **Enqueued IDs trigger exactly one upsert each**:
- Entity IDs are deduplicated before processing
- Implicate builder upserts are idempotent (same vector ID)
- Atomic job claiming prevents duplicate processing

✅ **Retries are idempotent**:
- Failed jobs automatically retry (up to max_retries)
- Entity ID deduplication ensures consistency
- Pinecone upserts are idempotent by design

✅ **Metrics report processed count**:
- Per-job metrics track: requested, processed, upserted
- Aggregated summary metrics across all jobs
- Success rate, error count, duration tracking
- Queue statistics for monitoring

## Configuration

### Feature Flags
- **`ingest.implicate.refresh_enabled`**: Enable/disable job enqueueing (default: False)

### Environment Variables
- **`PINECONE_IMPLICATE_INDEX`**: Pinecone index name for implicate index
- **`OPENAI_API_KEY`**: OpenAI API key for embeddings

### Job Queue Configuration
- **`max_retries`**: Max retry attempts per job (default: 3)
- **`poll_interval`**: Seconds between worker polls (default: 10)
- **`job_limit`**: Max jobs per worker iteration (default: 10)

## Performance Considerations

### Batching
- Entity IDs are batched in a single job (efficient)
- Implicate builder processes entities in batches of 50
- Pinecone upserts in batches of 100

### Concurrency
- Multiple workers can run simultaneously
- Atomic job claiming prevents conflicts
- No external locks required (database handles it)

### Cleanup
```python
# Clean up old completed jobs (prevent table bloat)
queue.cleanup_old_jobs(days=7, status="completed")
```

## Error Handling

### Worker-Level
- Catches all exceptions
- Logs errors with stack traces
- Continues processing remaining jobs
- Never crashes

### Job-Level
- Failed jobs automatically retry
- Error messages stored in job record
- Permanent failures after max retries

### Logging
```
2024-10-30 21:00:00 - INFO - Checking for pending implicate_refresh jobs
2024-10-30 21:00:01 - INFO - Processing 5 jobs
2024-10-30 21:00:01 - INFO - Job job-123: Processing 10 entity IDs
2024-10-30 21:00:03 - INFO - Job job-123: Completed in 2.5s - Processed: 10, Upserted: 10
2024-10-30 21:00:04 - ERROR - Job job-456: Unexpected error: Connection timeout
2024-10-30 21:00:05 - INFO - Batch complete: 5 jobs, 48 entities processed, 48 upserted
```

## Future Enhancements

1. **Priority Queue**: Add priority field for urgent jobs
2. **Job Dependencies**: Support dependent job chains
3. **Dead Letter Queue**: Move permanently failed jobs to separate table
4. **Metrics Export**: Export metrics to Prometheus/Datadog
5. **Distributed Locks**: Use Redis for distributed locking
6. **Job Scheduling**: Add scheduled/delayed job support
7. **Partial Batches**: Process entity IDs in sub-batches for large jobs
8. **Health Checks**: Worker health monitoring endpoint
