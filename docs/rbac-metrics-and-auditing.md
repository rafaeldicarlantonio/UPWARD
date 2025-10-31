# RBAC Metrics and Auditing

Comprehensive instrumentation for Role-Based Access Control (RBAC) operations, providing detailed metrics tracking and security audit logging.

## Overview

The RBAC metrics system tracks all authorization activities including:
- Role resolution attempts (JWT, API key, anonymous)
- Authorization checks (allowed/denied)
- Role distribution across requests
- Retrieval filtering by visibility level
- Security audit trails for access denials

## Metrics Tracked

### Resolution Metrics

**`rbac.resolutions{success=true|false}`**
- Total number of role resolution attempts
- Labels: `success` (true/false)
- Incremented by: `RoleResolutionMiddleware`

**`rbac.resolutions.by_method{method=jwt|api_key|anonymous|error}`**
- Resolution attempts by authentication method
- Labels: `method` (jwt, api_key, anonymous, error)
- Incremented by: `RoleResolutionMiddleware`

### Authorization Metrics

**`rbac.allowed`**
- Total number of successful authorization checks
- Incremented by: `@require` decorator

**`rbac.denied`**
- Total number of failed authorization checks
- Incremented by: `@require` decorator

**`rbac.allowed.by_capability{capability=CAP_NAME}`**
- Successful authorizations by capability
- Labels: `capability` (WRITE_GRAPH, PROPOSE_HYPOTHESIS, etc.)

**`rbac.denied.by_capability{capability=CAP_NAME}`**
- Failed authorizations by capability
- Labels: `capability`

**`rbac.denied.by_route{route=PATH}`**
- Failed authorizations by API route
- Labels: `route` (/entities, /hypotheses, etc.)

### Role Distribution

**`rbac.role_distribution{role=ROLE_NAME}`**
- Distribution of roles across requests
- Labels: `role` (general, pro, scholars, analytics, ops)
- Tracks which roles are actively being used

### Retrieval Filtering

**`retrieval.filtered_items`**
- Total number of items filtered during retrieval
- Tracks visibility-level filtering

**`retrieval.total_items`**
- Total items before filtering

**`retrieval.filtered_by_role{role=ROLE_NAME}`**
- Items filtered per role
- Labels: `role`

### Audit Metrics

**`rbac.audit.denials`**
- Total number of denials logged to audit trail
- Each denial creates a structured log entry

**`rbac.audit.denials.by_capability{capability=CAP_NAME}`**
- Audit denials by capability
- Labels: `capability`

## Usage

### Recording Metrics Programmatically

```python
from core.metrics import (
    record_rbac_resolution,
    record_rbac_check,
    record_role_distribution,
    record_retrieval_filtered,
    audit_rbac_denial,
)

# Record role resolution
record_rbac_resolution(success=True, auth_method="jwt")

# Record authorization check
record_rbac_check(
    allowed=True,
    capability="WRITE_GRAPH",
    roles=["analytics"],
    route="/entities"
)

# Record role distribution
record_role_distribution("pro")

# Record retrieval filtering
record_retrieval_filtered(
    filtered_count=5,
    total_count=10,
    caller_roles=["general"]
)

# Audit a denial
audit_rbac_denial(
    capability="WRITE_GRAPH",
    user_id="user-123",
    roles=["general"],
    route="/entities",
    method="POST",
    metadata={"ip": "192.168.1.1"}
)
```

### Automatic Instrumentation

Metrics are automatically recorded by:

1. **`RoleResolutionMiddleware`** - Records resolution attempts and role distribution
2. **`@require` decorator** - Records authorization checks and denials
3. **Retrieval functions** - Record filtering operations

## Audit Logging

### Denial Audit Structure

When an authorization denial occurs, a structured audit log entry is created:

```json
{
  "event": "rbac_denial",
  "capability": "WRITE_GRAPH",
  "user_id": "user-123",
  "roles": ["general"],
  "route": "/entities",
  "method": "POST",
  "timestamp": 1234567890.123,
  "metadata": {
    "is_authenticated": true,
    "ip": "192.168.1.1"
  }
}
```

### Log Levels

- **WARNING**: Used for all RBAC denials
- **INFO**: Used for successful authorizations (debug mode)
- **ERROR**: Used for resolution failures

### Log Format

```
RBAC_DENIAL capability=WRITE_GRAPH user=user-123 roles=general route=POST /entities
```

## Viewing Metrics

### Debug Endpoint

Metrics are exposed via the `/debug/metrics` endpoint (requires `VIEW_DEBUG` capability):

```bash
curl http://localhost:8000/debug/metrics
```

Response includes RBAC metrics:

```json
{
  "counters": {
    "rbac.resolutions{success=true}": 1250,
    "rbac.resolutions{success=false}": 12,
    "rbac.allowed": 980,
    "rbac.denied": 45,
    "rbac.audit.denials": 45,
    "retrieval.filtered_items": 234
  },
  "labeled_metrics": {
    "rbac.role_distribution": {
      "role=general": 500,
      "role=pro": 300,
      "role=analytics": 200,
      "role=scholars": 150,
      "role=ops": 100
    },
    "rbac.denied.by_capability": {
      "capability=WRITE_GRAPH": 20,
      "capability=WRITE_CONTRADICTIONS": 15,
      "capability=MANAGE_ROLES": 10
    }
  }
}
```

### Retrieving RBAC Metrics Only

```python
from core.metrics import get_rbac_metrics

metrics = get_rbac_metrics()
```

Returns:

```python
{
    "resolutions": {...},
    "authorization": {...},
    "role_distribution": {...},
    "retrieval": {...},
    "audit": {...}
}
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **High denial rate**: `rbac.denied / (rbac.allowed + rbac.denied) > 0.1`
   - May indicate misconfigured roles or attempted intrusion

2. **Resolution failures**: `rbac.resolutions{success=false}`
   - Could indicate authentication issues

3. **Audit denials spike**: Sudden increase in `rbac.audit.denials`
   - Potential security event

4. **Filtering rate**: `retrieval.filtered_items / retrieval.total_items`
   - High values may indicate overly restrictive visibility levels

### Example Alerts

```yaml
# Prometheus-style alert rules
alerts:
  - name: HighRBACDenialRate
    expr: rate(rbac_denied[5m]) / (rate(rbac_allowed[5m]) + rate(rbac_denied[5m])) > 0.15
    severity: warning
    description: "RBAC denial rate is {{ $value | humanizePercentage }}"
  
  - name: RBACResolutionFailures
    expr: rate(rbac_resolutions{success="false"}[5m]) > 5
    severity: critical
    description: "High rate of role resolution failures"
  
  - name: SuspiciousRBACActivity
    expr: increase(rbac_audit_denials[1m]) > 10
    severity: high
    description: "Unusual spike in access denials"
```

## Testing

Comprehensive tests are available in `tests/rbac/test_metrics.py`:

```bash
# Run all metrics tests
pytest tests/rbac/test_metrics.py -v

# Run specific test suites
pytest tests/rbac/test_metrics.py::TestAuthorizationMetrics -v
pytest tests/rbac/test_metrics.py::TestAuditLogging -v
```

### Test Coverage

- ✅ Resolution metrics (success/failure, by method)
- ✅ Authorization metrics (allowed/denied, by capability, by route)
- ✅ Role distribution tracking
- ✅ Retrieval filtering metrics
- ✅ Audit log generation and structure
- ✅ Middleware integration
- ✅ Guard decorator integration
- ✅ Metrics reset functionality

## Security Considerations

### Audit Trail Retention

Audit logs contain sensitive security information:
- User IDs
- Access patterns
- Denial reasons
- IP addresses (if included in metadata)

**Recommendations**:
- Retain audit logs for at least 90 days
- Export to secure long-term storage (SIEM, S3, etc.)
- Implement log rotation and archival
- Restrict access to audit logs (ops role only)

### GDPR Compliance

Audit logs may contain personal data:
- User IDs and emails
- IP addresses
- Access patterns

**Actions**:
- Document data retention policy
- Implement right-to-deletion for user data
- Anonymize logs after retention period
- Include audit logging in privacy policy

### Performance Impact

Metrics instrumentation is lightweight:
- Counter increments: ~1-2 microseconds
- Audit logging: ~50-100 microseconds
- No database writes (in-memory counters)

For high-throughput systems (>10k req/s):
- Consider sampling metrics (e.g., 10% of requests)
- Use async audit logging
- Buffer audit logs before writing to storage

## Integration Examples

### Adding Metrics to Custom Guards

```python
from core.metrics import record_rbac_check, audit_rbac_denial

def custom_check(user_roles, required_role):
    allowed = required_role in user_roles
    
    record_rbac_check(
        allowed=allowed,
        capability=f"CUSTOM_{required_role}",
        roles=user_roles,
        route="/custom/endpoint"
    )
    
    if not allowed:
        audit_rbac_denial(
            capability=f"CUSTOM_{required_role}",
            user_id=user_id,
            roles=user_roles,
            route="/custom/endpoint",
            method="POST"
        )
    
    return allowed
```

### Adding Filtering Metrics to Retrieval

```python
from core.metrics import record_retrieval_filtered

def filter_by_visibility(items, user_roles):
    user_level = get_max_role_level(user_roles)
    filtered = [item for item in items if item.visibility_level <= user_level]
    
    record_retrieval_filtered(
        filtered_count=len(items) - len(filtered),
        total_count=len(items),
        caller_roles=user_roles
    )
    
    return filtered
```

## Troubleshooting

### Metrics Not Appearing

1. **Check middleware registration**:
   ```python
   app.add_middleware(RoleResolutionMiddleware)
   ```

2. **Verify imports**:
   ```python
   from core.metrics import record_rbac_check
   ```

3. **Check debug endpoint**:
   ```bash
   curl http://localhost:8000/debug/metrics | jq '.counters | to_entries | map(select(.key | startswith("rbac")))'
   ```

### Audit Logs Not Appearing

1. **Check logger configuration**:
   ```python
   import logging
   logging.basicConfig(level=logging.WARNING)
   ```

2. **Verify audit logger**:
   ```python
   logger = logging.getLogger("rbac.audit")
   logger.setLevel(logging.WARNING)
   ```

3. **Check log handlers**:
   ```python
   # Add file handler for audit logs
   handler = logging.FileHandler("rbac_audit.log")
   audit_logger.addHandler(handler)
   ```

## Future Enhancements

Potential improvements:
- Export metrics to Prometheus/Grafana
- Real-time alerting on suspicious patterns
- ML-based anomaly detection
- Automatic role recommendation based on usage patterns
- Detailed user journey tracking across API calls

## Related Documentation

- [RBAC System Overview](./complete-rbac-system-final.md)
- [Write Path Guards](./write-path-guards.md)
- [Role Management API](./role-management-api.md)
- [Redaction Implementation](./redaction-implementation.md)
