/**
 * CompareCard Component Tests
 * 
 * Comprehensive test suite for CompareCard component including:
 * - Rendering compare summaries
 * - Role gating for external compare
 * - Feature flag compliance
 * - External evidence truncation
 * - Loading states
 * - Evidence grouping
 * - Provenance display
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CompareCard, { CompareSummary, EvidenceItem } from '../../app/components/CompareCard';
import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS } from '../../app/lib/roles';

// ============================================================================
// Mock Data
// ============================================================================

const mockInternalEvidence: EvidenceItem[] = [
  {
    text: 'Internal evidence supporting position A',
    confidence: 0.85,
    source: 'Internal database',
  },
  {
    text: 'Additional internal evidence',
    confidence: 0.72,
    source: 'Knowledge base',
  },
];

const mockExternalEvidence: EvidenceItem[] = [
  {
    text: 'External evidence from Wikipedia with a very long text that should be truncated based on the max_snippet_chars policy. This text continues for quite a while to demonstrate the truncation feature. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.',
    url: 'https://en.wikipedia.org/wiki/Example',
    host: 'en.wikipedia.org',
    label: 'Wikipedia',
    fetched_at: '2023-10-30T12:00:00Z',
  },
  {
    text: 'Evidence from arXiv research paper',
    url: 'https://arxiv.org/abs/1234.5678',
    host: 'arxiv.org',
    label: 'arXiv',
    fetched_at: '2023-10-30T12:01:00Z',
  },
];

const mockCompareSummary: CompareSummary = {
  stance_a: 'The population is approximately 8.3 million',
  stance_b: 'The population is approximately 8.8 million',
  recommendation: 'a',
  confidence: 0.75,
  internal_evidence: mockInternalEvidence,
  external_evidence: [],
  metadata: {
    sources_used: { internal: 2, external: 0 },
    used_external: false,
  },
};

const mockCompareSummaryWithExternal: CompareSummary = {
  ...mockCompareSummary,
  external_evidence: mockExternalEvidence,
  metadata: {
    sources_used: { internal: 2, external: 2 },
    used_external: true,
    tie_break: 'prefer_internal',
  },
};

// ============================================================================
// Mock Fetch
// ============================================================================

global.fetch = jest.fn();

function mockFetchSuccess(result: Partial<CompareSummary> = {}) {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    status: 200,
    json: async () => ({
      compare_summary: {
        stance_a: result.stance_a || mockCompareSummary.stance_a,
        stance_b: result.stance_b || mockCompareSummary.stance_b,
        recommendation: result.recommendation || 'a',
        confidence: result.confidence || 0.80,
        internal_evidence: result.internal_evidence || mockInternalEvidence,
        external_evidence: result.external_evidence || mockExternalEvidence,
        tie_break: 'prefer_internal',
      },
      used_external: true,
      sources: { internal: 2, external: 2 },
      contradictions: [],
    }),
  });
}

function mockFetchError(status = 500, statusText = 'Internal Server Error') {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    status,
    statusText,
  });
}

// ============================================================================
// Test Setup
// ============================================================================

describe('CompareCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  afterEach(() => {
    jest.restoreAllMocks();
  });
  
  // ==========================================================================
  // Rendering Tests
  // ==========================================================================
  
  describe('Rendering', () => {
    it('renders compare card with stances', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('Position A')).toBeInTheDocument();
      expect(screen.getByText('Position B')).toBeInTheDocument();
      expect(screen.getByText(mockCompareSummary.stance_a)).toBeInTheDocument();
      expect(screen.getByText(mockCompareSummary.stance_b)).toBeInTheDocument();
    });
    
    it('renders recommendation indicator', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      const indicator = screen.getByText('←');
      expect(indicator).toBeInTheDocument();
      expect(indicator).toHaveAttribute('title', 'Recommendation: a');
    });
    
    it('renders confidence score', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('75%')).toBeInTheDocument();
    });
    
    it('applies custom className', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          className="custom-class"
        />
      );
      
      const card = screen.getByTestId('compare-card');
      expect(card).toHaveClass('custom-class');
    });
  });
  
  // ==========================================================================
  // Internal Evidence Tests
  // ==========================================================================
  
  describe('Internal Evidence', () => {
    it('renders internal evidence section', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('Internal Evidence')).toBeInTheDocument();
      expect(screen.getByText('(2)')).toBeInTheDocument();
    });
    
    it('renders all internal evidence items', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('Internal evidence supporting position A')).toBeInTheDocument();
      expect(screen.getByText('Additional internal evidence')).toBeInTheDocument();
    });
    
    it('shows confidence scores for internal evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('Confidence: 85%')).toBeInTheDocument();
      expect(screen.getByText('Confidence: 72%')).toBeInTheDocument();
    });
    
    it('shows sources for internal evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText(/Internal database/)).toBeInTheDocument();
      expect(screen.getByText(/Knowledge base/)).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // External Evidence Tests
  // ==========================================================================
  
  describe('External Evidence', () => {
    it('renders external evidence section when present', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('External Evidence')).toBeInTheDocument();
    });
    
    it('shows external badge when external used', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('External sources used')).toBeInTheDocument();
    });
    
    it('truncates long external evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      const evidenceList = screen.getByTestId('compare-card-external-evidence');
      const firstItem = evidenceList.querySelector('.evidence-text');
      
      expect(firstItem?.textContent).toContain('...');
      expect(firstItem?.textContent?.length).toBeLessThan(mockExternalEvidence[0].text.length);
    });
    
    it('shows source labels for external evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('[Wikipedia]')).toBeInTheDocument();
      expect(screen.getByText('[arXiv]')).toBeInTheDocument();
    });
    
    it('shows host names for external evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('en.wikipedia.org')).toBeInTheDocument();
      expect(screen.getByText('arxiv.org')).toBeInTheDocument();
    });
    
    it('shows view source links for external evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      const links = screen.getAllByText('View source');
      expect(links).toHaveLength(2);
      
      expect(links[0]).toHaveAttribute('href', mockExternalEvidence[0].url);
      expect(links[0]).toHaveAttribute('target', '_blank');
      expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer');
    });
    
    it('shows fetched timestamps for external evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      const timestamps = screen.getAllByText(/Fetched:/);
      expect(timestamps).toHaveLength(2);
    });
  });
  
  // ==========================================================================
  // Role Gating Tests
  // ==========================================================================
  
  describe('Role Gating', () => {
    it('disables run button for General role', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_GENERAL}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).toBeDisabled();
    });
    
    it('enables run button for Pro role', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).not.toBeDisabled();
    });
    
    it('enables run button for Scholars role', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_SCHOLARS}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).not.toBeDisabled();
    });
    
    it('enables run button for Analytics role', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_ANALYTICS}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).not.toBeDisabled();
    });
    
    it('shows helpful title for disabled button (General)', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_GENERAL}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).toHaveAttribute('title', 'Pro or higher required for external compare');
    });
  });
  
  // ==========================================================================
  // Feature Flag Tests
  // ==========================================================================
  
  describe('Feature Flag Compliance', () => {
    it('disables run button when allowExternalCompare is false', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={false}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).toBeDisabled();
    });
    
    it('enables run button when allowExternalCompare is true and role is Pro', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).not.toBeDisabled();
    });
    
    it('shows helpful title when flag is off', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={false}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      expect(button).toHaveAttribute('title', 'External compare is disabled');
    });
    
    it('hides run button when no messageId provided', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
        />
      );
      
      expect(screen.queryByTestId('compare-card-run-button')).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Run Full Compare Tests
  // ==========================================================================
  
  describe('Run Full Compare', () => {
    it('calls API when button clicked', async () => {
      mockFetchSuccess();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/factate/compare',
          expect.objectContaining({
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              message_id: 'msg_123',
              allow_external: true,
            }),
          })
        );
      });
    });
    
    it('uses custom API base URL', async () => {
      mockFetchSuccess();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
          apiBaseUrl="https://custom.api"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          'https://custom.api/factate/compare',
          expect.any(Object)
        );
      });
    });
    
    it('calls onCompareComplete callback on success', async () => {
      mockFetchSuccess();
      const onCompareComplete = jest.fn();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
          onCompareComplete={onCompareComplete}
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      await waitFor(() => {
        expect(onCompareComplete).toHaveBeenCalled();
      });
    });
    
    it('displays error message on failure', async () => {
      mockFetchError(500, 'Server Error');
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      await waitFor(() => {
        expect(screen.getByTestId('compare-card-error')).toBeInTheDocument();
        expect(screen.getByText(/Compare failed: 500 Server Error/)).toBeInTheDocument();
      });
    });
  });
  
  // ==========================================================================
  // Loading State Tests
  // ==========================================================================
  
  describe('Loading States', () => {
    it('shows loading state when running compare', async () => {
      mockFetchSuccess();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      // Check loading state appears
      await waitFor(() => {
        expect(screen.getByText('Running...')).toBeInTheDocument();
        expect(button).toBeDisabled();
      });
    });
    
    it('clears loading state after success', async () => {
      mockFetchSuccess();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      await waitFor(() => {
        expect(screen.getByText('Running...')).toBeInTheDocument();
      });
      
      await waitFor(() => {
        expect(screen.queryByText('Running...')).not.toBeInTheDocument();
        expect(button).not.toBeDisabled();
      });
    });
    
    it('clears loading state after error', async () => {
      mockFetchError();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      await waitFor(() => {
        expect(screen.getByText('Running...')).toBeInTheDocument();
      });
      
      await waitFor(() => {
        expect(screen.queryByText('Running...')).not.toBeInTheDocument();
      });
    });
    
    it('prevents multiple simultaneous requests', async () => {
      mockFetchSuccess();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      
      // Click multiple times rapidly
      fireEvent.click(button);
      fireEvent.click(button);
      fireEvent.click(button);
      
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(1);
      });
    });
  });
  
  // ==========================================================================
  // Truncation Tests
  // ==========================================================================
  
  describe('External Evidence Truncation', () => {
    it('truncates Wikipedia evidence to 480 chars', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      const evidenceList = screen.getByTestId('compare-card-external-evidence');
      const firstItem = evidenceList.querySelector('.evidence-text[data-truncated="true"]');
      
      expect(firstItem).toBeInTheDocument();
      expect(firstItem?.textContent?.length).toBeLessThanOrEqual(480);
    });
    
    it('marks truncated text with data attribute', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      const evidenceList = screen.getByTestId('compare-card-external-evidence');
      const firstItem = evidenceList.querySelector('.evidence-text');
      
      expect(firstItem).toHaveAttribute('data-truncated', 'true');
    });
    
    it('does not truncate short external evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('Evidence from arXiv research paper')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Metadata Tests
  // ==========================================================================
  
  describe('Metadata Display', () => {
    it('shows source counts in footer', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('2 internal')).toBeInTheDocument();
      expect(screen.getByText(/, 2 external/)).toBeInTheDocument();
    });
    
    it('shows tie-break strategy in footer', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.getByText('prefer_internal')).toBeInTheDocument();
    });
    
    it('hides footer when no metadata', () => {
      const summaryNoMetadata: CompareSummary = {
        ...mockCompareSummary,
        metadata: undefined,
      };
      
      render(
        <CompareCard
          compareSummary={summaryNoMetadata}
          userRole={ROLE_PRO}
        />
      );
      
      expect(screen.queryByText('Sources:')).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('renders normalized compare_summary', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
        />
      );
      
      // Stances
      expect(screen.getByText(mockCompareSummary.stance_a)).toBeInTheDocument();
      expect(screen.getByText(mockCompareSummary.stance_b)).toBeInTheDocument();
      
      // Evidence
      expect(screen.getByText('Internal Evidence')).toBeInTheDocument();
      expect(screen.getByTestId('compare-card-internal-evidence')).toBeInTheDocument();
    });
    
    it('groups and truncates external evidence', () => {
      render(
        <CompareCard
          compareSummary={mockCompareSummaryWithExternal}
          userRole={ROLE_PRO}
        />
      );
      
      // External section exists
      expect(screen.getByText('External Evidence')).toBeInTheDocument();
      
      // Evidence is truncated
      const evidenceList = screen.getByTestId('compare-card-external-evidence');
      const truncated = evidenceList.querySelector('.evidence-text[data-truncated="true"]');
      expect(truncated).toBeInTheDocument();
    });
    
    it('run button disabled for General and when flags off', () => {
      const { rerender } = render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_GENERAL}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      let button = screen.getByTestId('compare-card-run-button');
      expect(button).toBeDisabled();
      
      rerender(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={false}
          messageId="msg_123"
        />
      );
      
      button = screen.getByTestId('compare-card-run-button');
      expect(button).toBeDisabled();
    });
    
    it('loading states tested', async () => {
      mockFetchSuccess();
      
      render(
        <CompareCard
          compareSummary={mockCompareSummary}
          userRole={ROLE_PRO}
          allowExternalCompare={true}
          messageId="msg_123"
        />
      );
      
      const button = screen.getByTestId('compare-card-run-button');
      fireEvent.click(button);
      
      // Loading appears
      await waitFor(() => {
        expect(screen.getByText('Running...')).toBeInTheDocument();
      });
      
      // Loading clears
      await waitFor(() => {
        expect(screen.queryByText('Running...')).not.toBeInTheDocument();
      });
    });
  });
});
