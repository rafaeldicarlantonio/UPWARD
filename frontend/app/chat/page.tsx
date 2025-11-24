'use client';

import { useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import { ChatComposer } from '@/components/chat/ChatComposer';
import { ProcessSidebar } from '@/components/chat/ProcessSidebar';
import type { ChatMessage } from '@/components/chat/types';

const generateSessionId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `session-${Math.random().toString(36).slice(2)}`;
};

export default function ChatPage() {
  const [sessionId] = useState<string>(() => generateSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const handleSend = (content: string) => {
    const timestamp = Date.now();
    const userMessage: ChatMessage = {
      id: `${sessionId}-user-${timestamp}`,
      role: 'user',
      content,
    };
    const assistantMessage: ChatMessage = {
      id: `${sessionId}-assistant-${timestamp + 1}`,
      role: 'assistant',
      content: 'Placeholder response. Structured epistemic output coming soon.',
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
  };

  return (
    <section className="space-y-6">
      <PageHeader
        title="Epistemic Workspace"
        description="Primary interface for conversing with UPWARD, reviewing answers, and inspecting the REDO trace."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-h-[60vh] flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex-1 overflow-y-auto px-6 py-6">
            <ChatMessageList messages={messages} />
          </div>
          <div className="border-t border-slate-100 px-6 py-4">
            <ChatComposer onSend={handleSend} />
          </div>
        </div>
        <div className="lg:sticky lg:top-32">
          <ProcessSidebar />
        </div>
      </div>
    </section>
  );
}

