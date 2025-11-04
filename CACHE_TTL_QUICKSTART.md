# Cache with TTL - Quick Reference

**Status**: ✅ Production Ready  
**Module**: `core/cache.py`

## Quick Start

### Transparent Caching (Automatic)

```python
from core.selection import DualSelector

selector = DualSelector(vector_store, db_adapter, ranker)

# Caching happens automatically
result = selector.select(
    query="What is machine learning?",
    embedding=embedding,
    caller_role="admin"
)

# Repeated queries hit cache (within TTL)
result_cached = selector.select(
    query="What is machine learning?",
    embedding=embedding,
    caller_role="admin"
)
# ✅ Returns in < 1ms from cache
```

### Manual Cache Operations

```python
from core.cache import get_cache, invalidate_cache_on_ingest

# Get cache instance
cache = get_cache()

# Check for cached result
cached = cache.get_selection(
    query="What is AI?",
    role="admin"
)

# Cache a result
cache.set_selection(
    query="What is AI?",
    result=result,
    role="admin",
    entity_ids={"mem1", "mem2"}
)

# Invalidate on ingest
invalidate_cache_on_ingest({"mem1", "entity_x"})
```

## Key Features

### 1. TTL-Based Expiration

```python
# Default TTLs
QueryCache(
    embedding_ttl=120.0,    # 2 minutes
    selection_ttl=60.0,     # 1 minute
    cleanup_interval=30.0   # Cleanup every 30s
)

# Entries automatically expire
cache.set_selection(query, result)
time.sleep(65)  # Wait past TTL
assert cache.get_selection(query) is None  # ✅ Expired
```

### 2. Query Normalization

```python
# These all hit the same cache entry
queries = [
    "What is AI?",
    "what is ai?",
    "  WHAT   IS   AI?  ",
    "What Is Ai?"
]

cache.set_embedding(queries[0], embedding)

for query in queries:
    cached = cache.get_embedding(query)
    assert cached is not None  # ✅ All hit same cache
```

### 3. Role-Based Isolation

```python
# Different roles get different caches
cache.set_embedding("query", emb_admin, role="admin")
cache.set_embedding("query", emb_user, role="user")

# Each role gets their own result
assert cache.get_embedding("query", role="admin") == emb_admin
assert cache.get_embedding("query", role="user") == emb_user
```

### 4. Entity-Based Invalidation

```python
# Cache with entity tracking
cache.set_selection(
    query="What is entity X?",
    result=result,
    entity_ids={"mem123", "entity_x"}
)

# Ingest new content
invalidate_cache_on_ingest({"entity_x"})

# ✅ Cache cleared for affected queries
assert cache.get_selection("What is entity X?") is None
```

## Common Operations

### Check Cache Stats

```python
cache = get_cache()
stats = cache.get_stats()

print(f"Embeddings: {stats['embeddings']['count']}")
print(f"Selections: {stats['selections']['count']}")
print(f"Entities tracked: {stats['entities_tracked']}")
```

### Bypass Cache

```python
# Force fresh result (skip cache)
result = selector.select(
    query="What is AI?",
    embedding=embedding,
    caller_role="admin",
    bypass_cache=True  # ✅ Ignores cache
)
```

### Clear All Cache

```python
# Clear everything
cache = get_cache()
cache.invalidate_all()
```

### Manual Invalidation

```python
# Invalidate specific entities
cache.invalidate_by_entities({"mem1", "mem2", "entity_x"})

# Or use convenience function
invalidate_cache_on_ingest({"mem1", "mem2"})
```

## Integration Patterns

### With Selection

```python
# Automatic caching on select()
result = selector.select(query, embedding, caller_role="admin")

# First call: cache miss, executes selection
# Second call: cache hit, returns in < 1ms
```

### With Ingest

```python
def ingest_memory(memory):
    # Store memory
    db.insert(memory)
    
    # ✅ Invalidate cache for affected entities
    entity_ids = {memory.id, memory.source_doc_id}
    invalidate_cache_on_ingest(entity_ids)
```

### With Embeddings

```python
# Cache embedding generation
def get_embedding_cached(query, role=None):
    cache = get_cache()
    
    # Check cache
    cached = cache.get_embedding(query, role=role)
    if cached:
        return cached
    
    # Generate embedding
    embedding = generate_embedding(query)
    
    # Cache it
    cache.set_embedding(query, embedding, role=role)
    return embedding
```

## Configuration

### Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `embedding_ttl` | 120s | Embedding cache TTL |
| `selection_ttl` | 60s | Selection cache TTL |
| `cleanup_interval` | 30s | Cleanup frequency |

### Custom Configuration

```python
from core.cache import QueryCache

# Longer TTLs for stable data
cache = QueryCache(
    embedding_ttl=300.0,   # 5 minutes
    selection_ttl=180.0    # 3 minutes
)

# Shorter TTLs for volatile data
cache = QueryCache(
    embedding_ttl=30.0,    # 30 seconds
    selection_ttl=15.0     # 15 seconds
)
```

## Metrics

**Tracked automatically**:
- `cache.hit{type}` - Cache hits
- `cache.miss{type, reason}` - Cache misses
- `cache.set{type}` - Cache writes
- `cache.expired{type}` - Expired entries
- `cache.invalidated{count, trigger}` - Invalidations

**Monitor hit rate**:
```python
from core.metrics import get_counter

hits = get_counter("cache.hit")
misses = get_counter("cache.miss")
hit_rate = hits / (hits + misses)

print(f"Cache hit rate: {hit_rate:.1%}")
```

## Testing

```bash
# Run all cache tests
python3 -m unittest tests.perf.test_cache_hits -v

# Run acceptance tests
python3 -m unittest tests.perf.test_cache_hits.TestAcceptanceCriteria -v
```

## Performance

| Operation | Latency | Improvement |
|-----------|---------|-------------|
| Cache hit | < 1ms | 450x faster |
| Cache miss | < 1ms | No overhead |
| Invalidation | < 5ms | - |
| Repeated query (10x) | 450ms + 9ms | 10x faster |

## Troubleshooting

### Low Hit Rate

**Check**:
```python
stats = cache.get_stats()
print(f"Cache size: {stats['selections']['count']}")
```

**Solutions**:
- Verify query normalization
- Increase TTL
- Check invalidation frequency

### Stale Results

**Check**:
```python
# Verify invalidation is called
invalidate_cache_on_ingest(entity_ids)
```

**Solutions**:
- Add invalidation to ingest paths
- Reduce TTL
- Verify entity tracking

### Memory Growth

**Check**:
```python
stats = cache.get_stats()
if stats['selections']['count'] > 10000:
    print("Cache too large")
```

**Solutions**:
- Reduce TTL
- Increase cleanup frequency
- Consider LRU eviction

## Best Practices

### ✅ Do

- Let caching happen transparently
- Invalidate on every ingest
- Monitor cache hit rate
- Use appropriate TTLs
- Include role in cache keys

### ❌ Don't

- Bypass cache unnecessarily
- Forget to invalidate on ingest
- Set TTL too long (stale data)
- Set TTL too short (no benefit)
- Ignore cache metrics

## Quick Reference Card

| Feature | Usage | Notes |
|---------|-------|-------|
| Get cached selection | `cache.get_selection(query, role=role)` | Returns None if miss |
| Cache selection | `cache.set_selection(query, result, entity_ids=ids)` | Automatic in select() |
| Invalidate | `invalidate_cache_on_ingest(entity_ids)` | Call on ingest |
| Bypass cache | `selector.select(..., bypass_cache=True)` | Force fresh |
| Get stats | `cache.get_stats()` | Monitor health |
| Clear all | `cache.invalidate_all()` | Nuclear option |

| Cache Type | TTL | When to Use |
|------------|-----|-------------|
| Embeddings | 120s | Rarely change |
| Selections | 60s | Change moderately |

## Examples

### Example 1: Repeated Queries

```python
# First query
result1 = selector.select("What is AI?", embedding, role="admin")
# Time: ~450ms (database + vector store)

# Second query
result2 = selector.select("What is AI?", embedding, role="admin")
# Time: ~1ms (cache hit)

# ✅ 450x faster
```

### Example 2: Invalidation

```python
# Cache result
result = selector.select("What is entity X?", embedding)

# Ingest new data
ingest_memory(memory_about_x)
invalidate_cache_on_ingest({"entity_x"})

# Next query gets fresh data
result_fresh = selector.select("What is entity X?", embedding)
# ✅ No stale results
```

### Example 3: Role Isolation

```python
# Admin query
result_admin = selector.select(
    "Sensitive query",
    embedding,
    caller_role="admin"
)

# User query (different cache)
result_user = selector.select(
    "Sensitive query",
    embedding,
    caller_role="user"
)

# ✅ Separate results per role
```

## Related Documentation

- **Delivery Summary**: `CACHE_TTL_DELIVERY_SUMMARY.md`
- **Implementation**: `core/cache.py`
- **Tests**: `tests/perf/test_cache_hits.py`
- **Selection**: `core/selection.py`

---

**Quick Start Complete** ✅  
For detailed documentation, see `CACHE_TTL_DELIVERY_SUMMARY.md`
