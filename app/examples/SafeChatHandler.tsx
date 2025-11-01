/**
 * SafeChatHandler - Example Integration
 * 
 * Demonstrates how to integrate the presenters module for defensive
 * client-side redaction in a chat application.
 */

import React, { useState, useCallback } from 'react';
import {
  redactChatResponseWithTelemetry,
  validateRedaction,
  ChatResponse,
} from '../lib/presenters';
import { getUserRole } from '../state/session';
import ChatAnswer from '../views/ChatAnswer';

// ============================================================================
// Types
// ============================================================================

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  response?: ChatResponse;
}

// ============================================================================
// Safe Chat Handler Component
// ============================================================================

export const SafeChatHandler: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [serverRedactionStatus, setServerRedactionStatus] = useState<Record<string, boolean>>({});
  
  const userRole = getUserRole();
  
  /**
   * Send message with defensive redaction
   */
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;
    
    // Add user message
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    
    try {
      // Call API
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const rawData = await response.json();
      
      // CRITICAL: Validate server redaction
      const isServerRedacted = validateRedaction(rawData, userRole);
      
      // Apply defensive client-side redaction WITH telemetry
      const safeData = redactChatResponseWithTelemetry(rawData, userRole);
      
      // Track server redaction status for debugging
      setServerRedactionStatus(prev => ({
        ...prev,
        [userMessage.id]: isServerRedacted,
      }));
      
      // Log warning if server failed
      if (!isServerRedacted) {
        console.warn(
          '[SafeChatHandler] Server redaction failed. Client-side redaction applied.',
          { role: userRole, messageId: userMessage.id }
        );
      }
      
      // Add assistant message with SAFE response
      const assistantMessage: Message = {
        id: `msg-${Date.now()}-assistant`,
        role: 'assistant',
        content: safeData.answer,
        response: safeData,
      };
      setMessages(prev => [...prev, assistantMessage]);
      
    } catch (error) {
      console.error('[SafeChatHandler] Error sending message:', error);
      
      // Add error message
      const errorMessage: Message = {
        id: `msg-${Date.now()}-error`,
        role: 'assistant',
        content: 'Sorry, an error occurred. Please try again.',
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }, [userRole]);
  
  return (
    <div className="safe-chat-handler">
      {/* Header */}
      <div className="chat-header">
        <h2>Safe Chat (with Client-Side Redaction)</h2>
        <div className="role-indicator">
          Role: <strong>{userRole}</strong>
        </div>
      </div>
      
      {/* Messages */}
      <div className="chat-messages">
        {messages.map(msg => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            {msg.role === 'user' ? (
              <div className="message-content">
                <strong>You:</strong> {msg.content}
              </div>
            ) : (
              <div className="message-content">
                <strong>Assistant:</strong>
                
                {/* Server redaction status indicator */}
                {serverRedactionStatus[msg.id] === false && (
                  <div className="warning-banner">
                    ⚠️ Server redaction failed. Client-side protection applied.
                  </div>
                )}
                
                {/* Render full response with ChatAnswer */}
                {msg.response ? (
                  <ChatAnswer
                    answer={msg.response.answer}
                    evidence={msg.response.evidence}
                    process_trace_summary={msg.response.process_trace_summary}
                    compare_summary={msg.response.compare_summary}
                    contradictions={msg.response.contradictions}
                    role_applied={msg.response.role_applied}
                  />
                ) : (
                  <div>{msg.content}</div>
                )}
              </div>
            )}
          </div>
        ))}
        
        {loading && (
          <div className="message message-assistant loading">
            <div className="loading-indicator">
              <span className="dot">.</span>
              <span className="dot">.</span>
              <span className="dot">.</span>
            </div>
          </div>
        )}
      </div>
      
      {/* Input */}
      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={e => e.key === 'Enter' && sendMessage(input)}
          placeholder="Ask a question..."
          disabled={loading}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
      
      {/* Debug Panel (Development Only) */}
      {process.env.NODE_ENV === 'development' && (
        <div className="debug-panel">
          <h3>Debug Info</h3>
          <ul>
            <li>User Role: {userRole}</li>
            <li>Total Messages: {messages.length}</li>
            <li>
              Server Redaction Failures:{' '}
              {Object.values(serverRedactionStatus).filter(v => v === false).length}
            </li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default SafeChatHandler;

// ============================================================================
// Example: Manual Redaction Check
// ============================================================================

/**
 * Example function showing how to manually check and apply redaction
 */
export function manualRedactionExample() {
  const userRole = getUserRole();
  
  // Receive response from API
  const serverResponse: ChatResponse = {
    answer: 'The answer is...',
    process_trace_summary: [
      { step: 'parse', duration_ms: 10 },
      { step: 'retrieve', duration_ms: 50 },
      // ... potentially 8+ lines
    ],
    evidence: [
      // ... potentially includes external evidence
    ],
  };
  
  // Check if server properly redacted
  const isServerRedacted = validateRedaction(serverResponse, userRole);
  
  if (!isServerRedacted) {
    console.warn('Server failed to redact. Applying client-side redaction.');
    
    // Apply client-side redaction
    const safeResponse = redactChatResponseWithTelemetry(serverResponse, userRole);
    
    // Use safe response
    return safeResponse;
  }
  
  // Server redacted correctly, but still apply defensive redaction
  // (defense in depth)
  return redactChatResponseWithTelemetry(serverResponse, userRole);
}

// ============================================================================
// Example: Testing Server Redaction
// ============================================================================

/**
 * Test helper to verify server is redacting correctly
 */
export async function testServerRedaction() {
  const userRole = getUserRole();
  
  // Send test message
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: 'test message' }),
  });
  
  const data = await response.json();
  
  // Validate
  const isRedacted = validateRedaction(data, userRole);
  
  console.log('Server Redaction Test:', {
    role: userRole,
    passed: isRedacted,
    response: data,
  });
  
  return {
    passed: isRedacted,
    response: data,
  };
}
