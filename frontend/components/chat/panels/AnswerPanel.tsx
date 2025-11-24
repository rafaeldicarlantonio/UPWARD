import type { ReactNode } from 'react';

interface AnswerPanelProps {
  answer: string;
  footer?: ReactNode;
}

export function AnswerPanel({ answer, footer }: AnswerPanelProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-medium text-slate-900">Answer</h3>
        {footer}
      </header>
      <p className="text-base leading-relaxed text-slate-800">{answer}</p>
    </section>
  );
}

