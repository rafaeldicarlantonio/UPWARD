'use client';

import { useEffect, useState } from 'react';
import { getContradictions, type ContradictionRecord } from '@/lib/api';

export function ContradictionsList() {
  const [contradictions, setContradictions] = useState<ContradictionRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchContradictions = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getContradictions({ status: 'open' });
        if (isMounted) {
          setContradictions(data);
        }
      } catch (err) {
        if (isMounted) {
          const message = err instanceof Error ? err.message : 'Failed to load contradictions.';
          setError(message);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchContradictions();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Open Contradictions</h3>
          <p className="text-sm text-slate-500">Conflicting claims that require review.</p>
        </div>
        {isLoading ? <p className="text-xs text-slate-500">Refreshing…</p> : null}
      </header>
      {error ? (
        <p className="text-sm text-rose-600">{error}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">ID</th>
                <th className="px-4 py-3 text-left">Claim A</th>
                <th className="px-4 py-3 text-left">Claim B</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {contradictions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    No open contradictions.
                  </td>
                </tr>
              ) : (
                contradictions.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{item.id}</td>
                    <td className="px-4 py-3 text-slate-700">{item.claimA || '—'}</td>
                    <td className="px-4 py-3 text-slate-700">{item.claimB || '—'}</td>
                    <td className="px-4 py-3 text-slate-600 capitalize">{item.status}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {item.updatedAt ? new Date(item.updatedAt).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

