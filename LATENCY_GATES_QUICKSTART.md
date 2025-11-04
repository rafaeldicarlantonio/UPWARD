# CI Latency Gates - Quick Reference

Fast reference for using CI latency gates.

## Quick Start

### 1. Generate Metrics

```bash
# Run performance tests to populate metrics
python3 -m pytest tests/perf/ -v
```

### 2. Check Gates

```bash
# Check all enabled gates
python3 evals/latency.py

# Check with slack (nightly mode)
python3 evals/latency.py --slack 10

# Check specific gates
python3 evals/latency.py --gates retrieval_ms packing_ms
```

### 3. Interpret Results

**✅ All gates passed**:
```
================================================================================
LATENCY GATE RESULTS
================================================================================
✅ Retrieval (dual-index) p95: 450.0ms ≤ 500.0ms (budget: 500ms, count: 100)
✅ Context packing p95: 520.0ms ≤ 550.0ms (budget: 550ms, count: 100)

Summary: 2/2 gates passed
✅ All gates passed
================================================================================
```

**❌ Gate failed**:
```
================================================================================
LATENCY GATE RESULTS
================================================================================
❌ Retrieval (dual-index) p95: 650.0ms > 500.0ms (budget: 500ms, overage: +150.0ms / +30.0%, count: 100)

Summary: 0/1 gates passed
⚠️  1 gate(s) failed
================================================================================

❌ LATENCY GATES FAILED

The following latency budgets were exceeded:
  • ❌ Retrieval (dual-index) p95: 650.0ms > 500.0ms (budget: 500ms, overage: +150.0ms / +30.0%)

Actionable steps:
  1. Review recent changes that may have impacted performance
  2. Profile slow operations to identify bottlenecks
  3. Consider optimizing hot paths or adding caching
  4. If budgets are unrealistic, update them in evals/latency.py
```

## Budgets

| Metric | p95 Budget | Description | Default Enabled |
|--------|------------|-------------|----------------|
| `retrieval_ms` | ≤ 500ms | Dual-index retrieval | ✅ |
| `graph_expand_ms` | ≤ 200ms | Graph expansion | ✅ |
| `packing_ms` | ≤ 550ms | Context packing | ✅ |
| `reviewer_ms` | ≤ 500ms | Reviewer call | ❌ (when enabled) |
| `chat_total_ms` | ≤ 1200ms | Overall /chat | ✅ |

## CLI Usage

### Basic Commands

```bash
# Check all enabled gates (no slack)
python3 evals/latency.py

# Apply 10% slack to all budgets
python3 evals/latency.py --slack 10

# Check only specific gates
python3 evals/latency.py --gates retrieval_ms packing_ms

# Quiet mode (only show failures)
python3 evals/latency.py --quiet
```

### With Environment Variables

```bash
# Set slack via env var
export LATENCY_SLACK_PERCENT=5
python3 evals/latency.py

# Temporary env var
LATENCY_SLACK_PERCENT=10 python3 evals/latency.py
```

## Python API

### Basic Usage

```python
from evals.latency import check_latency_gates

# Check all gates
success = check_latency_gates()

# With slack
success = check_latency_gates(slack_percent=10.0)

# Check specific gates
success = check_latency_gates(enabled_gates=["retrieval_ms", "packing_ms"])

# Don't exit on failure
success = check_latency_gates(exit_on_failure=False)
```

### Advanced Usage

```python
from evals.latency import LatencyGates, LatencyBudget

# Create custom budgets
custom_budgets = [
    LatencyBudget(
        metric_name="retrieval_ms",
        p95_budget_ms=400.0,  # Stricter budget
        description="Fast retrieval",
        labels={"method": "dual"}
    )
]

# Initialize gates
gates = LatencyGates(budgets=custom_budgets, slack_percent=5.0)

# Check gates
results = gates.check_all_gates()

# Print results
gates.print_results(results, verbose=True)

# Check for failures
success = gates.fail_if_exceeded(results, exit_on_failure=False)
```

### Programmatic Checking

```python
from evals.latency import LatencyGates

gates = LatencyGates(slack_percent=10.0)
results = gates.check_all_gates(enabled_gates=["retrieval_ms"])

for result in results:
    print(f"Metric: {result.metric_name}")
    print(f"Budget: {result.budget_ms}ms")
    print(f"Actual p95: {result.actual_p95}ms")
    print(f"Passed: {result.passed}")
    print(f"Message: {result.message}")
    print(f"Slack: {result.slack_applied_percent}%")
```

## CI/CD Integration

### GitHub Actions

**PR workflow** (strict, no slack):
```yaml
- name: Check latency gates
  env:
    LATENCY_SLACK_PERCENT: 0
  run: python3 evals/latency.py
```

**Nightly workflow** (lenient, 10% slack):
```yaml
- name: Check latency gates
  env:
    LATENCY_SLACK_PERCENT: 10
  run: python3 evals/latency.py
```

**Manual workflow** (configurable):
```yaml
- name: Check latency gates
  env:
    LATENCY_SLACK_PERCENT: ${{ github.event.inputs.slack_percent || '0' }}
  run: python3 evals/latency.py
```

### Complete CI Job

```yaml
jobs:
  latency-gates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Generate metrics
        run: python3 -m pytest tests/perf/ -v
      
      - name: Check gates
        env:
          LATENCY_SLACK_PERCENT: ${{ github.event_name == 'schedule' && '10' || '0' }}
        run: python3 evals/latency.py
```

## Slack Configuration

### When to Use Slack

| Context | Slack | Reason |
|---------|-------|--------|
| PR | 0% | Strict enforcement, prevent regressions |
| Nightly | 10% | Allow variance, monitor trends |
| Manual | Variable | Testing and debugging |
| Production | 0% | Strict monitoring |

### Slack Calculation

```python
# Base budget
budget = 500.0  # ms

# With 0% slack (PR mode)
allowed = 500.0ms

# With 10% slack (nightly mode)
allowed = 500.0 * 1.10 = 550.0ms

# With 5% slack (custom)
allowed = 500.0 * 1.05 = 525.0ms
```

## Customizing Budgets

### Edit Default Budgets

```python
# evals/latency.py

DEFAULT_BUDGETS = [
    LatencyBudget(
        metric_name="retrieval_ms",
        p95_budget_ms=400.0,  # ← Change this
        description="Retrieval (dual-index) p95",
        labels={"method": "dual"}
    ),
    # ... other budgets
]
```

### Add New Budget

```python
# evals/latency.py

DEFAULT_BUDGETS = [
    # ... existing budgets
    LatencyBudget(
        metric_name="my_custom_operation_ms",
        p95_budget_ms=300.0,
        description="Custom operation p95",
        enabled_by_default=True
    ),
]
```

### Disable Budget

```python
LatencyBudget(
    metric_name="reviewer_ms",
    p95_budget_ms=500.0,
    description="Reviewer call p95",
    enabled_by_default=False  # ← Disabled by default
)
```

## Common Workflows

### 1. Pre-commit Check

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running latency gates..."
python3 -m pytest tests/perf/ -v -q
python3 evals/latency.py --quiet

if [ $? -ne 0 ]; then
    echo "❌ Latency gates failed. Commit aborted."
    exit 1
fi
```

### 2. Local Development

```bash
# After making changes
python3 -m pytest tests/perf/ -v

# Check impact on latency
python3 evals/latency.py

# Compare with slack
python3 evals/latency.py --slack 10
```

### 3. Performance Regression Detection

```bash
# Baseline (main branch)
git checkout main
python3 -m pytest tests/perf/ -v
python3 evals/latency.py > baseline.txt

# Feature branch
git checkout feature-branch
python3 -m pytest tests/perf/ -v
python3 evals/latency.py > feature.txt

# Compare
diff baseline.txt feature.txt
```

### 4. Continuous Monitoring

```python
# monitor.py
from evals.latency import LatencyGates

def check_latency_daily():
    """Run daily latency checks."""
    gates = LatencyGates(slack_percent=10.0)
    results = gates.check_all_gates()
    
    failed = [r for r in results if not r.passed]
    
    if failed:
        send_alert(f"Daily latency check: {len(failed)} gates failed")
    
    return len(failed) == 0
```

## Troubleshooting

### No Data (Count=0)

**Symptom**: All gates show "No data (count=0)"

**Cause**: Metrics not recorded

**Fix**:
```bash
# Generate metrics first
python3 -m pytest tests/perf/ -v

# Then check gates
python3 evals/latency.py
```

### Gates Fail Unexpectedly

**Symptom**: Local gates pass, CI fails

**Cause**: Different slack settings

**Fix**:
```bash
# Test with CI settings (0% slack)
python3 evals/latency.py --slack 0

# Compare with nightly (10% slack)
python3 evals/latency.py --slack 10
```

### Budgets Too Strict

**Symptom**: Frequent failures on minor changes

**Fix**:
1. Use slack for nightly: `--slack 10`
2. Review budgets in `evals/latency.py`
3. Consider if budgets are realistic for your system

### Missing Gate

**Symptom**: Expected gate not checked

**Cause**: Gate disabled by default

**Fix**:
```bash
# Enable specific gate
python3 evals/latency.py --gates retrieval_ms reviewer_ms packing_ms
```

Or edit `evals/latency.py`:
```python
LatencyBudget(
    metric_name="reviewer_ms",
    enabled_by_default=True  # ← Enable
)
```

## Best Practices

### ✅ Do

- Run performance tests before checking gates
- Use 0% slack for PRs (strict enforcement)
- Use 10% slack for nightly (trend monitoring)
- Update budgets when architecture changes
- Include actionable messages in custom gates
- Check gates locally before pushing

### ❌ Don't

- Run gates without generating metrics first
- Use excessive slack (>10%)
- Keep unrealistic budgets
- Ignore repeated gate failures
- Skip gates in CI

## Examples

### Example 1: Basic Check

```bash
$ python3 -m pytest tests/perf/ -v
$ python3 evals/latency.py

================================================================================
LATENCY GATE RESULTS
================================================================================
✅ Retrieval (dual-index) p95: 450.0ms ≤ 500.0ms (budget: 500ms, count: 100)
✅ Graph expansion p95: 150.0ms ≤ 200.0ms (budget: 200ms, count: 100)
✅ Context packing p95: 520.0ms ≤ 550.0ms (budget: 550ms, count: 100)

Summary: 3/3 gates passed
✅ All gates passed
================================================================================
```

### Example 2: With Slack

```bash
$ LATENCY_SLACK_PERCENT=10 python3 evals/latency.py

================================================================================
LATENCY GATE RESULTS
================================================================================
ℹ️  Slack applied: +10.0% to all budgets

✅ Retrieval (dual-index) p95: 525.0ms ≤ 550.0ms (budget: 500ms, +10% slack, count: 100)
✅ Context packing p95: 580.0ms ≤ 605.0ms (budget: 550ms, +10% slack, count: 100)

Summary: 2/2 gates passed
✅ All gates passed
================================================================================
```

### Example 3: Failure

```bash
$ python3 evals/latency.py

================================================================================
LATENCY GATE RESULTS
================================================================================
❌ Retrieval (dual-index) p95: 650.0ms > 500.0ms (budget: 500ms, overage: +150.0ms / +30.0%, count: 100)

Summary: 0/1 gates passed
⚠️  1 gate(s) failed
================================================================================

❌ LATENCY GATES FAILED

The following latency budgets were exceeded:
  • ❌ Retrieval (dual-index) p95: 650.0ms > 500.0ms (budget: 500ms, overage: +150.0ms / +30.0%)

Actionable steps:
  1. Review recent changes that may have impacted performance
  2. Profile slow operations to identify bottlenecks
  3. Consider optimizing hot paths or adding caching
  4. If budgets are unrealistic, update them in evals/latency.py
```

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│ LATENCY GATES QUICK REFERENCE                               │
├─────────────────────────────────────────────────────────────┤
│ CHECK ALL GATES                                             │
│   python3 evals/latency.py                                  │
│                                                             │
│ WITH SLACK                                                  │
│   python3 evals/latency.py --slack 10                       │
│                                                             │
│ SPECIFIC GATES                                              │
│   python3 evals/latency.py --gates retrieval_ms packing_ms  │
│                                                             │
│ QUIET MODE                                                  │
│   python3 evals/latency.py --quiet                          │
│                                                             │
│ VIA ENV VAR                                                 │
│   LATENCY_SLACK_PERCENT=5 python3 evals/latency.py          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ BUDGETS                                                     │
├─────────────────────────────────────────────────────────────┤
│ retrieval_ms      ≤ 500ms   (dual-index)                   │
│ graph_expand_ms   ≤ 200ms   (graph expansion)              │
│ packing_ms        ≤ 550ms   (context packing)              │
│ reviewer_ms       ≤ 500ms   (reviewer call)                │
│ chat_total_ms     ≤ 1200ms  (overall /chat)                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SLACK SETTINGS                                              │
├─────────────────────────────────────────────────────────────┤
│ PR mode:      0%  (strict)                                  │
│ Nightly:      10% (lenient)                                 │
│ Manual:       0-10% (configurable)                          │
└─────────────────────────────────────────────────────────────┘
```

## Related Documentation

- `LATENCY_GATES_DELIVERY_SUMMARY.md` - Full implementation details
- `evals/latency.py` - Source code
- `.github/workflows/latency-gates.yml` - CI workflow
- `tests/perf/test_latency_gate_ci.py` - Test examples

---

**Need help?** Check the full delivery summary or file an issue.
