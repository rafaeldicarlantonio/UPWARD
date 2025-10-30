# API Endpoint Guards

## Overview

API guards provide declarative capability-based authorization for FastAPI routes using Python decorators. Guards check if the user (from `request.state.ctx`) has the required capabilities and return 403 Forbidden if not.

## Quick Start

```python
from fastapi import FastAPI, Request
from core.rbac import CAP_WRITE_GRAPH, CAP_PROPOSE_HYPOTHESIS
from api.guards import require

app = FastAPI()

@app.post("/graph/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    """Only users with WRITE_GRAPH capability can access."""
    return {"status": "created"}

@app.post("/hypotheses")
@require(CAP_PROPOSE_HYPOTHESIS)
def propose_hypothesis(request: Request, data: dict):
    """Only users with PROPOSE_HYPOTHESIS capability can access."""
    return {"status": "submitted"}
```

## Decorators

### `@require(capability)`

Require a single capability for route access.

**Signature**:
```python
def require(capability: str) -> Callable
```

**Parameters**:
- `capability`: Capability constant (e.g., `CAP_WRITE_GRAPH`)

**Returns**:
- `403 Forbidden` if user lacks capability
- Allows request to proceed if user has capability

**Example**:
```python
from api.guards import require
from core.rbac import CAP_WRITE_GRAPH

@app.post("/graph/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    # Only accessible by users with WRITE_GRAPH capability
    # (analytics role)
    return {"status": "created"}
```

**403 Response Format**:
```json
{
  "detail": {
    "error": "forbidden",
    "capability": "WRITE_GRAPH",
    "message": "Capability 'WRITE_GRAPH' required"
  }
}
```

### `@require_any(*capabilities)`

Require at least ONE of the specified capabilities.

**Signature**:
```python
def require_any(*capabilities: str) -> Callable
```

**Parameters**:
- `*capabilities`: One or more capability constants

**Returns**:
- `403 Forbidden` if user lacks ALL capabilities
- Allows request if user has ANY capability

**Example**:
```python
from api.guards import require_any
from core.rbac import CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS

@app.post("/content")
@require_any(CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS)
def create_content(request: Request, data: dict):
    # Accessible by users with EITHER capability
    # (analytics role has both)
    return {"status": "created"}
```

**403 Response Format**:
```json
{
  "detail": {
    "error": "forbidden",
    "capabilities": ["WRITE_GRAPH", "WRITE_CONTRADICTIONS"],
    "message": "One of ('WRITE_GRAPH', 'WRITE_CONTRADICTIONS') capabilities required"
  }
}
```

### `@require_all(*capabilities)`

Require ALL of the specified capabilities.

**Signature**:
```python
def require_all(*capabilities: str) -> Callable
```

**Parameters**:
- `*capabilities`: One or more capability constants

**Returns**:
- `403 Forbidden` if user lacks ANY capability
- Allows request only if user has ALL capabilities

**Example**:
```python
from api.guards import require_all
from core.rbac import CAP_WRITE_GRAPH, CAP_MANAGE_ROLES

@app.post("/admin/action")
@require_all(CAP_WRITE_GRAPH, CAP_MANAGE_ROLES)
def admin_action(request: Request, data: dict):
    # Only accessible if user has BOTH capabilities
    # (currently no role has MANAGE_ROLES)
    return {"status": "completed"}
```

**403 Response Format**:
```json
{
  "detail": {
    "error": "forbidden",
    "capabilities": ["WRITE_GRAPH", "MANAGE_ROLES"],
    "missing": "MANAGE_ROLES",
    "message": "All of ('WRITE_GRAPH', 'MANAGE_ROLES') capabilities required"
  }
}
```

## Usage Patterns

### Basic Protection

```python
from fastapi import Request
from api.guards import require
from core.rbac import CAP_WRITE_GRAPH

@app.post("/graph/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    # Protected route - only analytics role can access
    return {"id": "entity-123", "status": "created"}
```

### Multiple Decorators (Stacking)

```python
from api.guards import require
from core.rbac import CAP_WRITE_GRAPH, CAP_PROPOSE_HYPOTHESIS

# This would require BOTH capabilities
@app.post("/complex-action")
@require(CAP_WRITE_GRAPH)
@require(CAP_PROPOSE_HYPOTHESIS)
def complex_action(request: Request):
    # User needs both WRITE_GRAPH and PROPOSE_HYPOTHESIS
    return {"status": "done"}
```

**Note**: For multiple capabilities, consider using `@require_all()` instead.

### Async Routes

Guards work with both sync and async routes:

```python
@app.get("/async-data")
@require(CAP_READ_LEDGER_FULL)
async def get_async_data(request: Request):
    # Async route with guard
    data = await fetch_data()
    return {"data": data}
```

### Combining with Other Decorators

```python
from fastapi import Depends
from api.guards import require
from core.rbac import CAP_WRITE_GRAPH

def validate_data(data: dict):
    # Custom validation
    if not data.get("name"):
        raise ValueError("Name required")
    return data

@app.post("/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(
    request: Request,
    data: dict = Depends(validate_data)
):
    # Guard runs before validation
    return {"status": "created"}
```

### Public Routes (No Guard)

Routes without guards are accessible to all users (including anonymous):

```python
@app.get("/public/data")
def public_data(request: Request):
    # No guard - accessible by everyone
    from api.middleware import get_current_user
    ctx = get_current_user(request)
    
    return {
        "data": "public",
        "is_authenticated": ctx.is_authenticated,
    }
```

## Integration with RBAC System

Guards integrate seamlessly with the RBAC capability system:

### Role → Capability → Guard

```
User Request
    ↓
Middleware resolves roles (e.g., ["analytics"])
    ↓
Guard checks: has_capability("analytics", CAP_WRITE_GRAPH)
    ↓
RBAC System: analytics has WRITE_GRAPH → True
    ↓
Allow request to proceed
```

### Complete Example

```python
from fastapi import FastAPI, Request
from core.rbac import (
    configure_resolver,
    CAP_WRITE_GRAPH,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_VIEW_DEBUG,
)
from api.middleware import RoleResolutionMiddleware
from api.guards import require

app = FastAPI()

# Configure authentication
configure_resolver(
    supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET"),
    api_key_to_user_map={
        "service-key": {
            "user_id": "service-1",
            "roles": ["analytics"],
        },
    },
)

# Add middleware
app.add_middleware(RoleResolutionMiddleware)

# Public route
@app.get("/")
def root():
    return {"message": "Welcome"}

# Protected routes
@app.post("/graph/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    return {"status": "created"}

@app.post("/hypotheses")
@require(CAP_PROPOSE_HYPOTHESIS)
def propose_hypothesis(request: Request, data: dict):
    return {"status": "submitted"}

@app.get("/debug/metrics")
@require(CAP_VIEW_DEBUG)
def debug_metrics(request: Request):
    return {"metrics": "..."}
```

## Role-Based Access Matrix

| Route | Required Capability | general | pro | scholars | analytics | ops |
|-------|-------------------|---------|-----|----------|-----------|-----|
| `/graph/entities` | `WRITE_GRAPH` | ✗ | ✗ | ✗ | ✓ | ✗ |
| `/hypotheses` | `PROPOSE_HYPOTHESIS` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `/debug/metrics` | `VIEW_DEBUG` | ✗ | ✗ | ✗ | ✗ | ✓ |
| `/content` | `WRITE_GRAPH` OR `WRITE_CONTRADICTIONS` | ✗ | ✗ | ✗ | ✓ | ✗ |
| `/admin/action` | `WRITE_GRAPH` AND `MANAGE_ROLES` | ✗ | ✗ | ✗ | ✗ | ✗ |

## Error Handling

### 403 Forbidden Response

When a user lacks the required capability, the guard returns:

```json
{
  "detail": {
    "error": "forbidden",
    "capability": "WRITE_GRAPH",
    "message": "Capability 'WRITE_GRAPH' required"
  }
}
```

### Custom Error Handler

You can add a custom error handler for 403 responses:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(403)
async def custom_403_handler(request: Request, exc):
    return JSONResponse(
        status_code=403,
        content={
            "error": "Access Denied",
            "message": "You don't have permission to access this resource",
            "details": exc.detail if hasattr(exc, 'detail') else None,
        }
    )
```

### Logging

Guards automatically log access denials:

```python
import logging

logger = logging.getLogger("api.guards")
logger.setLevel(logging.WARNING)

# Logs will include:
# WARNING: Access denied: user_id=user-123, roles=['pro'], required_capability=WRITE_GRAPH
```

## Testing

### Unit Tests

```python
from fastapi.testclient import TestClient

def test_guarded_route_with_capability():
    """Users with capability should access guarded routes."""
    response = client.post(
        "/graph/entities",
        headers={"X-API-KEY": "analytics-key"}
    )
    
    assert response.status_code == 200

def test_guarded_route_without_capability():
    """Users without capability should get 403."""
    response = client.post(
        "/graph/entities",
        headers={"X-API-KEY": "pro-key"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "forbidden"
```

### Integration Tests

```python
def test_complete_workflow():
    """Test guards in complete workflow."""
    # Anonymous user - denied
    response = client.post("/graph/entities")
    assert response.status_code == 403
    
    # User with wrong capability - denied
    response = client.post(
        "/graph/entities",
        headers={"X-API-KEY": "pro-key"}
    )
    assert response.status_code == 403
    
    # User with correct capability - allowed
    response = client.post(
        "/graph/entities",
        headers={"X-API-KEY": "analytics-key"}
    )
    assert response.status_code == 200
```

See `tests/rbac/test_guards.py` for comprehensive examples.

## Prerequisites

Guards require:

1. **Middleware configured**:
   ```python
   app.add_middleware(RoleResolutionMiddleware)
   ```

2. **Resolver configured**:
   ```python
   configure_resolver(
       supabase_jwt_secret="...",
       api_key_to_user_map={...},
   )
   ```

3. **Request parameter in route**:
   ```python
   def route(request: Request):  # Request required!
       ...
   ```

## Best Practices

### 1. Apply Guards to All Sensitive Routes

```python
# Good - protected
@app.post("/graph/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    ...

# Bad - unprotected sensitive route
@app.post("/graph/entities")
def create_entity(request: Request, data: dict):
    # Anyone can create entities!
    ...
```

### 2. Use Most Specific Capability

```python
# Good - specific capability
@app.post("/graph/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    ...

# Bad - overly permissive
@app.post("/graph/entities")
@require(CAP_READ_PUBLIC)
def create_entity(request: Request, data: dict):
    # READ_PUBLIC doesn't make sense for writes
    ...
```

### 3. Document Required Capabilities

```python
@app.post("/graph/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    """
    Create a new graph entity.
    
    Requires: WRITE_GRAPH capability (analytics role)
    """
    ...
```

### 4. Test Both Success and Failure Cases

```python
def test_entity_creation():
    # Test success
    response = client.post("/entities", headers={"X-API-KEY": "analytics-key"})
    assert response.status_code == 200
    
    # Test failure
    response = client.post("/entities", headers={"X-API-KEY": "pro-key"})
    assert response.status_code == 403
```

### 5. Use require_any for Flexible Access

```python
# Allow both writers and admins
@app.post("/content")
@require_any(CAP_WRITE_GRAPH, CAP_MANAGE_ROLES)
def create_content(request: Request, data: dict):
    ...
```

## Common Pitfalls

### Missing Request Parameter

```python
# ✗ BAD - Missing request parameter
@app.post("/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(data: dict):
    ...

# ✓ GOOD - Include request parameter
@app.post("/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    ...
```

### Middleware Not Configured

```python
# ✗ BAD - Middleware not added
app = FastAPI()

@app.post("/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    ...

# ✓ GOOD - Middleware configured
app = FastAPI()
app.add_middleware(RoleResolutionMiddleware)

@app.post("/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    ...
```

### Wrong Decorator Order

```python
# ✗ BAD - Guard after route decorator won't work
@require(CAP_WRITE_GRAPH)
@app.post("/entities")
def create_entity(request: Request, data: dict):
    ...

# ✓ GOOD - Route decorator first, guard second
@app.post("/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    ...
```

## Troubleshooting

### Issue: 500 Error Instead of 403

**Cause**: Middleware not configured or Request parameter missing

**Solution**:
```python
# Ensure middleware is added
app.add_middleware(RoleResolutionMiddleware)

# Ensure route has Request parameter
def route(request: Request):
    ...
```

### Issue: Guard Not Working

**Cause**: Decorator order incorrect

**Solution**:
```python
# Correct order
@app.post("/route")
@require(CAP_WRITE_GRAPH)
def route(request: Request):
    ...
```

### Issue: All Requests Get 403

**Cause**: Capability constant misspelled or wrong capability used

**Solution**:
```python
# Use correct capability constants
from core.rbac import CAP_WRITE_GRAPH  # Import from module

@require(CAP_WRITE_GRAPH)  # Use constant, not string
```

## Performance

Guards add minimal overhead:

- **Capability check**: ~0.1ms (dictionary lookup)
- **User context access**: ~0.01ms (already cached by middleware)
- **Total overhead**: ~0.1ms per guarded route

## Migration from Manual Checks

### Before (Manual)

```python
from api.middleware import get_current_user
from core.rbac import has_capability, CAP_WRITE_GRAPH

@app.post("/entities")
def create_entity(request: Request, data: dict):
    ctx = get_current_user(request)
    
    if not any(has_capability(r, CAP_WRITE_GRAPH) for r in ctx.roles):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Business logic...
    return {"status": "created"}
```

### After (With Guard)

```python
from api.guards import require
from core.rbac import CAP_WRITE_GRAPH

@app.post("/entities")
@require(CAP_WRITE_GRAPH)
def create_entity(request: Request, data: dict):
    # Business logic...
    return {"status": "created"}
```

**Benefits**:
- Cleaner code
- Consistent error responses
- Easier to maintain
- Self-documenting

---

**Version**: 1.0  
**Last Updated**: 2025-10-30  
**See Also**:
- `docs/rbac-system.md` - RBAC capability system
- `docs/role-resolution-middleware.md` - Role resolution
- `api/guards.py` - Guard implementation
- `tests/rbac/test_guards.py` - Guard tests
