# Role Variant Test Cases Documentation

## Overview

Role variant test cases verify that RBAC (Role-Based Access Control) and redaction systems maintain correctness across different permission levels. Each test case is duplicated with two role variants:

- **General Role**: Public/limited access with redaction applied
- **Pro/Researcher Role**: Full access with no redaction

## Purpose

The role variant system ensures that:

1. **Redaction doesn't break correctness**: General users get correct answers despite redacted content
2. **Both roles retrieve same evidence**: Core functionality is consistent regardless of role
3. **Differences are expected and documented**: Redaction behavior is predictable
4. **RBAC doesn't interfere with evaluation**: Test suite works for all roles

## Directory Structure

```
evals/cases/
├── implicate_general/          # General role implicate lift cases
│   ├── case_001_attention_to_bert_general.json
│   ├── case_003_embeddings_to_rag_general.json
│   └── case_006_scaling_to_emergent_general.json
├── implicate_pro/              # Pro role implicate lift cases
│   ├── case_001_attention_to_bert_pro.json
│   ├── case_003_embeddings_to_rag_pro.json
│   └── case_006_scaling_to_emergent_pro.json
├── contradictions_general/     # General role contradiction cases
│   ├── case_001_climate_trends_general.json
│   └── case_003_ai_employment_general.json
└── contradictions_pro/         # Pro role contradiction cases
    ├── case_001_climate_trends_pro.json
    └── case_003_ai_employment_pro.json
```

## Test Case Pairs

### Implicate Lift Cases

#### 1. Attention → BERT (case_001)

**Query**: "How does attention mechanism relate to BERT's contextual understanding?"

**General Role**:
- ID: `implicate_001_general`
- Role: `general`
- Redaction Expected: ✓ Yes
- Expected Sources: `doc_transformer_003`, `doc_bert_004`
- Rationale: Redacted content should not prevent bridging attention mechanism to BERT

**Pro Role**:
- ID: `implicate_001_pro`
- Role: `researcher`
- Redaction Expected: ✗ No
- Expected Sources: `doc_transformer_003`, `doc_bert_004`
- Rationale: Full context access to validate same retrieval as general role

**Expected Behavior**:
- Both roles should retrieve same documents
- General role may have redacted text in response
- Pro role gets full proprietary details
- Core understanding (attention → BERT) preserved in both

---

#### 2. Embeddings → RAG (case_003)

**Query**: "How do semantic embeddings enable retrieval systems?"

**General Role**:
- ID: `implicate_003_general`
- Role: `general`
- Redaction Expected: ✓ Yes
- Expected Sources: `doc_embedding_008`, `doc_vector_012`, `doc_rag_011`
- Rationale: Redaction of implementation details should not break understanding of embeddings → RAG pipeline

**Pro Role**:
- ID: `implicate_003_pro`
- Role: `researcher`
- Redaction Expected: ✗ No
- Expected Sources: `doc_embedding_008`, `doc_vector_012`, `doc_rag_011`
- Rationale: Full access to embedding and vector database internals

**Expected Behavior**:
- Both roles understand the pipeline: embeddings → vector search → retrieval
- General role gets conceptual explanation
- Pro role gets implementation specifics
- Same documents retrieved

---

#### 3. Scaling → Emergent (case_006)

**Query**: "How does scaling language models lead to emergent capabilities?"

**General Role**:
- ID: `implicate_006_general`
- Role: `general`
- Redaction Expected: ✓ Yes
- Expected Sources: `doc_scaling_015`, `doc_emergent_016`
- Rationale: Sensitive model details redacted, core relationship preserved

**Pro Role**:
- ID: `implicate_006_pro`
- Role: `researcher`
- Redaction Expected: ✗ No
- Expected Sources: `doc_scaling_015`, `doc_emergent_016`
- Rationale: Full access to scaling laws and emergent behavior data

**Expected Behavior**:
- Both roles understand scaling → emergent capabilities relationship
- General role: redacted proprietary model architectures
- Pro role: full model specifications
- Same core documents

---

### Contradiction Detection Cases

#### 1. Climate Trends (case_001)

**Query**: "What are the recent global temperature trends?"

**General Role**:
- ID: `contradiction_001_general`
- Role: `general`
- Redaction Expected: ✓ Yes
- Expected Contradictions: `global_warming` (doc_climate_warming_001 vs doc_climate_cooling_002)
- Expected Badge: ✓ Yes

**Pro Role**:
- ID: `contradiction_001_pro`
- Role: `researcher`
- Redaction Expected: ✗ No
- Expected Contradictions: `global_warming` (doc_climate_warming_001 vs doc_climate_cooling_002)
- Expected Badge: ✓ Yes

**Expected Behavior**:
- Both roles detect the contradiction
- Both get contradiction badge
- General role: redacted proprietary climate models
- Pro role: full model outputs
- Contradiction detection works regardless of redaction

---

#### 2. AI Employment (case_003)

**Query**: "How will AI impact employment rates?"

**General Role**:
- ID: `contradiction_003_general`
- Role: `general`
- Redaction Expected: ✓ Yes
- Expected Contradictions: `ai_employment` (doc_ai_jobs_positive_003 vs doc_ai_jobs_negative_004)
- Expected Badge: ✓ Yes

**Pro Role**:
- ID: `contradiction_003_pro`
- Role: `researcher`
- Redaction Expected: ✗ No
- Expected Contradictions: `ai_employment` (doc_ai_jobs_positive_003 vs doc_ai_jobs_negative_004)
- Expected Badge: ✓ Yes

**Expected Behavior**:
- Both roles see conflicting employment predictions
- Contradiction badge shown to both
- General role: redacted company-specific analyses
- Pro role: full employment forecast data

---

## Test Case Schema

### Required Fields

All role variant test cases include:

```json
{
  "id": "unique_case_id_with_role_suffix",
  "query": "The test query",
  "category": "implicate_lift | contradictions | external_compare | pareto_gate",
  "role": "general | researcher",
  "redaction_expected": true | false,
  "rationale": "Explanation of role-specific expectations"
}
```

### Category-Specific Fields

**Implicate Lift**:
```json
{
  "expected_source_ids": ["doc_id_1", "doc_id_2"],
  "expected_in_top_k": 8,
  "max_latency_ms": 500,
  "legacy_should_miss": true
}
```

**Contradictions**:
```json
{
  "expected_contradictions": [
    {
      "subject": "topic",
      "claim_a_source": "doc_id_a",
      "claim_b_source": "doc_id_b"
    }
  ],
  "expected_badge": true,
  "max_packing_latency_ms": 550
}
```

---

## Running Role Variant Tests

### Run All Role Variant Tests

```bash
python3 -m unittest tests.evals.test_role_variants -v
```

### Run Role Variant Suite

```bash
python3 evals/run.py --testset evals/suites/role_variants.jsonl
```

### Run Specific Role

```bash
# General role only
python3 evals/run.py --testset evals/suites/role_variants.jsonl | grep general

# Pro role only
python3 evals/run.py --testset evals/suites/role_variants.jsonl | grep pro
```

---

## Expected Differences

### Content Differences

| Aspect | General Role | Pro/Researcher Role |
|--------|--------------|---------------------|
| **Redaction** | Applied | Not applied |
| **Proprietary Details** | Redacted | Full access |
| **Model Specifications** | Hidden | Visible |
| **Internal Metrics** | Limited | Complete |
| **Source Code** | Abstracted | Full code |

### Behavioral Invariants

These should be **identical** across roles:

1. **Retrieved Documents**: Same source IDs in top-k
2. **Contradiction Detection**: Same contradictions found
3. **Badge Display**: Same badges shown
4. **Answer Correctness**: Semantically equivalent answers
5. **Latency**: Similar performance characteristics

### Acceptable Variances

These **may differ** between roles:

1. **Response Length**: Pro responses may be longer
2. **Detail Level**: Pro gets more specific information
3. **Technical Depth**: Pro sees implementation details
4. **Citation Text**: General may have `[REDACTED]` markers
5. **Debug Info**: Pro may see internal metrics

---

## Validation Checklist

When creating or reviewing role variant pairs:

- [ ] Both cases have same `query`
- [ ] Both cases have same `expected_source_ids`
- [ ] Both cases have same `expected_contradictions` (if applicable)
- [ ] General role has `redaction_expected: true`
- [ ] Pro role has `redaction_expected: false`
- [ ] IDs differ by `_general` vs `_pro` suffix
- [ ] Roles are `general` vs `researcher`
- [ ] Rationales explain role-specific expectations
- [ ] Both cases in correct directories

---

## Common Issues

### Issue: General role fails but pro passes

**Cause**: Redaction broke required information

**Solution**: 
1. Check if expected sources are still retrievable
2. Verify redaction policy doesn't hide critical concepts
3. May need to adjust redaction rules or test expectations

### Issue: Both roles fail

**Cause**: Underlying functionality issue, not role-related

**Solution**:
1. Debug with pro role first (no redaction complexity)
2. Fix core retrieval/contradiction detection
3. Re-test both roles

### Issue: Pro role gets redaction

**Cause**: Role not being passed correctly

**Solution**:
1. Verify `role` field in test case JSON
2. Check eval runner passes role to API
3. Confirm RBAC middleware respects role

### Issue: Neither role gets expected redaction behavior

**Cause**: Mock responses in tests don't match production

**Solution**:
1. Update mock responses in tests
2. Add `redacted: true/false` field to mock
3. Verify test expectations match actual system behavior

---

## Future Enhancements

1. **Admin Role**: Add admin role variant with full system access
2. **Anonymous Role**: Add anonymous/public role with maximum redaction
3. **Custom Roles**: Support team-specific role variants
4. **Redaction Metrics**: Track redaction impact on quality scores
5. **Role Transitions**: Test role upgrade/downgrade scenarios

---

## References

- **RBAC Implementation**: See `RBAC_COMPLETE_SYSTEM_SUMMARY.md`
- **Redaction System**: See `REDACTION_IMPLEMENTATION.md`
- **Role Middleware**: See `ROLE_MIDDLEWARE_IMPLEMENTATION.md`
- **Test Suite Design**: See `evals/config.yaml`

---

## Summary

Role variant test cases ensure that:

✅ **Correctness is maintained** across permission levels
✅ **Redaction doesn't break** core functionality  
✅ **Both roles get** same evidence/contradictions
✅ **Differences are documented** and expected
✅ **RBAC works** as designed in production

All role variant tests should pass, confirming that the system provides correct answers regardless of access level while properly applying redaction where expected.
