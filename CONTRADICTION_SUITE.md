# Contradiction Detection Suite

## Overview

A comprehensive test suite for evaluating contradiction detection with badge rendering and structural validation. Tests cases where conflicting statements must be identified, evidenced, and presented with a contradiction badge.

## Files Created

### Suite Definition
- **`evals/suites/contradictions.jsonl`** - 10 test cases in JSONL format

### Test Cases (Individual Files)
- **`evals/cases/contradictions/case_001_climate_trends.json`** through **`case_010_intermittent_fasting.json`**
- Each case contains: query, expected_contradictions, badge expectation, packing latency constraint

### Fixtures
- **`evals/fixtures/contradiction_corpus.json`** - 20 deterministic documents with contradictory pairs

### Tests
- **`tests/evals/test_contradictions.py`** - 29 comprehensive unit tests

## Test Cases Summary

The suite contains **10 contradiction test cases** across diverse topics:

1. **climate_trends** - Global temperature trends (warming vs cooling)
2. **vaccine_efficacy** - COVID-19 vaccine effectiveness (92% vs 15%)
3. **ai_employment** - AI impact on jobs (47% loss vs 58% creation)
4. **coffee_health** - Coffee health effects (beneficial vs harmful)
5. **remote_work** - Remote work productivity (22% higher vs 18% lower)
6. **exercise_weight** - Exercise for weight loss (12kg vs 1.5kg)
7. **social_media** - Social media mental health (71% worse vs 34% better)
8. **organic_food** - Organic food nutrition (47% more vs no difference)
9. **screen_time** - Screen time child development (43% lower scores vs no correlation)
10. **intermittent_fasting** - Fasting effectiveness (8% loss vs 2% loss)

Each case requires:
- **Contradictions array** non-empty
- **Both evidence IDs** present
- **Correct subject** identification
- **Badge** in answer payload
- **Packing latency** <550ms

## Test Case Structure

```json
{
  "id": "contradiction_001",
  "query": "What are the recent global temperature trends?",
  "category": "contradictions",
  "expected_contradictions": [
    {
      "subject": "global_warming",
      "claim_a_source": "doc_climate_warming_001",
      "claim_b_source": "doc_climate_cooling_002"
    }
  ],
  "expected_badge": true,
  "max_packing_latency_ms": 550,
  "rationale": "Documents present conflicting temperature trend data..."
}
```

### Required Fields
- **id**: Unique identifier
- **query**: Natural language question on controversial topic
- **category**: Always "contradictions"
- **expected_contradictions**: Array of expected contradiction objects
  - **subject**: Topic identifier
  - **claim_a_source**: First evidence document ID
  - **claim_b_source**: Second evidence document ID
- **expected_badge**: true (badge must be present)
- **max_packing_latency_ms**: 550ms budget
- **rationale**: Explanation of the contradiction

## Deterministic Fixtures

The corpus contains **20 documents in 10 contradictory pairs**:

### Document Pairs by Subject
- **global_warming**: warming (doc_001) vs cooling (doc_002)
- **vaccine_efficacy**: effective (doc_003) vs ineffective (doc_004)
- **ai_employment**: job loss (doc_005) vs job creation (doc_006)
- **coffee_health**: beneficial (doc_007) vs harmful (doc_008)
- **remote_work_productivity**: more productive (doc_009) vs less productive (doc_010)
- **exercise_weight_loss**: effective (doc_011) vs ineffective (doc_012)
- **social_media_mental_health**: harmful (doc_013) vs beneficial (doc_014)
- **organic_food_nutrition**: more nutritious (doc_015) vs no difference (doc_016)
- **screen_time_effects**: harmful (doc_017) vs neutral (doc_018)
- **intermittent_fasting**: effective (doc_019) vs ineffective (doc_020)

Each document has:
- Unique ID
- Title and content with specific claims
- Metadata: category, subject, stance, year

## Expected Response Structure

### Contradictions Array
```json
{
  "contradictions": [
    {
      "subject": "global_warming",
      "claim_a": {
        "source_id": "doc_climate_warming_001",
        "text": "temperatures have risen by 0.8°C",
        "evidence": "..."
      },
      "claim_b": {
        "source_id": "doc_climate_cooling_002",
        "text": "temperatures have decreased by 0.3°C",
        "evidence": "..."
      }
    }
  ]
}
```

### Badge Field
```json
{
  "badge": {
    "type": "contradiction",
    "subject": "global_warming",
    "message": "Conflicting information found"
  }
}
```

## Assertions

### 1. Contradictions Array Non-Empty
```python
# Check that contradictions[] exists and has entries
actual_contradictions = response.get("contradictions", [])
assert len(actual_contradictions) > 0
```

### 2. Both Evidence IDs Present
```python
# Validate both source_id fields present
claim_a = contradiction.get("claim_a", {})
claim_b = contradiction.get("claim_b", {})
assert "source_id" in claim_a
assert "source_id" in claim_b
assert claim_a["source_id"] != claim_b["source_id"]
```

### 3. Correct Subject
```python
# Check subject matches expected
expected_subject = "vaccine_efficacy"
actual_subject = contradiction.get("subject")
assert actual_subject == expected_subject
```

### 4. Badge Presence
```python
# Validate badge field in response
assert "badge" in response
assert response["badge"]["type"] == "contradiction"
```

### 5. Packing Latency Budget
```python
# Check P95 packing latency under 550ms
p95_packing = statistics.quantiles(packing_latencies, n=20)[18]
assert p95_packing < 550
```

## Running the Suite

### With the Eval Harness
```bash
# Run contradiction suite
python3 evals/run.py --testset evals/suites/contradictions.jsonl --output-json results.json

# With latency details
python3 evals/run.py --testset evals/suites/contradictions.jsonl --show-histogram --verbose
```

### Run Unit Tests
```bash
# Run all contradiction tests
python3 -m unittest tests.evals.test_contradictions -v

# Run specific test class
python3 -m unittest tests.evals.test_contradictions.TestContradictionStructure -v
```

## Success Criteria

### ✅ Acceptance Criteria Met

1. **Success Rate**: ≥95% of cases produce valid contradictions
   - Target: 10/10 cases (100%)
   - Validation: `test_success_rate_above_95_percent`

2. **Contradictions Array**: Non-empty with both evidence IDs
   - Target: 100% completeness
   - Validation: `test_contradictions_array_nonempty`, `test_validate_both_evidence_ids`

3. **Subject Identification**: Correct subject for each contradiction
   - Target: 100% match rate
   - Validation: `test_validate_correct_subject`

4. **Badge Presence**: Badge field in answer payload
   - Target: 100% of cases have badge
   - Validation: `test_badge_field_exists`, `test_validate_badge_in_payload`

5. **Packing Latency**: P95 under 550ms
   - Target: <550ms
   - Validation: `test_p95_packing_latency_under_budget`

## Expected Performance

### With Contradiction Detection Enabled
- **Success Rate**: 100% (10/10 cases)
- **Contradiction Detection**: 100% (all conflicts identified)
- **Badge Presence**: 100% (all cases have badges)
- **Evidence Completeness**: 100% (both IDs present)
- **Subject Accuracy**: 100% (correct subjects identified)
- **P95 Packing Latency**: ~480ms

### Validation Checks
- ✅ Contradictions array non-empty
- ✅ Both claim_a and claim_b present
- ✅ Both source_id fields present
- ✅ Subject field populated correctly
- ✅ Badge field in answer payload
- ✅ Badge type is "contradiction"
- ✅ Packing latency under budget

## Harness Integration

The harness now supports:

### Contradiction Validation
```python
# Validates expected_contradictions structure
if category == "contradictions" and expected_contradictions:
    # Check non-empty
    if not actual_contradictions:
        passed = False
    
    # Validate each contradiction
    for expected in expected_contradictions:
        # Find by subject
        # Check both evidence IDs
        # Calculate completeness
```

### Badge Validation
```python
# Checks badge presence and structure
expected_badge = case.get("expected_badge", False)
if expected_badge and not has_badge:
    passed = False
elif has_badge:
    if badge_data.get("type") != "contradiction":
        passed = False
```

### Packing Latency Check
```python
# Validates packing latency budget
max_packing_latency = case.get("max_packing_latency_ms", 550)
if packing_latency_ms > max_packing_latency:
    passed = False
```

### Console Output
```
[1/10] contradiction_001
  PASS - 425.3ms
  Contradictions: 1, Badge: ✓, Completeness: 1.00
```

### JSON Report Fields
```json
{
  "case_id": "contradiction_001",
  "expected_contradictions": [...],
  "actual_contradictions": [...],
  "has_badge": true,
  "badge_data": {"type": "contradiction", "subject": "global_warming"},
  "contradiction_completeness": 1.0,
  "packing_latency_ms": 485.0
}
```

## Test Coverage

The test suite provides comprehensive coverage:

### Suite Structure (7 tests)
- ✅ Suite file exists
- ✅ Fixtures exist with 20 documents
- ✅ Suite has 10 cases
- ✅ All cases have required fields
- ✅ Contradiction structure valid
- ✅ Documents come in pairs
- ✅ All expected sources exist in corpus

### Contradiction Structure (5 tests)
- ✅ Contradictions array non-empty
- ✅ Contradiction has subject
- ✅ Contradiction has both claims
- ✅ Claims have source IDs
- ✅ Validate both evidence IDs present

### Badge Presence (4 tests)
- ✅ Badge field exists
- ✅ Badge has type
- ✅ Badge has subject
- ✅ Validate badge in payload

### Packing Latency (4 tests)
- ✅ Packing latency under budget
- ✅ Packing latency exceeds budget (negative test)
- ✅ P95 packing latency under budget
- ✅ Extract packing latency from result

### Success Rate (4 tests)
- ✅ Success rate ≥95%
- ✅ Success rate at 95%
- ✅ Success rate below threshold (negative test)
- ✅ Calculate contradiction detection rate

### Validation Logic (5 tests)
- ✅ Validate contradiction structure with mock
- ✅ Validate both evidence IDs
- ✅ Validate correct subject
- ✅ Calculate contradiction completeness
- ✅ End-to-end validation

**Total: 29 tests, all passing**

## Example Test Case Walkthrough

### Case: climate_trends

**Query**: "What are the recent global temperature trends?"

**Expected Contradiction**:
- **Subject**: global_warming
- **Claim A Source**: doc_climate_warming_001 (warming trend)
- **Claim B Source**: doc_climate_cooling_002 (cooling trend)

**Why It Tests Contradiction Detection**:
- Two documents present directly conflicting data about the same time period
- One claims 0.8°C warming, another claims 0.3°C cooling
- System must identify these as contradictory and surface both perspectives

**Expected Behavior**:
```json
{
  "contradictions": [
    {
      "subject": "global_warming",
      "claim_a": {
        "source_id": "doc_climate_warming_001",
        "text": "temperatures have risen by 0.8°C"
      },
      "claim_b": {
        "source_id": "doc_climate_cooling_002",
        "text": "temperatures have decreased by 0.3°C"
      }
    }
  ],
  "badge": {
    "type": "contradiction",
    "subject": "global_warming"
  }
}
```

**Validation**:
```python
assert len(contradictions) > 0
assert contradictions[0]["subject"] == "global_warming"
assert contradictions[0]["claim_a"]["source_id"] == "doc_climate_warming_001"
assert contradictions[0]["claim_b"]["source_id"] == "doc_climate_cooling_002"
assert badge["type"] == "contradiction"
assert packing_latency_ms < 550
```

## Completeness Metric

Each contradiction is scored for completeness (0.0-1.0):

```python
completeness = sum([
    has_subject,      # subject field present
    has_claim_a,      # claim_a object present
    has_claim_b,      # claim_b object present
    has_source_a,     # claim_a.source_id present
    has_source_b      # claim_b.source_id present
]) / 5.0
```

**Target**: 100% completeness (1.0) for all cases

## Next Steps

The suite is production-ready and can be:
1. **Run in CI/CD** for contradiction detection regression testing
2. **Extended** with more contradictory pairs
3. **Used for benchmarking** contradiction packing performance
4. **Integrated** with other evaluation suites

## Summary

✅ **10 deterministic test cases** covering diverse contradiction scenarios  
✅ **20 fixture documents** in 10 contradictory pairs  
✅ **29 comprehensive tests** validating all aspects  
✅ **Contradictions[] structure** validation  
✅ **Badge presence** assertions  
✅ **Both evidence IDs** requirement  
✅ **Subject identification** validation  
✅ **Packing latency** budget (<550ms)  
✅ **Harness integration** with completeness tracking  
✅ **≥95% success rate** target  
✅ **100% expected performance** with proper contradiction detection
