# RBAC (Role-Based Access Control) System

## Overview

The RBAC system provides fine-grained authorization control for the application. It defines roles, capabilities, and the mapping between them to ensure users can only perform actions they're authorized for.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        RBAC System                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐         ┌──────────────────────┐        │
│  │    Roles     │────────▶│    Capabilities      │        │
│  │              │         │                      │        │
│  │  • general   │         │  • READ_PUBLIC       │        │
│  │  • pro       │         │  • READ_LEDGER_FULL  │        │
│  │  • scholars  │         │  • PROPOSE_HYPOTHESIS│        │
│  │  • analytics │         │  • PROPOSE_AURA      │        │
│  │  • ops       │         │  • WRITE_GRAPH       │        │
│  └──────────────┘         │  • WRITE_CONTRADICTIONS       │
│                          │  • MANAGE_ROLES      │        │
│                          │  • VIEW_DEBUG        │        │
│                          └──────────────────────┘        │
│                                                             │
│  ┌──────────────────────────────────────────────┐         │
│  │      Authorization Functions                 │         │
│  │                                              │         │
│  │  • has_capability(role, capability)         │         │
│  │  • get_role_capabilities(role)              │         │
│  │  • validate_role(role)                      │         │
│  │  • has_any_capability(role, caps)           │         │
│  │  • has_all_capabilities(role, caps)         │         │
│  │  • get_missing_capabilities(role, caps)     │         │
│  └──────────────────────────────────────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Roles

### Role Definitions

| Role | Description | Use Case |
|------|-------------|----------|
| **general** | Basic role with minimal permissions | Public users, read-only access |
| **pro** | Professional role with full read and proposal capabilities | Power users who can suggest but not modify |
| **scholars** | Academic role, same as Pro but explicitly no writes | Researchers in suggest-only mode |
| **analytics** | Analytics role with read, propose, and write capabilities | Data scientists who can modify the graph |
| **ops** | Operations role with read and debug capabilities | Site operators and monitoring |

### Role Hierarchy

```
Permissions by Level:
┌──────────────────────────────────────────────────────────────┐
│ GENERAL (Read-Only)                                          │
│   └─ READ_PUBLIC                                             │
├──────────────────────────────────────────────────────────────┤
│ PRO / SCHOLARS (Read + Propose)                              │
│   ├─ READ_PUBLIC                                             │
│   ├─ READ_LEDGER_FULL                                        │
│   ├─ PROPOSE_HYPOTHESIS                                      │
│   └─ PROPOSE_AURA                                            │
├──────────────────────────────────────────────────────────────┤
│ ANALYTICS (Read + Propose + Write)                           │
│   ├─ READ_PUBLIC                                             │
│   ├─ READ_LEDGER_FULL                                        │
│   ├─ PROPOSE_HYPOTHESIS                                      │
│   ├─ PROPOSE_AURA                                            │
│   ├─ WRITE_GRAPH                                             │
│   └─ WRITE_CONTRADICTIONS                                    │
├──────────────────────────────────────────────────────────────┤
│ OPS (Read + Debug)                                           │
│   ├─ READ_PUBLIC                                             │
│   ├─ READ_LEDGER_FULL                                        │
│   └─ VIEW_DEBUG                                              │
└──────────────────────────────────────────────────────────────┘
```

## Capabilities

### Capability Definitions

| Capability | Description | Granted To |
|------------|-------------|------------|
| **READ_PUBLIC** | Read publicly available content and memories | All roles |
| **READ_LEDGER_FULL** | Read full ledger data including internal metadata | pro, scholars, analytics, ops |
| **PROPOSE_HYPOTHESIS** | Propose new hypotheses for system consideration | pro, scholars, analytics |
| **PROPOSE_AURA** | Propose new aura entries | pro, scholars, analytics |
| **WRITE_GRAPH** | Write to the knowledge graph (entities, edges) | analytics |
| **WRITE_CONTRADICTIONS** | Write contradiction data to memories | analytics |
| **MANAGE_ROLES** | Manage user roles and permissions | (reserved, not currently granted) |
| **VIEW_DEBUG** | Access debug endpoints and metrics | ops |

### Capability Matrix

Complete role-to-capability mapping:

```
                          │ general │ pro │ scholars │ analytics │ ops │
──────────────────────────┼─────────┼─────┼──────────┼───────────┼─────┤
READ_PUBLIC               │    ✓    │  ✓  │    ✓     │     ✓     │  ✓  │
READ_LEDGER_FULL          │    ✗    │  ✓  │    ✓     │     ✓     │  ✓  │
PROPOSE_HYPOTHESIS        │    ✗    │  ✓  │    ✓     │     ✓     │  ✗  │
PROPOSE_AURA              │    ✗    │  ✓  │    ✓     │     ✓     │  ✗  │
WRITE_GRAPH               │    ✗    │  ✗  │    ✗     │     ✓     │  ✗  │
WRITE_CONTRADICTIONS      │    ✗    │  ✗  │    ✗     │     ✓     │  ✗  │
MANAGE_ROLES              │    ✗    │  ✗  │    ✗     │     ✗     │  ✗  │
VIEW_DEBUG                │    ✗    │  ✗  │    ✗     │     ✗     │  ✓  │
```

## API Reference

### Core Functions

#### `has_capability(role: str, capability: str) -> bool`

Check if a role has a specific capability.

**Parameters**:
- `role`: Role name (case-insensitive)
- `capability`: Capability constant

**Returns**: `True` if the role has the capability, `False` otherwise

**Examples**:
```python
from core.rbac import has_capability, CAP_READ_PUBLIC, CAP_WRITE_GRAPH

# Check basic permissions
has_capability("general", CAP_READ_PUBLIC)  # True
has_capability("general", CAP_WRITE_GRAPH)  # False

# Check proposal capabilities
has_capability("pro", CAP_PROPOSE_HYPOTHESIS)  # True
has_capability("scholars", CAP_PROPOSE_AURA)   # True

# Check write capabilities
has_capability("analytics", CAP_WRITE_GRAPH)  # True
has_capability("pro", CAP_WRITE_GRAPH)        # False

# Check debug access
has_capability("ops", CAP_VIEW_DEBUG)  # True
```

#### `get_role_capabilities(role: str) -> Set[str]`

Get all capabilities for a role.

**Parameters**:
- `role`: Role name (case-insensitive)

**Returns**: Set of capability strings, or empty set if role is unknown

**Examples**:
```python
from core.rbac import get_role_capabilities

# Get all capabilities for a role
caps = get_role_capabilities("pro")
# {'READ_PUBLIC', 'READ_LEDGER_FULL', 'PROPOSE_HYPOTHESIS', 'PROPOSE_AURA'}

# Check capability count
len(get_role_capabilities("general"))    # 1
len(get_role_capabilities("analytics"))  # 6
```

#### `validate_role(role: str) -> bool`

Check if a role is valid.

**Parameters**:
- `role`: Role name to validate

**Returns**: `True` if the role exists, `False` otherwise

**Examples**:
```python
from core.rbac import validate_role

validate_role("general")   # True
validate_role("pro")       # True
validate_role("unknown")   # False
validate_role("")          # False
```

### Helper Functions

#### `has_any_capability(role: str, capabilities: List[str]) -> bool`

Check if a role has at least one of the specified capabilities.

**Examples**:
```python
from core.rbac import has_any_capability, CAP_READ_PUBLIC, CAP_WRITE_GRAPH

has_any_capability("general", [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])  # True
has_any_capability("general", [CAP_WRITE_GRAPH, CAP_MANAGE_ROLES]) # False
```

#### `has_all_capabilities(role: str, capabilities: List[str]) -> bool`

Check if a role has all of the specified capabilities.

**Examples**:
```python
from core.rbac import has_all_capabilities, CAP_READ_PUBLIC, CAP_READ_LEDGER_FULL

has_all_capabilities("pro", [CAP_READ_PUBLIC, CAP_READ_LEDGER_FULL])  # True
has_all_capabilities("general", [CAP_READ_PUBLIC, CAP_READ_LEDGER_FULL])  # False
```

#### `get_missing_capabilities(role: str, required_capabilities: List[str]) -> Set[str]`

Get capabilities that a role is missing from a required set.

**Examples**:
```python
from core.rbac import get_missing_capabilities, CAP_READ_PUBLIC, CAP_WRITE_GRAPH

missing = get_missing_capabilities("general", [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])
# {'WRITE_GRAPH'}
```

## Usage Patterns

### Basic Authorization Check

```python
from core.rbac import has_capability, CAP_WRITE_GRAPH

def update_graph_entity(user_role: str, entity_data: dict):
    """Update an entity in the knowledge graph."""
    if not has_capability(user_role, CAP_WRITE_GRAPH):
        raise PermissionError(f"Role '{user_role}' cannot write to graph")
    
    # Perform update...
    return {"status": "success"}
```

### Endpoint Protection

```python
from fastapi import HTTPException, Header
from core.rbac import has_capability, CAP_VIEW_DEBUG

@app.get("/debug/metrics")
def get_metrics(user_role: str = Header(None, alias="X-User-Role")):
    """Protected debug endpoint."""
    if not has_capability(user_role, CAP_VIEW_DEBUG):
        raise HTTPException(
            status_code=403,
            detail=f"Role '{user_role}' does not have VIEW_DEBUG capability"
        )
    
    return get_system_metrics()
```

### Multi-Capability Check

```python
from core.rbac import has_all_capabilities, CAP_READ_LEDGER_FULL, CAP_PROPOSE_HYPOTHESIS

def suggest_hypothesis(user_role: str, hypothesis_data: dict):
    """Suggest a new hypothesis."""
    required_caps = [CAP_READ_LEDGER_FULL, CAP_PROPOSE_HYPOTHESIS]
    
    if not has_all_capabilities(user_role, required_caps):
        missing = get_missing_capabilities(user_role, required_caps)
        raise PermissionError(
            f"Role '{user_role}' is missing capabilities: {missing}"
        )
    
    # Process hypothesis...
    return {"status": "submitted"}
```

### Role-Based Feature Flags

```python
from core.rbac import get_role_capabilities

def get_user_features(user_role: str) -> dict:
    """Get available features for a role."""
    caps = get_role_capabilities(user_role)
    
    return {
        "can_read_public": CAP_READ_PUBLIC in caps,
        "can_read_full_ledger": CAP_READ_LEDGER_FULL in caps,
        "can_propose": CAP_PROPOSE_HYPOTHESIS in caps or CAP_PROPOSE_AURA in caps,
        "can_write": CAP_WRITE_GRAPH in caps,
        "can_debug": CAP_VIEW_DEBUG in caps,
    }
```

## Integration with Existing Systems

### Policy System Integration

The RBAC system integrates with the ingest policy system:

```python
from core.rbac import has_capability, CAP_WRITE_CONTRADICTIONS
from core.policy import get_ingest_policy

def commit_analysis(db, analysis, memory_id, user_roles):
    """Commit analysis with RBAC checks."""
    # Check write permissions
    can_write_contradictions = any(
        has_capability(role, CAP_WRITE_CONTRADICTIONS) 
        for role in user_roles
    )
    
    if can_write_contradictions:
        # Get policy for user roles
        policy = get_ingest_policy(user_roles)
        
        # Apply policy and commit
        if policy.write_contradictions_to_memories:
            # Write contradictions...
            pass
```

### Router/API Integration

```python
from fastapi import Header, HTTPException
from core.rbac import has_capability, CAP_PROPOSE_HYPOTHESIS

@app.post("/api/hypotheses")
def create_hypothesis(
    data: dict,
    user_role: str = Header(None, alias="X-User-Role")
):
    """Create a new hypothesis (requires PROPOSE_HYPOTHESIS)."""
    if not user_role or not has_capability(user_role, CAP_PROPOSE_HYPOTHESIS):
        raise HTTPException(
            status_code=403,
            detail="PROPOSE_HYPOTHESIS capability required"
        )
    
    # Process hypothesis...
    return {"id": "hyp-123", "status": "pending"}
```

## Testing

The RBAC system includes comprehensive table-driven tests:

### Test Coverage

- **102 total test cases**
- **40 role × capability combination tests** (5 roles × 8 capabilities)
- **8 invalid input tests** (unknown roles/capabilities)
- **Multiple test classes** covering:
  - Capability matrix verification
  - Role capability set validation
  - Role validation
  - Capability constant verification
  - Capability denial tests
  - Role comparison tests
  - Helper function tests
  - Case sensitivity tests
  - Edge case and weird combo tests
  - Role metadata tests
  - Complete coverage verification

### Running Tests

```bash
# Run all RBAC tests
pytest tests/rbac/test_capabilities.py -v

# Run with coverage summary
pytest tests/rbac/test_capabilities.py::TestCompleteCoverageMatrix::test_test_coverage_summary -v -s

# Run specific test class
pytest tests/rbac/test_capabilities.py::TestCapabilityMatrix -v

# Run parametrized tests for a specific role
pytest tests/rbac/test_capabilities.py -k "pro" -v
```

### Test Output Example

```
RBAC Test Coverage Summary
======================================================================
Roles defined: 5
Capabilities defined: 8
Test cases (valid): 40
Test cases (invalid): 8
Total test cases: 48
======================================================================

GENERAL: 1 capabilities
  ✓ READ_PUBLIC

PRO: 4 capabilities
  ✓ PROPOSE_AURA
  ✓ PROPOSE_HYPOTHESIS
  ✓ READ_LEDGER_FULL
  ✓ READ_PUBLIC

SCHOLARS: 4 capabilities
  ✓ PROPOSE_AURA
  ✓ PROPOSE_HYPOTHESIS
  ✓ READ_LEDGER_FULL
  ✓ READ_PUBLIC

ANALYTICS: 6 capabilities
  ✓ PROPOSE_AURA
  ✓ PROPOSE_HYPOTHESIS
  ✓ READ_LEDGER_FULL
  ✓ READ_PUBLIC
  ✓ WRITE_CONTRADICTIONS
  ✓ WRITE_GRAPH

OPS: 3 capabilities
  ✓ READ_LEDGER_FULL
  ✓ READ_PUBLIC
  ✓ VIEW_DEBUG
```

## Security Considerations

### Design Principles

1. **Fail Closed**: Unknown roles or capabilities default to denial
2. **Explicit Grants**: Capabilities must be explicitly granted to roles
3. **No Privilege Escalation**: Lower-privilege roles cannot access higher-privilege capabilities
4. **Case Insensitive**: Role names are normalized to lowercase to prevent bypasses
5. **Input Validation**: All inputs are validated before authorization checks

### Security Features

- **Unknown roles are denied all capabilities**
- **Unknown capabilities always return False**
- **Empty/None roles are rejected**
- **Special characters in role names are handled safely**
- **No SQL injection risks** (uses Python data structures, not database queries)

### Best Practices

1. **Always validate role before use**:
   ```python
   if validate_role(user_role):
       # Proceed with authorization check
   ```

2. **Use capability constants, never strings**:
   ```python
   # Good
   has_capability(role, CAP_WRITE_GRAPH)
   
   # Bad
   has_capability(role, "WRITE_GRAPH")
   ```

3. **Check capabilities at the earliest possible point**:
   ```python
   def protected_function(user_role):
       if not has_capability(user_role, REQUIRED_CAP):
           raise PermissionError()
       # Rest of function...
   ```

4. **Log authorization failures**:
   ```python
   if not has_capability(role, cap):
       logger.warning(f"Authorization denied: role={role}, capability={cap}")
       raise PermissionError()
   ```

## Future Enhancements

### Planned Features

1. **Multi-Role Support**: Allow users to have multiple roles simultaneously
2. **Role Inheritance**: Define role hierarchies (e.g., analytics inherits from pro)
3. **Dynamic Capabilities**: Load capabilities from configuration or database
4. **Capability Scopes**: Add resource-level scoping (e.g., "write graph for org X")
5. **Audit Logging**: Track all capability checks for security auditing
6. **MANAGE_ROLES Implementation**: Admin functionality for role management

### Extension Points

The system is designed for extension:

```python
# Add new role
ROLE_ADMIN = "admin"
ALL_ROLES = frozenset({..., ROLE_ADMIN})
ROLE_CAPABILITIES[ROLE_ADMIN] = {
    CAP_MANAGE_ROLES,
    # ... all other capabilities
}

# Add new capability
CAP_DELETE_DATA = "DELETE_DATA"
ALL_CAPABILITIES = frozenset({..., CAP_DELETE_DATA})
ROLE_CAPABILITIES[ROLE_ANALYTICS] = {
    ...,
    CAP_DELETE_DATA,
}
```

## Files Reference

### Module Structure

```
core/rbac/
├── __init__.py           # Module exports
├── capabilities.py       # Capability constants and authorization functions
└── roles.py              # Role constants and role-to-capability mappings

tests/rbac/
├── __init__.py
└── test_capabilities.py  # Comprehensive table-driven tests (102 tests)
```

### Import Paths

```python
# Import roles
from core.rbac import (
    ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, 
    ROLE_ANALYTICS, ROLE_OPS
)

# Import capabilities
from core.rbac import (
    CAP_READ_PUBLIC, CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS, CAP_PROPOSE_AURA,
    CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS,
    CAP_MANAGE_ROLES, CAP_VIEW_DEBUG
)

# Import functions
from core.rbac import (
    has_capability,
    get_role_capabilities,
    validate_role,
)
```

## Troubleshooting

### Common Issues

**Issue**: Authorization check always returns False

**Solution**: Verify role name is correct and matches defined roles (case-insensitive)
```python
# Check if role is valid
if not validate_role(user_role):
    logger.error(f"Invalid role: {user_role}")
```

**Issue**: Capability check fails with warning

**Solution**: Ensure you're using capability constants, not string literals
```python
# Use constants from module
from core.rbac import CAP_WRITE_GRAPH
has_capability(role, CAP_WRITE_GRAPH)
```

**Issue**: Need to know what capabilities a role has

**Solution**: Use `get_role_capabilities()` or check the capability matrix
```python
caps = get_role_capabilities("pro")
print(f"Pro capabilities: {sorted(caps)}")
```

---

**Version**: 1.0  
**Last Updated**: 2025-10-30  
**Maintainer**: Platform Team
