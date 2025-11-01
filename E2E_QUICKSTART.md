# E2E Tests Quick Start

## Overview

Playwright E2E tests covering Pro vs General user flows with automatic screenshot capture.

**Test Scenarios**: 17  
**Browsers**: Chrome, Firefox, Safari, Mobile

## Quick Setup

### 1. Install

```bash
npm install -D @playwright/test
npx playwright install
```

### 2. Run Tests

```bash
# Run all tests
npx playwright test

# Run specific browser
npx playwright test --project=chromium

# Run with UI (interactive)
npx playwright test --ui

# Debug mode
npx playwright test --debug
```

### 3. View Results

```bash
# HTML report
npx playwright show-report

# Trace viewer (on failure)
npx playwright show-trace test-results/traces/trace-1.zip
```

## Test Scenarios

### Pro User (9 tests)
1. ✅ Contradiction badge visible
2. ✅ Tooltip opens on click
3. ✅ Compare card visible
4. ✅ External compare works
5. ✅ Process ledger visible
6. ✅ Ledger expands to full trace
7. ✅ Hypothesis promotion succeeds
8. ✅ AURA project creation succeeds
9. ✅ Complete Pro flow

### General User (6 tests)
1. ✅ Contradiction badge hidden
2. ✅ Compare card hidden
3. ✅ Ledger limited to 4 lines
4. ✅ Promote CTA hidden
5. ✅ AURA CTA hidden
6. ✅ Complete General flow with redactions

### Comparison (2 tests)
1. ✅ Pro shows all, General shows limited
2. ✅ Screenshots captured on failure

## Screenshot Capture

**Automatic on failure**:
```typescript
// playwright.config.ts
screenshot: 'only-on-failure'
```

**Manual capture**:
```typescript
await page.screenshot({ path: 'screenshot.png', fullPage: true });
```

**Location**: `test-results/screenshots/`

## CI/CD

Tests run automatically on push/PR:

```yaml
# .github/workflows/e2e-tests.yml
- Chrome
- Firefox
- Safari
```

**Artifacts**:
- Screenshots (on failure)
- Videos (on failure)
- HTML reports
- Traces

## Files

```
playwright.config.ts              Configuration
tests/e2e/chat-ui.spec.ts         Test scenarios (1,100 lines)
.github/workflows/e2e-tests.yml   CI workflow
test-results/                     Output directory
  screenshots/                    Failure screenshots
  videos/                         Failure videos
  traces/                         Debug traces
```

## Acceptance Criteria

✅ **Scenarios pass locally**  
✅ **Scenarios pass in CI**  
✅ **Screenshots saved on failure**

---

**Full docs**: `E2E_TESTS_IMPLEMENTATION.md`  
**Ready to run** 🚀
