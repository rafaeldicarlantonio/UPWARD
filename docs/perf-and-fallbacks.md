# Performance and Fallbacks - Operator Runbook

**Version**: 1.0  
**Last Updated**: 2025-11-04  
**Target Audience**: DevOps, SRE, Platform Engineers

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Performance Flags](#performance-flags)
3. [Circuit Breakers](#circuit-breakers)
4. [Latency Budgets](#latency-budgets)
5. [Resource Limits](#resource-limits)
6. [Fallback Mechanisms](#fallback-mechanisms)
7. [Checking Metrics (p95, etc.)](#checking-metrics)
8. [Responding to Budget Breaches](#responding-to-budget-breaches)
9. [Common Operations](#common-operations)
10. [Troubleshooting](#troubleshooting)
11. [Dashboards and Monitoring](#dashboards-and-monitoring)

---

## Quick Reference

### Emergency Actions

```bash
# System overloaded - increase resource limits
export LIMITS_MAX_CONCURRENT_GLOBAL=200
export LIMITS_MAX_QUEUE_SIZE_GLOBAL=1000
restart-service

# Pinecone down - enable pgvector fallback
export PERF_PGVECTOR_ENABLED=true
export PERF_FALLBACKS_ENABLED=true
restart-service

# Latency issues - relax budgets temporarily
export LATENCY_SLACK_PERCENT=10
# Then investigate root cause

# Complete outage - circuit breaker open
# Check logs: grep "circuit_breaker" /var/log/app.log
# Wait for auto-reset (60s default) or restart service
```

### Health Checks

```bash
# Overall health
curl http://localhost:8000/healthz

# Debug router status
curl http://localhost:8000/debug/routers

# Self-test (DB, Pinecone)
curl http://localhost:8000/debug/selftest
```

---

## Performance Flags

### Overview

Performance flags control timeouts, parallel execution, and fallback behavior.

### Configuration

Located in `config.py` under `DEFAULTS`:

```python
# Performance and fallback flags
"PERF_RETRIEVAL_PARALLEL": True,
"PERF_RETRIEVAL_TIMEOUT_MS": 450,
"PERF_GRAPH_TIMEOUT_MS": 150,
"PERF_COMPARE_TIMEOUT_MS": 400,
"PERF_REVIEWER_ENABLED": True,
"PERF_REVIEWER_BUDGET_MS": 500,
"PERF_PGVECTOR_ENABLED": True,
"PERF_FALLBACKS_ENABLED": True,
```

### Environment Variables

Set via `.env` or environment:

```bash
# Retrieval settings
PERF_RETRIEVAL_PARALLEL=true          # Enable parallel Pinecone + graph retrieval
PERF_RETRIEVAL_TIMEOUT_MS=450         # Timeout for retrieval operations

# Graph expansion
PERF_GRAPH_TIMEOUT_MS=150             # Timeout for graph traversal

# Comparison
PERF_COMPARE_TIMEOUT_MS=400           # Timeout for internal comparisons

# Reviewer
PERF_REVIEWER_ENABLED=true            # Enable answer review
PERF_REVIEWER_BUDGET_MS=500           # Max time for reviewer

# Fallbacks
PERF_PGVECTOR_ENABLED=true            # Enable pgvector fallback
PERF_FALLBACKS_ENABLED=true           # Enable all fallback mechanisms
```

### Checking Current Flags

```bash
# Via debug endpoint
curl http://localhost:8000/debug/config | jq '.PERF_RETRIEVAL_PARALLEL'

# Via Python
python3 << 'EOF'
from config import load_config
cfg = load_config()
print(f"Parallel: {cfg['PERF_RETRIEVAL_PARALLEL']}")
print(f"PGVector: {cfg['PERF_PGVECTOR_ENABLED']}")
print(f"Fallbacks: {cfg['PERF_FALLBACKS_ENABLED']}")
EOF
```

### Modifying Flags at Runtime

**⚠️ Warning**: Most flags require service restart.

```bash
# Update .env file
echo "PERF_RETRIEVAL_TIMEOUT_MS=600" >> .env

# Restart service
systemctl restart app
# or
supervisorctl restart app
# or
pkill -HUP python  # if using gunicorn
```

---

## Circuit Breakers

### Overview

Circuit breakers prevent cascading failures by opening when error rates exceed thresholds.

### Configuration

```bash
# Enable circuit breaker
CIRCUIT_BREAKER_ENABLED=true

# Failure threshold
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5   # Consecutive failures to open

# Reset timeout
CIRCUIT_BREAKER_RESET_TIMEOUT=60      # Seconds before auto-reset
```

### Circuit Breaker States

| State | Meaning | Behavior |
|-------|---------|----------|
| **CLOSED** | Normal operation | All requests allowed |
| **OPEN** | Circuit tripped | All requests fail fast |
| **HALF-OPEN** | Testing recovery | Limited requests allowed |

### Checking Circuit Breaker Status

```bash
# Via metrics endpoint
curl http://localhost:8000/metrics | grep circuit_breaker

# Via logs
grep "circuit_breaker" /var/log/app.log | tail -20

# Via Python
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace')
from core.circuit import get_circuit_breaker

breaker = get_circuit_breaker()
stats = breaker.get_stats()
print(f"State: {stats['state']}")
print(f"Failures: {stats['failure_count']}")
EOF
```

### Manually Resetting Circuit Breaker

```bash
# Option 1: Restart service (circuit breaker resets)
systemctl restart app

# Option 2: Via API (if implemented)
curl -X POST http://localhost:8000/admin/circuit-breaker/reset \
  -H "X-API-Key: $ADMIN_API_KEY"

# Option 3: Via Python
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace')
from core.circuit import get_circuit_breaker
get_circuit_breaker().reset()
print("Circuit breaker reset")
EOF
```

---

## Latency Budgets

### Overview

Latency budgets enforce p95 SLOs for critical operations.

### Default Budgets

| Operation | p95 Budget | Notes |
|-----------|------------|-------|
| Retrieval (dual-index) | 500ms | Pinecone + graph |
| Graph expansion | 200ms | Entity traversal |
| Context packing | 550ms | Prompt assembly |
| Reviewer call | 500ms | When enabled |
| Overall /chat | 1200ms | End-to-end |

### Configuration

```bash
# Located in evals/latency.py
# Or configure slack for flexibility:
LATENCY_SLACK_PERCENT=10   # Allow 10% slack on budgets
```

### Checking Latency Budgets

```bash
# Run latency gate checks
cd /workspace
python3 evals/latency.py --verbose

# Expected output:
# ✅ Retrieval (dual-index) p95: 450ms ≤ 500ms
# ✅ Context packing p95: 500ms ≤ 550ms
# ✅ Overall /chat p95: 1000ms ≤ 1200ms
```

### When Budgets Are Breached

See [Responding to Budget Breaches](#responding-to-budget-breaches) below.

---

## Resource Limits

### Overview

Resource limits prevent DoS and resource exhaustion via per-user concurrency caps and queues.

### Default Limits

| Limit | Default | Description |
|-------|---------|-------------|
| Per-user concurrent | 3 | Max simultaneous requests per user |
| Per-user queue | 10 | Max queued requests per user |
| Global concurrent | 100 | System-wide concurrent requests |
| Global queue | 500 | System-wide queue size |
| Retry-After | 5s | Header value for 429 responses |

### Configuration

```bash
# Resource limits
LIMITS_ENABLED=true
LIMITS_MAX_CONCURRENT_PER_USER=3
LIMITS_MAX_QUEUE_SIZE_PER_USER=10
LIMITS_MAX_CONCURRENT_GLOBAL=100
LIMITS_MAX_QUEUE_SIZE_GLOBAL=500
LIMITS_RETRY_AFTER_SECONDS=5
LIMITS_QUEUE_TIMEOUT_SECONDS=30.0
LIMITS_OVERLOAD_POLICY=drop_newest   # or drop_oldest, block
```

### Checking Resource Usage

```bash
# Via Python
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace')
from core.limits import get_limiter

limiter = get_limiter()
stats = limiter.get_stats()

print(f"Global concurrent: {stats['global_concurrent']}/{stats['config']['max_concurrent_global']}")
print(f"Global queue: {stats['global_queue_size']}/{stats['config']['max_queue_size_global']}")
print(f"Active users: {stats['total_users']}")

for user in stats['users'][:5]:  # Top 5 users
    print(f"  {user['user_id']}: {user['concurrent']} concurrent, {user['queued']} queued")
EOF
```

### Adjusting Limits Under Load

```bash
# Increase global limits (requires restart)
echo "LIMITS_MAX_CONCURRENT_GLOBAL=200" >> .env
echo "LIMITS_MAX_QUEUE_SIZE_GLOBAL=1000" >> .env
systemctl restart app

# Monitor impact
watch -n 5 'curl -s http://localhost:8000/metrics | grep -E "(concurrent|queue)"'
```

---

## Fallback Mechanisms

### Overview

Fallbacks provide degraded service when primary systems fail.

### pgvector Fallback (Primary Fallback)

**When**: Pinecone is slow, down, or returning errors  
**Fallback**: Use local pgvector for embeddings retrieval

#### Enabling pgvector Fallback

```bash
# Via environment variables
export PERF_PGVECTOR_ENABLED=true
export PERF_FALLBACKS_ENABLED=true

# Restart service
systemctl restart app
```

#### Testing pgvector Fallback

```bash
# Simulate Pinecone failure
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Pinecone-Failure: true" \
  -d '{
    "prompt": "What is machine learning?",
    "session_id": "test_fallback_123"
  }'

# Check response for fallback indicators
# Response should have: "metrics": { "pgvector_fallback_used": true }
```

#### Checking Fallback Usage

```bash
# Via metrics
curl http://localhost:8000/metrics | grep fallback

# Via smoke test tool
python3 tools/load_smoke.py --pinecone-down --requests 20

# Expected: High fallback rate but low error rate
```

### External Sources Fallback

**When**: Internal retrieval insufficient  
**Fallback**: Query external sources (if enabled)

```bash
# Enable external fallback
FACTARE_ENABLED=true
FACTARE_ALLOW_EXTERNAL=true
FACTARE_EXTERNAL_TIMEOUT_MS=2000

# Restart service
systemctl restart app
```

### Reviewer Fallback

**When**: Reviewer times out or fails  
**Fallback**: Skip review, proceed with answer

```bash
# Enable reviewer with timeout
PERF_REVIEWER_ENABLED=true
PERF_REVIEWER_BUDGET_MS=500

# If reviewer fails, answer still returned (without review)
```

---

## Checking Metrics

### p95 Latency

#### Method 1: Via Latency Gate Script

```bash
cd /workspace
python3 evals/latency.py --verbose

# Output:
# ✅ Retrieval (dual-index) p95: 450.0ms ≤ 500.0ms (budget: 500ms, count: 100)
# ✅ Context packing p95: 500.0ms ≤ 550.0ms (budget: 550ms, count: 100)
# ✅ Overall /chat p95: 1000.0ms ≤ 1200.0ms (budget: 1200ms, count: 50)
```

#### Method 2: Via Python

```python
import sys
sys.path.insert(0, '/workspace')
from core.metrics import get_histogram_stats

stats = get_histogram_stats("chat_total_ms")
print(f"p50: {stats['p50']:.2f}ms")
print(f"p95: {stats['p95']:.2f}ms")
print(f"p99: {stats['p99']:.2f}ms")
print(f"Count: {stats['count']}")
```

#### Method 3: Via Smoke Test

```bash
# Run smoke test to generate metrics
python3 tools/load_smoke.py --requests 50 --concurrency 10

# Output includes:
# Latency (successful requests):
#   p50: 725.34ms
#   p95: 1423.56ms
#   p99: 1987.23ms
```

### Success Rate

```bash
# Via smoke test
python3 tools/load_smoke.py --requests 50 | grep "Success Rates"

# Output:
# Success Rates:
#   Successful: 49/50 (98.0%)
#   Failed: 1/50 (2.0%)
```

### Fallback Rate

```bash
# Via smoke test
python3 tools/load_smoke.py --requests 50 | grep "Fallbacks"

# Output:
#   Fallbacks: 8/50 (16.0%)
```

### Throughput

```bash
# Via smoke test
python3 tools/load_smoke.py --requests 50 | grep "Throughput"

# Output:
# Throughput:
#   Requests: 50
#   Duration: 8.23s
#   Throughput: 6.08 req/s
```

---

## Responding to Budget Breaches

### Latency Budget Breach

**Symptom**: p95 latency exceeds budget (e.g., 1800ms > 1500ms)

**Investigation Steps**:

1. **Check recent changes**
   ```bash
   git log --oneline --since="24 hours ago"
   # Review for performance-impacting changes
   ```

2. **Check external dependencies**
   ```bash
   # Test Pinecone latency
   curl -X POST https://api.pinecone.io/... -w "\nTime: %{time_total}s\n"
   
   # Test database
   psql -c "SELECT pg_sleep(0); SELECT now();"  # Should be instant
   ```

3. **Check system resources**
   ```bash
   # CPU usage
   top -bn1 | head -20
   
   # Memory usage
   free -h
   
   # Disk I/O
   iostat -x 1 5
   ```

4. **Profile slow operations**
   ```bash
   # Run with profiling
   python3 -m cProfile -s cumtime app.py > profile.txt
   
   # Analyze hot paths
   grep -E "(chat|retrieval|packing)" profile.txt | head -20
   ```

**Remediation**:

- **Immediate**: Increase slack temporarily
  ```bash
  export LATENCY_SLACK_PERCENT=20
  systemctl restart app
  ```

- **Short-term**: Increase timeouts
  ```bash
  export PERF_RETRIEVAL_TIMEOUT_MS=600
  export PERF_GRAPH_TIMEOUT_MS=200
  systemctl restart app
  ```

- **Long-term**: Optimize hot paths, add caching, scale infrastructure

### Resource Limit Breach

**Symptom**: High 429 rate, users reporting "too many requests"

**Investigation Steps**:

1. **Check current limits**
   ```bash
   python3 << 'EOF'
   import sys
   sys.path.insert(0, '/workspace')
   from core.limits import get_limiter
   stats = get_limiter().get_stats()
   print(f"Global: {stats['global_concurrent']}/{stats['config']['max_concurrent_global']}")
   print(f"Queue: {stats['global_queue_size']}/{stats['config']['max_queue_size_global']}")
   EOF
   ```

2. **Identify heavy users**
   ```bash
   python3 << 'EOF'
   import sys
   sys.path.insert(0, '/workspace')
   from core.limits import get_limiter
   stats = get_limiter().get_stats()
   for user in sorted(stats['users'], key=lambda u: u['concurrent'] + u['queued'], reverse=True)[:10]:
       print(f"{user['user_id']}: {user['concurrent']} concurrent, {user['queued']} queued")
   EOF
   ```

3. **Check for attack/abuse**
   ```bash
   # Check request patterns
   grep "429" /var/log/app.log | cut -d' ' -f4 | sort | uniq -c | sort -rn | head -10
   ```

**Remediation**:

- **Immediate**: Increase limits
  ```bash
  export LIMITS_MAX_CONCURRENT_GLOBAL=200
  export LIMITS_MAX_QUEUE_SIZE_GLOBAL=1000
  systemctl restart app
  ```

- **Short-term**: Rate limit specific users
  ```bash
  # Add to rate limit configuration
  # Or block via API key
  ```

- **Long-term**: Scale horizontally, implement distributed rate limiting

### Fallback Rate High

**Symptom**: >30% of requests using fallback

**Investigation Steps**:

1. **Check Pinecone health**
   ```bash
   # Test Pinecone directly
   curl -X POST https://your-index.svc.pinecone.io/query \
     -H "Api-Key: $PINECONE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"vector": [0.1, 0.2, ..., 0.512], "topK": 10}'
   
   # Check latency
   time curl ...
   ```

2. **Check fallback metrics**
   ```bash
   python3 tools/load_smoke.py --requests 50 | grep Fallbacks
   ```

**Remediation**:

- **Immediate**: Ensure fallback is working
  ```bash
  export PERF_PGVECTOR_ENABLED=true
  export PERF_FALLBACKS_ENABLED=true
  ```

- **Investigate**: Contact Pinecone support, check API status
- **Long-term**: Optimize Pinecone index, consider caching

### Error Rate High

**Symptom**: >5% error rate

**Investigation Steps**:

1. **Check error types**
   ```bash
   grep "ERROR" /var/log/app.log | tail -50
   
   # Group by error type
   grep "ERROR" /var/log/app.log | cut -d':' -f3 | sort | uniq -c | sort -rn
   ```

2. **Check recent deployments**
   ```bash
   git log --oneline --since="1 hour ago"
   ```

3. **Run smoke test**
   ```bash
   python3 tools/load_smoke.py --requests 20 --budget-error 0.1
   ```

**Remediation**:

- **Immediate**: Rollback if recent deployment
  ```bash
  git revert HEAD
  git push
  deploy
  ```

- **Investigation**: Analyze error logs, check dependencies
- **Long-term**: Add retry logic, improve error handling

---

## Common Operations

### Operation 1: Enable pgvector Fallback

```bash
# 1. Update configuration
echo "PERF_PGVECTOR_ENABLED=true" >> .env
echo "PERF_FALLBACKS_ENABLED=true" >> .env

# 2. Restart service
systemctl restart app

# 3. Verify fallback works
python3 tools/load_smoke.py --pinecone-down --requests 10

# 4. Check metrics
curl http://localhost:8000/metrics | grep fallback
```

### Operation 2: Increase Latency Budgets

```bash
# 1. Add slack (temporary)
export LATENCY_SLACK_PERCENT=10

# 2. Or update budgets in evals/latency.py (permanent)
# Edit DEFAULT_BUDGETS, change p95_budget_ms values

# 3. Verify
python3 evals/latency.py --slack 10
```

### Operation 3: Scale Up Resource Limits

```bash
# 1. Update limits
cat >> .env << EOF
LIMITS_MAX_CONCURRENT_GLOBAL=200
LIMITS_MAX_QUEUE_SIZE_GLOBAL=1000
LIMITS_MAX_CONCURRENT_PER_USER=5
EOF

# 2. Restart
systemctl restart app

# 3. Monitor
watch -n 5 'python3 -c "
import sys
sys.path.insert(0, \"/workspace\")
from core.limits import get_limiter
stats = get_limiter().get_stats()
print(f\"Concurrent: {stats[\"global_concurrent\"]}/{stats[\"config\"][\"max_concurrent_global\"]}\")
print(f\"Queue: {stats[\"global_queue_size\"]}/{stats[\"config\"][\"max_queue_size_global\"]}\")
"'
```

### Operation 4: Run Performance Smoke Test

```bash
# 1. Basic smoke test
python3 tools/load_smoke.py --requests 50 --concurrency 10

# 2. With Pinecone failure simulation
python3 tools/load_smoke.py --pinecone-down --requests 20

# 3. Strict budgets (pre-deploy validation)
python3 tools/load_smoke.py \
  --budget-p50 600 \
  --budget-p95 1200 \
  --budget-error 0.02 \
  --requests 100

# 4. Save results
python3 tools/load_smoke.py --json --output smoke_$(date +%Y%m%d_%H%M).json
```

### Operation 5: Check All Metrics

```bash
# Run comprehensive check script
cat > check_all_metrics.sh << 'EOF'
#!/bin/bash
echo "=== Latency Budgets ==="
python3 evals/latency.py --verbose

echo -e "\n=== Resource Limits ==="
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/workspace')
from core.limits import get_limiter
stats = get_limiter().get_stats()
print(f"Global concurrent: {stats['global_concurrent']}/{stats['config']['max_concurrent_global']}")
print(f"Global queue: {stats['global_queue_size']}/{stats['config']['max_queue_size_global']}")
print(f"Active users: {stats['total_users']}")
PYEOF

echo -e "\n=== Smoke Test ==="
python3 tools/load_smoke.py --requests 20 --concurrency 5
EOF

chmod +x check_all_metrics.sh
./check_all_metrics.sh
```

---

## Troubleshooting

### Issue: All requests timing out

**Symptoms**:
- High latency (>10s)
- Timeout errors in logs
- 408 status codes

**Diagnosis**:
```bash
# Check if service is running
ps aux | grep python

# Check if port is listening
netstat -tulpn | grep 8000

# Test basic health
curl http://localhost:8000/healthz
```

**Resolution**:
1. Restart service: `systemctl restart app`
2. Check logs: `tail -100 /var/log/app.log`
3. Check resources: `top`, `free -h`, `df -h`
4. Scale up if needed

### Issue: High 429 rate

**Symptoms**:
- Users seeing "too many requests"
- Queue full messages in logs

**Diagnosis**:
```bash
# Check resource limits
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace')
from core.limits import get_limiter
print(get_limiter().get_stats())
EOF
```

**Resolution**:
1. Increase limits (see [Operation 3](#operation-3-scale-up-resource-limits))
2. Identify heavy users
3. Add per-user rate limiting if abuse detected

### Issue: Pinecone fallback not working

**Symptoms**:
- High error rate when Pinecone down
- Fallback rate at 0%

**Diagnosis**:
```bash
# Check fallback flags
python3 << 'EOF'
from config import load_config
cfg = load_config()
print(f"PGVector enabled: {cfg.get('PERF_PGVECTOR_ENABLED')}")
print(f"Fallbacks enabled: {cfg.get('PERF_FALLBACKS_ENABLED')}")
EOF
```

**Resolution**:
1. Enable flags: `PERF_PGVECTOR_ENABLED=true PERF_FALLBACKS_ENABLED=true`
2. Restart service
3. Test: `python3 tools/load_smoke.py --pinecone-down`

### Issue: Latency budgets failing in CI

**Symptoms**:
- CI failing on latency gate checks
- `python3 evals/latency.py` exits with code 1

**Diagnosis**:
```bash
# Run locally to see actual performance
python3 evals/latency.py --verbose

# Check if CI environment is slower
# Run smoke test
python3 tools/load_smoke.py --requests 50
```

**Resolution**:
1. **If CI is consistently slower**: Add slack for CI
   ```bash
   LATENCY_SLACK_PERCENT=10 python3 evals/latency.py
   ```
2. **If performance degraded**: Investigate and fix
3. **If budgets unrealistic**: Update budgets in `evals/latency.py`

---

## Dashboards and Monitoring

### Metrics to Monitor

| Metric | Threshold | Alert Level |
|--------|-----------|-------------|
| p95 latency | >1500ms | Warning |
| p95 latency | >2000ms | Critical |
| Error rate | >5% | Warning |
| Error rate | >10% | Critical |
| Fallback rate | >30% | Warning |
| Fallback rate | >50% | Critical |
| 429 rate | >5% | Warning |
| Queue depth | >80% full | Warning |
| Queue depth | >95% full | Critical |

### Prometheus Queries

```promql
# p95 latency
histogram_quantile(0.95, rate(chat_latency_ms_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Fallback rate
rate(pgvector_fallback_total[5m]) / rate(retrieval_total[5m])

# 429 rate
rate(http_requests_total{status="429"}[5m]) / rate(http_requests_total[5m])

# Queue depth
resource_limit_queue_size / resource_limit_queue_max
```

### Grafana Dashboard Panels

**Panel 1: Latency Over Time**
- Metric: `chat_latency_ms`
- Visualization: Graph
- Queries: p50, p95, p99
- Alert: p95 > 1500ms

**Panel 2: Success/Error Rates**
- Metric: `http_requests_total`
- Visualization: Stacked graph
- Queries: 2xx, 4xx, 5xx rates
- Alert: 5xx > 5%

**Panel 3: Fallback Usage**
- Metric: `pgvector_fallback_total`
- Visualization: Graph
- Alert: Fallback rate > 30%

**Panel 4: Resource Limits**
- Metrics: `concurrent_requests`, `queue_size`
- Visualization: Gauge
- Alert: >80% capacity

**Panel 5: Circuit Breaker**
- Metric: `circuit_breaker_state`
- Visualization: Stat
- States: CLOSED (green), OPEN (red), HALF_OPEN (yellow)

### Logging

**Important log patterns**:

```bash
# Circuit breaker events
grep "circuit_breaker" /var/log/app.log

# Fallback usage
grep "fallback" /var/log/app.log

# 429 responses
grep "429" /var/log/app.log

# Latency budget breaches
grep "budget.*exceeded" /var/log/app.log

# Errors
grep "ERROR" /var/log/app.log
```

### Alerting Rules

```yaml
# Prometheus alerting rules
groups:
  - name: performance
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(chat_latency_ms_bucket[5m])) > 1500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High p95 latency detected"
          description: "p95 latency is {{ $value }}ms (threshold: 1500ms)"
      
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"
      
      - alert: HighFallbackRate
        expr: rate(pgvector_fallback_total[5m]) / rate(retrieval_total[5m]) > 0.30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High fallback usage"
          description: "Fallback rate is {{ $value | humanizePercentage }} (threshold: 30%)"
      
      - alert: ResourceLimitReached
        expr: resource_limit_queue_size / resource_limit_queue_max > 0.80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Resource queue filling up"
          description: "Queue is {{ $value | humanizePercentage }} full"
      
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 2  # OPEN state
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker is open"
          description: "Service degraded - circuit breaker protecting system"
```

---

## Appendix: Configuration Reference

### Environment Variables Summary

```bash
# Performance Flags
PERF_RETRIEVAL_PARALLEL=true
PERF_RETRIEVAL_TIMEOUT_MS=450
PERF_GRAPH_TIMEOUT_MS=150
PERF_COMPARE_TIMEOUT_MS=400
PERF_REVIEWER_ENABLED=true
PERF_REVIEWER_BUDGET_MS=500
PERF_PGVECTOR_ENABLED=true
PERF_FALLBACKS_ENABLED=true

# Resource Limits
LIMITS_ENABLED=true
LIMITS_MAX_CONCURRENT_PER_USER=3
LIMITS_MAX_QUEUE_SIZE_PER_USER=10
LIMITS_MAX_CONCURRENT_GLOBAL=100
LIMITS_MAX_QUEUE_SIZE_GLOBAL=500
LIMITS_RETRY_AFTER_SECONDS=5
LIMITS_QUEUE_TIMEOUT_SECONDS=30.0
LIMITS_OVERLOAD_POLICY=drop_newest

# Latency Budgets
LATENCY_SLACK_PERCENT=0  # 0 for strict, 10 for ±10% slack

# Circuit Breakers
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RESET_TIMEOUT=60

# External Sources
FACTARE_ENABLED=false
FACTARE_ALLOW_EXTERNAL=false
FACTARE_EXTERNAL_TIMEOUT_MS=2000
```

### Curl Examples

```bash
# Health check
curl http://localhost:8000/healthz

# Chat request
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "prompt": "What is machine learning?",
    "session_id": "test_123"
  }'

# Chat with debug
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "prompt": "Explain neural networks",
    "session_id": "test_123",
    "debug": true
  }' | jq '.metrics'

# Simulate Pinecone failure
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Pinecone-Failure: true" \
  -d '{
    "prompt": "Test fallback",
    "session_id": "test_fallback"
  }' | jq '.metrics.pgvector_fallback_used'

# Check metrics
curl http://localhost:8000/metrics

# Check config
curl http://localhost:8000/debug/config | jq '.PERF_*'
```

---

## Quick Checklist

### Pre-Deploy Checklist

- [ ] Run smoke test: `python3 tools/load_smoke.py --requests 50`
- [ ] Check latency budgets: `python3 evals/latency.py`
- [ ] Verify fallback works: `python3 tools/load_smoke.py --pinecone-down`
- [ ] Check resource limits: verify capacity sufficient
- [ ] Review recent changes: `git log --oneline --since="24 hours"`
- [ ] Backup configuration: `cp .env .env.backup`

### Post-Deploy Checklist

- [ ] Verify health: `curl http://localhost:8000/healthz`
- [ ] Check metrics: Run smoke test
- [ ] Monitor logs: `tail -f /var/log/app.log`
- [ ] Verify latency: Check p95 < budgets
- [ ] Check error rate: Should be <5%
- [ ] Monitor for 15 minutes before marking complete

### Incident Response Checklist

- [ ] Check health endpoints
- [ ] Review recent deployments
- [ ] Check external dependencies (Pinecone, DB)
- [ ] Review error logs
- [ ] Check resource usage (CPU, memory, disk)
- [ ] Verify circuit breakers not stuck open
- [ ] Check queue depths
- [ ] Test fallback paths
- [ ] Collect metrics for post-mortem
- [ ] Document remediation steps

---

**Document Version**: 1.0  
**Last Reviewed**: 2025-11-04  
**Owner**: Platform Team  
**Feedback**: Submit issues or suggestions via pull request

---

## See Also

- [Latency Gates Implementation](../LATENCY_GATES_QUICKSTART.md)
- [Resource Limits Guide](../RESOURCE_LIMITS_QUICKSTART.md)
- [Load Smoke Test Tool](../LOAD_SMOKE_QUICKSTART.md)
- [Evaluation Runbook](evals-runbook.md)
