/**
 * ProposeAuraButton Tests
 * 
 * Comprehensive test suite for ProposeAuraButton component including:
 * - Role gating (Pro/Analytics only)
 * - Pre-linked hypothesis flow
 * - Manual hypothesis selection flow
 * - Starter task generation from compare_summary
 * - Success toast and navigation
 * - Error handling
 * - Telemetry tracking
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProposeAuraButton from '../../app/components/ProposeAuraButton';
import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS } from '../../app/lib/roles';
import * as auraAPI from '../../app/api/aura';
import { CompareSummary } from '../../app/components/CompareCard';

// ============================================================================
// Mock API
// ============================================================================

jest.mock('../../app/api/aura');

const mockProposeAuraProject = auraAPI.proposeAuraProject as jest.MockedFunction<typeof auraAPI.proposeAuraProject>;
const mockListRecentHypotheses = auraAPI.listRecentHypotheses as jest.MockedFunction<typeof auraAPI.listRecentHypotheses>;

function mockSuccessResponse(projectId: string = 'proj_123') {
  mockProposeAuraProject.mockResolvedValue({
    data: {
      project_id: projectId,
      title: 'Test Project',
      description: 'Test description',
      hypothesis_id: 'hyp_123',
      starter_tasks: [
        { task_id: 'task_1', title: 'Task 1', status: 'pending' },
        { task_id: 'task_2', title: 'Task 2', status: 'pending' },
      ],
      created_at: '2023-10-30T12:00:00Z',
    },
  });
}

function mockErrorResponse(message: string = 'Server error') {
  mockProposeAuraProject.mockRejectedValue(new Error(message));
}

function mockHypothesesList() {
  mockListRecentHypotheses.mockResolvedValue([
    { hypothesis_id: 'hyp_1', title: 'Hypothesis 1', score: 0.85, created_at: '2023-10-30T11:00:00Z' },
    { hypothesis_id: 'hyp_2', title: 'Hypothesis 2', score: 0.75, created_at: '2023-10-30T10:00:00Z' },
    { hypothesis_id: 'hyp_3', title: 'Hypothesis 3', score: 0.65, created_at: '2023-10-30T09:00:00Z' },
  ]);
}

function mockEmptyHypothesesList() {
  mockListRecentHypotheses.mockResolvedValue([]);
}

// ============================================================================
// Mock Navigation
// ============================================================================

const mockNavigate = jest.fn();

beforeEach(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { href: '' },
  });
});

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

const mockCompareSummary: CompareSummary = {
  stance_a: 'The population is 8.3 million according to Census 2020',
  stance_b: 'The population is approximately 8.8 million including undocumented residents',
  recommendation: 'a',
  confidence: 0.75,
  internal_evidence: [
    { text: 'Census 2020 shows official count of 8,336,817', confidence: 0.92 },
    { text: 'Historical data confirms this methodology', confidence: 0.85 },
  ],
  external_evidence: [],
};

// ============================================================================
// Tests
// ============================================================================

describe('ProposeAuraButton', () => {
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
        <ProposeAuraButton
          userRole={ROLE_GENERAL}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.queryByTestId('propose-aura-button')).not.toBeInTheDocument();
    });
    
    it('hides button for Scholars users', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_SCHOLARS}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.queryByTestId('propose-aura-button')).not.toBeInTheDocument();
    });
    
    it('hides button for Ops users', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_OPS}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.queryByTestId('propose-aura-button')).not.toBeInTheDocument();
    });
    
    it('shows button for Pro users', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.getByTestId('propose-aura-button')).toBeInTheDocument();
    });
    
    it('shows button for Analytics users', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_ANALYTICS}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.getByTestId('propose-aura-button')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Modal Tests
  // ==========================================================================
  
  describe('Modal Functionality', () => {
    it('opens modal when button clicked', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      const button = screen.getByTestId('propose-aura-button');
      fireEvent.click(button);
      
      expect(screen.getByTestId('propose-aura-button-modal')).toBeInTheDocument();
      expect(screen.getByText('Create AURA Project')).toBeInTheDocument();
    });
    
    it('closes modal when close button clicked', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      expect(screen.getByTestId('propose-aura-button-modal')).toBeInTheDocument();
      
      const closeButton = screen.getByLabelText('Close modal');
      fireEvent.click(closeButton);
      
      expect(screen.queryByTestId('propose-aura-button-modal')).not.toBeInTheDocument();
    });
    
    it('closes modal when overlay clicked', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      const overlay = screen.getByTestId('propose-aura-button-modal-overlay');
      fireEvent.click(overlay);
      
      expect(screen.queryByTestId('propose-aura-button-modal')).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Pre-linked Hypothesis Flow Tests
  // ==========================================================================
  
  describe('Pre-linked Hypothesis Flow', () => {
    it('shows pre-linked hypothesis when hypothesisId provided', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_abc123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      expect(screen.getByTestId('propose-aura-button-pre-linked')).toBeInTheDocument();
      expect(screen.getByText('Pre-linked from chat response')).toBeInTheDocument();
      expect(screen.getByText('hyp_abc123')).toBeInTheDocument();
    });
    
    it('does not load hypothesis list when pre-linked', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_abc123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      expect(mockListRecentHypotheses).not.toHaveBeenCalled();
    });
    
    it('does not show hypothesis select dropdown when pre-linked', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_abc123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      expect(screen.queryByTestId('propose-aura-button-hypothesis-select')).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Manual Hypothesis Selection Flow Tests
  // ==========================================================================
  
  describe('Manual Hypothesis Selection Flow', () => {
    it('loads recent hypotheses when no hypothesisId provided', async () => {
      mockHypothesesList();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      await waitFor(() => {
        expect(mockListRecentHypotheses).toHaveBeenCalledWith(
          { limit: 10 },
          '/api'
        );
      });
    });
    
    it('shows hypothesis dropdown when loaded', async () => {
      mockHypothesesList();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      await waitFor(() => {
        expect(screen.getByTestId('propose-aura-button-hypothesis-select')).toBeInTheDocument();
      });
    });
    
    it('displays hypothesis options with scores', async () => {
      mockHypothesesList();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      await waitFor(() => {
        const select = screen.getByTestId('propose-aura-button-hypothesis-select');
        expect(select).toBeInTheDocument();
        expect(screen.getByText(/Hypothesis 1.*85%/)).toBeInTheDocument();
        expect(screen.getByText(/Hypothesis 2.*75%/)).toBeInTheDocument();
      });
    });
    
    it('allows selecting a hypothesis', async () => {
      mockHypothesesList();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      await waitFor(() => {
        expect(screen.getByTestId('propose-aura-button-hypothesis-select')).toBeInTheDocument();
      });
      
      const select = screen.getByTestId('propose-aura-button-hypothesis-select') as HTMLSelectElement;
      fireEvent.change(select, { target: { value: 'hyp_2' } });
      
      expect(select.value).toBe('hyp_2');
    });
    
    it('shows message when no hypotheses available', async () => {
      mockEmptyHypothesesList();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      await waitFor(() => {
        expect(screen.getByText(/No recent hypotheses found/)).toBeInTheDocument();
      });
    });
  });
  
  // ==========================================================================
  // Starter Tasks Tests
  // ==========================================================================
  
  describe('Starter Tasks', () => {
    it('generates starter tasks from compare_summary', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      expect(screen.getByTestId('propose-aura-button-starter-tasks')).toBeInTheDocument();
      
      // Should have 3 tasks (stance_a, stance_b, top evidence)
      expect(screen.getByTestId('propose-aura-button-task-0')).toBeInTheDocument();
      expect(screen.getByTestId('propose-aura-button-task-1')).toBeInTheDocument();
      expect(screen.getByTestId('propose-aura-button-task-2')).toBeInTheDocument();
    });
    
    it('allows editing starter tasks', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      const taskInput = screen.getByTestId('propose-aura-button-task-0') as HTMLInputElement;
      fireEvent.change(taskInput, { target: { value: 'Custom task' } });
      
      expect(taskInput.value).toBe('Custom task');
    });
    
    it('allows removing starter tasks', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      const removeButton = screen.getAllByLabelText('Remove task')[0];
      fireEvent.click(removeButton);
      
      // Task should be removed
      expect(screen.queryByTestId('propose-aura-button-task-2')).not.toBeInTheDocument();
    });
    
    it('allows adding starter tasks up to 3', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={undefined} // No tasks initially
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      const addButton = screen.getByTestId('propose-aura-button-add-task');
      
      // Add first task
      fireEvent.click(addButton);
      expect(screen.getByTestId('propose-aura-button-task-0')).toBeInTheDocument();
      
      // Add second task
      fireEvent.click(addButton);
      expect(screen.getByTestId('propose-aura-button-task-1')).toBeInTheDocument();
      
      // Add third task
      fireEvent.click(addButton);
      expect(screen.getByTestId('propose-aura-button-task-2')).toBeInTheDocument();
      
      // Button should be hidden after 3 tasks
      expect(screen.queryByTestId('propose-aura-button-add-task')).not.toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Success Flow Tests
  // ==========================================================================
  
  describe('Success Flow', () => {
    it('calls API with correct data on submit', async () => {
      mockSuccessResponse('proj_abc');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
          messageId="msg_123"
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      const titleInput = screen.getByTestId('propose-aura-button-title-input');
      fireEvent.change(titleInput, { target: { value: 'My Project' } });
      
      const descInput = screen.getByTestId('propose-aura-button-description-input');
      fireEvent.change(descInput, { target: { value: 'Project description' } });
      
      const submitButton = screen.getByTestId('propose-aura-button-submit');
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(mockProposeAuraProject).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'My Project',
            description: 'Project description',
            hypothesis_id: 'hyp_123',
            message_id: 'msg_123',
          }),
          '/api'
        );
      });
    });
    
    it('shows success toast on project creation', async () => {
      mockSuccessResponse('proj_abc');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        const toast = screen.getByTestId('propose-aura-button-toast');
        expect(toast).toHaveAttribute('data-toast-type', 'success');
        expect(screen.getByText('AURA Project Created')).toBeInTheDocument();
      });
    });
    
    it('shows "View Project" link in toast', async () => {
      mockSuccessResponse('proj_abc');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        const actionLink = screen.getByTestId('propose-aura-button-toast-action');
        expect(actionLink).toHaveAttribute('href', '/aura/projects/proj_abc');
        expect(actionLink).toHaveTextContent('View Project');
      });
    });
    
    it('navigates to project after success', async () => {
      mockSuccessResponse('proj_abc');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        expect(screen.getByTestId('propose-aura-button-toast')).toBeInTheDocument();
      });
      
      // Wait for navigation (1.5s delay)
      await waitFor(() => {
        expect(window.location.href).toBe('/aura/projects/proj_abc');
      }, { timeout: 2000 });
    });
    
    it('calls onSuccess callback', async () => {
      mockSuccessResponse('proj_abc');
      const onSuccess = jest.fn();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
          onSuccess={onSuccess}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(
          expect.objectContaining({
            data: expect.objectContaining({
              project_id: 'proj_abc',
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
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        const toast = screen.getByTestId('propose-aura-button-toast');
        expect(toast).toHaveAttribute('data-toast-type', 'error');
        expect(screen.getByText('Proposal Failed')).toBeInTheDocument();
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
      });
    });
    
    it('calls onError callback on failure', async () => {
      mockErrorResponse('Server error');
      const onError = jest.fn();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
          onError={onError}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });
  });
  
  // ==========================================================================
  // Telemetry Tests
  // ==========================================================================
  
  describe('Telemetry', () => {
    it('fires modal_opened event when modal opens', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
          messageId="msg_123"
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      expect(mockTelemetryTrack).toHaveBeenCalledWith(
        'aura.propose.modal_opened',
        expect.objectContaining({
          user_role: ROLE_PRO,
          message_id: 'msg_123',
          has_hypothesis_id: true,
          has_compare_summary: true,
        })
      );
    });
    
    it('fires submitted event on form submit', async () => {
      mockSuccessResponse();
      
      render(
        <ProposeAuraButton
          userRole={ROLE_ANALYTICS}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
          messageId="msg_123"
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        expect(mockTelemetryTrack).toHaveBeenCalledWith(
          'aura.propose.submitted',
          expect.objectContaining({
            user_role: ROLE_ANALYTICS,
            message_id: 'msg_123',
            hypothesis_id: 'hyp_123',
          })
        );
      });
    });
    
    it('fires success event on project creation', async () => {
      mockSuccessResponse('proj_abc');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        expect(mockTelemetryTrack).toHaveBeenCalledWith(
          'aura.propose.success',
          expect.objectContaining({
            project_id: 'proj_abc',
            hypothesis_id: 'hyp_123',
          })
        );
      });
    });
    
    it('fires error event on failure', async () => {
      mockErrorResponse('API Error');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        expect(mockTelemetryTrack).toHaveBeenCalledWith(
          'aura.propose.error',
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
    it('role gating respected', () => {
      // Pro can see
      const { rerender } = render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.getByTestId('propose-aura-button')).toBeInTheDocument();
      
      // Analytics can see
      rerender(
        <ProposeAuraButton
          userRole={ROLE_ANALYTICS}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.getByTestId('propose-aura-button')).toBeInTheDocument();
      
      // General cannot see
      rerender(
        <ProposeAuraButton
          userRole={ROLE_GENERAL}
          compareSummary={mockCompareSummary}
        />
      );
      
      expect(screen.queryByTestId('propose-aura-button')).not.toBeInTheDocument();
    });
    
    it('success toast and navigation', async () => {
      mockSuccessResponse('proj_abc');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      // Success toast shown
      await waitFor(() => {
        expect(screen.getByTestId('propose-aura-button-toast')).toBeInTheDocument();
        expect(screen.getByText('AURA Project Created')).toBeInTheDocument();
      });
      
      // Navigation occurs
      await waitFor(() => {
        expect(window.location.href).toBe('/aura/projects/proj_abc');
      }, { timeout: 2000 });
    });
    
    it('error handling shown', async () => {
      mockErrorResponse('Test error');
      
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      fireEvent.change(screen.getByTestId('propose-aura-button-title-input'), { target: { value: 'Test' } });
      fireEvent.change(screen.getByTestId('propose-aura-button-description-input'), { target: { value: 'Desc' } });
      fireEvent.click(screen.getByTestId('propose-aura-button-submit'));
      
      await waitFor(() => {
        expect(screen.getByText('Proposal Failed')).toBeInTheDocument();
        expect(screen.getByText(/Test error/)).toBeInTheDocument();
      });
    });
    
    it('telemetry event fired', () => {
      render(
        <ProposeAuraButton
          userRole={ROLE_PRO}
          hypothesisId="hyp_123"
          compareSummary={mockCompareSummary}
        />
      );
      
      fireEvent.click(screen.getByTestId('propose-aura-button'));
      
      expect(mockTelemetryTrack).toHaveBeenCalled();
    });
  });
});
