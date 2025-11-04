# Circuit Breakers - Quick Reference

## What It Does

Implements circuit breaker pattern to prevent cascading failures and service spam during outages. Automatically opens after consecutive failures, prevents calls during cooldown, and recovers gracefully.

## Key Concepts

**Three States**:
- **CLOSED**: Normal operation, all calls allowed
- **OPEN**: Service failing, all calls rejected
- **HALF_OPEN**: Testing recovery with probe calls

**Transitions**:
```
CLOSED --[N failures]--> OPEN --[cooldown]--> HALF_OPEN --[success]--> CLOSED
                          ^                        |
                          └────────[failure]───────┘
```

## Quick Start

### 1. Create Circuit Breaker

```python
from core.circuit import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    name="my_service",
    failure_threshold=5,      # Open after 5 failures
    cooldown_seconds=60.0,    # Wait 60s before retry
    success_threshold=2       # Close after 2 successes
)

breaker = CircuitBreaker(config)
```

### 2. Wrap Service Calls

```python
from core.circuit import CircuitBreakerOpenError

try:
    result = breaker.call(external_api_call, arg1, arg2)
except CircuitBreakerOpenError:
    # Circuit open - use fallback
    result = fallback_logic()
```

### 3. Monitor State

```python
# Check current state
state = breaker.get_state()
print(f"Circuit is {state.value}")

# Get statistics
stats = breaker.get_stats()
print(f"Failures: {stats['consecutive_failures']}")
print(f"Opened at: {stats['opened_at']}")
```

## Health Checks

### Check Service Health

```python
from core.health import check_pinecone_health, check_reviewer_health

# Pinecone
result = check_pinecone_health()
if result.is_healthy:
    print(f"Pinecone OK ({result.latency_ms:.1f}ms)")
else:
    print(f"Pinecone DOWN: {result.error}")

# Reviewer
result = check_reviewer_health()
print(f"Reviewer: {'✓' if result.is_healthy else '✗'}")
```

### Use in Circuit Breaker

```python
# Health check as probe
def health_probe():
    result = check_pinecone_health()
    if not result.is_healthy:
        raise Exception(result.error)
    return result

# Use with breaker
try:
    health = breaker.call(health_probe)
except CircuitBreakerOpenError:
    print("Circuit open, service unavailable")
```

## Integration

### Pinecone (Already Integrated)

```python
from core.selection import DualSelector

selector = DualSelector()

# Circuit breaker applied automatically
result = selector.select(
    query="test",
    embedding=[0.1] * 1536
)

# Check if fallback was used
if result.fallback.get('used'):
    print(f"Used fallback: {result.fallback['reason']}")
```

### Custom Service

```python
from core.circuit import get_circuit_breaker, CircuitBreakerConfig

# Get or create breaker
breaker = get_circuit_breaker(
    "my_service",
    CircuitBreakerConfig(name="my_service")
)

# Use it
def call_service():
    return my_service.do_something()

result = breaker.call(call_service)
```

## Configuration

### Default Settings

| Setting | Pinecone | Reviewer |
|---------|----------|----------|
| Failure threshold | 5 | 5 |
| Cooldown (seconds) | 60 | 60 |
| Success threshold | 2 | 2 |

### Custom Configuration

```python
# More aggressive
config = CircuitBreakerConfig(
    name="fast_fail",
    failure_threshold=3,      # Open faster
    cooldown_seconds=30.0,    # Shorter cooldown
    success_threshold=1       # Close immediately
)

# More tolerant
config = CircuitBreakerConfig(
    name="slow_fail",
    failure_threshold=10,     # More failures allowed
    cooldown_seconds=120.0,   # Longer cooldown
    success_threshold=3       # Multiple successes required
)
```

## Metrics

Monitor circuit breakers via metrics:

```python
# Circuit breaker events
circuit_breaker.success{breaker="pinecone",state="closed"}
circuit_breaker.failure{breaker="pinecone",state="closed",error_type="TimeoutError"}
circuit_breaker.rejected{breaker="pinecone"}
circuit_breaker.state_change{breaker="pinecone",to_state="open"}

# Call duration
circuit_breaker.call_duration_ms{breaker="pinecone",result="success"}

# Health checks
health_check.success{service="pinecone"}
health_check.failure{service="pinecone",error_type="ConnectionError"}
health_check.latency_ms{service="pinecone"}
```

## Troubleshooting

### Circuit Keeps Opening

**Possible causes**:
1. Service is genuinely down
2. Threshold too low
3. Network issues

**Solutions**:
```python
# Check service health
result = check_pinecone_health()
print(f"Health: {result.is_healthy}, Error: {result.error}")

# Review stats
stats = breaker.get_stats()
print(f"Failure rate: {stats['total_failures']/stats['total_successes']}")

# Adjust threshold
config.failure_threshold = 10  # More tolerant
```

### Circuit Stuck Open

**Possible causes**:
1. Cooldown not expired
2. Health check failing
3. Service still down

**Solutions**:
```python
# Check opened_at time
stats = breaker.get_stats()
elapsed = time.time() - stats['opened_at']
print(f"Open for {elapsed:.1f}s, cooldown: {config.cooldown_seconds}s")

# Manual reset (use with caution)
breaker.reset()
```

### Half-Open Not Closing

**Possible causes**:
1. Probe calls failing
2. Success threshold not met
3. Intermittent failures

**Solutions**:
```python
# Check consecutive successes
stats = breaker.get_stats()
print(f"Successes: {stats['consecutive_successes']}/{config.success_threshold}")

# Lower success threshold
config.success_threshold = 1  # Close faster
```

## Best Practices

### 1. Use Registry

```python
# DON'T create multiple instances
breaker1 = CircuitBreaker(config)
breaker2 = CircuitBreaker(config)  # Different instance!

# DO use registry
breaker = get_circuit_breaker("service", config)
```

### 2. Always Have Fallback

```python
# DON'T just fail
result = breaker.call(service_call)

# DO provide fallback
try:
    result = breaker.call(service_call)
except CircuitBreakerOpenError:
    result = fallback_implementation()
```

### 3. Monitor State Changes

```python
# Track state changes
prev_state = breaker.get_state()

# After operation
new_state = breaker.get_state()
if prev_state != new_state:
    log.warning(f"Circuit {breaker.config.name}: {prev_state} → {new_state}")
```

### 4. Set Appropriate Thresholds

```python
# Critical services: Fail fast
critical_config = CircuitBreakerConfig(
    name="critical",
    failure_threshold=3,
    cooldown_seconds=30.0
)

# Non-critical: More tolerant
noncritical_config = CircuitBreakerConfig(
    name="noncritical",
    failure_threshold=10,
    cooldown_seconds=120.0
)
```

## Testing

### Unit Tests

```python
from core.circuit import CircuitBreaker, CircuitBreakerConfig, CircuitState

def test_opens_on_failure():
    config = CircuitBreakerConfig(name="test", failure_threshold=3)
    breaker = CircuitBreaker(config)
    
    for i in range(3):
        with pytest.raises(Exception):
            breaker.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
    
    assert breaker.get_state() == CircuitState.OPEN
```

### Integration Tests

```python
def test_with_fallback():
    breaker = get_circuit_breaker("test")
    
    # Simulate failures
    for i in range(5):
        with pytest.raises(Exception):
            breaker.call(failing_service)
    
    # Next call should use fallback
    result = get_with_breaker_and_fallback(breaker, failing_service, fallback)
    assert result == fallback_result
```

## API Reference

### CircuitBreaker Methods

- `call(func, *args, **kwargs)` - Execute function through breaker
- `can_execute()` - Check if calls allowed
- `get_state()` - Get current state
- `get_stats()` - Get statistics
- `reset()` - Manually reset to CLOSED

### Health Check Functions

- `check_pinecone_health()` - Check Pinecone status
- `check_reviewer_health()` - Check reviewer LLM status
- `check_all_services()` - Check all services
- `is_service_healthy(name)` - Quick health check

### Registry Functions

- `get_circuit_breaker(name, config)` - Get or create breaker
- `get_all_circuit_breakers()` - List all breakers
- `reset_all_circuit_breakers()` - Reset all (testing)

## Related

- `CIRCUIT_BREAKER_DELIVERY_SUMMARY.md` - Full delivery report
- `PGVECTOR_FALLBACK_QUICKSTART.md` - Fallback integration
- `core/circuit.py` - Implementation
- `core/health.py` - Health checks
- `tests/perf/test_circuit_breaker.py` - Test examples
