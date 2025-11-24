'use client';

import { useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { UploadForm } from '@/components/upload/UploadForm';
import { RecentUploadsTable } from '@/components/upload/RecentUploadsTable';

export default function UploadPage() {
  const [refreshToken, setRefreshToken] = useState(0);

  const handleUploadComplete = () => {
    setRefreshToken((token) => token + 1);
  };

  return (
    <section className="space-y-8">
      <PageHeader
        title="Upload & Enrich Corpus"
        description="Ingest new materials, capture epistemic metadata, and view recent uploads."
      />
      <UploadForm onUploadComplete={handleUploadComplete} />
      <RecentUploadsTable refreshToken={refreshToken} />
    </section>
  );
}

