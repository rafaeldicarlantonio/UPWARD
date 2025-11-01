/**
 * Example: Chat Interface with ProcessLedger Integration
 * 
 * Demonstrates how to integrate ProcessLedger into a chat application
 * with proper role resolution and feature flag handling.
 */

import React, { useState, useEffect } from 'react';
import ProcessLedger from '../components/ProcessLedger';
import { loadSession, UserSession } from '../state/session';
import { featureFlags } from '../config/flags';

// ============================================================================
// Types
// ============================================================================

interface ChatMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: number;
  process_trace_summary?: any[];
}

interface ChatResponse {
  message_id: string;
  content: string;
  process_trace_summary: any[];
  metadata: Record<string, any>;
}

// ============================================================================
// Example Component
// ============================================================================

export const ChatWithLedger: React.FC = () => {
  const [session, setSession] = useState<UserSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Load session on mount
  useEffect(() => {
    const loadedSession = loadSession();
    setSession(loadedSession);
  }, []);
  
  // Handle message submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!input.trim() || isLoading) return;
    
    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      content: input,
      role: 'user',
      timestamp: Date.now(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      // Send message to API
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.token || ''}`,
        },
        body: JSON.stringify({
          message: input,
          include_process_trace: true,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data: ChatResponse = await response.json();
      
      const assistantMessage: ChatMessage = {
        id: data.message_id,
        content: data.content,
        role: 'assistant',
        timestamp: Date.now(),
        process_trace_summary: data.process_trace_summary,
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      
      const errorMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        content: 'Sorry, I encountered an error processing your message.',
        role: 'assistant',
        timestamp: Date.now(),
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };
  
  if (!session) {
    return <div>Loading session...</div>;
  }
  
  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <h1>Chat with AI</h1>
        <div className="user-info">
          <span className="user-role">{session.metadata.primaryRole}</span>
          {session.uiFlags.show_ledger && (
            <span className="ledger-badge">📋 Ledger Enabled</span>
          )}
        </div>
      </div>
      
      {/* Messages */}
      <div className="chat-messages">
        {messages.map((message) => (
          <div 
            key={message.id} 
            className={`chat-message chat-message-${message.role}`}
          >
            <div className="message-content">
              {message.content}
            </div>
            
            {/* ProcessLedger for assistant messages */}
            {message.role === 'assistant' && message.process_trace_summary && (
              <ProcessLedger
                traceSummary={message.process_trace_summary}
                messageId={message.id}
                userRole={session.metadata.primaryRole}
                showLedger={session.uiFlags.show_ledger}
                onExpandChange={(expanded) => {
                  console.log(`Ledger ${expanded ? 'expanded' : 'collapsed'} for ${message.id}`);
                }}
              />
            )}
          </div>
        ))}
        
        {isLoading && (
          <div className="chat-message chat-message-assistant loading">
            <div className="message-content">Thinking...</div>
          </div>
        )}
      </div>
      
      {/* Input */}
      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatWithLedger;
