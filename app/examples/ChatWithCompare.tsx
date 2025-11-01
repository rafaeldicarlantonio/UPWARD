/**
 * Example: Chat Interface with CompareCard
 * 
 * Demonstrates how to integrate CompareCard into a chat application
 * with proper role resolution and feature flag handling.
 */

import React, { useState } from 'react';
import CompareCard, { CompareSummary, EvidenceItem } from '../components/CompareCard';
import { loadSession } from '../state/session';

// ============================================================================
// Mock Data
// ============================================================================

const mockInternalEvidence: EvidenceItem[] = [
  {
    text: 'According to our internal database, New York City had a population of 8,336,817 as of the 2020 Census.',
    confidence: 0.92,
    source: 'Census 2020 Official',
  },
  {
    text: 'Historical records from our knowledge base indicate the 2020 census was comprehensive.',
    confidence: 0.85,
    source: 'Knowledge Base',
  },
];

const mockExternalEvidence: EvidenceItem[] = [
  {
    text: 'Wikipedia reports that New York City had an estimated population of 8,804,190 in 2020, making it the most populous city in the United States. The city comprises five boroughs, and its metropolitan area is one of the largest in the world.',
    url: 'https://en.wikipedia.org/wiki/New_York_City',
    host: 'en.wikipedia.org',
    label: 'Wikipedia',
    fetched_at: '2023-10-30T12:00:00Z',
  },
  {
    text: 'Recent census data updates suggest adjustments to the population figures based on revised counting methodologies.',
    url: 'https://www.census.gov/quickfacts/newyorkcitynewyork',
    host: 'census.gov',
    label: 'Census.gov',
    fetched_at: '2023-10-30T12:05:00Z',
  },
];

const mockCompareSummaryInternalOnly: CompareSummary = {
  stance_a: 'The population is 8,336,817 (2020 Census official count)',
  stance_b: 'The population is approximately 8.8 million (various estimates)',
  recommendation: 'a',
  confidence: 0.78,
  internal_evidence: mockInternalEvidence,
  external_evidence: [],
  metadata: {
    sources_used: { internal: 2, external: 0 },
    used_external: false,
  },
};

const mockCompareSummaryWithExternal: CompareSummary = {
  stance_a: 'The population is 8,336,817 (2020 Census official count)',
  stance_b: 'The population is approximately 8.8 million (various estimates)',
  recommendation: 'both',
  confidence: 0.82,
  internal_evidence: mockInternalEvidence,
  external_evidence: mockExternalEvidence,
  metadata: {
    sources_used: { internal: 2, external: 2 },
    used_external: true,
    tie_break: 'prefer_internal',
  },
};

// ============================================================================
// Example Component
// ============================================================================

export const ChatWithCompare: React.FC = () => {
  const [compareSummary, setCompareSummary] = useState<CompareSummary>(
    mockCompareSummaryInternalOnly
  );
  const [hasRunExternal, setHasRunExternal] = useState(false);
  
  const session = loadSession();
  
  const handleCompareComplete = (updatedSummary: CompareSummary) => {
    console.log('Full compare completed:', updatedSummary);
    setCompareSummary(updatedSummary);
    setHasRunExternal(true);
  };
  
  return (
    <div className="chat-with-compare">
      {/* Header */}
      <div className="example-header">
        <h2>Compare Card Example</h2>
        <div className="user-info">
          <span className="user-role">
            Role: {session.metadata.primaryRole}
          </span>
          <span className="flag-status">
            External Compare: {session.uiFlags.external_compare ? 'ON' : 'OFF'}
          </span>
        </div>
      </div>
      
      {/* Question */}
      <div className="example-question">
        <h3>Question:</h3>
        <p>"What is the population of New York City?"</p>
      </div>
      
      {/* Answer */}
      <div className="example-answer">
        <h3>Answer:</h3>
        <p>
          According to the 2020 US Census, New York City's official population is 8,336,817.
          However, various estimates and projections suggest it may be higher, around 8.8 million.
        </p>
      </div>
      
      {/* CompareCard */}
      <div className="example-compare">
        <h3>Comparison:</h3>
        
        <CompareCard
          compareSummary={compareSummary}
          userRole={session.metadata.primaryRole}
          allowExternalCompare={session.uiFlags.external_compare}
          messageId="msg_demo_123"
          onCompareComplete={handleCompareComplete}
        />
      </div>
      
      {/* Status */}
      <div className="example-status">
        <h3>Status:</h3>
        <ul>
          <li>
            Internal evidence: {compareSummary.internal_evidence.length} sources
          </li>
          <li>
            External evidence: {compareSummary.external_evidence?.length || 0} sources
          </li>
          <li>
            Used external: {compareSummary.metadata?.used_external ? 'Yes' : 'No'}
          </li>
          {hasRunExternal && (
            <li style={{ color: '#28a745', fontWeight: 600 }}>
              ✓ Full compare completed with external sources
            </li>
          )}
        </ul>
      </div>
      
      {/* Instructions */}
      <div className="example-instructions">
        <h3>Try it:</h3>
        <ul>
          <li>View the comparison between two stances</li>
          <li>See internal evidence (always shown)</li>
          {session.uiFlags.external_compare && (
            <>
              <li>Click "Run full compare" to fetch external sources</li>
              <li>Observe external evidence truncation (Wikipedia: 480 chars)</li>
              <li>Click "View source" links to visit external URLs</li>
            </>
          )}
          {!session.uiFlags.external_compare && (
            <li style={{ color: '#dc3545' }}>
              External compare is disabled (flag off)
            </li>
          )}
          {session.metadata.primaryRole === 'general' && (
            <li style={{ color: '#ffc107' }}>
              General users cannot run external compare (upgrade to Pro)
            </li>
          )}
        </ul>
      </div>
      
      {/* Demo: Simulate full compare for visualization */}
      {!hasRunExternal && session.uiFlags.external_compare && (
        <div className="example-demo-section">
          <h3>Demo Mode:</h3>
          <button
            onClick={() => {
              setCompareSummary(mockCompareSummaryWithExternal);
              setHasRunExternal(true);
            }}
            className="demo-button"
          >
            Simulate Full Compare (Skip API)
          </button>
          <p style={{ fontSize: '13px', color: '#6c757d' }}>
            This simulates the result without actually calling the API.
          </p>
        </div>
      )}
    </div>
  );
};

export default ChatWithCompare;
