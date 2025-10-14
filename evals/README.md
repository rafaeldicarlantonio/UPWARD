# Evaluation System for Implicate Lift and Contradictions

This evaluation system provides comprehensive testing for implicate lift and contradiction surfacing capabilities, with detailed performance monitoring and CI integration.

## Features

- **Implicate Lift Testing**: Tests that concept entities outrank literal matches
- **Contradiction Detection**: Tests for proper contradiction surfacing
- **Performance Monitoring**: P95 latency < 500ms with N_e=16, N_i=8
- **CI Integration**: Proper markers for flaky tests and CI-safe execution
- **Comprehensive Metrics**: Detailed timing breakdown and constraint validation

## Quick Start

### Run All Evaluations
```bash
python evals/run.py
```

### Run Specific Testset
```bash
python evals/run.py --testset evals/testsets/implicate_lift.json
```

### Run in CI Mode
```bash
python evals/run.py --ci-mode --skip-flaky
```

### Run Performance Tests
```bash
python tests/test_perf.py --ci-mode
```

## Test Categories

### 1. Implicate Lift Tests (`implicate_lift.json`)
Tests that concept entities are properly surfaced and ranked higher than literal matches.

**Key Features:**
- Golden cases where implicate should outrank literal match
- Expected implicate rank validation
- Lift score validation
- Concept expansion testing

**Example Test:**
```json
{
  "id": "implicate_lift_001",
  "prompt": "What are the key principles of effective leadership?",
  "must_include": ["leadership", "principles"],
  "must_cite_any": ["concept:"],
  "expected_implicate_rank": 1,
  "expected_lift_score": 0.7,
  "golden_case": true
}
```

### 2. Contradiction Tests (`contradictions.json`)
Tests for proper contradiction detection and surfacing.

**Key Features:**
- True contradiction detection
- False positive prevention
- Contradiction score validation
- Multiple contradiction types

**Example Test:**
```json
{
  "id": "contradiction_001",
  "prompt": "What is the current policy on remote work?",
  "expected_contradictions": true,
  "expected_contradiction_score": 0.7,
  "golden_case": true
}
```

### 3. Performance Tests (`performance.json`)
Tests for performance constraints and timing validation.

**Key Features:**
- P95 latency < 500ms
- Individual request < 1000ms
- N_e=16, N_i=8 validation
- Stress testing with flaky markers

## Performance Constraints

### Latency Constraints
- **P95 Latency**: < 500ms (configurable with `--max-latency`)
- **Individual Requests**: < 1000ms (configurable with `--max-individual-latency`)
- **Retrieval Phase**: Optimized for N_e=16, N_i=8

### Timing Breakdown
- **Retrieval**: ~60% of total latency
- **Ranking**: ~20% of total latency
- **Packing**: ~20% of total latency

## CI Integration

### Test Markers
- `@pytest.mark.performance`: Performance-related tests
- `@pytest.mark.ci_safe`: Safe to run in CI
- `@pytest.mark.flaky`: Can be flaky, skip with `--skip-flaky`
- `@pytest.mark.stress`: Stress tests
- `@pytest.mark.integration`: Integration tests

### CI Commands
```bash
# Run all CI-safe performance tests
python tests/test_perf.py --ci-mode

# Run with flaky tests
python tests/test_perf.py --ci-mode --skip-flaky

# Run specific test categories
python tests/test_perf.py -m "performance and ci_safe"
```

## Configuration

### Environment Variables
- `BASE_URL`: API base URL (default: http://localhost:8000)
- `X_API_KEY`: API key for authentication
- `MAX_CONTEXT_TOKENS`: Maximum context tokens (default: 2000)

### Command Line Options
- `--max-latency`: Maximum P95 latency in ms (default: 500)
- `--max-individual-latency`: Maximum individual request latency in ms (default: 1000)
- `--explicate-k`: Expected explicate top-k (default: 16)
- `--implicate-k`: Expected implicate top-k (default: 8)
- `--ci-mode`: Enable CI mode with stricter constraints
- `--skip-flaky`: Skip tests marked as flaky

## Metrics and Reporting

### Evaluation Summary
The system provides comprehensive metrics including:

- **Basic Stats**: Total cases, passed/failed counts
- **Latency Metrics**: P50, P90, P95, P99, max latency
- **Timing Breakdown**: Retrieval, ranking, packing latencies
- **Implicate Lift Metrics**: Success rate, average rank, lift scores
- **Contradiction Metrics**: Detection accuracy, contradiction scores
- **Constraint Violations**: Detailed violation tracking

### Sample Output
```
================================================================================
EVALUATION SUMMARY
================================================================================
Total Cases: 25
Passed: 23 (92.0%)
Failed: 2 (8.0%)

📊 Latency Metrics:
  Average: 245.3ms
  P50: 220.1ms
  P90: 380.2ms
  P95: 420.5ms
  P99: 480.1ms
  Max: 520.3ms

⏱️  Timing Breakdown:
  Retrieval: 147.2ms
  Ranking: 49.1ms
  Packing: 49.0ms

🎯 Implicate Lift Metrics:
  Total Cases: 10
  Successful Lifts: 8
  Success Rate: 80.0%
  Avg Implicate Rank: 1.2

🔍 Contradiction Metrics:
  Total Cases: 12
  Contradictions Detected: 8
  Detection Accuracy: 83.3%
  Avg Contradiction Score: 0.65

✅ Performance Constraints:
  P95 < 500ms: ✅ PASS (420.5ms)
  All Constraints: ✅ PASS (0 violations)
```

## Troubleshooting

### Common Issues

1. **High Latency**: Check vector store performance and network connectivity
2. **Failed Implicate Tests**: Verify concept entity indexing and graph expansion
3. **Contradiction Detection Issues**: Check contradiction detection feature flags
4. **CI Failures**: Use `--skip-flaky` for flaky tests

### Debug Mode
Enable debug mode for detailed metrics:
```bash
python evals/run.py --verbose
```

### Performance Profiling
For detailed performance analysis:
```bash
python tests/test_perf.py -v --ci-mode
```

## Development

### Adding New Tests
1. Add test cases to appropriate JSON file in `evals/testsets/`
2. Include proper metadata (golden_case, expected scores, etc.)
3. Test locally before committing

### Adding New Metrics
1. Update `EvalResult` dataclass in `evals/run.py`
2. Add metric collection in `run_single_case`
3. Update `generate_summary` method
4. Add display logic in `print_summary`

### CI Integration
1. Use appropriate pytest markers
2. Mark flaky tests with `@pytest.mark.flaky`
3. Ensure CI-safe tests are marked with `@pytest.mark.ci_safe`
4. Test with `--ci-mode` flag locally