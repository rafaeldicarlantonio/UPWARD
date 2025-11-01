/**
 * Example: Standalone ProcessLedger Demo
 * 
 * Demonstrates ProcessLedger behavior across different roles.
 * Useful for testing, documentation, or style guide.
 */

import React, { useState } from 'react';
import ProcessLedger from '../components/ProcessLedger';
import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, Role } from '../lib/roles';

// ============================================================================
// Mock Data
// ============================================================================

const mockTraceSummary = [
  {
    step: 'Parse query',
    duration_ms: 12,
    status: 'success' as const,
    details: 'Query parsed successfully',
  },
  {
    step: 'Retrieve candidates',
    duration_ms: 245,
    status: 'success' as const,
    details: 'Found 8 candidates from vector store',
    provenance: 'pinecone:explicate-index',
  },
  {
    step: 'Generate response',
    duration_ms: 1834,
    status: 'success' as const,
    details: 'LLM generation complete',
    prompt: 'You are a helpful assistant. Answer the following question...',
    metadata: {
      model: 'gpt-4',
      tokens: 1250,
      internal_id: 'req_abc123',
    },
  },
  {
    step: 'Format output',
    duration_ms: 8,
    status: 'success' as const,
    details: 'Response formatted for display',
  },
  {
    step: 'Cache write',
    duration_ms: 15,
    status: 'success' as const,
    details: 'Response cached for future use',
  },
  {
    step: 'Metrics logging',
    duration_ms: 3,
    status: 'success' as const,
    details: 'Metrics recorded to analytics',
  },
];

// ============================================================================
// Demo Component
// ============================================================================

export const StandaloneExample: React.FC = () => {
  const [selectedRole, setSelectedRole] = useState<Role>(ROLE_GENERAL);
  const [showLedger, setShowLedger] = useState(true);
  
  const roles = [
    { value: ROLE_GENERAL, label: 'General', description: 'Limited view (4 lines max, no expand)' },
    { value: ROLE_PRO, label: 'Pro', description: 'Full summary + expandable' },
    { value: ROLE_SCHOLARS, label: 'Scholars', description: 'Full summary + expandable' },
    { value: ROLE_ANALYTICS, label: 'Analytics', description: 'Full summary + expandable' },
  ];
  
  return (
    <div className="standalone-demo">
      <div className="demo-controls">
        <h2>ProcessLedger Demo</h2>
        
        {/* Role Selector */}
        <div className="control-group">
          <label>User Role:</label>
          <div className="role-buttons">
            {roles.map((role) => (
              <button
                key={role.value}
                className={`role-button ${selectedRole === role.value ? 'active' : ''}`}
                onClick={() => setSelectedRole(role.value as Role)}
                title={role.description}
              >
                {role.label}
              </button>
            ))}
          </div>
          <p className="role-description">
            {roles.find(r => r.value === selectedRole)?.description}
          </p>
        </div>
        
        {/* Show Ledger Toggle */}
        <div className="control-group">
          <label>
            <input
              type="checkbox"
              checked={showLedger}
              onChange={(e) => setShowLedger(e.target.checked)}
            />
            Show Ledger (ui.flags.show_ledger)
          </label>
        </div>
        
        {/* Instructions */}
        <div className="demo-instructions">
          <h3>Try it:</h3>
          <ul>
            <li>Select different roles to see redaction differences</li>
            <li>General users see max 4 lines, no expand button</li>
            <li>Pro+ users can expand to see full trace</li>
            <li>Click line details toggles (+) to see more info</li>
            <li>Uncheck "Show Ledger" to hide component</li>
          </ul>
        </div>
      </div>
      
      {/* ProcessLedger */}
      <div className="demo-preview">
        <h3>Preview:</h3>
        
        {showLedger ? (
          <ProcessLedger
            traceSummary={mockTraceSummary}
            messageId="demo_msg_123"
            userRole={selectedRole}
            showLedger={showLedger}
            onExpandChange={(expanded) => {
              console.log(`Ledger ${expanded ? 'expanded' : 'collapsed'}`);
            }}
          />
        ) : (
          <div className="demo-hidden-message">
            Ledger hidden (showLedger = false)
          </div>
        )}
      </div>
      
      {/* Expected Behavior */}
      <div className="demo-expected">
        <h3>Expected Behavior for {roles.find(r => r.value === selectedRole)?.label}:</h3>
        {selectedRole === ROLE_GENERAL ? (
          <ul>
            <li>✓ Shows maximum 4 lines</li>
            <li>✓ No expand button</li>
            <li>✓ Prompts and provenance hidden</li>
            <li>✓ Sensitive metadata removed (internal_id, etc.)</li>
            <li>✓ Footer shows: "Showing 4 of 6 steps (Upgrade to Pro...)"</li>
          </ul>
        ) : (
          <ul>
            <li>✓ Shows all 6 lines in summary</li>
            <li>✓ Expand button available</li>
            <li>✓ Can view full trace on expand</li>
            <li>✓ All fields visible (prompts, provenance, metadata)</li>
            <li>✓ No footer message</li>
          </ul>
        )}
      </div>
      
      {/* Data Visibility Table */}
      <div className="demo-data-visibility">
        <h3>Data Visibility by Role:</h3>
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>General</th>
              <th>Pro/Scholars/Analytics</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>step</td>
              <td>✓ Visible</td>
              <td>✓ Visible</td>
            </tr>
            <tr>
              <td>duration_ms</td>
              <td>✓ Visible</td>
              <td>✓ Visible</td>
            </tr>
            <tr>
              <td>status</td>
              <td>✓ Visible</td>
              <td>✓ Visible</td>
            </tr>
            <tr>
              <td>details</td>
              <td>✓ Visible</td>
              <td>✓ Visible</td>
            </tr>
            <tr>
              <td>prompt</td>
              <td>✗ Hidden</td>
              <td>✓ Visible</td>
            </tr>
            <tr>
              <td>provenance</td>
              <td>✗ Hidden</td>
              <td>✓ Visible</td>
            </tr>
            <tr>
              <td>metadata</td>
              <td>⚠ Sanitized</td>
              <td>✓ Full</td>
            </tr>
            <tr>
              <td>Line count</td>
              <td>⚠ Max 4</td>
              <td>✓ All</td>
            </tr>
            <tr>
              <td>Expand to full trace</td>
              <td>✗ No</td>
              <td>✓ Yes</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default StandaloneExample;
