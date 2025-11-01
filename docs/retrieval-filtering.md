# Role-Based Retrieval Filtering

## Overview

The retrieval filtering system implements visibility levels to control which memories users can access based on their roles. It ensures data privacy and appropriate information disclosure through level-based filtering and trace summary processing.

## Visibility Levels

### Level Mapping

| Role | Level | Can View |
|------|-------|----------|
| **general** | 0 | Level 0 only |
| **pro** | 1 | Levels 0-1 |
| **scholars** | 1 | Levels 0-1 |
| **analytics** | 2 | Levels 0-2 (all) |
| **ops** | 2 | Levels 0-2 (all) |

### Level Descriptions

- **Level 0 (Public)**: General access - publicly shareable information
- **Level 1 (Professional)**: Pro/scholars access - detailed professional content
- **Level 2 (Internal)**: Analytics/ops access - internal system data

### Hierarchy

```
Level 2 (Internal)    ┌─────────────────────────┐
Analytics, Ops        │  All memories visible   │
                      └─────────────────────────┘
                                ▲
                                │
Level 1 (Professional)┌─────────┴───────────────┐
Pro, Scholars         │  Levels 0-1 visible     │
                      └─────────────────────────┘
                                ▲
                                │
Level 0 (Public)      ┌─────────┴───────────────┐
General               │  Level 0 only visible   │
                      └─────────────────────────┘
```

## Filtering Logic

### Memory Visibility

Memories are filtered by comparing their `role_view_level` to the caller's maximum level:

```python
# Visibility rule
memory_visible = memory.role_view_level <= caller_max_level
```

**Examples**:
- General (level 0) + Memory (level 0) → ✓ Visible
- General (level 0) + Memory (level 1) → ✗ Hidden
- Pro (level 1) + Memory (level 1) → ✓ Visible
- Analytics (level 2) + Memory (level 0) → ✓ Visible
- Analytics (level 2) + Memory (level 2) → ✓ Visible

### Multiple Roles

When a user has multiple roles, the **highest level** is used:

```python
user_roles = ["general", "pro"]  # Levels: 0, 1
max_level = 1  # Pro's level

# User can see levels 0 and 1
```

## Trace Summary Processing

Different roles receive different levels of detail in trace summaries:

### Level 0 (General)
- **Max lines**: 4
- **Sensitive data**: Stripped
- **Format**: "Line 1\nLine 2\nLine 3\nLine 4\n... (N more lines)"

### Level 1+ (Pro, Scholars, Analytics, Ops)
- **Max lines**: Unlimited (full summary)
- **Sensitive data**: Preserved
- **Format**: Full original text

### Sensitive Information Stripping

For level 0 users, sensitive information is automatically removed:

**Stripped Patterns**:
- UUIDs: `123e4567-e89b-12d3-a456-426614174000` → `[ID]`
- Internal markers: `[internal]` → (removed)
- System markers: `[system]` → (removed)
- Database references: `db.` → (removed)

**Example**:
```
Original:
  "Entity 123e4567-e89b-12d3-a456-426614174000 [internal] from db.memories"

Processed (level 0):
  "Entity [ID] from memories"

Processed (level 1+):
  "Entity 123e4567-e89b-12d3-a456-426614174000 [internal] from db.memories"
```

## API Reference

### Core Functions

#### `get_role_level(role: str) -> int`

Get visibility level for a role.

```python
from core.rbac import get_role_level

level = get_role_level("general")  # 0
level = get_role_level("pro")      # 1
level = get_role_level("analytics") # 2
```

#### `get_max_role_level(roles: List[str]) -> int`

Get maximum visibility level from multiple roles.

```python
from core.rbac import get_max_role_level

max_level = get_max_role_level(["general", "pro"])  # 1 (pro's level)
```

#### `can_view_memory(caller_roles: List[str], memory_level: int) -> bool`

Check if caller can view a memory.

```python
from core.rbac import can_view_memory

can_view = can_view_memory(["general"], 0)  # True
can_view = can_view_memory(["general"], 1)  # False
can_view = can_view_memory(["pro"], 1)      # True
```

#### `filter_memories_by_level(memories: List[Dict], caller_roles: List[str]) -> List[Dict]`

Filter memories by caller's visibility level.

```python
from core.rbac import filter_memories_by_level

memories = [
    {"id": "m1", "role_view_level": 0},
    {"id": "m2", "role_view_level": 1},
    {"id": "m3", "role_view_level": 2},
]

filtered = filter_memories_by_level(memories, ["general"])
# Returns: [{"id": "m1", "role_view_level": 0}]
```

#### `process_trace_summary(trace_summary: str, caller_roles: List[str]) -> str`

Process trace summary based on caller's level.

```python
from core.rbac import process_trace_summary

long_summary = "\n".join([f"Line {i}" for i in range(10)])

# General gets capped summary
general_summary = process_trace_summary(long_summary, ["general"])
# "Line 0\nLine 1\nLine 2\nLine 3\n... (6 more lines)"

# Pro gets full summary
pro_summary = process_trace_summary(long_summary, ["pro"])
# All 10 lines
```

## Integration with Selection System

The filtering is automatically applied in `core/selection.py`:

```python
# In DualSelector.select()
def select(self, query, embedding, caller_role=None, **kwargs):
    caller_roles = kwargs.get('caller_roles', [caller_role or 'general'])
    
    # Query indices...
    
    # Filter by role visibility level
    all_records = filter_memories_by_level(all_records, caller_roles)
    
    # Process trace summaries
    for record in all_records:
        if "process_trace_summary" in record:
            record["process_trace_summary"] = process_trace_summary(
                record["process_trace_summary"],
                caller_roles
            )
    
    # Return filtered results...
```

## Usage Examples

### Basic Filtering

```python
from core.rbac import filter_memories_by_level

memories = [
    {"id": "public", "text": "Public info", "role_view_level": 0},
    {"id": "pro", "text": "Pro info", "role_view_level": 1},
    {"id": "internal", "text": "Internal info", "role_view_level": 2},
]

# General user
general_memories = filter_memories_by_level(memories, ["general"])
# Returns: 1 memory (level 0 only)

# Pro user  
pro_memories = filter_memories_by_level(memories, ["pro"])
# Returns: 2 memories (levels 0-1)

# Analytics user
analytics_memories = filter_memories_by_level(memories, ["analytics"])
# Returns: 3 memories (all levels)
```

### Trace Summary Processing

```python
from core.rbac import process_trace_summary

summary = """
Step 1: Query analysis
Step 2: Memory retrieval  
Step 3: Entity expansion
Step 4: Ranking
Step 5: Packing
Step 6: Response generation
"""

# General user - capped to 4 lines
general_summary = process_trace_summary(summary, ["general"])
print(general_summary)
# Output:
# Step 1: Query analysis
# Step 2: Memory retrieval
# Step 3: Entity expansion
# Step 4: Ranking
# ... (2 more lines)

# Pro user - full summary
pro_summary = process_trace_summary(summary, ["pro"])
print(pro_summary)
# Output: (all 6 lines)
```

### API Endpoint with Filtering

```python
from fastapi import Request
from api.middleware import get_user_roles
from core.rbac import filter_memories_by_level

@app.get("/memories/search")
def search_memories(request: Request, query: str):
    """Search memories with role-based filtering."""
    # Get caller's roles
    caller_roles = get_user_roles(request)
    
    # Query memories (unfiltered)
    memories = database.search_memories(query)
    
    # Filter by visibility level
    visible_memories = filter_memories_by_level(memories, caller_roles)
    
    # Process trace summaries
    for memory in visible_memories:
        if "process_trace_summary" in memory:
            memory["process_trace_summary"] = process_trace_summary(
                memory["process_trace_summary"],
                caller_roles
            )
    
    return {"memories": visible_memories}
```

## Database Schema

Memories should include a `role_view_level` field:

```sql
-- Add to memories table
ALTER TABLE memories 
ADD COLUMN role_view_level INTEGER DEFAULT 0;

-- Create index for filtering
CREATE INDEX idx_memories_role_view_level 
ON memories(role_view_level);

-- Set levels for existing data
UPDATE memories 
SET role_view_level = 0 
WHERE type = 'public';

UPDATE memories 
SET role_view_level = 1 
WHERE type IN ('professional', 'detailed');

UPDATE memories 
SET role_view_level = 2 
WHERE type IN ('internal', 'system');
```

## Testing

### Unit Tests

```python
from core.rbac import filter_memories_by_level, ROLE_GENERAL, ROLE_PRO

def test_general_cannot_see_pro_memories():
    """General role should not see pro-level memories."""
    memories = [
        {"id": "m1", "role_view_level": 0},
        {"id": "m2", "role_view_level": 1},
    ]
    
    filtered = filter_memories_by_level(memories, [ROLE_GENERAL])
    
    assert len(filtered) == 1
    assert filtered[0]["id"] == "m1"

def test_pro_can_see_pro_memories():
    """Pro role should see pro-level memories."""
    memories = [
        {"id": "m1", "role_view_level": 0},
        {"id": "m2", "role_view_level": 1},
    ]
    
    filtered = filter_memories_by_level(memories, [ROLE_PRO])
    
    assert len(filtered) == 2
```

### Integration Tests

```python
def test_retrieval_respects_visibility():
    """Test that retrieval respects visibility levels."""
    # Create memories at different levels
    create_memory("public", level=0)
    create_memory("pro", level=1)
    create_memory("internal", level=2)
    
    # General user retrieval
    general_results = search_as_user(["general"], "query")
    assert len(general_results) == 1  # Only public
    
    # Pro user retrieval
    pro_results = search_as_user(["pro"], "query")
    assert len(pro_results) == 2  # Public + pro
    
    # Analytics user retrieval
    analytics_results = search_as_user(["analytics"], "query")
    assert len(analytics_results) == 3  # All
```

See `tests/rbac/test_retrieval_filters.py` for comprehensive examples.

## Monitoring

### Metrics

Track filtering effectiveness:

```python
from core.metrics import get_counter

# Add to selection.py
def select(self, query, embedding, caller_roles, **kwargs):
    # ... query and process ...
    
    original_count = len(all_records)
    all_records = filter_memories_by_level(all_records, caller_roles)
    filtered_count = original_count - len(all_records)
    
    # Record metrics
    record_counter("retrieval.filtered_by_level", filtered_count)
    record_histogram("retrieval.visible_memories", len(all_records))
```

### Logging

```python
import logging
logger = logging.getLogger("core.selection")

# Logs visibility filtering
logger.debug(
    f"Filtered {filtered_count} memories above caller level "
    f"(caller_level={caller_level}, roles={caller_roles})"
)
```

## Best Practices

### 1. Always Set role_view_level on Memories

```python
# When creating memories
memory = {
    "text": "Content...",
    "role_view_level": determine_visibility_level(content),
    # ...
}
```

### 2. Use Appropriate Levels for Content

```python
def determine_visibility_level(content, metadata):
    """Determine appropriate visibility level."""
    if "internal" in metadata.get("tags", []):
        return 2  # Internal only
    elif "professional" in metadata.get("tags", []):
        return 1  # Pro and above
    else:
        return 0  # Public
```

### 3. Filter Early in Pipeline

```python
# Filter as early as possible to avoid processing
# memories the user can't see anyway

def search(query, caller_roles):
    # Query database
    raw_results = query_database(query)
    
    # Filter immediately
    visible_results = filter_memories_by_level(raw_results, caller_roles)
    
    # Then process/rank only visible results
    ranked = rank_and_pack(visible_results)
    
    return ranked
```

### 4. Always Process Trace Summaries

```python
# Before returning to user
for memory in results:
    if "process_trace_summary" in memory:
        memory["process_trace_summary"] = process_trace_summary(
            memory["process_trace_summary"],
            caller_roles
        )
```

## Migration Guide

### Adding Levels to Existing Memories

```sql
-- Step 1: Add column with default
ALTER TABLE memories ADD COLUMN role_view_level INTEGER DEFAULT 0;

-- Step 2: Classify existing memories
UPDATE memories 
SET role_view_level = CASE
    WHEN metadata->>'sensitive' = 'true' THEN 2
    WHEN metadata->>'professional' = 'true' THEN 1
    ELSE 0
END;

-- Step 3: Create index
CREATE INDEX idx_memories_role_view_level ON memories(role_view_level);
```

### Updating Selection Logic

```python
# Old code (no filtering)
def select(self, query, embedding):
    hits = vector_store.query(embedding)
    return hits

# New code (with filtering)
def select(self, query, embedding, caller_roles):
    hits = vector_store.query(embedding)
    
    # Add role_view_level from metadata
    for hit in hits:
        hit["role_view_level"] = hit.metadata.get("role_view_level", 0)
    
    # Filter by level
    filtered = filter_memories_by_level(hits, caller_roles)
    
    return filtered
```

## Security Considerations

### Data Leakage Prevention

1. **Filter before processing**: Reduce risk of accidental leaks
2. **Strip sensitive data**: Remove internal IDs, markers for low-level users
3. **Cap trace summaries**: Limit detailed provenance for general users
4. **Default to level 0**: Unknown levels default to most restrictive

### Audit Logging

```python
import logging
logger = logging.getLogger("security.access")

def filter_memories_by_level(memories, caller_roles):
    caller_level = get_max_role_level(caller_roles)
    
    filtered = []
    denied_count = 0
    
    for memory in memories:
        if memory["role_view_level"] <= caller_level:
            filtered.append(memory)
        else:
            denied_count += 1
            logger.info(
                f"Access denied: memory_id={memory['id']}, "
                f"memory_level={memory['role_view_level']}, "
                f"caller_level={caller_level}, roles={caller_roles}"
            )
    
    return filtered
```

## Troubleshooting

### Issue: General Users See No Results

**Symptoms**: General users get empty results even when data exists

**Cause**: All memories have `role_view_level > 0`

**Solution**: Ensure some memories are marked as level 0
```sql
SELECT COUNT(*), role_view_level 
FROM memories 
GROUP BY role_view_level;

-- If no level 0 memories exist, mark some as public
UPDATE memories 
SET role_view_level = 0 
WHERE type = 'public' OR tags @> '["public"]';
```

### Issue: Pro Users See Same as General

**Symptoms**: Pro and general users see identical results

**Cause**: No level 1 memories exist, or level mapping incorrect

**Solution**: Verify level mapping and data
```python
from core.rbac import get_role_level

print(f"Pro level: {get_role_level('pro')}")  # Should be 1

# Check for level 1 memories
SELECT COUNT(*) FROM memories WHERE role_view_level = 1;
```

### Issue: Trace Summaries Always Capped

**Symptoms**: All users get capped summaries, even pro users

**Cause**: Caller roles not passed correctly

**Solution**: Ensure caller_roles parameter is provided
```python
# Wrong
result = selector.select(query, embedding)

# Correct
result = selector.select(query, embedding, caller_roles=["pro"])
```

---

**Version**: 1.0  
**Last Updated**: 2025-10-30  
**See Also**:
- `docs/rbac-system.md` - RBAC capability system
- `core/rbac/levels.py` - Level implementation
- `core/selection.py` - Selection with filtering
- `tests/rbac/test_retrieval_filters.py` - Comprehensive tests
