# Load Smoke Test Tool - Quick Start

## TL;DR

```bash
# Install dependencies (if not already installed)
pip install requests

# Basic smoke test
python tools/load_smoke.py --requests 50 --concurrency 10

# Test with Pinecone failure simulation
python tools/load_smoke.py --pinecone-down

# Custom budgets (strict)
python tools/load_smoke.py --budget-p95 1200 --budget-error 0.01
```

---

## What It Does

Fires parallel `/chat` requests with canned prompts, measures p50/p95/p99 latencies, tracks fallback rates, and asserts against performance budgets. **Exits with code 1 if budgets fail.**

---

## Quick Start

### 1. Basic Smoke Test

```bash
python tools/load_smoke.py --requests 50 --concurrency 10
```

**Output**:
```
================================================================================
SMOKE LOAD TEST
================================================================================
Configuration:
  Base URL: http://localhost:8000
  Requests: 50
  Concurrency: 10
  Timeout: 30.0s
  Pinecone Down Mode: False

Budgets:
  p50 ≤ 800ms
  p95 ≤ 1500ms
  p99 ≤ 2500ms
  Error rate ≤ 5.0%
  Fallback rate ≤ 30.0%
================================================================================

Progress: 50/50 (100.0%)

Completed 50 requests in 8.23s

================================================================================
METRICS
================================================================================

Throughput:
  Requests: 50
  Duration: 8.23s
  Throughput: 6.08 req/s

Success Rates:
  Successful: 49/50 (98.0%)
  Failed: 1/50 (2.0%)
  Fallbacks: 8/50 (16.0%)

Latency (successful requests):
  p50: 725.34ms
  p95: 1423.56ms
  p99: 1987.23ms
  Mean: 812.45ms
  Min: 345.12ms
  Max: 2134.67ms

================================================================================
BUDGET CHECKS
================================================================================

✅ PASS: P50 Latency
  Actual: 725.34ms
  Budget: 800.00ms

✅ PASS: P95 Latency
  Actual: 1423.56ms
  Budget: 1500.00ms

✅ PASS: P99 Latency
  Actual: 1987.23ms
  Budget: 2500.00ms

✅ PASS: Error Rate
  Actual: 2.00%
  Budget: 5.00%

✅ PASS: Fallback Rate
  Actual: 16.00%
  Budget: 30.00%

✅ ALL BUDGETS PASSED
================================================================================

✅ Exiting with code 0 (all budgets passed)
```

### 2. Simulate Pinecone Down

```bash
python tools/load_smoke.py --pinecone-down --requests 20
```

**Purpose**: Verify fallback paths work when Pinecone is unavailable.

**Expected**: Higher fallback rate, requests should still succeed via fallback.

### 3. Custom Budgets

```bash
# Strict budgets for production validation
python tools/load_smoke.py \
  --budget-p50 600 \
  --budget-p95 1200 \
  --budget-p99 2000 \
  --budget-error 0.02 \
  --budget-fallback 0.10
```

### 4. Test Against Staging

```bash
python tools/load_smoke.py \
  --url https://staging.api.example.com \
  --api-key your-api-key-here \
  --requests 100 \
  --concurrency 20
```

---

## Command-Line Options

### Request Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--requests, -n` | 50 | Number of requests to send |
| `--concurrency, -c` | 10 | Number of concurrent threads |
| `--url` | http://localhost:8000 | Base URL of API |
| `--api-key` | None | API key for authentication |
| `--timeout` | 30.0 | Request timeout in seconds |

### Simulation Modes

| Option | Description |
|--------|-------------|
| `--pinecone-down` | Simulate Pinecone being down (verify fallback paths) |

### Budget Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--budget-p50` | 800 | p50 latency budget in ms |
| `--budget-p95` | 1500 | p95 latency budget in ms |
| `--budget-p99` | 2500 | p99 latency budget in ms |
| `--budget-error` | 0.05 | Error rate budget (0.05 = 5%) |
| `--budget-fallback` | 0.30 | Fallback rate budget (0.30 = 30%) |

### Output Options

| Option | Description |
|--------|-------------|
| `--json` | Output results as JSON |
| `--output FILE` | Write results to file |

---

## Common Use Cases

### Use Case 1: Pre-Deploy Smoke Test

```bash
# Quick smoke test before deploying
python tools/load_smoke.py --requests 30 --concurrency 5

# Exit code 0 = safe to deploy
# Exit code 1 = performance regression detected
```

**In CI/CD**:
```yaml
- name: Smoke Test
  run: python tools/load_smoke.py --requests 50 --concurrency 10
  # Fails pipeline if budgets exceeded
```

### Use Case 2: Fallback Path Verification

```bash
# Verify system works when Pinecone fails
python tools/load_smoke.py --pinecone-down --requests 20

# Should see high fallback rate but low error rate
# Validates degraded mode still functional
```

### Use Case 3: Performance Regression Detection

```bash
# Strict budgets for catching regressions
python tools/load_smoke.py \
  --budget-p50 600 \
  --budget-p95 1200 \
  --budget-error 0.01 \
  --requests 100
  
# Exit 1 if performance degrades
```

### Use Case 4: Load Capacity Test

```bash
# Test higher concurrency
python tools/load_smoke.py \
  --requests 200 \
  --concurrency 50 \
  --timeout 60

# Observe error rate and latency degradation
```

### Use Case 5: Results for Analysis

```bash
# Save detailed results for later analysis
python tools/load_smoke.py \
  --requests 100 \
  --json \
  --output smoke_test_results.json

# Analyze trends over time
```

---

## Understanding Results

### Metrics Explained

**Throughput**:
- `Requests`: Total requests attempted
- `Duration`: Total test duration
- `Throughput`: Requests per second

**Success Rates**:
- `Successful`: Requests that returned 200 OK
- `Failed`: Requests that failed (timeout, error, etc.)
- `Fallbacks`: Requests that used fallback path (e.g., pgvector instead of Pinecone)

**Latency** (only successful requests):
- `p50`: 50th percentile (median) - half of requests faster than this
- `p95`: 95th percentile - 95% of requests faster than this
- `p99`: 99th percentile - 99% of requests faster than this
- `Mean`: Average latency
- `Min/Max`: Fastest and slowest requests

### Budget Checks

Each budget check shows:
- ✅ **PASS** or ❌ **FAIL**
- **Actual**: Measured value
- **Budget**: Configured limit
- **Overage**: How much over budget (if failed)

**Exit Code**:
- `0`: All budgets passed (safe to proceed)
- `1`: One or more budgets failed (performance issue)
- `130`: User interrupted (Ctrl+C)

---

## Troubleshooting

### Issue: "requests library not available"

**Solution**:
```bash
pip install requests
```

### Issue: Connection refused

**Symptom**:
```
Failed: [Errno 111] Connection refused
Error rate: 100%
```

**Solution**: Ensure API is running:
```bash
# Start API first
python app.py

# Then run smoke test in another terminal
python tools/load_smoke.py
```

### Issue: All requests timeout

**Symptom**:
```
Status code: 408 (timeout)
Error rate: 100%
```

**Solutions**:
1. Increase timeout: `--timeout 60`
2. Reduce concurrency: `--concurrency 5`
3. Check if API is responding slowly
4. Check network connectivity

### Issue: High error rate

**Symptom**:
```
Error rate: 15% (budget: 5%)
❌ FAIL: Error Rate
```

**Investigation**:
1. Check API logs for errors
2. Look at specific error messages in results
3. Reduce load: `--requests 20 --concurrency 2`
4. Check if system has capacity issues

### Issue: High fallback rate

**Symptom**:
```
Fallback rate: 45% (budget: 30%)
❌ FAIL: Fallback Rate
```

**Causes**:
1. Pinecone may be slow or down
2. Fallback threshold too aggressive
3. Network issues to Pinecone

**Actions**:
1. Check Pinecone status
2. Review fallback configuration
3. Adjust `--budget-fallback` if acceptable

### Issue: Budgets too strict

**Symptom**: Tests always fail even when system is healthy

**Solution**: Adjust budgets based on actual performance:
```bash
# Run without strict budgets to establish baseline
python tools/load_smoke.py --requests 50

# Note actual p95, then set budget with headroom
python tools/load_smoke.py --budget-p95 <actual_p95 * 1.2>
```

---

## Best Practices

### ✅ DO

- Run smoke tests before each deploy
- Set realistic budgets based on SLOs
- Test fallback paths regularly
- Monitor trends over time
- Save results for comparison
- Test in staging before production

### ❌ DON'T

- Set budgets too strict (causes false positives)
- Run at full production load (use dedicated load testing)
- Ignore budget failures
- Skip fallback path testing
- Test only happy path

---

## Integration Examples

### CI/CD Pipeline (GitHub Actions)

```yaml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install requests
      
      - name: Start API
        run: |
          python app.py &
          sleep 5
      
      - name: Run smoke test
        run: |
          python tools/load_smoke.py \
            --requests 50 \
            --concurrency 10 \
            --budget-p95 1500
      
      - name: Deploy if passed
        if: success()
        run: ./deploy.sh
```

### Local Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-push

echo "Running smoke test..."
python tools/load_smoke.py --requests 20 --concurrency 5

if [ $? -ne 0 ]; then
    echo "❌ Smoke test failed. Push aborted."
    exit 1
fi

echo "✅ Smoke test passed. Proceeding with push."
```

### Cron Job for Monitoring

```bash
# Hourly smoke test with alerts
0 * * * * cd /app && python tools/load_smoke.py --output /tmp/smoke_$(date +\%Y\%m\%d_\%H).json || echo "Smoke test failed" | mail -s "Alert: Smoke Test Failed" ops@example.com
```

---

## FAQ

**Q: How many requests should I send?**

A: Start with 20-50 for quick smoke tests. Use 100+ for more reliable percentile measurements.

**Q: What concurrency should I use?**

A: Start with 5-10. Increase based on expected production load, but don't exceed system capacity.

**Q: What if I don't have the API running?**

A: The script will show connection errors. Start the API first: `python app.py`

**Q: Can I test against production?**

A: Yes, but be careful with load. Use low concurrency: `--concurrency 2 --requests 10`

**Q: How do I know if my budgets are right?**

A: Run without budgets first, observe actual performance, then set budgets with 20-30% headroom.

**Q: What does --pinecone-down actually do?**

A: It sends a header to simulate Pinecone failures. The API should fall back to alternative methods (like pgvector).

---

## Summary

✅ **Quick**: Run in seconds for fast feedback
✅ **Parallel**: Tests concurrent load handling
✅ **Measurable**: p50/p95/p99 latencies
✅ **Assertable**: Fails when budgets exceeded
✅ **Fallback-aware**: Tracks degraded mode usage
✅ **CI-ready**: Exit codes for automation
✅ **Flexible**: Configurable via CLI

**Typical Workflow**:
1. Run smoke test locally before commit
2. Run in CI before deploy
3. Run in staging with --pinecone-down
4. Monitor production with cron job

---

**See Also**:
- [Full Implementation](tools/load_smoke.py)
- [Latency Gates](LATENCY_GATES_QUICKSTART.md)
- [Resource Limits](RESOURCE_LIMITS_QUICKSTART.md)

**Status**: ✅ Ready to Use
**Version**: 1.0
**Last Updated**: 2025-11-04
