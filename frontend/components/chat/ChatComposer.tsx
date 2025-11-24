'use client';

import { useCallback, useState } from 'react';

interface ChatComposerProps {
  onSend: (message: string) => void;
}

export function ChatComposer({ onSend }: ChatComposerProps) {
  const [message, setMessage] = useState('');

  const handleSend = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    onSend(trimmed);
    setMessage('');
  }, [message, onSend]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <label htmlFor="chat-composer" className="sr-only">
        Message
      </label>
      <textarea
        id="chat-composer"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about evidence, hypotheses, or request an update..."
        rows={3}
        className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
      />
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
        <p>Enter to send • Shift + Enter for newline</p>
        <button
          type="button"
          onClick={handleSend}
          className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
        >
          Send
        </button>
      </div>
    </div>
  );
}

