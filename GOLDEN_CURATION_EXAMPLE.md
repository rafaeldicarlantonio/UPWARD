# Golden Set Curation - Complete Example Walkthrough

This document shows a complete example of using the golden set curation tools.

## Scenario: Adding a New Golden Test Case

You've discovered that implicate bridging works well for connecting technology trends across time, and you want to preserve this as a golden test case.

### Step 1: Add the Golden Item

```bash
python tools/golden_add.py \
  --suite implicate_lift \
  --id golden_tech_trends_001 \
  --query "How do AI breakthroughs in the 2010s relate to current autonomous vehicle development?" \
  --expected-sources "src_ai_2015_deeplearn,src_ai_2017_transformer,src_av_2023_tesla,src_av_2024_waymo" \
  --rationale "Tests temporal technology trend bridging across 5+ year gap" \
  --approved-by "tech.curator@example.com"
```

**Output:**
```
✅ Added golden item 'golden_tech_trends_001' to implicate_lift
   Approved by: tech.curator@example.com
   Rationale: Tests temporal technology trend bridging across 5+ year gap
```

### Step 2: Verify the Item Was Created

```bash
cat evals/golden/implicate_lift/golden_set.jsonl | grep golden_tech_trends_001 | python -m json.tool
```

**Output:**
```json
{
  "id": "golden_tech_trends_001",
  "suite": "implicate_lift",
  "added_at": "2025-11-03T14:30:00Z",
  "approved_by": "tech.curator@example.com",
  "rationale": "Tests temporal technology trend bridging across 5+ year gap",
  "version": 1,
  "query": "How do AI breakthroughs in the 2010s relate to current autonomous vehicle development?",
  "expected_sources": [
    "src_ai_2015_deeplearn",
    "src_ai_2017_transformer",
    "src_av_2023_tesla",
    "src_av_2024_waymo"
  ],
  "category": "implicate_lift"
}
```

### Step 3: Review the Changes

```bash
python tools/golden_diff.py --suite implicate_lift --verbose
```

**Output:**
```
================================================================================
Golden Set Diff: implicate_lift
================================================================================

Summary:
  Added:    1 items
  Removed:  0 items
  Modified: 0 items

➕ Added Items:
--------------------------------------------------------------------------------
  + golden_tech_trends_001
    query: How do AI breakthroughs in the 2010s relate to current autonomous vehicle...
    expected_sources: src_ai_2015_deeplearn, src_ai_2017_transformer, src_av_2023_tesla, src_av_2024_waymo
    category: implicate_lift
    Added by: tech.curator@example.com
    Rationale: Tests temporal technology trend bridging across 5+ year gap
```

### Step 4: Commit the Changes

```bash
git add evals/golden/implicate_lift/golden_set.jsonl
git commit -m "Add golden item: golden_tech_trends_001

Tests temporal technology trend bridging across 5+ year gap.

Rationale: AI breakthroughs → autonomous vehicles represents important
implicate bridging pattern across temporal gap.

Approved-by: tech.curator@example.com
Suite: implicate_lift
"
```

## Scenario: Updating Evidence IDs After Source Migration

Your team migrated sources, and `src_av_2023_tesla` was replaced with `src_av_2023_tesla_v2`.

### Step 1: Update the Golden Item

```bash
python tools/golden_add.py \
  --suite implicate_lift \
  --id golden_tech_trends_001 \
  --update \
  --expected-sources "src_ai_2015_deeplearn,src_ai_2017_transformer,src_av_2023_tesla_v2,src_av_2024_waymo" \
  --rationale "Updated Tesla source ID after source migration (ticket #1234)" \
  --approved-by "data.eng@example.com"
```

**Output:**
```
✅ Updated golden item 'golden_tech_trends_001' in implicate_lift
   Version: 2
   Approved by: data.eng@example.com
   Rationale: Updated Tesla source ID after source migration (ticket #1234)
```

### Step 2: View the Diff

```bash
python tools/golden_diff.py --suite implicate_lift --id golden_tech_trends_001 --verbose
```

**Output:**
```
================================================================================
Golden Set Diff: implicate_lift
================================================================================

Summary:
  Added:    0 items
  Removed:  0 items
  Modified: 1 items

📝 Modified Items:
--------------------------------------------------------------------------------
  ~ golden_tech_trends_001
    Version: 1 → 2
    Updated by: data.eng@example.com
    Rationale: Updated Tesla source ID after source migration (ticket #1234)
    
    Changes:
      expected_sources:
        - Removed: src_av_2023_tesla
        + Added: src_av_2023_tesla_v2
```

### Step 3: Verify and Commit

```bash
# Verify the source exists
curl http://api/sources/src_av_2023_tesla_v2

# Commit
git add evals/golden/implicate_lift/golden_set.jsonl
git commit -m "Update golden item: golden_tech_trends_001

Updated Tesla source ID after source migration.

Changes:
- Removed: src_av_2023_tesla
- Added: src_av_2023_tesla_v2

Rationale: Source migration (ticket #1234)
Approved-by: data.eng@example.com
Version: 1 → 2
"
```

## Scenario: Weekly Review

### Step 1: Generate Review Summary

```bash
python tools/golden_diff.py --suite implicate_lift --review
```

**Output:**
```
================================================================================
Golden Set Review Summary: implicate_lift
================================================================================

Total Items: 5

Recent Changes (last 10):
--------------------------------------------------------------------------------
  golden_tech_trends_001
    Timestamp: 2025-11-03T14:35:00Z
    Approver: data.eng@example.com
    Version: 2

  golden_bridge_001
    Timestamp: 2025-11-01T10:00:00Z
    Approver: jane.doe@example.com
    Version: 1

  golden_causal_002
    Timestamp: 2025-10-28T15:20:00Z
    Approver: ml.researcher@example.com
    Version: 3

Review Checklist:
--------------------------------------------------------------------------------
  [ ] All IDs follow 'golden_*' naming convention
  [ ] All changes have human approval (approved_by field)
  [ ] All changes have clear rationale
  [ ] Evidence IDs are valid and accessible
  [ ] Expected values match actual system behavior
  [ ] No duplicate IDs
  [ ] Version numbers are sequential
```

### Step 2: Review Each Recent Change

```bash
# Review each updated item
for id in golden_tech_trends_001 golden_bridge_001 golden_causal_002; do
  echo "=== Reviewing $id ==="
  python tools/golden_diff.py --suite implicate_lift --id $id --verbose
done
```

### Step 3: Validate Evidence IDs

```bash
# Extract all evidence IDs
cat evals/golden/implicate_lift/golden_set.jsonl | \
  jq -r '.expected_sources[]' | \
  sort -u > /tmp/evidence_ids.txt

# Validate each (pseudo-code)
while read src_id; do
  curl -s http://api/sources/$src_id > /dev/null || echo "❌ Missing: $src_id"
done < /tmp/evidence_ids.txt
```

### Step 4: Run Tests

```bash
# Run the golden set against current system
python evals/run.py --testset evals/golden/implicate_lift/golden_set.jsonl
```

### Step 5: Approve

If all checks pass:
- ✅ All IDs follow convention
- ✅ All have human approval
- ✅ All rationales are clear
- ✅ All evidence IDs valid
- ✅ Tests pass

**Then:** No action needed, golden set is in good state.

If issues found:
- Request updates from original approver
- Fix evidence IDs
- Re-run validation

## Common Tasks

### Find Who Approved a Change

```bash
cat evals/golden/<suite>/golden_set.jsonl | \
  jq -r 'select(.id == "<item_id>") | .approved_by'
```

### See Version History

```bash
git log --all --oneline -- evals/golden/<suite>/golden_set.jsonl
```

### Revert a Change

```bash
# View old version
git show HEAD~1:evals/golden/<suite>/golden_set.jsonl

# Revert if needed
git revert <commit>
```

### Bulk Review All Suites

```bash
for suite in implicate_lift contradictions external_compare pareto_gate; do
  echo "=== $suite ==="
  python tools/golden_diff.py --suite $suite --review
  echo
done > weekly_review.txt

# Review the file
cat weekly_review.txt
```

## Tips

1. **Always review diffs before committing**
   ```bash
   python tools/golden_diff.py --suite <suite> --verbose
   ```

2. **Use meaningful rationales**
   - Bad: "Updated item"
   - Good: "Updated evidence IDs after source migration (ticket #1234)"

3. **Test after changes**
   ```bash
   python evals/run.py --testset evals/golden/<suite>/golden_set.jsonl
   ```

4. **Keep evidence IDs stable**
   - Only update when source truly changed
   - Document reason in rationale

5. **Version numbers tell a story**
   - v1: Original
   - v2: First update
   - v3+: Multiple updates (consider if item is too volatile)

## Troubleshooting

### Can't find an item

```bash
# List all IDs in suite
cat evals/golden/<suite>/golden_set.jsonl | jq -r '.id'

# Search for item
cat evals/golden/<suite>/golden_set.jsonl | jq 'select(.id | contains("search_term"))'
```

### Diff shows "Could not load from HEAD"

This happens when the file doesn't exist in git yet (first addition).

**Solution:** This is expected for new suites. The diff will show all items as "added".

### Need to see full history

```bash
# See all changes to golden set
git log -p -- evals/golden/<suite>/golden_set.jsonl
```
