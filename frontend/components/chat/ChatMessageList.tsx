'use client';

import { AssistantMessage } from './AssistantMessage';
import { UserMessage } from './UserMessage';
import type { ChatMessage } from './types';

interface ChatMessageListProps {
  messages: ChatMessage[];
}

export function ChatMessageList({ messages }: ChatMessageListProps) {
  if (!messages.length) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
        No messages yet. Start the conversation to generate an epistemic response.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {messages.map((message) =>
        message.role === 'assistant' ? (
          <AssistantMessage key={message.id} content={message.content} meta={message.meta} />
        ) : (
          <UserMessage key={message.id} content={message.content} />
        ),
      )}
    </div>
  );
}

