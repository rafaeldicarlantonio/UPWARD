# Role Management API

## Overview

Admin-only API endpoints for managing user roles. These endpoints are protected by the `MANAGE_ROLES` capability, which is assigned to the `ops` role.

## Authentication

All role management endpoints require:
- **Capability**: `MANAGE_ROLES`
- **Roles**: `ops` (operations/administrator role)

Users without this capability will receive a `403 Forbidden` response.

## Endpoints

### POST /admin/roles/assign

Assign a role to a user.

**Request**:
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "role_key": "pro"
}
```

**Response** (200 OK):
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "role_key": "pro",
  "assigned": true,
  "message": "Role 'pro' assigned successfully",
  "audit_id": "audit-123"
}
```

**Idempotency**: Assigning the same role twice returns success but indicates already assigned:
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "role_key": "pro",
  "assigned": false,
  "message": "Role 'pro' already assigned",
  "audit_id": "audit-124"
}
```

### GET /admin/roles/{user_id}

Get all roles for a user.

**Response** (200 OK):
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "roles": ["general", "pro", "analytics"]
}
```

### POST /admin/roles/revoke

Revoke a role from a user.

**Request**:
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "role_key": "pro"
}
```

**Response** (200 OK):
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "role_key": "pro",
  "revoked": true,
  "message": "Role 'pro' revoked successfully",
  "audit_id": "audit-125"
}
```

**Protection**: Cannot revoke the `general` role:
```json
{
  "error": "Cannot revoke 'general' role - all users must have it"
}
```

### GET /admin/roles/audit/{user_id}

Get audit log for role changes.

**Query Parameters**:
- `limit` (optional): Maximum number of entries (default: 50)

**Response** (200 OK):
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "audit_entries": [
    {
      "id": "audit-123",
      "action": "role_assign",
      "role_key": "pro",
      "performed_by": "admin-456",
      "result": "assigned",
      "metadata": {
        "admin_roles": ["ops"],
        "admin_email": "admin@example.com",
        "request_ip": "192.168.1.1"
      },
      "created_at": "2025-10-30T12:34:56Z"
    }
  ],
  "count": 1
}
```

## Error Responses

### 403 Forbidden

Returned when user lacks `MANAGE_ROLES` capability:
```json
{
  "error": "forbidden",
  "capability": "MANAGE_ROLES",
  "message": "Capability 'MANAGE_ROLES' required",
  "user_roles": ["pro"],
  "missing": ["MANAGE_ROLES"]
}
```

### 400 Bad Request

Returned for invalid role keys:
```json
{
  "detail": [
    {
      "loc": ["body", "role_key"],
      "msg": "Invalid role key: invalid_role. Must be one of: general, pro, scholars, analytics, ops",
      "type": "value_error"
    }
  ]
}
```

### 500 Internal Server Error

Returned for database or system errors:
```json
{
  "detail": "Failed to assign role: Database connection failed"
}
```

## Role Keys

Valid role keys:
- `general` - Basic access (cannot be revoked)
- `pro` - Professional access
- `scholars` - Academic/research access
- `analytics` - Analytics with write permissions
- `ops` - Operations and administration

**Case Insensitive**: Role keys are normalized to lowercase (`PRO` → `pro`).

## Audit Logging

All role management operations are logged with:
- **Action**: `role_assign`, `role_revoke`, `role_assign_idempotent`, etc.
- **Target User**: User receiving the role change
- **Performed By**: Admin user ID
- **Result**: `assigned`, `revoked`, `already_assigned`, `not_assigned`
- **Metadata**: Admin roles, email, IP address, etc.
- **Timestamp**: When the action occurred

Audit logs are stored in the `role_audit_log` table.

## Database Schema

```sql
CREATE TABLE role_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,
    target_user_id TEXT NOT NULL,
    role_key TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    result TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

## Usage Examples

### cURL Examples

**Assign Role**:
```bash
curl -X POST https://api.example.com/admin/roles/assign \
  -H "Authorization: Bearer $OPS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "role_key": "pro"
  }'
```

**Get User Roles**:
```bash
curl https://api.example.com/admin/roles/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer $OPS_TOKEN"
```

**Revoke Role**:
```bash
curl -X POST https://api.example.com/admin/roles/revoke \
  -H "Authorization: Bearer $OPS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "role_key": "pro"
  }'
```

**Get Audit Log**:
```bash
curl https://api.example.com/admin/roles/audit/123e4567-e89b-12d3-a456-426614174000?limit=20 \
  -H "Authorization: Bearer $OPS_TOKEN"
```

### Python Client Examples

```python
import requests

# Setup
API_BASE = "https://api.example.com"
OPS_TOKEN = "your-ops-token"
HEADERS = {"Authorization": f"Bearer {OPS_TOKEN}"}

# Assign role
response = requests.post(
    f"{API_BASE}/admin/roles/assign",
    headers=HEADERS,
    json={
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "role_key": "pro"
    }
)
print(response.json())

# Get roles
response = requests.get(
    f"{API_BASE}/admin/roles/123e4567-e89b-12d3-a456-426614174000",
    headers=HEADERS
)
print(response.json())

# Revoke role
response = requests.post(
    f"{API_BASE}/admin/roles/revoke",
    headers=HEADERS,
    json={
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "role_key": "pro"
    }
)
print(response.json())
```

## Security Considerations

### Access Control
- Only users with `MANAGE_ROLES` capability (ops role) can access endpoints
- All operations are logged for audit trail
- Failed access attempts are logged

### Idempotency
- Role assignment is idempotent - assigning twice doesn't error
- Role revocation is idempotent - revoking non-existent role doesn't error
- Safe for retries and distributed systems

### Protection
- Cannot revoke `general` role - all users must have it
- Case-insensitive role handling prevents duplicates
- Invalid roles rejected at request validation layer

### Audit Trail
- Every operation logged with admin context
- Includes IP address, admin email, admin roles
- Immutable audit log for compliance

## Best Practices

### 1. Always Check Current Roles

Before assigning, check what roles a user already has:
```python
current = requests.get(f"{API_BASE}/admin/roles/{user_id}", headers=HEADERS)
roles = current.json()["roles"]
if "pro" not in roles:
    # Assign pro
```

### 2. Use Idempotency

Don't check before assigning - just assign and check the `assigned` flag:
```python
response = requests.post(f"{API_BASE}/admin/roles/assign", ...)
if response.json()["assigned"]:
    print("Newly assigned")
else:
    print("Already had role")
```

### 3. Review Audit Logs

Regularly review audit logs for compliance:
```python
audit = requests.get(f"{API_BASE}/admin/roles/audit/{user_id}?limit=100", ...)
for entry in audit.json()["audit_entries"]:
    print(f"{entry['created_at']}: {entry['action']} by {entry['performed_by']}")
```

### 4. Handle Errors Gracefully

```python
try:
    response = requests.post(f"{API_BASE}/admin/roles/assign", ...)
    response.raise_for_status()
except requests.HTTPError as e:
    if e.response.status_code == 403:
        print("Insufficient permissions")
    elif e.response.status_code == 400:
        print(f"Invalid request: {e.response.json()}")
    else:
        print(f"Error: {e}")
```

## Testing

See `tests/rbac/test_admin_roles.py` for comprehensive test examples.

**Test Coverage**:
- Role assignment (new, existing, deleted)
- Role revocation
- Idempotency guarantees
- Input validation
- Error handling
- Audit logging

## Deployment

### 1. Run Migrations

```bash
psql -d your_database -f migrations/110_role_audit_log.sql
```

### 2. Grant Ops Role

Assign ops role to admin users:
```sql
INSERT INTO user_roles (user_id, role_key, created_at, updated_at)
VALUES ('admin-user-id', 'ops', NOW(), NOW());
```

### 3. Verify Access

Test that ops users can access endpoints:
```bash
curl https://api.example.com/admin/roles/test-user-id \
  -H "Authorization: Bearer $OPS_TOKEN"
```

## Monitoring

### Metrics to Track
- Role assignment rate
- Role revocation rate
- Failed authorization attempts
- Audit log growth rate

### Alerts
- Multiple failed access attempts (potential attack)
- Unusual role assignment patterns
- Audit log write failures

## Troubleshooting

### Issue: 403 Forbidden

**Symptom**: `{"error": "forbidden", "capability": "MANAGE_ROLES"}`

**Cause**: User doesn't have ops role

**Solution**: Verify user's roles in database:
```sql
SELECT * FROM user_roles WHERE user_id = 'xxx';
```

### Issue: Role Not Appearing

**Symptom**: Role assigned successfully but not visible

**Cause**: Cache or stale JWT

**Solution**: 
- Check database directly
- Regenerate JWT token
- Clear role resolution cache

### Issue: Cannot Revoke General Role

**Symptom**: Error when trying to revoke `general`

**Cause**: Protection - all users must have general role

**Solution**: This is expected behavior. Assign other roles instead.

---

**Version**: 1.0  
**Last Updated**: 2025-10-30  
**See Also**:
- `docs/rbac-system.md` - Complete RBAC system
- `api/admin/roles.py` - Implementation
- `tests/rbac/test_admin_roles.py` - Tests
