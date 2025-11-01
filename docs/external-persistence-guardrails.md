# External Content Persistence Guardrails

Critical security guardrails to prevent external content from being auto-ingested into internal storage.

## Overview

The system implements strict guardrails to ensure that external content (fetched from web sources) is **NEVER** automatically persisted to internal storage (memories, entities, edges). External content is intended for display and comparison only.

## Core Principle

**External content must remain ephemeral and display-only.**

Any attempt to write external content to the database is blocked and audited.

---

## Guardrail Function

### `forbid_external_persistence()`

Main guard function that checks items for external markers and blocks persistence.

```python
from core.guards import forbid_external_persistence

# Check items before persistence
items = [
    {
        "id": "mem_1",
        "text": "Internal content"
    },
    {
        "id": "ext_1",
        "text": "Wikipedia content",
        "provenance": {"url": "https://en.wikipedia.org/wiki/Test"}
    }
]

# This will raise ExternalPersistenceError
forbid_external_persistence(items, item_type="memory")
```

**Function Signature**:

```python
def forbid_external_persistence(
    items: List[Dict[str, Any]],
    item_type: str = "item",
    raise_on_external: bool = True
) -> Dict[str, Any]
```

**Parameters**:
- `items`: List of items to check
- `item_type`: Type of items (for logging: "memory", "entity", "edge")
- `raise_on_external`: If True, raises on external items; if False, returns report

**Returns**:
```python
{
    "checked": int,           # Number of items checked
    "external_count": int,    # Number of external items found
    "internal_count": int,    # Number of internal items
    "external_items": List,   # Details of blocked items
    "allowed": bool           # True if no external items
}
```

**Raises**:
- `ExternalPersistenceError`: If external items found and `raise_on_external=True`

---

## External Item Detection

An item is considered "external" if it has any of these markers:

### 1. Provenance URL
```python
{
    "id": "ext_1",
    "provenance": {
        "url": "https://example.com/page",
        "fetched_at": "2025-10-30T12:00:00Z"
    }
}
```

### 2. Source URL
```python
{
    "id": "ext_1",
    "source_url": "https://example.com/page"
}
```

### 3. External Flag
```python
{
    "id": "ext_1",
    "external": True
}
```

### 4. Metadata External Flag
```python
{
    "id": "ext_1",
    "metadata": {
        "external": True,
        "url": "https://example.com"
    }
}
```

---

## Integration Points

### 1. Commit Analysis (`ingest/commit.py`)

The `commit_analysis` function guards against external entities and edges:

```python
from ingest.commit import commit_analysis

# Source items with external marker will be blocked
source_items = [
    {
        "id": "ext_1",
        "provenance": {"url": "https://example.com"}
    }
]

# This will raise ExternalPersistenceError
commit_analysis(
    sb=supabase_client,
    analysis=analysis_result,
    source_items=source_items
)
```

### 2. Memory Upserts (`ingest/pipeline.py`)

The `upsert_memories_from_chunks` function guards against external memory writes:

```python
from ingest.pipeline import upsert_memories_from_chunks

# Source metadata with external marker will be blocked
source_metadata = {
    "source": "external",
    "provenance": {"url": "https://example.com"}
}

# This will raise ExternalPersistenceError
upsert_memories_from_chunks(
    sb=supabase_client,
    pinecone_index=index,
    embedder=embedder,
    file_id="test",
    title_prefix="Test",
    chunks=["Test chunk"],
    source_metadata=source_metadata
)
```

### 3. Web External Adapter (`adapters/web_external.py`)

The adapter includes warnings in documentation:

```python
async def fetch_content(self, url: str) -> Optional[str]:
    """
    Fetch content from a URL.
    
    IMPORTANT: This fetches external content for display/comparison ONLY.
    External content must NEVER be persisted to memories/entities/edges.
    All results should be marked with provenance.url to prevent auto-ingestion.
    """
```

---

## Audit Logging

When external items are blocked, a detailed audit log entry is created:

```json
{
    "event": "external_persistence_blocked",
    "item_type": "memory",
    "external_count": 2,
    "internal_count": 0,
    "external_items": [
        {
            "id": "ext_1",
            "url": "https://en.wikipedia.org/wiki/Test",
            "type": "memory"
        },
        {
            "id": "ext_2",
            "url": "https://arxiv.org/abs/1234.5678",
            "type": "memory"
        }
    ],
    "severity": "high"
}
```

Audit logs are written to the `audit.external_persistence` logger.

---

## Helper Functions

### `check_for_external_content()`

Check multiple content types at once:

```python
from core.guards import check_for_external_content

result = check_for_external_content(
    memories=[...],
    entities=[...],
    edges=[...]
)

# Returns:
# {
#     "memories": {...result...},
#     "entities": {...result...},
#     "edges": {...result...},
#     "total_external": int,
#     "allowed": bool
# }
```

### `filter_external_items()`

Split items into internal and external:

```python
from core.guards import filter_external_items

internal_items, external_items = filter_external_items(mixed_items)

# Process internal items safely
process_internal(internal_items)

# Handle external items separately (display only)
display_external(external_items)
```

---

## Usage Patterns

### Pattern 1: Guard Before Write

```python
from core.guards import forbid_external_persistence

def save_to_database(items):
    # Guard before any database writes
    forbid_external_persistence(items, item_type="memory")
    
    # Safe to write now - only internal items
    db.insert_many(items)
```

### Pattern 2: Check Without Raising

```python
from core.guards import forbid_external_persistence

def check_items(items):
    # Check without raising
    result = forbid_external_persistence(
        items,
        item_type="memory",
        raise_on_external=False
    )
    
    if result["external_count"] > 0:
        logger.warning(f"Found {result['external_count']} external items")
        return result["external_items"]
    
    return []
```

### Pattern 3: Filter and Process

```python
from core.guards import filter_external_items

def process_mixed_items(items):
    # Separate internal and external
    internal, external = filter_external_items(items)
    
    # Process internal items (persist)
    save_to_database(internal)
    
    # Process external items (display only)
    return format_for_display(external)
```

---

## Error Handling

### ExternalPersistenceError

Raised when attempting to persist external content:

```python
from core.guards import ExternalPersistenceError, forbid_external_persistence

try:
    forbid_external_persistence(items)
except ExternalPersistenceError as e:
    logger.error(f"Blocked external persistence: {e}")
    # Handle error (e.g., notify user, skip items)
```

**Error Message Format**:
```
Cannot persist external content: found 2 external memory(s) with provenance URLs. 
External content must not be written to internal storage.
```

---

## Security Properties

### 1. Fail-Safe by Default

The guard raises an exception by default, preventing any writes if external items are present.

### 2. Multiple Detection Mechanisms

Checks multiple fields to ensure external content is caught regardless of how it's marked.

### 3. Comprehensive Audit Trail

All blocked attempts are logged with:
- Event type
- Item count
- URLs
- Item type
- Severity

### 4. Zero False Negatives

Internal items without external markers always pass the guard.

### 5. Integration at Critical Points

Guards are placed at all database write entry points:
- Memory upserts
- Entity upserts
- Edge creation
- Commit phase

---

## Testing

Comprehensive tests verify all guardrail requirements:

```bash
# Run guardrail tests
pytest tests/external/test_non_ingest.py -v
```

**Test Coverage**:
- ✅ Basic guard functionality (5 tests)
- ✅ External item detection (7 tests)
- ✅ URL extraction (5 tests)
- ✅ Multiple content types (6 tests)
- ✅ Filtering (4 tests)
- ✅ Audit logging (3 tests)
- ✅ Pipeline integration (2 tests)
- ✅ Error messages (3 tests)
- ✅ Acceptance criteria (6 tests)
- ✅ Edge cases (5 tests)
- ✅ Comprehensive flow (1 test)

**Total**: 47 tests, 100% passing

---

## Monitoring

### Key Metrics

Track guardrail effectiveness:

```python
# Blocked persistence attempts
external.persistence.blocked{item_type=memory} = 15
external.persistence.blocked{item_type=entity} = 3
external.persistence.blocked{item_type=edge} = 1

# Items checked
external.persistence.checks{item_type=memory} = 1000
external.persistence.checks{item_type=entity} = 500

# Block rate
external.persistence.block_rate = blocked / checked
```

### Alerting

Set up alerts for:
- High block rate (>1% may indicate misconfiguration)
- Any external persistence blocks (should be rare in production)
- Repeated blocks from same source (may indicate bug)

---

## Troubleshooting

### Items Incorrectly Flagged as External

**Symptom**: Internal items are blocked

**Check**:
1. Ensure items don't have `provenance.url` field
2. Ensure `external` flag is not set to `True`
3. Check metadata for accidental `url` or `external` fields

**Fix**:
```python
# Remove external markers from internal items
item.pop("provenance", None)
item.pop("source_url", None)
item["external"] = False
```

### External Items Not Blocked

**Symptom**: External items pass the guard

**Check**:
1. Verify external items have proper markers
2. Check if `raise_on_external=False` was used
3. Review audit logs for detection

**Fix**:
```python
# Ensure external items have provenance
item["provenance"] = {
    "url": "https://example.com",
    "fetched_at": "2025-10-30T12:00:00Z"
}
```

### Audit Logs Not Appearing

**Symptom**: Blocks occur but no audit entries

**Check**:
1. Verify audit logger is configured
2. Check log level is WARNING or lower
3. Review log destination

**Fix**:
```python
import logging

# Configure audit logger
audit_logger = logging.getLogger("audit.external_persistence")
audit_logger.setLevel(logging.WARNING)
handler = logging.FileHandler("audit.log")
audit_logger.addHandler(handler)
```

---

## Best Practices

### 1. Guard Early

Place guards at the earliest possible point before database writes:

```python
def ingest_content(items):
    # Guard first
    forbid_external_persistence(items)
    
    # Then process
    analyze(items)
    persist(items)
```

### 2. Always Mark External Content

When fetching external content, immediately mark it:

```python
async def fetch_external(url):
    content = await fetch(url)
    
    # Mark as external
    return {
        "text": content,
        "provenance": {
            "url": url,
            "fetched_at": datetime.now().isoformat()
        }
    }
```

### 3. Filter Before Processing

Separate internal and external content early:

```python
def process_items(items):
    internal, external = filter_external_items(items)
    
    # Different handling
    persist(internal)
    display(external)
```

### 4. Monitor Audit Logs

Regularly review blocked attempts:

```bash
# Check for blocked persistence
grep "external_persistence_blocked" audit.log

# Count by item type
grep "external_persistence_blocked" audit.log | \
  jq '.item_type' | sort | uniq -c
```

### 5. Test Edge Cases

Always test with:
- Pure internal items
- Pure external items
- Mixed items
- Empty lists
- Missing fields

---

## Related Documentation

- [External Sources Configuration](./external-sources-config.md)
- [External Citation Formatting](./external-citation-formatting.md)
- [External Comparison Role Gating](./external-comparison-role-gating.md)
- [Ingest Pipeline Documentation](./ingest-pipeline.md)

---

## API Reference

### Core Functions

```python
# Main guard
forbid_external_persistence(items, item_type, raise_on_external) -> dict

# Multi-type check
check_for_external_content(memories, entities, edges, raise_on_external) -> dict

# Filter items
filter_external_items(items) -> tuple[list, list]
```

### Detection Functions

```python
# Check if item is external
_is_external_item(item) -> bool

# Extract URL from item
_extract_url(item) -> Optional[str]
```

### Exception Classes

```python
# Raised on external persistence attempt
class ExternalPersistenceError(Exception)
```

---

## Summary

The external persistence guardrails provide a robust, multi-layered defense against accidental ingestion of external content. Key features:

- **Comprehensive Detection**: Multiple marker types (provenance, flags, metadata)
- **Fail-Safe Default**: Raises exception by default
- **Detailed Auditing**: Every block is logged with full context
- **Integration Points**: Guards at all database write entry points
- **Well-Tested**: 47 comprehensive tests covering all scenarios

These guardrails ensure that external content remains ephemeral and display-only, maintaining the integrity of the internal knowledge base.
