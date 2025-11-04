# Evaluation System Runbook

## Overview

This runbook provides operational guidance for running, monitoring, and maintaining the evaluation system. It covers suite purposes, execution procedures, failure interpretation, golden set management, and performance tuning.

**Audience**: DevOps engineers, SRE, QA engineers, ML engineers

**Prerequisites**:
- Python 3.12+
- Access to the evaluation environment
- Understanding of the system architecture

---

## Table of Contents

1. [Suite Overview](#suite-overview)
2. [Running Evaluations](#running-evaluations)
3. [Interpreting Results](#interpreting-results)
4. [Golden Set Management](#golden-set-management)
5. [Failure Debugging](#failure-debugging)
6. [Latency Tuning](#latency-tuning)
7. [Replay CLI](#replay-cli)
8. [CI Integration](#ci-integration)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## Suite Overview

### Available Suites

#### 1. Implicate Lift (`implicate_lift`)

**Purpose**: Validates that the dual-index (explicate + implicate) retrieval system successfully bridges semantic gaps that pure keyword search would miss.

**What it tests**:
- Query requires connecting concepts across multiple documents
- Implicate/graph relationships enable finding relevant sources
- Legacy keyword search fails to retrieve expected documents

**Success criteria**:
- ≥90% of expected source IDs appear in top-8 results
- Recall@8 ≥ 0.9
- P95 retrieval latency ≤ 500ms

**When to run**:
- After changes to retrieval logic
- After graph/implicate index updates
- Before releases affecting search

**Example test**: "How does attention mechanism relate to BERT?" should retrieve both `doc_transformer_003` and `doc_bert_004` via bridging.

---

#### 2. Contradictions (`contradictions`)

**Purpose**: Ensures the system detects conflicting claims and surfaces them with proper contradiction badges.

**What it tests**:
- Contradiction detection algorithm
- Badge rendering
- Evidence pairing for both sides
- Subject identification

**Success criteria**:
- ≥95% of cases detect expected contradictions
- All contradictions have both evidence IDs
- Answer payload includes badge field
- P95 packing latency ≤ 550ms

**When to run**:
- After NLP/contradiction detection changes
- After badge rendering updates
- When verifying answer quality

**Example test**: Climate data with warming vs cooling trends should surface contradiction badge with both sources.

---

#### 3. External Compare (`external_compare`)

**Purpose**: Validates that external source integration works correctly with proper policy enforcement and no data persistence.

**What it tests**:
- External source fetching and timeout handling
- Policy-compliant tie-breaking (prefer_internal, abstain)
- No ingestion of external content
- Parity between external-off and external-on modes

**Success criteria**:
- Parity rate ≥80% when externals add nothing
- decision.tiebreak matches policy when externals matter
- Zero external text persisted
- P95 compare latency ≤ 2000ms (with timeouts)

**When to run**:
- After external source integration changes
- After policy updates
- Before enabling external sources for users

**Example test**: Query with redundant external sources should show prefer_internal policy.

---

#### 4. Pareto Gate (`pareto_gate`)

**Purpose**: Verifies that hypothesis scoring and persistence thresholds work correctly, including override mechanisms.

**What it tests**:
- Hypothesis scoring algorithm
- Threshold-based persistence decisions
- Analytics/security/executive overrides
- Rejection reasons for non-persisted

**Success criteria**:
- 100% match to expected persistence
- Proposals ≥ threshold persist
- Proposals < threshold return 202 with reason
- Overrides persist regardless of score
- P95 scoring latency ≤ 200ms

**When to run**:
- After scoring algorithm changes
- After threshold adjustments
- When validating gating logic

**Example test**: Proposal with score 0.75 and threshold 0.65 should persist.

---

#### 5. Role Variants (`role_variants`)

**Purpose**: Validates that RBAC and redaction maintain correctness across permission levels.

**What it tests**:
- General role gets correct answers despite redaction
- Pro/researcher role gets full context
- Both roles retrieve same documents
- Redaction doesn't break functionality

**Success criteria**:
- General role: 100% pass with redaction applied
- Pro role: 100% pass with full context
- Both roles retrieve identical source IDs
- Contradiction detection works for both

**When to run**:
- After RBAC changes
- After redaction policy updates
- When validating access control

**Example test**: Same query for general and researcher roles retrieves same documents, but general gets redacted response text.

---

## Running Evaluations

### Running a Single Suite

#### Basic Execution

```bash
# Run implicate lift suite
python3 evals/run.py --suite implicate_lift

# Run contradictions suite
python3 evals/run.py --suite contradictions

# Run with specific config
python3 evals/run.py --config evals/config.yaml --suite pareto_gate
```

#### With CI Profile

```bash
# PR profile (subset, 15% latency slack)
python3 evals/run.py --profile pr --suite implicate_lift

# Nightly profile (full suite, 10% slack)
python3 evals/run.py --profile nightly --suite contradictions

# Full profile (all cases, 5% slack)
python3 evals/run.py --profile full --suite external_compare
```

#### With Custom Latency Slack

```bash
# 20% latency slack for slow environments
export EVAL_LATENCY_SLACK_PERCENT=20
python3 evals/run.py --suite implicate_lift

# Via command line
python3 evals/run.py --latency-slack 20 --suite pareto_gate
```

### Running Multiple Suites

```bash
# Run all suites
python3 evals/run.py --all

# Run specific testset file
python3 evals/run.py --testset evals/suites/role_variants.jsonl

# Run with suite name pattern
for suite in implicate_lift contradictions pareto_gate; do
  echo "Running $suite..."
  python3 evals/run.py --suite $suite
done
```

### Running in CI

The evaluation system integrates with GitHub Actions:

```bash
# Triggered automatically on:
# - Pull requests to main/develop
# - Push to main
# - Scheduled (nightly at 2 AM UTC)
# - Manual workflow dispatch

# View workflow:
cat .github/workflows/evals.yml
```

---

## Interpreting Results

### Dashboard Output

After running a suite, you'll see a dashboard line:

```
================================================================================
[IMPLICATE_LIFT] Quality: 95.0% | Pass: 19/20 | Latency: p50=150ms p95=450ms | ✅
================================================================================
```

**Dashboard Components**:
- **Suite Name**: In uppercase brackets
- **Quality Score**: Success rate (passed/total × 100%)
- **Pass Rate**: Explicit count of passed/total cases
- **Latency**: P50 and P95 latency in milliseconds
- **Status Indicator**:
  - ✅ (or ?) - Quality ≥ 90%
  - ⚠️ (or ??) - Quality 70-90%
  - ❌ (or ?) - Quality < 70%

### Detailed Output

Each test case shows:

```
  [1/20] implicate_001
    Running implicate_001: How does attention mechanism... [role=researcher]
    PASS - 234.5ms
    Recall@8: 1.00 (2/2 docs)
```

**Output Fields**:
- **Case ID**: Unique identifier
- **Query**: Truncated prompt
- **Role**: User role (general, researcher, etc.)
- **Status**: PASS or FAIL
- **Latency**: Total execution time
- **Metrics**: Suite-specific (Recall@8, contradictions, etc.)

### JSON Report

Detailed results are saved to JSON:

```bash
# View JSON report
cat evals/results/implicate_lift_2025-11-03.json | jq '.'

# Extract quality score
jq '.summary.quality_score' evals/results/implicate_lift_latest.json

# Find failed cases
jq '.results[] | select(.passed == false) | .case_id' evals/results/*.json
```

---

## Golden Set Management

Golden sets are curated reference test cases with stable IDs, human approval, and version tracking.

### Viewing Golden Sets

```bash
# List golden sets
ls -la evals/golden/*/golden_set.jsonl

# View specific suite
cat evals/golden/implicate_lift/golden_set.jsonl | jq '.'

# Count golden items
wc -l evals/golden/*/golden_set.jsonl
```

### Adding Golden Items

#### Interactive Mode (Recommended)

```bash
python tools/golden_add.py --interactive
```

Follow the prompts to add a new item.

#### Command Line Mode

```bash
# Add implicate lift item
python tools/golden_add.py \
  --suite implicate_lift \
  --id golden_bridge_temporal_001 \
  --query "How do 2015 AI breakthroughs connect to 2024 autonomous vehicles?" \
  --expected-sources "src_ai_2015,src_av_2024" \
  --rationale "Tests temporal bridging across 9-year gap" \
  --approved-by "your.email@example.com"

# Add contradiction item
python tools/golden_add.py \
  --suite contradictions \
  --id golden_climate_conflict_001 \
  --query "What's the consensus on sea level rise?" \
  --expected-contradiction true \
  --expected-claims "rapid_rise,slow_rise" \
  --rationale "Tests contradiction detection for conflicting predictions" \
  --approved-by "your.email@example.com"
```

### Reviewing Changes

#### Before Committing

```bash
# View diff since last commit
python tools/golden_diff.py --suite implicate_lift --verbose

# Review specific item
python tools/golden_diff.py --suite implicate_lift --id golden_bridge_temporal_001

# Generate review summary
python tools/golden_diff.py --suite implicate_lift --review
```

**Review Checklist**:
- [ ] All IDs follow `golden_*` naming convention
- [ ] All changes have human approval
- [ ] All changes have clear rationale
- [ ] Evidence IDs are valid and accessible
- [ ] Expected values match actual system behavior
- [ ] No duplicate IDs
- [ ] Version numbers are sequential

#### Approving Changes

If diff looks good:

```bash
# Add to git
git add evals/golden/implicate_lift/golden_set.jsonl

# Commit with clear message
git commit -m "Add golden item: golden_bridge_temporal_001

Tests temporal technology trend bridging across 9-year gap.

Rationale: AI breakthroughs → autonomous vehicles represents important
implicate bridging pattern with significant temporal separation.

Approved-by: your.email@example.com
Suite: implicate_lift
"

# Push
git push origin HEAD
```

### Updating Golden Items

#### When Evidence IDs Change

```bash
# Update with new evidence ID
python tools/golden_add.py \
  --suite implicate_lift \
  --id golden_bridge_temporal_001 \
  --update \
  --expected-sources "src_ai_2015_v2,src_av_2024" \
  --rationale "Updated AI source ID after index migration" \
  --approved-by "your.email@example.com"

# View what changed
python tools/golden_diff.py --suite implicate_lift --id golden_bridge_temporal_001 --verbose
```

Output shows evidence ID changes:

```
📝 Modified Items:
  ~ golden_bridge_temporal_001
    Version: 1 → 2
    Updated by: your.email@example.com
    
    Changes:
      expected_sources:
        - Removed: src_ai_2015
        + Added: src_ai_2015_v2
```

---

## Failure Debugging

### Common Failure Patterns

#### 1. Retrieval Failures (Implicate Lift)

**Symptom**: Missing expected source IDs in top-k

```
FAIL - 245ms
Recall@8: 0.50 (1/2 docs)
Error: Missing expected IDs in top-8: ['doc_bert_004']
```

**Debugging Steps**:

```bash
# 1. Check if source exists
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/sources/doc_bert_004

# 2. Test direct keyword search
curl -X POST http://localhost:8000/search \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "BERT contextual understanding", "top_k": 20}'

# 3. Check implicate index
curl -X POST http://localhost:8000/implicate/query \
  -H "X-API-Key: $API_KEY" \
  -d '{"concept_id": "transformer_architecture"}'

# 4. Replay with frozen trace for debugging
python tools/replay_cli.py --trace-id failing_case_trace_001 --offline
```

**Common Causes**:
- Document not indexed
- Graph connection missing
- Query embeddings off
- Threshold too restrictive

---

#### 2. Contradiction Detection Failures

**Symptom**: Expected contradiction not detected

```
FAIL - 512ms
Contradictions: 0, Badge: ?, Completeness: 0.00
Error: Contradictions array is empty
```

**Debugging Steps**:

```bash
# 1. Verify documents have conflicting claims
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/sources/doc_climate_warming_001
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/sources/doc_climate_cooling_002

# 2. Test contradiction detection directly
curl -X POST http://localhost:8000/detect-contradiction \
  -H "X-API-Key: $API_KEY" \
  -d '{"text_a": "temperatures rising", "text_b": "temperatures falling"}'

# 3. Check NLP model status
curl http://localhost:8000/health/nlp

# 4. Review packing latency
# If packing latency > 550ms, contradiction detection may have timed out
```

**Common Causes**:
- NLP model not loaded
- Contradiction threshold too high
- Documents don't actually conflict
- Packing timeout

---

#### 3. Latency Violations

**Symptom**: Latency budget exceeded

```
⚠️ LATENCY BUDGETS: FAILED

Violations:
  - Retrieval p95 (520ms) exceeds budget 500ms by 20ms
```

**Debugging Steps**:

```bash
# 1. Check current latency slack
echo $EVAL_LATENCY_SLACK_PERCENT

# 2. Increase slack temporarily
export EVAL_LATENCY_SLACK_PERCENT=15
python3 evals/run.py --suite implicate_lift

# 3. Profile slow query
python3 evals/run.py --suite implicate_lift --debug | grep -A5 "FAIL.*ms"

# 4. Check system resources
htop  # CPU usage
free -h  # Memory
iostat  # Disk I/O
```

**Common Causes**:
- Database slow query
- Network latency
- Cold cache
- Resource contention

See [Latency Tuning](#latency-tuning) for optimization strategies.

---

#### 4. External Compare Issues

**Symptom**: External sources not fetched or timeout

```
FAIL - 2500ms
External: ?, Policy: N/A, No-Ingestion: ?
Error: External fetch timeout
```

**Debugging Steps**:

```bash
# 1. Test external source directly
curl -I https://external-source.com/api/endpoint

# 2. Check timeout settings
grep timeout config/external.yaml

# 3. Review external compare logs
tail -f logs/external_compare.log

# 4. Test with external disabled
python3 evals/run.py --suite external_compare --disable-external
```

**Common Causes**:
- External service down
- Network timeout
- Invalid credentials
- Rate limiting

---

#### 5. Pareto Gate Scoring

**Symptom**: Unexpected persistence decision

```
FAIL - 45ms
Score: 0.62, Threshold: 0.65, Persisted: ?
Error: Persistence mismatch: expected True, got False
```

**Debugging Steps**:

```bash
# 1. Check scoring breakdown
curl -X POST http://localhost:8000/hypotheses/score \
  -H "X-API-Key: $API_KEY" \
  -d @evals/cases/pareto/case_005_at_threshold.json \
  | jq '.scoring_breakdown'

# 2. Verify threshold
curl http://localhost:8000/config/pareto | jq '.threshold'

# 3. Test with explicit signals
curl -X POST http://localhost:8000/hypotheses/propose \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "hypothesis": "Test hypothesis",
    "signals": {"quality": 0.8, "relevance": 0.7, "novelty": 0.6}
  }'
```

**Common Causes**:
- Scoring weights changed
- Signal extraction failed
- Threshold misconfigured
- Override not applied

---

#### 6. Role-Based Failures

**Symptom**: General role fails, pro role passes

```
# General role
FAIL - 234ms [role=general]
Error: Missing expected IDs

# Pro role
PASS - 238ms [role=researcher]
Recall@8: 1.00 (2/2 docs)
```

**Debugging Steps**:

```bash
# 1. Check redaction policy
curl http://localhost:8000/config/redaction | jq '.rules'

# 2. Test with both roles
curl -X POST http://localhost:8000/chat \
  -H "X-API-Key: $API_KEY" \
  -d '{"prompt": "test query", "role": "general"}'

curl -X POST http://localhost:8000/chat \
  -H "X-API-Key: $API_KEY" \
  -d '{"prompt": "test query", "role": "researcher"}'

# 3. Verify RBAC middleware
curl http://localhost:8000/health/rbac
```

**Common Causes**:
- Redaction hiding critical information
- RBAC filtering wrong documents
- Role not passed correctly
- Permission check bug

---

## Latency Tuning

### Understanding Latency Budgets

**Default Budgets** (P95):
- **Retrieval**: 500ms
- **Packing**: 550ms
- **Internal Compare**: 400ms
- **External Compare**: 2000ms (with timeouts)
- **Scoring**: 200ms (Pareto gate)

### Measuring Current Performance

```bash
# Run suite and capture metrics
python3 evals/run.py --suite implicate_lift --json-output results.json

# Extract latency stats
jq '.summary.latency_distribution' results.json

# View latency breakdown
jq '.results[] | {case: .case_id, retrieval: .retrieval_latency_ms, packing: .packing_latency_ms}' results.json
```

### Tuning Strategies

#### 1. Adjust Latency Slack

For noisy environments (CI, shared resources):

```bash
# Increase slack to 20%
export EVAL_LATENCY_SLACK_PERCENT=20

# Or via command line
python3 evals/run.py --latency-slack 20 --suite implicate_lift
```

**Slack Applied**:
- 500ms budget → 600ms with 20% slack
- 550ms budget → 660ms with 20% slack

#### 2. Profile Slow Cases

```bash
# Find slowest cases
jq '.results | sort_by(.total_latency_ms) | reverse | .[0:5] | .[] | {case: .case_id, latency: .total_latency_ms}' results.json

# Profile specific case
python3 -m cProfile -s cumtime evals/run.py --suite implicate_lift --case implicate_001
```

#### 3. Database Optimization

```sql
-- Check slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Add indices for common searches
CREATE INDEX CONCURRENTLY idx_sources_embedding ON sources USING ivfflat (embedding vector_cosine_ops);

-- Vacuum and analyze
VACUUM ANALYZE sources;
VACUUM ANALYZE graph_edges;
```

#### 4. Cache Warming

```bash
# Warm up retrieval cache before running suite
curl -X POST http://localhost:8000/admin/warm-cache

# Or run a warmup suite
python3 evals/warmup.py --suite implicate_lift
```

#### 5. Resource Scaling

```yaml
# Increase resources in docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
```

#### 6. Adjust Timeouts

```yaml
# config/timeouts.yaml
retrieval:
  max_ms: 1000  # Increase from 500ms
  
packing:
  max_ms: 800   # Increase from 550ms
  
external:
  fetch_timeout_ms: 3000  # Increase from 2000ms
```

### Monitoring Latency Over Time

```bash
# Track latency trends
jq -r '.summary | [.timestamp, .p95_latency_ms] | @tsv' results/*.json > latency_trend.tsv

# Plot with gnuplot
gnuplot -e "set terminal png; set output 'latency.png'; plot 'latency_trend.tsv' with lines"
```

---

## Replay CLI

The replay CLI allows you to reproduce evaluation runs deterministically for debugging.

### Capturing a Trace

During evaluation runs, traces are automatically captured if freezer is enabled:

```bash
# Run with trace freezing
export EVAL_FREEZE_TRACES=true
python3 evals/run.py --suite implicate_lift
```

Traces saved to: `evals/frozen_traces/`

### Replaying a Trace

#### Online Replay (with API)

```bash
# Replay specific trace
python tools/replay_cli.py --trace-id implicate_001_trace_20251103

# Replay with validation
python tools/replay_cli.py \
  --trace-id implicate_001_trace_20251103 \
  --validate-hash \
  --validate-candidates
```

**Expected Output**:
```
Loading trace: implicate_001_trace_20251103
✓ Trace loaded successfully
✓ Random seed set: 42
✓ Retrieval fixtures loaded: 15 candidates

Replaying orchestration...
✓ Trace hash matches: abc123def456
✓ Candidate IDs match: 15/15

Replay successful!
```

#### Offline Replay (no API calls)

```bash
# Replay using frozen fixtures only
python tools/replay_cli.py \
  --trace-id implicate_001_trace_20251103 \
  --offline

# Useful for:
# - Debugging without backend
# - Testing in CI
# - Analyzing past behavior
```

### Debugging with Replay

#### Scenario: Case fails intermittently

```bash
# 1. Capture trace on failure
export EVAL_FREEZE_TRACES=true
python3 evals/run.py --suite implicate_lift --case implicate_001

# 2. Replay multiple times to verify determinism
for i in {1..5}; do
  echo "Replay $i:"
  python tools/replay_cli.py --trace-id implicate_001_trace_latest --offline
done

# 3. If hashes differ, non-determinism detected
# Check for:
# - Random number generation without seeding
# - Timestamp dependencies
# - Race conditions
```

#### Scenario: Case fails after code change

```bash
# 1. Get trace from before change
git checkout main
export EVAL_FREEZE_TRACES=true
python3 evals/run.py --suite implicate_lift --case implicate_001
cp evals/frozen_traces/implicate_001_trace_latest.json /tmp/before.json

# 2. Get trace from after change
git checkout feature-branch
export EVAL_FREEZE_TRACES=true
python3 evals/run.py --suite implicate_lift --case implicate_001
cp evals/frozen_traces/implicate_001_trace_latest.json /tmp/after.json

# 3. Compare traces
diff /tmp/before.json /tmp/after.json
jq --slurp '.[0].trace.candidates == .[1].trace.candidates' /tmp/before.json /tmp/after.json

# 4. Replay both to see divergence point
python tools/replay_cli.py --trace-file /tmp/before.json --offline
python tools/replay_cli.py --trace-file /tmp/after.json --offline
```

### Trace Analysis

```bash
# View trace structure
python tools/replay_cli.py --trace-id implicate_001_trace_latest --inspect

# Extract specific fields
jq '.trace.candidates[] | {id: .source_id, score: .score}' \
  evals/frozen_traces/implicate_001_trace_latest.json

# Compare candidate rankings
jq '.trace.candidates | map(.source_id)' \
  evals/frozen_traces/*implicate_001*.json
```

---

## CI Integration

### GitHub Actions Workflow

The evaluation system runs automatically in CI:

```yaml
# .github/workflows/evals.yml

Triggers:
  - Pull request to main/develop
  - Push to main
  - Scheduled: Daily at 2 AM UTC
  - Manual: workflow_dispatch

Profiles:
  - PR: Subset of tests, 15% slack, <5min
  - Nightly: Full tests, 10% slack, <30min
  - Manual: Configurable profile and slack
```

### Viewing CI Results

```bash
# Via GitHub UI
# Go to: https://github.com/org/repo/actions

# Via gh CLI
gh run list --workflow=evals.yml
gh run view <run-id>
gh run watch  # Watch latest run

# Download artifacts
gh run download <run-id> --name eval-results
```

### Troubleshooting CI Failures

#### Scenario: PR marked red

```bash
# 1. Check which suite failed
gh run view <run-id> | grep -A5 "run-evals"

# 2. Download results
gh run download <run-id>

# 3. Review failures
jq '.results[] | select(.passed == false)' eval-results/*.json

# 4. Reproduce locally
python3 evals/run.py --profile pr --suite <failed-suite>

# 5. If latency issue, check slack
jq '.summary.latency_violations' eval-results/*.json

# 6. If functional issue, debug specific case
python3 evals/run.py --suite <suite> --case <failing-case-id>
```

#### Scenario: Nightly build unstable

Common causes:
- Latency variance in CI environment
- Flaky external dependencies
- Resource contention

**Solutions**:

```bash
# 1. Increase latency slack for nightly
# Edit .github/workflows/evals.yml:
env:
  EVAL_LATENCY_SLACK_PERCENT: 15  # Increase from 10

# 2. Mark flaky tests
# Edit evals/ci_profile.yaml:
flaky_tests:
  skip_in_pr:
    - implicate_015_known_flaky
    - external_009_external_api_unreliable

# 3. Retry failed tests
# In workflow:
- name: Run evals
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 30
    max_attempts: 3
    command: python3 evals/run.py --profile nightly
```

---

## Troubleshooting

### Environment Issues

#### Python Dependencies

```bash
# Verify Python version
python3 --version  # Should be 3.12+

# Check installed packages
pip3 list | grep -E '(requests|pyyaml|numpy)'

# Reinstall dependencies
pip3 install -r requirements.txt

# Virtual environment recommended
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Database Connection

```bash
# Test database connection
psql -h localhost -U postgres -d evals_db -c "SELECT 1"

# Check connection string
echo $DATABASE_URL

# Verify tables exist
psql $DATABASE_URL -c "\dt"
```

#### API Availability

```bash
# Health check
curl http://localhost:8000/health

# Check specific components
curl http://localhost:8000/health/retrieval
curl http://localhost:8000/health/nlp
curl http://localhost:8000/health/rbac
```

### Performance Issues

#### Slow Test Execution

```bash
# Profile test run
python3 -m cProfile -o profile.stats evals/run.py --suite implicate_lift

# Analyze profile
python3 -m pstats profile.stats
# In pstats: sort cumtime; stats 20

# Check for network issues
time curl http://localhost:8000/health

# Check for disk I/O
iostat -x 1 10
```

#### Memory Issues

```bash
# Monitor memory during run
watch -n 1 'free -h'

# Check for memory leaks
python3 -m memory_profiler evals/run.py --suite implicate_lift

# Reduce batch size if needed
# Edit evals/config.yaml:
batch_size: 5  # Reduce from 10
```

### Data Issues

#### Missing Documents

```bash
# Check document count
curl http://localhost:8000/stats/sources | jq '.count'

# Verify specific document
curl http://localhost:8000/sources/doc_bert_004

# Re-index if needed
curl -X POST http://localhost:8000/admin/reindex
```

#### Stale Indices

```bash
# Check index freshness
curl http://localhost:8000/stats/indices | jq '.last_updated'

# Force refresh
curl -X POST http://localhost:8000/admin/refresh-indices

# Rebuild implicate graph
curl -X POST http://localhost:8000/admin/rebuild-graph
```

---

## Maintenance

### Regular Tasks

#### Daily

- [ ] Review nightly build results
- [ ] Check for new failures
- [ ] Monitor latency trends

```bash
# Quick daily check
gh run list --workflow=evals.yml --limit 1
```

#### Weekly

- [ ] Review golden set changes
- [ ] Update flaky test list
- [ ] Check for outdated test cases

```bash
# Review golden changes in last week
git log --since="1 week ago" --oneline -- evals/golden/

# Check flaky test patterns
jq -r '.results[] | select(.passed == false) | .case_id' \
  results/last_7_days/*.json | sort | uniq -c | sort -rn
```

#### Monthly

- [ ] Audit all golden sets
- [ ] Review and update latency budgets
- [ ] Clean up old frozen traces
- [ ] Update documentation

```bash
# Audit golden sets
for suite in implicate_lift contradictions external_compare pareto_gate; do
  python tools/golden_diff.py --suite $suite --review
done

# Clean old traces (keep last 30 days)
find evals/frozen_traces/ -name "*.json" -mtime +30 -delete

# Generate metrics report
python3 evals/report.py --since 30d --output monthly_report.pdf
```

#### Quarterly

- [ ] Full suite review
- [ ] Update test case scenarios
- [ ] Performance baseline refresh
- [ ] Documentation updates

---

### Updating Test Cases

#### When to Update

- **API changes**: Update expected responses
- **Feature additions**: Add new test cases
- **Bug fixes**: Add regression tests
- **Performance improvements**: Tighten latency budgets

#### Process

1. **Create new test case**:
```bash
cp evals/cases/implicate/case_001.json evals/cases/implicate/case_016_new_feature.json
# Edit case_016_new_feature.json
```

2. **Run locally**:
```bash
python3 evals/run.py --suite implicate_lift --case implicate_016
```

3. **Add to suite**:
```bash
echo '{"id": "implicate_016", "file": "evals/cases/implicate/case_016_new_feature.json"}' >> evals/suites/implicate_lift.jsonl
```

4. **Verify**:
```bash
python3 evals/run.py --suite implicate_lift
```

5. **Commit**:
```bash
git add evals/cases/implicate/case_016_new_feature.json evals/suites/implicate_lift.jsonl
git commit -m "Add test case for new feature X"
```

---

### Metrics and Monitoring

#### Collect Metrics

```bash
# Export metrics to JSON
python3 evals/run.py --suite implicate_lift --json-output metrics.json

# View quality scores
jq '.summary | {suite, quality_score, passed, total}' metrics.json

# Track over time
echo "$(date -I),$(jq '.summary.quality_score' metrics.json)" >> quality_trend.csv
```

#### Dashboard Integration

If using Grafana/Prometheus:

```python
# In evals/run.py, metrics are automatically exported
from core.metrics import EvalMetrics

# Metrics available:
# - eval.suite.runs
# - eval.suite.failures
# - eval.cases.{total,passed,failed}
# - eval.latency.{retrieval,packing,compare,scoring}_ms
# - eval.suite.quality_score
```

Query in Prometheus:
```promql
# Quality score trend
eval_suite_quality_score{suite="implicate_lift"}

# Failure rate
rate(eval_suite_failures[1h])

# P95 latency
histogram_quantile(0.95, eval_latency_retrieval_ms)
```

---

## Quick Reference

### Common Commands

```bash
# Run single suite
python3 evals/run.py --suite implicate_lift

# Run with PR profile
python3 evals/run.py --profile pr --suite contradictions

# View golden diff
python tools/golden_diff.py --suite implicate_lift --verbose

# Add golden item
python tools/golden_add.py --interactive

# Replay trace
python tools/replay_cli.py --trace-id <id> --offline

# Check CI status
gh run list --workflow=evals.yml
```

### File Locations

- **Suites**: `evals/suites/*.jsonl`
- **Cases**: `evals/cases/*/*.json`
- **Golden**: `evals/golden/*/golden_set.jsonl`
- **Results**: `evals/results/*.json`
- **Traces**: `evals/frozen_traces/*.json`
- **Config**: `evals/config.yaml`, `evals/ci_profile.yaml`
- **Logs**: `logs/evals.log`

### Important URLs

- **Documentation**: `docs/`
- **CI Workflow**: `.github/workflows/evals.yml`
- **Metrics**: Prometheus/Grafana dashboards
- **API Docs**: `http://localhost:8000/docs`

---

## Support

### Getting Help

1. **Check documentation**:
   - This runbook
   - `docs/evals-curation.md`
   - `ROLE_VARIANTS_DOCUMENTATION.md`
   - Suite-specific docs (e.g., `PARETO_GATE_SUITE.md`)

2. **Search issues**:
```bash
gh issue list --label evals
gh issue view <issue-number>
```

3. **Ask the team**:
   - Slack: `#evals` channel
   - Email: evals-team@example.com

### Reporting Issues

When reporting evaluation failures:

1. **Include**:
   - Suite name and profile
   - Failed case IDs
   - JSON output (if available)
   - Environment details (local, CI, production)

2. **Attach**:
   - Relevant logs
   - Frozen traces
   - Screenshots of dashboard output

3. **Steps to reproduce**:
```bash
python3 evals/run.py --suite <suite> --case <case_id>
```

---

## Appendix

### Exit Codes

- **0**: All tests passed
- **1**: One or more tests failed
- **2**: Configuration error
- **3**: Runtime error

### Environment Variables

- `BASE_URL`: API base URL (default: `http://localhost:8000`)
- `X_API_KEY`: API key for authentication
- `EVAL_LATENCY_SLACK_PERCENT`: Latency slack percentage (default: `10`)
- `EVAL_FREEZE_TRACES`: Enable trace freezing (default: `false`)
- `EVAL_CI_PROFILE`: CI profile name (default: `pr`)

### Glossary

- **Implicate**: Semantic/graph-based connections
- **Explicate**: Keyword/literal matches
- **Recall@k**: Fraction of expected items in top-k results
- **Packing**: Assembly of final answer from retrieved chunks
- **Contradiction Badge**: UI indicator for conflicting claims
- **Golden Set**: Curated reference test cases
- **Pareto Gate**: Scoring threshold for hypothesis persistence
- **Trace**: Frozen execution state for replay

---

*Last Updated: 2025-11-03*  
*Version: 1.0*  
*Maintainer: Evals Team*
