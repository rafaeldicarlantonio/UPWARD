# CI Evaluation Workflow - Quick Start

## Overview
Automated evaluation workflow with PR and nightly profiles, configurable latency slack, and comprehensive failure detection.

## Quick Commands

### Run PR Profile Locally
```bash
python3 evals/run.py \
  --config evals/ci_profile.yaml \
  --profile pr \
  --suite pareto_gate
```

### Run Nightly Profile Locally
```bash
python3 evals/run.py \
  --config evals/ci_profile.yaml \
  --profile nightly \
  --suite implicate_lift \
  --show-histogram
```

### Run with Custom Latency Slack
```bash
#Via environment variable
EVAL_LATENCY_SLACK_PERCENT=20 python3 evals/run.py --suite contradictions

# Via command line
python3 evals/run.py --suite contradictions --latency-slack 20
```

### Test CI Failure Detection
```bash
# Create functional failure test
python scripts/test_ci_failure.py --mode functional

# Run it (should fail)
python3 evals/run.py \
  --testset evals/testsets/ci_fail_functional.json \
  --ci-mode

# Clean up
python scripts/test_ci_failure.py --mode restore
```

## CI Profiles

| Profile | Cases | Flaky | Slack | Pass Rate | Use |
|---------|-------|-------|-------|-----------|-----|
| **pr** | 10 | Skip | 15% | 90% | PRs |
| **nightly** | All | Run | 10% | 95% | Daily |
| **full** | All | Run | 5% | 98% | Release |

## Latency Slack

### What is Slack?
Allows latency budgets to be relaxed by a percentage to account for CI environment variance.

### How It Works
```
Base budget: 500ms
Slack: 15%
Effective budget: 500 * 1.15 = 575ms
```

### Configuration
- **Environment**: `EVAL_LATENCY_SLACK_PERCENT=15`
- **Command line**: `--latency-slack 15`
- **Profile**: Defined in `ci_profile.yaml`
- **Constructor**: `LatencyGate(slack_percent=15)`

### Safe Defaults
- PR: 15% (allows variance)
- Nightly: 10% (tighter)
- Full: 5% (strict)
- Max: 50% (safety limit)

## GitHub Actions Workflow

### Triggers

**Pull Request**:
```yaml
on:
  pull_request:
    branches: [ main, develop ]
```
- Uses `pr` profile
- Runs subset of tests (10 per suite)
- 15% latency slack
- Fast feedback (< 5 min)

**Nightly**:
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC
```
- Uses `nightly` profile
- Runs all tests
- 10% latency slack
- Comprehensive validation

**Manual**:
```yaml
on:
  workflow_dispatch:
    inputs:
      profile: [ pr, nightly, full ]
      latency_slack: [ 0-50 ]
```
- User-selectable profile
- Custom slack percentage

### Status

**Success**: ✅ Green
- All tests pass
- No constraint violations
- Latency budgets met (with slack)

**Failure**: ❌ Red
- Test failures
- Constraint violations
- Latency budget exceeded

## Test PR Subset Configuration

Each suite defines representative scenarios for PR testing:

```yaml
suites:
  implicate_lift:
    pr_subset:
      max_cases: 8
      required_scenarios:
        - "bridge_entities"
        - "temporal_link"
        - "causal_chain"
```

Selection ensures coverage while keeping runtime fast.

## Flaky Test Management

### Skip in PR
```yaml
flaky_tests:
  skip_in_pr:
    - "implicate_003"
    - "external_009"
```

### Retry on Failure
```yaml
retry_on_failure:
  max_retries: 2
  patterns:
    - "timeout"
    - "connection"
```

## Failure Detection

### Functional Failures
```
Test assertion fails
  → Suite pass rate drops
  → If below min_pass_rate
    → CI RED
```

### Latency Violations
```
Latency exceeds budget (with slack)
  → Violation logged
  → latency_gate_passed = false
  → CI RED
```

### Constraint Violations
```
Pass rate < min_pass_rate
  → Constraint violated
  → CI RED
```

## Example Output

### PR Profile Success
```
🔧 Using CI profile: pr
   Description: Reduced test set for pull request validation
   Test selection: subset
   Latency slack: 15%

🎯 Running suite: pareto_gate
   Description: Pareto hypothesis retention gating

🚦 Latency Budget Gates:
  ✅ All latency budgets passed

✅ All evaluations passed!
```

### Nightly Profile with Violations
```
🔧 Using CI profile: nightly
   Description: Full test suites for nightly validation
   Test selection: full
   Latency slack: 10%

🚦 Latency Budget Gates:
  ❌ Latency budget violations detected:
     • retrieval p95 latency 650.0ms exceeds budget 550ms by 100.0ms

❌ Evaluation failed!
```

## Local Development Workflow

### 1. Before PR
```bash
# Run PR profile locally
python3 evals/run.py \
  --config evals/ci_profile.yaml \
  --profile pr \
  --suite <your_suite>

# Should match CI behavior
```

### 2. Investigate Failure
```bash
# Run with more verbose output
python3 evals/run.py \
  --suite <your_suite> \
  --verbose \
  --show-histogram
```

### 3. Test Latency Slack
```bash
# Test with no slack (strict)
EVAL_LATENCY_SLACK_PERCENT=0 python3 evals/run.py --suite <your_suite>

# Test with slack (relaxed)
EVAL_LATENCY_SLACK_PERCENT=15 python3 evals/run.py --suite <your_suite>
```

### 4. Run Full Validation
```bash
# Before release
python3 evals/run.py \
  --config evals/ci_profile.yaml \
  --profile full \
  --suite <your_suite>
```

## Common Scenarios

### Scenario: PR Failing Locally But Should Pass
**Issue**: Local environment slower than CI

**Solution**:
```bash
# Increase slack to match CI
EVAL_LATENCY_SLACK_PERCENT=20 python3 evals/run.py \
  --suite <your_suite>
```

### Scenario: Need Faster PR Feedback
**Issue**: PR tests taking too long

**Solution**:
- Check `pr_subset` configuration
- Reduce `max_cases` if needed
- Skip more flaky tests

### Scenario: Nightly Failing, PR Passing
**Issue**: PR subset missing edge cases

**Solution**:
- Review `required_scenarios`
- Add edge cases to PR subset
- Run full profile locally

### Scenario: Intermittent Latency Violations
**Issue**: CI environment variance

**Solution**:
- Check current slack percentage
- Consider increasing for affected profile
- Add to flaky_tests if persistent

## Testing

### Run CI Profile Tests
```bash
python3 -m unittest tests.evals.test_ci_profile -v
```

Expected: 23 tests, all passing

### Run All Eval Tests
```bash
python3 -m unittest discover -s tests/evals -p "test_*.py" -v
```

Expected: 95+ tests, all passing (1 may be skipped)

## Files

```
.github/workflows/evals.yml        # CI workflow
evals/ci_profile.yaml              # Profile config
evals/latency.py                   # Slack support
evals/run.py                       # Profile support
scripts/test_ci_failure.py         # Failure testing
tests/evals/test_ci_profile.py     # Tests
```

## Troubleshooting

### Problem: CI workflow not triggering
**Check**: PR branch and paths in `.github/workflows/evals.yml`

### Problem: Latency slack not applied
**Check**: Environment variable set correctly
```bash
echo $EVAL_LATENCY_SLACK_PERCENT
```

### Problem: Profile not found
**Check**: Profile name in `evals/ci_profile.yaml`
```bash
grep -A5 "profiles:" evals/ci_profile.yaml
```

### Problem: Test not in PR subset
**Check**: Suite configuration
```bash
grep -A10 "<suite_name>:" evals/ci_profile.yaml
```

## Next Steps

1. **Run tests**: `python3 -m unittest tests.evals.test_ci_profile -v`
2. **Test locally**: `python3 evals/run.py --profile pr --suite <suite>`
3. **Create PR**: CI will run automatically
4. **Monitor**: Check GitHub Actions for results

## Reference

See `CI_EVALS_IMPLEMENTATION.md` for complete documentation.
