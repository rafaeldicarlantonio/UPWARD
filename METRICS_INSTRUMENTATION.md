# Metrics Instrumentation for Ingest Pipeline and Refresh Worker

## Overview

Comprehensive metrics instrumentation has been added to the ingest analysis pipeline and implicate refresh worker, with all metrics exposed via the `/debug/metrics` endpoint.

## Files Modified

### 1. `core/metrics.py`
- **Added `IngestMetrics` class** with methods to record:
  - `record_chunk_analyzed()`: Records successful chunk analysis with verbs, frames, concepts, contradictions counts
  - `record_timeout()`: Increments counter when chunk analysis exceeds timeout
  - `record_analysis_error()`: Records analysis failures by error type
  - `record_entities_created()`: Tracks concepts, frames, and edges created during commit
  - `record_commit_errors()`: Records errors during the commit phase

- **Added `ImplicateRefreshMetrics` class** with methods to record:
  - `record_job_enqueued()`: Tracks when refresh jobs are enqueued
  - `record_job_processed()`: Records successful job processing with entity counts and duration
  - `record_job_failed()`: Tracks job failures with error type and retry count
  - `record_worker_iteration()`: Records worker run_once iterations
  - `record_deduplication()`: Tracks duplicate entity ID removal

### 2. `router/ingest.py`
- Added `IngestMetrics` import and instrumentation throughout the batch ingest flow
- Records metrics for:
  - Each chunk analyzed (success/failure)
  - Analysis timeouts
  - Analysis errors
  - Entities and edges created during commit
  - Commit errors

### 3. `ingest/commit.py`
- Added `ImplicateRefreshMetrics` import
- Records metric when implicate_refresh jobs are enqueued

### 4. `jobs/implicate_refresh.py`
- Added comprehensive metrics instrumentation:
  - Entity ID deduplication tracking
  - Job processing success/failure
  - Worker iteration metrics
  - Job failure with error type and retry count

### 5. `router/debug.py`
- Updated `/debug/metrics` endpoint to include key metrics summary for:
  - `ingest_chunks_analyzed_total`
  - `ingest_analysis_timeouts`
  - `implicate_refresh_enqueued_total`
  - `implicate_refresh_processed_total`

### 6. `tests/ingest/test_metrics.py` (New)
- Comprehensive test suite with 22 tests covering:
  - Unit tests for all IngestMetrics methods
  - Unit tests for all ImplicateRefreshMetrics methods
  - Integration tests for ingest pipeline with metrics
  - Integration tests for refresh worker with metrics
  - Tests for /debug/metrics endpoint
  - Histogram distribution tests

## Metrics Exposed

### Counters

#### Ingest Analysis
- `ingest.analysis.chunks_total{success}`: Total chunks analyzed (labeled by success)
- `ingest.analysis.timeout_count`: Number of chunks that exceeded timeout
- `ingest.analysis.errors_total{error_type}`: Analysis errors by type
- `ingest.commit.total`: Total commit operations
- `ingest.commit.errors_total`: Commit errors count

#### Implicate Refresh
- `implicate_refresh.enqueued`: Jobs enqueued for processing
- `implicate_refresh.processed{success}`: Jobs processed (labeled by success)
- `implicate_refresh.failed{error_type}`: Failed jobs by error type
- `implicate_refresh.worker_iterations`: Worker run_once iterations
- `implicate_refresh.duplicates_removed`: Duplicate entity IDs removed

### Histograms

#### Ingest Analysis
- `ingest.analysis.verbs_per_chunk`: Distribution of verb predicates per chunk
- `ingest.analysis.frames_per_chunk`: Distribution of event frames per chunk
- `ingest.analysis.concepts_suggested`: Distribution of concepts suggested per chunk
- `ingest.analysis.contradictions_found`: Distribution of contradictions detected
- `ingest.analysis.duration_ms{success}`: Analysis duration per chunk

#### Ingest Commit
- `ingest.commit.concepts_created`: Concepts created per commit
- `ingest.commit.frames_created`: Frames created per commit
- `ingest.commit.edges_created`: Edges created per commit

#### Implicate Refresh
- `implicate_refresh.entity_ids_per_job`: Entity IDs per enqueued job
- `implicate_refresh.entities_requested`: Entities requested per job
- `implicate_refresh.entities_processed`: Entities actually processed
- `implicate_refresh.entities_upserted`: Entities upserted to vector store
- `implicate_refresh.job_duration_seconds{success}`: Job processing duration
- `implicate_refresh.retry_count`: Retry attempts distribution
- `implicate_refresh.jobs_per_iteration`: Jobs processed per worker iteration
- `implicate_refresh.iteration_duration_seconds`: Worker iteration duration
- `implicate_refresh.deduplication_ratio`: Ratio of duplicates removed

## Usage

### Viewing Metrics

```bash
# Get all metrics via API
curl -H "X-API-KEY: your-key" http://localhost:8000/debug/metrics

# Get metrics with reset
curl -H "X-API-KEY: your-key" "http://localhost:8000/debug/metrics?reset=true"
```

### Sample Response

```json
{
  "status": "ok",
  "key_metrics": {
    "ingest_chunks_analyzed_total": 150,
    "ingest_analysis_timeouts": 3,
    "implicate_refresh_enqueued_total": 45,
    "implicate_refresh_processed_total": 42
  },
  "detailed_metrics": {
    "counters": {
      "ingest.analysis.chunks_total": [...],
      "implicate_refresh.enqueued": [...]
    },
    "histograms": {
      "ingest.analysis.verbs_per_chunk": [...],
      "implicate_refresh.job_duration_seconds": [...]
    }
  }
}
```

## Testing

All metrics are thoroughly tested:

```bash
# Run all metrics tests
pytest tests/ingest/test_metrics.py -v

# Run specific test class
pytest tests/ingest/test_metrics.py::TestIngestMetrics -v
pytest tests/ingest/test_metrics.py::TestImplicateRefreshMetrics -v

# Run integration tests
pytest tests/ingest/test_metrics.py::TestMetricsIntegration -v
```

## Acceptance Criteria ✅

All acceptance criteria met:

1. ✅ **Counters and histograms defined**: All requested metrics implemented
   - `ingest.analysis.chunks_total`
   - `ingest.analysis.verbs_per_chunk`
   - `ingest.analysis.frames_per_chunk`
   - `ingest.analysis.concepts_suggested`
   - `ingest.analysis.contradictions_found`
   - `ingest.analysis.timeout_count`
   - `implicate_refresh.enqueued`
   - `implicate_refresh.processed`

2. ✅ **Tests increment metrics**: Comprehensive test suite with 22 tests validates all metrics

3. ✅ **`/debug/metrics` shows them**: Updated endpoint includes key metrics summary and detailed metrics

## Notes

- All metrics are thread-safe and use the existing `MetricsCollector` infrastructure
- Histogram buckets use the default configuration: [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0]
- Metrics can be reset via the `/debug/metrics?reset=true` endpoint
- All existing tests continue to pass with the new instrumentation
