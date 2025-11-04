# Resource Limits - Quick Start Guide

## TL;DR

```python
from core.limits import get_limiter, OverloadError, create_429_response

limiter = get_limiter()

# Use context manager (recommended)
try:
    with limiter.limit(user_id="user123", session_id="session456"):
        # Your code here - slot automatically managed
        result = process_request()
except OverloadError as e:
    # Return 429 with Retry-After
    return create_429_response(e), 429
```

---

## Quick Start

### 1. Basic Usage

```python
from core.limits import get_limiter

limiter = get_limiter()

# Execute with automatic resource management
with limiter.limit(user_id="user123"):
    process_request()
# Slot automatically released
```

### 2. Handle Overload (429 Responses)

```python
from core.limits import OverloadError, create_429_response

try:
    with limiter.limit(user_id="user123"):
        process_request()
except OverloadError as e:
    # e.message: "User queue full (10/10). Too many concurrent requests."
    # e.retry_after: 5 (seconds)
    
    response = create_429_response(e)
    # {
    #   "status": 429,
    #   "error": "too_many_requests", 
    #   "message": "...",
    #   "retry_after": 5
    # }
```

### 3. FastAPI Integration

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from core.limits import get_limiter, OverloadError, create_429_response

router = APIRouter()

@router.post("/api/chat")
async def chat(request: ChatRequest, limiter = Depends(get_limiter)):
    try:
        with limiter.limit(user_id=request.user_id):
            return await process_chat(request)
    except OverloadError as e:
        return JSONResponse(
            status_code=429,
            content=create_429_response(e),
            headers={"Retry-After": str(e.retry_after)}
        )
```

---

## Default Limits

| What | Default | When it Triggers |
|------|---------|------------------|
| Per-user concurrent | 3 | User has 3+ active requests |
| Per-user queue | 10 | User has 3 concurrent + 10 queued |
| Global concurrent | 100 | System has 100+ total requests |
| Global queue | 500 | System has 100 concurrent + 500 queued |
| Retry-After | 5s | Returned in 429 response |

---

## Configuration

### Via Environment Variables

```bash
# .env file
LIMITS_ENABLED=true
LIMITS_MAX_CONCURRENT_PER_USER=5
LIMITS_MAX_QUEUE_SIZE_PER_USER=20
LIMITS_MAX_CONCURRENT_GLOBAL=200
LIMITS_RETRY_AFTER_SECONDS=10
```

### Via Code

```python
from core.limits import ResourceLimiter, LimitConfig

config = LimitConfig(
    max_concurrent_per_user=5,
    max_queue_size_per_user=20,
    retry_after_seconds=10
)

limiter = ResourceLimiter(config)
```

---

## Common Patterns

### Pattern 1: API Endpoint Protection

```python
@router.post("/api/expensive-operation")
async def expensive_op(user_id: str, limiter = Depends(get_limiter)):
    try:
        with limiter.limit(user_id=user_id):
            return await expensive_operation()
    except OverloadError as e:
        return JSONResponse(
            status_code=429,
            content=create_429_response(e),
            headers={"Retry-After": str(e.retry_after)}
        )
```

### Pattern 2: Background Task Limiting

```python
def process_batch(user_id: str, items: list):
    try:
        with limiter.limit(user_id=user_id):
            for item in items:
                process_item(item)
    except OverloadError:
        # Requeue for later
        requeue_batch(user_id, items)
```

### Pattern 3: Multi-User Operations

```python
def bulk_process(user_ids: list):
    results = {}
    
    for user_id in user_ids:
        try:
            with limiter.limit(user_id=user_id):
                results[user_id] = process_user(user_id)
        except OverloadError as e:
            results[user_id] = {
                "error": "rate_limited",
                "retry_after": e.retry_after
            }
    
    return results
```

---

## Monitoring

### Check Current State

```python
stats = limiter.get_stats()

print(f"Global: {stats['global_concurrent']} concurrent, {stats['global_queue_size']} queued")
print(f"Users: {stats['total_users']} active")

for user in stats['users']:
    print(f"  {user['user_id']}: {user['concurrent']} concurrent, {user['queued']} queued")
```

### Track Overload Events

```python
from core.metrics import increment_counter

try:
    with limiter.limit(user_id=user_id):
        process()
except OverloadError:
    increment_counter("overload_events", labels={"user": user_id})
    raise
```

---

## Testing

### Unit Tests

```python
from core.limits import ResourceLimiter, LimitConfig, OverloadError

def test_my_handler():
    # Create test limiter
    config = LimitConfig(
        max_concurrent_per_user=1,
        max_queue_size_per_user=2
    )
    limiter = ResourceLimiter(config)
    
    # Fill capacity
    ctx1 = limiter.check_limits("user1")
    ctx2 = limiter.check_limits("user1")
    ctx3 = limiter.check_limits("user1")
    
    # Should trigger overload
    with pytest.raises(OverloadError):
        limiter.check_limits("user1")
    
    # Cleanup
    limiter.release(ctx1)
```

### Load Testing

```python
import concurrent.futures

def simulate_load():
    errors = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        for i in range(1000):
            future = executor.submit(make_request, f"user{i % 10}")
            futures.append(future)
        
        for future in futures:
            try:
                future.result()
            except OverloadError as e:
                errors.append(e)
    
    print(f"Overload rate: {len(errors)/1000*100:.1f}%")
```

---

## Troubleshooting

### Issue: Too many 429s

```python
# Check if limits are too restrictive
stats = limiter.get_stats()
print(stats['config'])

# Adjust limits
LIMITS_MAX_CONCURRENT_PER_USER=5  # Increase from 3
```

### Issue: Queue not draining

```python
# Check queue sizes
stats = limiter.get_stats()
for user in stats['users']:
    if user['queued'] > 10:
        print(f"User {user['user_id']} queue stuck at {user['queued']}")

# Possible causes:
# 1. Requests taking too long
# 2. Not enough concurrency
# 3. Deadlock in request processing
```

### Issue: Memory growing

```python
# Limiter cleans up stale users every 60s
# Force cleanup if needed:
limiter._cleanup_stale_users(force=True)

# Or reset for tests:
limiter.reset()
```

---

## Best Practices

### ✅ DO

- Use context manager for automatic cleanup
- Return 429 with Retry-After header
- Set reasonable limits based on capacity
- Monitor overload rates
- Test with simulated load

### ❌ DON'T

- Manually acquire/release (error-prone)
- Set limits too restrictive (poor UX)
- Ignore OverloadError (will crash)
- Use BLOCK policy in production (can cascade)
- Share limiter state across processes (use Redis)

---

## API Reference

### ResourceLimiter

```python
limiter = ResourceLimiter(config)

# Context manager (recommended)
with limiter.limit(user_id, session_id=None, request_id=None):
    ...

# Manual (advanced)
ctx = limiter.acquire(user_id)
try:
    ...
finally:
    limiter.release(ctx)

# Check without acquiring
ctx = limiter.check_limits(user_id)  # May raise OverloadError

# Get stats
stats = limiter.get_stats()

# Reset (testing)
limiter.reset()
```

### LimitConfig

```python
config = LimitConfig(
    max_concurrent_per_user=3,
    max_queue_size_per_user=10,
    max_concurrent_global=100,
    max_queue_size_global=500,
    retry_after_seconds=5,
    queue_timeout_seconds=30.0,
    overload_policy=OverloadPolicy.DROP_NEWEST
)
```

### OverloadError

```python
try:
    limiter.check_limits(user_id)
except OverloadError as e:
    print(e.message)        # Human-readable message
    print(e.retry_after)    # Seconds to wait
```

---

## Quick Examples

### Example 1: Simple Rate Limiting

```python
from core.limits import get_limiter, OverloadError

def api_handler(user_id: str):
    limiter = get_limiter()
    
    try:
        with limiter.limit(user_id):
            return {"result": "success"}
    except OverloadError as e:
        return {"error": "too_many_requests", "retry_after": e.retry_after}, 429
```

### Example 2: Graceful Degradation

```python
def process_with_fallback(user_id: str):
    try:
        with limiter.limit(user_id):
            return expensive_operation()
    except OverloadError:
        # Fall back to cached result
        return get_cached_result(user_id)
```

### Example 3: Priority Queue

```python
def process_with_priority(user_id: str, priority: str):
    if priority == "high":
        # High priority bypasses queue (use with caution)
        return process_immediately(user_id)
    else:
        # Normal priority respects limits
        with limiter.limit(user_id):
            return process_normal(user_id)
```

---

## Environment Variables Reference

```bash
# Feature toggle
LIMITS_ENABLED=true

# Per-user limits
LIMITS_MAX_CONCURRENT_PER_USER=3      # Max simultaneous per user
LIMITS_MAX_QUEUE_SIZE_PER_USER=10     # Max queued per user

# Global limits  
LIMITS_MAX_CONCURRENT_GLOBAL=100      # System-wide concurrent
LIMITS_MAX_QUEUE_SIZE_GLOBAL=500      # System-wide queue

# Behavior
LIMITS_RETRY_AFTER_SECONDS=5          # 429 Retry-After value
LIMITS_QUEUE_TIMEOUT_SECONDS=30.0     # Max queue wait time
LIMITS_OVERLOAD_POLICY=drop_newest    # drop_newest|drop_oldest|block
```

---

## Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Request processed |
| 408 | Timeout | Request timed out in queue |
| 429 | Too Many Requests | Queue full, retry later |
| 503 | Service Unavailable | System overloaded |

---

## Metrics to Track

```python
# Overload events
increment_counter("api_overload_429", labels={"user": user_id})

# Queue time
observe_histogram("api_queue_time_ms", ctx.queue_time * 1000)

# Active requests
set_gauge("api_concurrent_requests", limiter.get_stats()["global_concurrent"])

# Queue depth
set_gauge("api_queue_depth", limiter.get_stats()["global_queue_size"])
```

---

## Common Questions

**Q: What happens if I don't use a context manager?**
A: Slots won't be released automatically. Use `try/finally` with manual `release()`.

**Q: Can I use this across multiple processes?**
A: No, it's in-memory. For distributed limiting, integrate with Redis.

**Q: What's the performance overhead?**
A: <1ms per check. Lock contention is minimal.

**Q: Can I have different limits per API endpoint?**
A: Yes, create separate limiter instances with different configs.

**Q: What if a request crashes?**
A: Context manager ensures cleanup even on exception.

---

## Summary

✅ Import: `from core.limits import get_limiter, OverloadError`
✅ Use: `with limiter.limit(user_id): ...`
✅ Handle: `except OverloadError as e: return 429`
✅ Configure: Via env vars or `LimitConfig`
✅ Monitor: `limiter.get_stats()`

**See Also**:
- [Full Documentation](RESOURCE_LIMITS_SUMMARY.md)
- [Tests](tests/perf/test_limits.py)
- [Implementation](core/limits.py)

---

**Version**: 1.0
**Status**: Production Ready
**Last Updated**: 2025-11-04
