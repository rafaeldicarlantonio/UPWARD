/**
 * ChatAnswer View Component
 * 
 * Unified view integrating ContradictionBadge, CompareCard, and ProcessLedger
 * with stable layout and skeleton loaders.
 * 
 * Features:
 * - ContradictionBadge in header
 * - CompareCard below answer (when compare_summary exists)
 * - ProcessLedger at bottom (when ui.flags.show_ledger)
 * - Skeleton loaders prevent layout shifts
 * - Conditional rendering based on data
 */

import React, { useState, useEffect } from 'react';
import ContradictionBadge, { Contradiction } from '../components/ContradictionBadge';
import CompareCard, { CompareSummary } from '../components/CompareCard';
import ProcessLedger, { ProcessTraceLine } from '../components/ProcessLedger';
import { Role } from '../lib/roles';
import '../styles/chat-answer.css';

// ============================================================================
// Skeleton Components
// ============================================================================

/**
 * Skeleton loader for CompareCard while fetching or loading.
 */
export const CompareCardSkeleton: React.FC<{ testId?: string }> = ({ testId = 'compare-skeleton' }) => (
  <div className="compare-card-skeleton skeleton" data-testid={testId}>
    <div className="skeleton-header">
      <div className="skeleton-bar skeleton-title"></div>
      <div className="skeleton-bar skeleton-button"></div>
    </div>
    <div className="skeleton-stances">
      <div className="skeleton-stance">
        <div className="skeleton-bar skeleton-label"></div>
        <div className="skeleton-bar skeleton-content"></div>
      </div>
      <div className="skeleton-divider"></div>
      <div className="skeleton-stance">
        <div className="skeleton-bar skeleton-label"></div>
        <div className="skeleton-bar skeleton-content"></div>
      </div>
    </div>
    <div className="skeleton-evidence">
      <div className="skeleton-bar skeleton-section"></div>
      <div className="skeleton-bar skeleton-item"></div>
      <div className="skeleton-bar skeleton-item"></div>
    </div>
  </div>
);

/**
 * Skeleton loader for ProcessLedger while fetching trace.
 */
export const ProcessLedgerSkeleton: React.FC<{ testId?: string }> = ({ testId = 'ledger-skeleton' }) => (
  <div className="process-ledger-skeleton skeleton" data-testid={testId}>
    <div className="skeleton-header">
      <div className="skeleton-bar skeleton-title"></div>
      <div className="skeleton-bar skeleton-expand"></div>
    </div>
    <div className="skeleton-lines">
      <div className="skeleton-bar skeleton-line"></div>
      <div className="skeleton-bar skeleton-line"></div>
      <div className="skeleton-bar skeleton-line"></div>
      <div className="skeleton-bar skeleton-line"></div>
    </div>
  </div>
);

// ============================================================================
// Types
// ============================================================================

export interface ChatAnswerData {
  /** Unique message ID */
  message_id: string;
  
  /** Answer content (HTML) */
  content: string;
  
  /** Process trace summary (compact) */
  process_trace_summary?: ProcessTraceLine[];
  
  /** Contradictions found */
  contradictions?: Contradiction[];
  
  /** Comparison summary (if available) */
  compare_summary?: CompareSummary;
  
  /** Whether compare is still loading */
  compare_loading?: boolean;
  
  /** Whether trace is still loading */
  trace_loading?: boolean;
}

export interface ChatAnswerProps {
  /** Answer data */
  answer: ChatAnswerData;
  
  /** Current user role */
  userRole: Role;
  
  /** UI flags */
  uiFlags: {
    show_ledger?: boolean;
    show_badges?: boolean;
    show_compare?: boolean;
    external_compare?: boolean;
  };
  
  /** Callback when compare completes */
  onCompareComplete?: (result: CompareSummary) => void;
  
  /** Callback when evidence anchor is clicked */
  onEvidenceClick?: (anchorId: string) => void;
  
  /** Custom class name */
  className?: string;
  
  /** Test ID */
  testId?: string;
}

// ============================================================================
// Component
// ============================================================================

export const ChatAnswer: React.FC<ChatAnswerProps> = ({
  answer,
  userRole,
  uiFlags,
  onCompareComplete,
  onEvidenceClick,
  className = '',
  testId = 'chat-answer',
}) => {
  const {
    message_id,
    content,
    process_trace_summary = [],
    contradictions = [],
    compare_summary,
    compare_loading = false,
    trace_loading = false,
  } = answer;
  
  const {
    show_ledger = false,
    show_badges = false,
    show_compare = false,
    external_compare = false,
  } = uiFlags;
  
  // Track whether compare has been loaded or is loading
  const [hasCompareData, setHasCompareData] = useState(!!compare_summary);
  const [showCompareSkeleton, setShowCompareSkeleton] = useState(compare_loading);
  
  // Update skeleton visibility when loading state changes
  useEffect(() => {
    if (compare_summary) {
      setHasCompareData(true);
      setShowCompareSkeleton(false);
    } else if (compare_loading) {
      setShowCompareSkeleton(true);
    }
  }, [compare_summary, compare_loading]);
  
  // Determine visibility
  const hasContradictions = contradictions.length > 0;
  const showContradictionBadge = hasContradictions || show_badges;
  const showCompareSection = show_compare && (hasCompareData || showCompareSkeleton);
  const showProcessLedger = show_ledger && process_trace_summary.length > 0;
  
  return (
    <div 
      className={`chat-answer ${className}`}
      data-testid={testId}
      data-has-contradictions={hasContradictions}
      data-has-compare={hasCompareData}
      data-has-ledger={showProcessLedger}
    >
      {/* Answer Header with ContradictionBadge */}
      <div className="chat-answer-header">
        <h3 className="answer-title">Answer</h3>
        
        {showContradictionBadge && (
          <ContradictionBadge
            contradictions={contradictions}
            alwaysShow={show_badges}
            onEvidenceClick={onEvidenceClick}
            testId={`${testId}-contradiction-badge`}
          />
        )}
      </div>
      
      {/* Answer Content */}
      <div 
        className="chat-answer-content"
        dangerouslySetInnerHTML={{ __html: content }}
        data-testid={`${testId}-content`}
      />
      
      {/* Compare Section with Stable Layout */}
      {showCompareSection && (
        <div className="chat-answer-compare-section" data-testid={`${testId}-compare-section`}>
          {showCompareSkeleton && !compare_summary ? (
            <CompareCardSkeleton testId={`${testId}-compare-skeleton`} />
          ) : compare_summary ? (
            <CompareCard
              compareSummary={compare_summary}
              userRole={userRole}
              allowExternalCompare={external_compare}
              messageId={message_id}
              onCompareComplete={(result) => {
                setHasCompareData(true);
                onCompareComplete?.(result);
              }}
              testId={`${testId}-compare-card`}
            />
          ) : null}
        </div>
      )}
      
      {/* Process Ledger Section */}
      {showProcessLedger && (
        <div className="chat-answer-ledger-section" data-testid={`${testId}-ledger-section`}>
          {trace_loading ? (
            <ProcessLedgerSkeleton testId={`${testId}-ledger-skeleton`} />
          ) : (
            <ProcessLedger
              traceSummary={process_trace_summary}
              messageId={message_id}
              userRole={userRole}
              showLedger={show_ledger}
              testId={`${testId}-process-ledger`}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default ChatAnswer;
