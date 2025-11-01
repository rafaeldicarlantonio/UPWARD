/**
 * CompareCard Component
 * 
 * Displays comparison between two stances with evidence from internal and external sources.
 * 
 * Features:
 * - Shows stance_a vs stance_b
 * - Groups evidence as Internal and External
 * - Truncates external snippets per policy
 * - Shows provenance label + host for external sources
 * - "Run full compare" button with role gating
 * - Disabled for General users and when flags are off
 * - Loading states for async operations
 */

import React, { useState } from 'react';
import { Role, hasCapability, CAP_READ_LEDGER_FULL } from '../lib/roles';
import '../styles/compare.css';

// ============================================================================
// Types
// ============================================================================

export interface EvidenceItem {
  /** Evidence text/snippet */
  text: string;
  
  /** Confidence score (0-1) */
  confidence?: number;
  
  /** Source information */
  source?: string;
  
  /** For external: Full URL */
  url?: string;
  
  /** For external: Domain/host */
  host?: string;
  
  /** For external: Source label (Wikipedia, arXiv, etc) */
  label?: string;
  
  /** Timestamp when fetched */
  fetched_at?: string;
}

export interface CompareSummary {
  /** First stance/position */
  stance_a: string;
  
  /** Second stance/position */
  stance_b: string;
  
  /** Recommended stance */
  recommendation?: 'a' | 'b' | 'neither' | 'both';
  
  /** Confidence in recommendation (0-1) */
  confidence?: number;
  
  /** Internal evidence supporting comparison */
  internal_evidence: EvidenceItem[];
  
  /** External evidence (if used) */
  external_evidence?: EvidenceItem[];
  
  /** Metadata about the comparison */
  metadata?: {
    sources_used?: { internal: number; external: number };
    used_external?: boolean;
    tie_break?: string;
  };
}

export interface CompareCardProps {
  /** Comparison summary data */
  compareSummary: CompareSummary;
  
  /** Current user role */
  userRole: Role;
  
  /** Whether external compare is enabled (from feature flags) */
  allowExternalCompare?: boolean;
  
  /** Message ID for running full compare */
  messageId?: string;
  
  /** API base URL */
  apiBaseUrl?: string;
  
  /** Callback when full compare completes */
  onCompareComplete?: (result: CompareSummary) => void;
  
  /** Custom class name */
  className?: string;
  
  /** Test ID for testing */
  testId?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if user can run external compare.
 */
function canRunExternalCompare(userRole: Role, allowExternalCompare: boolean): boolean {
  if (!allowExternalCompare) {
    return false;
  }
  
  // Must have CAP_READ_LEDGER_FULL (Pro, Scholars, Analytics)
  return hasCapability(userRole, CAP_READ_LEDGER_FULL);
}

/**
 * Truncate text to max length with ellipsis.
 */
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  
  return text.substring(0, maxLength - 3) + '...';
}

/**
 * Extract host from URL.
 */
function extractHost(url: string): string {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace('www.', '');
  } catch {
    return url;
  }
}

/**
 * Get max snippet chars for a source.
 * Defaults to 480 if not specified.
 */
function getMaxSnippetChars(label?: string): number {
  const defaults: Record<string, number> = {
    'Wikipedia': 480,
    'arXiv': 640,
    'PubMed': 500,
    'Google Scholar': 400,
    'Semantic Scholar': 450,
  };
  
  return label ? (defaults[label] || 480) : 480;
}

/**
 * Get recommendation icon and color.
 */
function getRecommendationStyle(recommendation?: string): { icon: string; color: string } {
  switch (recommendation) {
    case 'a':
      return { icon: '←', color: '#0066cc' };
    case 'b':
      return { icon: '→', color: '#0066cc' };
    case 'both':
      return { icon: '↔', color: '#28a745' };
    case 'neither':
      return { icon: '⊘', color: '#6c757d' };
    default:
      return { icon: '?', color: '#6c757d' };
  }
}

// ============================================================================
// Component
// ============================================================================

export const CompareCard: React.FC<CompareCardProps> = ({
  compareSummary,
  userRole,
  allowExternalCompare = false,
  messageId,
  apiBaseUrl = '/api',
  onCompareComplete,
  className = '',
  testId = 'compare-card',
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const canRunExternal = canRunExternalCompare(userRole, allowExternalCompare);
  const hasExternalEvidence = (compareSummary.external_evidence?.length || 0) > 0;
  const usedExternal = compareSummary.metadata?.used_external || false;
  
  // Recommendation style
  const recStyle = getRecommendationStyle(compareSummary.recommendation);
  
  // Handle "Run full compare" button click
  const handleRunFullCompare = async () => {
    if (!messageId || !canRunExternal || isLoading) {
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${apiBaseUrl}/factate/compare`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message_id: messageId,
          allow_external: true,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Compare failed: ${response.status} ${response.statusText}`);
      }
      
      const result = await response.json();
      
      // Map API response to CompareSummary
      const newSummary: CompareSummary = {
        stance_a: result.compare_summary.stance_a || compareSummary.stance_a,
        stance_b: result.compare_summary.stance_b || compareSummary.stance_b,
        recommendation: result.compare_summary.recommendation,
        confidence: result.compare_summary.confidence,
        internal_evidence: result.compare_summary.internal_evidence || [],
        external_evidence: result.compare_summary.external_evidence || [],
        metadata: {
          sources_used: result.sources,
          used_external: result.used_external,
          tie_break: result.compare_summary.tie_break,
        },
      };
      
      onCompareComplete?.(newSummary);
    } catch (err) {
      console.error('Failed to run full compare:', err);
      setError(err instanceof Error ? err.message : 'Failed to run comparison');
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div 
      className={`compare-card ${className}`}
      data-testid={testId}
      data-used-external={usedExternal}
    >
      {/* Header */}
      <div className="compare-card-header">
        <div className="compare-card-title">
          <span className="compare-card-icon">⚖️</span>
          <span className="compare-card-label">Comparison</span>
          {usedExternal && (
            <span className="compare-card-external-badge">
              External sources used
            </span>
          )}
        </div>
        
        {/* Run Full Compare Button */}
        {messageId && (
          <button
            className="compare-card-run-button"
            onClick={handleRunFullCompare}
            disabled={!canRunExternal || isLoading}
            data-testid={`${testId}-run-button`}
            title={
              !allowExternalCompare
                ? 'External compare is disabled'
                : !canRunExternal
                ? 'Pro or higher required for external compare'
                : 'Run full comparison with external sources'
            }
          >
            {isLoading ? (
              <>
                <span className="button-spinner">⏳</span>
                <span>Running...</span>
              </>
            ) : (
              <>
                <span className="button-icon">🔄</span>
                <span>Run full compare</span>
              </>
            )}
          </button>
        )}
      </div>
      
      {/* Error Display */}
      {error && (
        <div className="compare-card-error" data-testid={`${testId}-error`}>
          <span className="error-icon">⚠️</span>
          <span className="error-message">{error}</span>
        </div>
      )}
      
      {/* Stances */}
      <div className="compare-stances">
        <div className="stance stance-a">
          <div className="stance-label">Position A</div>
          <div className="stance-content">{compareSummary.stance_a}</div>
        </div>
        
        <div className="stance-divider">
          <div 
            className="recommendation-indicator"
            style={{ color: recStyle.color }}
            title={`Recommendation: ${compareSummary.recommendation || 'none'}`}
          >
            {recStyle.icon}
          </div>
          {compareSummary.confidence !== undefined && (
            <div className="confidence-score">
              {Math.round(compareSummary.confidence * 100)}%
            </div>
          )}
        </div>
        
        <div className="stance stance-b">
          <div className="stance-label">Position B</div>
          <div className="stance-content">{compareSummary.stance_b}</div>
        </div>
      </div>
      
      {/* Evidence Sections */}
      <div className="evidence-sections">
        {/* Internal Evidence */}
        {compareSummary.internal_evidence.length > 0 && (
          <div className="evidence-section">
            <div className="evidence-section-header">
              <span className="evidence-section-icon">📚</span>
              <span className="evidence-section-title">Internal Evidence</span>
              <span className="evidence-section-count">
                ({compareSummary.internal_evidence.length})
              </span>
            </div>
            
            <ul className="evidence-list" data-testid={`${testId}-internal-evidence`}>
              {compareSummary.internal_evidence.map((item, index) => (
                <li key={index} className="evidence-item internal">
                  <div className="evidence-text">{item.text}</div>
                  {item.confidence !== undefined && (
                    <div className="evidence-confidence">
                      Confidence: {Math.round(item.confidence * 100)}%
                    </div>
                  )}
                  {item.source && (
                    <div className="evidence-source">
                      Source: {item.source}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* External Evidence */}
        {hasExternalEvidence && (
          <div className="evidence-section">
            <div className="evidence-section-header">
              <span className="evidence-section-icon">🌐</span>
              <span className="evidence-section-title">External Evidence</span>
              <span className="evidence-section-count">
                ({compareSummary.external_evidence!.length})
              </span>
            </div>
            
            <ul className="evidence-list" data-testid={`${testId}-external-evidence`}>
              {compareSummary.external_evidence!.map((item, index) => {
                const maxChars = getMaxSnippetChars(item.label);
                const truncatedText = truncateText(item.text, maxChars);
                const host = item.host || (item.url ? extractHost(item.url) : '');
                
                return (
                  <li key={index} className="evidence-item external">
                    <div className="evidence-header">
                      {item.label && (
                        <span className="evidence-label">[{item.label}]</span>
                      )}
                      {host && (
                        <span className="evidence-host">{host}</span>
                      )}
                    </div>
                    <div 
                      className="evidence-text"
                      data-truncated={truncatedText.endsWith('...')}
                    >
                      {truncatedText}
                    </div>
                    {item.url && (
                      <div className="evidence-provenance">
                        <a 
                          href={item.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="evidence-url"
                        >
                          View source
                        </a>
                        {item.fetched_at && (
                          <span className="evidence-fetched">
                            Fetched: {new Date(item.fetched_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        
        {/* No Evidence Message */}
        {compareSummary.internal_evidence.length === 0 && !hasExternalEvidence && (
          <div className="no-evidence-message">
            No evidence available for this comparison
          </div>
        )}
      </div>
      
      {/* Footer with metadata */}
      {compareSummary.metadata?.sources_used && (
        <div className="compare-card-footer">
          <span className="footer-label">Sources:</span>
          <span className="footer-value">
            {compareSummary.metadata.sources_used.internal} internal
            {compareSummary.metadata.sources_used.external > 0 && 
              `, ${compareSummary.metadata.sources_used.external} external`
            }
          </span>
          {compareSummary.metadata.tie_break && (
            <>
              <span className="footer-separator">•</span>
              <span className="footer-label">Tie-break:</span>
              <span className="footer-value">{compareSummary.metadata.tie_break}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default CompareCard;
