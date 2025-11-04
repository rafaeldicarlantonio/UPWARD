# Performance Metrics - Quick Reference

**Status**: ✅ Production Ready  
**Modules**: `core/metrics.py`, `api/debug.py`

## Quick Start

### Recording Metrics

```python
from core.metrics import PerformanceMetrics

# Retrieval
PerformanceMetrics.record_retrieval(450.0, success=True, method="dual")

# Graph expansion
PerformanceMetrics.record_graph_expand(150.0, entities_expanded=5)

# Packing
PerformanceMetrics.record_packing(200.0, items_packed=10)

# Reviewer
PerformanceMetrics.record_reviewer(500.0, skipped=False)

# Failures
PerformanceMetrics.record_pinecone_timeout("query")
PerformanceMetrics.record_pgvector_fallback("timeout")
PerformanceMetrics.record_circuit_open("pinecone")
```

### Querying Metrics

```python
from core.metrics import get_histogram_stats, get_counter, PerformanceMetrics

# Get percentiles
stats = get_histogram_stats("retrieval_ms")
print(f"p50: {stats['p50']}ms, p95: {stats['p95']}ms")

# Get counters
timeouts = get_counter("pinecone_timeouts")
fallbacks = get_counter("pgvector_fallbacks")

# Get rates
error_rate = PerformanceMetrics.get_error_rate("retrieval")
fallback_rate = PerformanceMetrics.get_fallback_rate()
```

## API Endpoints

### `/debug/metrics`
Full metrics with percentiles:
```bash
curl http://localhost:8000/debug/metrics
```

### `/debug/metrics/summary`
Compact summary:
```bash
curl http://localhost:8000/debug/metrics/summary
```

### `/debug/health`
Health status:
```bash
curl http://localhost:8000/debug/health
```

## Key Metrics

### Histograms (with p50/p95)
- `retrieval_ms` - Retrieval latency
- `graph_expand_ms` - Graph expansion latency
- `packing_ms` - Packing latency
- `reviewer_ms` - Reviewer latency

### Counters
- `pinecone_timeouts` - Pinecone timeouts
- `pgvector_fallbacks` - Fallback events
- `reviewer_skips` - Reviewer skips
- `circuit_opens` - Circuit opens
- `circuit_closes` - Circuit closes

### Rates
- `retrieval_error_rate` - % failed retrievals
- `pgvector_fallback_rate` - % fallback usage

## Performance Targets

| Metric | p95 Target |
|--------|------------|
| Retrieval | < 500ms |
| Graph expansion | < 200ms |
| Packing | < 300ms |
| Reviewer | < 600ms |

| Rate | Target |
|------|--------|
| Error rate | < 5% |
| Fallback rate | < 20% |

## Common Patterns

### Instrument a Function

```python
import time
from core.metrics import PerformanceMetrics

def retrieve_data(query):
    start = time.time()
    try:
        results = perform_retrieval(query)
        latency_ms = (time.time() - start) * 1000
        PerformanceMetrics.record_retrieval(latency_ms, success=True)
        return results
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        PerformanceMetrics.record_retrieval(latency_ms, success=False)
        raise
```

### Monitor Health

```python
from core.metrics import PerformanceMetrics, get_counter

# Check error rate
error_rate = PerformanceMetrics.get_error_rate("retrieval")
if error_rate > 0.05:
    alert(f"High error rate: {error_rate:.1%}")

# Check circuit breakers
opens = get_counter("circuit_opens")
closes = get_counter("circuit_closes")
if opens > closes:
    alert(f"Circuit breaker open: {opens - closes}")
```

### Dashboard Query

```python
import requests

response = requests.get("http://localhost:8000/debug/metrics/summary")
data = response.json()

print(f"Retrieval: p95={data['retrieval']['p95']}ms")
print(f"Error rate: {data['errors']['retrieval_error_rate']:.1%}")
print(f"Fallbacks: {data['fallbacks']['pgvector_fallbacks']}")
```

## Testing

```bash
# Run all metrics tests
python3 -m unittest tests.perf.test_metrics_wireup -v

# Run acceptance tests
python3 -m unittest tests.perf.test_metrics_wireup.TestAcceptanceCriteria -v
```

## Quick Reference Card

| Operation | Code | Result |
|-----------|------|--------|
| Record retrieval | `PerformanceMetrics.record_retrieval(450.0)` | Histogram + counter |
| Record timeout | `PerformanceMetrics.record_pinecone_timeout()` | Counter++ |
| Record fallback | `PerformanceMetrics.record_pgvector_fallback()` | Counter++ |
| Get p95 | `get_histogram_stats("retrieval_ms")["p95"]` | Float (ms) |
| Get counter | `get_counter("pinecone_timeouts")` | Int |
| Get error rate | `PerformanceMetrics.get_error_rate()` | Float (0.0-1.0) |

## Best Practices

### ✅ Do

- Instrument all hot paths
- Use p95 for SLOs, not average
- Monitor error rates
- Set realistic thresholds
- Check health endpoint regularly

### ❌ Don't

- Skip instrumentation
- Use too many label values
- Ignore high p95 latency
- Set unrealistic thresholds
- Only monitor averages

## Related Documentation

- **Delivery Summary**: `METRICS_TELEMETRY_DELIVERY_SUMMARY.md`
- **Implementation**: `core/metrics.py`
- **Endpoints**: `api/debug.py`
- **Tests**: `tests/perf/test_metrics_wireup.py`

---

**Quick Start Complete** ✅  
For detailed documentation, see `METRICS_TELEMETRY_DELIVERY_SUMMARY.md`
