/**
 * PromoteHypothesisButton Component
 * 
 * Role-gated button for promoting evidence to hypotheses.
 * 
 * Features:
 * - Visible only to Pro and Analytics roles
 * - Modal form with pre-filled title and description
 * - Integrates with POST /hypotheses/propose
 * - Toast notifications for 201 (success) and 202 (threshold not met)
 * - Telemetry tracking
 */

import React, { useState, useCallback } from 'react';
import { Role, ROLE_PRO, ROLE_ANALYTICS } from '../lib/roles';
import { proposeHypothesis, ProposeHypothesisRequest, ProposeHypothesisResponse } from '../api/hypotheses';
import '../styles/promote-hypothesis.css';

// ============================================================================
// Types
// ============================================================================

export interface PromoteHypothesisButtonProps {
  /** Current user role */
  userRole: Role;
  
  /** User's question (for pre-filling title) */
  question?: string;
  
  /** Top evidence items (for pre-filling description) */
  evidence?: string[];
  
  /** Message ID for context */
  messageId?: string;
  
  /** API base URL */
  apiBaseUrl?: string;
  
  /** Callback when hypothesis is successfully proposed */
  onSuccess?: (response: ProposeHypothesisResponse) => void;
  
  /** Callback when proposal fails */
  onError?: (error: Error) => void;
  
  /** Custom class name */
  className?: string;
  
  /** Test ID */
  testId?: string;
}

export interface ToastMessage {
  type: 'success' | 'info' | 'error';
  title: string;
  message: string;
  details?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if user can promote hypotheses (Pro or Analytics only).
 */
function canPromoteHypothesis(userRole: Role): boolean {
  return userRole === ROLE_PRO || userRole === ROLE_ANALYTICS;
}

/**
 * Generate title suggestion from question.
 */
function generateTitleFromQuestion(question?: string): string {
  if (!question) return '';
  
  // Remove question marks and limit length
  let title = question.replace(/\?+$/, '').trim();
  
  if (title.length > 100) {
    title = title.substring(0, 97) + '...';
  }
  
  return title;
}

/**
 * Generate description from top evidence.
 */
function generateDescriptionFromEvidence(evidence?: string[]): string {
  if (!evidence || evidence.length === 0) return '';
  
  // Take top 3 evidence items
  const topEvidence = evidence.slice(0, 3);
  
  return topEvidence
    .map((item, idx) => `${idx + 1}. ${item}`)
    .join('\n\n');
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

// ============================================================================
// Component
// ============================================================================

export const PromoteHypothesisButton: React.FC<PromoteHypothesisButtonProps> = ({
  userRole,
  question,
  evidence,
  messageId,
  apiBaseUrl = '/api',
  onSuccess,
  onError,
  className = '',
  testId = 'promote-hypothesis-button',
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  
  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [confidence, setConfidence] = useState(0.75);
  
  // Check if user can see button
  const canPromote = canPromoteHypothesis(userRole);
  
  if (!canPromote) {
    return null; // Hide button for unauthorized roles
  }
  
  // Open modal and pre-fill form
  const handleOpenModal = useCallback(() => {
    setTitle(generateTitleFromQuestion(question));
    setDescription(generateDescriptionFromEvidence(evidence));
    setIsModalOpen(true);
    
    sendTelemetry('hypothesis.promote.modal_opened', {
      user_role: userRole,
      message_id: messageId,
      has_question: !!question,
      evidence_count: evidence?.length || 0,
    });
  }, [question, evidence, userRole, messageId]);
  
  // Close modal
  const handleCloseModal = useCallback(() => {
    setIsModalOpen(false);
    setTitle('');
    setDescription('');
    setConfidence(0.75);
  }, []);
  
  // Submit hypothesis
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title.trim() || !description.trim()) {
      setToast({
        type: 'error',
        title: 'Validation Error',
        message: 'Title and description are required',
      });
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const request: ProposeHypothesisRequest = {
        title: title.trim(),
        description: description.trim(),
        confidence_score: confidence,
        message_id: messageId,
      };
      
      sendTelemetry('hypothesis.propose.submitted', {
        user_role: userRole,
        message_id: messageId,
        title_length: title.length,
        description_length: description.length,
        confidence: confidence,
      });
      
      const response = await proposeHypothesis(request, apiBaseUrl);
      
      // Handle different status codes
      if (response.status === 201) {
        // Successfully persisted
        setToast({
          type: 'success',
          title: 'Hypothesis Created',
          message: `Your hypothesis "${response.data.title}" has been successfully created.`,
          details: `Score: ${Math.round(response.data.score * 100)}%`,
        });
        
        sendTelemetry('hypothesis.propose.success', {
          user_role: userRole,
          message_id: messageId,
          hypothesis_id: response.data.hypothesis_id,
          score: response.data.score,
          persisted: true,
        });
        
        onSuccess?.(response);
        
        // Close modal after success
        setTimeout(() => {
          handleCloseModal();
        }, 2000);
      } else if (response.status === 202) {
        // Below threshold, not persisted
        setToast({
          type: 'info',
          title: 'Hypothesis Below Threshold',
          message: `Score: ${Math.round(response.data.score * 100)}%. This hypothesis did not meet the Pareto threshold for persistence.`,
          details: 'The hypothesis was evaluated but not added to the knowledge base. It may still inform future queries.',
        });
        
        sendTelemetry('hypothesis.propose.threshold_not_met', {
          user_role: userRole,
          message_id: messageId,
          score: response.data.score,
          persisted: false,
          threshold_reason: 'pareto_threshold',
        });
        
        onSuccess?.(response);
      }
    } catch (error) {
      console.error('Failed to propose hypothesis:', error);
      
      setToast({
        type: 'error',
        title: 'Proposal Failed',
        message: error instanceof Error ? error.message : 'An unknown error occurred',
      });
      
      sendTelemetry('hypothesis.propose.error', {
        user_role: userRole,
        message_id: messageId,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
      
      onError?.(error instanceof Error ? error : new Error('Unknown error'));
    } finally {
      setIsSubmitting(false);
    }
  }, [title, description, confidence, messageId, userRole, apiBaseUrl, onSuccess, onError, handleCloseModal]);
  
  // Close toast
  const handleCloseToast = useCallback(() => {
    setToast(null);
  }, []);
  
  return (
    <>
      {/* Promote Button */}
      <button
        className={`promote-hypothesis-button ${className}`}
        onClick={handleOpenModal}
        data-testid={testId}
        title="Promote this answer to a hypothesis"
      >
        <span className="button-icon">💡</span>
        <span className="button-text">Promote to Hypothesis</span>
      </button>
      
      {/* Modal */}
      {isModalOpen && (
        <div 
          className="promote-hypothesis-modal-overlay"
          onClick={handleCloseModal}
          data-testid={`${testId}-modal-overlay`}
        >
          <div 
            className="promote-hypothesis-modal"
            onClick={(e) => e.stopPropagation()}
            data-testid={`${testId}-modal`}
          >
            <div className="modal-header">
              <h2>Promote to Hypothesis</h2>
              <button 
                className="modal-close"
                onClick={handleCloseModal}
                aria-label="Close modal"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="modal-form">
              <div className="form-group">
                <label htmlFor="hypothesis-title">
                  Title <span className="required">*</span>
                </label>
                <input
                  id="hypothesis-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter hypothesis title..."
                  maxLength={200}
                  required
                  data-testid={`${testId}-title-input`}
                />
                <span className="char-count">{title.length}/200</span>
              </div>
              
              <div className="form-group">
                <label htmlFor="hypothesis-description">
                  Description <span className="required">*</span>
                </label>
                <textarea
                  id="hypothesis-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Enter hypothesis description..."
                  rows={6}
                  maxLength={2000}
                  required
                  data-testid={`${testId}-description-input`}
                />
                <span className="char-count">{description.length}/2000</span>
              </div>
              
              <div className="form-group">
                <label htmlFor="hypothesis-confidence">
                  Confidence: {Math.round(confidence * 100)}%
                </label>
                <input
                  id="hypothesis-confidence"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={confidence}
                  onChange={(e) => setConfidence(parseFloat(e.target.value))}
                  data-testid={`${testId}-confidence-input`}
                />
                <div className="confidence-labels">
                  <span>Low</span>
                  <span>Medium</span>
                  <span>High</span>
                </div>
              </div>
              
              <div className="modal-info">
                <p>
                  <strong>Note:</strong> Hypotheses are evaluated using a Pareto threshold. 
                  High-quality hypotheses (201) will be persisted to the knowledge base. 
                  Lower-quality hypotheses (202) will be acknowledged but not stored.
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
                  disabled={isSubmitting || !title.trim() || !description.trim()}
                  data-testid={`${testId}-submit`}
                >
                  {isSubmitting ? (
                    <>
                      <span className="spinner">⏳</span>
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <span>Propose Hypothesis</span>
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
          className={`promote-hypothesis-toast toast-${toast.type}`}
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
            {toast.details && (
              <p className="toast-details">{toast.details}</p>
            )}
            {toast.type === 'info' && (
              <button 
                className="toast-link"
                onClick={() => {
                  // In a real app, this would navigate to a details page
                  alert('Details: The Pareto threshold ensures only high-quality hypotheses are persisted to maintain knowledge base integrity.');
                }}
                data-testid={`${testId}-view-details`}
              >
                View details
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default PromoteHypothesisButton;
