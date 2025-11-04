# Reviewer Budget - Quick Reference

## What It Does

Enforces time budgets on answer reviews, skips gracefully on timeout or circuit breaker open, and annotates results with skip reasons. Ensures reviews never block critical path responses.

## Quick Start

### 1. Review Answer

```python
from core.reviewer import review_answer_with_budget

# Review with automatic budget enforcement
result = review_answer_with_budget(
    answer="This is the answer text",
    context={"sources": ["doc1", "doc2"]},
    query="What is the question?"
)

# Check result
if result.skipped:
    print(f"Skipped: {result.skip_reason}")
else:
    print(f"Score: {result.score}")
    print(f"Confidence: {result.confidence}")
```

### 2. API Response Format

```python
# Convert to dict for API
response = {
    "answer": answer_text,
    "review": result.to_dict()
}

# When completed:
{
    "review": {
        "skipped": false,
        "score": 0.85,
        "confidence": 0.9,
        "flags": {"quality": "high"},
        "latency_ms": 120.0
    }
}

# When skipped:
{
    "review": {
        "skipped": true,
        "skip_reason": "timeout_exceeded: 500ms",
        "latency_ms": 510.0
    }
}
```

## Configuration

### Environment Variables

```bash
# Enable/disable
export PERF_REVIEWER_ENABLED=true       # Default: true

# Time budget
export PERF_REVIEWER_BUDGET_MS=500      # Default: 500ms
```

### Custom Config

```python
from core.reviewer import AnswerReviewer

# Create with custom config
reviewer = AnswerReviewer(config={
    "PERF_REVIEWER_ENABLED": True,
    "PERF_REVIEWER_BUDGET_MS": 300  # 300ms budget
})

result = reviewer.review_answer("Answer text")
```

## Skip Conditions

Review is skipped when:

1. **Disabled**
   ```bash
   PERF_REVIEWER_ENABLED=false
   ```
   - Skip reason: `reviewer_disabled`
   - Latency: <1ms

2. **Circuit Open**
   - Too many recent failures
   - Skip reason: `circuit_breaker_open`
   - Latency: <1ms

3. **Timeout**
   - Exceeds budget
   - Skip reason: `timeout_exceeded: 500ms`
   - Latency: ~budget duration

4. **Error**
   - Unexpected exception
   - Skip reason: `error: ExceptionType`
   - Latency: varies

## ReviewResult Fields

```python
@dataclass
class ReviewResult:
    skipped: bool              # True if review didn't complete
    skip_reason: Optional[str] # Reason for skip
    score: Optional[float]     # Quality score (0.0-1.0), None if skipped
    confidence: Optional[float] # Confidence level (0.0-1.0), None if skipped
    flags: Dict[str, Any]      # Review flags (quality issues, etc.)
    details: Dict[str, Any]    # Additional metadata
    latency_ms: float          # Review execution time
```

## Monitoring

### Check Skip Rate

```python
# Track skipped reviews
if result.skipped:
    metric.increment("reviews_skipped", tags={"reason": result.skip_reason})
```

### Alert on Circuit Open

```python
if result.skipped and "circuit_breaker" in result.skip_reason:
    alert_ops("Reviewer circuit breaker open - service may be down")
```

### Monitor Latency

```python
metric.histogram("review_latency_ms", result.latency_ms, tags={
    "skipped": str(result.skipped)
})
```

## Metrics

```python
# Success/failure
reviewer.success{within_budget="true"}
reviewer.skipped{reason="timeout"}
reviewer.error{error_type="TimeoutError"}

# Latency
reviewer.latency_ms{result="success"}
reviewer.latency_ms{result="timeout"}
reviewer.latency_ms{result="error"}

# Calls
reviewer.call{budgeted="true"}
```

## Troubleshooting

### Reviews Always Skip

**Possible causes**:
1. Reviewer disabled in config
2. Circuit breaker stuck open
3. Budget too short

**Solutions**:
```python
# Check config
reviewer = get_reviewer()
print(f"Enabled: {reviewer.is_enabled()}")
print(f"Budget: {reviewer.get_budget_ms()}ms")

# Check circuit
print(f"Circuit state: {reviewer.circuit_breaker.get_state()}")

# Increase budget
# In config: PERF_REVIEWER_BUDGET_MS=1000
```

### Reviews Timeout Frequently

**Possible causes**:
1. Budget too short for review complexity
2. Slow network/LLM
3. Large answer size

**Solutions**:
```bash
# Increase budget
export PERF_REVIEWER_BUDGET_MS=1000  # 1 second

# Or disable for testing
export PERF_REVIEWER_ENABLED=false
```

### Circuit Breaker Stuck Open

**Possible causes**:
1. Reviewer service down
2. Multiple consecutive failures
3. Network issues

**Solutions**:
```python
# Check health
from core.health import check_reviewer_health
health = check_reviewer_health()
print(f"Healthy: {health.is_healthy}, Error: {health.error}")

# Manual reset (caution!)
reviewer.circuit_breaker.reset()
```

## Best Practices

### 1. Always Check Skipped Flag

```python
result = review_answer_with_budget(answer)

if result.skipped:
    # Handle gracefully - answer still usable
    logger.info(f"Review skipped: {result.skip_reason}")
else:
    # Use review scores
    if result.score < 0.5:
        flag_for_review(answer)
```

### 2. Set Appropriate Budget

```python
# For interactive responses: tight budget
PERF_REVIEWER_BUDGET_MS=300

# For background processing: relaxed budget
PERF_REVIEWER_BUDGET_MS=2000

# For critical path: consider disabling
PERF_REVIEWER_ENABLED=false
```

### 3. Monitor Skip Reasons

```python
# Track distribution
skip_reasons = defaultdict(int)

for result in review_results:
    if result.skipped:
        skip_reasons[result.skip_reason] += 1

# Alert if timeout rate high
if skip_reasons["timeout"] > total * 0.1:
    alert("High timeout rate in reviews")
```

### 4. Graceful Degradation

```python
def get_answer_with_review(query):
    # Always return answer
    answer = generate_answer(query)
    
    # Try review, but don't block on it
    review = review_answer_with_budget(answer)
    
    return {
        "answer": answer,
        "review": review.to_dict(),
        "confidence": review.score if not review.skipped else None
    }
```

## API Integration

### Chat Endpoint

```python
@router.post("/chat")
def chat(request: ChatRequest):
    # Generate answer
    answer = orchestrate_answer(request.prompt)
    
    # Review with budget
    review = review_answer_with_budget(
        answer=answer.text,
        context={"sources": answer.sources},
        query=request.prompt
    )
    
    return ChatResponse(
        answer=answer.text,
        review=review.to_dict()
    )
```

### Background Jobs

```python
def review_historical_answers():
    """Review old answers with longer budget."""
    reviewer = AnswerReviewer(config={
        "PERF_REVIEWER_ENABLED": True,
        "PERF_REVIEWER_BUDGET_MS": 5000  # 5s budget for background
    })
    
    for answer in get_unreviewed_answers():
        result = reviewer.review_answer(answer.text)
        store_review(answer.id, result)
```

## Testing

### Unit Tests

```python
def test_skips_on_timeout():
    config = {"PERF_REVIEWER_BUDGET_MS": 100}
    reviewer = AnswerReviewer(config=config)
    
    # Mock slow review
    def slow_review(*args, **kwargs):
        time.sleep(0.2)
        return ReviewResult(score=0.8)
    
    with patch.object(reviewer, '_perform_review', side_effect=slow_review):
        result = reviewer.review_answer("Test")
    
    assert result.skipped == True
    assert "timeout" in result.skip_reason
```

### Integration Tests

```python
def test_chat_endpoint_with_review():
    response = client.post("/chat", json={
        "prompt": "What is the answer?"
    })
    
    assert response.status_code == 200
    data = response.json()
    
    assert "review" in data
    assert "skipped" in data["review"]
    
    if not data["review"]["skipped"]:
        assert "score" in data["review"]
```

## Performance Tips

1. **Cache reviews**: Same answer → cache result
2. **Batch processing**: Review multiple answers together (future)
3. **Progressive enhancement**: Start with fast heuristics, use LLM if within budget
4. **Async reviews**: Don't block response generation (future)

## Related

- `REVIEWER_BUDGET_DELIVERY_SUMMARY.md` - Full delivery report
- `CIRCUIT_BREAKER_QUICKSTART.md` - Circuit breaker details
- `core/reviewer.py` - Implementation
- `tests/perf/test_reviewer_budget.py` - Test examples
