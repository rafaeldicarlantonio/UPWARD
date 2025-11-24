'use client';

import type { Mode, ProcessTrace } from '@/lib/types';

interface ProcessSidebarProps {
  processTrace?: ProcessTrace;
  mode: Mode;
}

export function ProcessSidebar({ processTrace, mode }: ProcessSidebarProps) {
  const isPublic = mode === 'public';

  let content: React.ReactNode = null;

  if (isPublic) {
    content = (
      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-xs text-slate-500">
        Process trace hidden in Public mode. Switch to Scholar or Staff for REDO details.
      </div>
    );
  } else if (!processTrace) {
    content = (
      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-xs text-slate-500">
        No process trace available for this answer.
      </div>
    );
  } else {
    content = (
      <div className="space-y-4">
        <ProcessSection title="Relevate" description="Key concepts surfaced for this query.">
          {processTrace.relevate?.length ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {processTrace.relevate.map((item) => (
                <li key={item} className="rounded-lg bg-slate-50 px-3 py-2">
                  {item}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyLine />
          )}
        </ProcessSection>

        <ProcessSection title="Evidentiate" description="Evidence highlighted during grounding.">
          {processTrace.evidentiate?.length ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {processTrace.evidentiate.map((item) => (
                <li key={item.id} className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="font-medium text-slate-900">{item.title}</p>
                  <p className="text-xs uppercase tracking-wide text-slate-500">{item.sourceType}</p>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyLine />
          )}
        </ProcessSection>

        <ProcessSection title="Divide" description="Sub-questions driving the investigation.">
          {processTrace.divide?.length ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {processTrace.divide.map((item) => (
                <li key={item} className="rounded-lg bg-slate-50 px-3 py-2">
                  {item}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyLine />
          )}
        </ProcessSection>

        <ProcessSection title="Ordinate" description="How the final structure was assembled.">
          {processTrace.ordinate ? (
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{processTrace.ordinate}</p>
          ) : (
            <EmptyLine />
          )}
        </ProcessSection>
      </div>
    );
  }

  return (
    <aside className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-4 space-y-1">
        <p className="text-base font-medium text-slate-900">Process Trace (REDO)</p>
        <p className="text-sm text-slate-500">Scholar & Staff modes visualize Relevate, Evidentiate, Divide, Ordinate.</p>
      </header>
      {content}
    </aside>
  );
}

function ProcessSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <header className="mb-2">
        <p className="text-sm font-medium text-slate-700">{title}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </header>
      {children}
    </section>
  );
}

function EmptyLine() {
  return <p className="rounded-lg border border-dashed border-slate-200 px-3 py-2 text-sm text-slate-500">No data.</p>;
}

