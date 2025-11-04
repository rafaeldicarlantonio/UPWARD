# Evaluation Golden Set Curation Guide

## Overview

Golden sets are curated reference test cases that serve as ground truth for evaluation suites. They are versioned, human-approved, and maintained with stable IDs to ensure reproducible testing.

## Why Golden Sets?

1. **Reproducibility**: Stable test cases with fixed IDs
2. **Quality**: Human-reviewed and approved
3. **Traceability**: Version history with rationale
4. **Trust**: Evidence IDs verified and documented

## Directory Structure

```
evals/golden/
├── implicate_lift/
│   └── golden_set.jsonl
├── contradictions/
│   └── golden_set.jsonl
├── external_compare/
│   └── golden_set.jsonl
└── pareto_gate/
    └── golden_set.jsonl
```

Each suite has its own golden set in JSONL format (one item per line).

## Golden Item Structure

### Example: Implicate Lift

```json
{
  "id": "golden_bridge_001",
  "suite": "implicate_lift",
  "added_at": "2025-01-15T10:30:00Z",
  "approved_by": "jane.doe@example.com",
  "rationale": "Tests entity bridging via temporal relationship",
  "version": 1,
  "query": "How are SpaceX and NASA collaboration related to Mars missions?",
  "expected_sources": ["src_spacex_123", "src_nasa_456", "src_mars_789"],
  "category": "implicate_lift"
}
```

### Example: Pareto Gate

```json
{
  "id": "golden_pareto_005",
  "suite": "pareto_gate",
  "added_at": "2025-01-15T11:00:00Z",
  "approved_by": "john.smith@example.com",
  "rationale": "Boundary case at threshold",
  "version": 2,
  "updated_at": "2025-01-20T14:30:00Z",
  "updated_by": "alice.wong@example.com",
  "update_rationale": "Adjusted threshold after model improvements",
  "hypothesis": "Machine learning benefits from data augmentation",
  "expected_score": 0.65,
  "expected_persisted": true,
  "category": "pareto_gate"
}
```

## Required Fields

All golden items must include:

- **id**: Unique identifier starting with `golden_`
- **suite**: Suite name
- **added_at**: ISO 8601 timestamp
- **approved_by**: Email of approver
- **rationale**: Clear reason for inclusion
- **version**: Version number (starts at 1)

Updates add:

- **updated_at**: ISO 8601 timestamp
- **updated_by**: Email of updater
- **update_rationale**: Reason for update

## Tools

### 1. Adding Items: `tools/golden_add.py`

#### Interactive Mode (Recommended for New Users)

```bash
python tools/golden_add.py --interactive
```

Follow the prompts to add a new golden item.

#### Command Line Mode

**Add a new item:**

```bash
python tools/golden_add.py \
  --suite implicate_lift \
  --id golden_bridge_002 \
  --query "What connects renewable energy and climate policy?" \
  --expected-sources "src_renewable_111,src_climate_222" \
  --rationale "Tests policy-technology bridge" \
  --approved-by "your.email@example.com"
```

**Update an existing item:**

```bash
python tools/golden_add.py \
  --suite pareto_gate \
  --id golden_pareto_005 \
  --update \
  --expected-score 0.70 \
  --rationale "Threshold adjustment after model update" \
  --approved-by "your.email@example.com"
```

#### Suite-Specific Arguments

**Implicate Lift:**
- `--query`: Query text
- `--expected-sources`: Comma-separated source IDs

**Contradictions:**
- `--query`: Query text
- `--expected-contradiction`: Boolean (true/false)
- `--expected-claims`: Comma-separated claims

**External Compare:**
- `--query`: Query text
- `--expected-mode`: Mode (off/on)
- `--expected-parity`: Boolean (true/false)

**Pareto Gate:**
- `--hypothesis`: Hypothesis text
- `--expected-score`: Float (0-1)
- `--expected-persisted`: Boolean (true/false)

### 2. Viewing Changes: `tools/golden_diff.py`

#### Compare Current vs Committed

```bash
# Show changes since last commit
python tools/golden_diff.py --suite implicate_lift
```

#### Compare Against Specific Commit

```bash
# Compare with commit from 3 versions ago
python tools/golden_diff.py --suite pareto_gate --git-ref HEAD~3

# Compare with main branch
python tools/golden_diff.py --suite contradictions --git-ref main
```

#### View Specific Item

```bash
python tools/golden_diff.py --suite implicate_lift --id golden_bridge_001
```

#### Verbose Mode

```bash
# Show full details of all changes
python tools/golden_diff.py --suite pareto_gate --verbose
```

#### Review Summary

```bash
# Generate review checklist
python tools/golden_diff.py --suite implicate_lift --review
```

## Curation Workflow

### Step 1: Identify Need

Determine when a golden item is needed:

- **New feature**: Add test cases for new functionality
- **Bug fix**: Add regression test case
- **Edge case**: Add case that caught an issue
- **Coverage gap**: Add case for uncovered scenario

### Step 2: Create Item

Use `golden_add.py` to create the item:

```bash
python tools/golden_add.py \
  --suite <suite> \
  --id golden_<suite>_<number> \
  --<suite-specific-args> \
  --rationale "Clear reason for inclusion" \
  --approved-by "your.email@example.com"
```

**ID Naming Convention:**
- Format: `golden_<suite>_<number>`
- Examples:
  - `golden_bridge_001`
  - `golden_pareto_005`
  - `golden_contra_010`

### Step 3: Verify Evidence IDs

Ensure all evidence IDs (source IDs) exist and are accessible:

1. Check source database
2. Verify IDs return expected content
3. Document any special considerations

### Step 4: Review Changes

Use `golden_diff.py` to review your changes:

```bash
# Show diff
python tools/golden_diff.py --suite <suite> --verbose

# Generate review checklist
python tools/golden_diff.py --suite <suite> --review
```

### Step 5: Get Approval

**Self-Review Checklist:**

- [ ] ID follows `golden_*` naming convention
- [ ] ID is unique (no duplicates)
- [ ] `approved_by` field has valid email
- [ ] `rationale` clearly explains purpose
- [ ] Evidence IDs are valid and accessible
- [ ] Expected values match actual behavior
- [ ] Query/hypothesis is clear and unambiguous
- [ ] Test case adds value (not redundant)

**Peer Review (for significant changes):**

1. Share diff output with team
2. Explain rationale and evidence
3. Address feedback
4. Get explicit approval
5. Document approver in commit message

### Step 6: Commit

```bash
# Stage changes
git add evals/golden/<suite>/golden_set.jsonl

# Commit with clear message
git commit -m "Add golden item: <id>

Rationale: <rationale>
Approved-by: <email>
Suite: <suite>
"

# Push
git push
```

## Review Process

### When to Review

Golden sets should be reviewed:

1. **Before merging PR**: All new/updated items
2. **Weekly**: Recent changes
3. **Quarterly**: Full audit
4. **After incidents**: Related cases

### Review Steps

#### 1. Generate Diff

```bash
# For PR review
python tools/golden_diff.py --suite <suite>

# For periodic review
python tools/golden_diff.py --suite <suite> --git-ref main
```

#### 2. Check Diff Output

**Added Items (➕):**
- Verify ID uniqueness
- Check rationale is clear
- Validate evidence IDs exist
- Confirm expected values are correct

**Modified Items (📝):**
- Review version increment
- Check update rationale
- Verify evidence ID changes
  - Removed sources: Still valid to remove?
  - Added sources: New sources accessible?
- Validate expected value changes match behavior

**Removed Items (➖):**
- Understand why removed
- Check if replacement exists
- Verify not needed anymore

#### 3. Validate Evidence IDs

For any evidence ID changes:

```bash
# Check source still exists
curl http://api/sources/<source_id>

# Or query database
SELECT id, content FROM sources WHERE id IN ('src_123', 'src_456');
```

#### 4. Test Against System

Run the golden set against current system:

```bash
python evals/run.py --testset evals/golden/<suite>/golden_set.jsonl
```

Check:
- Do expected sources appear in top-k?
- Does expected score match actual?
- Does contradiction detection work?

#### 5. Approve or Request Changes

**Approve:**
- Comment: "LGTM - golden set changes approved"
- Merge PR

**Request Changes:**
- Comment specific issues
- Tag author
- Request fixes

## Common Scenarios

### Scenario: Adding First Golden Item for Suite

```bash
# Create first item
python tools/golden_add.py \
  --suite implicate_lift \
  --id golden_bridge_001 \
  --query "First test case" \
  --expected-sources "src_001,src_002" \
  --rationale "Initial golden set item" \
  --approved-by "curator@example.com"

# Verify
python tools/golden_diff.py --suite implicate_lift --verbose
```

### Scenario: Evidence ID Changed

**Problem**: Source ID `src_old_123` no longer exists, replaced with `src_new_456`

**Solution**:

```bash
python tools/golden_add.py \
  --suite implicate_lift \
  --id golden_bridge_001 \
  --update \
  --expected-sources "src_new_456,src_002" \
  --rationale "Updated evidence ID after source migration" \
  --approved-by "curator@example.com"
```

**Review**:

```bash
python tools/golden_diff.py --suite implicate_lift --id golden_bridge_001

# Output shows:
# expected_sources:
#   - Removed: src_old_123
#   + Added: src_new_456
```

### Scenario: Threshold Adjustment

**Problem**: Model improved, Pareto threshold changed from 0.65 to 0.70

**Solution**:

Update all affected golden items:

```bash
# Update boundary cases
python tools/golden_add.py \
  --suite pareto_gate \
  --id golden_pareto_005 \
  --update \
  --expected-score 0.70 \
  --rationale "Threshold increased after model v2.0 deployment" \
  --approved-by "ml-eng@example.com"
```

**Review**:

```bash
python tools/golden_diff.py --suite pareto_gate --verbose

# Check all score changes are intentional
```

### Scenario: Bulk Review

**Quarterly audit of all golden sets:**

```bash
# Review each suite
for suite in implicate_lift contradictions external_compare pareto_gate; do
  echo "=== Reviewing $suite ==="
  python tools/golden_diff.py --suite $suite --review > review_$suite.txt
done

# Review generated files
cat review_*.txt
```

## Best Practices

### DO:

✅ **Use descriptive IDs**: `golden_bridge_temporal_001` better than `golden_001`

✅ **Write clear rationale**: Explain WHY, not just WHAT
- Bad: "Added test case"
- Good: "Tests edge case where temporal link spans 3-hop bridge"

✅ **Verify before commit**: Always run diff and review

✅ **Keep evidence IDs stable**: Only update when necessary

✅ **Version incrementally**: Each update increments version

✅ **Document approvals**: Always include `approved_by`

✅ **Test after changes**: Run eval suite to confirm

### DON'T:

❌ **Don't skip approval**: Every change needs human approval

❌ **Don't reuse IDs**: Each golden item has unique, stable ID

❌ **Don't commit blindly**: Always review diff first

❌ **Don't use invalid evidence**: Verify all source IDs exist

❌ **Don't make mass changes**: Update items individually with rationale

❌ **Don't forget rationale**: Every change needs "why"

❌ **Don't use generic emails**: Use real approver emails

## Troubleshooting

### Error: "ID already exists"

**Problem**: Trying to add item with existing ID

**Solution**: Use `--update` flag or choose different ID

```bash
# Check existing IDs
python tools/golden_diff.py --suite <suite> --review

# Use update flag
python tools/golden_add.py --suite <suite> --id <id> --update ...
```

### Error: "ID must start with 'golden_'"

**Problem**: ID doesn't follow naming convention

**Solution**: Use correct format:

```bash
python tools/golden_add.py --id golden_bridge_001 ...  # Correct
```

### Error: "Invalid email format"

**Problem**: `approved_by` email is invalid

**Solution**: Use valid email address:

```bash
python tools/golden_add.py --approved-by "user@example.com" ...
```

### Changes Not Showing in Diff

**Problem**: `golden_diff.py` shows no changes

**Possible Causes**:
1. Changes not saved to file
2. Comparing wrong git ref
3. Looking at wrong suite

**Solution**:

```bash
# Check file exists and has content
cat evals/golden/<suite>/golden_set.jsonl

# Check git status
git status

# Compare with working directory (not HEAD)
python tools/golden_diff.py --suite <suite>
```

## Reference

### Tools Summary

| Tool | Purpose | Example |
|------|---------|---------|
| `golden_add.py` | Add/update items | `--suite <suite> --id <id> --approved-by <email>` |
| `golden_diff.py` | Show changes | `--suite <suite> --verbose` |

### File Locations

- **Golden sets**: `evals/golden/<suite>/golden_set.jsonl`
- **Tools**: `tools/golden_add.py`, `tools/golden_diff.py`
- **Tests**: (run eval suite with golden set)

### Exit Codes

- **0**: Success
- **1**: Error (invalid args, duplicate ID, etc.)

## Examples

See the tools themselves for comprehensive examples:

```bash
# Help for adding
python tools/golden_add.py --help

# Help for diffing
python tools/golden_diff.py --help
```

## Questions?

For questions or issues with golden set curation:

1. Check this documentation
2. Run `--help` on tools
3. Review existing golden sets
4. Ask team for guidance

## Appendix: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│ Golden Set Curation - Quick Reference                      │
├─────────────────────────────────────────────────────────────┤
│ ADD ITEM:                                                   │
│   python tools/golden_add.py \                             │
│     --suite <suite> \                                       │
│     --id golden_<name>_### \                               │
│     --<args> \                                              │
│     --rationale "<reason>" \                                │
│     --approved-by "email@example.com"                       │
│                                                             │
│ UPDATE ITEM:                                                │
│   python tools/golden_add.py \                             │
│     --suite <suite> \                                       │
│     --id <existing_id> \                                    │
│     --update \                                              │
│     --<args> \                                              │
│     --rationale "<reason>" \                                │
│     --approved-by "email@example.com"                       │
│                                                             │
│ VIEW DIFF:                                                  │
│   python tools/golden_diff.py --suite <suite> --verbose   │
│                                                             │
│ REVIEW:                                                     │
│   python tools/golden_diff.py --suite <suite> --review    │
│                                                             │
│ CHECKLIST:                                                  │
│   [ ] Unique ID starting with 'golden_'                   │
│   [ ] Valid approver email                                 │
│   [ ] Clear rationale                                       │
│   [ ] Evidence IDs verified                                 │
│   [ ] Expected values correct                               │
│   [ ] Diff reviewed                                         │
│   [ ] Tests pass                                            │
└─────────────────────────────────────────────────────────────┘
```
