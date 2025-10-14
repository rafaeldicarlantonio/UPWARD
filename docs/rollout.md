# REDO Rollout Guide

This document describes the rollout process for REDO (Retrieval Enhancement and Dynamic Orchestration) functionality, including feature flags, fallback mechanisms, and disaster recovery procedures.

## Overview

REDO introduces advanced retrieval orchestration with contradiction detection and evidence ordering. The system includes robust fallback mechanisms to ensure service continuity during rollout and in case of failures.

## Architecture

### Core Components

- **Central Guard**: `is_redo_active()` function that determines if REDO should be enabled
- **Fallback Manager**: `RedoFallbackManager` that tracks health and manages circuit breakers
- **Safe Execution**: Context managers for orchestrator and ledger operations with automatic fallback
- **Health Monitoring**: Continuous health checks and failure tracking

### Feature Flags

| Flag | Default | Description |
|------|---------|-------------|
| `orchestrator.redo_enabled` | `false` | Enables REDO orchestrator functionality |
| `ledger.enabled` | `false` | Enables ledger persistence for orchestration traces |

## Rollout Sequence

### Phase 1: Infrastructure Preparation

1. **Deploy Code**: Deploy REDO code with all feature flags disabled
2. **Verify Health**: Ensure all components are healthy and fallback mechanisms work
3. **Test Fallbacks**: Run fallback tests to verify graceful degradation

```bash
# Test fallback system
python3 tests/test_fallbacks.py

# Verify REDO is inactive by default
python3 -c "
from core.fallbacks import is_redo_active
print('REDO active:', is_redo_active())
"
```

### Phase 2: Gradual Rollout

1. **Enable Orchestrator**: Set `orchestrator.redo_enabled=true` for a small percentage of traffic
2. **Monitor Metrics**: Watch for errors, latency increases, and fallback activations
3. **Enable Ledger**: Set `ledger.enabled=true` once orchestrator is stable

```bash
# Enable orchestrator for 10% of traffic
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": true, "rollout_percentage": 10}'

# Monitor health status
curl /debug/fallback-health
```

### Phase 3: Full Rollout

1. **Increase Traffic**: Gradually increase rollout percentage to 100%
2. **Enable Ledger**: Enable ledger persistence once orchestrator is stable
3. **Monitor Performance**: Ensure all metrics remain within acceptable ranges

```bash
# Full rollout
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": true, "ledger.enabled": true, "rollout_percentage": 100}'
```

## Feature Flag Management

### Setting Flags

```python
from feature_flags import set_feature_flag

# Enable REDO orchestrator
set_feature_flag("orchestrator.redo_enabled", True)

# Enable ledger persistence
set_feature_flag("ledger.enabled", True)
```

### Checking Status

```python
from core.fallbacks import is_redo_active, get_fallback_manager

# Check if REDO is active
feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": True}
is_active = is_redo_active(feature_flags)

# Get detailed health status
manager = get_fallback_manager()
health = manager.get_health_status()
print(f"Orchestrator healthy: {health['orchestrator_healthy']}")
print(f"Ledger healthy: {health['ledger_healthy']}")
print(f"Consecutive failures: {health['consecutive_failures']}")
```

## Fallback Mechanisms

### Automatic Fallbacks

The system includes several automatic fallback mechanisms:

1. **Feature Flag Check**: REDO is disabled if `orchestrator.redo_enabled=false`
2. **Health Checks**: REDO is disabled if components are unhealthy
3. **Circuit Breaker**: REDO is disabled after consecutive failures
4. **Timeout Protection**: Operations timeout and fallback to legacy path

### Fallback Scenarios

| Scenario | Behavior | Recovery |
|----------|----------|----------|
| Orchestrator Failure | Falls back to legacy selection | Automatic after circuit breaker reset |
| Ledger Failure | Continues with orchestrator, skips ledger | Automatic retry on next request |
| Database Unavailable | Falls back to legacy selection | Automatic when database recovers |
| High Latency | Circuit breaker opens | Automatic after reset period |

## Monitoring and Alerting

### Key Metrics

- `redo.active`: Whether REDO is currently active
- `redo.orchestrator.failures`: Number of orchestrator failures
- `redo.ledger.failures`: Number of ledger failures
- `redo.fallback.activations`: Number of fallback activations
- `redo.circuit_breaker.state`: Circuit breaker state (open/closed)

### Health Endpoints

```bash
# Check overall health
curl /debug/fallback-health

# Check feature flags
curl /debug/config

# Check metrics
curl /debug/metrics
```

### Alerting Rules

```yaml
# High failure rate
- alert: RedoHighFailureRate
  expr: rate(redo_orchestrator_failures_total[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High REDO orchestrator failure rate"

# Circuit breaker open
- alert: RedoCircuitBreakerOpen
  expr: redo_circuit_breaker_open == 1
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "REDO circuit breaker is open"

# Fallback activations
- alert: RedoFallbackActivations
  expr: rate(redo_fallback_activations_total[5m]) > 0.05
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High REDO fallback activation rate"
```

## Rollback Procedures

### Emergency Rollback

If critical issues are detected, immediately disable REDO:

```bash
# Disable all REDO functionality
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": false, "ledger.enabled": false}'

# Verify rollback
curl /debug/fallback-health
```

### Gradual Rollback

For non-critical issues, gradually reduce traffic:

```bash
# Reduce to 50% traffic
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": true, "rollout_percentage": 50}'

# Further reduce to 10%
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": true, "rollout_percentage": 10}'

# Complete rollback
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": false}'
```

### Component-Specific Rollback

If only one component is problematic:

```bash
# Disable only ledger
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": true, "ledger.enabled": false}'

# Disable only orchestrator
curl -X POST /admin/feature-flags \
  -d '{"orchestrator.redo_enabled": false, "ledger.enabled": true}'
```

## Testing Procedures

### Pre-Rollout Testing

```bash
# Run all fallback tests
python3 tests/test_fallbacks.py

# Test with simulated failures
python3 -c "
from core.fallbacks import simulate_db_failure, simulate_orchestrator_failure
from core.fallbacks import is_redo_active

# Test DB failure fallback
simulate_db_failure()
print('After DB failure:', is_redo_active({'orchestrator.redo_enabled': True}))

# Test orchestrator failure fallback
simulate_orchestrator_failure()
print('After orchestrator failure:', is_redo_active({'orchestrator.redo_enabled': True}))
"
```

### Post-Rollout Testing

```bash
# Verify REDO is working
curl -X POST /chat \
  -d '{"prompt": "Test query", "debug": true}' \
  -H "Content-Type: application/json"

# Check for REDO metrics in response
# Should include: orchestration_enabled, orchestration_time_ms, etc.
```

## Configuration

### Fallback Configuration

```python
from core.fallbacks import FallbackConfig, RedoFallbackManager

config = FallbackConfig(
    enable_health_checks=True,
    health_check_interval_seconds=30.0,
    max_consecutive_failures=3,
    fallback_timeout_seconds=5.0,
    enable_circuit_breaker=True,
    circuit_breaker_reset_seconds=60.0
)

manager = RedoFallbackManager(config)
```

### Environment Variables

```bash
# REDO configuration
export ORCHESTRATOR_REDO_ENABLED=false
export LEDGER_ENABLED=false
export ORCHESTRATION_TIME_BUDGET_MS=400
export LEDGER_MAX_TRACE_BYTES=100000

# Fallback configuration
export REDO_HEALTH_CHECK_INTERVAL=30
export REDO_MAX_CONSECUTIVE_FAILURES=3
export REDO_CIRCUIT_BREAKER_RESET=60
```

## Troubleshooting

### Common Issues

1. **REDO Not Activating**
   - Check feature flags: `curl /debug/config`
   - Verify health status: `curl /debug/fallback-health`
   - Check logs for error messages

2. **High Fallback Rate**
   - Check orchestrator health
   - Verify database connectivity
   - Review timeout settings

3. **Circuit Breaker Stuck Open**
   - Check consecutive failure count
   - Verify error resolution
   - Manually reset if needed: `python3 -c "from core.fallbacks import reset_fallback_state; reset_fallback_state()"`

### Debug Commands

```bash
# Check feature flags
python3 -c "
from feature_flags import get_all_flags
print('Feature flags:', get_all_flags())
"

# Check health status
python3 -c "
from core.fallbacks import get_fallback_manager
manager = get_fallback_manager()
print('Health status:', manager.get_health_status())
"

# Test REDO activation
python3 -c "
from core.fallbacks import is_redo_active
flags = {'orchestrator.redo_enabled': True, 'ledger.enabled': True}
print('REDO active:', is_redo_active(flags))
"
```

## Success Criteria

### Rollout Success

- [ ] All fallback tests pass
- [ ] REDO activates correctly with feature flags
- [ ] Fallback mechanisms work as expected
- [ ] No increase in error rates
- [ ] Latency remains within acceptable limits
- [ ] Monitoring and alerting are functional

### Rollback Success

- [ ] Feature flags can be disabled immediately
- [ ] System falls back to legacy behavior
- [ ] No data loss or corruption
- [ ] Service remains available throughout rollback
- [ ] Metrics return to baseline levels

## Support

For issues or questions during rollout:

1. Check this documentation first
2. Review logs for error messages
3. Use debug endpoints to diagnose issues
4. Escalate to the REDO team if needed

## Changelog

- **v1.0.0**: Initial rollout documentation
- **v1.1.0**: Added circuit breaker configuration
- **v1.2.0**: Enhanced monitoring and alerting