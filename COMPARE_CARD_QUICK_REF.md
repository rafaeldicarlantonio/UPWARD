# CompareCard Quick Reference

## Import

```typescript
import CompareCard, { CompareSummary, EvidenceItem } from '@/app/components/CompareCard';
```

## Basic Usage

```typescript
<CompareCard
  compareSummary={response.compare_summary}
  userRole={session.metadata.primaryRole}
  allowExternalCompare={session.uiFlags.external_compare}
  messageId={response.message_id}
/>
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `compareSummary` | `CompareSummary` | ✅ | The comparison data |
| `userRole` | `Role` | ✅ | Current user's role |
| `allowExternalCompare` | `boolean` | ❌ | Enable external compare (default: false) |
| `messageId` | `string` | ❌ | For "Run full compare" button |
| `apiBaseUrl` | `string` | ❌ | API base (default: '/api') |
| `onCompareComplete` | `(result: CompareSummary) => void` | ❌ | Callback after compare |
| `className` | `string` | ❌ | Custom CSS class |
| `testId` | `string` | ❌ | Test ID (default: 'compare-card') |

## Types

```typescript
interface CompareSummary {
  stance_a: string;
  stance_b: string;
  recommendation?: 'a' | 'b' | 'neither' | 'both';
  confidence?: number;
  internal_evidence: EvidenceItem[];
  external_evidence?: EvidenceItem[];
  metadata?: {
    sources_used?: { internal: number; external: number };
    used_external?: boolean;
    tie_break?: string;
  };
}

interface EvidenceItem {
  text: string;
  confidence?: number;
  source?: string;
  url?: string;         // External only
  host?: string;        // External only
  label?: string;       // External only
  fetched_at?: string;  // External only
}
```

## States

| State | Display | Run Button |
|-------|---------|------------|
| Initial | Stances + evidence | Enabled (if allowed) |
| Loading | Spinner, "Running..." | Disabled |
| Success | Updated summary | Enabled |
| Error | Error message | Enabled |

## Role Gating

| Role | Can Run External Compare |
|------|--------------------------|
| General | ❌ No |
| Pro | ✅ Yes |
| Scholars | ✅ Yes |
| Analytics | ✅ Yes |
| Ops | ✅ Yes |

**Required**: `CAP_READ_LEDGER_FULL` + `allowExternalCompare === true`

## Truncation Policy

| Source | Max Chars |
|--------|-----------|
| Wikipedia | 480 |
| arXiv | 640 |
| PubMed | 500 |
| Google Scholar | 400 |
| Semantic Scholar | 450 |
| Default | 480 |

## API Call

```typescript
POST /factate/compare

Request:
{
  "message_id": "msg_123",
  "allow_external": true
}

Response:
{
  "compare_summary": { ... },
  "used_external": true,
  "sources": { internal: 2, external: 2 },
  "contradictions": []
}
```

## Testing

```bash
# Python structure tests
pytest tests/ui/test_compare_card_structure.py -v

# TypeScript tests
npm test CompareCard.test.tsx
```

**50 Python tests** + **60+ TypeScript tests** ✅

## Styling

**CSS File**: `app/styles/compare.css`

**Key Classes**:
- `.compare-card` - Main container
- `.compare-stances` - Stance grid
- `.evidence-item.internal` - Internal evidence
- `.evidence-item.external` - External evidence
- `.compare-card-run-button` - Run button
- `.compare-card-error` - Error display

## Common Issues

**Q**: Button disabled for Pro user?  
**A**: Check `allowExternalCompare` is true.

**Q**: External not truncating?  
**A**: Verify `label` field is set correctly.

**Q**: API call fails?  
**A**: Check messageId and endpoint `/factate/compare` exists.

## Security Notes

⚠️ **Client-side checks are UX only**  
Server MUST validate:
- JWT and roles
- External compare permissions
- Rate limits
- Content sanitization

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Files

```
app/components/CompareCard.tsx         453 lines
app/styles/compare.css                 599 lines
tests/ui/CompareCard.test.tsx          855 lines
tests/ui/test_compare_card_structure.py 449 lines
app/examples/ChatWithCompare.tsx       234 lines
```

**Total**: 2,590 lines

## Version

**v1.0** - 2025-10-30  
**Status**: ✅ Production ready
