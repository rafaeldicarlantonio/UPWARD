# External Comparison System - Operator Guide

**Version**: 1.0  
**Date**: 2025-10-30  
**Status**: Production Ready

---

## Overview

The external comparison system allows augmenting internal knowledge with content from trusted external sources (Wikipedia, arXiv, etc.) for display purposes only. External content is **never persisted** to the internal knowledge base.

### Key Features

- **Whitelist-based source control**: Only approved sources can be fetched
- **Token-bucket rate limiting**: Prevents abuse and respects source limits
- **Role-based access**: Only Pro, Scholars, and Analytics roles can use
- **Timeout enforcement**: Fast failure on slow sources
- **Graceful fallback**: Internal results always returned
- **Never persisted**: External content displayed only, never stored
- **Full observability**: Metrics and audit logs for all operations

---

## Architecture

```
User Request
    │
    ├─► Feature Flag Check (external_compare)
    │   └─► OFF → Internal-only
    │   └─► ON → Continue
    │
    ├─► Role Gate (can_use_external_compare)
    │   └─► General → Denied (audit logged)
    │   └─► Pro/Scholars/Analytics → Continue
    │
    ├─► Whitelist Check (URLMatcher)
    │   └─► Not whitelisted → Skip
    │   └─► Whitelisted → Continue
    │
    ├─► Rate Limit Check (RateLimiter)
    │   └─► Limit exceeded → Skip (logged)
    │   └─► Within limit → Continue
    │
    ├─► Fetch with Timeout (ExternalComparer)
    │   ├─► Success → Add to results
    │   ├─► Timeout → Log, continue with others
    │   └─► Error → Log, continue with others
    │
    ├─► Persistence Guard (CRITICAL)
    │   └─► External items BLOCKED from memories/entities
    │
    └─► Response
        ├─► Internal results (ALWAYS present)
        └─► External sources (separate section if available)
```

---

## Configuration Files

### Location

```
/workspace/config/
├── external_sources_whitelist.json  # Approved sources
└── compare_policy.yaml              # Policies and limits
```

### 1. External Sources Whitelist

**File**: `config/external_sources_whitelist.json`

**Format**:
```json
[
  {
    "source_id": "wikipedia",
    "label": "Wikipedia",
    "priority": 10,
    "url_pattern": "https://*.wikipedia.org/*",
    "max_snippet_chars": 480,
    "enabled": true
  },
  {
    "source_id": "arxiv",
    "label": "arXiv",
    "priority": 9,
    "url_pattern": "https://arxiv.org/*",
    "max_snippet_chars": 640,
    "enabled": true
  },
  {
    "source_id": "scholar",
    "label": "Google Scholar",
    "priority": 8,
    "url_pattern": "https://scholar.google.com/*",
    "max_snippet_chars": 400,
    "enabled": false
  }
]
```

**Field Definitions**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | string | Yes | Unique identifier for the source |
| `label` | string | Yes | Human-readable display name |
| `priority` | integer | Yes | Priority for selection (higher = higher priority) |
| `url_pattern` | string | Yes | Glob or regex pattern for URL matching |
| `max_snippet_chars` | integer | Yes | Maximum snippet length for this source |
| `enabled` | boolean | Yes | Whether source is active |

**URL Pattern Syntax**:
- Glob patterns: `*` matches any characters, `?` matches single character
- Supports subdomain wildcards: `https://*.wikipedia.org/*`
- Case-insensitive matching

### 2. Comparison Policy

**File**: `config/compare_policy.yaml`

**Format**:
```yaml
# Maximum number of external sources to fetch per request
max_external_sources_per_run: 5

# Maximum total characters from all external sources
max_total_external_chars: 2400

# Roles allowed to use external comparison
allowed_roles_for_external:
  - pro
  - scholars
  - analytics

# Timeout per external request (milliseconds)
timeout_ms_per_request: 2000

# Rate limit per domain per minute
rate_limit_per_domain_per_min: 6

# Tie-breaking strategy when internal and external conflict
tie_break: "prefer_internal"  # prefer_internal | prefer_external | abstain

# Patterns to redact from external content (regex)
redact_patterns:
  - "Authorization:\\s+\\S+"
  - "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/=]+"
```

**Field Definitions**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_external_sources_per_run` | integer | 5 | Max external sources to fetch |
| `max_total_external_chars` | integer | 2400 | Total character limit |
| `allowed_roles_for_external` | list[string] | `[pro, scholars, analytics]` | Roles with access |
| `timeout_ms_per_request` | integer | 2000 | Timeout per fetch (ms) |
| `rate_limit_per_domain_per_min` | integer | 6 | Per-domain rate limit |
| `tie_break` | string | prefer_internal | Conflict resolution strategy |
| `redact_patterns` | list[string] | `[]` | Regex patterns for redaction |

---

## Feature Flags

The external comparison system uses two feature flags:

```python
# In feature_flags.py or environment
FEATURE_FLAGS = {
    "external_compare": False,  # Master switch for external comparison
    "factare.enabled": True,    # Required for /factate API
    "factare.allow_external": True  # Allow external in factare service
}
```

**Flag Hierarchy**:
1. `external_compare` - Master switch (must be `true`)
2. `factare.allow_external` - Service-level switch (must be `true`)
3. Role gate - User must have allowed role
4. Configuration - Sources must be enabled

---

## Rollout Order

### Phase 1: Configuration Setup (Pre-Rollout)

1. **Create configuration files**:
   ```bash
   # Start with minimal whitelist
   cat > config/external_sources_whitelist.json << 'EOF'
   [
     {
       "source_id": "wikipedia",
       "label": "Wikipedia",
       "priority": 10,
       "url_pattern": "https://*.wikipedia.org/*",
       "max_snippet_chars": 480,
       "enabled": true
     }
   ]
   EOF
   
   # Use conservative policy
   cat > config/compare_policy.yaml << 'EOF'
   max_external_sources_per_run: 3
   max_total_external_chars: 1200
   allowed_roles_for_external:
     - analytics  # Start with most privileged only
   timeout_ms_per_request: 1000  # Fast timeout
   rate_limit_per_domain_per_min: 3  # Conservative
   tie_break: "prefer_internal"
   redact_patterns:
     - "Authorization:\\s+\\S+"
     - "Bearer\\s+[A-Za-z0-9\\-._~+/=]+"
   EOF
   ```

2. **Validate configuration**:
   ```bash
   # Test config loading
   python3 -c "
   from core.config_loader import get_loader
   loader = get_loader()
   whitelist = loader.get_whitelist()
   policy = loader.get_compare_policy()
   print(f'Loaded {len(whitelist)} sources')
   print(f'Allowed roles: {policy.allowed_roles_for_external}')
   "
   ```

3. **Verify persistence guards**:
   ```bash
   # Run guard tests
   pytest tests/external/test_non_ingest.py -v
   ```

### Phase 2: Limited Rollout (Analytics Only)

1. **Enable for Analytics role only**:
   ```yaml
   # config/compare_policy.yaml
   allowed_roles_for_external:
     - analytics  # Only analytics initially
   ```

2. **Enable feature flags**:
   ```bash
   # In environment or feature_flags.py
   export FEATURE_FLAG_EXTERNAL_COMPARE=true
   ```

3. **Test with Analytics user**:
   ```bash
   curl -X POST http://localhost:8000/factate/compare \
     -H "Content-Type: application/json" \
     -H "X-User-Roles: analytics" \
     -d '{
       "query": "What is machine learning?",
       "retrieval_candidates": [
         {
           "id": "mem_1",
           "content": "ML is a subset of AI",
           "source": "internal",
           "score": 0.9
         }
       ],
       "external_urls": ["https://en.wikipedia.org/wiki/Machine_learning"],
       "user_roles": ["analytics"],
       "options": {
         "allow_external": true,
         "timeout_seconds": 2
       }
     }'
   ```

4. **Monitor metrics** (let run for 24 hours):
   ```bash
   # Check denial rate
   curl http://localhost:8000/debug/metrics | jq '.counters."external.compare.denied"'
   
   # Check timeout rate
   curl http://localhost:8000/debug/metrics | jq '.counters."external.compare.timeouts"'
   
   # Check average duration
   curl http://localhost:8000/debug/metrics | jq '.histograms."external.compare.ms"'
   ```

5. **Review audit logs**:
   ```bash
   # Check for denials
   grep "EXTERNAL_COMPARE_DENIAL" logs/application.log
   
   # Check for timeouts
   grep "EXTERNAL_COMPARE_TIMEOUT" logs/application.log
   ```

### Phase 3: Expand to Pro and Scholars

1. **Update policy** (if Phase 2 metrics look good):
   ```yaml
   # config/compare_policy.yaml
   allowed_roles_for_external:
     - analytics
     - pro
     - scholars
   ```

2. **Increase limits** (if needed):
   ```yaml
   max_external_sources_per_run: 5
   rate_limit_per_domain_per_min: 6
   timeout_ms_per_request: 2000
   ```

3. **Test with Pro user**:
   ```bash
   curl -X POST http://localhost:8000/factate/compare \
     -H "X-User-Roles: pro" \
     -d '{ ... }'  # Same payload as before
   ```

4. **Monitor for 48 hours** and review metrics

### Phase 4: Add More Sources

1. **Add one source at a time**:
   ```json
   {
     "source_id": "arxiv",
     "label": "arXiv",
     "priority": 9,
     "url_pattern": "https://arxiv.org/*",
     "max_snippet_chars": 640,
     "enabled": true
   }
   ```

2. **Test new source**:
   ```bash
   curl -X POST http://localhost:8000/factate/compare \
     -H "X-User-Roles: analytics" \
     -d '{
       "query": "neural networks research",
       "retrieval_candidates": [...],
       "external_urls": ["https://arxiv.org/abs/1234.5678"],
       "options": {"allow_external": true}
     }'
   ```

3. **Monitor source-specific metrics**:
   ```bash
   # Check fetch success rate by domain
   curl http://localhost:8000/debug/metrics | \
     jq '.counters | to_entries | map(select(.key | contains("arxiv.org")))'
   ```

---

## Testing from curl

### Basic Internal-Only Test

```bash
curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: pro" \
  -d '{
    "query": "What is machine learning?",
    "retrieval_candidates": [
      {
        "id": "mem_1",
        "content": "Machine learning is a subset of artificial intelligence.",
        "source": "internal_memory",
        "score": 0.95
      }
    ]
  }'
```

**Expected Response**:
```json
{
  "compare_summary": {
    "query": "What is machine learning?",
    "internal_sources": [...],
    "summary_text": "..."
  },
  "contradictions": [],
  "used_external": false,
  "sources": {
    "internal": 1,
    "external": 0
  },
  "timings": {...},
  "metadata": {...}
}
```

### External Comparison Test (Allowed User)

```bash
curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: pro" \
  -H "X-User-ID: user_123" \
  -d '{
    "query": "What is machine learning?",
    "retrieval_candidates": [
      {
        "id": "mem_1",
        "content": "Machine learning is a subset of AI.",
        "source": "internal_memory",
        "score": 0.95
      }
    ],
    "external_urls": [
      "https://en.wikipedia.org/wiki/Machine_learning"
    ],
    "user_roles": ["pro"],
    "options": {
      "allow_external": true,
      "timeout_seconds": 2,
      "max_external_snippets": 5
    }
  }' | jq .
```

**Expected Response** (when feature enabled):
```json
{
  "compare_summary": {
    "query": "What is machine learning?",
    "internal_sources": [...],
    "external_sources": {
      "heading": "External sources",
      "items": [
        {
          "url": "https://en.wikipedia.org/wiki/Machine_learning",
          "snippet": "Machine learning (ML) is a field of artificial intelligence...",
          "label": "Wikipedia",
          "host": "en.wikipedia.org",
          "provenance": {
            "url": "https://en.wikipedia.org/wiki/Machine_learning",
            "fetched_at": "2025-10-30T12:00:00Z"
          },
          "external": true
        }
      ]
    },
    "summary_text": "..."
  },
  "used_external": true,
  "sources": {
    "internal": 1,
    "external": 1
  },
  "timings": {
    "internal_ms": 123.4,
    "external_ms": 456.7,
    "total_ms": 580.1
  }
}
```

### Test Denial (General User)

```bash
curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: general" \
  -H "X-User-ID: user_456" \
  -d '{
    "query": "What is machine learning?",
    "retrieval_candidates": [...],
    "external_urls": ["https://en.wikipedia.org/wiki/Machine_learning"],
    "user_roles": ["general"],
    "options": {"allow_external": true}
  }' | jq .
```

**Expected**: Internal-only response with `used_external: false`

**Audit Log**:
```
WARNING EXTERNAL_COMPARE_DENIAL user=user_456 roles=general reason=insufficient_permissions
```

### Test Timeout

```bash
curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: pro" \
  -d '{
    "query": "test query",
    "retrieval_candidates": [...],
    "external_urls": ["https://very-slow-site.example.com/page"],
    "user_roles": ["pro"],
    "options": {
      "allow_external": true,
      "timeout_seconds": 1
    }
  }' | jq .
```

**Expected**: Internal-only response (timeout triggers fallback)

**Audit Log**:
```
WARNING EXTERNAL_COMPARE_TIMEOUT url=https://very-slow-site.example.com/page domain=very-slow-site.example.com timeout_ms=1000
```

---

## Adding a New Source Safely

### Step-by-Step Process

#### 1. Add Source Configuration (Disabled)

Add to `config/external_sources_whitelist.json`:

```json
{
  "source_id": "pubmed",
  "label": "PubMed",
  "priority": 8,
  "url_pattern": "https://pubmed.ncbi.nlm.nih.gov/*",
  "max_snippet_chars": 500,
  "enabled": false  // Start disabled
}
```

**Commit and deploy** configuration change.

#### 2. Validate Configuration

```bash
# Verify config loads without errors
python3 -c "
from core.config_loader import get_loader
loader = get_loader()
sources = loader.get_whitelist(enabled_only=False)
pubmed = [s for s in sources if s.source_id == 'pubmed']
print(f'PubMed config: {pubmed[0].__dict__}')
"
```

#### 3. Test Offline

```bash
# Test URL pattern matching
python3 << 'EOF'
from core.config_loader import get_loader
from core.whitelist import create_matcher_and_limiter

loader = get_loader()
matcher, _ = create_matcher_and_limiter(loader)

# Test various PubMed URLs
test_urls = [
    "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    "https://pubmed.ncbi.nlm.nih.gov/search/?term=cancer",
    "https://example.com/not-pubmed"
]

for url in test_urls:
    match = matcher.match(url)
    if match:
        print(f"✅ {url} -> {match.source_id}")
    else:
        print(f"❌ {url} -> No match")
EOF
```

#### 4. Enable Source

Update `config/external_sources_whitelist.json`:

```json
{
  "source_id": "pubmed",
  "enabled": true  // Enable
}
```

#### 5. Test with Real Request

```bash
# Test with Analytics user first
curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: analytics" \
  -H "X-User-ID: ops_test" \
  -d '{
    "query": "cancer research",
    "retrieval_candidates": [...],
    "external_urls": ["https://pubmed.ncbi.nlm.nih.gov/12345678/"],
    "user_roles": ["analytics"],
    "options": {"allow_external": true}
  }' | jq '.sources, .used_external'
```

**Expected**:
```json
{
  "sources": {
    "internal": 1,
    "external": 1
  },
  "used_external": true
}
```

#### 6. Monitor Metrics

```bash
# Watch for 24 hours
watch -n 60 'curl -s http://localhost:8000/debug/metrics | \
  jq "{
    pubmed_success: .counters[\"external.compare.fetches.success\"] | 
                    map(select(.labels.domain == \"pubmed.ncbi.nlm.nih.gov\"))[0].value,
    pubmed_failed: .counters[\"external.compare.fetches.failed\"] | 
                   map(select(.labels.domain == \"pubmed.ncbi.nlm.nih.gov\"))[0].value,
    pubmed_timeouts: .counters[\"external.compare.timeouts.by_domain\"] | 
                     map(select(.labels.domain == \"pubmed.ncbi.nlm.nih.gov\"))[0].value
  }"'
```

#### 7. Review and Adjust

If success rate < 80% or timeout rate > 20%:
- Increase `timeout_ms_per_request`
- Decrease `priority` (try less frequently)
- Or disable and investigate

---

## Non-Ingestion Guarantee

### The Guarantee

**External content is NEVER persisted to the database.**

This is enforced by multiple layers:

### Layer 1: External Markers

All external items are marked:
```python
{
  "url": "https://en.wikipedia.org/...",
  "external": True,  # Top-level marker
  "provenance": {
    "url": "https://en.wikipedia.org/..."  # URL in provenance
  },
  "metadata": {
    "external": True,  # Metadata marker
    "url": "https://en.wikipedia.org/..."
  }
}
```

### Layer 2: Persistence Guards

All persistence paths protected:
```python
from core.guards import forbid_external_persistence

# Before ANY database write
forbid_external_persistence(
    items=items_to_write,
    item_type="memory",
    raise_on_external=True  # Raises ExternalPersistenceError
)
```

**Protected paths**:
- `ingest/pipeline.py::upsert_memories_from_chunks()` - Memories table
- `ingest/commit.py::commit_analysis()` - Entities and edges
- Any entity/edge upsert operations

### Layer 3: Detection Logic

The guard detects external items by checking:
1. `item.provenance.url` exists
2. `item.source_url` exists
3. `item.external == True`
4. `item.metadata.external == True`
5. `item.metadata.url` exists

**Any of these triggers the block.**

### Layer 4: Audit Logging

All blocked attempts are logged:
```
WARNING PERSISTENCE_GUARD Blocked external content from memories upsert: 
  items=1 urls=['https://en.wikipedia.org/...']
```

### Verification

You can verify the guarantee:

```bash
# Run persistence guard tests
pytest tests/external/test_non_ingest.py::TestAcceptanceCriteria -v

# Check that guard blocks external items
pytest tests/external/test_non_ingest.py::TestIngestPipelineIntegration -v

# Verify external items have required markers
pytest tests/external/test_api_contract.py::TestExternalProvenance -v
```

---

## Monitoring

### Key Metrics to Watch

#### Request Metrics

```bash
# Total requests with external enabled
curl http://localhost:8000/debug/metrics | \
  jq '.counters."external.compare.requests"'

# Allowed vs denied
curl http://localhost:8000/debug/metrics | \
  jq '{
    allowed: .counters."external.compare.allowed",
    denied: .counters."external.compare.denied"
  }'
```

#### Performance Metrics

```bash
# Average comparison duration
curl http://localhost:8000/debug/metrics | \
  jq '.histograms."external.compare.ms"[0].stats'

# Output example:
{
  "count": 150,
  "sum": 45000.0,
  "avg": 300.0,
  "buckets": {
    "100.0": 20,
    "250.0": 50,
    "500.0": 70,
    "1000.0": 10
  }
}
```

#### Timeout and Fallback Metrics

```bash
# Timeout rate
curl http://localhost:8000/debug/metrics | \
  jq '{
    timeouts: .counters."external.compare.timeouts",
    requests: .counters."external.compare.requests",
    rate: (.counters."external.compare.timeouts"[0].value / 
           .counters."external.compare.requests"[0].value)
  }'

# Fallback reasons
curl http://localhost:8000/debug/metrics | \
  jq '.counters."external.compare.fallbacks"'
```

#### Policy Configuration

```bash
# Current policy values (gauges)
curl http://localhost:8000/debug/metrics | \
  jq '{
    max_sources: .gauges."external.policy.max_sources",
    timeout_ms: .gauges."external.policy.timeout_ms"
  }'
```

### Alert Thresholds

**Recommended alerts**:

```yaml
# High denial rate (>30%)
- alert: HighExternalCompareDenialRate
  expr: |
    (external_compare_denied / external_compare_requests) > 0.3
  severity: warning

# High timeout rate (>20%)
- alert: HighExternalCompareTimeoutRate
  expr: |
    (external_compare_timeouts / external_compare_requests) > 0.2
  severity: warning

# Slow performance (p95 > 1 second)
- alert: SlowExternalComparison
  expr: |
    external_compare_ms_p95 > 1000
  severity: info

# Frequent fallbacks
- alert: FrequentExternalFallbacks
  expr: |
    rate(external_compare_fallbacks[5m]) > 10
  severity: warning
```

---

## Audit Logs

### Log Locations

**Production**:
```bash
/var/log/application/audit.log        # Structured audit logs
/var/log/application/application.log  # General application logs
```

**Development**:
```bash
logs/audit.log
logs/application.log
```

### Searching Audit Logs

#### Find All Denials

```bash
grep "EXTERNAL_COMPARE_DENIAL" /var/log/application/audit.log

# Example output:
WARNING EXTERNAL_COMPARE_DENIAL user=user_123 roles=general reason=insufficient_permissions
WARNING EXTERNAL_COMPARE_DENIAL user=user_456 roles=general reason=insufficient_permissions
```

#### Find Timeouts for Specific Domain

```bash
grep "EXTERNAL_COMPARE_TIMEOUT" /var/log/application/audit.log | \
  grep "slow.example.com"

# Example output:
WARNING EXTERNAL_COMPARE_TIMEOUT url=https://slow.example.com/page domain=slow.example.com timeout_ms=2000 user=user_789
```

#### Parse Structured Audit Entries

If using JSON logging:

```bash
# Get denial count by user
jq -r 'select(.audit.event == "external_compare_denial") | .audit.user_id' audit.json | \
  sort | uniq -c | sort -rn

# Get timeout count by domain
jq -r 'select(.audit.event == "external_compare_timeout") | .audit.domain' audit.json | \
  sort | uniq -c | sort -rn
```

---

## Troubleshooting

### Issue: External comparison not working

**Symptoms**: `used_external: false` even when requested

**Checklist**:
1. Check feature flags:
   ```bash
   curl http://localhost:8000/debug/flags | jq '.external_compare'
   ```

2. Check user role:
   ```bash
   # Verify role is in allowed list
   cat config/compare_policy.yaml | grep -A 3 allowed_roles_for_external
   ```

3. Check whitelist:
   ```bash
   # Verify URL matches pattern
   python3 -c "
   from core.config_loader import get_loader
   from core.whitelist import create_matcher_and_limiter
   loader = get_loader()
   matcher, _ = create_matcher_and_limiter(loader)
   match = matcher.match('YOUR_URL_HERE')
   print(f'Match: {match}')
   "
   ```

4. Check rate limits:
   ```bash
   # Check if domain is rate limited
   curl http://localhost:8000/debug/metrics | \
     jq '.counters."external.compare.rate_limited"'
   ```

5. Check audit logs:
   ```bash
   # Look for denials
   grep "EXTERNAL_COMPARE_DENIAL" logs/audit.log | tail -5
   ```

### Issue: High timeout rate

**Symptoms**: Many requests timing out

**Solutions**:

1. Increase timeout:
   ```yaml
   # config/compare_policy.yaml
   timeout_ms_per_request: 3000  # Increase from 2000
   ```

2. Lower priority of slow sources:
   ```json
   // config/external_sources_whitelist.json
   {
     "source_id": "slow_source",
     "priority": 5  // Lower priority (was 9)
   }
   ```

3. Disable problematic source:
   ```json
   {
     "source_id": "slow_source",
     "enabled": false  // Disable temporarily
   }
   ```

### Issue: Rate limit errors

**Symptoms**: Frequent `rate_limited` metrics

**Solutions**:

1. Increase rate limit:
   ```yaml
   # config/compare_policy.yaml
   rate_limit_per_domain_per_min: 10  # Increase from 6
   ```

2. Reduce max sources:
   ```yaml
   max_external_sources_per_run: 3  # Reduce from 5
   ```

3. Spread requests across more domains (add more sources)

---

## Configuration Validation

### Run Validation Tests

```bash
# Test configuration loading
pytest tests/external/test_config_loader.py -v

# Test whitelist matching
pytest tests/external/test_whitelist_rate.py::TestURLMatcherPatterns -v

# Test policy loading
pytest tests/external/test_config_loader.py::TestComparePolicyValidation -v
```

### Validate Syntax

**JSON validation**:
```bash
# Check JSON syntax
python3 -m json.tool config/external_sources_whitelist.json > /dev/null && \
  echo "✅ JSON valid" || echo "❌ JSON invalid"
```

**YAML validation**:
```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('config/compare_policy.yaml'))" && \
  echo "✅ YAML valid" || echo "❌ YAML invalid"
```

### Test Configuration Changes

```bash
# Before deploying config changes, test locally
python3 << 'EOF'
from core.config_loader import ConfigLoader
import json
import yaml

# Load your test config
with open('config/external_sources_whitelist.json') as f:
    whitelist_data = json.load(f)

with open('config/compare_policy.yaml') as f:
    policy_data = yaml.safe_load(f)

# Validate
loader = ConfigLoader(
    whitelist_path='config/external_sources_whitelist.json',
    policy_path='config/compare_policy.yaml'
)

whitelist = loader.get_whitelist()
policy = loader.get_compare_policy()

print(f"✅ Loaded {len(whitelist)} sources")
print(f"✅ Policy: max_sources={policy.max_external_sources_per_run}")
print(f"✅ Policy: allowed_roles={policy.allowed_roles_for_external}")
EOF
```

---

## Examples

### Example 1: Basic Wikipedia Lookup

```bash
#!/bin/bash
# test_wikipedia.sh

curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: pro" \
  -H "X-User-ID: test_user" \
  -d '{
    "query": "What is Python programming language?",
    "retrieval_candidates": [
      {
        "id": "mem_python_1",
        "content": "Python is a high-level programming language.",
        "source": "internal_memory",
        "score": 0.92
      }
    ],
    "external_urls": [
      "https://en.wikipedia.org/wiki/Python_(programming_language)"
    ],
    "user_roles": ["pro"],
    "options": {
      "allow_external": true,
      "timeout_seconds": 2
    }
  }' | jq '{
    used_external: .used_external,
    internal_count: .sources.internal,
    external_count: .sources.external,
    external_sources: .compare_summary.external_sources.items[0].label,
    duration_ms: .timings.total_ms
  }'
```

### Example 2: Multi-Source Comparison

```bash
#!/bin/bash
# test_multi_source.sh

curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: analytics" \
  -d '{
    "query": "machine learning algorithms",
    "retrieval_candidates": [
      {
        "id": "mem_ml_1",
        "content": "Common ML algorithms include decision trees and neural networks.",
        "source": "internal_memory",
        "score": 0.88
      }
    ],
    "external_urls": [
      "https://en.wikipedia.org/wiki/Machine_learning",
      "https://arxiv.org/abs/1234.5678"
    ],
    "user_roles": ["analytics"],
    "options": {
      "allow_external": true,
      "max_external_snippets": 5,
      "timeout_seconds": 3
    }
  }' | jq '{
    used_external: .used_external,
    sources: .sources,
    external_items: .compare_summary.external_sources.items | length
  }'
```

### Example 3: Test Graceful Fallback

```bash
#!/bin/bash
# test_fallback.sh

# Request external but with very short timeout
# Should fall back to internal-only

curl -X POST http://localhost:8000/factate/compare \
  -H "Content-Type: application/json" \
  -H "X-User-Roles: pro" \
  -d '{
    "query": "test query",
    "retrieval_candidates": [
      {
        "id": "mem_1",
        "content": "Internal content",
        "source": "internal",
        "score": 0.9
      }
    ],
    "external_urls": ["https://en.wikipedia.org/wiki/Very_long_page"],
    "user_roles": ["pro"],
    "options": {
      "allow_external": true,
      "timeout_seconds": 0.1  // Very short timeout
    }
  }' | jq '{
    used_external: .used_external,
    internal_count: .sources.internal,
    external_count: .sources.external,
    message: "Internal results still returned despite timeout"
  }'
```

**Expected**: `used_external: false`, but internal results still present

### Example 4: Check Metrics Dashboard

```bash
#!/bin/bash
# metrics_dashboard.sh

echo "External Comparison Metrics Dashboard"
echo "======================================"
echo

curl -s http://localhost:8000/debug/metrics | jq '
{
  "Total Requests": .counters."external.compare.requests"[0].value,
  "Allowed": .counters."external.compare.allowed"[0].value,
  "Denied": .counters."external.compare.denied"[0].value,
  "With Externals": .counters."external.compare.with_externals"[0].value,
  "Internal Only": .counters."external.compare.internal_only"[0].value,
  "Timeouts": .counters."external.compare.timeouts"[0].value,
  "Fallbacks": .counters."external.compare.fallbacks"[0].value,
  "Avg Duration (ms)": .histograms."external.compare.ms"[0].stats.avg,
  "Policy Max Sources": .gauges."external.policy.max_sources"[0].value,
  "Policy Timeout (ms)": .gauges."external.policy.timeout_ms"[0].value
}
' | column -t
```

---

## Security Best Practices

### 1. Whitelist Only Trusted Sources

**DO**:
- Government sites (`.gov`)
- Academic institutions (`.edu`)
- Well-known public databases (Wikipedia, arXiv, PubMed)

**DON'T**:
- User-generated content sites
- Social media
- Forums or discussion boards
- Sites with paywalls
- Sites requiring authentication

### 2. Use Conservative Rate Limits

Start with:
```yaml
rate_limit_per_domain_per_min: 3  # Very conservative
max_external_sources_per_run: 2    # Minimal
```

Increase gradually based on:
- Success rate > 90%
- Timeout rate < 10%
- No rate limit errors from sources

### 3. Aggressive Redaction

Always redact:
```yaml
redact_patterns:
  - "Authorization:\\s+\\S+"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/=]+"
  - "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"  # Emails
  - "api[_-]?key[\\s:=]+\\S+"  # API keys
  - "password[\\s:=]+\\S+"     # Passwords
  - "token[\\s:=]+\\S+"        # Tokens
```

### 4. Monitor Audit Logs

Set up alerting for:
- Unusual denial patterns
- Repeated timeout from same user
- Attempts to access non-whitelisted sources

### 5. Regular Review

**Monthly**:
- Review enabled sources (disable unused)
- Review timeout rates (adjust or remove slow sources)
- Review denial patterns (adjust policies or educate users)

**Quarterly**:
- Audit all whitelisted sources (still trustworthy?)
- Review and update redaction patterns
- Analyze usage by role (adjust allowed_roles if needed)

---

## Configuration Examples

### Minimal Production Config

**Whitelist** (1 source only):
```json
[
  {
    "source_id": "wikipedia",
    "label": "Wikipedia",
    "priority": 10,
    "url_pattern": "https://*.wikipedia.org/*",
    "max_snippet_chars": 400,
    "enabled": true
  }
]
```

**Policy** (very conservative):
```yaml
max_external_sources_per_run: 2
max_total_external_chars: 1000
allowed_roles_for_external:
  - analytics
timeout_ms_per_request: 1000
rate_limit_per_domain_per_min: 3
tie_break: "prefer_internal"
redact_patterns:
  - "Authorization:\\s+\\S+"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/=]+"
```

### Expanded Production Config

**Whitelist** (multiple trusted sources):
```json
[
  {
    "source_id": "wikipedia",
    "label": "Wikipedia",
    "priority": 10,
    "url_pattern": "https://*.wikipedia.org/*",
    "max_snippet_chars": 480,
    "enabled": true
  },
  {
    "source_id": "arxiv",
    "label": "arXiv",
    "priority": 9,
    "url_pattern": "https://arxiv.org/*",
    "max_snippet_chars": 640,
    "enabled": true
  },
  {
    "source_id": "pubmed",
    "label": "PubMed",
    "priority": 8,
    "url_pattern": "https://pubmed.ncbi.nlm.nih.gov/*",
    "max_snippet_chars": 500,
    "enabled": true
  },
  {
    "source_id": "stanford_encyclopedia",
    "label": "Stanford Encyclopedia of Philosophy",
    "priority": 7,
    "url_pattern": "https://plato.stanford.edu/*",
    "max_snippet_chars": 600,
    "enabled": true
  }
]
```

**Policy** (balanced):
```yaml
max_external_sources_per_run: 5
max_total_external_chars: 2400
allowed_roles_for_external:
  - pro
  - scholars
  - analytics
timeout_ms_per_request: 2000
rate_limit_per_domain_per_min: 6
tie_break: "prefer_internal"
redact_patterns:
  - "Authorization:\\s+\\S+"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/=]+"
  - "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
  - "api[_-]?key[\\s:=]+\\S+"
```

---

## Quick Reference

### Enable External Comparison

```bash
# 1. Create configs
cp config/external_sources_whitelist.json.example config/external_sources_whitelist.json
cp config/compare_policy.yaml.example config/compare_policy.yaml

# 2. Edit configs (add sources, set limits)
vim config/external_sources_whitelist.json
vim config/compare_policy.yaml

# 3. Validate
pytest tests/external/test_config_loader.py -v

# 4. Enable feature flag
export FEATURE_FLAG_EXTERNAL_COMPARE=true

# 5. Restart application
systemctl restart factare-api

# 6. Test
curl -X POST http://localhost:8000/factate/compare -H "X-User-Roles: analytics" -d '{...}'

# 7. Monitor
watch -n 60 'curl -s http://localhost:8000/debug/metrics | jq .counters.\"external.compare.requests\"'
```

### Disable External Comparison

```bash
# 1. Set feature flag to false
export FEATURE_FLAG_EXTERNAL_COMPARE=false

# 2. Restart application
systemctl restart factare-api

# 3. Verify disabled
curl http://localhost:8000/debug/flags | jq '.external_compare'
# Should show: false
```

### Emergency Disable (Incident Response)

If external comparison is causing issues:

```bash
# Option 1: Disable via feature flag (fastest)
export FEATURE_FLAG_EXTERNAL_COMPARE=false
systemctl restart factare-api

# Option 2: Disable all sources in config
python3 << 'EOF'
import json
with open('config/external_sources_whitelist.json', 'r+') as f:
    sources = json.load(f)
    for source in sources:
        source['enabled'] = False
    f.seek(0)
    json.dump(sources, f, indent=2)
    f.truncate()
EOF

# Option 3: Remove all allowed roles
sed -i 's/allowed_roles_for_external:.*/allowed_roles_for_external: []/' \
  config/compare_policy.yaml
```

---

## Testing Checklist

Before enabling in production:

- [ ] Configuration files validated
- [ ] All persistence guard tests pass
- [ ] Contract tests pass
- [ ] Metrics tests pass
- [ ] Test with Analytics role (curl)
- [ ] Test denial for General role (curl)
- [ ] Verify audit logs appear
- [ ] Check metrics endpoint shows counters
- [ ] Test timeout handling
- [ ] Test graceful fallback
- [ ] Verify internal results always present
- [ ] Check external items have provenance
- [ ] Confirm external items not in database

---

## Maintenance

### Weekly

```bash
# Check error rates
curl http://localhost:8000/debug/metrics | \
  jq '{
    timeout_rate: (.counters."external.compare.timeouts"[0].value / 
                   .counters."external.compare.requests"[0].value),
    fallback_rate: (.counters."external.compare.fallbacks"[0].value / 
                    .counters."external.compare.requests"[0].value)
  }'

# Review audit logs for patterns
grep "EXTERNAL_COMPARE" logs/audit.log | \
  awk '{print $NF}' | sort | uniq -c | sort -rn
```

### Monthly

```bash
# Generate usage report
python3 << 'EOF'
from core.metrics import get_all_metrics
import json

metrics = get_all_metrics()

report = {
    "period": "monthly",
    "total_requests": metrics["counters"].get("external.compare.requests", [{}])[0].get("value", 0),
    "allowed": metrics["counters"].get("external.compare.allowed", [{}])[0].get("value", 0),
    "denied": metrics["counters"].get("external.compare.denied", [{}])[0].get("value", 0),
    "with_externals": metrics["counters"].get("external.compare.with_externals", [{}])[0].get("value", 0),
    "timeouts": metrics["counters"].get("external.compare.timeouts", [{}])[0].get("value", 0),
    "avg_duration_ms": metrics["histograms"].get("external.compare.ms", [{}])[0].get("stats", {}).get("avg", 0)
}

print(json.dumps(report, indent=2))
EOF
```

---

## Common Commands

```bash
# Get current config
cat config/external_sources_whitelist.json | jq .
cat config/compare_policy.yaml

# Reload config (if hot reload supported)
curl -X POST http://localhost:8000/admin/reload-config

# Check which sources are enabled
cat config/external_sources_whitelist.json | jq '.[] | select(.enabled == true) | .source_id'

# Get metrics summary
curl http://localhost:8000/debug/metrics | jq '{
  counters: .counters | keys | map(select(startswith("external."))),
  histograms: .histograms | keys | map(select(startswith("external."))),
  gauges: .gauges | keys | map(select(startswith("external.")))
}'

# Count audit denials
grep -c "EXTERNAL_COMPARE_DENIAL" logs/audit.log

# Count audit timeouts
grep -c "EXTERNAL_COMPARE_TIMEOUT" logs/audit.log

# Get recent audit events
tail -20 logs/audit.log | grep "EXTERNAL_COMPARE"
```

---

## Support and Resources

### Documentation

- **Configuration**: `docs/external-sources-config.md`
- **Role Gating**: `docs/external-comparison-role-gating.md`
- **Citation Formatting**: `docs/external-citation-formatting.md`
- **Persistence Guards**: `docs/external-persistence-guardrails.md`
- **Implementation Details**: `EXTERNAL_SOURCES_FINAL_SUMMARY.md`

### Test Files

- **Config Tests**: `tests/external/test_config_loader.py`
- **Role Gate Tests**: `tests/external/test_role_gate.py`
- **Whitelist Tests**: `tests/external/test_whitelist_rate.py`
- **Timeout Tests**: `tests/external/test_timeouts_fallback.py`
- **Guard Tests**: `tests/external/test_non_ingest.py`
- **Contract Tests**: `tests/external/test_api_contract.py`
- **Metrics Tests**: `tests/external/test_metrics_audit.py`

### Key Files

- **Core Logic**: `core/factare/compare_external.py`
- **API Endpoint**: `api/factate.py`
- **Persistence Guards**: `core/guards.py`
- **URL Matching**: `core/whitelist.py`
- **Config Loader**: `core/config_loader.py`
- **Metrics**: `core/metrics.py`

---

## FAQ

### Q: Can I add any external source?

**A**: No. Only sources explicitly whitelisted in `external_sources_whitelist.json` can be fetched. This is a security feature.

### Q: What happens if external fetch fails?

**A**: The system gracefully falls back to internal-only results. Internal results are **always** returned, even if all external fetches fail.

### Q: Can external content be saved to the knowledge base?

**A**: **No**. This is the core guarantee. External content is for display only and is blocked by persistence guards from being written to memories, entities, or edges.

### Q: How do I know if external comparison is working?

**A**: Check the response:
- `used_external: true` means external sources were included
- `sources.external > 0` confirms external items present
- `compare_summary.external_sources` contains the items

### Q: Why is external comparison disabled for General users?

**A**: This is a policy decision to:
1. Limit external API load
2. Reserve feature for paying users (Pro) or internal roles
3. Reduce potential for abuse

### Q: Can I customize which roles have access?

**A**: Yes, edit `allowed_roles_for_external` in `compare_policy.yaml`.

### Q: What if I want to completely disable external comparison?

**A**: Set `FEATURE_FLAG_EXTERNAL_COMPARE=false` or remove all `allowed_roles_for_external`.

---

## Appendix: Full Configuration Schema

### external_sources_whitelist.json Schema

```typescript
[
  {
    source_id: string;           // Required, unique ID
    label: string;               // Required, display name
    priority: number;            // Required, 1-10 (higher = more important)
    url_pattern: string;         // Required, glob or regex
    max_snippet_chars: number;   // Required, 100-1000
    enabled: boolean;            // Required, true/false
  }
]
```

### compare_policy.yaml Schema

```typescript
{
  max_external_sources_per_run: number;     // Default: 5, range: 1-20
  max_total_external_chars: number;         // Default: 2400, range: 500-10000
  allowed_roles_for_external: string[];     // Default: [pro, scholars, analytics]
  timeout_ms_per_request: number;           // Default: 2000, range: 500-10000
  rate_limit_per_domain_per_min: number;    // Default: 6, range: 1-60
  tie_break: "prefer_internal" | "prefer_external" | "abstain";
  redact_patterns: string[];                // Regex patterns
}
```

---

## Version History

- **1.0** (2025-10-30): Initial release
  - Configuration management
  - Role-based access control
  - Whitelist and rate limiting
  - Timeout and fallback
  - Persistence guards
  - Metrics and audit logging

---

**End of Document**

For questions or issues, consult the test files or implementation documentation.
