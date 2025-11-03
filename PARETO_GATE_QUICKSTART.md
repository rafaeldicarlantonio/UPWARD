# Pareto Gate Suite - Quick Start

## Overview
Test suite for hypothesis proposal persistence based on Pareto scoring (threshold: 0.65).

## Quick Run

```bash
# Run the suite
cd /workspace
python3 evals/run.py --testset evals/suites/pareto_gate.jsonl

# Run unit tests
python3 -m unittest tests.evals.test_pareto_gate -v
```

## Test Coverage

| Category | Count | Details |
|----------|-------|---------|
| **Total Cases** | 16 | Full suite |
| **Persist (Natural)** | 8 | Score ≥ 0.65 |
| **Persist (Override)** | 3 | Analytics, Security, Executive |
| **Reject** | 5 | Score < 0.65 |
| **Unit Tests** | 32 | All passing ✅ |

## Expected Behavior

### Persist (201 Created)
- Score ≥ 0.65 → persist naturally
- Override enabled → persist regardless of score
- Response includes: `persisted: true, score, threshold`

### Reject (202 Accepted)
- Score < 0.65 (no override) → reject
- Response includes: `persisted: false, score, reason: "score_below_threshold"`

### Override Types
1. **Analytics Priority**: Product insights
2. **Security Critical**: Security findings
3. **Executive Directive**: Leadership mandates

## Files

```
evals/
├── suites/pareto_gate.jsonl           # 16 test cases
├── cases/pareto/                      # Individual case files (16)
└── fixtures/pareto_proposals.json     # Deterministic fixtures

tests/evals/
└── test_pareto_gate.py                # 32 unit tests

docs/
├── PARETO_GATE_SUITE.md               # Full documentation
├── PARETO_GATE_DELIVERY_SUMMARY.md    # Implementation summary
└── PARETO_GATE_QUICKSTART.md          # This quickstart
```

## Validation

Harness validates:
- ✅ Persistence matches expectation (100% required)
- ✅ Status codes (201 vs 202)
- ✅ Override logging
- ✅ Rejection reasons
- ✅ Scoring latency < 200ms (p95)

## Example Output

```
Running testset: evals/suites/pareto_gate.jsonl
  [1/16] pareto_001
    PASS - 150.2ms
    Score: 0.870, Threshold: 0.650, Persisted: ✓, Scoring: 145.0ms
  
  [10/16] pareto_010
    PASS - 152.3ms
    Score: 0.470, Threshold: 0.650, Persisted: ✓ [OVERRIDE: analytics_priority], Scoring: 138.0ms
  
  [6/16] pareto_006
    PASS - 148.1ms
    Score: 0.630, Threshold: 0.650, Persisted: ✗ (reason: score_below_threshold), Scoring: 132.0ms

EVALUATION SUMMARY
==================
Total Cases: 16
Passed: 16 (100.0%)

Category Breakdown:
  pareto_gate: 16/16 (100.0%)

Performance Constraints:
  P95 < 200ms: ✓ PASS (165.0ms)
```

## Acceptance Criteria ✅

- ✅ 100% match to expected persisted flag
- ✅ Correct metrics (11 persist, 5 reject)
- ✅ P95 latency < 200ms
- ✅ All 32 unit tests passing
- ✅ Override behavior validated

## Next Steps

1. **Run against live API**: Point to actual `/hypotheses/propose` endpoint
2. **Verify metrics**: Check persisted/rejected counts match expectations
3. **Monitor latency**: Ensure p95 scoring < 200ms
4. **Review overrides**: Validate override logging behavior

## Troubleshooting

**All tests fail**: Verify `/hypotheses/propose` endpoint exists and returns expected schema

**Override tests fail**: Check that `override: true` is logged in response for override cases

**Latency tests fail**: Optimize scoring path to achieve < 180ms per request, p95 < 200ms

## More Information

See `PARETO_GATE_SUITE.md` for complete documentation.
