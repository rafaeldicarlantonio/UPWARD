'use client';

import { useState } from 'react';
import { getMemoryById, type MemoryRecord } from '@/lib/api';

export function MemoryLookup() {
  const [memoryId, setMemoryId] = useState('');
  const [memory, setMemory] = useState<MemoryRecord | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLookup = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!memoryId.trim()) {
      setError('Enter a memory ID.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setMemory(null);
    try {
      const result = await getMemoryById(memoryId.trim());
      setMemory(result);
    } catch (lookupError) {
      const message =
        lookupError instanceof Error ? lookupError.message : 'Failed to fetch memory.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const metadata = (memory?.metadata ?? {}) as Record<string, unknown>;
  const snippet =
    memory && typeof memory.content === 'string' && memory.content.trim() ? memory.content : '';
  const metadataSnippet =
    typeof metadata.contentSnippet === 'string' && metadata.contentSnippet ? metadata.contentSnippet : '';
  const displayedSnippet = snippet || metadataSnippet || '—';

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Memory Lookup</h3>
          <p className="text-sm text-slate-500">Inspect stored memories by ID.</p>
        </div>
      </header>
      <form onSubmit={handleLookup} className="flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          value={memoryId}
          onChange={(event) => setMemoryId(event.target.value)}
          placeholder="mem_12345"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading}
          className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isLoading ? 'Looking up…' : 'Lookup memory'}
        </button>
      </form>
      {isLoading ? <p className="mt-2 text-xs text-slate-500">Fetching memory…</p> : null}
      {error ? <p className="mt-2 text-sm text-rose-600">{error}</p> : null}
      {!memory && !error && !isLoading ? (
        <p className="mt-4 text-sm text-slate-500">Enter a memory ID to inspect its metadata.</p>
      ) : null}
      {memory ? (
        <article className="mt-4 space-y-3 rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Title</p>
            <p className="font-medium text-slate-900">{memory.title || 'Untitled memory'}</p>
          </div>
          <InfoLine label="Snippet" value={displayedSnippet} />
          <div className="grid gap-3 md:grid-cols-2">
            <InfoLine label="Source Type" value={(metadata.sourceType as string) || '—'} />
            <InfoLine label="Domain" value={(metadata.domain as string) || '—'} />
            <InfoLine label="Reliability" value={(metadata.reliability as string) || '—'} />
            <InfoLine label="Status" value={(metadata.status as string) || '—'} />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Tags</p>
            <div className="mt-1 flex flex-wrap gap-2">
              {Array.isArray(memory.tags) && memory.tags.length > 0 ? (
                memory.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-white px-3 py-1 text-xs text-slate-700 shadow-sm">
                    {tag}
                  </span>
                ))
              ) : (
                <span className="text-slate-400">—</span>
              )}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <InfoLine
              label="Created"
              value={memory.createdAt ? new Date(memory.createdAt).toLocaleString() : '—'}
            />
            <InfoLine
              label="Updated"
              value={(metadata.updatedAt as string) ? new Date(metadata.updatedAt as string).toLocaleString() : '—'}
            />
          </div>
        </article>
      ) : null}
    </section>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-slate-700">{value || '—'}</p>
    </div>
  );
}
