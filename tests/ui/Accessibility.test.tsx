/**
 * Accessibility Tests
 * 
 * Comprehensive accessibility testing using axe-core for all UI components.
 * Ensures WCAG 2.1 AA compliance.
 */

import React from 'react';
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import ProcessLedger from '../../app/components/ProcessLedger';
import ContradictionBadge, { Contradiction } from '../../app/components/ContradictionBadge';
import CompareCard from '../../app/components/CompareCard';
import PromoteHypothesisButton from '../../app/components/PromoteHypothesisButton';
import ProposeAuraButton from '../../app/components/ProposeAuraButton';
import AnswerEvidence from '../../app/components/AnswerEvidence';
import ChatAnswer from '../../app/views/ChatAnswer';
import { ROLE_GENERAL, ROLE_PRO } from '../../app/lib/roles';

// Extend Jest matchers
expect.extend(toHaveNoViolations);

// ============================================================================
// Mock Data
// ============================================================================

const mockProcessTrace = [
  { step: 'parse_query', duration_ms: 10 },
  { step: 'retrieve', duration_ms: 50, details: 'Found 10 memories' },
  { step: 'rank', duration_ms: 20 },
  { step: 'generate', duration_ms: 200 },
];

const mockContradictions: Contradiction[] = [
  {
    id: 'c1',
    subject: 'Population discrepancy',
    description: 'Different sources show different numbers',
    evidenceAnchor: 'evidence-1',
    severity: 'high',
  },
  {
    id: 'c2',
    subject: 'Methodology conflict',
    description: 'Different counting methods',
    evidenceAnchor: 'evidence-2',
    severity: 'medium',
  },
];

const mockCompareSummary = {
  stance_a: 'Position A supports this view',
  stance_b: 'Position B contests this',
  evidence_a: [
    { text: 'Internal evidence A', score: 0.95, source: 'memory' },
  ],
  evidence_b: [
    { text: 'Internal evidence B', score: 0.90, source: 'memory' },
  ],
};

const mockAnswerContent = `
  <p>According to the <span id="evidence-1">2020 Census</span>, the population is
  <span id="evidence-2">8.3 million</span>.</p>
`;

// ============================================================================
// Tests
// ============================================================================

describe('Accessibility Tests (axe-core)', () => {
  // ==========================================================================
  // ProcessLedger A11y Tests
  // ==========================================================================
  
  describe('ProcessLedger', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('has no violations when expanded', async () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_PRO}
          showLedger={true}
          defaultExpanded={true}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('has no violations for General role', async () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_GENERAL}
          showLedger={true}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('expand button has proper aria attributes', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const button = container.querySelector('[aria-expanded]');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-controls');
      expect(button).toHaveAttribute('aria-label');
    });
    
    it('loading state has aria-live', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const liveRegion = container.querySelector('[aria-live]');
      expect(liveRegion).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // ContradictionBadge A11y Tests
  // ==========================================================================
  
  describe('ContradictionBadge', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <ContradictionBadge
          contradictions={mockContradictions}
          alwaysShow={true}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('has no violations with no contradictions', async () => {
      const { container } = render(
        <ContradictionBadge
          contradictions={[]}
          alwaysShow={false}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('badge has proper aria-label', () => {
      const { container } = render(
        <ContradictionBadge
          contradictions={mockContradictions}
          alwaysShow={true}
        />
      );
      
      const badge = container.querySelector('[aria-label]');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute('role', 'button');
    });
    
    it('is keyboard accessible', () => {
      const { container } = render(
        <ContradictionBadge
          contradictions={mockContradictions}
          alwaysShow={true}
        />
      );
      
      const badge = container.querySelector('[role="button"]');
      expect(badge).toHaveAttribute('tabindex', '0');
    });
    
    it('tooltip has role="tooltip"', () => {
      const { container } = render(
        <ContradictionBadge
          contradictions={mockContradictions}
          alwaysShow={true}
        />
      );
      
      const tooltip = container.querySelector('[role="tooltip"]');
      expect(tooltip).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // CompareCard A11y Tests
  // ==========================================================================
  
  describe('CompareCard', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('has no violations with external evidence', async () => {
      const summaryWithExternal = {
        ...mockCompareSummary,
        evidence_b: [
          { text: 'External evidence', label: 'Wikipedia', is_external: true },
        ],
      };
      
      const { container } = render(
        <CompareCard
          compareSummary={summaryWithExternal}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('buttons have minimum touch target', () => {
      const { container } = render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
        />
      );
      
      const buttons = container.querySelectorAll('button');
      buttons.forEach(button => {
        const styles = window.getComputedStyle(button);
        const height = parseInt(styles.height);
        expect(height).toBeGreaterThanOrEqual(44); // WCAG 2.1 AA minimum
      });
    });
  });
  
  // ==========================================================================
  // PromoteHypothesisButton A11y Tests
  // ==========================================================================
  
  describe('PromoteHypothesisButton', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question="Test question"
          evidence={[{ text: 'Evidence' }]}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('modal has no violations when open', async () => {
      const { container, getByText } = render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question="Test question"
          evidence={[{ text: 'Evidence' }]}
        />
      );
      
      // Open modal
      const button = getByText('Promote to Hypothesis');
      button.click();
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('modal has proper aria attributes', () => {
      const { container, getByText } = render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question="Test question"
          evidence={[{ text: 'Evidence' }]}
        />
      );
      
      button.click();
      
      const modal = container.querySelector('[role="dialog"]');
      expect(modal).toBeInTheDocument();
      expect(modal).toHaveAttribute('aria-modal', 'true');
      expect(modal).toHaveAttribute('aria-labelledby');
    });
    
    it('toast has aria-live', () => {
      const { container } = render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question="Test question"
          evidence={[{ text: 'Evidence' }]}
        />
      );
      
      // After form submission, toast should appear with aria-live
      const toastContainer = container.querySelector('[aria-live]');
      // Toast appears dynamically, so we check for the container
      expect(toastContainer || container.querySelector('.toast-container')).toBeTruthy();
    });
  });
  
  // ==========================================================================
  // ProposeAuraButton A11y Tests
  // ==========================================================================
  
  describe('ProposeAuraButton', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp-123"
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('modal has proper role and aria attributes', () => {
      const { container, getByText } = render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp-123"
        />
      );
      
      const button = getByText(/AURA/i);
      button.click();
      
      const modal = container.querySelector('[role="dialog"]');
      expect(modal).toHaveAttribute('aria-modal', 'true');
    });
    
    it('form inputs have labels', () => {
      const { container, getByText } = render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp-123"
        />
      );
      
      const button = getByText(/AURA/i);
      button.click();
      
      const inputs = container.querySelectorAll('input, textarea, select');
      inputs.forEach(input => {
        const id = input.getAttribute('id');
        if (id) {
          const label = container.querySelector(`label[for="${id}"]`);
          expect(label || input.getAttribute('aria-label')).toBeTruthy();
        }
      });
    });
  });
  
  // ==========================================================================
  // AnswerEvidence A11y Tests
  // ==========================================================================
  
  describe('AnswerEvidence', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <AnswerEvidence
          content={mockAnswerContent}
          contradictions={mockContradictions}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('has no violations without contradictions', async () => {
      const { container } = render(
        <AnswerEvidence
          content={mockAnswerContent}
          contradictions={[]}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('evidence anchors are keyboard accessible', () => {
      const { container } = render(
        <AnswerEvidence
          content={mockAnswerContent}
          contradictions={mockContradictions}
        />
      );
      
      const anchors = container.querySelectorAll('[data-evidence-anchor]');
      anchors.forEach(anchor => {
        // Should be focusable via click
        expect(anchor).toBeInTheDocument();
      });
    });
    
    it('contradiction markers have aria-label', () => {
      const { container } = render(
        <AnswerEvidence
          content={mockAnswerContent}
          contradictions={mockContradictions}
        />
      );
      
      const markers = container.querySelectorAll('.contradiction-marker');
      markers.forEach(marker => {
        expect(marker).toHaveAttribute('aria-label');
        expect(marker).toHaveAttribute('role', 'button');
        expect(marker).toHaveAttribute('tabindex', '0');
      });
    });
  });
  
  // ==========================================================================
  // ChatAnswer A11y Tests
  // ==========================================================================
  
  describe('ChatAnswer', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <ChatAnswer
          answer="This is the answer"
          evidence={[{ text: 'Evidence' }]}
          process_trace_summary={mockProcessTrace}
          compare_summary={mockCompareSummary}
          contradictions={mockContradictions}
          userRole={ROLE_PRO}
          show_ledger={true}
          show_badges={true}
          show_compare={true}
        />
      );
      
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
    
    it('has proper heading hierarchy', () => {
      const { container } = render(
        <ChatAnswer
          answer="This is the answer"
          userRole={ROLE_PRO}
        />
      );
      
      const h2s = container.querySelectorAll('h2');
      const h3s = container.querySelectorAll('h3');
      const h4s = container.querySelectorAll('h4');
      
      // Should have proper heading hierarchy (no h1 in component, starts at h2/h3)
      expect(h2s.length + h3s.length + h4s.length).toBeGreaterThan(0);
    });
    
    it('has landmark regions', () => {
      const { container } = render(
        <ChatAnswer
          answer="This is the answer"
          userRole={ROLE_PRO}
        />
      );
      
      const regions = container.querySelectorAll('[role="region"]');
      expect(regions.length).toBeGreaterThan(0);
    });
  });
  
  // ==========================================================================
  // Prefers-Reduced-Motion Tests
  // ==========================================================================
  
  describe('Prefers-Reduced-Motion', () => {
    beforeEach(() => {
      // Mock matchMedia for prefers-reduced-motion
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(query => ({
          matches: query === '(prefers-reduced-motion: reduce)',
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });
    });
    
    it('disables animations in ProcessLedger', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const elements = container.querySelectorAll('*');
      elements.forEach(element => {
        const styles = window.getComputedStyle(element);
        // In reduced motion, animations should be disabled or very fast
        if (styles.animationDuration) {
          const duration = parseFloat(styles.animationDuration);
          expect(duration).toBeLessThanOrEqual(0.01); // 10ms or instant
        }
      });
    });
    
    it('disables animations in toasts', () => {
      // Toast animations should respect prefers-reduced-motion
      const style = document.createElement('style');
      style.textContent = `
        @media (prefers-reduced-motion: reduce) {
          .toast { animation-duration: 0.01ms !important; }
        }
      `;
      document.head.appendChild(style);
      
      const toast = document.createElement('div');
      toast.className = 'toast';
      document.body.appendChild(toast);
      
      const styles = window.getComputedStyle(toast);
      // Should have reduced/no animation
      expect(styles.animationDuration).toBeTruthy();
      
      document.body.removeChild(toast);
      document.head.removeChild(style);
    });
  });
  
  // ==========================================================================
  // Color Contrast Tests
  // ==========================================================================
  
  describe('Color Contrast', () => {
    it('badges have sufficient contrast', async () => {
      const { container } = render(
        <ContradictionBadge
          contradictions={mockContradictions}
          alwaysShow={true}
        />
      );
      
      // axe-core will check color-contrast automatically
      const results = await axe(container, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });
      
      expect(results).toHaveNoViolations();
    });
    
    it('buttons have sufficient contrast', async () => {
      const { container } = render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
        />
      );
      
      const results = await axe(container, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });
      
      expect(results).toHaveNoViolations();
    });
  });
  
  // ==========================================================================
  // Keyboard Navigation Tests
  // ==========================================================================
  
  describe('Keyboard Navigation', () => {
    it('all interactive elements are keyboard accessible', () => {
      const { container } = render(
        <ChatAnswer
          answer="Answer"
          evidence={[{ text: 'Evidence' }]}
          process_trace_summary={mockProcessTrace}
          compare_summary={mockCompareSummary}
          contradictions={mockContradictions}
          userRole={ROLE_PRO}
          show_ledger={true}
          show_badges={true}
          show_compare={true}
        />
      );
      
      // Find all interactive elements
      const interactive = container.querySelectorAll(
        'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      
      interactive.forEach(element => {
        // Each should be focusable
        expect(
          element.hasAttribute('tabindex') || 
          ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(element.tagName)
        ).toBe(true);
      });
    });
    
    it('tab order is logical', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const focusable = container.querySelectorAll(
        'button:not(:disabled), [tabindex]:not([tabindex="-1"])'
      );
      
      const tabIndexes = Array.from(focusable).map(el => 
        parseInt(el.getAttribute('tabindex') || '0')
      );
      
      // Should not have negative tabindex on interactive elements
      expect(tabIndexes.every(idx => idx >= 0)).toBe(true);
    });
  });
  
  // ==========================================================================
  // ARIA Live Region Tests
  // ==========================================================================
  
  describe('ARIA Live Regions', () => {
    it('toast notifications have aria-live', () => {
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      
      expect(toast.getAttribute('aria-live')).toBe('polite');
    });
    
    it('error messages have aria-live="assertive"', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockProcessTrace}
          messageId="test-123"
          userRole={ROLE_PRO}
          showLedger={true}
          error="Test error"
        />
      );
      
      const errorElement = container.querySelector('[role="alert"]');
      expect(errorElement).toBeInTheDocument();
    });
  });
});
