# External Comparison Role Gating

Role-based access control for external source comparison with feature flag control.

## Overview

External source comparison is a powerful feature that must be carefully controlled to manage costs, rate limits, and data quality. Access is gated by:

1. **Feature Flag**: `external_compare` must be enabled
2. **Role Authorization**: User must have an allowed role from policy

## Feature Flag

**Flag Name**: `external_compare`  
**Default**: `false` (disabled)  
**Location**: `feature_flags.py`

### Enabling the Feature

```python
from feature_flags import set_feature_flag

# Enable external comparison
set_feature_flag("external_compare", True)

# Disable external comparison
set_feature_flag("external_compare", False)
```

### Checking Flag Status

```python
from feature_flags import get_feature_flag

if get_feature_flag("external_compare"):
    print("External comparison is enabled")
```

## Role Authorization

### Allowed Roles Configuration

Roles are configured in `config/compare_policy.yaml`:

```yaml
allowed_roles_for_external:
  - pro
  - scholars
  - analytics
```

**Default Allowed Roles**:
- `pro` - Pro tier users
- `scholars` - Scholars/academic users  
- `analytics` - Analytics team users

**Denied by Default**:
- `general` - Free tier users
- `ops` - Operations team (read-only access)

### Checking User Access

```python
from core.policy import can_use_external_compare

# Check if user can access external comparison
user_roles = ["pro", "general"]
if can_use_external_compare(user_roles):
    # User has access
    result = perform_external_comparison(query)
else:
    # User denied access
    return {"error": "External comparison not available for your account"}
```

## Access Control Logic

The `can_use_external_compare(user_roles)` function implements two-level gating:

### Level 1: Feature Flag Check

```python
if not feature_flag_enabled:
    return False  # Deny all users
```

### Level 2: Role Check

```python
if any(role in allowed_roles for role in user_roles):
    return True  # Allow user
else:
    return False  # Deny user
```

## Access Matrix

| Role | Flag OFF | Flag ON | Notes |
|------|----------|---------|-------|
| `general` | ❌ Denied | ❌ Denied | Never allowed |
| `pro` | ❌ Denied | ✅ Allowed | Allowed when flag on |
| `scholars` | ❌ Denied | ✅ Allowed | Allowed when flag on |
| `analytics` | ❌ Denied | ✅ Allowed | Allowed when flag on |
| `ops` | ❌ Denied | ❌ Denied | Not in default policy |

## Usage Examples

### Basic Check

```python
from core.policy import can_use_external_compare

def fetch_external_data(user_roles):
    # Check access
    if not can_use_external_compare(user_roles):
        return {
            "error": "External comparison not available",
            "upgrade_url": "/upgrade"
        }
    
    # Proceed with external fetch
    return fetch_from_external_sources()
```

### API Endpoint Integration

```python
from fastapi import Request, HTTPException
from api.middleware.roles import get_user_roles
from core.policy import can_use_external_compare

@app.post("/compare/external")
async def compare_with_external(request: Request, query: str):
    # Get user roles from request context
    user_roles = get_user_roles(request)
    
    # Check access
    if not can_use_external_compare(user_roles):
        raise HTTPException(
            status_code=403,
            detail="External comparison not available for your account"
        )
    
    # Perform comparison
    results = await external_compare_service(query)
    return results
```

### Conditional Feature Display

```python
from core.policy import can_use_external_compare

def get_available_features(user_roles):
    features = {
        "internal_search": True,
        "memory_graph": True,
        "external_comparison": can_use_external_compare(user_roles)
    }
    return features
```

## Configuration Management

### Policy Updates

To change which roles can access external comparison:

```yaml
# config/compare_policy.yaml

# Option 1: Restrict to analytics only
allowed_roles_for_external:
  - analytics

# Option 2: Allow all paid tiers
allowed_roles_for_external:
  - pro
  - scholars
  - analytics

# Option 3: Allow everyone (not recommended)
allowed_roles_for_external:
  - general
  - pro
  - scholars
  - analytics
  - ops
```

After updating the file, reload the configuration:

```python
from core.config_loader import get_loader

loader = get_loader()
loader.reload()
```

### Gradual Rollout

Example phased rollout strategy:

```python
# Phase 1: Enable for analytics only (testing)
# policy: allowed_roles_for_external = ["analytics"]
set_feature_flag("external_compare", True)

# Monitor for 1 week...

# Phase 2: Add scholars
# policy: allowed_roles_for_external = ["analytics", "scholars"]
loader.reload()

# Monitor for 1 week...

# Phase 3: Add pro users
# policy: allowed_roles_for_external = ["analytics", "scholars", "pro"]
loader.reload()

# Monitor for 2 weeks...

# Phase 4: General availability (if desired)
# policy: allowed_roles_for_external = ["general", "pro", "scholars", "analytics"]
loader.reload()
```

## Monitoring and Metrics

### Access Denial Tracking

```python
from core.metrics import record_rbac_check, audit_rbac_denial

def check_external_access(user_roles):
    allowed = can_use_external_compare(user_roles)
    
    # Record metric
    record_rbac_check(
        allowed=allowed,
        capability="external_compare",
        roles=user_roles,
        route="/compare/external"
    )
    
    # Audit denials
    if not allowed:
        audit_rbac_denial(
            capability="external_compare",
            user_id=user_id,
            roles=user_roles,
            route="/compare/external",
            method="POST"
        )
    
    return allowed
```

### Key Metrics

- `rbac.denied.by_capability{capability=external_compare}` - Denial count
- `rbac.allowed.by_capability{capability=external_compare}` - Access count
- `external_compare.requests_by_role{role=*}` - Usage by role

## Security Considerations

### Rate Limiting

External comparison should be rate limited per role:

```python
from core.config_loader import get_loader

policy = get_loader().get_compare_policy()

# Apply rate limits
rate_limit = policy.rate_limit_per_domain_per_min
timeout = policy.timeout_ms_per_request
max_sources = policy.max_external_sources_per_run
```

### Cost Control

To prevent excessive API costs:

1. **Feature flag** provides kill switch
2. **Role gating** limits to paid tiers
3. **Rate limiting** per user/domain
4. **Timeout** prevents hanging requests
5. **Max sources** caps parallel requests

### Data Privacy

```yaml
# Redact sensitive patterns from external responses
redact_patterns:
  - "Authorization:\\s+\\S+"
  - "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*"
```

## Testing

Comprehensive tests in `tests/external/test_role_gate.py`:

```bash
# Run all role gating tests
pytest tests/external/test_role_gate.py -v

# Test specific scenarios
pytest tests/external/test_role_gate.py::TestAcceptanceCriteria -v
```

### Test Coverage

- ✅ Feature flag on/off
- ✅ All role permutations
- ✅ Multiple roles per user
- ✅ Policy configuration changes
- ✅ Missing/malformed policies
- ✅ Error handling

## Troubleshooting

### Users Can't Access External Comparison

1. **Check feature flag**:
```python
from feature_flags import get_feature_flag
print(f"Flag enabled: {get_feature_flag('external_compare')}")
```

2. **Check user roles**:
```python
from api.middleware.roles import get_user_roles
print(f"User roles: {get_user_roles(request)}")
```

3. **Check policy**:
```python
from core.config_loader import get_loader
policy = get_loader().get_compare_policy()
print(f"Allowed roles: {policy.allowed_roles_for_external}")
```

4. **Check access**:
```python
from core.policy import can_use_external_compare
print(f"Access granted: {can_use_external_compare(user_roles)}")
```

### Feature Flag Not Persisting

The flag is stored in the database. Ensure:
- Database connection is working
- `feature_flags` table exists
- Proper write permissions

### Policy Changes Not Taking Effect

```python
# Force reload configuration
from core.config_loader import get_loader
loader = get_loader(force_reload=True)
```

## Related Documentation

- [External Sources Configuration](./external-sources-config.md)
- [RBAC System](./rbac-system.md)
- [Feature Flags](./feature-flags.md)
- [Compare Policy](./compare-policy.md)
