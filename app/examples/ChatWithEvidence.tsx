/**
 * Example: Chat Interface with AnswerEvidence
 * 
 * Demonstrates how to use AnswerEvidence component with contradiction markers
 * and evidence anchors in a chat application.
 */

import React, { useState } from 'react';
import AnswerEvidence from '../components/AnswerEvidence';
import ContradictionBadge, { Contradiction } from '../components/ContradictionBadge';

// ============================================================================
// Mock Data
// ============================================================================

const mockAnswerContent = `
  <h3>New York City Population</h3>
  
  <p>According to the <span id="evidence-1">2020 United States Census</span>, 
  New York City's official population is <span id="evidence-2">8,336,817 residents</span>, 
  making it the most populous city in the United States.</p>
  
  <p>However, various demographic studies and estimates suggest that the actual 
  population may be closer to <span id="evidence-3">8.8 million</span> when accounting 
  for <span id="evidence-4">undocumented residents and temporary workers</span>.</p>
  
  <p>The <span id="evidence-5">Census methodology</span> has been validated by independent 
  auditors and follows <span id="evidence-6">strict protocols</span> established by the 
  U.S. Census Bureau.</p>
  
  <h4>Key Facts</h4>
  <ul>
    <li>Official count: <span id="evidence-7">8,336,817</span></li>
    <li>Estimated range: <span id="evidence-8">8.3 - 8.8 million</span></li>
    <li>Data source: <span id="evidence-9">U.S. Census Bureau 2020</span></li>
  </ul>
`;

const mockContradictions: Contradiction[] = [
  {
    id: 'c1',
    subject: 'Population count discrepancy',
    description: 'Official census (8.3M) differs from demographic estimates (8.8M)',
    evidenceAnchor: 'evidence-2',
    severity: 'high',
    source: 'Census vs Demographic Studies',
  },
  {
    id: 'c2',
    subject: 'Estimation methodology conflict',
    description: 'Different counting methodologies produce different results',
    evidenceAnchor: 'evidence-3',
    severity: 'medium',
    source: 'Methodology comparison',
  },
  {
    id: 'c3',
    subject: 'Undocumented population variance',
    description: 'Uncertainty in counting undocumented residents leads to varying estimates',
    evidenceAnchor: 'evidence-4',
    severity: 'medium',
    source: 'Demographic analysis',
  },
  {
    id: 'c4',
    subject: 'Data validation question',
    description: 'Independent auditors found minor discrepancies in validation protocols',
    evidenceAnchor: 'evidence-6',
    severity: 'low',
    source: 'Audit reports',
  },
];

// ============================================================================
// Component
// ============================================================================

export const ChatWithEvidence: React.FC = () => {
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);
  
  const handleEvidenceClick = (anchorId: string) => {
    console.log('Evidence clicked:', anchorId);
    setSelectedEvidence(anchorId);
  };
  
  return (
    <div className="chat-with-evidence">
      {/* Header */}
      <div className="example-header">
        <h2>AnswerEvidence Example</h2>
        <ContradictionBadge
          contradictions={mockContradictions}
          onEvidenceClick={handleEvidenceClick}
        />
      </div>
      
      {/* Answer with Evidence */}
      <div className="example-answer">
        <AnswerEvidence
          content={mockAnswerContent}
          contradictions={mockContradictions}
          onEvidenceClick={handleEvidenceClick}
        />
      </div>
      
      {/* Status Panel */}
      <div className="example-status">
        <h3>Component Status:</h3>
        <ul>
          <li>Total contradictions: {mockContradictions.length}</li>
          <li>Evidence anchors: 9</li>
          <li>Anchors with conflicts: 4</li>
          <li>
            Selected evidence: 
            {selectedEvidence ? (
              <code style={{ marginLeft: '8px', padding: '2px 6px', background: '#f0f0f0' }}>
                {selectedEvidence}
              </code>
            ) : (
              ' None'
            )}
          </li>
        </ul>
      </div>
      
      {/* Instructions */}
      <div className="example-instructions">
        <h3>Try it:</h3>
        <ol>
          <li>Hover over yellow-highlighted evidence text to see anchors</li>
          <li>Click the ContradictionBadge to see all conflicts</li>
          <li>Click on evidence links in the badge to scroll to that evidence</li>
          <li>Notice the mini contradiction markers (⚠️, ⚡, ℹ️) next to conflicting evidence</li>
          <li>Hover over markers to see tooltip with contradiction details</li>
          <li>Evidence with conflicts is visually flagged with the marker</li>
        </ol>
      </div>
      
      {/* Legend */}
      <div className="example-legend">
        <h3>Marker Legend:</h3>
        <ul>
          <li><span style={{ color: '#dc3545' }}>⚠️ High Severity</span> - Critical contradiction</li>
          <li><span style={{ color: '#ffc107' }}>⚡ Medium Severity</span> - Notable discrepancy</li>
          <li><span style={{ color: '#17a2b8' }}>ℹ️ Low Severity</span> - Minor inconsistency</li>
        </ul>
      </div>
    </div>
  );
};

export default ChatWithEvidence;
