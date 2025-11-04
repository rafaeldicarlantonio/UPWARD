# Performance Flags - Quick Start

## Overview
Performance flags and timeout budgets for tuning system behavior.

## Flags

### Boolean Flags
```bash
export PERF_RETRIEVAL_PARALLEL=true    # Enable parallel retrieval (default: true)
export PERF_REVIEWER_ENABLED=true       # Enable answer review (default: true)
export PERF_PGVECTOR_ENABLED=true       # Enable pgvector (default: true)
export PERF_FALLBACKS_ENABLED=true      # Enable fallback strategies (default: true)
```

### Timeout Budgets (milliseconds)
```bash
export PERF_RETRIEVAL_TIMEOUT_MS=450    # Retrieval timeout (default: 450)
export PERF_GRAPH_TIMEOUT_MS=150        # Graph expansion timeout (default: 150)
export PERF_COMPARE_TIMEOUT_MS=400      # Compare timeout (default: 400)
export PERF_REVIEWER_BUDGET_MS=500      # Review budget (default: 500)
```

## Usage

### Load in Python
```python
from config import load_config

cfg = load_config()

# Check flags
if cfg["PERF_RETRIEVAL_PARALLEL"]:
    # Use parallel retrieval
    pass

# Check budgets
timeout = cfg["PERF_RETRIEVAL_TIMEOUT_MS"]
```

### Query via API
```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config
```

Response:
```json
{
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
  }
}
```

### Validate Config
```python
from config import validate_perf_config, load_config

cfg = load_config()
errors = validate_perf_config(cfg)

if errors:
    for key, msg in errors.items():
        print(f"Warning: {key}: {msg}")
```

## Common Scenarios

### Speed Mode (Lower Latency)
```bash
export PERF_REVIEWER_ENABLED=false      # Skip review
export PERF_GRAPH_TIMEOUT_MS=50         # Fast graph
export PERF_RETRIEVAL_TIMEOUT_MS=300    # Fast retrieval
```

### Quality Mode (Higher Accuracy)
```bash
export PERF_REVIEWER_ENABLED=true       # Enable review
export PERF_GRAPH_TIMEOUT_MS=300        # Allow more graph time
export PERF_RETRIEVAL_TIMEOUT_MS=800    # Allow more retrieval time
```

### High Load (Resource Constrained)
```bash
export PERF_RETRIEVAL_PARALLEL=false    # Sequential retrieval
export PERF_REVIEWER_ENABLED=false      # Skip review
export PERF_FALLBACKS_ENABLED=false     # Fail fast
```

## Validation Rules

- All timeout budgets must be positive integers
- Retrieval timeout should be ≤ 1000ms for responsive UX
- Graph timeout should be ≤ 300ms (part of retrieval)
- Compare timeout should be ≤ 1000ms (synchronous)
- Reviewer budget should be ≤ 1000ms
- Parallel retrieval requires pgvector to be enabled

## Testing

```bash
# Run all tests
python3 -m unittest tests.perf.test_flags -v

# Test specific functionality
python3 -m unittest tests.perf.test_flags.TestPerformanceFlagDefaults
```

## Defaults

All flags have safe defaults:
- Boolean flags: `True` (features enabled)
- Timeouts: Conservative values for responsive UX
- Total request budget: ~1650ms (under 2 second target)

## Debug

Check current config:
```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config | jq '.performance'
```

Check validation warnings:
```python
from config import load_config, validate_perf_config
errors = validate_perf_config(load_config())
print(errors)  # {} if all valid
```
