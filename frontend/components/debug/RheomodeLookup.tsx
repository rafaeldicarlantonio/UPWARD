'use client';

import { useState } from 'react';
import { getRheomodeRun, type RheomodeRun } from '@/lib/api';

export function RheomodeLookup() {
  const [runId, setRunId] = useState('');
  const [run, setRun] = useState<RheomodeRun | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLookup = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!runId.trim()) {
      setError('Enter a run ID.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setRun(null);
    try {
      const result = await getRheomodeRun(runId.trim());
      setRun(result);
    } catch (lookupError) {
      const message =
        lookupError instanceof Error ? lookupError.message : 'Failed to fetch run.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const process = run?.processTrace || run?.processTraceSummary;
  const metadata = (run?.metadata ?? {}) as Record<string, unknown>;
  const question = (run?.query || metadata.question || '') as string;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Rheomode Run Lookup</h3>
          <p className="text-sm text-slate-500">Inspect REDO traces recorded for chat runs.</p>
        </div>
      </header>
      <form onSubmit={handleLookup} className="flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          value={runId}
          onChange={(event) => setRunId(event.target.value)}
          placeholder="run_123"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading}
          className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isLoading ? 'Looking up…' : 'Lookup run'}
        </button>
      </form>
      {isLoading ? <p className="mt-2 text-xs text-slate-500">Fetching run…</p> : null}
      {error ? <p className="mt-2 text-sm text-rose-600">{error}</p> : null}
      {!run && !error && !isLoading ? (
        <p className="mt-4 text-sm text-slate-500">Enter a run ID to inspect its REDO trace.</p>
      ) : null}
      {run ? (
        <article className="mt-4 space-y-4 rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm">
          <InfoBlock label="Question" value={question || '—'} />
          <TraceList title="Relevate" items={process?.relevate} />
          <TraceEvidence title="Evidentiate" items={process?.evidentiate?.map((item) => item.title)} />
          <TraceList title="Divide" items={process?.divide} />
          <InfoBlock label="Ordinate" value={process?.ordinate || '—'} />
        </article>
      ) : null}
    </section>
  );
}

function TraceList({ title, items }: { title: string; items?: string[] }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      {items?.length ? (
        <ul className="mt-1 space-y-1 text-slate-700">
          {items.map((item) => (
            <li key={item} className="rounded-lg bg-white px-3 py-2 text-sm shadow-sm">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-400">No entries.</p>
      )}
    </div>
  );
}

function TraceEvidence({ title, items }: { title: string; items?: (string | undefined)[] }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      {items?.length ? (
        <ul className="mt-1 space-y-1 text-slate-700">
          {items.map((item) =>
            item ? (
              <li key={item} className="rounded-lg bg-white px-3 py-2 text-sm shadow-sm">
                {item}
              </li>
            ) : null,
          )}
        </ul>
      ) : (
        <p className="text-xs text-slate-400">No evidence recorded.</p>
      )}
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-slate-700">{value || '—'}</p>
    </div>
  );
}
