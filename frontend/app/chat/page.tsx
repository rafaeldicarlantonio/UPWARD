import { PageHeader } from '@/components/layout/PageHeader';

export default function ChatPage() {
  return (
    <section className="space-y-6">
      <PageHeader
        title="Epistemic Workspace"
        description="Primary interface for conversing with UPWARD, reviewing answers, and inspecting the REDO trace."
      />
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          Chat UI coming soon. This area will show conversation threads, epistemic panels, and the process sidebar.
        </p>
      </div>
    </section>
  );
}

