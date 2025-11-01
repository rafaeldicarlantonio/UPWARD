# Flip Sequence Guide - Quick Start

## Automated Flip Sequence

Run the interactive flip sequence script:

```bash
./scripts/flip_sequence.sh
```

This script will guide you through:
1. Checking current state
2. Enabling analysis flags
3. Ingesting test files
4. Verifying database growth
5. Starting refresh worker
6. Tuning contradiction tolerance
7. Final validation

## Manual Flip Sequence

### Phase 1: Enable Analysis

```sql
-- Enable analysis
UPDATE feature_flags SET enabled = true WHERE flag_name = 'ingest.analysis.enabled';
UPDATE feature_flags SET enabled = true WHERE flag_name = 'ingest.contradictions.enabled';
```

### Phase 2: Ingest Test Corpus

```bash
# Option A: Use Python script
python3 dev_flip_test.py

# Option B: Use API directly
curl -X POST http://localhost:8000/ingest/batch \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $X_API_KEY" \
  -d '{
    "items": [
      {
        "text": "Your test content here...",
        "type": "semantic",
        "tags": ["test"]
      }
    ]
  }'
```

### Phase 3: Verify Growth

```sql
-- Entity growth
SELECT type, COUNT(*) 
FROM entities 
WHERE created_at > NOW() - INTERVAL '10 minutes'
GROUP BY type;

-- Edge growth  
SELECT rel_type, COUNT(*) 
FROM entity_edges 
WHERE created_at > NOW() - INTERVAL '10 minutes'
GROUP BY rel_type;

-- Contradictions
SELECT COUNT(*) as memories_with_contradictions
FROM memories
WHERE contradictions IS NOT NULL
  AND jsonb_array_length(contradictions) > 0
  AND created_at > NOW() - INTERVAL '10 minutes';
```

### Phase 4: Enable Refresh

```sql
-- Enable refresh
UPDATE feature_flags SET enabled = true WHERE flag_name = 'ingest.implicate.refresh_enabled';
```

```bash
# Start worker
python3 jobs/implicate_refresh.py --mode forever --poll-interval 10
```

### Phase 5: Monitor

```bash
# Watch metrics
watch -n 5 'curl -s -H "X-API-KEY: $X_API_KEY" \
  http://localhost:8000/debug/metrics | \
  jq ".key_metrics | {
    chunks: .ingest_chunks_analyzed_total,
    enqueued: .implicate_refresh_enqueued_total,
    processed: .implicate_refresh_processed_total
  }"'
```

### Phase 6: Tune & Validate

1. **Review sample contradictions** (manually)
2. **Calculate false positive rate**
3. **Adjust tolerance** in `config/ingest_policy.yaml`
4. **Restart** application
5. **Verify** summaries look sane

## Success Criteria

✅ Entities created (concepts + frames)  
✅ Edges created (evidence_of, supports, contradicts)  
✅ Contradictions populated in memories  
✅ Refresh jobs processing successfully  
✅ False positive rate <10%  
✅ Summaries are accurate and useful  

## Rollback Procedure

If issues arise:

```sql
-- Disable all flags
UPDATE feature_flags SET enabled = false WHERE flag_name LIKE 'ingest%';

-- Or selectively disable
UPDATE feature_flags SET enabled = false WHERE flag_name = 'ingest.analysis.enabled';
```

```bash
# Stop refresh worker
pkill -f implicate_refresh.py
```

## See Also

- **Full Documentation**: `docs/ingest-analysis.md`
- **Test Results**: `FLIP_SEQUENCE_REPORT.md`
- **Metrics Guide**: `METRICS_INSTRUMENTATION.md`
- **Policy Guide**: `POLICY_IMPLEMENTATION.md`
