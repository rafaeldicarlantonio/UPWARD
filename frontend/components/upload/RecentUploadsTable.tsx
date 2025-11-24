'use client';

import { useEffect, useState } from 'react';
import { getRecentUploads, RecentUpload } from '@/lib/api';

interface RecentUploadsTableProps {
  refreshToken?: number;
}

export function RecentUploadsTable({ refreshToken = 0 }: RecentUploadsTableProps) {
  const [uploads, setUploads] = useState<RecentUpload[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchUploads = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getRecentUploads();
        if (isMounted) {
          setUploads(data);
        }
      } catch (err) {
        if (isMounted) {
          const message = err instanceof Error ? err.message : 'Failed to load uploads.';
          setError(message);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchUploads();
    return () => {
      isMounted = false;
    };
  }, [refreshToken]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Recent Uploads</h3>
          <p className="text-sm text-slate-500">Latest files ingested into the corpus.</p>
        </div>
        {isLoading ? <p className="text-xs text-slate-500">Refreshing…</p> : null}
      </header>
      {error ? (
        <p className="text-sm text-rose-600">{error}</p>
      ) : uploads.length === 0 && !isLoading ? (
        <p className="text-sm text-slate-500">No uploads found yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Filename</th>
                <th className="px-4 py-3 text-left">Source Type</th>
                <th className="px-4 py-3 text-left">Reliability</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Uploaded At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {uploads.map((upload) => (
                <tr key={upload.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{upload.filename}</td>
                  <td className="px-4 py-3 text-slate-600">{upload.sourceType || '—'}</td>
                  <td className="px-4 py-3 text-slate-600 capitalize">{upload.reliability || '—'}</td>
                  <td className="px-4 py-3 text-slate-600 capitalize">{upload.status || '—'}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {upload.uploadedAt ? new Date(upload.uploadedAt).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

