# Role Resolution Middleware

## Overview

The role resolution middleware automatically extracts user identity and roles from incoming requests, supporting multiple authentication methods:

1. **JWT Tokens** (Supabase format)
2. **API Keys** (header-based)
3. **Anonymous Fallback** (default to 'general' role)

The middleware attaches user context to `request.state.ctx` for use in route handlers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Incoming HTTP Request                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │ RoleResolutionMiddleware      │
          └──────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │     Extract Headers          │
          │  • Authorization (JWT)       │
          │  • X-API-KEY (API key)       │
          └──────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │      RoleResolver            │
          │  1. Try JWT first            │
          │  2. Try API key second       │
          │  3. Fall back to anonymous   │
          └──────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │   Attach to request.state    │
          │  • user_id                   │
          │  • email                     │
          │  • roles                     │
          │  • auth_method               │
          │  • is_authenticated          │
          └──────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │     Route Handler            │
          │  (can access user context)   │
          └──────────────────────────────┘
```

## Quick Start

### 1. Configure Resolver

At application startup, configure the global resolver with your secrets:

```python
from core.rbac import configure_resolver

# Configure at app startup
configure_resolver(
    supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET"),
    api_key_to_user_map={
        "your-api-key-123": {
            "user_id": "service-account-1",
            "email": "service@example.com",
            "roles": ["analytics", "pro"],
        },
        "ops-key-456": {
            "user_id": "ops-user",
            "email": "ops@example.com",
            "roles": ["ops"],
        },
    },
    default_anonymous_roles=['general'],
)
```

### 2. Add Middleware to FastAPI App

```python
from fastapi import FastAPI
from api.middleware import RoleResolutionMiddleware

app = FastAPI()

# Add middleware
app.add_middleware(RoleResolutionMiddleware)

# Now all routes have access to user context
```

### 3. Use in Route Handlers

```python
from fastapi import Request
from api.middleware import get_current_user, require_authenticated, get_user_id

@app.get("/profile")
def get_profile(request: Request):
    """Public endpoint - works for authenticated and anonymous users."""
    ctx = get_current_user(request)
    
    if ctx.is_authenticated:
        return {"user_id": ctx.user_id, "email": ctx.email, "roles": ctx.roles}
    else:
        return {"message": "Anonymous user", "roles": ctx.roles}

@app.post("/create-entity")
def create_entity(request: Request, data: dict):
    """Protected endpoint - requires authentication."""
    ctx = require_authenticated(request)  # Raises PermissionError if not authenticated
    
    # Check specific capability
    from core.rbac import has_capability, CAP_WRITE_GRAPH
    if not has_capability(ctx.roles[0], CAP_WRITE_GRAPH):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Process entity creation...
    return {"user_id": ctx.user_id, "status": "created"}

@app.get("/my-data")
def get_my_data(request: Request):
    """Get current user ID."""
    user_id = get_user_id(request)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Fetch user's data...
    return {"user_id": user_id, "data": [...]}
```

## Authentication Methods

### Method 1: JWT Token (Supabase)

**Priority**: Highest (tried first)

**Header Format**:
```
Authorization: Bearer <jwt-token>
```

**JWT Payload Structure**:
```json
{
  "sub": "user-123",
  "email": "user@example.com",
  "roles": ["pro", "scholars"],
  "iat": 1234567890,
  "exp": 1234571490
}
```

**Role Extraction** (checked in order):
1. `payload['roles']` (direct)
2. `payload['app_metadata']['roles']`
3. `payload['user_metadata']['roles']`
4. Default to `['pro']` for authenticated users

**Example**:
```python
import jwt
from datetime import datetime, timedelta

# Create JWT token
payload = {
    "sub": "user-123",
    "email": "user@example.com",
    "roles": ["analytics"],
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=1),
}
token = jwt.encode(payload, supabase_jwt_secret, algorithm="HS256")

# Use in request
response = requests.get(
    "http://api.example.com/data",
    headers={"Authorization": f"Bearer {token}"}
)
```

**Resolved User**:
- `user_id`: From `sub` claim
- `email`: From `email` claim
- `roles`: From `roles` claim (or default 'pro')
- `auth_method`: `'jwt'`
- `is_authenticated`: `True`

### Method 2: API Key

**Priority**: Medium (tried if JWT fails)

**Header Format**:
```
X-API-KEY: your-api-key-123
```

or

```
X-Api-Key: your-api-key-123
```

(Case-insensitive)

**Configuration**:
```python
configure_resolver(
    api_key_to_user_map={
        "your-api-key-123": {
            "user_id": "api-user-1",
            "email": "apiuser@example.com",
            "roles": ["analytics", "pro"],
        },
    }
)
```

**Example**:
```bash
curl -H "X-API-KEY: your-api-key-123" \
  http://api.example.com/data
```

**Resolved User**:
- `user_id`: From configuration
- `email`: From configuration
- `roles`: From configuration (default 'pro' if not specified)
- `auth_method`: `'api_key'`
- `is_authenticated`: `True`

### Method 3: Anonymous Fallback

**Priority**: Lowest (used if all methods fail)

**Conditions**:
- No Authorization header
- No X-API-KEY header
- Invalid JWT token
- Unknown API key
- Any authentication error

**Resolved User**:
- `user_id`: `None`
- `email`: `None`
- `roles`: `['general']` (configurable)
- `auth_method`: `'anonymous'`
- `is_authenticated`: `False`

**Example**:
```bash
# Request without any auth headers
curl http://api.example.com/public-data
```

## Request Context API

### `RequestContext` Class

Attached to `request.state.ctx` by the middleware:

```python
class RequestContext:
    user_id: Optional[str]      # User ID or None
    email: Optional[str]         # Email or None
    roles: List[str]             # List of role names
    auth_method: str             # 'jwt', 'api_key', or 'anonymous'
    is_authenticated: bool       # True if not anonymous
    metadata: dict               # Additional auth metadata
```

### Helper Functions

#### `get_current_user(request: Request) -> RequestContext`

Get the current user context from the request.

```python
from api.middleware import get_current_user

@app.get("/whoami")
def whoami(request: Request):
    ctx = get_current_user(request)
    return {
        "user_id": ctx.user_id,
        "roles": ctx.roles,
        "auth_method": ctx.auth_method,
    }
```

#### `require_authenticated(request: Request) -> RequestContext`

Require that the user is authenticated (not anonymous).

```python
from api.middleware import require_authenticated

@app.post("/protected")
def protected_endpoint(request: Request):
    ctx = require_authenticated(request)  # Raises PermissionError if anonymous
    
    # User is authenticated
    return {"user_id": ctx.user_id}
```

#### `get_user_id(request: Request) -> Optional[str]`

Get just the user ID.

```python
from api.middleware import get_user_id

@app.get("/my-profile")
def my_profile(request: Request):
    user_id = get_user_id(request)
    
    if not user_id:
        return {"message": "Not logged in"}
    
    return {"user_id": user_id}
```

#### `get_user_roles(request: Request) -> List[str]`

Get just the user roles.

```python
from api.middleware import get_user_roles

@app.get("/permissions")
def permissions(request: Request):
    roles = get_user_roles(request)
    return {"roles": roles}
```

## Integration with RBAC

The middleware integrates seamlessly with the RBAC capability system:

```python
from fastapi import Request, HTTPException
from api.middleware import get_current_user
from core.rbac import has_capability, CAP_WRITE_GRAPH, CAP_PROPOSE_HYPOTHESIS

@app.post("/graph/entities")
def create_graph_entity(request: Request, data: dict):
    """Create entity - requires WRITE_GRAPH capability."""
    ctx = get_current_user(request)
    
    # Check if any of the user's roles have the required capability
    if not any(has_capability(role, CAP_WRITE_GRAPH) for role in ctx.roles):
        raise HTTPException(
            status_code=403,
            detail=f"None of your roles ({ctx.roles}) have WRITE_GRAPH capability"
        )
    
    # Process entity creation
    return {"status": "created"}

@app.post("/hypotheses")
def propose_hypothesis(request: Request, data: dict):
    """Propose hypothesis - requires PROPOSE_HYPOTHESIS capability."""
    ctx = get_current_user(request)
    
    # Check capability
    can_propose = any(
        has_capability(role, CAP_PROPOSE_HYPOTHESIS) 
        for role in ctx.roles
    )
    
    if not can_propose:
        raise HTTPException(
            status_code=403,
            detail="PROPOSE_HYPOTHESIS capability required"
        )
    
    # Process hypothesis
    return {"status": "submitted"}
```

## Caching

The resolver implements request-level caching to avoid redundant JWT decoding or API key lookups:

```python
# First call - decodes JWT
user1 = resolver.resolve_from_request(authorization_header=auth_header)

# Second call with same headers - returns cached result
user2 = resolver.resolve_from_request(authorization_header=auth_header)

# user1 is user2  -> True (same object)
```

The cache is cleared automatically between requests.

## Error Handling

The middleware handles errors gracefully:

1. **JWT Decoding Errors**: Fall back to API key or anonymous
2. **Expired JWT**: Fall back to API key or anonymous
3. **Invalid API Key**: Fall back to anonymous
4. **Any Exception**: Create anonymous user with error in metadata

Example error metadata:

```python
ctx = get_current_user(request)
if 'error' in ctx.metadata:
    logger.warning(f"Auth error: {ctx.metadata['error']}")
```

## Security Considerations

### JWT Verification

- **Algorithm**: HS256 (configurable)
- **Expiration**: Enforced (`verify_exp=True`)
- **Required Claims**: `sub` (user ID)
- **Secret**: Must match Supabase project secret

### API Key Security

- **Storage**: Configure securely (environment variables, secrets manager)
- **Prefix Logging**: Only first 8 characters logged
- **Unknown Keys**: Rejected (no fallback that leaks key validity)

### Anonymous Fallback

- **Default Roles**: `['general']` (minimal permissions)
- **No User ID**: Prevents access to user-specific data
- **Explicit Checks**: Use `require_authenticated()` for protected endpoints

## Configuration Examples

### Development (Local)

```python
# config_dev.py
import os

configure_resolver(
    supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", "dev-secret-123"),
    api_key_to_user_map={
        "dev-key-123": {
            "user_id": "dev-user",
            "email": "dev@example.com",
            "roles": ["analytics", "ops"],
        },
    },
    default_anonymous_roles=['general'],
)
```

### Production

```python
# config_prod.py
import os
import json

# Load from environment
SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]

# Load API keys from secure storage
API_KEYS = json.loads(os.environ["API_KEY_CONFIG"])

configure_resolver(
    supabase_jwt_secret=SUPABASE_JWT_SECRET,
    api_key_to_user_map=API_KEYS,
    default_anonymous_roles=['general'],
)
```

### Multiple Environments

```python
# app.py
from core.rbac import configure_resolver
import os

def setup_auth():
    """Configure authentication based on environment."""
    env = os.getenv("ENV", "development")
    
    if env == "production":
        configure_resolver(
            supabase_jwt_secret=os.environ["SUPABASE_JWT_SECRET"],
            api_key_to_user_map=load_api_keys_from_vault(),
            default_anonymous_roles=['general'],
        )
    elif env == "staging":
        configure_resolver(
            supabase_jwt_secret=os.environ["SUPABASE_JWT_SECRET_STAGING"],
            api_key_to_user_map=load_api_keys_from_file("staging_keys.json"),
            default_anonymous_roles=['general'],
        )
    else:  # development
        configure_resolver(
            supabase_jwt_secret="dev-secret-not-secure",
            api_key_to_user_map={
                "dev-key": {"user_id": "dev", "roles": ["analytics"]},
            },
            default_anonymous_roles=['general'],
        )

@app.on_event("startup")
async def startup_event():
    setup_auth()
```

## Testing

### Unit Tests

```python
from core.rbac import RoleResolver
import jwt
from datetime import datetime, timedelta

def test_jwt_authentication():
    """Test JWT authentication."""
    secret = "test-secret"
    resolver = RoleResolver(supabase_jwt_secret=secret)
    
    # Create token
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "roles": ["pro"],
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    # Resolve user
    user = resolver.resolve_from_request(
        authorization_header=f"Bearer {token}"
    )
    
    assert user.user_id == "user-123"
    assert user.auth_method == "jwt"
    assert "pro" in user.roles
```

### Integration Tests

```python
from fastapi.testclient import TestClient

def test_middleware_authentication(client: TestClient, valid_jwt_token: str):
    """Test middleware resolves authentication."""
    response = client.get(
        "/test",
        headers={"Authorization": f"Bearer {valid_jwt_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_authenticated"] is True
    assert data["user_id"] == "user-123"
```

See `tests/rbac/test_resolver.py` for comprehensive test examples.

## Troubleshooting

### Issue: JWT Always Falls Back to Anonymous

**Symptoms**: Valid JWT tokens are not recognized

**Causes**:
1. Wrong JWT secret configured
2. JWT algorithm mismatch
3. Token expired
4. Missing "Bearer " prefix

**Solution**:
```python
# Check JWT secret
print(f"Configured secret: {os.getenv('SUPABASE_JWT_SECRET')[:10]}...")

# Decode JWT manually to inspect
import jwt
try:
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    print(f"Payload: {payload}")
except jwt.ExpiredSignatureError:
    print("Token expired!")
except jwt.InvalidTokenError as e:
    print(f"Invalid token: {e}")
```

### Issue: API Key Not Recognized

**Symptoms**: Valid API key falls back to anonymous

**Causes**:
1. API key not in configuration
2. Case sensitivity issue (use X-API-KEY or X-Api-Key)
3. Whitespace in header value

**Solution**:
```python
# Check API key configuration
from core.rbac import get_resolver
resolver = get_resolver()
print(f"Configured API keys: {list(resolver.api_key_to_user_map.keys())}")

# Test API key lookup
user = resolver.resolve_from_request(api_key_header="your-key-123")
print(f"Resolved: {user.auth_method}, {user.roles}")
```

### Issue: request.state.ctx Not Available

**Symptoms**: `AttributeError: 'State' object has no attribute 'ctx'`

**Cause**: Middleware not configured

**Solution**:
```python
from api.middleware import RoleResolutionMiddleware

app = FastAPI()
app.add_middleware(RoleResolutionMiddleware)  # Add this!
```

## Migration Guide

### From Manual Auth Checks

**Before**:
```python
@app.get("/data")
def get_data(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401)
    
    # Manual JWT decoding
    token = authorization.replace("Bearer ", "")
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    user_id = payload["sub"]
    
    # Fetch data...
```

**After**:
```python
@app.get("/data")
def get_data(request: Request):
    ctx = require_authenticated(request)  # Automatic!
    user_id = ctx.user_id
    
    # Fetch data...
```

### From Custom Role Extraction

**Before**:
```python
def extract_roles(request):
    # Custom logic...
    if api_key := request.headers.get("X-API-KEY"):
        return lookup_api_key_roles(api_key)
    elif auth := request.headers.get("Authorization"):
        token = parse_jwt(auth)
        return token.get("roles", ["general"])
    return ["general"]
```

**After**:
```python
from api.middleware import get_user_roles

@app.get("/endpoint")
def endpoint(request: Request):
    roles = get_user_roles(request)  # Automatic!
```

---

**Version**: 1.0  
**Last Updated**: 2025-10-30  
**See Also**: 
- `docs/rbac-system.md` - RBAC capability system
- `core/rbac/resolve.py` - Role resolver implementation
- `api/middleware/roles.py` - Middleware implementation
