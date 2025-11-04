# Performance Monitoring & Fallback Management — Operator Runbook

**Last Updated**: 2025-11-04  
**Audience**: Site Reliability Engineers, DevOps, Operators  
**Prerequisites**: Access to production environment, `curl`, `jq` (optional)

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Performance Flags & Configuration](#performance-flags--configuration)
3. [Circuit Breakers](#circuit-breakers)
4. [Fallback System](#fallback-system)
5. [Metrics & Observability](#metrics--observability)
6. [Performance SLOs](#performance-slos)
7. [Load Testing](#load-testing)
8. [Troubleshooting](#troubleshooting)
9. [Runbook Procedures](#runbook-procedures)

---

## Quick Reference

### Essential Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Metrics with p95 latencies
curl http://localhost:8000/debug/metrics | jq '.performance'

# Compact metrics summary
curl http://localhost:8000/debug/metrics/summary

# Current configuration
curl http://localhost:8000/debug/config

# Limiter statistics
curl http://localhost:8000/debug/limits
```

### Key Performance Indicators

| Metric | SLO | Critical Threshold | Action |
|--------|-----|-------------------|---------|
| Retrieval p95 | ≤ 500ms | > 600ms | Check Pinecone, review circuit breaker |
| Packing p95 | ≤ 550ms | > 650ms | Review context size, optimize packing |
| Reviewer p95 | ≤ 500ms | > 600ms | Check LLM API, consider disabling |
| Overall /chat p95 | ≤ 1200ms | > 1500ms | Investigate all components |
| Error rate | ≤ 5% | > 10% | Check logs, circuit breakers |
| Fallback rate | ≤ 30% | > 50% | Check Pinecone health |

### Emergency Commands

```bash
# Force all traffic to fallback (Pinecone outage)
export PERF_PGVECTOR_ENABLED=true
export PERF_FALLBACKS_ENABLED=true

# Disable reviewer to reduce latency
export PERF_REVIEWER_ENABLED=false

# Increase concurrency limits during load spike
export LIMITS_MAX_CONCURRENT_GLOBAL=200

# Reset circuit breakers
curl -X POST http://localhost:8000/debug/circuit-breakers/reset
```

---

## Performance Flags & Configuration

### Overview

Performance flags control system behavior and resource allocation. All flags have sensible defaults and can be overridden via environment variables.

### Flag Reference

#### Retrieval Flags

```bash
# Enable parallel dual-index retrieval (recommended)
PERF_RETRIEVAL_PARALLEL=true

# Retrieval timeout (milliseconds)
PERF_RETRIEVAL_TIMEOUT_MS=450

# Example: Increase timeout for slow networks
export PERF_RETRIEVAL_TIMEOUT_MS=600
```

#### Graph Expansion Flags

```bash
# Graph expansion timeout (milliseconds)
PERF_GRAPH_TIMEOUT_MS=150

# Maximum neighbors to expand
LIMITS_GRAPH_MAX_NEIGHBORS=50

# Maximum graph depth
LIMITS_GRAPH_MAX_DEPTH=1

# Example: Reduce graph expansion for lower latency
export PERF_GRAPH_TIMEOUT_MS=100
export LIMITS_GRAPH_MAX_NEIGHBORS=30
```

#### Fallback Flags

```bash
# Enable pgvector fallback
PERF_PGVECTOR_ENABLED=true

# Enable all fallback mechanisms
PERF_FALLBACKS_ENABLED=true

# Example: Disable fallbacks (Pinecone-only mode)
export PERF_PGVECTOR_ENABLED=false
export PERF_FALLBACKS_ENABLED=false
```

#### Reviewer Flags

```bash
# Enable answer reviewer
PERF_REVIEWER_ENABLED=true

# Reviewer time budget (milliseconds)
PERF_REVIEWER_BUDGET_MS=500

# Example: Disable reviewer during high load
export PERF_REVIEWER_ENABLED=false
```

### Viewing Current Configuration

```bash
# Get all performance flags
curl http://localhost:8000/debug/config | jq '.performance'

# Example output:
# {
#   "flags": {
#     "retrieval_parallel": true,
#     "pgvector_enabled": true,
#     "fallbacks_enabled": true,
#     "reviewer_enabled": true
#   },
#   "budgets": {
#     "retrieval_timeout_ms": 450,
#     "graph_timeout_ms": 150,
#     "reviewer_budget_ms": 500
#   }
# }
```

### Updating Configuration

**Method 1: Environment Variables** (requires restart)

```bash
# In systemd service file or .env
PERF_RETRIEVAL_TIMEOUT_MS=600
PERF_REVIEWER_ENABLED=false

# Restart service
sudo systemctl restart chatbot-api
```

**Method 2: Configuration File** (requires deployment)

```yaml
# config/production.yaml
performance:
  retrieval_timeout_ms: 600
  reviewer_enabled: false
```

---

## Circuit Breakers

### Overview

Circuit breakers prevent cascading failures by automatically stopping requests to failing services. They implement a three-state pattern: CLOSED (normal), OPEN (failing), HALF_OPEN (testing recovery).

### Circuit Breaker Configuration

```python
# Default configuration
CircuitBreakerConfig(
    failure_threshold=5,        # Open after 5 consecutive failures
    cooldown_seconds=60.0,      # Wait 60s before testing recovery
    success_threshold=2         # Close after 2 consecutive successes
)
```

### Monitored Services

1. **Pinecone** (vector database)
   - Failure: Query timeouts, connection errors
   - Fallback: Pgvector
   - Recovery: Automatic after cooldown

2. **Reviewer LLM** (answer quality check)
   - Failure: API errors, timeouts
   - Fallback: Skip review (set `skipped=true`)
   - Recovery: Automatic after cooldown

### Checking Circuit Breaker Status

```bash
# Get circuit breaker metrics
curl http://localhost:8000/debug/metrics | jq '.counters | 
  with_entries(select(.key | contains("circuit")))'

# Example output:
# {
#   "circuit_opens": 3,
#   "circuit_closes": 2,
#   "circuit_opens_by_service": [
#     {"labels": {"service": "pinecone"}, "value": 2},
#     {"labels": {"service": "reviewer"}, "value": 1}
#   ]
# }
```

### Circuit Breaker States

**CLOSED** (Normal Operation)
```bash
# All requests pass through
# Failures are counted
# Opens on reaching failure_threshold
```

**OPEN** (Failing)
```bash
# All requests immediately fail
# Fallback mechanisms activated
# Transitions to HALF_OPEN after cooldown
```

**HALF_OPEN** (Testing Recovery)
```bash
# One probe request allowed
# Success → CLOSED (recovered)
# Failure → OPEN (still failing)
```

### Manual Circuit Breaker Operations

```bash
# Reset all circuit breakers (force CLOSED)
curl -X POST http://localhost:8000/debug/circuit-breakers/reset

# Reset specific circuit breaker
curl -X POST http://localhost:8000/debug/circuit-breakers/reset/pinecone

# Get circuit breaker stats
curl http://localhost:8000/debug/circuit-breakers
```

---

## Fallback System

### Overview

The fallback system provides graceful degradation when primary services fail. It operates transparently with automatic triggering and recovery.

### Fallback Chain

```
Primary: Pinecone (fast, full k)
    ↓ (on failure/timeout)
Fallback: Pgvector (slower, reduced k)
    ↓ (on failure)
Error: 500 (graceful failure)
```

### Reduced k Values

When fallback is active:
- **Explicate**: 8 results (reduced from 16)
- **Implicate**: 4 results (reduced from 8)
- **Timeout**: 350ms (faster than primary)

### Detecting Fallback Usage

```bash
# Check fallback rate
curl http://localhost:8000/debug/metrics/summary | jq '.fallbacks'

# Example output:
# {
#   "pgvector_fallback_rate": 0.15,  # 15% of requests
#   "pgvector_fallbacks": 45
# }
```

### Fallback Response Indicators

```json
{
  "answer": "...",
  "metrics": {
    "retrieval_fallback": true,
    "fallback_reason": "pinecone_timeout",
    "fallback_used": true
  }
}
```

### Triggering Conditions

1. **Circuit Breaker Open**
   - Pinecone circuit breaker in OPEN state
   - Automatic fallback to pgvector

2. **Health Check Failure**
   - Pinecone health check fails
   - Cached for 30 seconds

3. **Timeout**
   - Pinecone query exceeds timeout
   - Fallback triggered on next request

### Manual Fallback Control

```bash
# Enable fallback system
export PERF_PGVECTOR_ENABLED=true
export PERF_FALLBACKS_ENABLED=true

# Disable fallback (Pinecone-only mode)
export PERF_PGVECTOR_ENABLED=false
export PERF_FALLBACKS_ENABLED=false

# Test fallback behavior
curl -X POST http://localhost:8000/chat \
  -H "X-Simulate-Pinecone-Failure: true" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "session_id": "test123"}'
```

---

## Metrics & Observability

### Metrics Endpoints

```bash
# Full metrics (all histograms, counters, gauges)
curl http://localhost:8000/debug/metrics

# Compact summary (key metrics only)
curl http://localhost:8000/debug/metrics/summary

# Health status with warnings
curl http://localhost:8000/debug/health
```

### Understanding /debug/metrics

#### Structure

```json
{
  "timestamp": 1699123456.789,
  "performance": {
    "retrieval": {"p50": 420, "p95": 480, "p99": 550, "count": 1000},
    "graph_expand": {"p50": 140, "p95": 170, "p99": 195, "count": 800},
    "packing": {"p50": 190, "p95": 220, "p99": 245, "count": 1000},
    "reviewer": {"p50": 490, "p95": 550, "p99": 580, "count": 600}
  },
  "counters": {
    "pinecone_timeouts": 5,
    "pgvector_fallbacks": 45,
    "reviewer_skips": 12,
    "circuit_opens": 2,
    "circuit_closes": 1
  },
  "rates": {
    "retrieval_error_rate": 0.02,  # 2%
    "pgvector_fallback_rate": 0.15  # 15%
  }
}
```

#### Key Metrics Explained

**Histograms** (latency in milliseconds)
- `retrieval_ms`: Time to fetch context from vector DB
- `graph_expand_ms`: Time to expand entity neighborhoods
- `packing_ms`: Time to pack context into prompt
- `reviewer_ms`: Time for answer quality review

**Counters** (cumulative counts)
- `pinecone_timeouts`: Pinecone query timeouts
- `pgvector_fallbacks`: Fallback activations
- `reviewer_skips`: Reviews skipped (timeout/circuit)
- `circuit_opens`: Circuit breaker openings
- `circuit_closes`: Circuit breaker recoveries

**Rates** (0.0 - 1.0)
- `retrieval_error_rate`: Failed retrievals / total
- `pgvector_fallback_rate`: Fallback uses / total

### Querying Metrics with jq

```bash
# Get all p95 latencies
curl -s http://localhost:8000/debug/metrics/summary | jq '
  {
    retrieval_p95: .retrieval.p95,
    graph_p95: .graph_expand.p95,
    packing_p95: .packing.p95,
    reviewer_p95: .reviewer.p95
  }'

# Check if any p95 exceeds SLO
curl -s http://localhost:8000/debug/metrics/summary | jq '
  {
    retrieval_ok: (.retrieval.p95 <= 500),
    packing_ok: (.packing.p95 <= 550),
    reviewer_ok: (.reviewer.p95 <= 500)
  }'

# Get failure indicators
curl -s http://localhost:8000/debug/metrics/summary | jq '
  .counters + .fallbacks + .errors'

# Count open circuits
curl -s http://localhost:8000/debug/metrics/summary | jq '
  .circuit_breakers.opens - .circuit_breakers.closes'
```

### Metrics in Monitoring Systems

**Prometheus** (if integrated)
```promql
# p95 retrieval latency
histogram_quantile(0.95, retrieval_ms_bucket)

# Fallback rate over 5 minutes
rate(pgvector_fallbacks[5m]) / rate(retrieval_total[5m])

# Circuit breaker status (open circuits)
circuit_opens - circuit_closes
```

**Datadog** (if integrated)
```
# Dashboard queries
avg:retrieval_ms.p95{env:prod}
sum:pgvector_fallbacks{env:prod}.as_rate()
circuit_opens{env:prod} - circuit_closes{env:prod}
```

---

## Performance SLOs

### Service Level Objectives

| Component | Metric | SLO | Warning | Critical |
|-----------|--------|-----|---------|----------|
| Retrieval | p95 latency | ≤ 500ms | > 500ms | > 600ms |
| Graph Expand | p95 latency | ≤ 200ms | > 200ms | > 250ms |
| Packing | p95 latency | ≤ 550ms | > 550ms | > 650ms |
| Reviewer | p95 latency | ≤ 500ms | > 500ms | > 600ms |
| Overall /chat | p95 latency | ≤ 1200ms | > 1200ms | > 1500ms |
| Availability | Success rate | ≥ 99% | < 99% | < 95% |
| Fallback | Usage rate | ≤ 30% | > 30% | > 50% |

### Checking SLO Compliance

```bash
# Run latency gate checks
python evals/latency.py --verbose

# Output:
# ================================================================================
# LATENCY GATE RESULTS
# ================================================================================
# ✅ Retrieval (dual-index) p95: 450.0ms ≤ 500.0ms (budget: 500ms, count: 100)
# ✅ Context packing p95: 520.0ms ≤ 550.0ms (budget: 550ms, count: 100)
# ✅ Reviewer call p95: 480.0ms ≤ 500.0ms (budget: 500ms, count: 60)
# 
# Summary: 3/3 gates passed
# ✅ All gates passed
```

### SLO Violation Response

**Level 1: Warning** (SLO exceeded but below critical)
1. Monitor for trend
2. Review recent changes
3. Check resource utilization
4. No immediate action required

**Level 2: Critical** (Above critical threshold)
1. Page on-call engineer
2. Check circuit breaker status
3. Review error logs
4. Consider scaling resources
5. Enable fallback if not already active

### SLO Reporting

```bash
# Generate SLO report
curl -s http://localhost:8000/debug/metrics/summary | python3 << 'EOF'
import sys, json
data = json.load(sys.stdin)

print("SLO Compliance Report")
print("=" * 50)

checks = [
    ("Retrieval p95", data["retrieval"]["p95"], 500),
    ("Packing p95", data["packing"]["p95"], 550),
    ("Reviewer p95", data["reviewer"]["p95"], 500),
]

for name, actual, slo in checks:
    status = "✅" if actual <= slo else "❌"
    print(f"{status} {name}: {actual:.0f}ms / {slo}ms")

print()
print(f"Error Rate: {data['errors']['retrieval_error_rate']*100:.1f}%")
print(f"Fallback Rate: {data['fallbacks']['pgvector_fallback_rate']*100:.1f}%")
EOF
```

---

## Load Testing

### Smoke Load Tool

The smoke load tool exercises the critical /chat path with parallel requests and validates performance budgets.

#### Basic Usage

```bash
# Quick smoke test (50 requests, 10 concurrent)
python tools/load_smoke.py

# Custom load
python tools/load_smoke.py --requests 100 --concurrency 20

# Against staging
python tools/load_smoke.py --url https://staging-api.example.com
```

#### Testing Scenarios

**Scenario 1: Normal Load**
```bash
python tools/load_smoke.py \
  --requests 50 \
  --concurrency 10 \
  --budget-p95 1500
```

**Scenario 2: High Load**
```bash
python tools/load_smoke.py \
  --requests 200 \
  --concurrency 50 \
  --budget-p95 2000 \
  --budget-error 0.1
```

**Scenario 3: Fallback Path**
```bash
python tools/load_smoke.py \
  --requests 50 \
  --pinecone-down \
  --budget-p95 2000
```

**Scenario 4: Stress Test**
```bash
python tools/load_smoke.py \
  --requests 500 \
  --concurrency 100 \
  --timeout 10.0
```

#### Interpreting Results

```
================================================================================
METRICS
================================================================================

Throughput:
  Requests: 50
  Duration: 12.45s
  Throughput: 4.02 req/s        # ← Requests per second

Success Rates:
  Successful: 49/50 (98.0%)     # ← Should be ≥95%
  Failed: 1/50 (2.0%)            # ← Should be ≤5%
  Fallbacks: 3/50 (6.0%)         # ← Should be ≤30% (normal mode)

Latency (successful requests):
  p50: 720.45ms                  # ← Should be ≤800ms
  p95: 1350.23ms                 # ← Should be ≤1500ms
  p99: 1480.67ms                 # ← Should be ≤2500ms
```

**Good Results**:
- Success rate ≥ 95%
- p95 ≤ 1500ms
- Fallback rate ≤ 30%
- Throughput ≥ 3 req/s

**Concerning Results**:
- Success rate < 95%
- p95 > 1500ms
- Fallback rate > 50%
- Throughput < 2 req/s

#### CI Integration

```bash
# In CI pipeline
python tools/load_smoke.py \
  --requests 100 \
  --concurrency 20 \
  --budget-p95 1500 \
  --budget-error 0.05

# Exit code 0 = pass, 1 = fail
if [ $? -ne 0 ]; then
  echo "Load test failed - budgets exceeded"
  exit 1
fi
```

---

## Troubleshooting

### High Latency

**Symptom**: p95 latency exceeding SLO

**Diagnosis**:
```bash
# Check component breakdown
curl -s http://localhost:8000/debug/metrics/summary | jq '
  .retrieval.p95, .graph_expand.p95, .packing.p95, .reviewer.p95'

# Identify slowest component
# If retrieval: Check Pinecone, consider fallback
# If packing: Reduce context size
# If reviewer: Consider disabling
```

**Resolution**:
1. Check circuit breaker status
2. Review recent code changes
3. Check external service health
4. Scale resources if needed
5. Enable fallback mechanisms

### High Error Rate

**Symptom**: Error rate > 5%

**Diagnosis**:
```bash
# Check error breakdown
curl -s http://localhost:8000/debug/metrics | jq '.counters | 
  with_entries(select(.key | contains("error") or contains("timeout")))'

# Check logs for error patterns
tail -f /var/log/chatbot-api/error.log | grep -i error
```

**Resolution**:
1. Identify error source (retrieval, LLM, database)
2. Check circuit breakers
3. Verify service dependencies
4. Review error logs
5. Scale or restart affected services

### High Fallback Rate

**Symptom**: Fallback rate > 30% (non-outage)

**Diagnosis**:
```bash
# Check Pinecone health
curl http://localhost:8000/debug/health

# Check fallback reasons
curl -s http://localhost:8000/debug/metrics | jq '
  .counters.pgvector_fallbacks_by_reason'
```

**Resolution**:
1. Check Pinecone service status
2. Review Pinecone timeouts
3. Check network connectivity
4. Verify API keys/credentials
5. Contact Pinecone support if persistent

### Circuit Breaker Stuck Open

**Symptom**: Circuit breaker not recovering

**Diagnosis**:
```bash
# Check circuit breaker stats
curl http://localhost:8000/debug/circuit-breakers | jq '
  .[] | select(.state == "OPEN")'

# Check last failure time
curl http://localhost:8000/debug/circuit-breakers | jq '
  .[] | {service: .service, state: .state, last_failure: .last_failure_time}'
```

**Resolution**:
1. Verify underlying service is healthy
2. Check failure threshold configuration
3. Wait for cooldown period (default: 60s)
4. Manually reset if needed:
   ```bash
   curl -X POST http://localhost:8000/debug/circuit-breakers/reset/pinecone
   ```

### Rate Limiting (429 Errors)

**Symptom**: Requests receiving 429 Too Many Requests

**Diagnosis**:
```bash
# Check limiter stats
curl http://localhost:8000/debug/limits | jq

# Check user queue status
curl -s http://localhost:8000/debug/limits | jq '.users[] | 
  select(.queued > 0 or .concurrent > 2)'
```

**Resolution**:
1. Identify high-volume users
2. Check if legitimate traffic spike
3. Increase concurrency limits if needed:
   ```bash
   export LIMITS_MAX_CONCURRENT_PER_USER=5
   export LIMITS_MAX_CONCURRENT_GLOBAL=200
   ```
4. Review rate limit policy
5. Contact users if abuse suspected

---

## Runbook Procedures

### Procedure 1: Pinecone Outage

**Situation**: Pinecone is completely down

**Steps**:
1. Verify outage:
   ```bash
   curl http://localhost:8000/debug/health | jq '.services.pinecone'
   ```

2. Enable fallback mode:
   ```bash
   export PERF_PGVECTOR_ENABLED=true
   export PERF_FALLBACKS_ENABLED=true
   sudo systemctl restart chatbot-api
   ```

3. Verify fallback working:
   ```bash
   python tools/load_smoke.py --requests 20 --budget-p95 2000
   ```

4. Monitor fallback rate:
   ```bash
   watch -n 5 'curl -s http://localhost:8000/debug/metrics/summary | 
     jq ".fallbacks"'
   ```

5. When Pinecone recovers:
   ```bash
   # Circuit breaker will auto-recover
   # Or manually reset:
   curl -X POST http://localhost:8000/debug/circuit-breakers/reset/pinecone
   ```

### Procedure 2: High Latency Incident

**Situation**: p95 latency > 1500ms

**Steps**:
1. Identify slow component:
   ```bash
   curl -s http://localhost:8000/debug/metrics/summary | jq '
     {retrieval:.retrieval.p95, graph:.graph_expand.p95, 
      packing:.packing.p95, reviewer:.reviewer.p95}'
   ```

2. If retrieval slow:
   ```bash
   # Check Pinecone
   # Enable fallback if needed
   export PERF_PGVECTOR_ENABLED=true
   ```

3. If reviewer slow:
   ```bash
   # Disable reviewer temporarily
   export PERF_REVIEWER_ENABLED=false
   sudo systemctl reload chatbot-api
   ```

4. If graph expand slow:
   ```bash
   # Reduce graph limits
   export PERF_GRAPH_TIMEOUT_MS=100
   export LIMITS_GRAPH_MAX_NEIGHBORS=30
   ```

5. Verify improvement:
   ```bash
   python tools/load_smoke.py --requests 50
   ```

### Procedure 3: Load Spike Response

**Situation**: Sudden traffic spike causing degradation

**Steps**:
1. Check current load:
   ```bash
   curl http://localhost:8000/debug/limits | jq '
     {global_concurrent, global_queue_size, total_users}'
   ```

2. Increase limits temporarily:
   ```bash
   export LIMITS_MAX_CONCURRENT_GLOBAL=200
   export LIMITS_MAX_CONCURRENT_PER_USER=5
   sudo systemctl reload chatbot-api
   ```

3. Disable non-critical features:
   ```bash
   export PERF_REVIEWER_ENABLED=false
   ```

4. Monitor queue drain:
   ```bash
   watch -n 2 'curl -s http://localhost:8000/debug/limits | 
     jq ".global_queue_size"'
   ```

5. Scale horizontally if needed:
   ```bash
   # AWS Auto Scaling
   aws autoscaling set-desired-capacity \
     --auto-scaling-group-name chatbot-api-asg \
     --desired-capacity 10
   ```

### Procedure 4: Circuit Breaker Recovery

**Situation**: Multiple circuit breakers open

**Steps**:
1. Check all circuit breakers:
   ```bash
   curl http://localhost:8000/debug/circuit-breakers | jq '
     .[] | select(.state == "OPEN" or .state == "HALF_OPEN")'
   ```

2. Verify underlying services:
   ```bash
   # Pinecone
   curl -H "Api-Key: $PINECONE_API_KEY" \
     https://api.pinecone.io/databases
   
   # Reviewer LLM
   curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
   ```

3. Wait for auto-recovery (60s default)
   ```bash
   sleep 60
   curl http://localhost:8000/debug/circuit-breakers
   ```

4. Manual reset if auto-recovery fails:
   ```bash
   curl -X POST http://localhost:8000/debug/circuit-breakers/reset
   ```

5. Verify system health:
   ```bash
   python tools/load_smoke.py --requests 50
   ```

---

## Appendix

### Environment Variables Reference

```bash
# Performance
PERF_RETRIEVAL_PARALLEL=true
PERF_RETRIEVAL_TIMEOUT_MS=450
PERF_GRAPH_TIMEOUT_MS=150
PERF_PGVECTOR_ENABLED=true
PERF_FALLBACKS_ENABLED=true
PERF_REVIEWER_ENABLED=true
PERF_REVIEWER_BUDGET_MS=500

# Limits
LIMITS_MAX_CONCURRENT_PER_USER=3
LIMITS_MAX_QUEUE_SIZE_PER_USER=10
LIMITS_MAX_CONCURRENT_GLOBAL=100
LIMITS_MAX_QUEUE_SIZE_GLOBAL=500
LIMITS_RETRY_AFTER_SECONDS=5

# Circuit Breakers
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_COOLDOWN_SECONDS=60
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2

# Cache
CACHE_EMBEDDING_TTL=120
CACHE_SELECTION_TTL=60
```

### Useful curl Commands

```bash
# Health check with pretty output
curl -s http://localhost:8000/debug/health | jq '
  {status, warnings, metrics_summary}'

# Get all p95 latencies
curl -s http://localhost:8000/debug/metrics/summary | jq '
  to_entries | 
  map(select(.key | test("p95"))) | 
  from_entries'

# Check for any alerts
curl -s http://localhost:8000/debug/metrics/summary | jq '
  {
    high_error_rate: (.errors.retrieval_error_rate > 0.05),
    high_fallback_rate: (.fallbacks.pgvector_fallback_rate > 0.3),
    open_circuits: ((.circuit_breakers.opens - .circuit_breakers.closes) > 0)
  }'

# Monitor metrics in real-time
watch -n 5 'curl -s http://localhost:8000/debug/metrics/summary | 
  jq "{retrieval_p95:.retrieval.p95, error_rate:.errors.retrieval_error_rate}"'
```

### Monitoring Queries

**CloudWatch Logs Insights**
```sql
-- Count errors by type
fields @timestamp, error_type, error_message
| filter @message like /ERROR/
| stats count() by error_type
| sort count desc

-- p95 latency over time
fields @timestamp, latency_ms
| filter endpoint = "/chat"
| stats percentile(latency_ms, 95) as p95 by bin(5m)
```

**Grafana Dashboard**
```
Panel 1: p95 Latencies (Time Series)
- retrieval_ms{quantile="0.95"}
- packing_ms{quantile="0.95"}
- reviewer_ms{quantile="0.95"}

Panel 2: Error & Fallback Rates (Gauge)
- rate(errors_total[5m]) / rate(requests_total[5m])
- rate(pgvector_fallbacks[5m]) / rate(retrieval_total[5m])

Panel 3: Circuit Breaker Status (Stat)
- circuit_opens - circuit_closes
```

---

## Support & Escalation

### Quick Wins

1. **Disable reviewer**: `export PERF_REVIEWER_ENABLED=false`
2. **Enable fallback**: `export PERF_PGVECTOR_ENABLED=true`
3. **Reset breakers**: `curl -X POST localhost:8000/debug/circuit-breakers/reset`
4. **Increase limits**: `export LIMITS_MAX_CONCURRENT_GLOBAL=200`

### When to Escalate

- Error rate > 10% for > 5 minutes
- p95 latency > 2000ms for > 5 minutes
- Multiple circuit breakers stuck open
- Fallback rate > 80% (complete Pinecone outage)
- Complete service unavailability

### Contact Information

- **On-Call Engineer**: PagerDuty → chatbot-api-oncall
- **Pinecone Support**: support@pinecone.io
- **Internal Slack**: #chatbot-api-alerts

---

**Document Version**: 1.0  
**Last Review**: 2025-11-04  
**Next Review**: 2025-12-04  
**Owner**: SRE Team
