# CI Latency Gates - Quick Start Guide

## What Are Latency Gates?

Latency gates enforce performance SLOs in CI by checking p95 latencies against budgets and failing PRs that exceed thresholds.

---

## Budgets (All enforced in CI)

| Metric | Budget | Description |
|--------|--------|-------------|
| Retrieval (dual-index) | ≤ 500ms | Vector + graph retrieval |
| Graph expansion | ≤ 200ms | Knowledge graph traversal |
| Context packing | ≤ 550ms | Prompt construction |
| Reviewer call | ≤ 500ms | External reviewer API (when enabled) |
| Overall /chat | ≤ 1200ms | End-to-end chat endpoint |

---

## Slack Configuration

### Automatic Slack by Environment

- **Pull Requests**: 0% slack (strict)
- **Nightly Builds**: 10% slack (allows variance)
- **Manual Runs**: Configurable via input

### Why Slack?

Allows for non-deterministic system variance in CI while maintaining strict enforcement on PRs.

---

## Quick Commands

### Check Gates Locally

```bash
# 1. Generate metrics by running performance tests
python3 -m pytest tests/perf/ -v

# 2. Check all gates (reads LATENCY_SLACK_PERCENT env var)
python3 evals/latency.py

# 3. Apply 10% slack (simulate nightly mode)
python3 evals/latency.py --slack 10

# 4. Check specific gates only
python3 evals/latency.py --gates retrieval_ms packing_ms

# 5. Quiet mode (only show failures)
python3 evals/latency.py --quiet
```

### Run Tests

```bash
# Run latency gate unit tests
python3 -m unittest tests.perf.test_latency_gate_ci -v

# Run all performance tests
python3 -m pytest tests/perf/ -v
```

---

## CI Workflows

### Latency Gates Workflow (`.github/workflows/latency-gates.yml`)

**When it runs:**
- Every PR to `main`/`develop`
- Nightly at 2 AM UTC
- Manual trigger via Actions tab

**What it does:**
1. Determines slack (0% for PRs, 10% for nightly)
2. Runs performance tests to generate metrics
3. Checks latency gates
4. Reports results in GitHub summary
5. Comments on PR if gates fail
6. Fails CI if budgets exceeded

**Manual trigger:**
1. Go to Actions tab
2. Select "Latency Gates" workflow
3. Click "Run workflow"
4. Set slack percentage (0-10)
5. Run

### Evaluation Workflow (`.github/workflows/evals.yml`)

Includes latency awareness with `EVAL_LATENCY_SLACK_PERCENT` env var.

---

## Interpreting Results

### ✅ Passing Gates

```
================================================================================
LATENCY GATE RESULTS
================================================================================
✅ Retrieval (dual-index) p95: 450.0ms ≤ 500.0ms (budget: 500ms, count: 100)
✅ Context packing p95: 500.0ms ≤ 550.0ms (budget: 550ms, count: 100)

Summary: 2/2 gates passed
✅ All gates passed
================================================================================
```

**What it means:** All operations meet performance SLOs. CI will pass.

### ❌ Failing Gates

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
  • ❌ Retrieval (dual-index) p95: 650.0ms > 500.0ms (budget: 500ms, overage: +150.0ms / +30.0%, count: 100)

Actionable steps:
  1. Review recent changes that may have impacted performance
  2. Profile slow operations to identify bottlenecks
  3. Consider optimizing hot paths or adding caching
  4. If budgets are unrealistic, update them in evals/latency.py
```

**What it means:** Retrieval is 30% slower than budget. CI will fail. Review changes for performance regressions.

### ⚠️ Warning (No Data)

```
⚠️  Retrieval (dual-index) p95: No data (count=0)
```

**What it means:** No metrics recorded. Run performance tests first or check if feature is disabled.

---

## Common Scenarios

### Scenario 1: PR Fails Gates

**Problem:** Your PR fails latency gates in CI

**Steps:**
1. Check workflow logs for which gates failed
2. Review changes in your PR that touch those areas
3. Run gates locally to reproduce:
   ```bash
   LATENCY_SLACK_PERCENT=0 python3 evals/latency.py
   ```
4. Profile slow operations:
   ```bash
   python3 -m cProfile -s cumtime your_script.py
   ```
5. Optimize hot paths (caching, query optimization, etc.)
6. Re-test locally before pushing
7. If budgets are unrealistic, discuss with team

### Scenario 2: Nightly Build Fails

**Problem:** Nightly build fails gates (with 10% slack applied)

**Steps:**
1. Check if it's a consistent failure (check last 3-5 nights)
2. Compare with PR runs to see if it's CI-specific
3. Investigate if recent merged PRs degraded performance
4. Consider if budgets need adjustment for new features
5. If persistent, file issue for investigation

### Scenario 3: Local Pass, CI Fails

**Problem:** Gates pass locally but fail in CI

**Possible Causes:**
- Local run uses slack, CI PR run uses 0% slack
- Different data/load in CI
- CI environment slower than local

**Steps:**
1. Test locally with 0% slack:
   ```bash
   LATENCY_SLACK_PERCENT=0 python3 evals/latency.py
   ```
2. Review differences in CI vs local environment
3. Ensure tests are deterministic
4. Consider if CI environment needs optimization

### Scenario 4: Adding New Feature

**Problem:** New feature needs latency budget

**Steps:**
1. Determine appropriate p95 budget based on requirements
2. Edit `evals/latency.py`:
   ```python
   DEFAULT_BUDGETS = [
       # ... existing ...
       LatencyBudget(
           metric_name="new_feature_ms",
           p95_budget_ms=400.0,
           description="New feature p95"
       ),
   ]
   ```
3. Add metric recording in code:
   ```python
   from core.metrics import observe_histogram
   observe_histogram("new_feature_ms", duration_ms)
   ```
4. Add test coverage in `tests/perf/test_latency_gate_ci.py`
5. Update documentation

---

## Python API

### Quick Check

```python
from evals.latency import check_latency_gates

# Simple check (returns True/False)
success = check_latency_gates(
    slack_percent=10.0,
    enabled_gates=["retrieval_ms", "packing_ms"],
    verbose=True,
    exit_on_failure=False
)

if not success:
    print("Gates failed!")
```

### Custom Gates

```python
from evals.latency import LatencyGates, LatencyBudget

# Create custom budget
custom_budget = LatencyBudget(
    metric_name="my_operation_ms",
    p95_budget_ms=300.0,
    description="My operation p95"
)

# Check custom gates
gates = LatencyGates(budgets=[custom_budget], slack_percent=5.0)
results = gates.check_all_gates()
gates.print_results(results)
success = gates.fail_if_exceeded(results, exit_on_failure=False)
```

### Recording Metrics

```python
from core.metrics import observe_histogram
import time

start = time.perf_counter()
# ... your operation ...
duration_ms = (time.perf_counter() - start) * 1000.0

observe_histogram("operation_ms", duration_ms, labels={"type": "sync"})
```

---

## Troubleshooting

### No Data (count=0)

**Problem:** Gates show "No data (count=0)"

**Solution:** 
```bash
# Run performance tests to generate metrics first
python3 -m pytest tests/perf/ -v

# Then check gates
python3 evals/latency.py
```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'core.metrics'`

**Solution:**
```bash
# Ensure you're in the workspace root
cd /workspace

# Or add workspace to PYTHONPATH
export PYTHONPATH=/workspace:$PYTHONPATH
```

### Workflow Doesn't Trigger

**Problem:** Latency gates workflow doesn't run on PR

**Solution:**
1. Check if PR modifies files in workflow paths:
   - `core/**`, `adapters/**`, `router/**`, `evals/**`, `tests/**`
2. Verify workflow file exists: `.github/workflows/latency-gates.yml`
3. Check branch protection rules allow workflow runs

### Gates Always Fail

**Problem:** Gates consistently fail even with good code

**Solution:**
1. Review budgets - may be too strict for current implementation
2. Check if test data is realistic
3. Verify metrics are being recorded correctly
4. Consider adjusting budgets in `evals/latency.py`

---

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `evals/latency.py` | Core gate checker | 363 |
| `tests/perf/test_latency_gate_ci.py` | Unit tests | 390 |
| `.github/workflows/latency-gates.yml` | CI workflow | 180 |
| `.github/workflows/evals.yml` | Eval workflow | 245 |
| `core/metrics.py` | Metrics collection | ~1000 |

---

## Best Practices

### Development Workflow

1. **Before starting work:** Check current gate status
2. **During development:** Run performance tests frequently
3. **Before committing:** Verify gates pass locally with 0% slack
4. **After PR fails:** Investigate immediately, don't merge with failures
5. **After merge:** Monitor nightly builds for trends

### Writing Performance-Sensitive Code

1. **Profile first:** Identify actual bottlenecks before optimizing
2. **Cache aggressively:** Reuse expensive computations
3. **Lazy load:** Defer expensive operations until needed
4. **Batch operations:** Reduce API calls and DB queries
5. **Monitor metrics:** Add observability for new operations

### Updating Budgets

1. **Document rationale:** Explain why budget changed
2. **Get approval:** Discuss with team before relaxing budgets
3. **Add tests:** Ensure new budgets are enforced
4. **Update docs:** Keep documentation in sync

---

## FAQ

**Q: Why do we have different slack for PRs vs nightly?**

A: PRs get 0% slack to catch regressions immediately. Nightly builds allow 10% slack to handle legitimate system variance while monitoring trends.

**Q: Can I disable a specific gate?**

A: Set `enabled_by_default=False` in the budget definition, or use `--gates` to check only specific gates.

**Q: What if my feature legitimately needs more time?**

A: Update the budget in `evals/latency.py` with team approval and clear documentation of why.

**Q: How do I test gates locally without running all perf tests?**

A: Record test metrics manually:
```python
from core.metrics import reset_metrics, observe_histogram
reset_metrics()
for _ in range(100):
    observe_histogram("retrieval_ms", 450.0, labels={"method": "dual"})
```

**Q: Can I run gates on specific branches?**

A: Yes, trigger manually via Actions tab with workflow dispatch.

**Q: How are percentiles calculated?**

A: P95 is calculated from sorted raw values using linear interpolation.

---

## Getting Help

1. **Check logs:** Review CI workflow logs for details
2. **Read summary:** Check GitHub Step Summary for results
3. **Run locally:** Reproduce issue with local testing
4. **Ask team:** Discuss performance concerns with team
5. **File issue:** Create issue for persistent problems

---

## Summary

✅ **All latency budgets enforced in CI**
✅ **Automatic slack based on environment**
✅ **Clear, actionable failure messages**
✅ **Comprehensive test coverage**
✅ **Easy local testing**
✅ **GitHub integration**

**Remember:** Latency gates protect user experience by preventing performance regressions from reaching production.

---

**Quick Links:**
- [Full Implementation Summary](LATENCY_GATES_CI_SUMMARY.md)
- [Test File](tests/perf/test_latency_gate_ci.py)
- [Latency Script](evals/latency.py)
- [Workflow](./github/workflows/latency-gates.yml)
