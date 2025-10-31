# Write Path Authorization Guards

## Overview

All write operations in the system are protected by capability-based guards. This ensures that only authorized roles can modify data in the knowledge graph, propose hypotheses, or flag contradictions.

## Protected Operations

### 1. Hypothesis Proposals (PROPOSE_HYPOTHESIS)

**Capability**: `PROPOSE_HYPOTHESIS`  
**Roles**: Pro, Scholars, Analytics

**Endpoints**:
- `POST /hypotheses/propose` - Propose new hypothesis

**Access Control**:
```
✓ Pro       - Can propose hypotheses
✓ Scholars  - Can propose hypotheses  
✓ Analytics - Can propose hypotheses
✗ General   - 403 Forbidden
✗ Ops       - 403 Forbidden
```

**Example**:
```bash
curl -X POST /hypotheses/propose \
  -H "Authorization: Bearer $PRO_TOKEN" \
  -d '{
    "title": "ML Performance Hypothesis",
    "description": "Neural networks improve with more data",
    "source_message_id": "msg-123"
  }'
```

### 2. Graph Writes (WRITE_GRAPH)

**Capability**: `WRITE_GRAPH`  
**Roles**: Analytics only

**Endpoints**:
- `POST /entities` - Create new entity
- `POST /entities/{id}/edges` - Create edge between entities
- `PUT /entities/{id}` - Update entity properties

**Access Control**:
```
✓ Analytics - Can write to graph
✗ General   - 403 Forbidden
✗ Pro       - 403 Forbidden
✗ Scholars  - 403 Forbidden
✗ Ops       - 403 Forbidden
```

**Example**:
```bash
# Create entity
curl -X POST /entities \
  -H "Authorization: Bearer $ANALYTICS_TOKEN" \
  -d '{
    "name": "Machine Learning",
    "type": "concept",
    "properties": {"category": "AI"}
  }'

# Create edge
curl -X POST /entities/concept-1/edges \
  -H "Authorization: Bearer $ANALYTICS_TOKEN" \
  -d '{
    "target_id": "concept-2",
    "relationship": "relates_to",
    "properties": {"weight": 0.9}
  }'
```

### 3. Contradiction Writes (WRITE_CONTRADICTIONS)

**Capability**: `WRITE_CONTRADICTIONS`  
**Roles**: Analytics only

**Endpoints**:
- `POST /memories/{id}/contradictions` - Add contradiction to memory

**Access Control**:
```
✓ Analytics - Can write contradictions
✗ General   - 403 Forbidden
✗ Pro       - 403 Forbidden
✗ Scholars  - 403 Forbidden
✗ Ops       - 403 Forbidden
```

**Example**:
```bash
curl -X POST /memories/mem-123/contradictions \
  -H "Authorization: Bearer $ANALYTICS_TOKEN" \
  -d '{
    "contradicting_memory_id": "mem-456",
    "explanation": "These statements conflict on key facts",
    "confidence": 0.92
  }'
```

## Role Capabilities Summary

### General
- **Can**: Read public content
- **Cannot**: Propose, write to graph, write contradictions
- **Use Case**: Basic content consumer

### Pro
- **Can**: Read all content, propose hypotheses
- **Cannot**: Write to graph, write contradictions
- **Use Case**: Professional user suggesting improvements

### Scholars
- **Can**: Read all content, propose hypotheses
- **Cannot**: Write to graph, write contradictions
- **Use Case**: Academic researcher (suggest-only access)

### Analytics
- **Can**: Read all content, propose hypotheses, write to graph, write contradictions
- **Cannot**: Manage roles
- **Use Case**: Data scientist modifying knowledge graph

### Ops
- **Can**: Read content, manage roles, view debug info
- **Cannot**: Propose, write to graph, write contradictions
- **Use Case**: System administrator

## Implementation

### Guard Decorator

All write endpoints use the `@require` decorator:

```python
from fastapi import Request
from api.guards import require

@router.post("/hypotheses/propose")
@require("PROPOSE_HYPOTHESIS")
async def propose_hypothesis(request: Request, proposal: HypothesisProposal):
    """Propose a new hypothesis - requires PROPOSE_HYPOTHESIS capability."""
    # Implementation...

@router.post("/entities")
@require("WRITE_GRAPH")
async def create_entity(request: Request, entity: EntityCreate):
    """Create entity - requires WRITE_GRAPH capability."""
    # Implementation...

@router.post("/memories/{id}/contradictions")
@require("WRITE_CONTRADICTIONS")
async def add_contradiction(request: Request, memory_id: str, contradiction: ContradictionCreate):
    """Add contradiction - requires WRITE_CONTRADICTIONS capability."""
    # Implementation...
```

### 403 Error Response

When a user lacks the required capability:

```json
{
  "error": "forbidden",
  "capability": "WRITE_GRAPH",
  "message": "Capability 'WRITE_GRAPH' required",
  "user_roles": ["pro"],
  "missing": ["WRITE_GRAPH"]
}
```

## Usage Patterns

### Pattern 1: Scholars Suggest, Analytics Apply

Scholars can propose hypotheses, but analytics must apply them:

```python
# Scholars user proposes
POST /hypotheses/propose
Headers: Authorization: Bearer $SCHOLARS_TOKEN
Body: {"title": "Research hypothesis", ...}

# Response: 200 OK
{"hypothesis_id": "hyp-123", "status": "proposed"}

# Later, analytics user applies
POST /entities
Headers: Authorization: Bearer $ANALYTICS_TOKEN
Body: {"name": "Research hypothesis", "type": "hypothesis", ...}

# Response: 200 OK
{"id": "entity-456"}
```

### Pattern 2: Pro Proposes, Analytics Writes

Pro users propose, analytics writes to graph:

```python
# Pro user proposes connection
POST /hypotheses/propose
Headers: Authorization: Bearer $PRO_TOKEN
Body: {"title": "Concepts A and B are related", ...}

# Analytics reviews and creates edge
POST /entities/concept-a/edges
Headers: Authorization: Bearer $ANALYTICS_TOKEN
Body: {"target_id": "concept-b", "relationship": "relates_to", ...}
```

### Pattern 3: Analytics Direct Write

Analytics can directly write without proposal:

```python
# Analytics creates entity
POST /entities
Headers: Authorization: Bearer $ANALYTICS_TOKEN
Body: {"name": "New Concept", "type": "concept", ...}

# Analytics creates edge
POST /entities/new-concept/edges
Headers: Authorization: Bearer $ANALYTICS_TOKEN
Body: {"target_id": "existing-concept", "relationship": "supports", ...}

# Analytics flags contradiction
POST /memories/mem-123/contradictions
Headers: Authorization: Bearer $ANALYTICS_TOKEN
Body: {"contradicting_memory_id": "mem-456", ...}
```

## Error Handling

### Handling 403 Responses

```python
import requests

def propose_hypothesis(token, proposal):
    """Propose hypothesis with error handling."""
    response = requests.post(
        "https://api.example.com/hypotheses/propose",
        headers={"Authorization": f"Bearer {token}"},
        json=proposal
    )
    
    if response.status_code == 403:
        error = response.json()
        print(f"Access denied: {error['message']}")
        print(f"Required capability: {error['capability']}")
        print(f"Your roles: {error['user_roles']}")
        return None
    
    response.raise_for_status()
    return response.json()
```

### Graceful Degradation

```python
# Try to write, fall back to propose
def add_entity(user_roles, entity_data):
    """Add entity or propose it based on permissions."""
    if "analytics" in user_roles:
        # Direct write
        return create_entity(entity_data)
    elif any(role in user_roles for role in ["pro", "scholars"]):
        # Propose for review
        return propose_hypothesis({
            "title": f"Add {entity_data['name']}",
            "description": entity_data.get("description", "")
        })
    else:
        # No permissions
        raise PermissionError("Cannot add entities or propose hypotheses")
```

## Testing

See `tests/rbac/test_write_paths.py` for comprehensive examples.

### Running Tests

```bash
# All write path tests
pytest tests/rbac/test_write_paths.py -v

# Specific capability
pytest tests/rbac/test_write_paths.py::TestHypothesisProposal -v
pytest tests/rbac/test_write_paths.py::TestGraphWrites -v
pytest tests/rbac/test_write_paths.py::TestContradictionsWrites -v
```

## Monitoring

### Metrics to Track

```python
from core.metrics import record_counter

# Track authorization attempts
record_counter("auth.capability_check", 1, 
    labels={"capability": "WRITE_GRAPH", "granted": False})

# Track successful writes
record_counter("graph.entity_created", 1,
    labels={"role": "analytics"})
```

### Audit Logging

```python
import logging
logger = logging.getLogger("security.write_access")

# Log all write attempts
logger.info(
    f"Write attempt: endpoint=/entities, user={user_id}, "
    f"roles={user_roles}, capability=WRITE_GRAPH, granted={granted}"
)
```

## Best Practices

### 1. Always Use Appropriate Role

```python
# ✓ Correct
# Scholars propose (suggest-only)
POST /hypotheses/propose with scholars token

# Analytics applies to graph
POST /entities with analytics token

# ✗ Wrong
# Trying to write directly with scholars token
POST /entities with scholars token  # → 403 Forbidden
```

### 2. Check Permissions Client-Side

```python
from core.rbac import has_capability

def can_write_graph(user_roles):
    """Check if user can write to graph."""
    return any(
        has_capability(role, "WRITE_GRAPH")
        for role in user_roles
    )

# Show/hide UI elements based on permissions
if can_write_graph(user_roles):
    show_create_entity_button()
else:
    show_propose_hypothesis_button()
```

### 3. Provide Clear UI Feedback

```python
# When 403 occurs
if response.status_code == 403:
    error = response.json()
    
    if error["capability"] == "WRITE_GRAPH":
        show_message(
            "You cannot modify the graph directly. "
            "Use the 'Propose' feature to suggest changes."
        )
    elif error["capability"] == "PROPOSE_HYPOTHESIS":
        show_message(
            "Upgrade to Pro to propose hypotheses."
        )
```

## Troubleshooting

### Issue: 403 Forbidden on Proposal

**Symptom**: Pro user gets 403 when proposing

**Cause**: Pro role not properly assigned

**Solution**: Verify user roles
```sql
SELECT user_id, role_key FROM user_roles WHERE user_id = 'xxx';
```

### Issue: Analytics Gets 403 on Graph Write

**Symptom**: Analytics user gets 403

**Cause**: Analytics role not assigned or JWT token stale

**Solution**: 
- Verify analytics role in database
- Regenerate JWT token
- Clear middleware cache

### Issue: Scholars Cannot Propose

**Symptom**: Scholars gets 403 on proposal

**Cause**: PROPOSE_HYPOTHESIS not assigned to scholars

**Solution**: Verify `core/rbac/roles.py`:
```python
ROLE_SCHOLARS: {
    CAP_PROPOSE_HYPOTHESIS,  # Must be present
    # ...
}
```

---

**Version**: 1.0  
**Last Updated**: 2025-10-30  
**See Also**:
- `docs/rbac-system.md` - RBAC framework
- `docs/api-guards.md` - Guard decorators
- `tests/rbac/test_write_paths.py` - Comprehensive tests
