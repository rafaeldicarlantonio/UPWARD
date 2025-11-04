# Performance Flags & Budgets - Quick Reference

**Status**: ✅ Implemented and Tested  
**Tests**: 31/31 passing  
**Files**: `config.py`, `feature_flags.py`, `api/debug.py`, `tests/perf/test_flags.py`

---

## TL;DR

All performance flags and budgets are exposed in `/debug/config` with validation and comprehensive unit tests.

```bash
# View all performance configuration
curl http://localhost:8000/debug/config | jq '.performance'

# Get just the flags
curl http://localhost:8000/debug/config | jq '.performance.flags'

# Get just the budgets
curl http://localhost:8000/debug/config | jq '.performance.budgets'
```

---

## Available Flags

### Boolean Flags (True/False)

| Flag | Default | Description |
|------|---------|-------------|
| `PERF_RETRIEVAL_PARALLEL` | `true` | Enable parallel retrieval from Pinecone and pgvector |
| `PERF_REVIEWER_ENABLED` | `true` | Enable reviewer call for answer quality |
| `PERF_PGVECTOR_ENABLED` | `true` | Enable pgvector fallback when Pinecone fails |
| `PERF_FALLBACKS_ENABLED` | `true` | Enable all fallback mechanisms |

### Budget Flags (Milliseconds)

| Flag | Default | Range | Description |
|------|---------|-------|-------------|
| `PERF_RETRIEVAL_TIMEOUT_MS` | `450` | 1-1000 | Timeout for retrieval phase |
| `PERF_GRAPH_TIMEOUT_MS` | `150` | 1-300 | Timeout for graph expansion |
| `PERF_COMPARE_TIMEOUT_MS` | `400` | 1-1000 | Timeout for comparison operations |
| `PERF_REVIEWER_BUDGET_MS` | `500` | 1-1000 | Budget for reviewer call |

---

## Configuration

### Environment Variables

Set via environment variables (takes precedence over defaults):

```bash
# Boolean flags (case-insensitive)
export PERF_RETRIEVAL_PARALLEL=true
export PERF_REVIEWER_ENABLED=false
export PERF_PGVECTOR_ENABLED=true
export PERF_FALLBACKS_ENABLED=true

# Budget flags (integers only)
export PERF_RETRIEVAL_TIMEOUT_MS=600
export PERF_GRAPH_TIMEOUT_MS=200
export PERF_COMPARE_TIMEOUT_MS=500
export PERF_REVIEWER_BUDGET_MS=700
```

### In Python Code

```python
from config import load_config

# Load full configuration
cfg = load_config()

# Access flags
parallel_enabled = cfg["PERF_RETRIEVAL_PARALLEL"]
retrieval_timeout = cfg["PERF_RETRIEVAL_TIMEOUT_MS"]

# Get structured performance config
from feature_flags import get_perf_flags

perf = get_perf_flags()
# Returns: {"flags": {...}, "budgets": {...}}
```

---

## API Response Format

`GET /debug/config` returns:

```json
{
  "performance": {
    "flags": {
      "retrieval_parallel": true,
      "reviewer_enabled": true,
      "pgvector_enabled": true,
      "fallbacks_enabled": true
    },
    "budgets": {
      "retrieval_timeout_ms": 450,
      "graph_timeout_ms": 150,
      "compare_timeout_ms": 400,
      "reviewer_budget_ms": 500
    },
    "raw_config": {
      "PERF_RETRIEVAL_PARALLEL": true,
      "PERF_RETRIEVAL_TIMEOUT_MS": 450,
      ...
    }
  },
  "resource_limits": {...},
  "feature_flags": {...},
  "config": {...},
  "timestamp": 1730736000.0
}
```

---

## Validation

### Automatic Validation

All flags are validated when `load_config()` is called:

- **Type checking**: Booleans must be bool, timeouts must be int
- **Range checking**: Timeouts must be positive (> 0)
- **Relationship checking**: Parallel retrieval requires pgvector enabled

### Error Examples

```bash
# Invalid timeout (not an integer)
export PERF_RETRIEVAL_TIMEOUT_MS=abc
# RuntimeError: PERF_RETRIEVAL_TIMEOUT_MS must be a positive integer

# Negative timeout
export PERF_GRAPH_TIMEOUT_MS=-100
# RuntimeError: PERF_GRAPH_TIMEOUT_MS must be a positive integer

# Zero timeout
export PERF_REVIEWER_BUDGET_MS=0
# RuntimeError: PERF_REVIEWER_BUDGET_MS must be a positive integer
```

---

## Common Patterns

### Disable Reviewer for Speed

```bash
export PERF_REVIEWER_ENABLED=false
```

### Aggressive Timeouts

```bash
export PERF_RETRIEVAL_TIMEOUT_MS=300
export PERF_GRAPH_TIMEOUT_MS=100
export PERF_COMPARE_TIMEOUT_MS=300
export PERF_REVIEWER_BUDGET_MS=400
```

### Conservative Timeouts (Development)

```bash
export PERF_RETRIEVAL_TIMEOUT_MS=1000
export PERF_GRAPH_TIMEOUT_MS=300
export PERF_COMPARE_TIMEOUT_MS=800
export PERF_REVIEWER_BUDGET_MS=1000
```

### Disable All Fallbacks

```bash
export PERF_FALLBACKS_ENABLED=false
export PERF_PGVECTOR_ENABLED=false
```

---

## Monitoring

### Check Current Configuration

```bash
# Quick check
curl -s http://localhost:8000/debug/config | jq '.performance.flags'

# View all budgets
curl -s http://localhost:8000/debug/config | jq '.performance.budgets'

# Check if reviewer is enabled
curl -s http://localhost:8000/debug/config | jq '.performance.flags.reviewer_enabled'
```

### Check Against Metrics

```bash
# Get current p95 latencies
curl -s http://localhost:8000/debug/metrics/summary

# Compare budgets vs actual
curl -s http://localhost:8000/debug/config | jq '.performance.budgets.retrieval_timeout_ms'
curl -s http://localhost:8000/debug/metrics/summary | jq '.retrieval.p95'
```

---

## Testing

### Run All Flag Tests

```bash
# All 31 tests
python3 -m unittest tests.perf.test_flags -v

# Specific test class
python3 -m unittest tests.perf.test_flags.TestPerformanceFlagDefaults -v

# Specific test
python3 -m unittest tests.perf.test_flags.TestPerformanceFlagDefaults.test_retrieval_timeout_default
```

### Test Scenarios Covered

- ✅ Default values
- ✅ Type validation (bool/int)
- ✅ Range validation (positive timeouts)
- ✅ Environment variable overrides
- ✅ Invalid values raise clear errors
- ✅ Debug endpoint exposure
- ✅ Relationship constraints
- ✅ Sensitive data redaction

---

## Troubleshooting

### Flag Not Taking Effect

**Problem**: Changed environment variable but flag still shows old value

**Solution**:
```bash
# 1. Verify environment variable is set
echo $PERF_RETRIEVAL_TIMEOUT_MS

# 2. Restart application
# 3. Verify via API
curl -s http://localhost:8000/debug/config | jq '.performance.budgets.retrieval_timeout_ms'
```

### Config Load Error

**Problem**: `RuntimeError: Missing required environment variables`

**Solution**: The error is about required variables (API keys, etc.), not performance flags. Check `env.sample` for required variables:
```bash
# Required for config load
export OPENAI_API_KEY=your_key
export SUPABASE_URL=your_url
export PINECONE_API_KEY=your_key
# ... etc
```

### Validation Error

**Problem**: `RuntimeError: PERF_RETRIEVAL_TIMEOUT_MS must be a positive integer`

**Solution**: Check your value:
```bash
# Bad values
export PERF_RETRIEVAL_TIMEOUT_MS=abc  # Not an integer
export PERF_RETRIEVAL_TIMEOUT_MS=-100 # Negative
export PERF_RETRIEVAL_TIMEOUT_MS=0    # Zero

# Good value
export PERF_RETRIEVAL_TIMEOUT_MS=600  # Positive integer
```

---

## Best Practices

### 1. Start with Defaults

The defaults are tuned for production use. Only override if you have specific needs.

### 2. Monitor Before Tuning

Check actual metrics before adjusting budgets:
```bash
curl -s http://localhost:8000/debug/metrics/summary | jq '.'
```

### 3. Test Changes

Use the smoke test tool to verify changes:
```bash
python3 tools/load_smoke.py --requests 10
```

### 4. Document Overrides

If you override defaults in production, document why:
```bash
# Increased for slow network environment
export PERF_RETRIEVAL_TIMEOUT_MS=800
```

### 5. Use Budgets with Gates

Combine flags with latency gates (see `evals/latency.py`) for CI enforcement.

---

## Related Documentation

- **Latency Gates**: `LATENCY_GATES_QUICKSTART.md`
- **Resource Limits**: `RESOURCE_LIMITS_QUICKSTART.md`
- **Load Testing**: `LOAD_SMOKE_QUICKSTART.md`
- **Operator Runbook**: `docs/perf-and-fallbacks.md`

---

## Acceptance Criteria

All acceptance criteria met:

- ✅ `perf.retrieval.parallel=true` flag present and exposed
- ✅ `perf.retrieval.timeout_ms=[450]` budget present and exposed
- ✅ `perf.graph.timeout_ms=[150]` budget present and exposed
- ✅ `perf.pgvector.enabled=true` flag present and exposed
- ✅ `perf.fallbacks.enabled=true` flag present and exposed
- ✅ `perf.reviewer.enabled=true` flag present and exposed
- ✅ `perf.reviewer.budget_ms=[500]` budget present and exposed
- ✅ `/debug/config` endpoint shows all flags
- ✅ Defaults validated (31 tests passing)
- ✅ Bad environment variables throw clear errors

---

## Summary

Performance flags and budgets provide fine-grained control over system behavior:

- **8 flags** total (4 boolean, 4 budget)
- **31 unit tests** all passing
- **Structured API** response in `/debug/config`
- **Automatic validation** with clear error messages
- **Environment variable** override support
- **Type-safe** and range-checked

Use these flags to tune performance, disable features, or adjust budgets based on your deployment environment and requirements.
