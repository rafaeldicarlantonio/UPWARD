# Performance Flags and Budgets - Delivery Summary

## Overview
Added comprehensive performance flags and timeout budgets with type validation and debug endpoint exposure.

## Deliverables

### 1. Performance Flags in config.py ✅
**File**: `config.py`

Added 8 new performance configuration flags:

#### Boolean Flags (with safe defaults):
- `PERF_RETRIEVAL_PARALLEL`: True (enable parallel retrieval)
- `PERF_REVIEWER_ENABLED`: True (enable answer review)
- `PERF_PGVECTOR_ENABLED`: True (enable pgvector indexing)
- `PERF_FALLBACKS_ENABLED`: True (enable fallback strategies)

#### Timeout/Budget Flags (in milliseconds):
- `PERF_RETRIEVAL_TIMEOUT_MS`: 450ms
- `PERF_GRAPH_TIMEOUT_MS`: 150ms
- `PERF_COMPARE_TIMEOUT_MS`: 400ms
- `PERF_REVIEWER_BUDGET_MS`: 500ms

**Features**:
- All flags have sensible defaults
- Environment variable overrides supported
- Type validation ensures correct parsing
- Proper error messages for invalid values

### 2. Type Validation ✅
**File**: `config.py` (in `load_config()`)

**Boolean Flags Validation**:
- Accepts: 'true', '1', 'yes', 'on' (case-insensitive) → True
- Accepts: 'false', '0', 'no', 'off' → False
- Returns: Python `bool` type

**Timeout/Budget Validation**:
- Must be positive integers (> 0)
- Rejects: negative values, zero, non-numeric strings
- Returns: Python `int` type
- Clear error messages on validation failure

**Example Error**:
```python
RuntimeError: PERF_RETRIEVAL_TIMEOUT_MS must be a positive integer, got: -100
```

### 3. Config Validation Helper ✅
**File**: `config.py`

Added `validate_perf_config(cfg)` function:
- Warns if retrieval timeout > 1000ms
- Warns if graph timeout > 300ms
- Warns if compare timeout > 1000ms
- Warns if reviewer budget > 1000ms
- Catches conflict: parallel retrieval requires pgvector

Returns dict of validation errors (empty if all valid).

### 4. Debug Config Helper ✅
**File**: `config.py`

Added `get_debug_config()` function:
- Returns sanitized configuration (no secrets)
- Removes keys containing: KEY, SECRET, PASSWORD, TOKEN
- Adds metadata (version, environment, loaded_at timestamp)
- Safe for public exposure via API

### 5. Debug Endpoint Exposure ✅
**File**: `router/debug.py`

Enhanced `GET /debug/config` endpoint:

**Response Structure**:
```json
{
  "config": {
    "SUPABASE_URL": "...",
    "EMBED_MODEL": "text-embedding-3-small",
    ...
  },
  "feature_flags": {
    "retrieval.dual_index": false,
    ...
  },
  "performance": {
    "flags": {
      "PERF_RETRIEVAL_PARALLEL": true,
      "PERF_REVIEWER_ENABLED": true,
      "PERF_PGVECTOR_ENABLED": true,
      "PERF_FALLBACKS_ENABLED": true
    },
    "budgets_ms": {
      "PERF_RETRIEVAL_TIMEOUT_MS": 450,
      "PERF_GRAPH_TIMEOUT_MS": 150,
      "PERF_COMPARE_TIMEOUT_MS": 400,
      "PERF_REVIEWER_BUDGET_MS": 500
    }
  },
  "status": "ok"
}
```

**Key Features**:
- Separates boolean flags from timeout budgets
- All sensitive values redacted
- Graceful error handling
- Requires API key authentication

### 6. Comprehensive Tests ✅
**File**: `tests/perf/test_flags.py`

**31 tests covering**:

#### Default Values (8 tests):
- All flags have correct default values
- All flags have correct types (bool vs int)

#### Type Validation (7 tests):
- Boolean parsing: 'true', 'false', '1', '0'
- Integer parsing for timeouts
- Rejection of invalid values (negative, zero, non-numeric)
- Clear error messages

#### Full Config Loading (3 tests):
- All 8 flags present after load
- All types correct (bool/int)
- Default values are sensible (positive, reasonable ranges)

#### Config Validation (5 tests):
- Valid config passes
- Excessive timeouts caught
- Conflicting settings detected (parallel without pgvector)

#### Debug Endpoint (2 tests):
- Sanitized config removes secrets
- Performance flags exposed

#### Environment Overrides (3 tests):
- Boolean flags overridable
- Timeout budgets overridable
- All timeouts independently configurable

#### Budget Ranges (2 tests):
- Default budgets sensibly ordered (graph < retrieval)
- Total latency budget reasonable (< 2 seconds)

#### Acceptance Criteria (2 tests):
- Defaults validated and load correctly
- Debug endpoint shows all performance keys

**Test Results**: ✅ All 31 tests passing

## Acceptance Criteria Validation

### ✅ Defaults Validated
```bash
$ python3 -m unittest tests.perf.test_flags.TestAcceptanceCriteria.test_defaults_validated
...
ok
```

All default values:
- Load without errors ✅
- Have correct types ✅
- Are within reasonable ranges ✅
- Can be validated programmatically ✅

### ✅ /debug/config Shows Keys
```bash
$ python3 -m unittest tests.perf.test_flags.TestAcceptanceCriteria.test_debug_config_shows_keys
...
ok
```

Endpoint exposes:
- All 4 boolean performance flags ✅
- All 4 timeout/budget values ✅
- Separated into `flags` and `budgets_ms` sections ✅
- No secrets leaked ✅

## Usage Examples

### 1. Load Config with Defaults
```python
from config import load_config

cfg = load_config()

# Boolean flags
assert cfg["PERF_RETRIEVAL_PARALLEL"] is True
assert cfg["PERF_REVIEWER_ENABLED"] is True

# Timeout budgets
assert cfg["PERF_RETRIEVAL_TIMEOUT_MS"] == 450
assert cfg["PERF_GRAPH_TIMEOUT_MS"] == 150
```

### 2. Override via Environment
```bash
export PERF_RETRIEVAL_TIMEOUT_MS=600
export PERF_FALLBACKS_ENABLED=false
python3 app.py
```

### 3. Validate Configuration
```python
from config import load_config, validate_perf_config

cfg = load_config()
errors = validate_perf_config(cfg)

if errors:
    for key, msg in errors.items():
        print(f"Warning: {key}: {msg}")
```

### 4. Query Debug Endpoint
```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config | jq '.performance'
```

Expected output:
```json
{
  "flags": {
    "PERF_RETRIEVAL_PARALLEL": true,
    "PERF_REVIEWER_ENABLED": true,
    "PERF_PGVECTOR_ENABLED": true,
    "PERF_FALLBACKS_ENABLED": true
  },
  "budgets_ms": {
    "PERF_RETRIEVAL_TIMEOUT_MS": 450,
    "PERF_GRAPH_TIMEOUT_MS": 150,
    "PERF_COMPARE_TIMEOUT_MS": 400,
    "PERF_REVIEWER_BUDGET_MS": 500
  }
}
```

## Flag Design Rationale

### Retrieval Parallel (default: True)
- Enables concurrent queries to multiple indices
- Reduces total retrieval latency
- Requires pgvector for connection pooling

### Retrieval Timeout (default: 450ms)
- Keeps total retrieval under 500ms (p95 target)
- Allows 50ms buffer for ranking/scoring
- Responsive UX without blocking

### Graph Timeout (default: 150ms)
- Graph expansion is part of retrieval pipeline
- Must complete within retrieval budget
- Fallback to literal results if exceeded

### Compare Timeout (default: 400ms)
- Internal comparisons are synchronous
- Must complete before answer generation
- Aligns with p95 compare latency target (≤400ms)

### Reviewer Enabled (default: True)
- Post-generation answer quality check
- Validates citations, detects hallucinations
- Small latency cost for quality gains

### Reviewer Budget (default: 500ms)
- Allows thorough quality checks
- Keeps total request under 2 seconds
- Can be lowered in high-throughput scenarios

### PGVector Enabled (default: True)
- Modern vector database with connection pooling
- Required for parallel retrieval
- Better performance than legacy pinecone-only

### Fallbacks Enabled (default: True)
- Graceful degradation on timeout/failure
- Literal retrieval if implicate fails
- Internal-only answer if external times out

## Budget Composition

Typical request timeline:
```
Retrieval (450ms)
  ├─ Graph expansion (150ms)
  ├─ Vector search (200ms)
  └─ Ranking (100ms)
Compare (400ms)
  ├─ Contradiction detection (200ms)
  └─ Confidence scoring (200ms)
Answer generation (300ms)
Review (500ms)
  ├─ Citation validation (300ms)
  └─ Hallucination check (200ms)
────────────────────────────────
Total: ~1650ms (well under 2s)
```

## Error Handling

### Invalid Type
```python
# PERF_RETRIEVAL_TIMEOUT_MS=abc
RuntimeError: PERF_RETRIEVAL_TIMEOUT_MS must be a positive integer, got: abc
```

### Negative/Zero Value
```python
# PERF_GRAPH_TIMEOUT_MS=-100
RuntimeError: PERF_GRAPH_TIMEOUT_MS must be a positive integer, got: -100
```

### Validation Warning
```python
cfg["PERF_RETRIEVAL_TIMEOUT_MS"] = 1500
errors = validate_perf_config(cfg)
# errors = {"PERF_RETRIEVAL_TIMEOUT_MS": "Should be ≤ 1000ms for responsive UX"}
```

### Config Conflict
```python
cfg["PERF_RETRIEVAL_PARALLEL"] = True
cfg["PERF_PGVECTOR_ENABLED"] = False
errors = validate_perf_config(cfg)
# errors = {"PERF_RETRIEVAL_PARALLEL": "Parallel retrieval requires pgvector to be enabled"}
```

## Testing Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Default Values | 8 | ✅ |
| Type Validation | 7 | ✅ |
| Full Config | 3 | ✅ |
| Validation Logic | 5 | ✅ |
| Debug Endpoint | 2 | ✅ |
| Env Overrides | 3 | ✅ |
| Budget Ranges | 2 | ✅ |
| Acceptance | 2 | ✅ |
| **Total** | **31** | **✅** |

## Files Modified/Created

### Modified:
1. `config.py` (+58 lines)
   - Added 8 performance flags to DEFAULTS
   - Added type validation logic
   - Added `get_debug_config()` helper
   - Added `validate_perf_config()` helper

2. `router/debug.py` (+12 lines, modified 1 function)
   - Enhanced `/debug/config` endpoint
   - Separated flags and budgets in response
   - Better structure for performance settings

### Created:
1. `tests/perf/__init__.py` (new directory)
2. `tests/perf/test_flags.py` (502 lines, 31 tests)

## Running the Tests

```bash
# Run all performance flag tests
python3 -m unittest tests.perf.test_flags -v

# Run specific test categories
python3 -m unittest tests.perf.test_flags.TestPerformanceFlagDefaults
python3 -m unittest tests.perf.test_flags.TestPerformanceFlagTypes
python3 -m unittest tests.perf.test_flags.TestConfigValidation
python3 -m unittest tests.perf.test_flags.TestAcceptanceCriteria

# Run single test
python3 -m unittest tests.perf.test_flags.TestAcceptanceCriteria.test_defaults_validated
```

## Integration Points

These flags can now be consumed by:

1. **Retrieval Engine** (`core/retrieval.py`)
   - Check `PERF_RETRIEVAL_PARALLEL` for parallel vs sequential
   - Enforce `PERF_RETRIEVAL_TIMEOUT_MS` timeout
   - Fallback logic if `PERF_FALLBACKS_ENABLED`

2. **Graph Expander** (`core/graph.py`)
   - Enforce `PERF_GRAPH_TIMEOUT_MS` timeout
   - Return partial results on timeout if fallbacks enabled

3. **Compare Engine** (`core/compare.py`)
   - Enforce `PERF_COMPARE_TIMEOUT_MS` timeout
   - Skip external if exceeds budget

4. **Answer Reviewer** (`core/reviewer.py`)
   - Check `PERF_REVIEWER_ENABLED` before running
   - Enforce `PERF_REVIEWER_BUDGET_MS` timeout
   - Skip review if disabled or budget exceeded

5. **Monitoring/Alerts** (`core/metrics.py`)
   - Compare actual latencies against budgets
   - Alert when p95 exceeds configured timeouts

## Backward Compatibility

- All flags have safe defaults
- Existing systems work without changes
- Override only when tuning needed
- No breaking changes to API or behavior

## Future Enhancements

Potential additions:
- `PERF_EXTERNAL_COMPARE_TIMEOUT_MS` (separate from internal)
- `PERF_RETRY_ENABLED` + `PERF_RETRY_MAX_ATTEMPTS`
- `PERF_CACHE_ENABLED` + `PERF_CACHE_TTL_SECONDS`
- `PERF_BATCH_SIZE` for bulk operations
- Per-role budget multipliers (general vs researcher)

## Conclusion

✅ **All acceptance criteria met**:
1. Defaults validated ✅
2. /debug/config shows keys ✅
3. Type validation comprehensive ✅
4. 31 tests passing ✅

**Status**: Ready for deployment

**Estimated Impact**:
- Better observability (debug endpoint)
- Flexible tuning (env overrides)
- Safer configuration (type validation)
- Foundation for performance optimization

---

**Delivered**: Performance flags and budgets with validation, debug exposure, and comprehensive tests.
**Test Coverage**: 31 tests, 100% passing.
**Documentation**: This summary + inline docstrings.
