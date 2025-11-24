'use client';

import type { ChatResponse } from '@/lib/types';

interface AssistantMessageProps {
  content: string;
  meta?: ChatResponse;
}

export function AssistantMessage({ content }: AssistantMessageProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-900/90 p-4 text-sm text-white shadow-md">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-200">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        Assistant
      </div>
      <p className="mt-2 text-base leading-relaxed text-slate-50">{content}</p>
    </div>
  );
}

