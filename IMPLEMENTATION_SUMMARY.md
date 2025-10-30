# Implementation Summary: Ingest Pipeline Analyze and Commit Phases

## Overview
Implemented the analyze_chunk and commit phase for the ingestion pipeline, including comprehensive integration tests.

## Files Modified/Created

### 1. `ingest/pipeline.py` (Modified)
Added the following components:

#### Data Classes
- **`AnalysisContext`**: Context for chunk analysis with optional backend and existing concepts
- **`AnalysisLimits`**: Limits for analysis (max_ms_per_chunk, max_verbs, max_frames, max_concepts)
- **`AnalysisResult`**: Results container with predicates, frames, concepts, and contradictions

#### Main Function: `analyze_chunk(text, ctx, limits)`
Wires together the NLP pipeline:
1. **Tokenize** → Extract tokens using the tokenization backend
2. **Verbs** → Extract predicate frames from text
3. **Frames** → Build event frames from predicates
4. **Concepts** → Suggest concepts based on frames and tokens
5. **Contradictions** → Detect contradictory claims

### 2. `ingest/commit.py` (Created)
Implements the commit phase with the following functionality:

#### Data Classes
- **`CommitResult`**: Results from committing analysis (entity IDs, edge IDs, jobs enqueued, errors)

#### Core Functions

##### Entity Management
- **`upsert_concept_entity(sb, name)`**: Upserts concept entities (type='concept')
- **`upsert_frame_entity(sb, frame_id, frame_type)`**: Upserts frame entities (type='artifact')

##### Edge Creation
- **`create_entity_edge(sb, from_id, to_id, rel_type, weight, meta)`**: Creates entity_edges with support for:
  - `evidence_of`: Frames provide evidence for concepts
  - `supports`: Positive relationships between entities
  - `contradicts`: Negative/contradictory relationships

##### Memory Updates
- **`update_memory_contradictions(sb, memory_id, contradictions)`**: Appends contradictions to the memory row's contradictions field

##### Job Queue
- **`enqueue_implicate_refresh(sb, entity_ids)`**: Enqueues implicate_refresh jobs when the feature flag `ingest.implicate.refresh_enabled` is enabled

#### Main Function: `commit_analysis(sb, analysis, memory_id)`
Orchestrates the commit process:
1. Upserts concept entities from suggested concepts
2. Upserts frame entities (stored as artifact type)
3. Creates entity_edges:
   - Frames `evidence_of` concepts (based on frame roles)
   - `supports`/`contradicts` edges between entities (based on predicate polarity)
4. Updates memory contradictions field
5. Enqueues implicate_refresh jobs for changed entities (when flag enabled)

### 3. `tests/ingest/test_pipeline_commit.py` (Created)
Comprehensive integration test suite with 20 tests:

#### Test Classes

##### `TestAnalyzeChunk` (5 tests)
- Basic chunk analysis
- Predicate extraction
- Frame extraction
- Concept suggestion
- Limit enforcement

##### `TestCommitAnalysis` (7 tests)
- Concept entity creation
- Frame entity creation
- Evidence edge creation (frames → concepts)
- Support/contradict edge creation
- Memory contradiction updates
- Job enqueueing (enabled/disabled)

##### `TestIntegrationEndToEnd` (2 tests)
- Complete analyze → commit pipeline
- Complex document with contradictions

##### `TestHelperFunctions` (6 tests)
- Individual function testing for all commit helpers
- Feature flag behavior verification

## Key Features

### 1. Entity Management
- Automatically upserts concept entities (type='concept')
- Creates frame entities as artifacts (type='artifact')
- Handles duplicate detection via name+type unique constraint

### 2. Knowledge Graph Construction
- Creates `evidence_of` edges: frames → concepts
- Creates `supports` edges: positive predicates
- Creates `contradicts` edges: negative predicates
- Stores edge metadata (roles, verbs)

### 3. Contradiction Tracking
- Detects contradictions in predicates
- Stores contradictions in memory.contradictions JSONB field
- Includes subject, claims, and evidence IDs

### 4. Incremental Index Refresh
- Enqueues implicate_refresh jobs for changed entities
- Respects feature flag `ingest.implicate.refresh_enabled`
- Placeholder implementation for job queue (ready for production queue integration)

## Configuration

### Feature Flags
- `ingest.implicate.refresh_enabled`: Controls whether implicate_refresh jobs are enqueued (default: False)

### Environment Variables (from config.py)
- `INGEST_ANALYSIS_ENABLED`: Enable/disable analysis phase
- `INGEST_ANALYSIS_MAX_MS_PER_CHUNK`: Time budget per chunk (default: 40ms)
- `INGEST_ANALYSIS_MAX_VERBS`: Max predicates to extract (default: 20)
- `INGEST_ANALYSIS_MAX_FRAMES`: Max event frames (default: 10)
- `INGEST_ANALYSIS_MAX_CONCEPTS`: Max concepts to suggest (default: 10)
- `INGEST_CONTRADICTIONS_ENABLED`: Enable contradiction detection (default: False)

## Testing

All 20 tests pass successfully:
```bash
cd /workspace && export PYTHONPATH=/workspace:$PYTHONPATH && pytest tests/ingest/test_pipeline_commit.py -v
```

### Test Coverage
- ✅ Analyze chunk with various limits
- ✅ Commit creates entities and edges
- ✅ Contradiction detection and storage
- ✅ Feature flag behavior
- ✅ End-to-end integration
- ✅ Error handling

## Database Schema Integration

### Tables Used
- **`entities`**: Stores concepts and frames
- **`entity_edges`**: Stores relationships with rel_types:
  - `evidence_of`
  - `supports`
  - `contradicts`
  - (existing: `affiliated_with`, `authored`, `cites`, `references`, `mentions`, `frames`, `derived_from`)
- **`memories`**: Updated with contradictions JSONB field
- **`jobs`**: (Optional) Job queue for implicate_refresh

### Relationship Types
All edge types comply with the existing schema check constraint in `040_knowledge_graph.sql`.

## Next Steps / Future Enhancements

1. **Job Queue Integration**: Replace placeholder with production-ready job queue (Celery, RQ, or dedicated table)
2. **Batch Processing**: Add batch commit support for multiple chunks
3. **Performance Optimization**: Add caching for entity lookups
4. **Metrics**: Add instrumentation for analysis/commit performance
5. **Rollback**: Add transaction support for atomic commits

## Usage Example

```python
from ingest.pipeline import analyze_chunk, AnalysisContext, AnalysisLimits
from ingest.commit import commit_analysis
from vendors.supabase_client import get_client

# Analyze a chunk
text = "Neural networks support deep learning concepts."
analysis = analyze_chunk(
    text,
    ctx=AnalysisContext(backend=None),  # Uses default backend
    limits=AnalysisLimits(
        max_verbs=20,
        max_frames=10,
        max_concepts=10,
    )
)

# Commit the analysis
sb = get_client()
result = commit_analysis(
    sb,
    analysis,
    memory_id="memory-123"
)

print(f"Created {len(result.concept_entity_ids)} concepts")
print(f"Created {len(result.frame_entity_ids)} frames")
print(f"Created {len(result.edge_ids)} edges")
print(f"Enqueued {result.jobs_enqueued} jobs")
```

## Acceptance Criteria Met

✅ **Wire NLP Pipeline**: tokenize → verbs → frames → concepts → contradictions in single `analyze_chunk` function

✅ **Upsert Entities**: Creates concept entities (type='concept') and frame entities (type='artifact')

✅ **Create Edges**: 
  - Frames `evidence_of` concepts
  - `supports`/`contradicts` edges between entities

✅ **Update Contradictions**: Appends to memories.contradictions field

✅ **Enqueue Jobs**: Enqueues implicate_refresh when `ingest.implicate.refresh_enabled=true`

✅ **Integration Tests**: Comprehensive test suite with fixtures validating expected entities/edges, memory updates, and job enqueueing
