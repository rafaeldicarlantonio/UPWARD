'use client';

import { PageHeader } from '@/components/layout/PageHeader';
import { MemoryLookup } from '@/components/debug/MemoryLookup';
import { RheomodeLookup } from '@/components/debug/RheomodeLookup';
import { ContradictionsList } from '@/components/debug/ContradictionsList';

export default function DebugPage() {
  return (
    <section className="space-y-8">
      <PageHeader
        title="Epistemic Control Room"
        description="Inspect memories, Rheomode runs, contradictions, and system diagnostics."
      />
      <MemoryLookup />
      <RheomodeLookup />
      <ContradictionsList />
    </section>
  );
}

