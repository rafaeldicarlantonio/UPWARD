# Pgvector Fallback - Quick Reference

## What It Does

Automatically routes vector queries to pgvector when Pinecone is unavailable, ensuring continued operation with reduced k values and sub-350ms latency.

## Key Features

- **Automatic detection**: Health checks every 30 seconds
- **Reduced k values**: Explicate=8, Implicate=4 (vs 16/8 normal)
- **Fast**: 350ms timeout budget
- **Transparent**: Response includes fallback flag

## Configuration

```bash
# Required flags
PERF_PGVECTOR_ENABLED=true      # Enable pgvector fallback
PERF_FALLBACKS_ENABLED=true     # Master fallback toggle
```

## Usage

No code changes required - fallback activates automatically:

```python
from core.selection import DualSelector

selector = DualSelector()
result = selector.select(query="...", embedding=[...])

# Check if fallback was used
if result.fallback.get('used'):
    print(f"Fallback reason: {result.fallback['reason']}")
    print(f"Reduced k: {result.fallback['reduced_k']}")
```

## Response Format

```json
{
  "context": [...],
  "fallback": {
    "used": true,
    "reason": "pinecone_unhealthy: Connection refused",
    "reduced_k": {
      "explicate": 8,
      "implicate": 4
    }
  }
}
```

## Metrics

Monitor fallback health:

```python
# Fallback triggers
vector.fallback.triggered{reason="pinecone_unhealthy"}

# Fallback queries
vector.fallback.queries{index="explicate",backend="pgvector"}

# Fallback latency
vector.fallback.latency_ms{index="explicate"}

# Health check failures
vector.health_check.failed{backend="pinecone"}
```

## Testing Fallback

Force fallback mode:

```python
result = selector.select(
    query="test",
    embedding=[0.1] * 1536,
    force_fallback=True  # Force pgvector
)

assert result.fallback['used'] == True
```

## Performance

| Metric | Value |
|--------|-------|
| Latency budget | 350ms |
| Explicate k | 8 |
| Implicate k | 4 |
| Cache TTL | 30s |

## Troubleshooting

### Fallback not activating?

1. Check flags: `PERF_PGVECTOR_ENABLED=true` and `PERF_FALLBACKS_ENABLED=true`
2. Verify Pinecone is actually down: Check health endpoint
3. Review metrics: `vector.fallback.triggered`

### Queries still failing?

1. Check pgvector connection: Supabase should be accessible
2. Review error metrics: `vector.fallback.errors`
3. Check logs for SQL errors

### High latency in fallback?

1. Verify 350ms budget not exceeded: `vector.fallback.latency_ms`
2. Check pgvector index health
3. Consider increasing budget in config

## Design Notes

- **Health check caching**: Avoids repeated connection attempts
- **Reduced k**: Balances quality vs latency in degraded mode
- **No cross-namespace merge**: Simplifies fallback queries
- **RBAC preserved**: Role filtering still applies in fallback

## Related

- `PGVECTOR_FALLBACK_DELIVERY_SUMMARY.md` - Full delivery report
- `adapters/vector_fallback.py` - Implementation
- `tests/perf/test_pgvector_fallback.py` - Test examples
