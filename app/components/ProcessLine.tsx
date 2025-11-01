/**
 * ProcessLine Component
 * 
 * Displays a single line from the process trace ledger.
 * 
 * Features:
 * - Shows step name, duration, and status
 * - Optional details, prompt, and provenance (role-dependent)
 * - Collapsible details section
 * - Color-coded status indicators
 */

import React, { useState } from 'react';
import { ProcessTraceLine } from './ProcessLedger';
import '../styles/ledger.css';

// ============================================================================
// Types
// ============================================================================

export interface ProcessLineProps {
  /** Trace line data */
  line: ProcessTraceLine;
  
  /** Line index for display */
  index: number;
  
  /** Test ID for testing */
  testId?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get status icon for a trace line.
 */
function getStatusIcon(status?: string): string {
  switch (status) {
    case 'success':
      return '✓';
    case 'error':
      return '✗';
    case 'skipped':
      return '⊘';
    default:
      return '•';
  }
}

/**
 * Get status class name for styling.
 */
function getStatusClass(status?: string): string {
  switch (status) {
    case 'success':
      return 'status-success';
    case 'error':
      return 'status-error';
    case 'skipped':
      return 'status-skipped';
    default:
      return 'status-default';
  }
}

/**
 * Format duration for display.
 */
function formatDuration(durationMs?: number): string {
  if (!durationMs) return '';
  
  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }
  
  const seconds = (durationMs / 1000).toFixed(2);
  return `${seconds}s`;
}

// ============================================================================
// Component
// ============================================================================

export const ProcessLine: React.FC<ProcessLineProps> = ({
  line,
  index,
  testId = 'process-line',
}) => {
  const [showDetails, setShowDetails] = useState(false);
  
  // Check if there are expandable details
  const hasDetails = !!(
    line.details ||
    line.prompt ||
    line.provenance ||
    (line.metadata && Object.keys(line.metadata).length > 0)
  );
  
  const statusClass = getStatusClass(line.status);
  const statusIcon = getStatusIcon(line.status);
  const duration = formatDuration(line.duration_ms);
  
  return (
    <div
      className={`process-line ${statusClass}`}
      data-testid={testId}
      data-index={index}
      data-status={line.status}
    >
      {/* Main line */}
      <div className="process-line-main">
        <span className="process-line-index">{index + 1}.</span>
        <span className="process-line-status-icon">{statusIcon}</span>
        <span className="process-line-step">{line.step}</span>
        {duration && (
          <span className="process-line-duration">{duration}</span>
        )}
        
        {hasDetails && (
          <button
            className="process-line-details-toggle"
            onClick={() => setShowDetails(!showDetails)}
            aria-label={showDetails ? 'Hide details' : 'Show details'}
            aria-expanded={showDetails}
            data-testid={`${testId}-details-toggle`}
          >
            {showDetails ? '−' : '+'}
          </button>
        )}
      </div>
      
      {/* Expandable details */}
      {showDetails && hasDetails && (
        <div 
          className="process-line-details"
          data-testid={`${testId}-details`}
        >
          {line.details && (
            <div className="process-line-detail-section">
              <span className="process-line-detail-label">Details:</span>
              <span className="process-line-detail-value">{line.details}</span>
            </div>
          )}
          
          {line.prompt && (
            <div className="process-line-detail-section">
              <span className="process-line-detail-label">Prompt:</span>
              <pre className="process-line-detail-code">{line.prompt}</pre>
            </div>
          )}
          
          {line.provenance && (
            <div className="process-line-detail-section">
              <span className="process-line-detail-label">Provenance:</span>
              <span className="process-line-detail-value">{line.provenance}</span>
            </div>
          )}
          
          {line.metadata && Object.keys(line.metadata).length > 0 && (
            <div className="process-line-detail-section">
              <span className="process-line-detail-label">Metadata:</span>
              <pre className="process-line-detail-code">
                {JSON.stringify(line.metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ProcessLine;
