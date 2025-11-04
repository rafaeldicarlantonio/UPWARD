# Graph Expansion Budget - Quick Start

## Overview
Bounded graph neighborhood expansion with node/time caps and automatic short-circuit when budgets are exceeded.

## Key Features

- **Node Budget**: Max 50 neighbors (configurable)
- **Time Budget**: Max 150ms from config (configurable)
- **Depth Budget**: Max depth 1 (configurable)
- **Short-Circuit**: Returns partial results when over budget
- **Metrics**: Tracks truncation events and reasons

## Quick Usage

### Basic Expansion
```python
from core.graph_expand import expand_entity_bounded

result = expand_entity_bounded(
    entity_id="entity_123",
    db_adapter=db_adapter,
    caller_roles=["general"]
)

# Check results
print(f"Relations: {len(result.relations)}")
print(f"Memories: {len(result.memories)}")
print(f"Truncated: {result.truncated}")

if result.truncated:
    print(f"Reason: {result.truncation_reason}")
```

### Custom Budgets
```python
from core.graph_expand import GraphExpander

expander = GraphExpander(
    max_neighbors=30,  # Lower node budget
    max_depth=1,
    timeout_ms=100     # Tighter time budget
)

result = expander.expand_entity(
    entity_id="entity_456",
    db_adapter=db_adapter,
    caller_role="researcher"
)
```

### Check Budget Status
```python
result = expand_entity_bounded(...)

# Which budgets were exceeded?
if result.budget_exceeded.get('time'):
    print("Time budget exceeded")

if result.budget_exceeded.get('nodes'):
    print("Node budget exceeded")

# Performance info
print(f"Took {result.elapsed_ms:.2f}ms")
print(f"Visited {result.nodes_visited} nodes")
```

## Configuration

### From Environment
```bash
# Set graph timeout (default 150ms)
export PERF_GRAPH_TIMEOUT_MS=200
```

### Query Current Config
```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:5000/debug/config | \
  jq '.performance.budgets_ms.PERF_GRAPH_TIMEOUT_MS'
```

## Truncation Scenarios

| Scenario | Result | Truncated? |
|----------|--------|-----------|
| 5 relations, 3 memories | Full results | No |
| 60 relations | First 50 + truncation | Yes (nodes) |
| Slow DB (200ms) | Partial results | Yes (time) |
| 1000 relations + slow DB | Short-circuit quickly | Yes (both) |

## Use Cases

### 1. Normal Case (No Truncation)
```python
# Small entity with few connections
result = expand_entity_bounded(entity_id="small_entity", db_adapter=db)

# result.truncated = False
# result.nodes_visited = 5
# result.relations = [(rel1), (rel2), ...]
# result.memories = [mem1, mem2, ...]
```

### 2. Heavy Entity (Truncation)
```python
# Large entity with many connections
result = expand_entity_bounded(entity_id="hub_entity", db_adapter=db)

# result.truncated = True
# result.truncation_reason = "node_budget_exceeded"
# result.nodes_visited = 50 (capped)
# Still have usable partial results
```

### 3. Slow Database (Timeout)
```python
# Expansion hits time budget
result = expand_entity_bounded(entity_id="entity", db_adapter=slow_db)

# result.truncated = True
# result.truncation_reason = "timeout_after_relations"
# result.budget_exceeded['time'] = True
# Returns what was collected before timeout
```

## Metrics

### Track Truncation Rate
```python
# In monitoring dashboard
truncation_rate = graph_expansion_truncated_total / graph_expansion_total
```

### Truncation Reasons
- `node_budget_exceeded`: Too many relations
- `total_nodes_exceeded`: Relations + memories exceeded budget
- `timeout_after_relations`: Timed out after fetching relations
- `timeout_after_memories`: Timed out after fetching memories
- `error: <msg>`: Error during expansion

### Key Metrics
- `graph.expansion.truncated`: Truncation events by reason
- `graph.expansion.budget_exceeded`: Budget exceeded by type (time/nodes)
- `graph.expansion.latency_ms`: Expansion latency histogram
- `graph.expansion.nodes_visited`: Nodes visited histogram

## Testing

```bash
# Run all tests
python3 -m unittest tests.perf.test_graph_budget -v

# Run acceptance tests
python3 -m unittest tests.perf.test_graph_budget.TestAcceptanceCriteria -v

# Test heavy graph performance
python3 -m unittest tests.perf.test_graph_budget.TestHeavyGraphPerformance -v
```

## Integration Example

### In Selection Pipeline
```python
from core.graph_expand import expand_entity_bounded

def _expand_implicate_content(self, entity_id, caller_role, caller_roles):
    """Expand implicate content with bounded search."""
    result = expand_entity_bounded(
        entity_id=entity_id,
        db_adapter=self.db_adapter,
        caller_role=caller_role,
        caller_roles=caller_roles,
        max_neighbors=50,
        timeout_ms=150
    )
    
    # Log truncation
    if result.truncated:
        print(f"Graph expansion truncated for {entity_id}: {result.truncation_reason}")
    
    return {
        "summary": result.summary,
        "relations": result.relations,
        "memories": result.memories
    }
```

## Best Practices

1. **Use Default Budgets**: Start with defaults (50 nodes, 150ms)
2. **Monitor Truncation**: Track truncation rate in production
3. **Adjust if Needed**: Increase budgets if truncation rate is high
4. **Handle Partial Results**: Code should work with partial results
5. **Check Budget Status**: Use `result.budget_exceeded` to understand why

## Troubleshooting

### High Truncation Rate
```python
# Check metrics
if truncation_rate > 0.5:
    # Consider increasing budgets
    expander = GraphExpander(
        max_neighbors=100,  # Double the budget
        timeout_ms=300      # Double the timeout
    )
```

### Slow Performance
```python
# Check which budget is hit most
if budget_exceeded['time'] > budget_exceeded['nodes']:
    # Time is the bottleneck - optimize DB queries
    # Or increase timeout
    timeout_ms=200
else:
    # Node count is the bottleneck - reduce max_neighbors
    max_neighbors=30
```

### Empty Results
```python
# Check if entity exists
result = expand_entity_bounded(entity_id, db_adapter)

if result.nodes_visited == 0:
    print("Entity has no connections or doesn't exist")
```

## Performance Tips

- **Small graphs**: No overhead, completes normally
- **Medium graphs**: May hit node budget, still fast
- **Large graphs**: Will truncate, completes within timeout
- **Extreme graphs**: Short-circuits quickly, returns partial results

Average latencies:
- Small (< 10 nodes): ~5ms
- Medium (10-50 nodes): ~50ms
- Large (50+ nodes, truncated): ~150ms (timeout)

Memory usage is bounded to O(max_neighbors) regardless of actual graph size.
