# Latency Budget Gates - Quick Start

## Overview
Enforce latency budgets across different operations in evaluation suites.

## Budget Thresholds

| Operation | Metric | Budget | Use Case |
|-----------|--------|--------|----------|
| **Retrieval** | p95 | 500ms | Fast candidate retrieval |
| **Packing** | p95 | 550ms | Answer assembly with citations |
| **Internal Compare** | p95 | 400ms | Internal-only comparison |
| **External Compare** | p95 | 2000ms | External API calls, timeouts |

## Quick Usage

### Check Retrieval Latencies

```python
from evals.latency import LatencyGate

gate = LatencyGate()
latencies = [200, 250, 300, 350, 400, 450]

result = gate.validate_retrieval(latencies)

if result.passed:
    print("✅ Retrieval within budget")
else:
    print(f"❌ {result.violations}")
```

### Check All Operations

```python
result = gate.validate_all(
    retrieval_latencies=[200, 250, 300],
    packing_latencies=[100, 150, 200],
    internal_compare_latencies=[150, 200, 250],
    external_compare_latencies=[1000, 1500]
)

if not result.passed:
    for violation in result.violations:
        print(f"  • {violation}")
```

### Use Assertion Helpers

```python
from evals.latency import assert_retrieval_budget

try:
    assert_retrieval_budget(latencies, budget=500)
    print("✅ Budget met")
except AssertionError as e:
    print(f"❌ {e}")
```

### With Eval Harness

```python
from evals.run import EvalRunner

# Latency gates enabled by default
runner = EvalRunner()

# Run evaluations
runner.run_testset("my_tests.json")

# Summary automatically includes latency gate results
summary = runner.print_summary()

# Console output:
# 🚦 Latency Budget Gates:
#   ✅ All latency budgets passed
#
# Or on failure:
# 🚦 Latency Budget Gates:
#   ❌ Latency budget violations detected:
#      • retrieval p95 latency 650.0ms exceeds budget 500ms by 150.0ms
```

## Violation Messages

When a budget is exceeded:

```
retrieval p95 latency 650.0ms exceeds budget 500ms by 150.0ms (20 samples)
```

Components:
- **Operation**: retrieval, packing, internal_compare, external_compare
- **Metric**: p95
- **Measured**: Actual p95 value (650.0ms)
- **Budget**: Configured threshold (500ms)
- **Excess**: Amount over budget (150.0ms)
- **Samples**: Number of measurements (20)

## Testing

### Run Tests

```bash
cd /workspace
python3 -m unittest tests.evals.test_latency_gates -v
```

**Expected**: 36 tests, all passing

### Test Slow Paths

The test suite includes simulated slow path scenarios:

```python
# Simulate slow retrieval (18 fast, 2 slow)
latencies = [200] * 18 + [800, 900]  # p95 will be ~800ms

result = gate.validate_retrieval(latencies)
# Result: FAILED, exceeds 500ms budget
```

## Custom Budgets

Override default budgets:

```python
gate = LatencyGate(budgets={
    "retrieval": 400,  # Stricter: 400ms instead of 500ms
    "packing": 500     # Stricter: 500ms instead of 550ms
})

result = gate.validate_retrieval(latencies, budget=400)
```

## Example Output

### Passing Suite

```
🚦 Latency Budget Gates:
  ✅ All latency budgets passed
```

### Failing Suite

```
🚦 Latency Budget Gates:
  ❌ Latency budget violations detected:
     • retrieval p95 latency 650.0ms exceeds budget 500ms by 150.0ms (20 samples)
     • packing p95 latency 600.0ms exceeds budget 550ms by 50.0ms (15 samples)

⚠️ Performance Issues:
  retrieval p95 latency 650.0ms exceeds budget 500ms by 150.0ms (20 samples)
  packing p95 latency 600.0ms exceeds budget 550ms by 50.0ms (15 samples)
```

## Integration Points

### 1. Development
- Validate latencies during dev runs
- Catch performance regressions early

### 2. CI/CD
- Fail builds on budget violations
- Track latency trends over time

### 3. Evaluation Suites
- Automatic budget checking in all suites
- Suite marked failed if budgets exceeded

## Common Scenarios

### Scenario: Slow Retrieval
**Symptom**: Retrieval p95 > 500ms

**Possible Causes**:
- Database index performance
- Network latency
- Large result sets

**Fix**:
- Optimize database queries
- Add caching layer
- Reduce result set size

### Scenario: Slow Packing
**Symptom**: Packing p95 > 550ms

**Possible Causes**:
- Complex citation formatting
- Large answer generation
- Contradiction detection overhead

**Fix**:
- Optimize citation assembly
- Stream large answers
- Cache contradiction checks

### Scenario: External Compare Timeout
**Symptom**: External compare p95 > 2000ms

**Possible Causes**:
- External API slow/down
- Network issues
- Large payloads

**Fix**:
- Implement timeout/retry
- Use circuit breaker
- Add caching for external results

## Files

```
evals/
└── latency.py                         # Latency gate module

tests/evals/
└── test_latency_gates.py              # Tests (36 tests)

evals/
└── run.py                             # Enhanced with latency gates
```

## Next Steps

1. **Run tests**: `python3 -m unittest tests.evals.test_latency_gates -v`
2. **Check budgets**: Run evaluations and check latency gates
3. **Monitor trends**: Track latency over time
4. **Optimize**: Address violations proactively

## Reference

See `LATENCY_GATES_IMPLEMENTATION.md` for complete documentation.
