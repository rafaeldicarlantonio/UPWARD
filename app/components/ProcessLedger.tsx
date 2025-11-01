/**
 * ProcessLedger Component
 * 
 * Displays process trace summary with role-aware redaction and lazy loading.
 * 
 * Features:
 * - Compact view shows process_trace_summary (4 lines max)
 * - Expandable to full trace (fetched from /debug/redo_trace)
 * - Role-based redaction:
 *   - General: 4 lines max, no raw prompts/provenance
 *   - Pro/Scholars/Analytics: Full summary + expandable
 * - Respects ui.flags.show_ledger
 * - Graceful error handling
 */

import React, { useState, useCallback, useMemo } from 'react';
import ProcessLine from './ProcessLine';
import { Role, hasCapability, CAP_READ_LEDGER_FULL } from '../lib/roles';
import '../styles/ledger.css';

// ============================================================================
// Types
// ============================================================================

export interface ProcessTraceLine {
  step: string;
  duration_ms?: number;
  status?: 'success' | 'error' | 'skipped';
  details?: string;
  prompt?: string;
  provenance?: string;
  metadata?: Record<string, any>;
}

export interface ProcessLedgerProps {
  /** Process trace summary (compact, 4 lines) */
  traceSummary: ProcessTraceLine[];
  
  /** Message ID for fetching full trace */
  messageId?: string;
  
  /** Current user role */
  userRole: Role;
  
  /** Whether to show ledger (from feature flags) */
  showLedger?: boolean;
  
  /** Initial expanded state */
  defaultExpanded?: boolean;
  
  /** API base URL */
  apiBaseUrl?: string;
  
  /** Custom class name */
  className?: string;
  
  /** Callback when expand/collapse */
  onExpandChange?: (expanded: boolean) => void;
  
  /** Test ID for testing */
  testId?: string;
}

interface FullTraceResponse {
  trace: ProcessTraceLine[];
  message_id: string;
  total_duration_ms: number;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Redact sensitive information from a trace line based on role.
 */
function redactLine(line: ProcessTraceLine, userRole: Role): ProcessTraceLine {
  const hasFullAccess = hasCapability(userRole, CAP_READ_LEDGER_FULL);
  
  if (hasFullAccess) {
    return line; // No redaction for Pro/Scholars/Analytics
  }
  
  // For General users: strip prompts and provenance
  const redacted = { ...line };
  delete redacted.prompt;
  delete redacted.provenance;
  
  // Sanitize metadata
  if (redacted.metadata) {
    const sanitized = { ...redacted.metadata };
    delete sanitized.internal_id;
    delete sanitized.db_refs;
    delete sanitized.raw_output;
    redacted.metadata = sanitized;
  }
  
  return redacted;
}

/**
 * Cap trace summary to 4 lines for General users.
 */
function capTraceLines(lines: ProcessTraceLine[], userRole: Role): ProcessTraceLine[] {
  const hasFullAccess = hasCapability(userRole, CAP_READ_LEDGER_FULL);
  
  if (hasFullAccess) {
    return lines;
  }
  
  // General users: max 4 lines
  return lines.slice(0, 4);
}

// ============================================================================
// Component
// ============================================================================

export const ProcessLedger: React.FC<ProcessLedgerProps> = ({
  traceSummary,
  messageId,
  userRole,
  showLedger = true,
  defaultExpanded = false,
  apiBaseUrl = '/api',
  className = '',
  onExpandChange,
  testId = 'process-ledger',
}) => {
  // State
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [fullTrace, setFullTrace] = useState<ProcessTraceLine[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Check if user has full ledger access
  const hasFullAccess = useMemo(
    () => hasCapability(userRole, CAP_READ_LEDGER_FULL),
    [userRole]
  );
  
  // Don't render if show_ledger flag is off
  if (!showLedger) {
    return null;
  }
  
  // Don't render if no trace summary
  if (!traceSummary || traceSummary.length === 0) {
    return null;
  }
  
  // Apply role-based redaction and capping
  const displayedSummary = useMemo(() => {
    const capped = capTraceLines(traceSummary, userRole);
    return capped.map(line => redactLine(line, userRole));
  }, [traceSummary, userRole]);
  
  // Determine if expand is available
  const canExpand = hasFullAccess && messageId;
  
  // Fetch full trace
  const fetchFullTrace = useCallback(async () => {
    if (!messageId) {
      setError('No message ID available');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const url = `${apiBaseUrl}/debug/redo_trace?message_id=${encodeURIComponent(messageId)}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch trace: ${response.status} ${response.statusText}`);
      }
      
      const data: FullTraceResponse = await response.json();
      
      // Apply redaction to full trace
      const redactedTrace = data.trace.map(line => redactLine(line, userRole));
      setFullTrace(redactedTrace);
    } catch (err) {
      console.error('Error fetching full trace:', err);
      setError(err instanceof Error ? err.message : 'Failed to load full trace');
      setFullTrace(null);
    } finally {
      setIsLoading(false);
    }
  }, [messageId, apiBaseUrl, userRole]);
  
  // Handle expand/collapse
  const handleToggleExpand = useCallback(async () => {
    const newExpanded = !isExpanded;
    setIsExpanded(newExpanded);
    
    // Fetch full trace if expanding and not already loaded
    if (newExpanded && !fullTrace && !isLoading) {
      await fetchFullTrace();
    }
    
    onExpandChange?.(newExpanded);
  }, [isExpanded, fullTrace, isLoading, fetchFullTrace, onExpandChange]);
  
  // Determine which lines to display
  const displayedLines = isExpanded && fullTrace ? fullTrace : displayedSummary;
  
  // Calculate total duration
  const totalDuration = useMemo(() => {
    return displayedLines.reduce((sum, line) => sum + (line.duration_ms || 0), 0);
  }, [displayedLines]);
  
  return (
    <div 
      className={`process-ledger ${className}`}
      data-testid={testId}
      data-expanded={isExpanded}
      data-role={userRole}
    >
      {/* Header */}
      <div className="process-ledger-header">
        <div className="process-ledger-title">
          <span className="process-ledger-icon">📋</span>
          <span className="process-ledger-label">Process Ledger</span>
          <span className="process-ledger-duration">
            {totalDuration > 0 && `(${totalDuration}ms)`}
          </span>
        </div>
        
        {canExpand && (
          <button
            className="process-ledger-expand-button"
            onClick={handleToggleExpand}
            disabled={isLoading}
            data-testid={`${testId}-expand-button`}
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
            aria-expanded={isExpanded}
          >
            {isLoading ? (
              <span className="process-ledger-spinner">⏳</span>
            ) : (
              <span className="process-ledger-arrow">
                {isExpanded ? '▼' : '▶'}
              </span>
            )}
            <span className="process-ledger-expand-label">
              {isLoading ? 'Loading...' : isExpanded ? 'Collapse' : 'Expand'}
            </span>
          </button>
        )}
      </div>
      
      {/* Lines */}
      <div 
        className="process-ledger-lines"
        data-testid={`${testId}-lines`}
      >
        {displayedLines.map((line, index) => (
          <ProcessLine
            key={`${line.step}-${index}`}
            line={line}
            index={index}
            testId={`${testId}-line-${index}`}
          />
        ))}
      </div>
      
      {/* Error Display */}
      {error && (
        <div 
          className="process-ledger-error"
          data-testid={`${testId}-error`}
          role="alert"
        >
          <span className="process-ledger-error-icon">⚠️</span>
          <span className="process-ledger-error-message">{error}</span>
          <button
            className="process-ledger-retry-button"
            onClick={fetchFullTrace}
            data-testid={`${testId}-retry-button`}
          >
            Retry
          </button>
        </div>
      )}
      
      {/* Footer - Show line count if capped */}
      {!hasFullAccess && traceSummary.length > 4 && (
        <div 
          className="process-ledger-footer"
          data-testid={`${testId}-footer`}
        >
          <span className="process-ledger-footer-text">
            Showing {displayedSummary.length} of {traceSummary.length} steps
          </span>
          <span className="process-ledger-footer-hint">
            (Upgrade to Pro for full trace)
          </span>
        </div>
      )}
      
      {/* Expanded Indicator */}
      {isExpanded && fullTrace && (
        <div 
          className="process-ledger-expanded-indicator"
          data-testid={`${testId}-expanded-indicator`}
        >
          <span>Showing full trace ({fullTrace.length} steps)</span>
        </div>
      )}
    </div>
  );
};

export default ProcessLedger;
