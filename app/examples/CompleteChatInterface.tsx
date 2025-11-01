/**
 * Complete Chat Interface Example
 * 
 * Demonstrates how to use ChatAnswer view in a full chat application
 * with multiple messages, loading states, and real-time updates.
 */

import React, { useState, useEffect } from 'react';
import ChatAnswer, { ChatAnswerData } from '../views/ChatAnswer';
import { loadSession } from '../state/session';
import { Role } from '../lib/roles';

// ============================================================================
// Types
// ============================================================================

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  // For assistant messages
  message_id?: string;
  process_trace_summary?: any[];
  contradictions?: any[];
  compare_summary?: any;
  compare_loading?: boolean;
  trace_loading?: boolean;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockMessages: Message[] = [
  {
    role: 'user',
    content: 'What is the population of New York City?',
    timestamp: new Date(Date.now() - 5000),
  },
  {
    role: 'assistant',
    content: `
      <p>According to the 2020 US Census, New York City's official population 
      is <span id="evidence-1">8,336,817</span>. This represents the most 
      accurate count available.</p>
      <p>However, some estimates suggest the population may be closer to 
      <span id="evidence-2">8.8 million</span> when including undocumented 
      residents and temporary workers.</p>
    `,
    message_id: 'msg_001',
    timestamp: new Date(Date.now() - 3000),
    process_trace_summary: [
      { step: 'Parse query', duration_ms: 12, status: 'success' },
      { step: 'Retrieve candidates', duration_ms: 245, status: 'success' },
      { step: 'Generate response', duration_ms: 1830, status: 'success' },
      { step: 'Format output', duration_ms: 8, status: 'success' },
    ],
    contradictions: [
      {
        id: 'c1',
        subject: 'Population count',
        description: 'Census vs estimates show different numbers',
        evidenceAnchor: 'evidence-1',
        severity: 'medium',
        source: 'Multiple sources',
      },
    ],
    compare_summary: {
      stance_a: 'The population is 8,336,817 (2020 Census)',
      stance_b: 'The population is approximately 8.8 million (estimates)',
      recommendation: 'a',
      confidence: 0.75,
      internal_evidence: [
        {
          text: 'Official Census 2020 data shows 8,336,817 residents',
          confidence: 0.92,
          source: 'US Census Bureau',
        },
        {
          text: 'Historical census data confirms this is the official count',
          confidence: 0.85,
          source: 'Census Historical Records',
        },
      ],
      external_evidence: [],
      metadata: {
        sources_used: { internal: 2, external: 0 },
        used_external: false,
      },
    },
  },
];

// ============================================================================
// Component
// ============================================================================

export const CompleteChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  
  const session = loadSession();
  const userRole = session.metadata.primaryRole;
  const uiFlags = session.uiFlags;
  
  // Simulate streaming response
  const handleSendMessage = async () => {
    if (!input.trim()) return;
    
    // Add user message
    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Add assistant message with loading states
    const assistantMessage: Message = {
      role: 'assistant',
      content: '<p>Loading...</p>',
      message_id: `msg_${Date.now()}`,
      timestamp: new Date(),
      process_trace_summary: [],
      contradictions: [],
      compare_loading: true,
      trace_loading: true,
    };
    
    setMessages(prev => [...prev, assistantMessage]);
    setIsTyping(false);
    
    // Simulate content arriving
    await new Promise(resolve => setTimeout(resolve, 500));
    
    setMessages(prev => prev.map((msg, idx) => 
      idx === prev.length - 1
        ? {
            ...msg,
            content: '<p>This is a simulated response. In a real app, this would come from your API.</p>',
            trace_loading: false,
            process_trace_summary: [
              { step: 'Parse query', duration_ms: 10, status: 'success' },
              { step: 'Generate', duration_ms: 450, status: 'success' },
            ],
          }
        : msg
    ));
    
    // Simulate compare arriving
    if (uiFlags.show_compare) {
      await new Promise(resolve => setTimeout(resolve, 800));
      
      setMessages(prev => prev.map((msg, idx) => 
        idx === prev.length - 1
          ? {
              ...msg,
              compare_loading: false,
              compare_summary: {
                stance_a: 'Position A',
                stance_b: 'Position B',
                recommendation: 'a',
                confidence: 0.70,
                internal_evidence: [
                  { text: 'Evidence supporting position A', confidence: 0.80 },
                ],
                external_evidence: [],
              },
            }
          : msg
      ));
    }
  };
  
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  
  return (
    <div className="complete-chat-interface">
      {/* Header */}
      <div className="chat-header">
        <h2>AI Assistant</h2>
        <div className="user-info">
          <span className="user-role-badge">{userRole}</span>
          <div className="flag-indicators">
            {uiFlags.show_ledger && <span title="Ledger enabled">📋</span>}
            {uiFlags.show_compare && <span title="Compare enabled">⚖️</span>}
            {uiFlags.show_badges && <span title="Badges enabled">🏷️</span>}
            {uiFlags.external_compare && <span title="External compare enabled">🌐</span>}
          </div>
        </div>
      </div>
      
      {/* Messages */}
      <div className="chat-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message message-${message.role}`}>
            {message.role === 'user' ? (
              <div className="user-message">
                <div className="message-avatar">👤</div>
                <div className="message-content">
                  <p>{message.content}</p>
                </div>
              </div>
            ) : (
              <ChatAnswer
                answer={{
                  message_id: message.message_id!,
                  content: message.content,
                  process_trace_summary: message.process_trace_summary,
                  contradictions: message.contradictions,
                  compare_summary: message.compare_summary,
                  compare_loading: message.compare_loading,
                  trace_loading: message.trace_loading,
                }}
                userRole={userRole}
                uiFlags={uiFlags}
                onCompareComplete={(result) => {
                  console.log('Compare completed:', result);
                  // Update message with new compare result
                  setMessages(prev => prev.map((msg, idx) => 
                    idx === index && msg.message_id === message.message_id
                      ? { ...msg, compare_summary: result }
                      : msg
                  ));
                }}
                onEvidenceClick={(anchorId) => {
                  console.log('Navigate to evidence:', anchorId);
                  // Scroll to evidence anchor
                  const element = document.getElementById(anchorId);
                  element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }}
              />
            )}
            <div className="message-timestamp">
              {message.timestamp.toLocaleTimeString()}
            </div>
          </div>
        ))}
        
        {isTyping && (
          <div className="typing-indicator">
            <span className="dot"></span>
            <span className="dot"></span>
            <span className="dot"></span>
          </div>
        )}
      </div>
      
      {/* Input */}
      <div className="chat-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a question..."
          rows={2}
        />
        <button 
          onClick={handleSendMessage}
          disabled={!input.trim() || isTyping}
        >
          Send
        </button>
      </div>
      
      {/* Footer Info */}
      <div className="chat-footer">
        <p>
          Current role: <strong>{userRole}</strong>
          {' • '}
          Ledger: {uiFlags.show_ledger ? '✅ On' : '❌ Off'}
          {' • '}
          Compare: {uiFlags.show_compare ? '✅ On' : '❌ Off'}
        </p>
      </div>
    </div>
  );
};

export default CompleteChatInterface;
