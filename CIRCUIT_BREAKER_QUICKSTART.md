# Circuit Breakers - Quick Reference

**TL;DR**: Circuit breakers prevent spamming failed services. Opens after N failures, cooldown period, half-open probe, auto-recovery on success.

---

## What It Does

Circuit breaker pattern for external services (Pinecone vector store, reviewer LLM):

- **Prevents service spam**: Stops calling failed services
- **Three states**: CLOSED (normal), OPEN (blocked), HALF_OPEN (testing)
- **Automatic recovery**: Half-open probe after cooldown
- **Rolling counters**: Tracks consecutive failures/successes
- **Graceful degradation**: Works with fallback systems

---

## Quick Start

### 1. Basic Usage

```python
from core.circuit import get_circuit_breaker, CircuitBreakerConfig, CircuitBreakerOpenError

# Get circuit breaker
breaker = get_circuit_breaker(
    "my_service",
    CircuitBreakerConfig(
        name="my_service",
        failure_threshold=5,     # Open after 5 failures
        cooldown_seconds=60.0,   # Wait 60s before retry
        success_threshold=2      # Close after 2 successes
    )
)

# Call through circuit breaker
try:
    result = breaker.call(my_function, arg1, arg2)
except CircuitBreakerOpenError:
    print("Circuit is open, service unavailable")
    result = fallback_function()
```

### 2. Health Checks

```python
from core.health import check_pinecone_health, check_reviewer_health

# Check Pinecone
result = check_pinecone_health()
if result.is_healthy:
    print(f"✅ Pinecone healthy ({result.latency_ms:.1f}ms)")
else:
    print(f"❌ Pinecone unhealthy: {result.error}")

# Check reviewer
result = check_reviewer_health()
print(f"Reviewer: {'✅' if result.is_healthy else '❌'}")
```

### 3. Check Circuit State

```python
from core.circuit import get_circuit_breaker

breaker = get_circuit_breaker("pinecone")
stats = breaker.get_stats()

print(f"State: {stats['state']}")
print(f"Consecutive failures: {stats['consecutive_failures']}")
print(f"Total failures: {stats['total_failures']}")
```

---

## Circuit States

### CLOSED (Normal Operation)

- **All calls allowed**
- Tracks consecutive failures
- Opens after `failure_threshold` reached

```python
breaker.get_state() == CircuitState.CLOSED
# can_execute() returns True
```

### OPEN (Service Down)

- **All calls rejected** immediately
- No actual service calls made
- Raises `CircuitBreakerOpenError`
- After `cooldown_seconds`, transitions to HALF_OPEN

```python
breaker.get_state() == CircuitState.OPEN
# can_execute() returns False
# Raises CircuitBreakerOpenError
```

### HALF_OPEN (Testing Recovery)

- **Single probe call** allowed at a time
- Success → Increment success counter
- After `success_threshold` successes → CLOSED
- Any failure → Back to OPEN

```python
breaker.get_state() == CircuitState.HALF_OPEN
# can_execute() returns True (for single probe)
```

---

## State Transitions

```
CLOSED ──(N failures)──> OPEN ──(cooldown)──> HALF_OPEN
   ↑                                               │
   │                                               │
   └────────────(M successes)──────────────────────┘
                                                    │
                                         (any failure)
                                                    ↓
                                                  OPEN
```

**Legend**:
- N = `failure_threshold` (default: 5)
- M = `success_threshold` (default: 2)
- Cooldown = `cooldown_seconds` (default: 60s)

---

## Configuration

### Default Configuration

```python
CircuitBreakerConfig(
    name="service_name",
    failure_threshold=5,        # Open after 5 consecutive failures
    cooldown_seconds=60.0,      # Wait 60s before half-open
    success_threshold=2,        # Close after 2 consecutive successes
    timeout_seconds=None        # Optional call timeout
)
```

### Pinecone Circuit Breaker

Already configured in `core/selection.py`:

```python
CircuitBreakerConfig(
    name="pinecone",
    failure_threshold=5,
    cooldown_seconds=60.0,
    success_threshold=2
)
```

### Reviewer Circuit Breaker

Already configured in `core/reviewer.py`:

```python
CircuitBreakerConfig(
    name="reviewer",
    failure_threshold=5,
    cooldown_seconds=60.0,
    success_threshold=2
)
```

---

## Integration

### DualSelector (Already Integrated)

Pinecone circuit breaker is automatically used:

```python
from core.selection import DualSelector

selector = DualSelector()

# Circuit breaker is consulted automatically
result = selector.select(
    query="machine learning",
    embedding=embedding_vector
)

# If circuit is open, automatically uses pgvector fallback
if result.fallback.get('used'):
    print(f"Using fallback: {result.fallback['reason']}")
```

### AnswerReviewer (Already Integrated)

Reviewer circuit breaker is automatically used:

```python
from core.reviewer import AnswerReviewer

reviewer = AnswerReviewer()

# Circuit breaker is consulted automatically
result = reviewer.review(
    answer="The answer is 42",
    context=context_items
)

# If circuit is open, review is skipped
if result.skipped:
    print(f"Review skipped: {result.skip_reason}")
```

---

## Common Patterns

### 1. Call with Fallback

```python
from core.circuit import get_circuit_breaker, CircuitBreakerOpenError

breaker = get_circuit_breaker("my_service")

try:
    result = breaker.call(primary_service_call)
except CircuitBreakerOpenError:
    # Circuit is open, use fallback
    result = fallback_service_call()
```

### 2. Pre-Check Before Call

```python
breaker = get_circuit_breaker("my_service")

if breaker.can_execute():
    result = breaker.call(service_call)
else:
    print("Circuit is open, skipping call")
    result = None
```

### 3. Monitor Circuit State

```python
import time
from core.circuit import get_circuit_breaker

breaker = get_circuit_breaker("pinecone")

while True:
    stats = breaker.get_stats()
    
    if stats['state'] == 'open':
        print(f"⚠️  Circuit OPEN: {stats['consecutive_failures']} failures")
    
    time.sleep(10)
```

### 4. Health Check Integration

```python
from core.circuit import get_circuit_breaker, CircuitBreakerOpenError
from core.health import check_pinecone_health

breaker = get_circuit_breaker("pinecone")

try:
    # Health check through circuit breaker
    health = breaker.call(check_pinecone_health)
    
    if not health.is_healthy:
        print(f"Service unhealthy: {health.error}")
except CircuitBreakerOpenError:
    print("Circuit open, service unavailable")
```

### 5. Manual Reset (Testing)

```python
from core.circuit import get_circuit_breaker

breaker = get_circuit_breaker("pinecone")

# Manually reset to CLOSED state
breaker.reset()

# Or reset all breakers
from core.circuit import reset_all_circuit_breakers
reset_all_circuit_breakers()
```

---

## Health Checks

### Pinecone Health Check

```python
from core.health import check_pinecone_health

result = check_pinecone_health()

print(f"Service: {result.service}")
print(f"Healthy: {result.is_healthy}")
print(f"Latency: {result.latency_ms:.1f}ms")

if not result.is_healthy:
    print(f"Error: {result.error}")
else:
    print(f"Total vectors: {result.details.get('total_vectors', 0)}")
```

**What it checks**:
- Pinecone client import
- Index availability
- `describe_index_stats()` operation
- Returns total vector count

### Reviewer Health Check

```python
from core.health import check_reviewer_health

result = check_reviewer_health()

if result.is_healthy:
    print(f"Reviewer ready: {result.details.get('status')}")
else:
    print(f"Reviewer unavailable: {result.error}")
```

**What it checks**:
- Reviewer enabled in config
- OpenAI client initialization
- Client readiness

### Check All Services

```python
from core.health import check_all_services

results = check_all_services()

for service, result in results.items():
    status = "✅" if result.is_healthy else "❌"
    print(f"{status} {service}: {result.latency_ms:.1f}ms")
```

---

## Metrics

### Counters

- `circuit_breaker.success{breaker,state}` - Successful calls
- `circuit_breaker.failure{breaker,state,error_type}` - Failed calls
- `circuit_breaker.rejected{breaker}` - Rejected calls
- `circuit_breaker.state_change{breaker,to_state}` - State transitions
- `health_check.success{service}` - Successful health checks
- `health_check.failure{service,error_type}` - Failed health checks

### Histograms

- `circuit_breaker.call_duration_ms{breaker,result}` - Call latency
- `health_check.latency_ms{service}` - Health check latency

### Example Queries (Prometheus)

```promql
# Circuit breaker state changes
rate(circuit_breaker_state_change_total[5m])

# Rejection rate
rate(circuit_breaker_rejected_total{breaker="pinecone"}[5m])

# Failure rate
rate(circuit_breaker_failure_total[5m]) by (breaker)

# Health check success rate
rate(health_check_success_total[5m]) / rate(health_check_total[5m])
```

---

## Troubleshooting

### Problem: Circuit keeps opening

**Check circuit stats**:
```python
breaker = get_circuit_breaker("pinecone")
stats = breaker.get_stats()

print(f"Consecutive failures: {stats['consecutive_failures']}")
print(f"Total failures: {stats['total_failures']}")
print(f"Total successes: {stats['total_successes']}")
```

**Check service health**:
```python
from core.health import check_pinecone_health

result = check_pinecone_health()
if not result.is_healthy:
    print(f"Service issue: {result.error}")
```

**Solutions**:
- Check service logs
- Verify API keys/credentials
- Increase `failure_threshold`
- Check network connectivity

### Problem: Circuit stuck open

**Check time since opening**:
```python
import time

stats = breaker.get_stats()
if stats['opened_at']:
    elapsed = time.time() - stats['opened_at']
    print(f"Circuit opened {elapsed:.1f}s ago")
    print(f"Cooldown: {stats['cooldown_seconds']}s")
    print(f"Remaining: {stats['cooldown_seconds'] - elapsed:.1f}s")
```

**Manual reset** (if service is healthy):
```python
breaker.reset()
```

### Problem: False positive failures

**Symptoms**:
- Circuit opens due to transient errors
- Service is actually healthy

**Solutions**:
```python
# Increase failure threshold
config = CircuitBreakerConfig(
    name="service",
    failure_threshold=10,  # More tolerant
    cooldown_seconds=30.0  # Shorter recovery
)

# Or add retry logic before circuit breaker
```

---

## Testing

### Unit Tests

```bash
# Run all circuit breaker tests
python3 -m unittest tests.perf.test_circuit_breaker -v
```

Expected: **19/19 tests passing**

### Integration Test

```python
#!/usr/bin/env python3
"""Test circuit breaker integration."""

from core.circuit import get_circuit_breaker, CircuitBreakerConfig, CircuitBreakerOpenError
import time

def test_circuit_breaker():
    # Create breaker
    breaker = get_circuit_breaker(
        "test",
        CircuitBreakerConfig(
            name="test",
            failure_threshold=3,
            cooldown_seconds=0.1,
            success_threshold=2
        )
    )
    
    # Fail 3 times to open
    for i in range(3):
        try:
            breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
    
    # Should be OPEN
    assert breaker.get_state().value == "open"
    
    # Should reject next call
    try:
        breaker.call(lambda: "attempt")
        assert False, "Should have raised CircuitBreakerOpenError"
    except CircuitBreakerOpenError:
        pass
    
    # Wait for cooldown
    time.sleep(0.15)
    
    # Should allow probe (HALF_OPEN)
    result = breaker.call(lambda: "probe1")
    assert result == "probe1"
    
    # Second success should close
    result = breaker.call(lambda: "probe2")
    assert result == "probe2"
    assert breaker.get_state().value == "closed"
    
    print("✅ Circuit breaker test passed")

if __name__ == "__main__":
    test_circuit_breaker()
```

### Smoke Test

```bash
python3 << 'EOF'
from core.circuit import get_circuit_breaker, CircuitBreakerConfig, CircuitState
from core.health import check_pinecone_health, check_reviewer_health

# Test circuit breaker creation
breaker = get_circuit_breaker("test", CircuitBreakerConfig(name="test"))
assert breaker.get_state() == CircuitState.CLOSED

# Test health checks exist
pinecone_health = check_pinecone_health()
assert hasattr(pinecone_health, 'is_healthy')

reviewer_health = check_reviewer_health()
assert hasattr(reviewer_health, 'is_healthy')

print("✅ Smoke test passed")
EOF
```

---

## API Reference

### CircuitBreaker

```python
class CircuitBreaker:
    def call(self, func: Callable, *args, **kwargs) -> Any
    def can_execute(self) -> bool
    def get_state(self) -> CircuitState
    def get_stats(self) -> Dict[str, Any]
    def reset(self) -> None
```

### CircuitBreakerConfig

```python
@dataclass
class CircuitBreakerConfig:
    name: str
    failure_threshold: int = 5
    cooldown_seconds: float = 60.0
    success_threshold: int = 2
    timeout_seconds: Optional[float] = None
```

### HealthCheckResult

```python
class HealthCheckResult:
    service: str
    is_healthy: bool
    latency_ms: float
    error: Optional[str]
    details: Dict[str, Any]
    timestamp: float
```

### Functions

```python
# Circuit breaker registry
def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker
def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]
def reset_all_circuit_breakers() -> None

# Health checks
def check_pinecone_health() -> HealthCheckResult
def check_reviewer_health() -> HealthCheckResult
def check_all_services() -> Dict[str, HealthCheckResult]
def is_service_healthy(service: str) -> bool
```

---

## Best Practices

### ✅ DO

- Use circuit breakers for all external service calls
- Monitor circuit state changes
- Combine with fallback systems
- Use health checks as probes
- Log when circuit opens/closes
- Configure thresholds based on service criticality

### ❌ DON'T

- Don't bypass circuit breaker for "important" calls
- Don't reset circuit breakers in production without investigation
- Don't set failure_threshold too low (avoid false positives)
- Don't ignore OPEN state (it's telling you something)
- Don't forget to implement fallbacks

---

## Examples

### Example 1: API Endpoint with Circuit Breaker

```python
from fastapi import APIRouter, HTTPException
from core.circuit import get_circuit_breaker, CircuitBreakerOpenError

router = APIRouter()

@router.get("/search")
def search(query: str):
    breaker = get_circuit_breaker("pinecone")
    
    try:
        results = breaker.call(
            search_pinecone,
            query=query
        )
        return {"results": results}
    
    except CircuitBreakerOpenError:
        # Circuit open, return cached results
        return {
            "results": get_cached_results(query),
            "warning": "Using cached results (service unavailable)"
        }
```

### Example 2: Background Task with Circuit Breaker

```python
from core.circuit import get_circuit_breaker, CircuitBreakerOpenError
import logging

logger = logging.getLogger(__name__)

def process_batch(items):
    breaker = get_circuit_breaker("external_api")
    
    results = []
    for item in items:
        try:
            result = breaker.call(process_item, item)
            results.append(result)
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit open, skipping item {item.id}")
            results.append(None)
    
    return results
```

### Example 3: Circuit Breaker Dashboard

```python
from core.circuit import get_all_circuit_breakers

def get_circuit_breaker_dashboard():
    """Get dashboard data for all circuit breakers."""
    breakers = get_all_circuit_breakers()
    
    dashboard = {}
    for name, breaker in breakers.items():
        stats = breaker.get_stats()
        dashboard[name] = {
            "state": stats['state'],
            "health": "🟢" if stats['state'] == 'closed' else "🔴" if stats['state'] == 'open' else "🟡",
            "consecutive_failures": stats['consecutive_failures'],
            "total_failures": stats['total_failures'],
            "total_successes": stats['total_successes'],
            "success_rate": f"{100 * stats['total_successes'] / max(stats['total_successes'] + stats['total_failures'], 1):.1f}%"
        }
    
    return dashboard

# Use in API
@router.get("/debug/circuit-breakers")
def get_circuit_breaker_status():
    return get_circuit_breaker_dashboard()
```

---

## Related Docs

- **Implementation Details**: `CIRCUIT_BREAKER_IMPLEMENTATION.md`
- **Pgvector Fallback**: `PGVECTOR_FALLBACK_QUICKSTART.md`
- **Performance Flags**: `PERF_FLAGS_QUICKSTART.md`

---

## Summary

**Circuit breakers provide automatic failure protection**:

- ✅ Prevents spamming failed services
- ✅ Three-state machine (CLOSED/OPEN/HALF_OPEN)
- ✅ Automatic recovery with probes
- ✅ Rolling failure counters
- ✅ Configurable thresholds
- ✅ Integrated with Pinecone and reviewer
- ✅ Health probes for monitoring

**Key Benefit**: Services degrade gracefully when dependencies fail. Circuit breakers prevent cascading failures and enable automatic recovery without manual intervention.

**Production Ready**: 19/19 tests passing, thread-safe implementation, comprehensive metrics, integrated with critical services.
