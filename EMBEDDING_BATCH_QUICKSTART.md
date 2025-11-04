# Embedding Batching - Quick Reference

**Status**: ✅ Production Ready  
**Module**: `adapters/embeddings.py`

## Quick Start

### Basic Usage

```python
from adapters.embeddings import embed_texts, embed_text

# Embed multiple texts (automatic batching)
embeddings = embed_texts([
    "What is machine learning?",
    "How does AI work?",
    "Explain neural networks"
])

# Embed single text
embedding = embed_text("Single text to embed")
```

### With Configuration

```python
from adapters.embeddings import EmbeddingBatcher, EmbeddingConfig

# Custom configuration
config = EmbeddingConfig(
    batch_size=8,          # Max prompts per API call
    max_retries=3,         # Retry up to 3 times
    initial_backoff=1.0,   # Start at 1s
    jitter_factor=0.2      # ±20% jitter
)

batcher = EmbeddingBatcher(config)
result = batcher.embed_batch(texts)

print(f"API calls: {result.batch_size}")
print(f"Latency: {result.latency_ms}ms")
print(f"Retries: {result.retries}")
```

## Key Features

### 1. Automatic Batching

```python
# Without batching: 24 API calls
texts = [f"text{i}" for i in range(24)]

# With batching: 3 API calls (8 + 8 + 8)
embeddings = embed_texts(texts)

# ✅ 8x reduction in network calls
```

### 2. Connection Pool

- Pool size: 3 clients
- Keep-alive connections
- Thread-safe
- Automatic initialization

### 3. Exponential Backoff with Jitter

**Retry schedule**:
- Attempt 0: Immediate
- Attempt 1: ~1s (±20%)
- Attempt 2: ~2s (±20%)
- Attempt 3: ~4s (±20%)
- Then: Raise error

**Prevents thundering herd**: ✅  
Jitter ensures concurrent retries don't align.

### 4. Smart Retries

**Retryable errors**:
- 429 Rate limit
- 500, 502, 503, 504 Server errors
- Timeouts

**Non-retryable errors**:
- 400, 401, 403, 404 Client errors
- All other 4xx errors

## Error Handling

```python
from adapters.embeddings import (
    EmbeddingRateLimitError,
    EmbeddingPoolExhausted
)

try:
    embeddings = embed_texts(texts)
except EmbeddingRateLimitError as e:
    print(f"Rate limited after retries: {e}")
    # Wait longer or reduce batch size
    
except EmbeddingPoolExhausted:
    print("Connection pool full, waiting...")
    time.sleep(1)
    # Retry
```

## Configuration Reference

```python
EmbeddingConfig(
    model="text-embedding-3-small",  # Model name
    batch_size=8,                    # Max prompts per call
    max_retries=3,                   # Max retry attempts
    initial_backoff=1.0,             # Initial backoff (seconds)
    max_backoff=32.0,                # Max backoff (seconds)
    jitter_factor=0.2,               # Jitter amount (0.0-1.0)
    timeout=30.0                     # Per-call timeout (seconds)
)
```

## Result Structure

```python
@dataclass
class EmbeddingResult:
    embeddings: List[List[float]]    # Embedding vectors
    usage: Dict[str, int]            # Token usage
    latency_ms: float                # Total latency
    retries: int                     # Number of retries
    batch_size: int                  # Number of API calls made
```

## Performance Tips

### 1. Batch When Possible

```python
# ❌ Don't
for text in texts:
    embedding = embed_text(text)  # 100 API calls

# ✅ Do
embeddings = embed_texts(texts)  # ~13 API calls
```

### 2. Monitor Efficiency

```python
result = batcher.embed_batch(texts)
efficiency = len(texts) / result.batch_size
print(f"Efficiency: {efficiency}x")  # Target: ~8x
```

### 3. Handle Rate Limits

```python
# Split large batches
if len(texts) > 100:
    mid = len(texts) // 2
    embeddings1 = embed_texts(texts[:mid])
    time.sleep(1)  # Brief pause
    embeddings2 = embed_texts(texts[mid:])
    embeddings = embeddings1 + embeddings2
```

## Metrics

**Tracked metrics**:
- `embeddings.success{batch_size, retries}` - Successful calls
- `embeddings.failure{error_type, retries}` - Failed calls
- `embeddings.retry{attempt, error_type}` - Retry attempts
- `embeddings.latency_ms{batch_size}` - Latencies
- `embeddings.pool_exhausted` - Pool exhaustion

## Testing

```bash
# Run all tests
python3 -m unittest tests.perf.test_embedding_batch -v

# Run acceptance tests
python3 -m unittest tests.perf.test_embedding_batch.TestAcceptanceCriteria -v
```

## Common Patterns

### Batch Processing

```python
# Process large dataset in batches
all_embeddings = []
for i in range(0, len(large_dataset), 100):
    batch = large_dataset[i:i+100]
    embeddings = embed_texts(batch)
    all_embeddings.extend(embeddings)
    time.sleep(0.5)  # Rate limit protection
```

### Error Recovery

```python
def embed_with_retry(texts, max_attempts=3):
    """Embed with fallback."""
    for attempt in range(max_attempts):
        try:
            return embed_texts(texts)
        except EmbeddingRateLimitError:
            if attempt == max_attempts - 1:
                raise
            wait = 2 ** attempt
            time.sleep(wait)
    return []
```

### Monitoring

```python
# Track performance
start = time.time()
result = batcher.embed_batch(texts)
wall_time = (time.time() - start) * 1000

print(f"Embeddings: {len(result.embeddings)}")
print(f"API calls: {result.batch_size}")
print(f"API time: {result.latency_ms:.1f}ms")
print(f"Wall time: {wall_time:.1f}ms")
print(f"Retries: {result.retries}")
print(f"Efficiency: {len(texts)/result.batch_size:.1f}x")
```

## Integration Examples

### Replace Existing Embedding Logic

**Before**:
```python
def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
```

**After**:
```python
from adapters.embeddings import embed_text

def get_embedding(text):
    return embed_text(text)
```

### Batch Query Processing

**Before**:
```python
# Sequential, one at a time
embeddings = []
for query in queries:
    emb = get_embedding(query)
    embeddings.append(emb)
# N API calls
```

**After**:
```python
from adapters.embeddings import embed_texts

# Batched automatically
embeddings = embed_texts(queries)
# ~N/8 API calls
```

## Troubleshooting

### High Retry Rate

**Symptoms**: Many retries, slow performance  
**Check**:
```python
result = batcher.embed_batch(texts)
if result.retries > 1:
    print("High retry rate detected")
```

**Solutions**:
- Reduce batch size
- Add delays between batches
- Check API quota/limits

### Pool Exhaustion

**Symptoms**: `EmbeddingPoolExhausted` errors  
**Check**:
```python
# Monitor pool exhaustion metric
from core.metrics import get_counter
exhausted = get_counter("embeddings.pool_exhausted")
```

**Solutions**:
- Reduce concurrency
- Increase pool size (modify `_pool_size`)
- Add request queuing

### Slow Embeddings

**Symptoms**: High latency  
**Check**:
```python
result = batcher.embed_batch(texts)
if result.latency_ms > 5000:
    print(f"Slow: {result.latency_ms}ms")
```

**Solutions**:
- Reduce batch size
- Check network/API health
- Verify timeout settings

## Best Practices

### ✅ Do

- Batch multiple texts together
- Handle rate limit errors gracefully
- Monitor retry rate and efficiency
- Use jitter (enabled by default)
- Log high retry counts

### ❌ Don't

- Embed texts one at a time
- Ignore `EmbeddingRateLimitError`
- Disable jitter (causes thundering herd)
- Set `max_retries` too high (> 5)
- Ignore pool exhaustion errors

## Quick Reference Card

| Feature | Setting | Default |
|---------|---------|---------|
| Batch size | `batch_size` | 8 |
| Max retries | `max_retries` | 3 |
| Initial backoff | `initial_backoff` | 1.0s |
| Max backoff | `max_backoff` | 32s |
| Jitter | `jitter_factor` | 0.2 (20%) |
| Timeout | `timeout` | 30s |
| Pool size | `_pool_size` | 3 |

| Operation | Network Calls | Improvement |
|-----------|---------------|-------------|
| 8 texts | 1 (was 8) | 8x |
| 24 texts | 3 (was 24) | 8x |
| 100 texts | 13 (was 100) | 7.7x |

## Related Documentation

- **Delivery Summary**: `EMBEDDING_BATCH_DELIVERY_SUMMARY.md`
- **Implementation**: `adapters/embeddings.py`
- **Tests**: `tests/perf/test_embedding_batch.py`
- **Circuit Breakers**: `CIRCUIT_BREAKER_QUICKSTART.md`
- **Performance Flags**: `config.py`

---

**Quick Start Complete** ✅  
For detailed documentation, see `EMBEDDING_BATCH_DELIVERY_SUMMARY.md`
