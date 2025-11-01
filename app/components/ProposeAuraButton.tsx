/**
 * ProposeAuraButton Component
 * 
 * Role-gated button for creating AURA projects from chat responses.
 * 
 * Features:
 * - Visible only to Pro and Analytics roles
 * - Pre-links hypothesis if already created, otherwise prompts selection
 * - Generates 1-3 starter tasks from compare_summary
 * - Deep-links to new project view on success
 * - Telemetry tracking
 */

import React, { useState, useCallback, useEffect } from 'react';
import { Role, ROLE_PRO, ROLE_ANALYTICS } from '../lib/roles';
import { proposeAuraProject, ProposeAuraProjectRequest, ProposeAuraProjectResponse, listRecentHypotheses, HypothesisSummary } from '../api/aura';
import { CompareSummary } from './CompareCard';
import '../styles/propose-aura.css';

// ============================================================================
// Types
// ============================================================================

export interface ProposeAuraButtonProps {
  /** Current user role */
  userRole: Role;
  
  /** Hypothesis ID if already created (pre-link) */
  hypothesisId?: string;
  
  /** Compare summary for generating starter tasks */
  compareSummary?: CompareSummary;
  
  /** Message ID for context */
  messageId?: string;
  
  /** API base URL */
  apiBaseUrl?: string;
  
  /** Callback when project is successfully created */
  onSuccess?: (response: ProposeAuraProjectResponse) => void;
  
  /** Callback when proposal fails */
  onError?: (error: Error) => void;
  
  /** Custom class name */
  className?: string;
  
  /** Test ID */
  testId?: string;
}

export interface ToastMessage {
  type: 'success' | 'error';
  title: string;
  message: string;
  actionUrl?: string;
  actionLabel?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if user can propose AURA projects (Pro or Analytics only).
 */
function canProposeAura(userRole: Role): boolean {
  return userRole === ROLE_PRO || userRole === ROLE_ANALYTICS;
}

/**
 * Generate starter tasks from compare summary.
 * Returns 1-3 tasks based on available evidence.
 */
function generateStarterTasks(compareSummary?: CompareSummary): string[] {
  if (!compareSummary) return [];
  
  const tasks: string[] = [];
  
  // Task 1: Investigate stance A
  if (compareSummary.stance_a) {
    tasks.push(`Investigate: ${compareSummary.stance_a.substring(0, 80)}${compareSummary.stance_a.length > 80 ? '...' : ''}`);
  }
  
  // Task 2: Investigate stance B
  if (compareSummary.stance_b && tasks.length < 3) {
    tasks.push(`Investigate: ${compareSummary.stance_b.substring(0, 80)}${compareSummary.stance_b.length > 80 ? '...' : ''}`);
  }
  
  // Task 3: Validate top evidence
  if (compareSummary.internal_evidence?.length > 0 && tasks.length < 3) {
    const topEvidence = compareSummary.internal_evidence[0];
    tasks.push(`Validate: ${topEvidence.text.substring(0, 80)}${topEvidence.text.length > 80 ? '...' : ''}`);
  }
  
  return tasks.slice(0, 3); // Ensure max 3 tasks
}

/**
 * Send telemetry event.
 */
function sendTelemetry(event: string, data: Record<string, any>) {
  if (typeof window !== 'undefined' && (window as any).analytics) {
    (window as any).analytics.track(event, data);
  } else {
    console.log('[Telemetry]', event, data);
  }
}

/**
 * Navigate to project view.
 */
function navigateToProject(projectId: string) {
  if (typeof window !== 'undefined') {
    window.location.href = `/aura/projects/${projectId}`;
  }
}

// ============================================================================
// Component
// ============================================================================

export const ProposeAuraButton: React.FC<ProposeAuraButtonProps> = ({
  userRole,
  hypothesisId,
  compareSummary,
  messageId,
  apiBaseUrl = '/api',
  onSuccess,
  onError,
  className = '',
  testId = 'propose-aura-button',
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  
  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [selectedHypothesisId, setSelectedHypothesisId] = useState(hypothesisId || '');
  const [recentHypotheses, setRecentHypotheses] = useState<HypothesisSummary[]>([]);
  const [isLoadingHypotheses, setIsLoadingHypotheses] = useState(false);
  const [starterTasks, setStarterTasks] = useState<string[]>([]);
  
  // Check if user can see button
  const canPropose = canProposeAura(userRole);
  
  if (!canPropose) {
    return null; // Hide button for unauthorized roles
  }
  
  // Load recent hypotheses when modal opens (if no pre-linked hypothesis)
  useEffect(() => {
    if (isModalOpen && !hypothesisId) {
      setIsLoadingHypotheses(true);
      
      listRecentHypotheses({ limit: 10 }, apiBaseUrl)
        .then((hypotheses) => {
          setRecentHypotheses(hypotheses);
          if (hypotheses.length > 0 && !selectedHypothesisId) {
            setSelectedHypothesisId(hypotheses[0].hypothesis_id);
          }
        })
        .catch((error) => {
          console.error('Failed to load hypotheses:', error);
          setRecentHypotheses([]);
        })
        .finally(() => {
          setIsLoadingHypotheses(false);
        });
    }
  }, [isModalOpen, hypothesisId, apiBaseUrl, selectedHypothesisId]);
  
  // Open modal and generate starter tasks
  const handleOpenModal = useCallback(() => {
    const tasks = generateStarterTasks(compareSummary);
    setStarterTasks(tasks);
    setTitle('');
    setDescription('');
    setSelectedHypothesisId(hypothesisId || '');
    setIsModalOpen(true);
    
    sendTelemetry('aura.propose.modal_opened', {
      user_role: userRole,
      message_id: messageId,
      has_hypothesis_id: !!hypothesisId,
      has_compare_summary: !!compareSummary,
      starter_tasks_count: tasks.length,
    });
  }, [compareSummary, hypothesisId, userRole, messageId]);
  
  // Close modal
  const handleCloseModal = useCallback(() => {
    setIsModalOpen(false);
    setTitle('');
    setDescription('');
    setStarterTasks([]);
  }, []);
  
  // Submit project
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title.trim() || !description.trim() || !selectedHypothesisId) {
      setToast({
        type: 'error',
        title: 'Validation Error',
        message: 'Title, description, and hypothesis are required',
      });
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const request: ProposeAuraProjectRequest = {
        title: title.trim(),
        description: description.trim(),
        hypothesis_id: selectedHypothesisId,
        starter_tasks: starterTasks.filter(t => t.trim().length > 0),
        message_id: messageId,
      };
      
      sendTelemetry('aura.propose.submitted', {
        user_role: userRole,
        message_id: messageId,
        hypothesis_id: selectedHypothesisId,
        title_length: title.length,
        description_length: description.length,
        starter_tasks_count: starterTasks.length,
      });
      
      const response = await proposeAuraProject(request, apiBaseUrl);
      
      setToast({
        type: 'success',
        title: 'AURA Project Created',
        message: `Project "${response.data.title}" has been created successfully.`,
        actionUrl: `/aura/projects/${response.data.project_id}`,
        actionLabel: 'View Project',
      });
      
      sendTelemetry('aura.propose.success', {
        user_role: userRole,
        message_id: messageId,
        project_id: response.data.project_id,
        hypothesis_id: selectedHypothesisId,
        tasks_created: response.data.starter_tasks?.length || 0,
      });
      
      onSuccess?.(response);
      
      // Navigate to project after short delay
      setTimeout(() => {
        handleCloseModal();
        navigateToProject(response.data.project_id);
      }, 1500);
    } catch (error) {
      console.error('Failed to propose AURA project:', error);
      
      setToast({
        type: 'error',
        title: 'Proposal Failed',
        message: error instanceof Error ? error.message : 'An unknown error occurred',
      });
      
      sendTelemetry('aura.propose.error', {
        user_role: userRole,
        message_id: messageId,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
      
      onError?.(error instanceof Error ? error : new Error('Unknown error'));
    } finally {
      setIsSubmitting(false);
    }
  }, [title, description, selectedHypothesisId, starterTasks, messageId, userRole, apiBaseUrl, onSuccess, onError, handleCloseModal]);
  
  // Close toast
  const handleCloseToast = useCallback(() => {
    setToast(null);
  }, []);
  
  // Edit starter task
  const handleEditTask = useCallback((index: number, value: string) => {
    setStarterTasks(prev => {
      const updated = [...prev];
      updated[index] = value;
      return updated;
    });
  }, []);
  
  // Remove starter task
  const handleRemoveTask = useCallback((index: number) => {
    setStarterTasks(prev => prev.filter((_, i) => i !== index));
  }, []);
  
  // Add starter task
  const handleAddTask = useCallback(() => {
    if (starterTasks.length < 3) {
      setStarterTasks(prev => [...prev, '']);
    }
  }, [starterTasks.length]);
  
  return (
    <>
      {/* Propose Button */}
      <button
        className={`propose-aura-button ${className}`}
        onClick={handleOpenModal}
        data-testid={testId}
        title="Create an AURA project from this answer"
      >
        <span className="button-icon">🎯</span>
        <span className="button-text">Create AURA Project</span>
      </button>
      
      {/* Modal */}
      {isModalOpen && (
        <div 
          className="propose-aura-modal-overlay"
          onClick={handleCloseModal}
          data-testid={`${testId}-modal-overlay`}
        >
          <div 
            className="propose-aura-modal"
            onClick={(e) => e.stopPropagation()}
            data-testid={`${testId}-modal`}
          >
            <div className="modal-header">
              <h2>Create AURA Project</h2>
              <button 
                className="modal-close"
                onClick={handleCloseModal}
                aria-label="Close modal"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="modal-form">
              {/* Hypothesis Selection */}
              <div className="form-group">
                <label htmlFor="aura-hypothesis">
                  Hypothesis <span className="required">*</span>
                </label>
                {hypothesisId ? (
                  <div className="pre-linked-hypothesis" data-testid={`${testId}-pre-linked`}>
                    <span className="hypothesis-icon">💡</span>
                    <span className="hypothesis-label">Pre-linked from chat response</span>
                    <span className="hypothesis-id">{hypothesisId}</span>
                  </div>
                ) : (
                  <>
                    {isLoadingHypotheses ? (
                      <div className="loading-hypotheses">Loading recent hypotheses...</div>
                    ) : recentHypotheses.length > 0 ? (
                      <select
                        id="aura-hypothesis"
                        value={selectedHypothesisId}
                        onChange={(e) => setSelectedHypothesisId(e.target.value)}
                        required
                        data-testid={`${testId}-hypothesis-select`}
                      >
                        <option value="">Select a hypothesis...</option>
                        {recentHypotheses.map((hyp) => (
                          <option key={hyp.hypothesis_id} value={hyp.hypothesis_id}>
                            {hyp.title} (Score: {Math.round(hyp.score * 100)}%)
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="no-hypotheses">
                        No recent hypotheses found. Create a hypothesis first.
                      </div>
                    )}
                  </>
                )}
              </div>
              
              <div className="form-group">
                <label htmlFor="aura-title">
                  Project Title <span className="required">*</span>
                </label>
                <input
                  id="aura-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter project title..."
                  maxLength={150}
                  required
                  data-testid={`${testId}-title-input`}
                />
                <span className="char-count">{title.length}/150</span>
              </div>
              
              <div className="form-group">
                <label htmlFor="aura-description">
                  Description <span className="required">*</span>
                </label>
                <textarea
                  id="aura-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Enter project description..."
                  rows={4}
                  maxLength={1000}
                  required
                  data-testid={`${testId}-description-input`}
                />
                <span className="char-count">{description.length}/1000</span>
              </div>
              
              <div className="form-group">
                <label>
                  Starter Tasks (1-3)
                  <span className="optional"> - Optional</span>
                </label>
                <div className="starter-tasks" data-testid={`${testId}-starter-tasks`}>
                  {starterTasks.map((task, index) => (
                    <div key={index} className="task-item">
                      <input
                        type="text"
                        value={task}
                        onChange={(e) => handleEditTask(index, e.target.value)}
                        placeholder={`Task ${index + 1}...`}
                        maxLength={200}
                        data-testid={`${testId}-task-${index}`}
                      />
                      <button
                        type="button"
                        className="task-remove"
                        onClick={() => handleRemoveTask(index)}
                        aria-label="Remove task"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  {starterTasks.length < 3 && (
                    <button
                      type="button"
                      className="task-add"
                      onClick={handleAddTask}
                      data-testid={`${testId}-add-task`}
                    >
                      + Add Task
                    </button>
                  )}
                </div>
              </div>
              
              <div className="modal-info">
                <p>
                  <strong>Note:</strong> AURA projects help you track investigations 
                  and research tasks. The selected hypothesis will be linked to this project.
                </p>
              </div>
              
              <div className="modal-actions">
                <button
                  type="button"
                  className="button-secondary"
                  onClick={handleCloseModal}
                  disabled={isSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button-primary"
                  disabled={isSubmitting || !title.trim() || !description.trim() || !selectedHypothesisId}
                  data-testid={`${testId}-submit`}
                >
                  {isSubmitting ? (
                    <>
                      <span className="spinner">⏳</span>
                      <span>Creating...</span>
                    </>
                  ) : (
                    <>
                      <span>Create Project</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {/* Toast Notification */}
      {toast && (
        <div 
          className={`propose-aura-toast toast-${toast.type}`}
          data-testid={`${testId}-toast`}
          data-toast-type={toast.type}
        >
          <div className="toast-header">
            <strong>{toast.title}</strong>
            <button 
              className="toast-close"
              onClick={handleCloseToast}
              aria-label="Close notification"
            >
              ×
            </button>
          </div>
          <div className="toast-body">
            <p>{toast.message}</p>
            {toast.actionUrl && (
              <a 
                href={toast.actionUrl}
                className="toast-action"
                data-testid={`${testId}-toast-action`}
              >
                {toast.actionLabel || 'View'}
              </a>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default ProposeAuraButton;
