import { PageHeader } from '@/components/layout/PageHeader';

export default function UploadPage() {
  return (
    <section className="space-y-6">
      <PageHeader
        title="Upload & Enrich Corpus"
        description="Ingest new materials, capture epistemic metadata, and view recent uploads."
      />
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          Upload workflow coming soon. You’ll be able to submit files, annotate metadata, and track ingestion status.
        </p>
      </div>
    </section>
  );
}

