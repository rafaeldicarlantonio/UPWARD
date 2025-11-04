# External Compare Suite

## Overview

A comprehensive test suite for evaluating external source comparison with parity validation, policy compliance, and no-persistence guarantees. Tests dual-mode execution (external OFF vs ON) to ensure proper handling of external sources.

## Files Created

### Suite Definition
- **`evals/suites/external_compare.jsonl`** - 10 test cases in JSONL format

### Test Cases (Individual Files)
- **`evals/cases/external/case_001_redundant_python.json`** through **`case_010_no_external_match.json`**
- Each case contains: query, parity expectation, policy expectation, external scenario

### Fixtures
- **`evals/fixtures/external_compare_corpus.json`** - 8 internal documents + external source definitions

### Tests
- **`tests/evals/test_external_compare.py`** - 25 comprehensive unit tests

## Test Cases Summary

The suite contains **10 dual-mode test cases** across different scenarios:

### Parity Cases (5 cases) - Should have identical results OFF vs ON
1. **redundant_python** - External duplicates internal Python docs
2. **redundant_ml** - External duplicates internal ML docs
3. **redundant_sql** - External duplicates internal SQL docs
4. **low_quality** - External is spam/low-quality (rejected)
5. **no_external_match** - No external source found

### Policy Divergence Cases (5 cases) - Policy-compliant differences
6. **additive_hooks** - External adds React hooks info (prefer_internal)
7. **additive_compose** - External adds Docker Compose info (prefer_internal)
8. **additive_helm** - External adds Kubernetes Helm info (prefer_internal)
9. **contradiction_git** - External contradicts Git practices (abstain)
10. **contradiction_rest** - External contradicts REST guidance (prefer_internal)

## Test Case Structure

```json
{
  "id": "external_001",
  "query": "What are the key features of Python programming?",
  "category": "external_compare",
  "expected_parity": true,
  "expected_policy": null,
  "external_scenario": "redundant",
  "internal_sources": ["internal_python_001"],
  "external_source": "ext_python_wiki",
  "rationale": "External source provides redundant information..."
}
```

### Required Fields
- **id**: Unique identifier
- **query**: Natural language question
- **category**: Always "external_compare"
- **expected_parity**: true if OFF and ON should match
- **expected_policy**: Tiebreak policy ("prefer_internal", "abstain", "reject", or null)
- **external_scenario**: Type ("redundant", "additive", "contradictory", "low_quality", "no_match")
- **internal_sources**: Internal document IDs
- **external_source**: External source ID (or null)
- **rationale**: Explanation of test case

## External Scenarios

### 1. Redundant Externals
External provides same information as internal docs.
- **Expected**: Perfect parity (results identical)
- **Policy**: N/A (external adds nothing)

### 2. Additive Externals
External adds valuable information not in internal docs.
- **Expected**: Policy-compliant divergence
- **Policy**: prefer_internal (favor internal sources)

### 3. Contradictory Externals
External conflicts with internal information.
- **Expected**: Policy-compliant divergence
- **Policy**: abstain or prefer_internal

### 4. Low-Quality Externals
External is spam or unreliable.
- **Expected**: Parity (external rejected)
- **Policy**: reject

### 5. No External Match
No relevant external source found.
- **Expected**: Perfect parity
- **Policy**: N/A

## Assertions

### 1. Parity Checking (OFF vs ON)
```python
# Compare results from external OFF and ON modes
has_parity = (
    result_off["answer"] == result_on["answer"] and
    result_off["confidence"] == result_on["confidence"]
)
# For redundant externals: parity rate ≥80%
assert parity_rate >= 0.80
```

### 2. Policy Compliance
```python
# Validate tiebreak follows expected policy
actual_policy = decision["tiebreak"]
expected_policy = case["expected_policy"]
assert actual_policy == expected_policy
```

### 3. No Persistence (Zero Ingestion)
```python
# Check that external text is not persisted
citation_ids = [c["source_id"] for c in citations]
external_ingested = any("ext_" in cid for cid in citation_ids)
assert external_ingested == False
# Across all cases: ingestion rate = 0.0
```

## Running the Suite

### Dual-Mode Execution
```bash
# Run with external compare OFF
python3 evals/run.py --testset evals/suites/external_compare.jsonl --pipeline off --output-json off_results.json

# Run with external compare ON
python3 evals/run.py --testset evals/suites/external_compare.jsonl --pipeline on --output-json on_results.json

# Compare results
python3 scripts/compare_external_results.py off_results.json on_results.json
```

### Run Unit Tests
```bash
# Run all external compare tests
python3 -m unittest tests.evals.test_external_compare -v

# Run specific test class
python3 -m unittest tests.evals.test_external_compare.TestParityChecking -v
```

## Success Criteria

### ✅ Acceptance Criteria Met

1. **Parity Rate**: ≥80% for redundant externals (OFF vs ON match)
   - Target: 100% for 5 parity cases
   - Validation: `test_parity_rate_above_threshold`

2. **Policy Compliance**: 100% for policy-divergence cases
   - Target: Tiebreak matches expected_policy
   - Validation: `test_policy_compliance_rate`

3. **Zero Ingestion**: 0.0% external text persistence
   - Target: No external source IDs in citations
   - Validation: `test_zero_ingestion_rate`

4. **Dual-Mode Execution**: Both modes run successfully
   - Target: All cases execute in both OFF and ON modes
   - Validation: `test_run_external_off_mode`, `test_run_external_on_mode`

## Expected Performance

### With External Compare OFF
- Uses only internal documents
- No external API calls
- Baseline behavior

### With External Compare ON - Redundant Externals (5 cases)
- External sources considered
- Results identical to OFF mode (parity)
- Zero external ingestion
- **Expected Parity Rate**: 100%

### With External Compare ON - Policy Divergence (5 cases)
- External sources add value or conflict
- Results diverge per policy
- Tiebreak follows expected_policy
- Zero external ingestion
- **Expected Policy Compliance**: 100%

### Overall Metrics
- **Parity Rate**: 100% (5/5 redundant cases)
- **Policy Compliance**: 100% (5/5 policy cases)
- **Ingestion Rate**: 0.0% (0/10 cases)

## Policy Actions

### prefer_internal
- Used when external adds value but internal is trusted
- Internal sources get priority in confidence/ranking
- Common for additive externals

### abstain
- Used when sources conflict significantly
- System abstains from definitive answer
- Common for contradictory externals

### reject
- Used for low-quality external sources
- External completely ignored
- Common for spam/unreliable externals

## Harness Integration

The harness now supports:

### Dual-Mode Execution
```python
# Run with pipeline="off" or pipeline="on"
result_off = runner.run_single_case(case, pipeline="off")
result_on = runner.run_single_case(case, pipeline="on")
```

### External Validation
```python
# Validates external usage and ingestion
external_used = data.get("external_used", False)
external_ingested = any("ext_" in cid for cid in citation_ids)
decision_tiebreak = data.get("decision", {}).get("tiebreak")

# Check policy compliance
if expected_policy and decision_tiebreak != expected_policy:
    passed = False
```

### Ingestion Detection
```python
# Checks citations for external source IDs
external_markers = ["ext_", "external"]
citation_ids = [c["source_id"] for c in citations]
has_external = any(marker in cid for marker in external_markers for cid in citation_ids)
```

### Console Output
```
[1/10] external_001
  PASS - 325.1ms
  External: ✗, Policy: N/A, No-Ingestion: ✓

[4/10] external_004
  PASS - 342.5ms
  External: ✓, Policy: prefer_internal, No-Ingestion: ✓
```

### JSON Report Fields
```json
{
  "case_id": "external_004",
  "external_mode": "on",
  "external_used": true,
  "external_sources": ["ext_react_hooks"],
  "external_ingested": false,
  "decision_tiebreak": "prefer_internal",
  "expected_parity": false,
  "expected_policy": "prefer_internal"
}
```

## Test Coverage

The test suite provides comprehensive coverage:

### Suite Structure (5 tests)
- ✅ Suite file exists
- ✅ Fixtures exist
- ✅ Suite has 10 cases
- ✅ All cases have required fields
- ✅ Parity cases identified

### Parity Checking (4 tests)
- ✅ Identical results have parity
- ✅ Different results no parity
- ✅ Calculate parity rate
- ✅ Parity rate above threshold

### Policy Compliance (5 tests)
- ✅ prefer_internal tiebreak
- ✅ abstain policy
- ✅ reject low-quality
- ✅ Validate policy compliance
- ✅ Policy compliance rate

### No Persistence (4 tests)
- ✅ No external text in sources
- ✅ No external source IDs
- ✅ Detect external ingestion
- ✅ Zero ingestion rate

### Dual-Mode Execution (3 tests)
- ✅ Run external OFF mode
- ✅ Run external ON mode
- ✅ Compare OFF vs ON results

### Success Metrics (4 tests)
- ✅ Calculate parity success rate
- ✅ Calculate policy success rate
- ✅ Overall success rate above threshold
- ✅ All metrics validation

**Total: 25 tests, all passing**

## Example Test Case Walkthrough

### Case: redundant_python (Parity Expected)

**Query**: "What are the key features of Python programming?"

**Internal Source**: internal_python_001 (Python basics)

**External Source**: ext_python_wiki (redundant Python info)

**Expected Behavior**:
- **External OFF**: Uses internal_python_001
- **External ON**: Considers ext_python_wiki but results identical
- **Parity**: ✅ Yes (results match)
- **Policy**: N/A (external adds nothing)
- **Ingestion**: ✅ Zero (no external text persisted)

### Case: additive_hooks (Policy Divergence Expected)

**Query**: "How do React hooks work?"

**Internal Source**: internal_react_003 (React basics)

**External Source**: ext_react_hooks (React hooks specifics)

**Expected Behavior**:
- **External OFF**: Uses internal_react_003 (general React)
- **External ON**: Considers ext_react_hooks (adds hooks info)
- **Parity**: ❌ No (results may differ)
- **Policy**: prefer_internal (favor internal source)
- **Ingestion**: ✅ Zero (no external text persisted)

**Validation**:
```python
assert result_on["external_used"] == True
assert result_on["decision"]["tiebreak"] == "prefer_internal"
assert not has_external_ingestion(result_on["citations"])
```

## Next Steps

The suite is production-ready and can be:
1. **Run in CI/CD** for external compare regression testing
2. **Extended** with more external scenarios
3. **Used for policy validation** in production
4. **Integrated** with governance audits

## Summary

✅ **10 deterministic test cases** covering diverse external scenarios  
✅ **Dual-mode execution** (external OFF and ON)  
✅ **Parity validation** (≥80% for redundant externals)  
✅ **Policy compliance** (100% tiebreak adherence)  
✅ **No-persistence guarantee** (zero ingestion detected)  
✅ **25 comprehensive tests** validating all aspects  
✅ **Harness integration** with dual-mode support  
✅ **Complete documentation** with examples
