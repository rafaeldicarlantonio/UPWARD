/**
 * Example: Chat Interface with ContradictionBadge
 * 
 * Demonstrates how to integrate ContradictionBadge into a chat application
 * with evidence anchors and proper flag handling.
 */

import React, { useState } from 'react';
import ContradictionBadge, { Contradiction } from '../components/ContradictionBadge';
import { loadSession } from '../state/session';

// ============================================================================
// Types
// ============================================================================

interface ChatResponse {
  id: string;
  content: string;
  contradictions: Contradiction[];
  timestamp: number;
}

// ============================================================================
// Mock Response Data
// ============================================================================

const mockResponse: ChatResponse = {
  id: 'msg_123',
  content: `
    The population of New York City is approximately 8.3 million as of 2020.
    
    <span id="evidence-1">However, some sources cite it as 8.8 million.</span>
    
    The city was founded in 1624 by Dutch colonists.
    
    <span id="evidence-2">Alternative historical records suggest 1625 as the founding year.</span>
    
    Central Park spans 843 acres in the heart of Manhattan.
  `,
  contradictions: [
    {
      id: 'c1',
      subject: 'NYC Population',
      description: 'Conflicting population figures from different census data',
      evidenceAnchor: 'evidence-1',
      severity: 'medium',
      source: 'Census 2020 vs 2021 estimate',
    },
    {
      id: 'c2',
      subject: 'NYC Founding Year',
      description: 'Historical records show different founding dates',
      evidenceAnchor: 'evidence-2',
      severity: 'low',
      source: 'Primary historical sources',
    },
  ],
  timestamp: Date.now(),
};

// ============================================================================
// Example Component
// ============================================================================

export const ChatWithBadges: React.FC = () => {
  const [response] = useState(mockResponse);
  const session = loadSession();
  
  // Get show_badges flag from session
  const showBadges = session?.uiFlags?.show_badges ?? false;
  
  return (
    <div className="chat-with-badges">
      {/* Header */}
      <div className="chat-header">
        <h2>Chat Response</h2>
        
        {/* ContradictionBadge */}
        <ContradictionBadge
          contradictions={response.contradictions}
          alwaysShow={showBadges}
          onEvidenceClick={(anchor) => {
            console.log(`Navigated to evidence: ${anchor}`);
          }}
        />
      </div>
      
      {/* Response Content */}
      <div 
        className="chat-content"
        dangerouslySetInnerHTML={{ __html: response.content }}
      />
      
      {/* Info */}
      <div className="chat-info">
        <p>
          The ContradictionBadge shows {response.contradictions.length} contradictions.
          Click the badge to see details and click on subjects to scroll to evidence.
        </p>
        <p>
          <strong>Current setting:</strong> show_badges = {showBadges.toString()}
        </p>
      </div>
    </div>
  );
};

export default ChatWithBadges;
