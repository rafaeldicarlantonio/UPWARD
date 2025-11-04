# Reviewer Time Budget - Quick Reference

**TL;DR**: Reviewer enforces 500ms budget. Fast path includes review, slow path skips with timeout flag. Never blocks beyond budget.

---

## What It Does

Answer reviewer with time budget enforcement:

- **Budget enforcement**: Default 500ms deadline
- **Deadline cancellation**: Terminates review if budget exceeded
- **Skip annotation**: Marks `skipped=true` with reason
- **Fast path**: Includes full review with scores
- **Slow path**: Returns quickly with skip flag
- **Circuit breaker**: Integrated failure protection
- **Graceful degradation**: Never fails, always returns

---

## Quick Start

### 1. Basic Usage

```python
from core.reviewer import AnswerReviewer

reviewer = AnswerReviewer()

# Review answer (500ms budget by default)
result = reviewer.review_answer(
    answer="This is a detailed answer...",
    context={"source": "research"},
    query="What is X?"
)

# Check result
if result.skipped:
    print(f"Skipped: {result.skip_reason}")
else:
    print(f"Score: {result.score}, Confidence: {result.confidence}")
```

### 2. Handle Skipped Reviews

```python
result = reviewer.review_answer(answer)

if result.skipped:
    # Use default or skip quality check
    logger.warning(f"Review skipped: {result.skip_reason}")
    default_score = 0.7
else:
    # Use actual score
    if result.score < 0.5:
        logger.warning("Low quality answer")
```

### 3. Convenience Function

```python
from core.reviewer import review_answer_with_budget

# Uses global reviewer instance
result = review_answer_with_budget(
    answer="Answer text",
    context={"doc": "123"},
    query="User query"
)
```

---

## Configuration

### Environment Variables

```bash
# Enable reviewer (default: true)
export PERF_REVIEWER_ENABLED=true

# Set budget in milliseconds (default: 500)
export PERF_REVIEWER_BUDGET_MS=500
```

### Custom Budget

```python
# Low latency (300ms)
config = {"PERF_REVIEWER_BUDGET_MS": 300}
reviewer = AnswerReviewer(config=config)

# High quality (1000ms)
config = {"PERF_REVIEWER_BUDGET_MS": 1000}
reviewer = AnswerReviewer(config=config)
```

---

## ReviewResult Format

### When NOT Skipped (Fast Path)

```python
result = reviewer.review_answer("Good answer")

# Result object
{
    "skipped": False,
    "score": 0.85,
    "confidence": 0.9,
    "flags": {"quality": "high"},
    "details": {"answer_length": 150},
    "latency_ms": 120.0,
    "skip_reason": None
}

# to_dict() for API
{
    "skipped": false,
    "score": 0.85,
    "confidence": 0.9,
    "flags": {"quality": "high"},
    "details": {"answer_length": 150},
    "latency_ms": 120.0
}
```

### When Skipped (Slow Path)

```python
result = reviewer.review_answer("Slow review...")

# Result object
{
    "skipped": True,
    "skip_reason": "timeout_exceeded: 500ms",
    "score": None,
    "confidence": None,
    "flags": {},
    "details": {},
    "latency_ms": 520.0
}

# to_dict() for API
{
    "skipped": true,
    "skip_reason": "timeout_exceeded: 500ms",
    "latency_ms": 520.0
    # Note: score/confidence/flags excluded
}
```

---

## Skip Reasons

| Reason | Description |
|--------|-------------|
| `reviewer_disabled` | Reviewer disabled via config |
| `circuit_breaker_open` | Circuit breaker is open (too many failures) |
| `timeout_exceeded: {budget}ms` | Review exceeded time budget |
| `error: {exception}` | Review encountered an error |

---

## Common Patterns

### 1. Always Include Review in Response

```python
result = reviewer.review_answer(answer)

# Include in API response
response = {
    "answer": answer_text,
    "review": result.to_dict(),  # Always include
    ...
}

# Client can check if skipped
if response["review"]["skipped"]:
    # Handle skipped case
    pass
```

### 2. Use Default Score When Skipped

```python
result = reviewer.review_answer(answer)

if result.skipped:
    score = 0.7  # Default score
else:
    score = result.score

# Use score for ranking/filtering
if score < 0.5:
    logger.warning("Low quality answer")
```

### 3. Log Skip Reasons

```python
result = reviewer.review_answer(answer)

if result.skipped:
    logger.warning(
        "Review skipped",
        extra={
            "reason": result.skip_reason,
            "latency_ms": result.latency_ms
        }
    )
```

### 4. Monitor Skip Rate

```python
from core.metrics import get_counter

skipped = get_counter("reviewer.skipped")
success = get_counter("reviewer.success")
total = skipped + success

skip_rate = skipped / total if total > 0 else 0

if skip_rate > 0.2:
    alert("High review skip rate", skip_rate=skip_rate)
```

---

## API Integration

### FastAPI Example

```python
from fastapi import APIRouter
from core.reviewer import review_answer_with_budget

router = APIRouter()

@router.post("/answer")
def generate_answer(request: AnswerRequest):
    # Generate answer
    answer = generate_answer_text(request.query)
    
    # Review answer with budget
    review = review_answer_with_budget(
        answer=answer,
        context={"query": request.query},
        query=request.query
    )
    
    # Return answer with review
    return {
        "answer": answer,
        "review": review.to_dict()
    }
```

### Response Example

**Fast path (review completed)**:
```json
{
    "answer": "Quantum computing is...",
    "review": {
        "skipped": false,
        "score": 0.88,
        "confidence": 0.92,
        "flags": {"quality": "high"},
        "latency_ms": 180
    }
}
```

**Slow path (review skipped)**:
```json
{
    "answer": "Quantum computing is...",
    "review": {
        "skipped": true,
        "skip_reason": "timeout_exceeded: 500ms",
        "latency_ms": 520
    }
}
```

---

## Metrics

### Counters

- `reviewer.skipped{reason}` - Skipped reviews
- `reviewer.success{within_budget}` - Successful reviews
- `reviewer.error{error_type}` - Review errors

### Histograms

- `reviewer.latency_ms{result}` - Review latency

### Prometheus Queries

```promql
# Skip rate
rate(reviewer_skipped_total[5m]) / 
    (rate(reviewer_skipped_total[5m]) + rate(reviewer_success_total[5m]))

# Timeout rate
rate(reviewer_skipped_total{reason="timeout"}[5m])

# Budget compliance
rate(reviewer_success_total{within_budget="true"}[5m]) / 
    rate(reviewer_success_total[5m])

# Latency p95
histogram_quantile(0.95, rate(reviewer_latency_ms_bucket[5m]))
```

---

## Troubleshooting

### Problem: High skip rate

**Check configuration**:
```python
reviewer = AnswerReviewer()
print(f"Enabled: {reviewer.is_enabled()}")
print(f"Budget: {reviewer.get_budget_ms()}ms")
```

**Solutions**:
```bash
# Enable reviewer
export PERF_REVIEWER_ENABLED=true

# Increase budget
export PERF_REVIEWER_BUDGET_MS=1000
```

### Problem: Reviews timing out

**Symptom**: Most reviews skipped with timeout

**Check budget**:
```bash
echo $PERF_REVIEWER_BUDGET_MS
```

**Solutions**:
- Increase budget: `PERF_REVIEWER_BUDGET_MS=1000`
- Optimize review logic
- Check LLM service latency

### Problem: Circuit breaker open

**Symptom**: Reviews skipped with "circuit_breaker_open"

**Check state**:
```python
reviewer = AnswerReviewer()
state = reviewer.circuit_breaker.get_state()
print(f"Circuit state: {state}")
```

**Solutions**:
- Wait for cooldown (60s)
- Check LLM service health
- Reset circuit (testing only): `reviewer.circuit_breaker.reset()`

---

## Testing

### Unit Tests

```bash
# Run all reviewer tests
python3 -m unittest tests.perf.test_reviewer_budget -v
```

Expected: **21/21 tests passing**

### Integration Test

```python
#!/usr/bin/env python3
"""Test reviewer budget enforcement."""

from core.reviewer import AnswerReviewer
from core.circuit import reset_all_circuit_breakers
import time

def test_reviewer_budget():
    reset_all_circuit_breakers()
    
    # Fast review (within budget)
    config = {"PERF_REVIEWER_BUDGET_MS": 500}
    reviewer = AnswerReviewer(config=config)
    
    result = reviewer.review_answer("Good answer with detail")
    assert not result.skipped
    assert result.score is not None
    print(f"✅ Fast path: score={result.score}")
    
    # Slow review (exceeds budget) - mock with patch
    from unittest.mock import patch
    def slow_review(*args, **kwargs):
        time.sleep(0.6)
        return None
    
    config = {"PERF_REVIEWER_BUDGET_MS": 100}
    reviewer = AnswerReviewer(config=config)
    
    with patch.object(reviewer, '_perform_review', side_effect=slow_review):
        result = reviewer.review_answer("Test")
    
    assert result.skipped
    assert "timeout" in result.skip_reason.lower()
    print(f"✅ Slow path: skipped={result.skipped}")

if __name__ == "__main__":
    test_reviewer_budget()
```

### Smoke Test

```bash
python3 << 'EOF'
from core.reviewer import AnswerReviewer, ReviewResult

# Create reviewer
reviewer = AnswerReviewer()

# Check configuration
assert reviewer.is_enabled()
assert reviewer.get_budget_ms() == 500

# Test review
result = reviewer.review_answer("Test answer")
assert isinstance(result, ReviewResult)
assert hasattr(result, 'skipped')

print("✅ Smoke test passed")
EOF
```

---

## Best Practices

### ✅ DO

- Always check `result.skipped` before using scores
- Include review in API responses
- Log skip reasons for debugging
- Monitor skip rate
- Set budget based on latency requirements
- Handle skipped reviews gracefully

### ❌ DON'T

- Don't assume review always completes
- Don't ignore skip reasons
- Don't set budget too low (<100ms)
- Don't fail request if review skipped
- Don't call reviewer in critical path if unavoidable

---

## Examples

### Example 1: Basic Review

```python
from core.reviewer import AnswerReviewer

reviewer = AnswerReviewer()
result = reviewer.review_answer("This is a good answer")

if result.skipped:
    print(f"Skipped: {result.skip_reason}")
else:
    print(f"Score: {result.score}")
    if result.flags:
        print(f"Flags: {result.flags}")
```

### Example 2: With Context

```python
result = reviewer.review_answer(
    answer="Detailed answer...",
    context={
        "source": "research_paper",
        "confidence": 0.95
    },
    query="What is quantum entanglement?"
)
```

### Example 3: Conditional Logic

```python
result = reviewer.review_answer(answer)

if result.skipped:
    # Use default behavior
    quality = "unknown"
else:
    # Use review score
    if result.score >= 0.8:
        quality = "high"
    elif result.score >= 0.6:
        quality = "medium"
    else:
        quality = "low"
```

### Example 4: API Response

```python
@router.post("/chat")
def chat(request: ChatRequest):
    answer = generate_answer(request.prompt)
    review = review_answer_with_budget(answer)
    
    return {
        "answer": answer,
        "review": review.to_dict(),
        "metadata": {
            "reviewed": not review.skipped,
            "review_latency_ms": review.latency_ms
        }
    }
```

---

## Related Docs

- **Implementation Details**: `REVIEWER_BUDGET_IMPLEMENTATION.md`
- **Circuit Breakers**: `CIRCUIT_BREAKER_QUICKSTART.md`
- **Performance Flags**: `PERF_FLAGS_QUICKSTART.md`

---

## Summary

**Reviewer time budget provides controlled quality checking**:

- ✅ Enforces 500ms budget (configurable)
- ✅ Deadline and cancellation
- ✅ Skip annotation with reasons
- ✅ Fast path includes review
- ✅ Slow path returns quickly
- ✅ Circuit breaker integration
- ✅ Never blocks beyond budget

**Key Benefit**: Answer quality checking without risking request latency. Reviews that would exceed budget are skipped gracefully with clear annotation.

**Production Ready**: 21/21 tests passing, comprehensive timeout handling, robust error handling, integrated with circuit breakers.
