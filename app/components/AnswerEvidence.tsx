/**
 * AnswerEvidence Component
 * 
 * Displays answer content with evidence anchors and inline contradiction markers.
 * 
 * Features:
 * - Evidence anchors for scrolling/linking
 * - Mini-contradiction markers inline with evidence
 * - Smooth scroll to evidence
 * - Highlight animation on anchor target
 * - Tooltip on contradiction markers
 * - Accessible markup
 */

import React, { useCallback, useEffect } from 'react';
import { Contradiction } from './ContradictionBadge';
import '../styles/answer-evidence.css';

// ============================================================================
// Types
// ============================================================================

export interface AnswerEvidenceProps {
  /** Answer content (HTML string) */
  content: string;
  
  /** Array of contradictions with evidence anchors */
  contradictions: Contradiction[];
  
  /** Callback when evidence anchor is clicked */
  onEvidenceClick?: (anchorId: string) => void;
  
  /** Custom class name */
  className?: string;
  
  /** Test ID */
  testId?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Create a map of evidence anchors to contradictions.
 */
function createEvidenceContradictionMap(contradictions: Contradiction[]): Map<string, Contradiction[]> {
  const map = new Map<string, Contradiction[]>();
  
  contradictions.forEach(contradiction => {
    if (contradiction.evidenceAnchor) {
      const existing = map.get(contradiction.evidenceAnchor) || [];
      map.set(contradiction.evidenceAnchor, [...existing, contradiction]);
    }
  });
  
  return map;
}

/**
 * Get severity color for contradiction marker.
 */
function getSeverityColor(severity?: string): string {
  switch (severity) {
    case 'high':
      return '#dc3545';
    case 'medium':
      return '#ffc107';
    case 'low':
      return '#17a2b8';
    default:
      return '#6c757d';
  }
}

/**
 * Get severity icon for contradiction marker.
 */
function getSeverityIcon(severity?: string): string {
  switch (severity) {
    case 'high':
      return '⚠️';
    case 'medium':
      return '⚡';
    case 'low':
      return 'ℹ️';
    default:
      return '•';
  }
}

/**
 * Smooth scroll to evidence anchor.
 */
function scrollToEvidence(anchorId: string) {
  const element = document.getElementById(anchorId);
  if (element) {
    element.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    });
    
    // Add highlight animation
    element.classList.add('evidence-highlight-active');
    setTimeout(() => {
      element.classList.remove('evidence-highlight-active');
    }, 2000);
  }
}

// ============================================================================
// Component
// ============================================================================

export const AnswerEvidence: React.FC<AnswerEvidenceProps> = ({
  content,
  contradictions,
  onEvidenceClick,
  className = '',
  testId = 'answer-evidence',
}) => {
  const contradictionMap = createEvidenceContradictionMap(contradictions);
  
  // Handle evidence anchor clicks
  useEffect(() => {
    const handleAnchorClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      
      // Check if clicked on or inside an evidence anchor
      const evidenceAnchor = target.closest('[data-evidence-anchor]');
      if (evidenceAnchor) {
        const anchorId = evidenceAnchor.getAttribute('data-evidence-anchor');
        if (anchorId) {
          e.preventDefault();
          scrollToEvidence(anchorId);
          onEvidenceClick?.(anchorId);
        }
      }
    };
    
    document.addEventListener('click', handleAnchorClick);
    return () => document.removeEventListener('click', handleAnchorClick);
  }, [onEvidenceClick]);
  
  // Handle hash navigation on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const anchorId = window.location.hash.substring(1);
      setTimeout(() => {
        scrollToEvidence(anchorId);
      }, 100);
    }
  }, []);
  
  // Process content to add contradiction markers
  const processContent = useCallback(() => {
    // Create a temporary div to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = content;
    
    // Find all elements with IDs (evidence anchors)
    const evidenceElements = tempDiv.querySelectorAll('[id]');
    
    evidenceElements.forEach(element => {
      const anchorId = element.getAttribute('id');
      if (!anchorId) return;
      
      // Add data attribute for click handling
      element.setAttribute('data-evidence-anchor', anchorId);
      
      // Add evidence anchor class
      element.classList.add('evidence-anchor');
      
      // Check if this evidence has contradictions
      const contradictionsForAnchor = contradictionMap.get(anchorId);
      if (contradictionsForAnchor && contradictionsForAnchor.length > 0) {
        // Add contradiction marker after the element
        const marker = document.createElement('span');
        marker.className = 'contradiction-marker';
        marker.setAttribute('data-testid', `contradiction-marker-${anchorId}`);
        marker.setAttribute('role', 'button');
        marker.setAttribute('tabindex', '0');
        marker.setAttribute('aria-label', `${contradictionsForAnchor.length} contradiction(s)`);
        
        // Get highest severity
        const highestSeverity = contradictionsForAnchor.reduce((highest, c) => {
          if (c.severity === 'high') return 'high';
          if (c.severity === 'medium' && highest !== 'high') return 'medium';
          if (c.severity === 'low' && highest !== 'high' && highest !== 'medium') return 'low';
          return highest;
        }, contradictionsForAnchor[0].severity);
        
        marker.style.setProperty('--marker-color', getSeverityColor(highestSeverity));
        
        // Create marker content
        const icon = document.createElement('span');
        icon.className = 'marker-icon';
        icon.textContent = getSeverityIcon(highestSeverity);
        
        const count = document.createElement('span');
        count.className = 'marker-count';
        count.textContent = String(contradictionsForAnchor.length);
        
        marker.appendChild(icon);
        marker.appendChild(count);
        
        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'contradiction-tooltip';
        tooltip.setAttribute('role', 'tooltip');
        
        const tooltipTitle = document.createElement('div');
        tooltipTitle.className = 'tooltip-title';
        tooltipTitle.textContent = `${contradictionsForAnchor.length} Contradiction${contradictionsForAnchor.length > 1 ? 's' : ''}`;
        tooltip.appendChild(tooltipTitle);
        
        const tooltipList = document.createElement('ul');
        tooltipList.className = 'tooltip-list';
        
        contradictionsForAnchor.forEach(contradiction => {
          const item = document.createElement('li');
          item.className = `tooltip-item severity-${contradiction.severity || 'unknown'}`;
          
          const subject = document.createElement('strong');
          subject.textContent = contradiction.subject;
          item.appendChild(subject);
          
          if (contradiction.description) {
            const desc = document.createElement('p');
            desc.textContent = contradiction.description;
            item.appendChild(desc);
          }
          
          tooltipList.appendChild(item);
        });
        
        tooltip.appendChild(tooltipList);
        marker.appendChild(tooltip);
        
        // Insert marker after the element
        element.insertAdjacentElement('afterend', marker);
      }
    });
    
    return tempDiv.innerHTML;
  }, [content, contradictionMap]);
  
  const processedContent = processContent();
  
  return (
    <div 
      className={`answer-evidence ${className}`}
      data-testid={testId}
      data-has-contradictions={contradictions.length > 0}
    >
      <div 
        className="answer-evidence-content"
        dangerouslySetInnerHTML={{ __html: processedContent }}
      />
    </div>
  );
};

export default AnswerEvidence;
