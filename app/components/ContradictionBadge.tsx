/**
 * ContradictionBadge Component
 * 
 * Displays a badge showing contradiction count with tooltip details.
 * 
 * Features:
 * - Shows "Contradictions: N" count
 * - Tooltip lists subjects with links to evidence anchors
 * - Color/icon changes when N > 0
 * - Hidden when N = 0 (unless ui.flags.show_badges forces always-on)
 * - Smooth scroll to evidence anchors
 */

import React, { useState, useRef, useEffect } from 'react';
import '../styles/badges.css';

// ============================================================================
// Types
// ============================================================================

export interface Contradiction {
  /** Unique identifier for this contradiction */
  id: string;
  
  /** Subject of the contradiction */
  subject: string;
  
  /** Brief description of the contradiction */
  description?: string;
  
  /** Anchor ID in the answer text (for scrolling) */
  evidenceAnchor?: string;
  
  /** Severity level */
  severity?: 'low' | 'medium' | 'high';
  
  /** Source of conflicting information */
  source?: string;
}

export interface ContradictionBadgeProps {
  /** Array of contradictions */
  contradictions: Contradiction[];
  
  /** Whether to always show badge (from ui.flags.show_badges) */
  alwaysShow?: boolean;
  
  /** Custom class name */
  className?: string;
  
  /** Callback when evidence anchor is clicked */
  onEvidenceClick?: (evidenceAnchor: string) => void;
  
  /** Test ID for testing */
  testId?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get badge color class based on contradiction count and severity.
 */
function getBadgeColorClass(count: number, contradictions: Contradiction[]): string {
  if (count === 0) {
    return 'badge-success';
  }
  
  // Check for high severity contradictions
  const hasHighSeverity = contradictions.some(c => c.severity === 'high');
  if (hasHighSeverity) {
    return 'badge-danger';
  }
  
  // Check for medium severity
  const hasMediumSeverity = contradictions.some(c => c.severity === 'medium');
  if (hasMediumSeverity) {
    return 'badge-warning';
  }
  
  // Default for low severity or unspecified
  return 'badge-info';
}

/**
 * Get icon based on count.
 */
function getBadgeIcon(count: number): string {
  return count === 0 ? '✓' : '⚠';
}

/**
 * Scroll to evidence anchor with smooth behavior.
 */
function scrollToEvidence(evidenceAnchor: string): void {
  const element = document.getElementById(evidenceAnchor);
  if (element) {
    element.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    });
    
    // Add highlight effect
    element.classList.add('evidence-highlight');
    setTimeout(() => {
      element.classList.remove('evidence-highlight');
    }, 2000);
  }
}

// ============================================================================
// Component
// ============================================================================

export const ContradictionBadge: React.FC<ContradictionBadgeProps> = ({
  contradictions = [],
  alwaysShow = false,
  className = '',
  onEvidenceClick,
  testId = 'contradiction-badge',
}) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const badgeRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  
  const count = contradictions.length;
  const colorClass = getBadgeColorClass(count, contradictions);
  const icon = getBadgeIcon(count);
  
  // Hide if count is 0 and not forced to show
  if (count === 0 && !alwaysShow) {
    return null;
  }
  
  // Handle click on evidence link
  const handleEvidenceClick = (e: React.MouseEvent, evidenceAnchor: string) => {
    e.preventDefault();
    e.stopPropagation();
    
    scrollToEvidence(evidenceAnchor);
    onEvidenceClick?.(evidenceAnchor);
    setShowTooltip(false);
  };
  
  // Handle click outside to close tooltip
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        showTooltip &&
        badgeRef.current &&
        tooltipRef.current &&
        !badgeRef.current.contains(event.target as Node) &&
        !tooltipRef.current.contains(event.target as Node)
      ) {
        setShowTooltip(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showTooltip]);
  
  // Handle escape key to close tooltip
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && showTooltip) {
        setShowTooltip(false);
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [showTooltip]);
  
  return (
    <div 
      className={`contradiction-badge-container ${className}`}
      data-testid={testId}
      ref={badgeRef}
    >
      <button
        className={`contradiction-badge ${colorClass}`}
        onClick={() => setShowTooltip(!showTooltip)}
        aria-label={`${count} contradiction${count !== 1 ? 's' : ''}`}
        aria-expanded={showTooltip}
        data-testid={`${testId}-button`}
        data-count={count}
      >
        <span className="badge-icon">{icon}</span>
        <span className="badge-label">
          Contradictions: <strong>{count}</strong>
        </span>
      </button>
      
      {showTooltip && (
        <div
          className="contradiction-tooltip"
          role="tooltip"
          ref={tooltipRef}
          data-testid={`${testId}-tooltip`}
        >
          <div className="tooltip-header">
            <span className="tooltip-title">
              {count} Contradiction{count !== 1 ? 's' : ''} Found
            </span>
            <button
              className="tooltip-close"
              onClick={() => setShowTooltip(false)}
              aria-label="Close tooltip"
              data-testid={`${testId}-tooltip-close`}
            >
              ×
            </button>
          </div>
          
          <div className="tooltip-content">
            {contradictions.length > 0 ? (
              <ul className="contradiction-list">
                {contradictions.map((contradiction, index) => (
                  <li
                    key={contradiction.id}
                    className={`contradiction-item severity-${contradiction.severity || 'low'}`}
                    data-testid={`${testId}-item-${index}`}
                  >
                    <div className="contradiction-subject">
                      {contradiction.evidenceAnchor ? (
                        <a
                          href={`#${contradiction.evidenceAnchor}`}
                          onClick={(e) => handleEvidenceClick(e, contradiction.evidenceAnchor!)}
                          className="evidence-link"
                          data-testid={`${testId}-link-${index}`}
                        >
                          {contradiction.subject}
                        </a>
                      ) : (
                        <span>{contradiction.subject}</span>
                      )}
                      {contradiction.severity && (
                        <span className={`severity-badge severity-${contradiction.severity}`}>
                          {contradiction.severity}
                        </span>
                      )}
                    </div>
                    
                    {contradiction.description && (
                      <div className="contradiction-description">
                        {contradiction.description}
                      </div>
                    )}
                    
                    {contradiction.source && (
                      <div className="contradiction-source">
                        Source: {contradiction.source}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="no-contradictions">
                <span className="success-icon">✓</span>
                <span>No contradictions detected</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ContradictionBadge;
