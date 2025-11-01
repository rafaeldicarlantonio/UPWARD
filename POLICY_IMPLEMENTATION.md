# Ingest Policy System Implementation

## Overview

A comprehensive policy system has been implemented for the ingestion pipeline, providing role-based caps, tolerances, and constraints loaded from YAML configuration.

## Files Created/Modified

### 1. `config/ingest_policy.yaml` (New)
- Role-specific policies (admin, pro, scholars, analytics, general, user)
- Global limits that cannot be exceeded
- Default fallback policy for safe operation
- Valid frame types list

### 2. `core/policy.py` (Modified)
Added ingest policy system:
- **`IngestPolicy` dataclass**: Defines policy structure with caps and tolerances
- **`IngestPolicyManager` class**: Loads and manages policies from YAML
  - Safe fallback to defaults if file is missing or malformed
  - Validates policies against global limits
  - Selects most permissive policy for users with multiple roles
  - Enforces caps on analysis results
- **Helper functions**: `get_ingest_policy()`, `get_ingest_policy_manager()`

### 3. `ingest/commit.py` (Modified)
- Updated `commit_analysis()` to accept `user_roles` parameter
- Applies policy enforcement before committing entities
- Filters concepts, frames, and contradictions based on policy
- Logs policy application for observability

### 4. `tests/ingest/test_policy.py` (New)
Comprehensive test suite with 24 tests covering:
- Policy loading and YAML validation
- Malformed policy fallback to safe defaults
- Role-based policy selection
- Policy validation and clamping
- Cap enforcement (concepts, frames, contradictions)
- Frame type filtering
- Contradiction tolerance filtering
- Integration tests with commit_analysis

## Policy Structure

### Role-Based Policies

Each role has specific caps and permissions:

#### Admin
- Max concepts per file: 500
- Max frames per chunk: 50
- Write contradictions: Yes
- Allowed frame types: All (claim, evidence, question, observation, hypothesis, conclusion, method, result)
- Contradiction tolerance: 0.1 (10%)

#### Pro
- Max concepts per file: 200
- Max frames per chunk: 30
- Write contradictions: Yes
- Allowed frame types: claim, evidence, question, observation, hypothesis, conclusion
- Contradiction tolerance: 0.15

#### General (Conservative)
- Max concepts per file: 50
- Max frames per chunk: 10
- Write contradictions: No
- Allowed frame types: claim, evidence only
- Contradiction tolerance: 0.3

### Global Limits

Absolute maximum values that cannot be exceeded:
- Max concepts per file: 1000
- Max frames per chunk: 100
- Max edges per commit: 5000
- Contradiction tolerance range: 0.05 - 0.9

### Default Fallback Policy

Safe defaults used when:
- Policy file is missing
- Policy file is malformed
- No matching role is found

Values:
- Max concepts: 20
- Max frames: 5
- Write contradictions: No
- Allowed frame types: claim only
- Contradiction tolerance: 0.5

## Policy Enforcement Flow

1. **Load Policy**: `get_ingest_policy_manager()` loads YAML on first call
2. **Select Policy**: Based on user roles (most permissive wins)
3. **Enforce Caps**: `IngestPolicyManager.enforce_caps()` applies limits:
   - Caps concepts to `max_concepts_per_file`
   - Filters frames by `allowed_frame_types`
   - Caps frames to `max_frames_per_chunk`
   - Filters contradictions by `contradiction_tolerance`
   - Blocks contradictions if `write_contradictions_to_memories` is False
4. **Commit**: `commit_analysis()` uses capped/filtered results

## Usage

### In Code

```python
from core.policy import get_ingest_policy
from ingest.commit import commit_analysis

# Get policy for user roles
policy = get_ingest_policy(["pro"])
print(f"Max concepts: {policy.max_concepts_per_file}")
print(f"Allowed frames: {policy.allowed_frame_types}")

# Commit with policy enforcement
result = commit_analysis(
    sb=supabase_client,
    analysis=analysis_result,
    memory_id="mem-123",
    file_id="file-456",
    chunk_idx=0,
    user_roles=["pro"]  # Policy applied automatically
)
```

### Policy Configuration

Edit `config/ingest_policy.yaml` to adjust:
- Per-role caps and tolerances
- Global absolute limits
- Valid frame types
- Default fallback values

## Key Features

### 1. Safe Fallback
- Malformed YAML → safe defaults
- Missing file → safe defaults
- Unknown role → default policy
- Invalid values → clamped to limits

### 2. Role Flexibility
- Multiple roles → most permissive policy
- Hierarchical permissions
- Extensible role system

### 3. Frame Type Control
- Whitelist allowed frame types per role
- Filters out disallowed types
- Tracks filtered frames for observability

### 4. Contradiction Management
- Tolerance threshold filtering (score-based)
- Role-specific write permissions
- General users don't see contradictions

### 5. Validation & Clamping
- Global limits enforced
- Values clamped to safe ranges
- Prevents policy misconfiguration

## Test Results

All 24 tests passing:

```
✅ Policy Loading (3 tests)
   - Load valid policy
   - Malformed policy falls back
   - Missing file falls back

✅ Policy Selection (5 tests)
   - Admin role selection
   - General role selection
   - Multiple roles pick most permissive
   - No roles return default
   - Unknown role returns default

✅ Policy Validation (2 tests)
   - Clamps to global limits
   - Enforces minimum tolerance

✅ Policy Enforcement (4 tests)
   - Limits concepts
   - Filters frame types
   - Filters contradictions by tolerance
   - Blocks contradictions for general role

✅ Commit Integration (4 tests)
   - Enforces concept caps
   - Filters frame types
   - Blocks contradictions for general role
   - Allows more concepts for admin

✅ Helper Functions (3 tests)
   - Convenience function works
   - Manager is singleton
   - Frame type validation

✅ YAML Structure (3 tests)
   - Policy file exists
   - Valid YAML format
   - Has required sections
```

## Acceptance Criteria ✅

All acceptance criteria met:

1. ✅ **Load from YAML with caps and tolerances**
   - `config/ingest_policy.yaml` with all required fields
   - Role-specific policies loaded
   - Global limits defined
   - Default fallback configured

2. ✅ **Enforce during commit**
   - `commit_analysis()` applies policy before creating entities
   - Concepts capped to `max_concepts_per_file`
   - Frames filtered by `allowed_frame_types`
   - Contradictions filtered by tolerance and role permissions

3. ✅ **Caps for max concepts, allowed frame types, numeric tolerance**
   - Per-role concept caps
   - Frame type whitelist
   - Contradiction tolerance threshold (numeric)
   - All enforced with validation

4. ✅ **Control contradiction writes for 'general' role**
   - `write_contradictions_to_memories: false` for general users
   - Contradictions filtered out before memory update
   - Other roles can still write contradictions

5. ✅ **Malformed policy falls back**
   - Safe defaults when YAML is invalid
   - Logging for troubleshooting
   - System remains operational

6. ✅ **Tests validate enforcement**
   - 24 comprehensive tests
   - Unit tests for each component
   - Integration tests with commit_analysis
   - YAML structure validation

## Notes

- Thread-safe singleton pattern for policy manager
- Policies are loaded once at startup for performance
- Detailed logging for policy application
- Backward compatible (user_roles parameter is optional)
- Future-proof: Easy to add new policies or roles
