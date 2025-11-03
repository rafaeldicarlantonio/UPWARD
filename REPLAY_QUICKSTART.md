# Replay CLI & Trace Freezer - Quick Start

## Overview
Freeze orchestration traces for deterministic replay and regression testing.

## Quick Commands

```bash
# List all frozen traces
python tools/replay_cli.py --list

# Get info about a trace
python tools/replay_cli.py --info <trace_id>

# Replay a trace
python tools/replay_cli.py <trace_id>

# Run tests
python -m unittest tests.evals.test_replay_freezer -v
```

## Freezing a Trace

### From Python Code

```python
from evals.freezer import TraceFreezer

freezer = TraceFreezer()

# Freeze a trace with candidates
candidates = [
    {"id": "doc_001", "score": 0.95},
    {"id": "doc_002", "score": 0.89}
]

trace = {
    "answer": "Test answer",
    "citations": [{"source_id": "doc_001"}],
    "candidates": candidates  # Important: include for determinism
}

frozen = freezer.freeze(
    query="What is regularization?",
    role="researcher",
    candidates=candidates,
    trace=trace,
    notes="Test freeze"
)

print(f"✅ Frozen: {frozen.trace_id}")
print(f"   Hash: {frozen.trace_hash}")
```

### From API Response

```python
from evals.freezer import freeze_from_response

# After making API call
response = api_client.chat(query="Test query")

# Freeze the response
frozen = freeze_from_response(
    query="Test query",
    role="researcher",
    response=response,
    notes="Captured from dev run"
)
```

## Replaying a Trace

### Using CLI

```bash
# Replay with full validation
python tools/replay_cli.py my_trace_123

# Output:
# 🔄 Loading frozen trace: my_trace_123
# ✅ Loaded trace from 2025-11-03T22:12:41Z
#    Query: What is regularization?...
#    Original hash: 20aaf635bfd132bc
# 🎲 Seeding randomness: 1234567890
# ▶️  Replaying orchestration...
#    Using frozen candidates (offline mode)
#    Replay hash: 20aaf635bfd132bc
#    Hash validation: ✅ MATCH
#    Candidate validation: ✅ MATCH
#
# ✅ Replay PASSED - Determinism verified

# Save results to file
python tools/replay_cli.py my_trace_123 --output results.json
```

### Using Python API

```python
from tools.replay_cli import ReplayRunner

runner = ReplayRunner()

result = runner.replay(
    trace_id="my_trace_123",
    offline_mode=True,
    validate_hash=True,
    validate_candidates=True
)

if result["success"]:
    print("✅ Replay PASSED")
else:
    print(f"❌ Replay FAILED: {result['validation']}")
```

## Key Concepts

### Deterministic Hashing
Traces are hashed excluding non-deterministic fields:
- ❌ Excluded: `latency`, `timing`, `timestamp`, `duration`
- ✅ Included: `answer`, `citations`, `candidates`, `orchestration`

### Randomness Seeding
All randomness sources are seeded for determinism:
- Python `random` module
- NumPy (if available)
- PyTorch (if available)
- `PYTHONHASHSEED` environment variable

### Offline Replay
Replays use frozen candidates without API calls:
- No network required
- Instant execution
- Perfect for CI/CD

## Common Workflows

### Development
```python
# During development, freeze interesting traces
if dev_mode:
    frozen = freeze_from_response(
        query=user_query,
        role=user_role,
        response=api_response,
        notes=f"Feature: {feature_name}"
    )
```

### Regression Testing
```bash
# Before deploying, replay all frozen traces
for trace in evals/frozen_traces/*.json; do
    id=$(basename $trace .json)
    python tools/replay_cli.py $id || exit 1
done
echo "✅ All traces replayed successfully"
```

### CI/CD Integration
```yaml
# .github/workflows/replay-tests.yml
- name: Replay Frozen Traces
  run: |
    for trace in evals/frozen_traces/*.json; do
      id=$(basename $trace .json)
      python tools/replay_cli.py $id
    done
```

## Testing

```bash
# Run all replay/freezer tests
python -m unittest tests.evals.test_replay_freezer -v

# Expected: 27-29 tests, all passing
# Ran 27 tests in 0.043s
# OK (skipped=1)
```

## Troubleshooting

### "Hash mismatch" Error
**Cause**: Non-deterministic code or unseeded randomness

**Fix**:
1. Ensure candidates are included in trace
2. Seed randomness via `ReplaySeeder.seed_all()`
3. Use offline mode for guaranteed determinism

### "Trace not found" Error
**Cause**: Trace file doesn't exist

**Fix**:
```bash
# List available traces
python tools/replay_cli.py --list

# Verify file exists
ls -la evals/frozen_traces/
```

### "Candidate ID mismatch" Error
**Cause**: Retrieval logic changed

**Fix**:
1. Use offline mode (always uses frozen candidates)
2. Re-freeze traces after intentional changes
3. Check for database/index updates

## File Locations

```
evals/
├── freezer.py                         # Freezer module
└── frozen_traces/                     # Frozen trace storage
    ├── trace_001.json
    ├── trace_002.json
    └── ...

tools/
└── replay_cli.py                      # Replay CLI

tests/evals/
└── test_replay_freezer.py             # Tests
```

## Next Steps

1. **Freeze your first trace**: Follow the examples above
2. **Replay it**: Verify determinism with `replay_cli.py`
3. **Add to CI**: Integrate replay into your test suite
4. **Build library**: Accumulate traces for regression testing

## Reference

See `REPLAY_FREEZER_IMPLEMENTATION.md` for complete documentation.
