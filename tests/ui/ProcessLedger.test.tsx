/**
 * ProcessLedger Component Tests
 * 
 * Comprehensive test suite for ProcessLedger component including:
 * - Snapshot tests for different roles
 * - Expand/collapse functionality
 * - Network error handling
 * - Role-based redaction
 * - Feature flag compliance
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProcessLedger, { ProcessTraceLine } from '../../app/components/ProcessLedger';
import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS } from '../../app/lib/roles';

// ============================================================================
// Mock Data
// ============================================================================

const mockTraceSummary: ProcessTraceLine[] = [
  {
    step: 'Parse query',
    duration_ms: 12,
    status: 'success',
    details: 'Query parsed successfully',
  },
  {
    step: 'Retrieve candidates',
    duration_ms: 245,
    status: 'success',
    details: 'Found 8 candidates',
    provenance: 'pinecone:explicate-index',
  },
  {
    step: 'Generate response',
    duration_ms: 1834,
    status: 'success',
    details: 'LLM generation complete',
    prompt: 'You are a helpful assistant...',
    metadata: {
      model: 'gpt-4',
      tokens: 1250,
      internal_id: 'req_abc123',
    },
  },
  {
    step: 'Format output',
    duration_ms: 8,
    status: 'success',
    details: 'Response formatted',
  },
];

const mockFullTrace: ProcessTraceLine[] = [
  ...mockTraceSummary,
  {
    step: 'Cache write',
    duration_ms: 15,
    status: 'success',
    details: 'Response cached',
  },
  {
    step: 'Metrics logging',
    duration_ms: 3,
    status: 'success',
    details: 'Metrics recorded',
  },
];

// ============================================================================
// Mock Fetch
// ============================================================================

global.fetch = jest.fn();

function mockFetchSuccess() {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    status: 200,
    json: async () => ({
      trace: mockFullTrace,
      message_id: 'msg_123',
      total_duration_ms: 2117,
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

function mockFetchNetworkError() {
  (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));
}

// ============================================================================
// Test Setup
// ============================================================================

describe('ProcessLedger', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  afterEach(() => {
    jest.restoreAllMocks();
  });
  
  // ==========================================================================
  // Snapshot Tests
  // ==========================================================================
  
  describe('Snapshot Tests', () => {
    it('renders correctly for General role', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_GENERAL}
          showLedger={true}
        />
      );
      
      expect(container.firstChild).toMatchSnapshot();
    });
    
    it('renders correctly for Pro role', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      expect(container.firstChild).toMatchSnapshot();
    });
    
    it('renders correctly for Scholars role', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_SCHOLARS}
          showLedger={true}
        />
      );
      
      expect(container.firstChild).toMatchSnapshot();
    });
    
    it('renders correctly for Analytics role', () => {
      const { container } = render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_ANALYTICS}
          showLedger={true}
        />
      );
      
      expect(container.firstChild).toMatchSnapshot();
    });
  });
  
  // ==========================================================================
  // Role-Based Redaction Tests
  // ==========================================================================
  
  describe('Role-Based Redaction', () => {
    it('caps to 4 lines for General role', () => {
      const longTrace = [...mockTraceSummary, ...mockTraceSummary]; // 8 lines
      
      render(
        <ProcessLedger
          traceSummary={longTrace}
          messageId="msg_123"
          userRole={ROLE_GENERAL}
          showLedger={true}
        />
      );
      
      const lines = screen.getAllByTestId(/process-line-\d+/);
      expect(lines).toHaveLength(4);
    });
    
    it('shows all summary lines for Pro role', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const lines = screen.getAllByTestId(/process-line-\d+/);
      expect(lines).toHaveLength(4);
    });
    
    it('hides expand button for General role', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_GENERAL}
          showLedger={true}
        />
      );
      
      const expandButton = screen.queryByTestId('process-ledger-expand-button');
      expect(expandButton).not.toBeInTheDocument();
    });
    
    it('shows expand button for Pro role', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      expect(expandButton).toBeInTheDocument();
    });
    
    it('shows footer hint for General role when capped', () => {
      const longTrace = [...mockTraceSummary, ...mockTraceSummary]; // 8 lines
      
      render(
        <ProcessLedger
          traceSummary={longTrace}
          messageId="msg_123"
          userRole={ROLE_GENERAL}
          showLedger={true}
        />
      );
      
      expect(screen.getByText(/Showing 4 of 8 steps/)).toBeInTheDocument();
      expect(screen.getByText(/Upgrade to Pro for full trace/)).toBeInTheDocument();
    });
    
    it('does not show footer for Pro role', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const footer = screen.queryByTestId('process-ledger-footer');
      expect(footer).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Expand/Collapse Functionality Tests
  // ==========================================================================
  
  describe('Expand/Collapse Functionality', () => {
    it('expands and fetches full trace on click', async () => {
      mockFetchSuccess();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText('Loading...')).toBeInTheDocument();
      });
      
      // Should fetch from correct URL
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/debug/redo_trace?message_id=msg_123'
        );
      });
      
      // Should display full trace
      await waitFor(() => {
        const lines = screen.getAllByTestId(/process-line-\d+/);
        expect(lines).toHaveLength(6); // Full trace has 6 lines
      });
      
      // Should show expanded indicator
      expect(screen.getByText(/Showing full trace \(6 steps\)/)).toBeInTheDocument();
    });
    
    it('collapses back to summary on second click', async () => {
      mockFetchSuccess();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      
      // Expand
      fireEvent.click(expandButton);
      await waitFor(() => {
        const lines = screen.getAllByTestId(/process-line-\d+/);
        expect(lines).toHaveLength(6);
      });
      
      // Collapse
      fireEvent.click(expandButton);
      await waitFor(() => {
        const lines = screen.getAllByTestId(/process-line-\d+/);
        expect(lines).toHaveLength(4); // Back to summary
      });
    });
    
    it('calls onExpandChange callback', async () => {
      mockFetchSuccess();
      const onExpandChange = jest.fn();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
          onExpandChange={onExpandChange}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        expect(onExpandChange).toHaveBeenCalledWith(true);
      });
    });
    
    it('does not fetch again if already loaded', async () => {
      mockFetchSuccess();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      
      // Expand first time
      fireEvent.click(expandButton);
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(1);
      });
      
      // Collapse
      fireEvent.click(expandButton);
      
      // Expand again
      fireEvent.click(expandButton);
      
      // Should not fetch again
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });
    
    it('respects defaultExpanded prop', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
          defaultExpanded={true}
        />
      );
      
      const ledger = screen.getByTestId('process-ledger');
      expect(ledger).toHaveAttribute('data-expanded', 'true');
    });
  });
  
  // ==========================================================================
  // Error Handling Tests
  // ==========================================================================
  
  describe('Error Handling', () => {
    it('displays error message on fetch failure', async () => {
      mockFetchError(500, 'Internal Server Error');
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('process-ledger-error')).toBeInTheDocument();
      });
      
      expect(screen.getByText(/Failed to fetch trace: 500 Internal Server Error/)).toBeInTheDocument();
    });
    
    it('displays error on network failure', async () => {
      mockFetchNetworkError();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
      });
    });
    
    it('shows retry button on error', async () => {
      mockFetchError();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('process-ledger-retry-button')).toBeInTheDocument();
      });
    });
    
    it('retries fetch on retry button click', async () => {
      mockFetchError();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('process-ledger-retry-button')).toBeInTheDocument();
      });
      
      // Mock success for retry
      mockFetchSuccess();
      
      const retryButton = screen.getByTestId('process-ledger-retry-button');
      fireEvent.click(retryButton);
      
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });
    
    it('handles missing message ID gracefully', async () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      // Should not show expand button without message ID
      const expandButton = screen.queryByTestId('process-ledger-expand-button');
      expect(expandButton).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Feature Flag Tests
  // ==========================================================================
  
  describe('Feature Flag Compliance', () => {
    it('renders when showLedger is true', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      expect(screen.getByTestId('process-ledger')).toBeInTheDocument();
    });
    
    it('does not render when showLedger is false', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={false}
        />
      );
      
      expect(screen.queryByTestId('process-ledger')).not.toBeInTheDocument();
    });
    
    it('does not render when trace summary is empty', () => {
      render(
        <ProcessLedger
          traceSummary={[]}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      expect(screen.queryByTestId('process-ledger')).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // UI Element Tests
  // ==========================================================================
  
  describe('UI Elements', () => {
    it('displays total duration', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const totalDuration = 12 + 245 + 1834 + 8; // Sum of all durations
      expect(screen.getByText(`(${totalDuration}ms)`)).toBeInTheDocument();
    });
    
    it('applies custom className', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
          className="custom-class"
        />
      );
      
      const ledger = screen.getByTestId('process-ledger');
      expect(ledger).toHaveClass('custom-class');
    });
    
    it('sets data-role attribute', () => {
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const ledger = screen.getByTestId('process-ledger');
      expect(ledger).toHaveAttribute('data-role', ROLE_PRO);
    });
    
    it('uses custom apiBaseUrl', async () => {
      mockFetchSuccess();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
          apiBaseUrl="https://custom.api"
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          'https://custom.api/debug/redo_trace?message_id=msg_123'
        );
      });
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('shows 4-line cap for General with upgrade hint', () => {
      const longTrace = [...mockTraceSummary, ...mockTraceSummary];
      
      render(
        <ProcessLedger
          traceSummary={longTrace}
          messageId="msg_123"
          userRole={ROLE_GENERAL}
          showLedger={true}
        />
      );
      
      // 4 lines max
      const lines = screen.getAllByTestId(/process-line-\d+/);
      expect(lines).toHaveLength(4);
      
      // Upgrade hint
      expect(screen.getByText(/Upgrade to Pro for full trace/)).toBeInTheDocument();
    });
    
    it('allows Pro to expand and see full trace', async () => {
      mockFetchSuccess();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      // Has expand button
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      expect(expandButton).toBeInTheDocument();
      
      // Expand works
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        const lines = screen.getAllByTestId(/process-line-\d+/);
        expect(lines).toHaveLength(6);
      });
    });
    
    it('network error shows friendly fallback', async () => {
      mockFetchNetworkError();
      
      render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      const expandButton = screen.getByTestId('process-ledger-expand-button');
      fireEvent.click(expandButton);
      
      await waitFor(() => {
        const error = screen.getByTestId('process-ledger-error');
        expect(error).toBeInTheDocument();
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
        expect(screen.getByTestId('process-ledger-retry-button')).toBeInTheDocument();
      });
    });
    
    it('respects ui.flags.show_ledger', () => {
      const { rerender } = render(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={true}
        />
      );
      
      expect(screen.getByTestId('process-ledger')).toBeInTheDocument();
      
      rerender(
        <ProcessLedger
          traceSummary={mockTraceSummary}
          messageId="msg_123"
          userRole={ROLE_PRO}
          showLedger={false}
        />
      );
      
      expect(screen.queryByTestId('process-ledger')).not.toBeInTheDocument();
    });
  });
});
