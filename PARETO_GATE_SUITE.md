# Pareto Gate Evaluation Suite

## Overview

The Pareto Gate suite tests the hypothesis proposal persistence behavior based on Pareto scoring and override mechanisms. This suite validates that:

1. **Proposals with score ≥ threshold persist** (return 201 Created)
2. **Proposals with score < threshold are rejected** (return 202 Accepted with reason)
3. **Override mechanisms always persist** (regardless of score)
4. **Metrics accurately count persisted/rejected proposals**
5. **Scoring latency stays under budget** (p95 < 200ms)

## Files

### Suite Definition
- **`evals/suites/pareto_gate.jsonl`**: 16 test cases in JSONL format

### Test Cases
- **`evals/cases/pareto/case_001_well_above.json`**: Score 0.87, well above threshold
- **`evals/cases/pareto/case_002_above.json`**: Score 0.81, above threshold
- **`evals/cases/pareto/case_003_above.json`**: Score 0.76, above threshold
- **`evals/cases/pareto/case_004_just_above.json`**: Score 0.67, just above threshold
- **`evals/cases/pareto/case_005_at_threshold.json`**: Score 0.65, exactly at threshold
- **`evals/cases/pareto/case_006_just_below.json`**: Score 0.63, just below threshold
- **`evals/cases/pareto/case_007_below.json`**: Score 0.57, below threshold
- **`evals/cases/pareto/case_008_well_below.json`**: Score 0.46, well below threshold
- **`evals/cases/pareto/case_009_far_below.json`**: Score 0.32, far below threshold
- **`evals/cases/pareto/case_010_analytics_override.json`**: Score 0.47, analytics override
- **`evals/cases/pareto/case_011_security_override.json`**: Score 0.39, security override
- **`evals/cases/pareto/case_012_executive_override.json`**: Score 0.50, executive override
- **`evals/cases/pareto/case_013_high_microservices.json`**: Score 0.88, high quality
- **`evals/cases/pareto/case_014_high_graphql.json`**: Score 0.77, high quality
- **`evals/cases/pareto/case_015_low_functions.json`**: Score 0.49, below threshold
- **`evals/cases/pareto/case_016_boundary_caching.json`**: Score 0.66, boundary case

### Fixtures
- **`evals/fixtures/pareto_proposals.json`**: 16 deterministic proposals with known scores

### Unit Tests
- **`tests/evals/test_pareto_gate.py`**: 32 tests validating persistence logic

## Test Case Summary

| Case ID | Score | Scenario | Expected Persisted | Status Code | Rationale |
|---------|-------|----------|-------------------|-------------|-----------|
| pareto_001 | 0.87 | well_above_threshold | ✓ | 201 | Score well above 0.65 threshold |
| pareto_002 | 0.81 | above_threshold | ✓ | 201 | Score above threshold |
| pareto_003 | 0.76 | above_threshold | ✓ | 201 | Score comfortably above threshold |
| pareto_004 | 0.67 | just_above_threshold | ✓ | 201 | Score just above threshold |
| pareto_005 | 0.65 | at_threshold | ✓ | 201 | Score exactly at threshold (≥ condition) |
| pareto_006 | 0.63 | just_below_threshold | ✗ | 202 | Score just below threshold |
| pareto_007 | 0.57 | below_threshold | ✗ | 202 | Score below threshold |
| pareto_008 | 0.46 | well_below_threshold | ✗ | 202 | Score well below threshold |
| pareto_009 | 0.32 | far_below_threshold | ✗ | 202 | Score far below threshold |
| pareto_010 | 0.47 | analytics_override | ✓ | 201 | Override persists despite low score |
| pareto_011 | 0.39 | security_override | ✓ | 201 | Security override persists |
| pareto_012 | 0.50 | executive_override | ✓ | 201 | Executive override persists |
| pareto_013 | 0.88 | well_above_threshold | ✓ | 201 | Excellent score, clear persist |
| pareto_014 | 0.77 | above_threshold | ✓ | 201 | High quality proposal |
| pareto_015 | 0.49 | below_threshold | ✗ | 202 | Below threshold, reject |
| pareto_016 | 0.66 | just_above_threshold | ✓ | 201 | Marginally above threshold |

## Scoring Configuration

The Pareto score is calculated as a weighted sum of four signal components:

```python
score = (
    novelty * 0.35 +
    evidence_strength * 0.30 +
    coherence * 0.20 +
    specificity * 0.15
)
```

**Threshold**: 0.65

- **Score ≥ 0.65**: Proposal persists (201 Created)
- **Score < 0.65**: Proposal rejected (202 Accepted)

## Expected Endpoint Behavior

### POST /hypotheses/propose

The endpoint should:

1. **Calculate Pareto score** from input signals
2. **Check for override flags** (analytics, security, executive)
3. **Persist if score ≥ threshold OR override enabled**
4. **Return appropriate status code**:
   - **201 Created**: Proposal persisted
   - **202 Accepted**: Proposal evaluated but not persisted

### Response Schema

#### Persisted Proposal (201 Created)
```json
{
  "persisted": true,
  "score": 0.87,
  "threshold": 0.65,
  "override": false,
  "timing": {
    "scoring_ms": 145.0
  }
}
```

#### Override Persisted (201 Created)
```json
{
  "persisted": true,
  "score": 0.47,
  "threshold": 0.65,
  "override": true,
  "override_reason": "analytics_priority",
  "timing": {
    "scoring_ms": 138.0
  }
}
```

#### Rejected Proposal (202 Accepted)
```json
{
  "persisted": false,
  "score": 0.57,
  "threshold": 0.65,
  "reason": "score_below_threshold",
  "timing": {
    "scoring_ms": 132.0
  }
}
```

## Harness Validation

For each test case, the harness validates:

### 1. Persistence Behavior
```python
if persisted != expected_persisted:
    FAIL("Persistence mismatch")
```

### 2. Status Code
```python
if status_code != expected_status_code:
    FAIL("Status code mismatch")
```

### 3. Override Logging
```python
if override_enabled and not response["override"]:
    FAIL("Override not logged")
```

### 4. Rejection Reason
```python
if not persisted and not rejection_reason:
    FAIL("Missing rejection reason")
```

### 5. Scoring Latency
```python
if scoring_latency_ms > max_scoring_latency_ms:
    FAIL("Scoring latency exceeds budget")
```

## Running the Suite

### Run Full Suite
```bash
cd /workspace
python3 evals/run.py --testset evals/suites/pareto_gate.jsonl
```

### Run Unit Tests
```bash
cd /workspace
python3 -m unittest tests.evals.test_pareto_gate -v
```

### Expected Output
```
Running testset: evals/suites/pareto_gate.jsonl
  [1/16] pareto_001
    PASS - 150.2ms
    Score: 0.870, Threshold: 0.650, Persisted: ✓, Scoring: 145.0ms
  [2/16] pareto_002
    PASS - 148.5ms
    Score: 0.810, Threshold: 0.650, Persisted: ✓, Scoring: 142.0ms
  ...
  [10/16] pareto_010
    PASS - 152.3ms
    Score: 0.470, Threshold: 0.650, Persisted: ✓ [OVERRIDE: analytics_priority], Scoring: 138.0ms
  ...

EVALUATION SUMMARY
================================================================================
Total Cases: 16
Passed: 16 (100.0%)
Failed: 0 (0.0%)

Category Breakdown:
  pareto_gate: 16/16 (100.0%)

Performance Constraints:
  P95 < 200ms: ✓ PASS (165.0ms)
```

## Acceptance Criteria

### ✅ 100% Match to Expected Persisted Flag
- All 16 cases must match their `expected_persisted` value
- 9 cases should persist (6 natural + 3 override)
- 7 cases should be rejected

### ✅ Correct Metrics
- **Total proposals**: 16
- **Persisted**: 9
- **Rejected**: 7
- **Natural persist**: 6 (score ≥ threshold)
- **Override persist**: 3 (analytics, security, executive)

### ✅ Status Codes
- **201 Created**: 9 persisted cases
- **202 Accepted**: 7 rejected cases

### ✅ Override Behavior
- All 3 override cases must persist
- Override flag must be logged as `true`
- Override reason must be included

### ✅ Rejection Reasons
- All 7 rejected cases must include `reason: "score_below_threshold"`

### ✅ Scoring Latency
- **P95 < 200ms** for scoring path
- Individual scoring latency should be 120-180ms

## Test Suite Validation

Run all unit tests to verify:

```bash
python3 -m unittest tests.evals.test_pareto_gate -v
```

Expected: **32 tests, all passing**

### Test Classes
1. **TestParetoGateSuite** (6 tests): Suite structure validation
2. **TestPersistenceBehavior** (4 tests): Threshold logic
3. **TestOverrideBehavior** (5 tests): Override mechanisms
4. **TestStatusCodes** (3 tests): HTTP response codes
5. **TestMetricsCounting** (3 tests): Metrics accuracy
6. **TestScoringLatency** (3 tests): Performance budgets
7. **TestParetoValidation** (4 tests): End-to-end validation
8. **TestAcceptanceCriteria** (3 tests): Acceptance criteria verification

## Integration with Harness

The harness (`evals/run.py`) includes Pareto-specific logic:

### EvalResult Fields
```python
@dataclass
class EvalResult:
    # Pareto gate metrics
    pareto_score: float = 0.0
    pareto_threshold: float = 0.65
    persisted: bool = False
    expected_persisted: bool = False
    override_enabled: bool = False
    override_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    scoring_latency_ms: float = 0.0
```

### Console Output
For each Pareto case:
```
Score: 0.870, Threshold: 0.650, Persisted: ✓, Scoring: 145.0ms
Score: 0.470, Threshold: 0.650, Persisted: ✓ [OVERRIDE: analytics_priority], Scoring: 138.0ms
Score: 0.570, Threshold: 0.650, Persisted: ✗ (reason: score_below_threshold), Scoring: 132.0ms
```

## Troubleshooting

### All Cases Failing
- Verify `POST /hypotheses/propose` endpoint exists
- Check that response includes `persisted`, `score`, `threshold` fields
- Ensure status codes are 201 (persisted) or 202 (rejected)

### Override Cases Failing
- Verify override detection in request
- Check that `override: true` is logged in response
- Ensure override reason is included

### Latency Budget Exceeded
- Check scoring path performance
- Verify timing includes only scoring, not full request
- Target: individual scoring < 180ms, p95 < 200ms

### Metrics Mismatch
- Verify total count: 16 cases
- Check persisted count: 9 (6 natural + 3 override)
- Verify rejected count: 7

## Next Steps

After successful suite execution:

1. **Verify acceptance criteria** (100% match rate)
2. **Check metrics** (correct persisted/rejected counts)
3. **Validate latency** (p95 scoring < 200ms)
4. **Review logs** for override behavior
5. **Document findings** in test report
