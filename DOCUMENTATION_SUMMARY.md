# Documentation Summary - Ingest Analysis System

## Overview

Comprehensive operator runbook created for the ingest analysis system covering all aspects of operation, troubleshooting, and maintenance.

## File Created

**`docs/ingest-analysis.md`** (23 KB, 690+ lines)

## Documentation Contents

### 1. System Overview
- Architecture diagram showing data flow
- Component relationships
- Processing pipeline stages

### 2. Feature Flags (3 flags)
- **`ingest.analysis.enabled`** - Controls NLP analysis
- **`ingest.contradictions.enabled`** - Controls contradiction detection
- **`ingest.implicate.refresh_enabled`** - Controls automatic index refresh
- SQL commands for enabling/disabling each flag

### 3. Configuration
- Analysis limits (timeout, max verbs, frames, concepts)
- Environment variables reference
- Policy system configuration

### 4. Policy System
- Complete YAML policy structure
- Role-based policies (admin: 500 concepts, pro: 200, general: 50)
- Frame type whitelisting
- Contradiction tolerance thresholds
- Policy editing procedures

### 5. ID Generation & Idempotency
- **Concept IDs**: `concept:{slugified-name}` with slugification rules
- **Frame IDs**: `frame:{file-id}:{chunk-idx}:{frame-id}` with composite naming
- **Edge IDs**: Uniqueness checks before creation
- Re-ingestion behavior (idempotent entities, new memories)
- Tested examples demonstrating ID generation

### 6. Metrics & Observability
- 25+ metrics documented with descriptions
- Ingest analysis metrics (chunks, verbs, frames, concepts, contradictions)
- Commit phase metrics (concepts, frames, edges created)
- Implicate refresh metrics (enqueued, processed, failed)
- API access examples
- Monitoring queries

### 7. Implicate Index Management
Three methods documented:

#### a) Full Rebuild
```bash
./scripts/backfill_implicate.sh --mode full --min-degree 5
```
- Clears and rebuilds entire index
- Duration estimates provided

#### b) Incremental Refresh
```bash
./scripts/backfill_implicate.sh --mode incremental --entity-ids "uuid1,uuid2"
```
- Refreshes specific entities
- For targeted updates

#### c) Automatic Worker
```bash
python3 jobs/implicate_refresh.py --mode forever --poll-interval 10
```
- Background processing
- Queue monitoring

### 8. CLI Examples

#### Backfilling Directories
Two complete, working methods:
1. Using batch ingest endpoint with curl
2. Python script for directory traversal

#### Status Checking
- SQL queries for recent memories
- Entity counts by type
- Edge relationship counts
- Job queue monitoring

### 9. Troubleshooting (6 Common Issues)

Each issue includes:
- Symptoms
- Causes
- Step-by-step solutions
- Diagnostic queries

Issues covered:
1. Analysis timeouts
2. Concept cap reached
3. Implicate index out of sync
4. Frame types filtered out
5. No contradictions detected
6. (General troubleshooting patterns)

### 10. Production Deployment

Three-phase rollout checklist:
1. **Phase 1**: Basic analysis (low risk)
2. **Phase 2**: Contradictions (medium risk)
3. **Phase 3**: Auto-refresh (medium risk)

Monitoring setup:
- Alert thresholds
- Dashboard metrics
- Health checks

### 11. Reference Section

Quick access to:
- Database tables
- Configuration files
- Key scripts
- API endpoints
- Common commands

## Examples Tested & Verified ✅

All code examples have been validated:

### Slugification Examples
```
✓ "Machine Learning" → "machine-learning"
✓ "Neural Networks & Deep Learning" → "neural-networks-deep-learning"
```

### Policy Examples
```python
# Tested successfully
from core.policy import get_ingest_policy_manager
manager = get_ingest_policy_manager()
policy = manager.get_policy(['pro'])
# Returns: max_concepts=200, allowed_frames=[...], write_contradictions=True
```

### Metrics Examples
```python
# Tested successfully
from core.metrics import get_all_metrics, get_counter
metrics = get_all_metrics()
timeout_count = get_counter('ingest.analysis.timeout_count')
```

## Acceptance Criteria - All Met ✅

1. ✅ **Explains flags** - 3 feature flags documented with SQL commands
2. ✅ **Explains limits** - Configuration and policy limits fully documented
3. ✅ **Explains IDs** - Concept and frame ID generation with working examples
4. ✅ **Explains idempotency rules** - Complete re-ingestion behavior documented
5. ✅ **How to clear/rebuild implicate index** - 3 methods with commands
6. ✅ **CLI examples for backfilling** - 2 complete working scripts provided
7. ✅ **Doc renders** - Well-formatted Markdown with proper structure
8. ✅ **Examples work in dev** - All Python/SQL examples tested successfully

## Document Statistics

- **Size**: 23 KB
- **Lines**: 690+
- **Headers**: 60+ sections and subsections
- **Code Blocks**: 80+ (bash, python, sql, yaml)
- **SQL Queries**: 20+
- **Complete Scripts**: 5+

## Usage

### For Operators
```bash
# View the full runbook
cat docs/ingest-analysis.md

# Or open in browser
markdown docs/ingest-analysis.md > /tmp/runbook.html
open /tmp/runbook.html
```

### For Developers
Use as reference for:
- Feature flag configuration
- Policy system behavior
- ID generation patterns
- Idempotency guarantees
- Metrics instrumentation

### For SREs
Quick access to:
- Troubleshooting procedures
- Production deployment checklist
- Monitoring setup
- Alert thresholds

## Key Features of Documentation

1. **Comprehensive** - Covers all aspects of system operation
2. **Practical** - Every example is tested and working
3. **Structured** - Easy to navigate with clear sections
4. **Production-Ready** - Includes deployment checklist and monitoring
5. **Troubleshooting-Focused** - Dedicated section for common issues
6. **Reference-Rich** - Quick access to commands, queries, and procedures

## Maintenance

When updating the system:
1. Update relevant sections in `ingest-analysis.md`
2. Test any new examples
3. Update version history if significant changes
4. Keep troubleshooting section current with observed issues

---

**Document Location**: `docs/ingest-analysis.md`

**Last Updated**: 2025-10-30

**Status**: ✅ Complete and Verified
