'use client';

interface UserMessageProps {
  content: string;
}

export function UserMessage({ content }: UserMessageProps) {
  return (
    <div className="ml-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
      <div className="flex items-center justify-end gap-2 text-xs uppercase tracking-wide text-slate-500">
        User
        <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
      </div>
      <p className="mt-2 text-base leading-relaxed text-slate-800">{content}</p>
    </div>
  );
}

