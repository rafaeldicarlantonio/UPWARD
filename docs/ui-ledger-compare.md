# UI Components Guide: Ledger, Compare Card, and Badges

**Last Updated**: 2025-10-30  
**Version**: 1.0

## Table of Contents

- [Overview](#overview)
- [Process Ledger](#process-ledger)
- [Compare Card](#compare-card)
- [Contradiction Badge](#contradiction-badge)
- [Role-Based Access](#role-based-access)
- [Screenshots](#screenshots)
- [Troubleshooting](#troubleshooting)
- [API Routes](#api-routes)
- [Feature Flags](#feature-flags)

---

## Overview

The UPWARD UI includes three main components for displaying answer context and analysis:

1. **Process Ledger** - Shows how the answer was generated
2. **Compare Card** - Displays comparative analysis between stances
3. **Contradiction Badge** - Highlights conflicts in evidence

**Role-Based Display**:
- **General**: Limited view (4 ledger lines, no compare, no badges)
- **Pro**: Full view (expand ledger, compare with external, badges)
- **Scholars**: Same as Pro
- **Analytics**: Same as Pro with additional analytics

---

## Process Ledger

### What It Shows

The **Process Ledger** displays the step-by-step trace of how an answer was generated.

**Default View (Compact)**:
```
┌─────────────────────────────────────────────┐
│ 🔍 Process Trace              [Expand ▼]   │
├─────────────────────────────────────────────┤
│ 1. parse_query          10ms               │
│ 2. retrieve            50ms  Found 10 items│
│ 3. rank                20ms  100 tokens    │
│ 4. generate           200ms  gpt-4         │
└─────────────────────────────────────────────┘
```

**Expanded View (Pro/Scholars/Analytics)**:
```
┌─────────────────────────────────────────────┐
│ 🔍 Process Trace              [Collapse ▲] │
├─────────────────────────────────────────────┤
│ 1. parse_query          10ms               │
│ 2. retrieve            50ms  Found 10 items│
│ 3. rank                20ms  100 tokens    │
│ 4. generate           200ms  gpt-4         │
│ 5. validate            15ms                │
│ 6. finalize             5ms                │
│ 7. extra_step_7         5ms                │
│ 8. extra_step_8         5ms                │
└─────────────────────────────────────────────┘
```

### Information Displayed

Each line in the ledger shows:

| Field | Description | Example |
|-------|-------------|---------|
| **Step** | Processing stage | `retrieve` |
| **Duration** | Time taken | `50ms` |
| **Details** | Additional info | `Found 10 memories` |
| **Tokens** | Token count (if applicable) | `100 tokens` |
| **Model** | AI model used | `gpt-4` |

### Role-Based Behavior

#### General Users
- **Lines shown**: 4 (maximum)
- **Expand button**: Hidden
- **Prompts**: Stripped (redacted)
- **Provenance**: Stripped (redacted)

#### Pro/Scholars/Analytics
- **Lines shown**: 4 (summary)
- **Expand button**: Visible
- **Expanded lines**: Full trace (8+ lines)
- **Prompts**: Visible (in expanded view)
- **Provenance**: Visible (in expanded view)

### How to Use

1. **View Compact Trace**: Automatically shown below answer
2. **Expand (Pro+)**: Click "Expand Full Trace" button
3. **Collapse**: Click "Collapse" to return to summary

### Data Source

- **API Route**: `/api/chat` (includes `process_trace_summary`)
- **Expand API**: `/api/debug/redo_trace?message_id={id}`
- **Component**: `app/components/ProcessLedger.tsx`

---

## Compare Card

### What It Means

The **Compare Card** displays a **comparative analysis** between two different stances or viewpoints on the user's question.

**Visual Structure**:
```
┌─────────────────────────────────────────────────────────┐
│             Compare: Stance A vs Stance B               │
├─────────────────────────────────────────────────────────┤
│  Stance A                    │  Stance B                │
│  Census reports official     │  Estimates suggest 8.8M  │
│  count of 8,336,817         │  including undocumented  │
├──────────────────────────────┼──────────────────────────┤
│  Internal Evidence:          │  Internal Evidence:      │
│  • Official 2020 Census      │  • Demographic estimates │
│    count (95%)              │    include undocumented  │
│                             │    (85%)                 │
│                             │                          │
│                             │  External Evidence:      │
│                             │  • Wikipedia: NYC pop.   │
│                             │    8.3-8.8M (label)      │
├─────────────────────────────────────────────────────────┤
│                [Run Full Compare ▶]                     │
└─────────────────────────────────────────────────────────┘
```

### What It Shows

1. **Stance A** (Left): First viewpoint with supporting evidence
2. **Stance B** (Right): Alternative viewpoint with supporting evidence
3. **Evidence Lists**: 
   - **Internal**: From your knowledge base
   - **External**: From web sources (Wikipedia, arXiv, etc.)
4. **Run Full Compare**: Fetches additional external sources

### Evidence Display

**Internal Evidence**:
- Source: Your knowledge base
- Display: Full text
- Score: Confidence percentage
- Example: `"Official 2020 Census count" (95%)`

**External Evidence** (Pro+ only):
- Source: Web (Wikipedia, arXiv, PubMed, GitHub)
- Display: Truncated snippet
- Truncation limits:
  - Wikipedia: 480 chars (General), 800 chars (Pro)
  - arXiv: 640 chars (General), 1200 chars (Pro)
  - Default: 480 chars (General), 800 chars (Pro)
- Label: Source name (e.g., "Wikipedia")
- Provenance: Host URL shown

### Role-Based Behavior

#### General Users
- **Compare Card**: Hidden (not displayed)
- **External Evidence**: Not accessible
- **Run Full Compare**: Not available

#### Pro/Scholars/Analytics
- **Compare Card**: Visible
- **External Evidence**: Truncated per policy
- **Run Full Compare**: Enabled (if `flags.external_compare=true`)

### How to Use

1. **View Comparison**: Automatically shown if `compare_summary` exists
2. **Read Stances**: Compare left vs right viewpoints
3. **Review Evidence**: Check supporting evidence for each stance
4. **Run Full Compare** (Pro+):
   - Click "Run Full Compare"
   - System fetches additional external sources
   - New evidence appears in "External Evidence" section
   - Shows source labels (Wikipedia, arXiv, etc.)

### When It Appears

The compare card appears when:
- ✅ Role is Pro, Scholars, or Analytics
- ✅ `ui.flags.show_compare=true`
- ✅ `compare_summary` exists in response
- ✅ At least one stance has evidence

The compare card does NOT appear when:
- ❌ Role is General
- ❌ `ui.flags.show_compare=false`
- ❌ No `compare_summary` in response
- ❌ Both stances are empty

### Data Source

- **API Route**: `/api/chat` (includes `compare_summary`)
- **Full Compare**: `/api/factate/compare` (POST with `allow_external=true`)
- **Component**: `app/components/CompareCard.tsx`

---

## Contradiction Badge

### What It Signals

The **Contradiction Badge** highlights when there are **conflicts or inconsistencies** in the evidence used to generate the answer.

**Visual Appearance**:
```
┌──────────────────────────┐
│  Answer                  │
│  ⚠️ 2 Contradictions     │  ← Badge
└──────────────────────────┘
```

**Badge States**:

| Count | Icon | Color | Meaning |
|-------|------|-------|---------|
| 0 | - | Hidden | No contradictions |
| 1 | ⚠️ | 🔴 Red | High severity |
| 2+ | ⚠️ | 🔴 Red | Multiple high severity |
| Medium | ⚡ | 🟡 Yellow | Notable discrepancy |
| Low | ℹ️ | 🔵 Blue | Minor inconsistency |

### Severity Levels

**High** (Red ⚠️):
- Critical contradictions
- Major discrepancies in facts
- Conflicting primary sources
- Example: "Population count differs by > 1 million"

**Medium** (Yellow ⚡):
- Notable conflicts
- Different methodologies
- Conflicting secondary sources
- Example: "Census vs estimates use different methods"

**Low** (Blue ℹ️):
- Minor inconsistencies
- Interpretation differences
- Conflicting tertiary sources
- Example: "Minor discrepancy in validation protocols"

### Tooltip Details

**Hover/Click to View**:
```
┌─────────────────────────────────────┐
│  2 Contradictions                   │
├─────────────────────────────────────┤
│  ⚠️ Population count discrepancy    │
│     Census vs estimates show        │
│     different numbers               │
│                                     │
│  ⚡ Methodology conflict             │
│     Different counting methods      │
│     produce different results       │
└─────────────────────────────────────┘
```

**Tooltip Information**:
- Severity icon
- Subject (brief description)
- Description (detailed explanation)
- Evidence anchor (link to specific evidence)

### Role-Based Behavior

#### General Users
- **Badge**: Hidden (not displayed)
- **Contradictions exist**: Yes (in data)
- **Tooltip**: Not accessible
- **Rationale**: Simplified UX for general audience

#### Pro/Scholars/Analytics
- **Badge**: Visible (when contradictions > 0)
- **Badge count**: Shows number of contradictions
- **Tooltip**: Opens on click/hover
- **Evidence links**: Click to scroll to conflicting evidence
- **Always show**: If `ui.flags.show_badges=true`, shows even when 0

### How to Use

1. **Check Badge**: Look for badge next to answer title
2. **View Count**: Number indicates how many contradictions
3. **Open Tooltip**: Click badge to see details
4. **Navigate**: Click contradiction subject to scroll to evidence
5. **Assess Severity**: Check icon/color for importance level

### When It Appears

The badge appears when:
- ✅ Role is Pro, Scholars, or Analytics
- ✅ `ui.flags.show_badges=true` OR contradictions > 0
- ✅ `contradictions` array exists in response

The badge does NOT appear when:
- ❌ Role is General
- ❌ `ui.flags.show_badges=false` AND contradictions = 0
- ❌ No contradictions in response

### Data Source

- **API Route**: `/api/chat` (includes `contradictions` array)
- **Component**: `app/components/ContradictionBadge.tsx`
- **Types**: `app/components/ContradictionBadge.tsx` (`Contradiction` interface)

---

## Role-Based Access

### Feature Matrix

| Feature | General | Pro | Scholars | Analytics |
|---------|---------|-----|----------|-----------|
| **Process Ledger** | 4 lines (limited) | 4 lines + expand | 4 lines + expand | 4 lines + expand |
| **Ledger Expand** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Raw Prompts** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Provenance** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Compare Card** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **External Compare** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **External Evidence** | ❌ No | ✅ Truncated | ✅ Truncated | ✅ Truncated |
| **Contradiction Badge** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Promote Hypothesis** | ❌ No | ✅ Yes | ❌ No | ✅ Yes |
| **Create AURA Project** | ❌ No | ✅ Yes | ❌ No | ✅ Yes |

### Button Visibility

#### "Expand Full Trace" Button

**Visible for**:
- ✅ Pro
- ✅ Scholars  
- ✅ Analytics

**Hidden for**:
- ❌ General

**Condition**: `hasCapability(role, CAP_READ_LEDGER_FULL)`

#### "Run Full Compare" Button

**Visible for**:
- ✅ Pro (if external compare enabled)
- ✅ Scholars (if external compare enabled)
- ✅ Analytics (if external compare enabled)

**Hidden for**:
- ❌ General

**Condition**: `allowExternal && hasCapability(role, CAP_READ_LEDGER_FULL)`

#### "Promote to Hypothesis" Button

**Visible for**:
- ✅ Pro
- ✅ Analytics

**Hidden for**:
- ❌ General
- ❌ Scholars

**Condition**: `role === ROLE_PRO || role === ROLE_ANALYTICS`

#### "Create AURA Project" Button

**Visible for**:
- ✅ Pro
- ✅ Analytics

**Hidden for**:
- ❌ General
- ❌ Scholars

**Condition**: `role === ROLE_PRO || role === ROLE_ANALYTICS`

### Redaction Summary

**General Users See**:
- ✅ Answer text
- ✅ Internal evidence (truncated)
- ✅ Process ledger (4 lines, no prompts/provenance)
- ❌ Compare card
- ❌ External evidence
- ❌ Contradiction badge
- ❌ Promote/AURA buttons
- ❌ Expand ledger button

**Pro/Scholars/Analytics See**:
- ✅ Everything General sees, plus:
- ✅ Compare card with stances
- ✅ External evidence (truncated per policy)
- ✅ Contradiction badge with tooltip
- ✅ Full ledger (expandable)
- ✅ Raw prompts and provenance (in expanded ledger)
- ✅ "Run Full Compare" button
- ✅ (Pro/Analytics only) Promote/AURA buttons

---

## Screenshots

### Pro User View

**Full Answer with All Components**:

![Pro User View](screenshots/pro-complete-flow.png)

1. Answer text
2. Contradiction badge (⚠️ 2 Contradictions)
3. Compare card with stances A & B
4. Internal & external evidence
5. "Run Full Compare" button
6. Process ledger (4 lines)
7. "Expand Full Trace" button
8. "Promote to Hypothesis" button
9. "Create AURA Project" button

**Contradiction Badge with Tooltip**:

![Contradiction Tooltip](screenshots/pro-contradiction-tooltip.png)

**Compare Card with External Evidence**:

![Compare with External](screenshots/pro-compare-external.png)

**Expanded Process Ledger**:

![Expanded Ledger](screenshots/pro-ledger-expanded.png)

### General User View

**Limited Answer View**:

![General User View](screenshots/general-complete-flow.png)

1. Answer text
2. ❌ No contradiction badge
3. ❌ No compare card
4. Process ledger (4 lines, limited)
5. ❌ No expand button
6. ❌ No Promote button
7. ❌ No AURA button

**Side-by-Side Comparison**:

![Pro vs General](screenshots/comparison-pro-vs-general.png)

Left: Pro user (all features)  
Right: General user (limited features)

---

## Troubleshooting

### "No Compare Card" Issue

**Symptom**: Compare card doesn't appear in chat response.

**Possible Causes**:

#### 1. Role Restriction
**Check**: User role is General
```typescript
// Check in browser console
localStorage.getItem('user_role')
// Should return: "pro", "scholars", or "analytics"
```
**Solution**: Upgrade to Pro or higher tier

#### 2. Feature Flag Disabled
**Check**: `ui.flags.show_compare` is false
```typescript
// Check in browser console
window.uiFlags?.show_compare
// Should return: true
```
**Solution**: 
- Enable flag in `app/config/flags.ts`
- Or set via API: `POST /api/flags/update { show_compare: true }`

#### 3. No Compare Summary in Response
**Check**: API response missing `compare_summary`
```javascript
// Check network tab (DevTools > Network > chat)
response.compare_summary
// Should exist with stance_a, stance_b
```
**Solution**:
- Server issue: Check backend compare generation
- Question type: Not all questions generate comparisons
- Try different question that has multiple viewpoints

#### 4. Empty Compare Summary
**Check**: Both stances are empty
```javascript
response.compare_summary.evidence_a.length === 0 &&
response.compare_summary.evidence_b.length === 0
// Should be false
```
**Solution**: 
- Add more context to question
- Check if knowledge base has relevant evidence

#### 5. Client-Side Redaction
**Check**: Presenters module removed compare for General
```typescript
// Check in browser console
window.__DEBUG_RESPONSE__?.compare_summary
// Original response before redaction
```
**Solution**: Verify role is Pro+ to prevent client-side redaction

**Debug Checklist**:
```
□ User role is Pro, Scholars, or Analytics
□ ui.flags.show_compare = true
□ Server sent compare_summary in response
□ compare_summary has non-empty evidence
□ No client-side redaction applied
```

### "Button Disabled" Issue

**Symptom**: "Run Full Compare" or other button is disabled/grayed out.

**Possible Causes**:

#### 1. Role Insufficient
**Check**: User doesn't have required capability
```typescript
// For "Run Full Compare"
hasCapability(userRole, CAP_READ_LEDGER_FULL)
// Should return: true
```
**Solution**: Upgrade role to Pro or higher

#### 2. External Compare Flag Disabled
**Check**: `flags.external_compare` is false
```typescript
window.uiFlags?.external_compare
// Should return: true (for Pro+)
```
**Solution**:
- Check `feature_flags.py`: `chat.flags.external_compare`
- Ensure set to `true` for your role

#### 3. Loading State
**Check**: Button disabled during API call
```typescript
// Check button state
document.querySelector('button:contains("Run Full Compare")').disabled
// Should be: false (when not loading)
```
**Solution**: Wait for previous operation to complete

#### 4. No External Sources Available
**Check**: Whitelist empty or rate limit reached
```javascript
// Check console for errors
"Rate limit exceeded for domain"
"No external sources in whitelist"
```
**Solution**:
- Check `config/external_sources_whitelist.json`
- Wait for rate limit to reset (1 minute)

#### 5. API Error
**Check**: Previous API call failed
```javascript
// Check network tab for 500 errors
POST /api/factate/compare → 500 Internal Server Error
```
**Solution**:
- Check server logs
- Retry operation
- Report error if persistent

**Debug Checklist**:
```
□ User role has required capability
□ Feature flag enabled for role
□ Not in loading state
□ No rate limit errors
□ API endpoint accessible
□ Network connection stable
```

### "Badge Not Showing" Issue

**Symptom**: Contradiction badge doesn't appear even though contradictions exist.

**Possible Causes**:

#### 1. Role is General
**Check**: Badges are hidden for General users
```typescript
localStorage.getItem('user_role') === 'general'
```
**Solution**: Upgrade to Pro or higher

#### 2. No Contradictions
**Check**: Response has zero contradictions
```javascript
response.contradictions.length === 0
```
**Solution**: This is expected; badge only shows when contradictions exist

#### 3. Badge Flag Disabled
**Check**: `ui.flags.show_badges` is false AND contradictions = 0
```typescript
window.uiFlags?.show_badges === false
```
**Solution**: Enable flag or wait for contradictions to appear

**Debug Checklist**:
```
□ User role is Pro, Scholars, or Analytics
□ Contradictions array has items
□ ui.flags.show_badges = true OR contradictions > 0
```

### "Ledger Won't Expand" Issue

**Symptom**: "Expand Full Trace" button missing or doesn't work.

**Possible Causes**:

#### 1. Role is General
**Check**: General users cannot expand ledger
```typescript
hasCapability(userRole, CAP_READ_LEDGER_FULL) === false
```
**Solution**: Upgrade to Pro or higher

#### 2. No Message ID
**Check**: Cannot fetch full trace without message ID
```javascript
messageId === undefined || messageId === null
```
**Solution**: Ensure chat response includes message ID

#### 3. API Error
**Check**: `/api/debug/redo_trace` endpoint failing
```javascript
GET /api/debug/redo_trace?message_id=123 → 404
```
**Solution**: Check server logs, ensure debug endpoint enabled

#### 4. Already Expanded
**Check**: Ledger is already showing full trace
```typescript
isExpanded === true
```
**Solution**: Click "Collapse" to return to summary view

**Debug Checklist**:
```
□ User role is Pro, Scholars, or Analytics
□ Message ID exists
□ API endpoint /api/debug/redo_trace accessible
□ Not already in expanded state
```

---

## API Routes

### Chat Endpoint

**Route**: `POST /api/chat`

**Request**:
```json
{
  "message": "What is the population of NYC?",
  "allow_external": true
}
```

**Response**:
```json
{
  "answer": "According to the 2020 Census...",
  "evidence": [...],
  "contradictions": [
    {
      "id": "c1",
      "subject": "Population count discrepancy",
      "description": "Different sources...",
      "evidenceAnchor": "evidence-1",
      "severity": "high"
    }
  ],
  "process_trace_summary": [
    { "step": "parse_query", "duration_ms": 10 },
    { "step": "retrieve", "duration_ms": 50 },
    { "step": "rank", "duration_ms": 20 },
    { "step": "generate", "duration_ms": 200 }
  ],
  "compare_summary": {
    "stance_a": "Census reports 8,336,817",
    "stance_b": "Estimates suggest 8.8M",
    "evidence_a": [...],
    "evidence_b": [...]
  },
  "role_applied": "pro"
}
```

### Full Trace Endpoint

**Route**: `GET /api/debug/redo_trace?message_id={id}`

**Response**:
```json
{
  "trace": [
    { "step": "parse_query", "duration_ms": 10 },
    { "step": "retrieve", "duration_ms": 50 },
    { "step": "rank", "duration_ms": 20 },
    { "step": "generate", "duration_ms": 200 },
    { "step": "validate", "duration_ms": 15 },
    { "step": "finalize", "duration_ms": 5 }
  ]
}
```

### Full Compare Endpoint

**Route**: `POST /api/factate/compare`

**Request**:
```json
{
  "question": "What is the population of NYC?",
  "stance_a": "Census reports 8,336,817",
  "stance_b": "Estimates suggest 8.8M",
  "allow_external": true
}
```

**Response**:
```json
{
  "stance_a": "Census reports 8,336,817",
  "stance_b": "Estimates suggest 8.8M",
  "evidence_a": [...],
  "evidence_b": [
    {
      "text": "Wikipedia: NYC population...",
      "label": "Wikipedia",
      "url": "https://en.wikipedia.org/wiki/NYC",
      "is_external": true
    },
    ...
  ]
}
```

---

## Feature Flags

### UI Flags

Located in: `app/config/flags.ts`

```typescript
interface UIFlags {
  show_ledger: boolean;          // Show process ledger
  show_compare: boolean;          // Show compare card
  show_badges: boolean;           // Show contradiction badge
  show_debug: boolean;            // Show debug info
  show_graph: boolean;            // Show knowledge graph
  show_contradictions: boolean;   // Show contradictions in evidence
  show_hypothesis: boolean;       // Show hypothesis CTAs
  show_aura: boolean;             // Show AURA CTAs
}
```

**Default Values** (by role):

```typescript
// General
{
  show_ledger: true,    // Limited to 4 lines
  show_compare: false,  // Hidden
  show_badges: false,   // Hidden
  show_hypothesis: false,
  show_aura: false
}

// Pro/Scholars/Analytics
{
  show_ledger: true,    // Expandable
  show_compare: true,   // Visible
  show_badges: true,    // Visible
  show_hypothesis: true,  // Pro/Analytics only
  show_aura: true         // Pro/Analytics only
}
```

### Server Flags

Located in: `feature_flags.py`

```python
@dataclass
class ChatFlags:
    external_compare: bool = False   # Allow external sources in compare
    max_trace_lines: int = 4         # Max lines for General
    show_prompts: bool = False       # Show raw prompts (Pro+)
    show_provenance: bool = False    # Show provenance (Pro+)
```

### Checking Flags

**Client-Side**:
```typescript
import { getFeatureFlags } from './config/flags';

const flags = getFeatureFlags(userRole);

if (flags.show_compare) {
  // Show compare card
}
```

**Server-Side**:
```python
from feature_flags import get_chat_flags

flags = get_chat_flags(user_role)

if flags.external_compare:
    # Allow external sources
```

---

## Related Documentation

- [RBAC Roles and Capabilities](../core/rbac/roles.py)
- [External Compare Configuration](external-compare.md)
- [Client-Side Redaction](PRESENTERS_IMPLEMENTATION.md)
- [Accessibility Implementation](ACCESSIBILITY_IMPLEMENTATION.md)
- [E2E Tests](E2E_TESTS_IMPLEMENTATION.md)

---

## Quick Reference

### Component Locations

| Component | File Path |
|-----------|-----------|
| ProcessLedger | `app/components/ProcessLedger.tsx` |
| CompareCard | `app/components/CompareCard.tsx` |
| ContradictionBadge | `app/components/ContradictionBadge.tsx` |
| ChatAnswer | `app/views/ChatAnswer.tsx` |

### Key Imports

```typescript
import ProcessLedger from '@/app/components/ProcessLedger';
import CompareCard from '@/app/components/CompareCard';
import ContradictionBadge from '@/app/components/ContradictionBadge';
import { getUserRole } from '@/app/state/session';
import { hasCapability, CAP_READ_LEDGER_FULL } from '@/app/lib/roles';
```

### Common Tasks

**Enable Compare for All Users**:
```typescript
// app/config/flags.ts
export const UI_FLAGS_DEFAULT = {
  show_compare: true,  // Change to true
};
```

**Adjust Ledger Line Limit**:
```python
# feature_flags.py
@dataclass
class ChatFlags:
    max_trace_lines: int = 8  # Change from 4
```

**Show Badges Always**:
```typescript
// app/config/flags.ts
show_badges: true  // Shows even when contradictions = 0
```

---

## Version History

- **v1.0** (2025-10-30): Initial documentation
  - Process Ledger documentation
  - Compare Card documentation
  - Contradiction Badge documentation
  - Role-based access matrix
  - Troubleshooting section
  - API routes and feature flags

---

**Questions or Issues?**

- Check [Troubleshooting](#troubleshooting) section
- Review [Feature Flags](#feature-flags)
- See [E2E Tests](E2E_TESTS_IMPLEMENTATION.md) for examples
- Contact: support@upward.ai
