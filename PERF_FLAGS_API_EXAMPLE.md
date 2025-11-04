# Performance Flags - API Examples

## GET /debug/config

### Request
```bash
curl -X GET "http://localhost:5000/debug/config" \
  -H "X-API-Key: YOUR_API_KEY_HERE"
```

### Response
```json
{
  "config": {
    "SUPABASE_URL": "https://...",
    "EMBED_MODEL": "text-embedding-3-small",
    "EMBED_DIM": null,
    "ORCHESTRATOR_REDO_ENABLED": false,
    "LEDGER_ENABLED": false,
    "LEDGER_LEVEL": "off",
    "LEDGER_MAX_TRACE_BYTES": 100000,
    "LEDGER_SUMMARY_MAX_LINES": 4,
    "ORCHESTRATION_TIME_BUDGET_MS": 400,
    "FACTARE_ENABLED": false,
    "FACTARE_ALLOW_EXTERNAL": false,
    "FACTARE_EXTERNAL_TIMEOUT_MS": 2000,
    "FACTARE_MAX_SOURCES_INTERNAL": 24,
    "FACTARE_MAX_SOURCES_EXTERNAL": 8,
    "HYPOTHESES_PARETO_THRESHOLD": 0.65,
    "INGEST_ANALYSIS_ENABLED": false,
    "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 40,
    "INGEST_ANALYSIS_MAX_VERBS": 20,
    "INGEST_ANALYSIS_MAX_FRAMES": 10,
    "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
    "INGEST_CONTRADICTIONS_ENABLED": false,
    "INGEST_IMPLICATE_REFRESH_ENABLED": false,
    "PINECONE_API_KEY": "***REDACTED***",
    "OPENAI_API_KEY": "***REDACTED***",
    "X_API_KEY": "***REDACTED***"
  },
  "feature_flags": {
    "retrieval.dual_index": false,
    "retrieval.liftscore": false,
    "retrieval.contradictions_pack": false,
    "ingest.analysis.enabled": false,
    "ingest.contradictions.enabled": false,
    "ingest.implicate.refresh_enabled": false,
    "orchestrator.redo_enabled": false,
    "ledger.enabled": false,
    "factare.enabled": false,
    "factare.allow_external": false,
    "external_compare": false
  },
  "performance": {
    "flags": {
      "PERF_RETRIEVAL_PARALLEL": true,
      "PERF_REVIEWER_ENABLED": true,
      "PERF_PGVECTOR_ENABLED": true,
      "PERF_FALLBACKS_ENABLED": true
    },
    "budgets_ms": {
      "PERF_RETRIEVAL_TIMEOUT_MS": 450,
      "PERF_GRAPH_TIMEOUT_MS": 150,
      "PERF_COMPARE_TIMEOUT_MS": 400,
      "PERF_REVIEWER_BUDGET_MS": 500
    }
  },
  "status": "ok"
}
```

## Using jq to Extract Performance Settings

### Get all performance flags
```bash
curl -s -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config | \
  jq '.performance.flags'
```

Output:
```json
{
  "PERF_RETRIEVAL_PARALLEL": true,
  "PERF_REVIEWER_ENABLED": true,
  "PERF_PGVECTOR_ENABLED": true,
  "PERF_FALLBACKS_ENABLED": true
}
```

### Get all timeout budgets
```bash
curl -s -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config | \
  jq '.performance.budgets_ms'
```

Output:
```json
{
  "PERF_RETRIEVAL_TIMEOUT_MS": 450,
  "PERF_GRAPH_TIMEOUT_MS": 150,
  "PERF_COMPARE_TIMEOUT_MS": 400,
  "PERF_REVIEWER_BUDGET_MS": 500
}
```

### Get specific flag
```bash
curl -s -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config | \
  jq '.performance.flags.PERF_RETRIEVAL_PARALLEL'
```

Output:
```
true
```

### Calculate total budget
```bash
curl -s -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config | \
  jq '.performance.budgets_ms | to_entries | map(.value) | add'
```

Output:
```
1500
```

## Python Client Example

### Basic usage
```python
import requests

def get_performance_config(api_key: str, base_url: str = "http://localhost:5000"):
    """Get performance configuration from debug endpoint."""
    response = requests.get(
        f"{base_url}/debug/config",
        headers={"X-API-Key": api_key}
    )
    response.raise_for_status()
    return response.json()["performance"]

# Usage
perf_config = get_performance_config("YOUR_API_KEY")

# Access flags
if perf_config["flags"]["PERF_RETRIEVAL_PARALLEL"]:
    print("Parallel retrieval is enabled")

# Access budgets
retrieval_timeout = perf_config["budgets_ms"]["PERF_RETRIEVAL_TIMEOUT_MS"]
print(f"Retrieval timeout: {retrieval_timeout}ms")
```

### Monitor budget utilization
```python
import requests
import time

def check_performance_health(api_key: str, base_url: str = "http://localhost:5000"):
    """Check if current performance meets configured budgets."""
    # Get configured budgets
    config_resp = requests.get(
        f"{base_url}/debug/config",
        headers={"X-API-Key": api_key}
    )
    budgets = config_resp.json()["performance"]["budgets_ms"]
    
    # Get actual metrics
    metrics_resp = requests.get(
        f"{base_url}/debug/metrics",
        headers={"X-API-Key": api_key}
    )
    metrics = metrics_resp.json()
    
    # Compare (pseudo-code - actual metric extraction depends on your schema)
    issues = []
    
    # Example: Check if retrieval p95 exceeds budget
    # actual_retrieval_p95 = extract_p95(metrics, "retrieval")
    # if actual_retrieval_p95 > budgets["PERF_RETRIEVAL_TIMEOUT_MS"]:
    #     issues.append(f"Retrieval p95 ({actual_retrieval_p95}ms) exceeds budget")
    
    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "budgets": budgets
    }
```

### Adaptive timeout
```python
def get_timeout_with_buffer(api_key: str, operation: str, buffer_percent: float = 0.2):
    """Get timeout for operation with safety buffer."""
    perf_config = get_performance_config(api_key)
    
    budget_key_map = {
        "retrieval": "PERF_RETRIEVAL_TIMEOUT_MS",
        "graph": "PERF_GRAPH_TIMEOUT_MS",
        "compare": "PERF_COMPARE_TIMEOUT_MS",
        "review": "PERF_REVIEWER_BUDGET_MS"
    }
    
    budget_key = budget_key_map.get(operation)
    if not budget_key:
        raise ValueError(f"Unknown operation: {operation}")
    
    base_timeout = perf_config["budgets_ms"][budget_key]
    timeout_with_buffer = int(base_timeout * (1 + buffer_percent))
    
    return timeout_with_buffer

# Usage
timeout = get_timeout_with_buffer("YOUR_KEY", "retrieval", buffer_percent=0.2)
# Returns 540ms (450ms * 1.2)
```

## Shell Script Example

```bash
#!/bin/bash
# check_performance_config.sh

API_KEY="${X_API_KEY:-YOUR_DEFAULT_KEY}"
BASE_URL="${BASE_URL:-http://localhost:5000}"

echo "=== Performance Configuration ==="
echo

# Get and display config
CONFIG=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/debug/config")

# Check if request succeeded
if [ $? -ne 0 ]; then
    echo "❌ Failed to fetch config"
    exit 1
fi

# Display flags
echo "Boolean Flags:"
echo "$CONFIG" | jq -r '.performance.flags | to_entries[] | "  \(.key): \(.value)"'

echo
echo "Timeout Budgets:"
echo "$CONFIG" | jq -r '.performance.budgets_ms | to_entries[] | "  \(.key): \(.value)ms"'

# Calculate total budget
TOTAL=$(echo "$CONFIG" | jq '.performance.budgets_ms | to_entries | map(.value) | add')
echo
echo "Total Budget: ${TOTAL}ms"

# Health check
if [ "$TOTAL" -gt 2000 ]; then
    echo "⚠️  Warning: Total budget exceeds 2 seconds"
else
    echo "✅ Total budget within acceptable range"
fi
```

## Integration Example

### FastAPI Dependency
```python
from fastapi import Depends, Request
from typing import Dict, Any

async def get_perf_config(request: Request) -> Dict[str, Any]:
    """Dependency to inject performance config."""
    # Assuming config is available in app state
    return request.app.state.perf_config

@app.get("/api/search")
async def search(
    query: str,
    perf_config: Dict = Depends(get_perf_config)
):
    """Search endpoint with performance-aware timeouts."""
    timeout = perf_config["budgets_ms"]["PERF_RETRIEVAL_TIMEOUT_MS"] / 1000.0
    
    # Use timeout in retrieval call
    results = await retrieval_engine.search(
        query=query,
        timeout=timeout,
        parallel=perf_config["flags"]["PERF_RETRIEVAL_PARALLEL"]
    )
    
    return {"results": results}
```

### Django Middleware
```python
from django.conf import settings
from config import load_config, validate_perf_config

class PerformanceConfigMiddleware:
    """Middleware to attach performance config to request."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.perf_config = self._load_perf_config()
    
    def _load_perf_config(self):
        cfg = load_config()
        perf_keys = {k: v for k, v in cfg.items() if k.startswith("PERF_")}
        
        # Validate
        errors = validate_perf_config(perf_keys)
        if errors:
            logger.warning(f"Performance config validation warnings: {errors}")
        
        return perf_keys
    
    def __call__(self, request):
        request.perf_config = self.perf_config
        response = self.get_response(request)
        return response
```

## Monitoring Integration

### Prometheus Exporter
```python
from prometheus_client import Gauge

# Define gauges for budgets
retrieval_budget_gauge = Gauge(
    'perf_retrieval_budget_ms',
    'Configured retrieval timeout budget in milliseconds'
)

graph_budget_gauge = Gauge(
    'perf_graph_budget_ms',
    'Configured graph timeout budget in milliseconds'
)

def export_perf_budgets():
    """Export performance budgets as Prometheus metrics."""
    cfg = load_config()
    
    retrieval_budget_gauge.set(cfg["PERF_RETRIEVAL_TIMEOUT_MS"])
    graph_budget_gauge.set(cfg["PERF_GRAPH_TIMEOUT_MS"])
    # ... export other budgets

# Call on startup
export_perf_budgets()
```

### Grafana Dashboard Query
```promql
# Alert when p95 exceeds budget
(
  histogram_quantile(0.95, rate(retrieval_latency_ms_bucket[5m]))
  > 
  perf_retrieval_budget_ms
)
```

## Environment-Specific Configs

### Development (.env.dev)
```bash
PERF_RETRIEVAL_TIMEOUT_MS=1000
PERF_GRAPH_TIMEOUT_MS=300
PERF_REVIEWER_ENABLED=true
PERF_FALLBACKS_ENABLED=true
```

### Production (.env.prod)
```bash
PERF_RETRIEVAL_TIMEOUT_MS=450
PERF_GRAPH_TIMEOUT_MS=150
PERF_REVIEWER_ENABLED=true
PERF_FALLBACKS_ENABLED=true
```

### CI/Testing (.env.test)
```bash
PERF_RETRIEVAL_TIMEOUT_MS=2000
PERF_GRAPH_TIMEOUT_MS=500
PERF_REVIEWER_ENABLED=false
PERF_FALLBACKS_ENABLED=true
```

## Troubleshooting

### Check if flags are loaded
```bash
curl -s -H "X-API-Key: $KEY" http://localhost:5000/debug/config | \
  jq '.performance | keys'
```

Expected output:
```json
[
  "budgets_ms",
  "flags"
]
```

### Verify flag values
```bash
# Test in Python
python3 -c "from config import DEFAULTS; print([k for k in DEFAULTS if k.startswith('PERF_')])"
```

### Check for validation errors
```python
from config import load_config, validate_perf_config
errors = validate_perf_config(load_config())
if errors:
    print("Validation errors:", errors)
else:
    print("No validation errors")
```
