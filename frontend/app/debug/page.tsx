import { PageHeader } from '@/components/layout/PageHeader';

export default function DebugPage() {
  return (
    <section className="space-y-6">
      <PageHeader
        title="Epistemic Control Room"
        description="Inspect memories, Rheomode runs, contradictions, and system diagnostics."
      />
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          Debug tooling coming soon. This space will expose lookup forms, trace viewers, and metrics.
        </p>
      </div>
    </section>
  );
}

