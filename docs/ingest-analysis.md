# Ingest Analysis System - Operator Runbook

## Overview

The ingest analysis system processes uploaded files through an NLP pipeline to extract:
- **Concepts**: Key ideas and entities from the text
- **Event Frames**: Structured events with roles (claims, evidence, observations, etc.)
- **Contradictions**: Conflicting statements detected within and across documents
- **Entity Relationships**: Semantic links (supports, contradicts, evidence_of)

The system is designed to be **idempotent**, **policy-enforced**, and **observable** through comprehensive metrics.

---

## Architecture

```
┌─────────────────┐
│  Upload File    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Chunk Text     │─────▶│ Store in Memory  │
└────────┬────────┘      └──────────────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│ Analyze Chunk   │─────▶│  Apply Policy    │
│  (NLP Pipeline) │      │   Caps & Filter  │
└────────┬────────┘      └─────────┬────────┘
         │                         │
         │  ┌──────────────────────┘
         │  │
         ▼  ▼
┌─────────────────┐
│  Commit Phase   │
│  - Concepts     │
│  - Frames       │
│  - Edges        │
│  - Contradicts  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│ Enqueue Refresh │─────▶│ Refresh Worker   │
│     Jobs        │      │  (Background)    │
└─────────────────┘      └─────────┬────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │ Implicate Index  │
                         │  (Pinecone)      │
                         └──────────────────┘
```

---

## Feature Flags

The system is controlled by three main feature flags (set in database or env):

### 1. `ingest.analysis.enabled`

**Controls**: Whether NLP analysis runs during batch ingest

- **Default**: `False`
- **When enabled**: Each chunk is analyzed for concepts, frames, and contradictions
- **When disabled**: Only basic memory storage (no NLP analysis)

```sql
-- Enable analysis
INSERT INTO feature_flags (flag_name, enabled) 
VALUES ('ingest.analysis.enabled', true)
ON CONFLICT (flag_name) DO UPDATE SET enabled = true;

-- Disable analysis
UPDATE feature_flags SET enabled = false WHERE flag_name = 'ingest.analysis.enabled';
```

### 2. `ingest.contradictions.enabled`

**Controls**: Whether contradiction detection runs

- **Default**: `False`
- **Requires**: `ingest.analysis.enabled = true`
- **When enabled**: Detects conflicting statements and stores them
- **Note**: Subject to role policy (general users never get contradictions)

```sql
-- Enable contradictions
INSERT INTO feature_flags (flag_name, enabled)
VALUES ('ingest.contradictions.enabled', true)
ON CONFLICT (flag_name) DO UPDATE SET enabled = true;
```

### 3. `ingest.implicate.refresh_enabled`

**Controls**: Whether implicate index refresh jobs are enqueued

- **Default**: `False`
- **When enabled**: New concepts/frames trigger background index refresh
- **When disabled**: Manual index rebuild required

```sql
-- Enable automatic refresh
INSERT INTO feature_flags (flag_name, enabled)
VALUES ('ingest.implicate.refresh_enabled', true)
ON CONFLICT (flag_name) DO UPDATE SET enabled = true;
```

---

## Configuration Limits

Set in `config.py` or environment variables:

### Analysis Limits

```bash
# Maximum time per chunk (ms) - chunks exceeding this are skipped
INGEST_ANALYSIS_MAX_MS_PER_CHUNK=5000  # 5 seconds

# Maximum verbs/predicates to extract per chunk
INGEST_ANALYSIS_MAX_VERBS=20

# Maximum event frames to extract per chunk
INGEST_ANALYSIS_MAX_FRAMES=10

# Maximum concepts to suggest per chunk
INGEST_ANALYSIS_MAX_CONCEPTS=10
```

### Policy Limits

Defined in `config/ingest_policy.yaml` (see Policy System section below)

---

## Policy System

### Overview

The policy system enforces role-based caps and tolerances defined in `config/ingest_policy.yaml`.

### Policy File Structure

```yaml
roles:
  admin:
    max_concepts_per_file: 500
    max_frames_per_chunk: 50
    write_contradictions_to_memories: true
    allowed_frame_types:
      - claim
      - evidence
      - question
      - observation
      - hypothesis
      - conclusion
      - method
      - result
    contradiction_tolerance: 0.1  # Only keep high-confidence (90%+)
  
  general:
    max_concepts_per_file: 50
    max_frames_per_chunk: 10
    write_contradictions_to_memories: false  # No contradictions for general users
    allowed_frame_types:
      - claim
      - evidence
    contradiction_tolerance: 0.3

global_limits:
  max_concepts_per_file_absolute: 1000
  max_frames_per_chunk_absolute: 100
  max_edges_per_commit_absolute: 5000
```

### Policy Enforcement Rules

1. **Concept Capping**: Limits concepts per file to role's `max_concepts_per_file`
2. **Frame Filtering**: Only allows frame types in `allowed_frame_types` list
3. **Frame Capping**: Limits frames per chunk to `max_frames_per_chunk`
4. **Contradiction Filtering**: 
   - Filters by `contradiction_tolerance` (score threshold)
   - Blocks all contradictions if `write_contradictions_to_memories = false`
5. **Multiple Roles**: Uses most permissive policy when user has multiple roles
6. **Unknown Roles**: Falls back to safe default policy (20 concepts, claim only)

### Editing Policies

```bash
# Edit policy file
vim config/ingest_policy.yaml

# Test policy loading
python3 -c "
from core.policy import get_ingest_policy_manager
manager = get_ingest_policy_manager()
policy = manager.get_policy(['pro'])
print(f'Max concepts: {policy.max_concepts_per_file}')
print(f'Allowed frames: {policy.allowed_frame_types}')
"

# Reload application to pick up changes (policies load at startup)
```

---

## ID Generation and Idempotency

### Concept Entity IDs

**Format**: `concept:{slugified-name}`

**Slugification Rules**:
- Convert to lowercase
- Replace spaces/underscores with hyphens
- Remove non-alphanumeric (except hyphens)
- Remove consecutive hyphens
- Strip leading/trailing hyphens
- Limit to 64 characters

**Example**:
```
Input:  "Machine Learning"
Output: concept:machine-learning

Input:  "Neural Networks & Deep Learning"
Output: concept:neural-networks-deep-learning
```

**Idempotency**: Same concept name always generates same stable ID

### Frame Entity IDs

**Format**: `frame:{slugified-file-id}:{chunk-idx}:{frame-id}`

**Example**:
```
file_id = "research-paper-2024.pdf"
chunk_idx = 2
frame_id = "frame-1"

Result: frame:research-paper-2024-pdf:2:frame-1
```

**Idempotency**: Same file + chunk + frame combination always generates same ID

### Edge IDs

**Idempotency Check**: Before creating edge, checks if edge exists:
```sql
SELECT id FROM entity_edges 
WHERE from_id = ? AND to_id = ? AND rel_type = ?
LIMIT 1
```

If exists, returns existing ID. If not, creates new edge.

### Re-Ingestion Behavior

**Scenario**: Same file uploaded twice

1. **Memory rows**: New memory rows created (not idempotent at memory level)
2. **Concept entities**: Reuse existing (idempotent via name uniqueness)
3. **Frame entities**: Reuse existing (idempotent via stable naming)
4. **Edges**: Reuse existing (idempotent via uniqueness check)
5. **Result**: No duplicate entities or edges, but new memories link to existing entities

---

## Metrics and Observability

### Accessing Metrics

```bash
# Get all metrics
curl -H "X-API-KEY: $API_KEY" https://your-app.com/debug/metrics

# Get metrics and reset
curl -H "X-API-KEY: $API_KEY" "https://your-app.com/debug/metrics?reset=true"
```

### Key Metrics

#### Ingest Analysis
- `ingest.analysis.chunks_total{success}` - Total chunks analyzed
- `ingest.analysis.verbs_per_chunk` - Histogram of verb counts
- `ingest.analysis.frames_per_chunk` - Histogram of frame counts
- `ingest.analysis.concepts_suggested` - Histogram of concept counts
- `ingest.analysis.contradictions_found` - Histogram of contradiction counts
- `ingest.analysis.timeout_count` - Chunks that exceeded timeout
- `ingest.analysis.errors_total{error_type}` - Analysis failures by type
- `ingest.analysis.duration_ms{success}` - Analysis duration histogram

#### Commit Phase
- `ingest.commit.total` - Total commit operations
- `ingest.commit.concepts_created` - Concepts per commit
- `ingest.commit.frames_created` - Frames per commit
- `ingest.commit.edges_created` - Edges per commit
- `ingest.commit.errors_total` - Commit errors

#### Implicate Refresh
- `implicate_refresh.enqueued` - Jobs enqueued
- `implicate_refresh.processed{success}` - Jobs processed
- `implicate_refresh.failed{error_type}` - Failed jobs
- `implicate_refresh.entities_upserted` - Entities added to index
- `implicate_refresh.job_duration_seconds{success}` - Job duration

### Monitoring Queries

```python
# Check health
from core.metrics import get_all_metrics

metrics = get_all_metrics()
print(f"Uptime: {metrics['uptime_seconds']}s")
print(f"Chunks analyzed: {metrics['counters'].get('ingest.analysis.chunks_total', [])}")

# Check for issues
timeouts = get_counter('ingest.analysis.timeout_count')
errors = get_counter('ingest.analysis.errors_total')
print(f"Timeouts: {timeouts}, Errors: {errors}")
```

---

## Implicate Index Management

### What is the Implicate Index?

The implicate index is a vector store (Pinecone) containing embedded representations of:
- Concepts and their relationships
- Event frames and their connections
- Entity neighborhood context

Used for semantic search and hypothesis generation.

### Rebuilding the Index

#### Full Rebuild (Clears and Rebuilds Everything)

```bash
# Clear Pinecone index first (deletes all vectors)
python3 -c "
from adapters.pinecone_client import get_pinecone_client
pc = get_pinecone_client()
index = pc.Index('your-implicate-index-name')
# Delete all vectors in batches
index.delete(delete_all=True)
print('Index cleared')
"

# Full rebuild from database
./scripts/backfill_implicate.sh --mode full --min-degree 5 --batch-size 50
```

**Parameters**:
- `--mode full`: Rebuild entire index from scratch
- `--min-degree 5`: Only index entities with ≥5 connections
- `--batch-size 50`: Process 50 entities at a time

**Duration**: Depends on data size. ~1000 entities ≈ 5-10 minutes

#### Incremental Refresh (Specific Entities)

```bash
# Refresh specific concepts/frames
./scripts/backfill_implicate.sh --mode incremental \
  --entity-ids "uuid-1,uuid-2,uuid-3"
```

**Use cases**:
- After manual entity edits
- Fixing specific entities that failed
- Testing index updates

#### Via Refresh Worker (Automatic)

```bash
# Start the refresh worker (processes queued jobs)
python3 jobs/implicate_refresh.py --mode forever --poll-interval 10 --job-limit 10

# Or run once (process pending jobs then exit)
python3 jobs/implicate_refresh.py --mode once --job-limit 10
```

**When to use**:
- Production: Run as background service
- Development: Run on-demand or in dev mode

**Monitoring**:
```bash
# Check queue status
python3 -c "
from adapters.queue import QueueAdapter
from vendors.supabase_client import get_client

queue = QueueAdapter(sb=get_client())
stats = queue.get_stats()
print(f'Pending: {stats[\"pending\"]}')
print(f'Processing: {stats[\"processing\"]}')
print(f'Completed: {stats[\"completed\"]}')
print(f'Failed: {stats[\"failed\"]}')
"
```

### Clearing Specific Entity Types

```bash
# Delete all concept entities and their edges
psql "$DATABASE_URL" << EOF
DELETE FROM entity_edges WHERE from_id IN (SELECT id FROM entities WHERE type = 'concept');
DELETE FROM entity_edges WHERE to_id IN (SELECT id FROM entities WHERE type = 'concept');
DELETE FROM entities WHERE type = 'concept';
EOF

# Delete all frame entities (type = 'artifact')
psql "$DATABASE_URL" << EOF
DELETE FROM entity_edges WHERE from_id IN (SELECT id FROM entities WHERE type = 'artifact');
DELETE FROM entity_edges WHERE to_id IN (SELECT id FROM entities WHERE type = 'artifact');
DELETE FROM entities WHERE type = 'artifact';
EOF

# Rebuild index after deletion
./scripts/backfill_implicate.sh --mode full
```

---

## CLI Examples

### Backfilling a Directory

#### Option 1: Using the Batch Ingest Endpoint

```bash
# Prepare files for ingestion
python3 scripts/make_ingest_payload.py /path/to/docs > payload.json

# Send to API
curl -X POST https://your-app.com/ingest/batch \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d @payload.json
```

#### Option 2: Direct Python Script

```python
#!/usr/bin/env python3
"""Backfill a directory of files."""
import os
import glob
import requests
from pathlib import Path

API_URL = os.getenv("API_URL", "https://your-app.com")
API_KEY = os.getenv("API_KEY")

def read_file(path):
    """Read file content."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def ingest_directory(directory, file_pattern="*.md"):
    """Ingest all matching files in directory."""
    files = glob.glob(f"{directory}/**/{file_pattern}", recursive=True)
    
    for file_path in files:
        print(f"Processing: {file_path}")
        
        # Read content
        content = read_file(file_path)
        
        # Prepare payload
        payload = {
            "items": [
                {
                    "text": content,
                    "title": Path(file_path).name,
                    "type": "semantic",
                    "tags": ["backfill", "docs"]
                }
            ]
        }
        
        # Send to API
        response = requests.post(
            f"{API_URL}/ingest/batch",
            json=payload,
            headers={
                "X-API-KEY": API_KEY,
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Upserted: {len(result.get('upserted', []))}")
            print(f"  ✓ Skipped: {len(result.get('skipped', []))}")
        else:
            print(f"  ✗ Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    import sys
    directory = sys.argv[1] if len(sys.argv) > 1 else "docs"
    pattern = sys.argv[2] if len(sys.argv) > 2 else "*.md"
    
    print(f"Backfilling directory: {directory}")
    print(f"File pattern: {pattern}")
    print()
    
    ingest_directory(directory, pattern)
    print("\nBackfill complete!")
```

**Usage**:
```bash
# Backfill all markdown files
python3 backfill.py docs "*.md"

# Backfill PDFs
python3 backfill.py research "*.pdf"

# Backfill everything
python3 backfill.py data "*.*"
```

### Checking Ingestion Status

```bash
# Check recent memories
psql "$DATABASE_URL" << EOF
SELECT 
  id, 
  text_snippet,
  created_at,
  (contradictions IS NOT NULL) as has_contradictions
FROM memories 
ORDER BY created_at DESC 
LIMIT 10;
EOF

# Count entities by type
psql "$DATABASE_URL" << EOF
SELECT 
  type, 
  COUNT(*) as count
FROM entities
GROUP BY type
ORDER BY count DESC;
EOF

# Check recent entity edges
psql "$DATABASE_URL" << EOF
SELECT 
  rel_type,
  COUNT(*) as count
FROM entity_edges
GROUP BY rel_type
ORDER BY count DESC;
EOF
```

### Monitoring Refresh Jobs

```bash
# Check job queue status
psql "$DATABASE_URL" << EOF
SELECT 
  job_type,
  status,
  COUNT(*) as count,
  MIN(created_at) as oldest,
  MAX(created_at) as newest
FROM jobs
GROUP BY job_type, status
ORDER BY job_type, status;
EOF

# Check failed jobs
psql "$DATABASE_URL" << EOF
SELECT 
  id,
  job_type,
  error,
  retry_count,
  created_at
FROM jobs
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 10;
EOF
```

---

## Troubleshooting

### Issue: Analysis Timeouts

**Symptoms**: High `ingest.analysis.timeout_count` metric

**Causes**:
- Chunks too large or complex
- `INGEST_ANALYSIS_MAX_MS_PER_CHUNK` too low
- LLM API slow/unavailable

**Solutions**:
```bash
# Increase timeout
export INGEST_ANALYSIS_MAX_MS_PER_CHUNK=10000  # 10 seconds

# Check for large chunks
psql "$DATABASE_URL" << EOF
SELECT id, LENGTH(text) as text_length
FROM memories
WHERE LENGTH(text) > 10000
ORDER BY text_length DESC
LIMIT 20;
EOF

# Consider re-chunking strategy
```

### Issue: Concept Cap Reached

**Symptoms**: Many concepts filtered, policy shows `concepts_after < concepts_before`

**Causes**:
- Role policy too restrictive
- File genuinely has many concepts

**Solutions**:
```bash
# Check user's role policy
python3 -c "
from core.policy import get_ingest_policy
policy = get_ingest_policy(['pro'])  # Replace with user's roles
print(f'Max concepts: {policy.max_concepts_per_file}')
"

# Adjust policy in config/ingest_policy.yaml
vim config/ingest_policy.yaml
# Increase max_concepts_per_file for the role

# Or upgrade user role to more permissive tier
```

### Issue: Implicate Index Out of Sync

**Symptoms**: 
- Search returns outdated results
- Missing entities in search
- `implicate_refresh.failed` metric high

**Causes**:
- Refresh worker not running
- Jobs failing due to errors
- Index manually modified

**Solutions**:
```bash
# Check refresh worker status
ps aux | grep implicate_refresh

# Check failed jobs
psql "$DATABASE_URL" << EOF
SELECT error, COUNT(*) 
FROM jobs 
WHERE status = 'failed' AND job_type = 'implicate_refresh'
GROUP BY error;
EOF

# Full rebuild
./scripts/backfill_implicate.sh --mode full

# Restart refresh worker
python3 jobs/implicate_refresh.py --mode forever --poll-interval 10
```

### Issue: Frame Types Filtered Out

**Symptoms**: Expected frames missing, `frames_filtered_count > 0` in metrics

**Causes**:
- Frame type not in role's `allowed_frame_types`
- Policy too restrictive

**Solutions**:
```bash
# Check what frame types were filtered
# (Look at logs during commit)

# Edit policy to allow more frame types
vim config/ingest_policy.yaml
# Add frame types to allowed_frame_types list for the role
```

### Issue: No Contradictions Detected

**Symptoms**: `contradictions_found = 0` even though they exist

**Causes**:
- `ingest.contradictions.enabled = false`
- Role policy: `write_contradictions_to_memories = false`
- Contradiction tolerance too high

**Solutions**:
```sql
-- Check flag
SELECT * FROM feature_flags WHERE flag_name = 'ingest.contradictions.enabled';

-- Enable if needed
UPDATE feature_flags 
SET enabled = true 
WHERE flag_name = 'ingest.contradictions.enabled';
```

```bash
# Check policy
python3 -c "
from core.policy import get_ingest_policy
policy = get_ingest_policy(['general'])
print(f'Write contradictions: {policy.write_contradictions_to_memories}')
print(f'Tolerance: {policy.contradiction_tolerance}')
"

# Adjust policy or upgrade user role
```

---

## Production Deployment Checklist

### Before Enabling Analysis

- [ ] Configure `INGEST_ANALYSIS_MAX_MS_PER_CHUNK` appropriately
- [ ] Review and adjust `config/ingest_policy.yaml` for your roles
- [ ] Test with sample files in staging
- [ ] Set up metrics monitoring/alerts
- [ ] Verify database has adequate storage
- [ ] Test idempotency (re-ingest same file)

### Enabling Features (Progressive Rollout)

1. **Phase 1: Basic Analysis** (Low Risk)
   ```sql
   UPDATE feature_flags SET enabled = true WHERE flag_name = 'ingest.analysis.enabled';
   ```
   - Monitor metrics for 24-48 hours
   - Check timeout_count and error rates
   - Verify entities are being created

2. **Phase 2: Contradictions** (Medium Risk)
   ```sql
   UPDATE feature_flags SET enabled = true WHERE flag_name = 'ingest.contradictions.enabled';
   ```
   - Monitor for false positives
   - Check contradiction_found distribution
   - Verify role policies working correctly

3. **Phase 3: Auto-Refresh** (Medium Risk)
   ```sql
   UPDATE feature_flags SET enabled = true WHERE flag_name = 'ingest.implicate.refresh_enabled';
   ```
   - Start refresh worker as background service
   - Monitor job queue depth
   - Check Pinecone index size and health

### Monitoring Setup

```bash
# Set up alerts on:
- ingest.analysis.timeout_count > 100/hour
- ingest.analysis.errors_total > 50/hour  
- implicate_refresh.failed > 20/hour
- jobs.pending > 1000 (queue backup)

# Dashboard metrics:
- ingest.analysis.chunks_total (throughput)
- ingest.analysis.duration_ms (p50, p95, p99)
- ingest.commit.concepts_created (data growth)
- implicate_refresh.job_duration_seconds (performance)
```

---

## Reference

### Database Tables

- **`memories`**: Text chunks with optional contradictions JSONB field
- **`entities`**: Concepts (type='concept') and Frames (type='artifact')
- **`entity_edges`**: Relationships between entities (supports, contradicts, evidence_of)
- **`jobs`**: Background job queue for implicate refresh
- **`feature_flags`**: System-wide feature toggles

### Configuration Files

- **`config.py`**: System defaults and limits
- **`config/ingest_policy.yaml`**: Role-based policies
- **`.env`**: Environment variables (API keys, database URLs)

### Key Scripts

- **`scripts/backfill_implicate.sh`**: Build/rebuild implicate index
- **`scripts/ingest_from_files.py`**: Direct file ingestion helper
- **`scripts/make_ingest_payload.py`**: Prepare JSON payload for batch API
- **`jobs/implicate_refresh.py`**: Background refresh worker CLI

### API Endpoints

- **POST `/ingest/batch`**: Batch ingest with optional analysis
- **GET `/debug/metrics`**: System metrics for monitoring
- **GET `/debug/config`**: Current configuration values

---

## Questions?

For issues or questions, check:
1. Metrics endpoint for current system state
2. Database job queue for stuck jobs
3. Feature flags for enabled/disabled features
4. Policy file for current enforcement rules
5. Logs for detailed error messages

**Common Commands Quick Reference**:
```bash
# Enable analysis
psql "$DATABASE_URL" -c "UPDATE feature_flags SET enabled=true WHERE flag_name='ingest.analysis.enabled';"

# Rebuild index
./scripts/backfill_implicate.sh --mode full

# Start worker
python3 jobs/implicate_refresh.py --mode forever

# Check status
curl -H "X-API-KEY: $API_KEY" https://your-app.com/debug/metrics
```
