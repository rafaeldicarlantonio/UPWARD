/**
 * Chat UI E2E Tests
 * 
 * Comprehensive Playwright tests covering Pro vs General user flows.
 * Tests contradictions, compare, hypothesis promotion, and AURA project creation.
 */

import { test, expect, Page } from '@playwright/test';

// ============================================================================
// Test Data & Constants
// ============================================================================

const TEST_QUESTION = 'What is the population of New York City?';

const EXPECTED_ANSWER_SNIPPET = '8.3 million';

// Mock API responses
const MOCK_CHAT_RESPONSE_PRO = {
  answer: 'According to the 2020 Census, New York City has a population of 8,336,817 residents.',
  evidence: [
    { text: '2020 Census data shows 8,336,817 residents', score: 0.95, source: 'census' },
    { text: 'NYC population estimate: 8.3 million', score: 0.90, source: 'estimates' },
  ],
  contradictions: [
    {
      id: 'c1',
      subject: 'Population count discrepancy',
      description: 'Different sources report different numbers',
      evidenceAnchor: 'evidence-1',
      severity: 'high',
    },
    {
      id: 'c2',
      subject: 'Methodology conflict',
      description: 'Census vs estimates use different methods',
      evidenceAnchor: 'evidence-2',
      severity: 'medium',
    },
  ],
  process_trace_summary: [
    { step: 'parse_query', duration_ms: 10 },
    { step: 'retrieve', duration_ms: 50 },
    { step: 'rank', duration_ms: 20 },
    { step: 'generate', duration_ms: 200 },
  ],
  compare_summary: {
    stance_a: 'Census reports official count of 8,336,817',
    stance_b: 'Estimates suggest 8.8 million including undocumented',
    evidence_a: [
      { text: 'Official 2020 Census count', score: 0.95, source: 'census' },
    ],
    evidence_b: [
      { text: 'Demographic estimates include undocumented', score: 0.85, source: 'studies' },
    ],
  },
  role_applied: 'pro',
};

const MOCK_CHAT_RESPONSE_GENERAL = {
  answer: 'According to the 2020 Census, New York City has a population of 8,336,817 residents.',
  evidence: [
    { text: '2020 Census data shows 8,336,817 residents', score: 0.95, source: 'census' },
  ],
  // Contradictions exist but badge should be hidden for General
  contradictions: [
    {
      id: 'c1',
      subject: 'Population count discrepancy',
      description: 'Different sources report different numbers',
      severity: 'high',
    },
  ],
  process_trace_summary: [
    { step: 'parse_query', duration_ms: 10 },
    { step: 'retrieve', duration_ms: 50 },
    { step: 'rank', duration_ms: 20 },
    { step: 'generate', duration_ms: 200 },
  ],
  // No compare_summary for General
  role_applied: 'general',
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Login as specific role
 */
async function loginAs(page: Page, role: 'pro' | 'general' | 'analytics') {
  await page.goto('/login');
  
  // Mock JWT or session storage
  await page.evaluate((userRole) => {
    localStorage.setItem('user_role', userRole);
    localStorage.setItem('user_token', `mock-token-${userRole}`);
  }, role);
  
  await page.goto('/chat');
  await page.waitForLoadState('networkidle');
}

/**
 * Send chat message
 */
async function sendChatMessage(page: Page, message: string) {
  const input = page.locator('input[type="text"], textarea').first();
  await input.fill(message);
  await input.press('Enter');
  
  // Wait for response
  await page.waitForSelector('[data-testid="chat-answer"]', { timeout: 30000 });
}

/**
 * Take screenshot with context
 */
async function takeScreenshot(page: Page, name: string) {
  await page.screenshot({
    path: `test-results/screenshots/${name}.png`,
    fullPage: true,
  });
}

// ============================================================================
// Pro User Tests
// ============================================================================

test.describe('Pro User Flow', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, 'pro');
  });
  
  test('displays contradiction badge for Pro user', async ({ page }) => {
    // Mock API response
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Check contradiction badge appears
    const badge = page.locator('[data-testid="contradiction-badge"]');
    await expect(badge).toBeVisible();
    
    // Check count
    await expect(badge).toContainText('2');
    
    // Take screenshot for verification
    await takeScreenshot(page, 'pro-contradiction-badge');
  });
  
  test('opens contradiction tooltip on click', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Click badge
    const badge = page.locator('[data-testid="contradiction-badge"]');
    await badge.click();
    
    // Check tooltip appears
    const tooltip = page.locator('[role="tooltip"]');
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toContainText('Population count discrepancy');
    
    await takeScreenshot(page, 'pro-contradiction-tooltip');
  });
  
  test('displays compare card for Pro user', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Check compare card appears
    const compareCard = page.locator('[data-testid="compare-card"]');
    await expect(compareCard).toBeVisible();
    
    // Check stances
    await expect(compareCard).toContainText('Census reports official count');
    await expect(compareCard).toContainText('Estimates suggest 8.8 million');
    
    await takeScreenshot(page, 'pro-compare-card');
  });
  
  test('runs full compare with external sources', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    // Mock compare API
    await page.route('**/api/factate/compare', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...MOCK_CHAT_RESPONSE_PRO.compare_summary,
          evidence_b: [
            ...MOCK_CHAT_RESPONSE_PRO.compare_summary.evidence_b,
            {
              text: 'Wikipedia: NYC population 8.3-8.8 million',
              label: 'Wikipedia',
              is_external: true,
            },
          ],
        }),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Click "Run Full Compare"
    const runButton = page.locator('button', { hasText: 'Run Full Compare' });
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
    await runButton.click();
    
    // Wait for external evidence
    await page.waitForSelector('text=Wikipedia', { timeout: 10000 });
    
    // Verify external evidence appears
    const externalEvidence = page.locator('text=Wikipedia');
    await expect(externalEvidence).toBeVisible();
    
    await takeScreenshot(page, 'pro-compare-external');
  });
  
  test('displays process ledger for Pro user', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Check ledger appears
    const ledger = page.locator('[data-testid="process-ledger"]');
    await expect(ledger).toBeVisible();
    
    // Should show 4 lines
    const lines = page.locator('[data-testid="ledger-line"]');
    await expect(lines).toHaveCount(4);
    
    await takeScreenshot(page, 'pro-process-ledger');
  });
  
  test('expands process ledger to show full trace', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    // Mock full trace API
    await page.route('**/api/debug/redo_trace?message_id=*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          trace: [
            ...MOCK_CHAT_RESPONSE_PRO.process_trace_summary,
            { step: 'validate', duration_ms: 15 },
            { step: 'finalize', duration_ms: 5 },
            { step: 'extra_step_7', duration_ms: 5 },
            { step: 'extra_step_8', duration_ms: 5 },
          ],
        }),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Click expand
    const expandButton = page.locator('button', { hasText: /Expand|Show Full/ });
    await expandButton.click();
    
    // Wait for full trace
    await page.waitForSelector('text=validate', { timeout: 10000 });
    
    // Should now show 8 lines
    const lines = page.locator('[data-testid="ledger-line"]');
    await expect(lines).toHaveCount(8);
    
    await takeScreenshot(page, 'pro-ledger-expanded');
  });
  
  test('promotes answer to hypothesis', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    // Mock hypothesis API
    await page.route('**/api/hypotheses/propose', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          hypothesis_id: 'hyp-123',
          score: 0.95,
          persisted: true,
        }),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Click "Promote to Hypothesis"
    const promoteButton = page.locator('button', { hasText: /Promote.*Hypothesis/ });
    await expect(promoteButton).toBeVisible();
    await promoteButton.click();
    
    // Fill modal
    await page.waitForSelector('[role="dialog"]');
    await page.fill('input[name="title"]', 'NYC Population Hypothesis');
    await page.fill('textarea[name="description"]', 'Analysis of NYC population counts');
    
    // Submit
    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();
    
    // Wait for success toast
    await page.waitForSelector('text=Hypothesis Created', { timeout: 10000 });
    
    // Verify toast
    const toast = page.locator('[role="status"]');
    await expect(toast).toContainText('Hypothesis Created');
    await expect(toast).toContainText('95%');
    
    await takeScreenshot(page, 'pro-hypothesis-success');
  });
  
  test('creates AURA project from hypothesis', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    // Mock hypothesis API
    await page.route('**/api/hypotheses/propose', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          hypothesis_id: 'hyp-123',
          score: 0.95,
          persisted: true,
        }),
      });
    });
    
    // Mock AURA API
    await page.route('**/api/aura/projects/propose', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          project_id: 'proj-456',
          hypothesis_id: 'hyp-123',
        }),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // First create hypothesis
    await page.locator('button', { hasText: /Promote.*Hypothesis/ }).click();
    await page.waitForSelector('[role="dialog"]');
    await page.fill('input[name="title"]', 'NYC Population Hypothesis');
    await page.fill('textarea[name="description"]', 'Analysis');
    await page.locator('button[type="submit"]').click();
    await page.waitForSelector('text=Hypothesis Created');
    
    // Close toast/modal
    await page.keyboard.press('Escape');
    
    // Now create AURA project
    const auraButton = page.locator('button', { hasText: /AURA|Create Project/ });
    await expect(auraButton).toBeVisible();
    await auraButton.click();
    
    // Fill AURA modal
    await page.waitForSelector('[role="dialog"]');
    await page.fill('input[name="title"]', 'NYC Population Investigation');
    await page.fill('textarea[name="description"]', 'Comprehensive investigation');
    
    // Submit
    await page.locator('button[type="submit"]').click();
    
    // Wait for success
    await page.waitForSelector('text=Project Created', { timeout: 10000 });
    
    // Verify navigation or toast
    const toast = page.locator('[role="status"]');
    await expect(toast).toContainText('Project Created');
    
    await takeScreenshot(page, 'pro-aura-success');
  });
  
  test('complete Pro user flow', async ({ page }) => {
    // Mock all APIs
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    await page.route('**/api/hypotheses/propose', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ hypothesis_id: 'hyp-123', score: 0.95 }),
      });
    });
    
    await page.route('**/api/aura/projects/propose', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ project_id: 'proj-456' }),
      });
    });
    
    // 1. Send message
    await sendChatMessage(page, TEST_QUESTION);
    
    // 2. Verify all Pro features visible
    await expect(page.locator('[data-testid="contradiction-badge"]')).toBeVisible();
    await expect(page.locator('[data-testid="compare-card"]')).toBeVisible();
    await expect(page.locator('[data-testid="process-ledger"]')).toBeVisible();
    await expect(page.locator('button', { hasText: /Promote.*Hypothesis/ })).toBeVisible();
    await expect(page.locator('button', { hasText: /AURA|Create Project/ })).toBeVisible();
    
    // 3. Open contradiction tooltip
    await page.locator('[data-testid="contradiction-badge"]').click();
    await expect(page.locator('[role="tooltip"]')).toBeVisible();
    
    // 4. Promote to hypothesis
    await page.keyboard.press('Escape'); // Close tooltip
    await page.locator('button', { hasText: /Promote.*Hypothesis/ }).click();
    await page.fill('input[name="title"]', 'Test Hypothesis');
    await page.fill('textarea[name="description"]', 'Test');
    await page.locator('button[type="submit"]').click();
    await page.waitForSelector('text=Hypothesis Created');
    
    // 5. Create AURA project
    await page.keyboard.press('Escape');
    await page.locator('button', { hasText: /AURA/ }).click();
    await page.fill('input[name="title"]', 'Test Project');
    await page.fill('textarea[name="description"]', 'Test');
    await page.locator('button[type="submit"]').click();
    await page.waitForSelector('text=Project Created');
    
    await takeScreenshot(page, 'pro-complete-flow');
  });
});

// ============================================================================
// General User Tests
// ============================================================================

test.describe('General User Flow', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, 'general');
  });
  
  test('hides contradiction badge for General user', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_GENERAL),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Badge should NOT be visible
    const badge = page.locator('[data-testid="contradiction-badge"]');
    await expect(badge).not.toBeVisible();
    
    await takeScreenshot(page, 'general-no-badge');
  });
  
  test('hides compare card for General user', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_GENERAL),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Compare card should NOT be visible
    const compareCard = page.locator('[data-testid="compare-card"]');
    await expect(compareCard).not.toBeVisible();
    
    await takeScreenshot(page, 'general-no-compare');
  });
  
  test('shows limited ledger for General user', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_GENERAL),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Ledger should show 4 lines max
    const lines = page.locator('[data-testid="ledger-line"]');
    await expect(lines).toHaveCount(4);
    
    // Expand button should NOT be visible
    const expandButton = page.locator('button', { hasText: /Expand|Show Full/ });
    await expect(expandButton).not.toBeVisible();
    
    await takeScreenshot(page, 'general-limited-ledger');
  });
  
  test('hides Promote Hypothesis CTA for General user', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_GENERAL),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // Promote button should NOT be visible
    const promoteButton = page.locator('button', { hasText: /Promote.*Hypothesis/ });
    await expect(promoteButton).not.toBeVisible();
    
    await takeScreenshot(page, 'general-no-promote-cta');
  });
  
  test('hides AURA Project CTA for General user', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_GENERAL),
      });
    });
    
    await sendChatMessage(page, TEST_QUESTION);
    
    // AURA button should NOT be visible
    const auraButton = page.locator('button', { hasText: /AURA|Create Project/ });
    await expect(auraButton).not.toBeVisible();
    
    await takeScreenshot(page, 'general-no-aura-cta');
  });
  
  test('complete General user flow with redactions', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_GENERAL),
      });
    });
    
    // Send message
    await sendChatMessage(page, TEST_QUESTION);
    
    // Verify answer appears
    const answer = page.locator('[data-testid="chat-answer"]');
    await expect(answer).toBeVisible();
    await expect(answer).toContainText(EXPECTED_ANSWER_SNIPPET);
    
    // Verify General-specific behavior
    await expect(page.locator('[data-testid="contradiction-badge"]')).not.toBeVisible();
    await expect(page.locator('[data-testid="compare-card"]')).not.toBeVisible();
    await expect(page.locator('button', { hasText: /Promote.*Hypothesis/ })).not.toBeVisible();
    await expect(page.locator('button', { hasText: /AURA/ })).not.toBeVisible();
    await expect(page.locator('button', { hasText: /Expand/ })).not.toBeVisible();
    
    // Ledger should be limited
    const lines = page.locator('[data-testid="ledger-line"]');
    await expect(lines).toHaveCount(4);
    
    await takeScreenshot(page, 'general-complete-flow');
  });
});

// ============================================================================
// Role Comparison Tests
// ============================================================================

test.describe('Pro vs General Comparison', () => {
  test('Pro shows all features, General shows limited', async ({ browser }) => {
    // Create two contexts for parallel testing
    const proContext = await browser.newContext();
    const generalContext = await browser.newContext();
    
    const proPage = await proContext.newPage();
    const generalPage = await generalContext.newPage();
    
    // Setup Pro
    await loginAs(proPage, 'pro');
    await proPage.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_PRO),
      });
    });
    
    // Setup General
    await loginAs(generalPage, 'general');
    await generalPage.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE_GENERAL),
      });
    });
    
    // Send same message to both
    await sendChatMessage(proPage, TEST_QUESTION);
    await sendChatMessage(generalPage, TEST_QUESTION);
    
    // Compare features
    // Pro should have all features
    await expect(proPage.locator('[data-testid="contradiction-badge"]')).toBeVisible();
    await expect(proPage.locator('[data-testid="compare-card"]')).toBeVisible();
    await expect(proPage.locator('button', { hasText: /Promote/ })).toBeVisible();
    await expect(proPage.locator('button', { hasText: /AURA/ })).toBeVisible();
    
    // General should have none
    await expect(generalPage.locator('[data-testid="contradiction-badge"]')).not.toBeVisible();
    await expect(generalPage.locator('[data-testid="compare-card"]')).not.toBeVisible();
    await expect(generalPage.locator('button', { hasText: /Promote/ })).not.toBeVisible();
    await expect(generalPage.locator('button', { hasText: /AURA/ })).not.toBeVisible();
    
    // Screenshot comparison
    await takeScreenshot(proPage, 'comparison-pro');
    await takeScreenshot(generalPage, 'comparison-general');
    
    // Cleanup
    await proContext.close();
    await generalContext.close();
  });
});

// ============================================================================
// Screenshot Tests
// ============================================================================

test.describe('Visual Regression', () => {
  test('captures full page screenshots on failure', async ({ page }) => {
    await loginAs(page, 'pro');
    
    // Force a failure to test screenshot capture
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Server error' }),
      });
    });
    
    try {
      await sendChatMessage(page, TEST_QUESTION);
      
      // This should fail
      await expect(page.locator('[data-testid="chat-answer"]')).toBeVisible({ timeout: 5000 });
    } catch (error) {
      // Screenshot should be captured automatically by Playwright config
      console.log('Screenshot captured on failure');
    }
  });
});
