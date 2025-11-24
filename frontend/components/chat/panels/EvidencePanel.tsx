import { useState } from 'react';
import type { EvidenceItem } from '@/lib/types';

interface EvidencePanelProps {
  evidence: EvidenceItem[];
  collapsed?: boolean;
}

export function EvidencePanel({ evidence, collapsed = false }: EvidencePanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);

  if (!evidence?.length) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-medium text-slate-900">Evidence</h3>
        <button
          type="button"
          className="text-xs font-medium text-slate-600 hover:text-slate-900"
          onClick={() => setIsCollapsed((prev) => !prev)}
        >
          {isCollapsed ? 'Expand' : 'Collapse'}
        </button>
      </header>
      <div className={`space-y-4 ${isCollapsed ? 'hidden' : 'block'}`}>
        {evidence.map((item) => (
          <article
            key={item.id}
            className="rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm text-slate-700"
          >
            <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
              <span className="font-semibold text-slate-800">{item.title}</span>
              <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                {item.sourceType}
              </span>
              {item.date ? <span>{new Date(item.date).toLocaleDateString()}</span> : null}
              {item.reliability ? (
                <span className="rounded-full border border-slate-300 px-2 py-0.5 text-[10px]">
                  {item.reliability}
                </span>
              ) : null}
              {item.status ? (
                <span className="rounded-full border border-slate-300 px-2 py-0.5 text-[10px]">
                  {item.status}
                </span>
              ) : null}
            </div>
            {(item.snippet || item.originSummary) && (
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-slate-600">Details</summary>
                <div className="mt-2 space-y-2 text-slate-600">
                  {item.snippet ? <p className="text-sm italic text-slate-700">“{item.snippet}”</p> : null}
                  {item.originSummary ? <p className="text-xs text-slate-500">{item.originSummary}</p> : null}
                </div>
              </details>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

