/**
 * PromoteHypothesisButton Tests
 * 
 * Comprehensive test suite for PromoteHypothesisButton component including:
 * - Role gating (Pro/Analytics only)
 * - Modal form functionality
 * - API integration (201 success, 202 threshold not met)
 * - Toast notifications
 * - Telemetry tracking
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PromoteHypothesisButton from '../../app/components/PromoteHypothesisButton';
import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS } from '../../app/lib/roles';
import * as hypothesesAPI from '../../app/api/hypotheses';

// ============================================================================
// Mock API
// ============================================================================

jest.mock('../../app/api/hypotheses');

const mockProposeHypothesis = hypothesesAPI.proposeHypothesis as jest.MockedFunction<typeof hypothesesAPI.proposeHypothesis>;

function mockSuccessResponse(score: number = 0.85) {
  mockProposeHypothesis.mockResolvedValue({
    status: 201,
    data: {
      hypothesis_id: 'hyp_123',
      title: 'Test Hypothesis',
      description: 'Test description',
      score: score,
      persisted: true,
      created_at: '2023-10-30T12:00:00Z',
    },
  });
}

function mockThresholdNotMetResponse(score: number = 0.55) {
  mockProposeHypothesis.mockResolvedValue({
    status: 202,
    data: {
      hypothesis_id: 'hyp_124',
      title: 'Test Hypothesis',
      description: 'Test description',
      score: score,
      persisted: false,
      created_at: '2023-10-30T12:00:00Z',
    },
  });
}

function mockErrorResponse(message: string = 'Server error') {
  mockProposeHypothesis.mockRejectedValue(new Error(message));
}

// ============================================================================
// Mock Telemetry
// ============================================================================

const mockTelemetryTrack = jest.fn();

beforeEach(() => {
  (window as any).analytics = {
    track: mockTelemetryTrack,
  };
});

// ============================================================================
// Mock Data
// ============================================================================

const mockQuestion = 'What is the population of New York City?';
const mockEvidence = [
  'According to Census 2020, the population is 8,336,817',
  'Historical data confirms this count',
  'Multiple sources validate this figure',
];

// ============================================================================
// Tests
// ============================================================================

describe('PromoteHypothesisButton', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  afterEach(() => {
    jest.restoreAllMocks();
  });
  
  // ==========================================================================
  // Role Gating Tests
  // ==========================================================================
  
  describe('Role Gating', () => {
    it('hides button for General users', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_GENERAL}
          question={mockQuestion}
        />
      );
      
      expect(screen.queryByTestId('promote-hypothesis-button')).not.toBeInTheDocument();
    });
    
    it('hides button for Scholars users', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_SCHOLARS}
          question={mockQuestion}
        />
      );
      
      expect(screen.queryByTestId('promote-hypothesis-button')).not.toBeInTheDocument();
    });
    
    it('hides button for Ops users', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_OPS}
          question={mockQuestion}
        />
      );
      
      expect(screen.queryByTestId('promote-hypothesis-button')).not.toBeInTheDocument();
    });
    
    it('shows button for Pro users', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      expect(screen.getByTestId('promote-hypothesis-button')).toBeInTheDocument();
    });
    
    it('shows button for Analytics users', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_ANALYTICS}
          question={mockQuestion}
        />
      );
      
      expect(screen.getByTestId('promote-hypothesis-button')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Modal Tests
  // ==========================================================================
  
  describe('Modal Functionality', () => {
    it('opens modal when button clicked', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      const button = screen.getByTestId('promote-hypothesis-button');
      fireEvent.click(button);
      
      expect(screen.getByTestId('promote-hypothesis-button-modal')).toBeInTheDocument();
      expect(screen.getByText('Promote to Hypothesis')).toBeInTheDocument();
    });
    
    it('pre-fills title from question', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const titleInput = screen.getByTestId('promote-hypothesis-button-title-input') as HTMLInputElement;
      expect(titleInput.value).toBe('What is the population of New York City');
    });
    
    it('pre-fills description from evidence', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const descInput = screen.getByTestId('promote-hypothesis-button-description-input') as HTMLTextAreaElement;
      expect(descInput.value).toContain('1. According to Census 2020');
      expect(descInput.value).toContain('2. Historical data confirms');
      expect(descInput.value).toContain('3. Multiple sources validate');
    });
    
    it('closes modal when close button clicked', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      expect(screen.getByTestId('promote-hypothesis-button-modal')).toBeInTheDocument();
      
      const closeButton = screen.getByLabelText('Close modal');
      fireEvent.click(closeButton);
      
      expect(screen.queryByTestId('promote-hypothesis-button-modal')).not.toBeInTheDocument();
    });
    
    it('closes modal when overlay clicked', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const overlay = screen.getByTestId('promote-hypothesis-button-modal-overlay');
      fireEvent.click(overlay);
      
      expect(screen.queryByTestId('promote-hypothesis-button-modal')).not.toBeInTheDocument();
    });
    
    it('does not close modal when modal content clicked', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const modal = screen.getByTestId('promote-hypothesis-button-modal');
      fireEvent.click(modal);
      
      expect(screen.getByTestId('promote-hypothesis-button-modal')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Form Validation Tests
  // ==========================================================================
  
  describe('Form Validation', () => {
    it('disables submit button when title is empty', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const submitButton = screen.getByTestId('promote-hypothesis-button-submit');
      expect(submitButton).toBeDisabled();
    });
    
    it('allows editing title and description', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const titleInput = screen.getByTestId('promote-hypothesis-button-title-input') as HTMLInputElement;
      const descInput = screen.getByTestId('promote-hypothesis-button-description-input') as HTMLTextAreaElement;
      
      fireEvent.change(titleInput, { target: { value: 'New Title' } });
      fireEvent.change(descInput, { target: { value: 'New Description' } });
      
      expect(titleInput.value).toBe('New Title');
      expect(descInput.value).toBe('New Description');
    });
    
    it('allows adjusting confidence slider', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const confidenceInput = screen.getByTestId('promote-hypothesis-button-confidence-input') as HTMLInputElement;
      
      fireEvent.change(confidenceInput, { target: { value: '0.9' } });
      
      expect(confidenceInput.value).toBe('0.9');
      expect(screen.getByText(/90%/)).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Success Case (201) Tests
  // ==========================================================================
  
  describe('Success Case (201)', () => {
    it('calls API with correct data on submit', async () => {
      mockSuccessResponse(0.85);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
          messageId="msg_123"
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const submitButton = screen.getByTestId('promote-hypothesis-button-submit');
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(mockProposeHypothesis).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'What is the population of New York City',
            confidence_score: 0.75,
            message_id: 'msg_123',
          }),
          '/api'
        );
      });
    });
    
    it('shows success toast with score on 201', async () => {
      mockSuccessResponse(0.85);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        const toast = screen.getByTestId('promote-hypothesis-button-toast');
        expect(toast).toHaveAttribute('data-toast-type', 'success');
        expect(screen.getByText('Hypothesis Created')).toBeInTheDocument();
        expect(screen.getByText(/Score: 85%/)).toBeInTheDocument();
      });
    });
    
    it('calls onSuccess callback on 201', async () => {
      mockSuccessResponse(0.85);
      const onSuccess = jest.fn();
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
          onSuccess={onSuccess}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(
          expect.objectContaining({
            status: 201,
            data: expect.objectContaining({
              hypothesis_id: 'hyp_123',
              score: 0.85,
              persisted: true,
            }),
          })
        );
      });
    });
    
    it('closes modal after successful submission', async () => {
      mockSuccessResponse(0.85);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(screen.getByTestId('promote-hypothesis-button-toast')).toBeInTheDocument();
      });
      
      // Wait for modal to close (2s delay)
      await waitFor(() => {
        expect(screen.queryByTestId('promote-hypothesis-button-modal')).not.toBeInTheDocument();
      }, { timeout: 3000 });
    });
  });
  
  // ==========================================================================
  // Threshold Not Met (202) Tests
  // ==========================================================================
  
  describe('Threshold Not Met (202)', () => {
    it('shows info toast with score on 202', async () => {
      mockThresholdNotMetResponse(0.55);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_ANALYTICS}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        const toast = screen.getByTestId('promote-hypothesis-button-toast');
        expect(toast).toHaveAttribute('data-toast-type', 'info');
        expect(screen.getByText('Hypothesis Below Threshold')).toBeInTheDocument();
        expect(screen.getByText(/Score: 55%/)).toBeInTheDocument();
        expect(screen.getByText(/Pareto threshold/)).toBeInTheDocument();
      });
    });
    
    it('shows "View details" button on 202', async () => {
      mockThresholdNotMetResponse(0.55);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(screen.getByTestId('promote-hypothesis-button-view-details')).toBeInTheDocument();
      });
    });
    
    it('calls onSuccess callback on 202', async () => {
      mockThresholdNotMetResponse(0.55);
      const onSuccess = jest.fn();
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
          onSuccess={onSuccess}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(
          expect.objectContaining({
            status: 202,
            data: expect.objectContaining({
              score: 0.55,
              persisted: false,
            }),
          })
        );
      });
    });
  });
  
  // ==========================================================================
  // Error Handling Tests
  // ==========================================================================
  
  describe('Error Handling', () => {
    it('shows error toast on API failure', async () => {
      mockErrorResponse('Network error');
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        const toast = screen.getByTestId('promote-hypothesis-button-toast');
        expect(toast).toHaveAttribute('data-toast-type', 'error');
        expect(screen.getByText('Proposal Failed')).toBeInTheDocument();
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
      });
    });
    
    it('calls onError callback on failure', async () => {
      mockErrorResponse('Server error');
      const onError = jest.fn();
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
          onError={onError}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });
    
    it('shows validation error when fields are empty', async () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      const titleInput = screen.getByTestId('promote-hypothesis-button-title-input');
      fireEvent.change(titleInput, { target: { value: '   ' } }); // Whitespace only
      
      const submitButton = screen.getByTestId('promote-hypothesis-button-submit');
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/required/i)).toBeInTheDocument();
      });
    });
  });
  
  // ==========================================================================
  // Telemetry Tests
  // ==========================================================================
  
  describe('Telemetry', () => {
    it('fires modal_opened event when modal opens', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
          messageId="msg_123"
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      expect(mockTelemetryTrack).toHaveBeenCalledWith(
        'hypothesis.promote.modal_opened',
        expect.objectContaining({
          user_role: ROLE_PRO,
          message_id: 'msg_123',
          has_question: true,
          evidence_count: 3,
        })
      );
    });
    
    it('fires submitted event on form submit', async () => {
      mockSuccessResponse(0.85);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_ANALYTICS}
          question={mockQuestion}
          evidence={mockEvidence}
          messageId="msg_123"
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(mockTelemetryTrack).toHaveBeenCalledWith(
          'hypothesis.propose.submitted',
          expect.objectContaining({
            user_role: ROLE_ANALYTICS,
            message_id: 'msg_123',
          })
        );
      });
    });
    
    it('fires success event on 201', async () => {
      mockSuccessResponse(0.85);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(mockTelemetryTrack).toHaveBeenCalledWith(
          'hypothesis.propose.success',
          expect.objectContaining({
            hypothesis_id: 'hyp_123',
            score: 0.85,
            persisted: true,
          })
        );
      });
    });
    
    it('fires threshold_not_met event on 202', async () => {
      mockThresholdNotMetResponse(0.55);
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(mockTelemetryTrack).toHaveBeenCalledWith(
          'hypothesis.propose.threshold_not_met',
          expect.objectContaining({
            score: 0.55,
            persisted: false,
            threshold_reason: 'pareto_threshold',
          })
        );
      });
    });
    
    it('fires error event on failure', async () => {
      mockErrorResponse('API Error');
      
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(mockTelemetryTrack).toHaveBeenCalledWith(
          'hypothesis.propose.error',
          expect.objectContaining({
            error: 'API Error',
          })
        );
      });
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('General/Scholars do not see button', () => {
      const { rerender } = render(
        <PromoteHypothesisButton
          userRole={ROLE_GENERAL}
          question={mockQuestion}
        />
      );
      
      expect(screen.queryByTestId('promote-hypothesis-button')).not.toBeInTheDocument();
      
      rerender(
        <PromoteHypothesisButton
          userRole={ROLE_SCHOLARS}
          question={mockQuestion}
        />
      );
      
      expect(screen.queryByTestId('promote-hypothesis-button')).not.toBeInTheDocument();
    });
    
    it('Pro/Analytics do see button', () => {
      const { rerender } = render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      expect(screen.getByTestId('promote-hypothesis-button')).toBeInTheDocument();
      
      rerender(
        <PromoteHypothesisButton
          userRole={ROLE_ANALYTICS}
          question={mockQuestion}
        />
      );
      
      expect(screen.getByTestId('promote-hypothesis-button')).toBeInTheDocument();
    });
    
    it('success (201) and threshold-not-met (202) paths tested', async () => {
      // Test 201
      mockSuccessResponse(0.85);
      
      const { rerender } = render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(screen.getByText(/Hypothesis Created/)).toBeInTheDocument();
      });
      
      // Clear and test 202
      mockThresholdNotMetResponse(0.55);
      
      rerender(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
          evidence={mockEvidence}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      fireEvent.click(screen.getByTestId('promote-hypothesis-button-submit'));
      
      await waitFor(() => {
        expect(screen.getByText(/Below Threshold/)).toBeInTheDocument();
      });
    });
    
    it('telemetry event fired', () => {
      render(
        <PromoteHypothesisButton
          userRole={ROLE_PRO}
          question={mockQuestion}
        />
      );
      
      fireEvent.click(screen.getByTestId('promote-hypothesis-button'));
      
      expect(mockTelemetryTrack).toHaveBeenCalled();
    });
  });
});
