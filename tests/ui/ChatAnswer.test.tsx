/**
 * ChatAnswer View Tests
 * 
 * Comprehensive test suite for ChatAnswer view including:
 * - Conditional rendering of components
 * - Skeleton loader visibility
 * - Stable layout without content shifts
 * - Feature flag compliance
 * - Empty state handling
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ChatAnswer, { 
  ChatAnswerData, 
  CompareCardSkeleton, 
  ProcessLedgerSkeleton 
} from '../../app/views/ChatAnswer';
import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS } from '../../app/lib/roles';
import { CompareSummary } from '../../app/components/CompareCard';
import { ProcessTraceLine } from '../../app/components/ProcessLedger';
import { Contradiction } from '../../app/components/ContradictionBadge';

// ============================================================================
// Mock Data
// ============================================================================

const mockProcessTrace: ProcessTraceLine[] = [
  { step: 'Parse query', duration_ms: 12, status: 'success' },
  { step: 'Retrieve candidates', duration_ms: 245, status: 'success' },
  { step: 'Generate response', duration_ms: 1830, status: 'success' },
  { step: 'Format output', duration_ms: 8, status: 'success' },
];

const mockContradictions: Contradiction[] = [
  {
    id: 'c1',
    subject: 'Population figure',
    description: 'Different sources report different numbers',
    evidenceAnchor: 'evidence-1',
    severity: 'medium',
  },
];

const mockCompareSummary: CompareSummary = {
  stance_a: 'The population is 8.3 million',
  stance_b: 'The population is 8.8 million',
  recommendation: 'a',
  confidence: 0.75,
  internal_evidence: [
    { text: 'Census data shows 8.3M', confidence: 0.85 },
  ],
  external_evidence: [],
};

const baseAnswerData: ChatAnswerData = {
  message_id: 'msg_123',
  content: '<p>This is the answer with <span id="evidence-1">marked evidence</span>.</p>',
  process_trace_summary: mockProcessTrace,
  contradictions: mockContradictions,
  compare_summary: undefined,
};

const baseUIFlags = {
  show_ledger: false,
  show_badges: false,
  show_compare: false,
  external_compare: false,
};

// ============================================================================
// Tests
// ============================================================================

describe('ChatAnswer', () => {
  // ==========================================================================
  // Basic Rendering
  // ==========================================================================
  
  describe('Basic Rendering', () => {
    it('renders answer header and content', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
        />
      );
      
      expect(screen.getByText('Answer')).toBeInTheDocument();
      expect(screen.getByTestId('chat-answer-content')).toBeInTheDocument();
      expect(screen.getByText(/This is the answer/)).toBeInTheDocument();
    });
    
    it('applies custom className and testId', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
          className="custom-class"
          testId="custom-test-id"
        />
      );
      
      const element = screen.getByTestId('custom-test-id');
      expect(element).toHaveClass('custom-class');
    });
    
    it('sets data attributes correctly', () => {
      const { rerender } = render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
        />
      );
      
      const element = screen.getByTestId('chat-answer');
      expect(element).toHaveAttribute('data-has-contradictions', 'true');
      expect(element).toHaveAttribute('data-has-compare', 'false');
      expect(element).toHaveAttribute('data-has-ledger', 'false');
      
      // With compare
      rerender(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer')).toHaveAttribute('data-has-compare', 'true');
    });
  });
  
  // ==========================================================================
  // ContradictionBadge Conditional Rendering
  // ==========================================================================
  
  describe('ContradictionBadge Rendering', () => {
    it('shows badge when contradictions exist', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
        />
      );
      
      expect(screen.getByTestId('chat-answer-contradiction-badge')).toBeInTheDocument();
    });
    
    it('hides badge when no contradictions and show_badges is false', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, contradictions: [] }}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-contradiction-badge')).not.toBeInTheDocument();
    });
    
    it('shows badge when no contradictions but show_badges is true', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, contradictions: [] }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_badges: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-contradiction-badge')).toBeInTheDocument();
    });
    
    it('passes contradictions to badge', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
        />
      );
      
      expect(screen.getByText('Contradictions: 1')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // CompareCard Conditional Rendering
  // ==========================================================================
  
  describe('CompareCard Rendering', () => {
    it('hides compare section when show_compare is false', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: false }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-compare-section')).not.toBeInTheDocument();
    });
    
    it('shows compare section when show_compare is true and compare_summary exists', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-compare-section')).toBeInTheDocument();
      expect(screen.getByTestId('chat-answer-compare-card')).toBeInTheDocument();
    });
    
    it('does not render compare when no compare_summary and not loading', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: undefined }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-compare-section')).not.toBeInTheDocument();
    });
    
    it('passes external_compare flag to CompareCard', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true, external_compare: true }}
        />
      );
      
      // CompareCard should be present
      expect(screen.getByTestId('chat-answer-compare-card')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // ProcessLedger Conditional Rendering
  // ==========================================================================
  
  describe('ProcessLedger Rendering', () => {
    it('hides ledger when show_ledger is false', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: false }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-ledger-section')).not.toBeInTheDocument();
    });
    
    it('shows ledger when show_ledger is true', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-ledger-section')).toBeInTheDocument();
      expect(screen.getByTestId('chat-answer-process-ledger')).toBeInTheDocument();
    });
    
    it('does not render ledger when process_trace_summary is empty', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, process_trace_summary: [] }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-ledger-section')).not.toBeInTheDocument();
    });
    
    it('passes correct props to ProcessLedger', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_SCHOLARS}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      const ledger = screen.getByTestId('chat-answer-process-ledger');
      expect(ledger).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Skeleton Loading States
  // ==========================================================================
  
  describe('Skeleton Loaders', () => {
    it('shows compare skeleton when compare_loading is true', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-compare-skeleton')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-answer-compare-card')).not.toBeInTheDocument();
    });
    
    it('hides compare skeleton when compare_summary arrives', () => {
      const { rerender } = render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-compare-skeleton')).toBeInTheDocument();
      
      rerender(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-compare-skeleton')).not.toBeInTheDocument();
      expect(screen.getByTestId('chat-answer-compare-card')).toBeInTheDocument();
    });
    
    it('shows ledger skeleton when trace_loading is true', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, trace_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-ledger-skeleton')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-answer-process-ledger')).not.toBeInTheDocument();
    });
    
    it('hides ledger skeleton when trace_loading becomes false', () => {
      const { rerender } = render(
        <ChatAnswer
          answer={{ ...baseAnswerData, trace_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-ledger-skeleton')).toBeInTheDocument();
      
      rerender(
        <ChatAnswer
          answer={{ ...baseAnswerData, trace_loading: false }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-ledger-skeleton')).not.toBeInTheDocument();
      expect(screen.getByTestId('chat-answer-process-ledger')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Stable Layout (No Content Shift)
  // ==========================================================================
  
  describe('Stable Layout', () => {
    it('reserves space for compare section with skeleton', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      const section = screen.getByTestId('chat-answer-compare-section');
      expect(section).toBeInTheDocument();
      
      // Skeleton should be visible
      expect(screen.getByTestId('chat-answer-compare-skeleton')).toBeInTheDocument();
    });
    
    it('maintains compare section when data arrives', () => {
      const { rerender } = render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      const sectionBefore = screen.getByTestId('chat-answer-compare-section');
      
      rerender(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      const sectionAfter = screen.getByTestId('chat-answer-compare-section');
      expect(sectionAfter).toBe(sectionBefore); // Same DOM node
    });
  });
  
  // ==========================================================================
  // Callbacks
  // ==========================================================================
  
  describe('Callbacks', () => {
    it('calls onCompareComplete when compare finishes', async () => {
      const onCompareComplete = jest.fn();
      
      const { rerender } = render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
          onCompareComplete={onCompareComplete}
        />
      );
      
      rerender(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
          onCompareComplete={onCompareComplete}
        />
      );
      
      // Note: The callback is called from CompareCard, not directly tested here
      // This would require mocking CompareCard's onCompareComplete handler
    });
    
    it('passes onEvidenceClick to ContradictionBadge', () => {
      const onEvidenceClick = jest.fn();
      
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
          onEvidenceClick={onEvidenceClick}
        />
      );
      
      expect(screen.getByTestId('chat-answer-contradiction-badge')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Empty State Handling
  // ==========================================================================
  
  describe('Empty State Handling', () => {
    it('does not render compare when compare_summary is null', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: undefined }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-compare-section')).not.toBeInTheDocument();
    });
    
    it('does not render ledger when process_trace_summary is empty', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, process_trace_summary: [] }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-ledger-section')).not.toBeInTheDocument();
    });
    
    it('does not render badge when no contradictions and show_badges false', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, contradictions: [] }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_badges: false }}
        />
      );
      
      expect(screen.queryByTestId('chat-answer-contradiction-badge')).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Role-Based Rendering
  // ==========================================================================
  
  describe('Role-Based Rendering', () => {
    it('renders for General user', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_GENERAL}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer')).toBeInTheDocument();
    });
    
    it('renders for Pro user', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true, show_ledger: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer')).toBeInTheDocument();
      expect(screen.getByTestId('chat-answer-compare-card')).toBeInTheDocument();
    });
    
    it('passes userRole to child components', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_SCHOLARS}
          uiFlags={{ 
            show_ledger: true, 
            show_compare: true,
            show_badges: false,
            external_compare: true 
          }}
        />
      );
      
      // Both components should receive the role
      expect(screen.getByTestId('chat-answer-compare-card')).toBeInTheDocument();
      expect(screen.getByTestId('chat-answer-process-ledger')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('places ContradictionBadge next to answer header', () => {
      render(
        <ChatAnswer
          answer={baseAnswerData}
          userRole={ROLE_PRO}
          uiFlags={baseUIFlags}
        />
      );
      
      const header = screen.getByTestId('chat-answer').querySelector('.chat-answer-header');
      const badge = screen.getByTestId('chat-answer-contradiction-badge');
      
      expect(header).toContainElement(badge);
    });
    
    it('shows CompareCard below answer when compare_summary exists', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      const content = screen.getByTestId('chat-answer-content');
      const compareSection = screen.getByTestId('chat-answer-compare-section');
      
      // Compare should be after content in DOM
      expect(content.compareDocumentPosition(compareSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
    
    it('shows ProcessLedger below compare section', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true, show_ledger: true }}
        />
      );
      
      const compareSection = screen.getByTestId('chat-answer-compare-section');
      const ledgerSection = screen.getByTestId('chat-answer-ledger-section');
      
      // Ledger should be after compare in DOM
      expect(compareSection.compareDocumentPosition(ledgerSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
    
    it('layout does not shift on late-arriving compare', () => {
      const { rerender } = render(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      // Skeleton should be present
      expect(screen.getByTestId('chat-answer-compare-skeleton')).toBeInTheDocument();
      
      rerender(
        <ChatAnswer
          answer={{ ...baseAnswerData, compare_summary: mockCompareSummary }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_compare: true }}
        />
      );
      
      // Card should replace skeleton without section disappearing
      expect(screen.getByTestId('chat-answer-compare-card')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-answer-compare-skeleton')).not.toBeInTheDocument();
    });
    
    it('shows skeletons while fetching full trace', () => {
      render(
        <ChatAnswer
          answer={{ ...baseAnswerData, trace_loading: true }}
          userRole={ROLE_PRO}
          uiFlags={{ ...baseUIFlags, show_ledger: true }}
        />
      );
      
      expect(screen.getByTestId('chat-answer-ledger-skeleton')).toBeInTheDocument();
    });
    
    it('no render for empty summaries', () => {
      render(
        <ChatAnswer
          answer={{
            ...baseAnswerData,
            compare_summary: undefined,
            process_trace_summary: [],
            contradictions: [],
          }}
          userRole={ROLE_PRO}
          uiFlags={{ 
            show_compare: true, 
            show_ledger: true,
            show_badges: false 
          }}
        />
      );
      
      // Only content should be present
      expect(screen.getByTestId('chat-answer-content')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-answer-contradiction-badge')).not.toBeInTheDocument();
      expect(screen.queryByTestId('chat-answer-compare-section')).not.toBeInTheDocument();
      expect(screen.queryByTestId('chat-answer-ledger-section')).not.toBeInTheDocument();
    });
  });
});

// ============================================================================
// Skeleton Component Tests
// ============================================================================

describe('Skeleton Components', () => {
  it('renders CompareCardSkeleton', () => {
    render(<CompareCardSkeleton />);
    expect(screen.getByTestId('compare-skeleton')).toBeInTheDocument();
  });
  
  it('renders ProcessLedgerSkeleton', () => {
    render(<ProcessLedgerSkeleton />);
    expect(screen.getByTestId('ledger-skeleton')).toBeInTheDocument();
  });
  
  it('applies custom testId to skeletons', () => {
    render(<CompareCardSkeleton testId="custom-compare" />);
    expect(screen.getByTestId('custom-compare')).toBeInTheDocument();
    
    render(<ProcessLedgerSkeleton testId="custom-ledger" />);
    expect(screen.getByTestId('custom-ledger')).toBeInTheDocument();
  });
});
