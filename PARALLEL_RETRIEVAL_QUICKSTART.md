# Parallel Dual-Index Retrieval - Quick Start

## Overview
Async parallelism for dual-index queries with `asyncio.gather` and timeout handling.

## Key Features

- **Parallel execution**: Explicate and implicate queries run concurrently
- **Timeout handling**: Per-query timeouts with graceful degradation
- **Partial results**: Continue with available results if one index times out
- **Timing metrics**: Individual and total wall time recorded
- **Configurable**: Enable/disable via performance flags

## Quick Usage

### Basic (Auto-Parallel)
```python
from core.selection import DualSelector

selector = DualSelector()
result = selector.select(
    query="transformer architecture",
    embedding=query_embedding,
    explicate_top_k=16,
    implicate_top_k=8
)

# Check warnings
if result.warnings:
    print(f"Warnings: {result.warnings}")

# Check timings
print(f"Wall time: {result.timings['total_wall_time_ms']}ms")
print(f"Speedup: {result.timings['explicate_ms'] + result.timings['implicate_ms']} → {result.timings['total_wall_time_ms']}ms")
```

### Configuration
```bash
# Enable parallel (default)
export PERF_RETRIEVAL_PARALLEL=true
export PERF_RETRIEVAL_TIMEOUT_MS=450

# Disable parallel (sequential fallback)
export PERF_RETRIEVAL_PARALLEL=false
```

### Check for Timeouts
```python
if result.timings.get('explicate_timeout'):
    print("Explicate timed out - using implicate results only")

if result.timings.get('implicate_timeout'):
    print("Implicate timed out - using explicate results only")
```

## Performance

### Before (Sequential)
```
Explicate: 200ms
Implicate: 250ms
Total: 450ms
```

### After (Parallel)
```
Explicate: 200ms  ]
Implicate: 250ms  ] → 250ms
Total: 250ms (44% faster)
```

## Timeout Scenarios

| Scenario | Behavior | Result |
|----------|----------|--------|
| Both succeed | Wall time = max(explicate, implicate) | Full results |
| One times out | Wall time = timeout value | Partial results + warning |
| Both timeout | Wall time = timeout value | Empty results + 2 warnings |
| Parallel fails | Fall back to sequential | Warning + full results |

## Testing

```bash
# Run all tests
python3 -m unittest tests.perf.test_parallel_selection -v

# Run acceptance tests
python3 -m unittest tests.perf.test_parallel_selection.TestAcceptanceCriteria -v
```

## Monitoring

### Key Metrics:
- `total_wall_time_ms`: Total execution time (should be ~max not sum)
- `explicate_ms`: Explicate query latency
- `implicate_ms`: Implicate query latency
- `explicate_timeout`: Boolean flag
- `implicate_timeout`: Boolean flag

### Example:
```python
# Calculate speedup
sequential_time = result.timings['explicate_ms'] + result.timings['implicate_ms']
parallel_time = result.timings['total_wall_time_ms']
speedup = sequential_time / parallel_time
print(f"Speedup: {speedup:.2f}x")
```

## Fallback Behavior

1. **Parallel execution enabled** → Try parallel queries
2. **If parallel fails** → Fall back to sequential
3. **If one query times out** → Use partial results
4. **If both timeout** → Return empty with warnings

All fallbacks are automatic and transparent to the caller.
