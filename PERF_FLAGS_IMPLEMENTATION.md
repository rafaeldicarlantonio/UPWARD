# Performance Flags & Budgets - Implementation Summary

**Status**: ✅ Complete  
**Date**: 2025-11-04  
**Tests**: 31/31 passing  

---

## Overview

Implemented comprehensive performance flags and budgets system with:
- ✅ All 8 requested flags present in config
- ✅ Structured exposure via `/debug/config` endpoint
- ✅ Type and range validation with clear error messages
- ✅ 31 unit tests covering all scenarios
- ✅ Complete documentation

---

## Implementation Details

### 1. Configuration (`config.py`)

**Status**: ✅ Already present

All performance flags were already defined in `config.DEFAULTS`:

```python
DEFAULTS = {
    # Performance flags (boolean)
    "PERF_RETRIEVAL_PARALLEL": True,
    "PERF_REVIEWER_ENABLED": True,
    "PERF_PGVECTOR_ENABLED": True,
    "PERF_FALLBACKS_ENABLED": True,
    
    # Performance budgets (milliseconds)
    "PERF_RETRIEVAL_TIMEOUT_MS": 450,
    "PERF_GRAPH_TIMEOUT_MS": 150,
    "PERF_COMPARE_TIMEOUT_MS": 400,
    "PERF_REVIEWER_BUDGET_MS": 500,
}
```

Validation functions:
- `validate_perf_config()` - Validates ranges and relationships
- `get_debug_config()` - Returns sanitized config for API exposure

### 2. Feature Flags Module (`feature_flags.py`)

**Status**: ✅ Enhanced (+66 lines)

Added `get_perf_flags()` function for structured access:

```python
def get_perf_flags() -> Dict[str, Any]:
    """
    Get all performance flags and budgets from config.
    
    Returns:
        {
            "flags": {
                "retrieval_parallel": True,
                "reviewer_enabled": True,
                "pgvector_enabled": True,
                "fallbacks_enabled": True
            },
            "budgets": {
                "retrieval_timeout_ms": 450,
                "graph_timeout_ms": 150,
                "compare_timeout_ms": 400,
                "reviewer_budget_ms": 500
            }
        }
    """
```

**Key Features**:
- Transforms raw config keys to friendly names
- Separates boolean flags from numeric budgets
- Graceful fallback to defaults on error
- No external dependencies (imports config internally)

### 3. Debug API Endpoint (`api/debug.py`)

**Status**: ✅ Enhanced (+27 lines)

Updated `/debug/config` endpoint to return structured response:

```python
@router.get("/debug/config")
def get_debug_config() -> Dict[str, Any]:
    """Returns configuration with special sections."""
    return {
        "performance": {
            "flags": {...},      # Boolean flags
            "budgets": {...},    # Timeout budgets
            "raw_config": {...}  # Raw PERF_* keys
        },
        "resource_limits": {...},  # LIMITS_* keys
        "feature_flags": {...},    # Database flags
        "config": {...},           # Other config
        "timestamp": ...
    }
```

**Key Features**:
- Separates PERF_* and LIMITS_* from general config
- Uses `get_perf_flags()` for structured flags/budgets
- Maintains sensitive data redaction (API keys)
- Backward compatible (still returns full config)

### 4. Unit Tests (`tests/perf/test_flags.py`)

**Status**: ✅ Already comprehensive

31 tests covering:

1. **Default Values** (8 tests)
   - Verify each flag has correct default
   - Verify correct types (bool/int)

2. **Type Validation** (7 tests)
   - Boolean parsing (true/false/1/0)
   - Integer parsing
   - Invalid values raise errors
   - Negative values raise errors
   - Zero values raise errors

3. **All Flags Present** (3 tests)
   - All 8 flags in config
   - Correct types for all flags
   - Sensible default ranges

4. **Config Validation** (4 tests)
   - Valid config passes
   - Excessive timeouts caught
   - Graph timeout too high caught
   - Parallel retrieval without pgvector caught

5. **Debug Endpoint** (2 tests)
   - Sensitive data redacted
   - Performance flags visible

6. **Environment Overrides** (3 tests)
   - Timeout overrides work
   - Boolean overrides work
   - All timeouts overridable

7. **Budget Ranges** (2 tests)
   - Budgets sensibly ordered
   - Total latency reasonable

8. **Acceptance Criteria** (2 tests)
   - Defaults validated
   - Debug config shows keys

**Test Results**:
```
Ran 31 tests in 0.003s
OK
```

All tests pass with 100% success rate.

---

## Acceptance Criteria

### Original Requirements

From user request:
> Goals: perf.retrieval.parallel=true, perf.retrieval.timeout_ms=[450], 
> perf.graph.timeout_ms=[150], perf.pgvector.enabled=true, 
> perf.fallbacks.enabled=true, perf.reviewer.enabled=true, 
> perf.reviewer.budget_ms=[500]. /debug/config must show them.
> Acceptance: defaults validated; bad envs throw clear errors.

### Verification

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `perf.retrieval.parallel=true` | ✅ | `PERF_RETRIEVAL_PARALLEL: True` in config.py |
| `perf.retrieval.timeout_ms=[450]` | ✅ | `PERF_RETRIEVAL_TIMEOUT_MS: 450` in config.py |
| `perf.graph.timeout_ms=[150]` | ✅ | `PERF_GRAPH_TIMEOUT_MS: 150` in config.py |
| `perf.pgvector.enabled=true` | ✅ | `PERF_PGVECTOR_ENABLED: True` in config.py |
| `perf.fallbacks.enabled=true` | ✅ | `PERF_FALLBACKS_ENABLED: True` in config.py |
| `perf.reviewer.enabled=true` | ✅ | `PERF_REVIEWER_ENABLED: True` in config.py |
| `perf.reviewer.budget_ms=[500]` | ✅ | `PERF_REVIEWER_BUDGET_MS: 500` in config.py |
| `/debug/config` shows them | ✅ | Returns `performance` section with flags and budgets |
| Defaults validated | ✅ | 31 tests verify defaults |
| Bad envs throw clear errors | ✅ | Tests verify RuntimeError with clear messages |

---

## API Documentation

### Endpoint: `GET /debug/config`

Returns complete configuration with special sections for performance.

**Request**:
```bash
curl http://localhost:8000/debug/config
```

**Response Structure**:
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
      "PERF_GRAPH_TIMEOUT_MS": 150,
      "PERF_COMPARE_TIMEOUT_MS": 400,
      "PERF_REVIEWER_ENABLED": true,
      "PERF_REVIEWER_BUDGET_MS": 500,
      "PERF_PGVECTOR_ENABLED": true,
      "PERF_FALLBACKS_ENABLED": true
    }
  },
  "resource_limits": {
    "LIMITS_ENABLED": true,
    "LIMITS_MAX_CONCURRENT_PER_USER": 3,
    "LIMITS_MAX_QUEUE_SIZE_PER_USER": 10,
    "LIMITS_MAX_CONCURRENT_GLOBAL": 100,
    "LIMITS_MAX_QUEUE_SIZE_GLOBAL": 500,
    "LIMITS_RETRY_AFTER_SECONDS": 5,
    "LIMITS_QUEUE_TIMEOUT_SECONDS": 30.0,
    "LIMITS_OVERLOAD_POLICY": "drop_newest"
  },
  "feature_flags": {
    "retrieval.dual_index": false,
    "retrieval.liftscore": false,
    "external_compare": false,
    ...
  },
  "config": {
    "OPENAI_API_KEY": "***REDACTED***",
    "PINECONE_API_KEY": "***REDACTED***",
    "SUPABASE_URL": "http://...",
    "EMBED_DIM": 1536,
    ...
  },
  "timestamp": 1730736000.0
}
```

**Query Examples**:
```bash
# Get just performance section
curl -s http://localhost:8000/debug/config | jq '.performance'

# Get just flags
curl -s http://localhost:8000/debug/config | jq '.performance.flags'

# Get just budgets
curl -s http://localhost:8000/debug/config | jq '.performance.budgets'

# Check specific flag
curl -s http://localhost:8000/debug/config | jq '.performance.flags.reviewer_enabled'

# Check specific budget
curl -s http://localhost:8000/debug/config | jq '.performance.budgets.retrieval_timeout_ms'
```

---

## Validation & Error Handling

### Type Validation

**Boolean Flags**:
- Valid: `"true"`, `"false"`, `"1"`, `"0"`, `"yes"`, `"no"`, `"on"`, `"off"`
- Case-insensitive
- Converted to Python `bool`

**Budget Flags**:
- Must be valid integers
- Must be positive (> 0)
- Range constraints enforced by validation

### Error Examples

**Invalid Type**:
```bash
export PERF_RETRIEVAL_TIMEOUT_MS=abc
python3 -c "from config import load_config; load_config()"
# RuntimeError: PERF_RETRIEVAL_TIMEOUT_MS must be a positive integer
```

**Negative Value**:
```bash
export PERF_GRAPH_TIMEOUT_MS=-100
python3 -c "from config import load_config; load_config()"
# RuntimeError: PERF_GRAPH_TIMEOUT_MS must be a positive integer
```

**Zero Value**:
```bash
export PERF_REVIEWER_BUDGET_MS=0
python3 -c "from config import load_config; load_config()"
# RuntimeError: PERF_REVIEWER_BUDGET_MS must be a positive integer
```

**Relationship Violation**:
```bash
export PERF_RETRIEVAL_PARALLEL=true
export PERF_PGVECTOR_ENABLED=false
python3 -c "from config import load_config; cfg = load_config(); from config import validate_perf_config; validate_perf_config(cfg)"
# Returns: ["PERF_RETRIEVAL_PARALLEL: parallel retrieval requires pgvector enabled"]
```

---

## Environment Variables

All flags can be overridden via environment variables:

```bash
# Boolean flags
export PERF_RETRIEVAL_PARALLEL=true
export PERF_REVIEWER_ENABLED=false
export PERF_PGVECTOR_ENABLED=true
export PERF_FALLBACKS_ENABLED=true

# Budget flags (milliseconds)
export PERF_RETRIEVAL_TIMEOUT_MS=600
export PERF_GRAPH_TIMEOUT_MS=200
export PERF_COMPARE_TIMEOUT_MS=500
export PERF_REVIEWER_BUDGET_MS=700
```

Precedence: Environment variable > Default value

---

## Documentation

### Created Files

1. **`PERF_FLAGS_QUICKSTART.md`** - Quick reference guide
   - TL;DR and quick examples
   - All flags with descriptions
   - Configuration methods
   - API response format
   - Validation rules
   - Common patterns
   - Monitoring examples
   - Testing guide
   - Troubleshooting
   - Best practices

2. **`PERF_FLAGS_IMPLEMENTATION.md`** - This file
   - Comprehensive implementation details
   - Acceptance criteria verification
   - API documentation
   - Validation rules
   - Test coverage

### Existing Documentation

- `docs/perf-and-fallbacks.md` - Operator runbook (references these flags)
- `LATENCY_GATES_QUICKSTART.md` - Works with these budgets
- `RESOURCE_LIMITS_QUICKSTART.md` - Complementary limits system

---

## Files Modified

| File | Changes | Lines | Description |
|------|---------|-------|-------------|
| `feature_flags.py` | Added | +66 | Added `get_perf_flags()` function |
| `api/debug.py` | Enhanced | +27 | Structured performance section in `/debug/config` |
| `config.py` | None | 0 | Flags already present |
| `tests/perf/test_flags.py` | None | 0 | Tests already comprehensive |

**Total**: +93 lines of code

---

## Test Coverage

### Test Classes (8)

1. `TestPerformanceFlagDefaults` - Default value verification
2. `TestPerformanceFlagTypes` - Type validation and parsing
3. `TestAllPerformanceFlags` - Presence and type checks
4. `TestConfigValidation` - Validation logic
5. `TestDebugConfigEndpoint` - API endpoint behavior
6. `TestEnvironmentOverrides` - Environment variable support
7. `TestBudgetRanges` - Budget reasonableness
8. `TestAcceptanceCriteria` - Explicit acceptance tests

### Test Methods (31)

All tests pass in 0.003s with 100% success rate.

**Coverage Areas**:
- ✅ Default values correct
- ✅ Type validation works
- ✅ Range validation works
- ✅ Environment overrides work
- ✅ Invalid values raise errors
- ✅ Clear error messages
- ✅ API endpoint exposes flags
- ✅ Sensitive data redacted
- ✅ Budget relationships sensible
- ✅ All acceptance criteria met

---

## Usage Examples

### Python Code

```python
from config import load_config

# Load full configuration
cfg = load_config()

# Access individual flags
parallel = cfg["PERF_RETRIEVAL_PARALLEL"]
timeout = cfg["PERF_RETRIEVAL_TIMEOUT_MS"]

# Get structured performance config
from feature_flags import get_perf_flags

perf = get_perf_flags()
flags = perf["flags"]        # Boolean flags
budgets = perf["budgets"]    # Timeout budgets

# Use in code
if flags["reviewer_enabled"]:
    timeout = budgets["reviewer_budget_ms"]
    run_reviewer(timeout=timeout)
```

### API Queries

```bash
# View all performance configuration
curl -s http://localhost:8000/debug/config | jq '.performance'

# Check if reviewer is enabled
curl -s http://localhost:8000/debug/config \
  | jq '.performance.flags.reviewer_enabled'

# Get retrieval timeout
curl -s http://localhost:8000/debug/config \
  | jq '.performance.budgets.retrieval_timeout_ms'

# Compare budget to actual p95
BUDGET=$(curl -s http://localhost:8000/debug/config | jq '.performance.budgets.retrieval_timeout_ms')
ACTUAL=$(curl -s http://localhost:8000/debug/metrics/summary | jq '.retrieval.p95')
echo "Budget: ${BUDGET}ms, Actual: ${ACTUAL}ms"
```

### Environment Overrides

```bash
# Disable reviewer for speed test
PERF_REVIEWER_ENABLED=false python3 tools/load_smoke.py

# Increase timeouts for slow network
export PERF_RETRIEVAL_TIMEOUT_MS=1000
export PERF_GRAPH_TIMEOUT_MS=300
python3 app.py

# Aggressive timeouts for production
export PERF_RETRIEVAL_TIMEOUT_MS=300
export PERF_GRAPH_TIMEOUT_MS=100
export PERF_REVIEWER_BUDGET_MS=400
python3 app.py
```

---

## Integration Points

### 1. Latency Gates (`evals/latency.py`)

Performance budgets should align with latency gate thresholds:

```python
# Budget configuration
PERF_RETRIEVAL_TIMEOUT_MS = 450  # Budget
LATENCY_GATE_RETRIEVAL_P95 = 500  # Gate (allows slack)

# Use together
from config import load_config
from evals.latency import LatencyGates

cfg = load_config()
gates = LatencyGates()
# Gates enforce p95 ≤ budget + slack
```

### 2. Resource Limits (`core/limits.py`)

Budgets control per-operation timeouts, limits control concurrency:

```python
from config import load_config
from core.limits import get_limiter

cfg = load_config()
limiter = get_limiter()

# Limits apply before operation
with limiter.limit(user_id="user123"):
    # Budgets apply during operation
    result = retrieve(timeout=cfg["PERF_RETRIEVAL_TIMEOUT_MS"])
```

### 3. Circuit Breakers (`core/circuit_breaker.py`)

Flags control whether fallbacks are enabled:

```python
from config import load_config

cfg = load_config()

if cfg["PERF_FALLBACKS_ENABLED"] and cfg["PERF_PGVECTOR_ENABLED"]:
    # Circuit breaker can trigger pgvector fallback
    result = retrieve_with_fallback()
else:
    # Direct retrieval only
    result = retrieve()
```

---

## Monitoring & Operations

### Pre-Deploy Checklist

- [ ] Review current flag values: `curl /debug/config | jq '.performance'`
- [ ] Check metrics align with budgets: `curl /debug/metrics/summary`
- [ ] Run smoke tests: `python3 tools/load_smoke.py`
- [ ] Verify tests pass: `python3 -m unittest tests.perf.test_flags`

### Post-Deploy Checklist

- [ ] Verify flags loaded: `curl /debug/config | jq '.performance.flags'`
- [ ] Verify budgets loaded: `curl /debug/config | jq '.performance.budgets'`
- [ ] Check p95 latencies: `curl /debug/metrics/summary`
- [ ] Monitor for budget breaches: Check latency gates in CI

### Troubleshooting

**Problem**: Flag not taking effect
```bash
# Check environment
echo $PERF_RETRIEVAL_TIMEOUT_MS

# Check loaded value
curl -s http://localhost:8000/debug/config | jq '.performance.budgets.retrieval_timeout_ms'

# Restart application to reload config
```

**Problem**: Validation error on startup
```bash
# Check which flag is invalid
python3 -c "from config import load_config; load_config()" 2>&1 | grep RuntimeError

# Fix the invalid value
export PERF_RETRIEVAL_TIMEOUT_MS=450  # Valid positive integer
```

---

## Related Systems

| System | File | Relationship |
|--------|------|--------------|
| Latency Gates | `evals/latency.py` | Enforces budgets in CI |
| Resource Limits | `core/limits.py` | Complements operation budgets |
| Circuit Breakers | `core/circuit_breaker.py` | Uses fallback flags |
| Metrics | `core/metrics.py` | Tracks actual vs budgets |
| Load Testing | `tools/load_smoke.py` | Tests against budgets |

---

## Summary

**Implementation Status**: ✅ Complete

All acceptance criteria met:
- ✅ All 8 requested flags present in config
- ✅ Proper defaults validated (31 tests passing)
- ✅ `/debug/config` endpoint shows flags in structured format
- ✅ Bad environment variables throw clear errors
- ✅ Type and range validation implemented
- ✅ Comprehensive documentation created
- ✅ Environment variable overrides supported
- ✅ Sensitive data properly redacted

**Key Achievements**:
- 93 lines of new code
- 31 unit tests (100% passing)
- Structured API response
- Complete documentation
- Zero breaking changes

**Ready for**:
- ✅ Production deployment
- ✅ Operator use
- ✅ CI/CD integration
- ✅ Monitoring dashboards
