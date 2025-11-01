# Presenters Module - Quick Reference

## Overview

Client-side defensive redaction layer that protects users from server-side redaction failures.

**Security Principle**: Defense in depth - client validates and fixes server responses.

## Quick Start

```typescript
import { redactChatResponseWithTelemetry } from '@/app/lib/presenters';
import { getUserRole } from '@/app/state/session';

// Apply defensive redaction to all chat responses
const response = await fetch('/api/chat', { body: message }).then(r => r.json());
const userRole = getUserRole();
const safeResponse = redactChatResponseWithTelemetry(response, userRole);

// Now safe to display
return <ChatAnswer data={safeResponse} />;
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `redactChatResponseWithTelemetry()` | **Main entry point** - validates, reports, and redacts |
| `redactChatResponse()` | Applies redaction without telemetry |
| `validateRedaction()` | Checks if server properly redacted |
| `getRedactionPolicy()` | Gets role-specific redaction rules |

## Redaction Rules

### General Role
- ❌ Max 4 ledger lines
- ❌ No prompts
- ❌ No provenance
- ❌ No external evidence
- ❌ Max 480 chars per snippet

### Pro/Scholars/Analytics
- ✅ Unlimited ledger lines
- ✅ Show prompts
- ✅ Show provenance
- ✅ External evidence allowed (truncated)
- ✅ Max 800-1200 chars per snippet

## Server Misbehavior Protection

| Server Failure | Client Protection |
|----------------|-------------------|
| Sends 8 ledger lines to General | Truncates to 4 lines |
| Sends prompts to General | Strips all prompt fields |
| Sends external evidence to General | Strips all external items |
| Sends 10,000-char snippet | Truncates to policy limit |

## Telemetry

When server fails to redact:
- Event: `redaction.client_side_applied`
- Data: `{ role, failureType, messageId, timestamp }`

**Alert**: If this event fires in production, server redaction is broken.

## Testing

```bash
# Run all tests
python3 -m pytest tests/ui/test_presenters_structure.py

# Expected: 58 passed in 0.03s
```

## Files

```
app/lib/presenters.ts                   550 lines - Core module
tests/ui/Presenters.test.ts             950 lines - 80+ TypeScript tests
tests/ui/test_presenters_structure.py   335 lines - 58 Python tests
app/examples/SafeChatHandler.tsx        220 lines - Integration example
```

## Status

✅ **COMPLETE** - All 58 tests passing (100%)

See `PRESENTERS_IMPLEMENTATION.md` for full documentation.
