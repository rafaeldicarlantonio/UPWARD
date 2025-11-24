import type { EvidenceItem, Hypothesis } from '@/lib/types';

interface HypothesesPanelProps {
  hypotheses: Hypothesis[];
  evidenceMap: Record<string, EvidenceItem>;
  collapsed?: boolean;
}

const supportLevelStyles: Record<Hypothesis['supportLevel'], string> = {
  speculative: 'bg-amber-100 text-amber-800',
  plausible: 'bg-blue-100 text-blue-800',
  strong: 'bg-emerald-100 text-emerald-800',
};

export function HypothesesPanel({ hypotheses, evidenceMap, collapsed = false }: HypothesesPanelProps) {
  if (!hypotheses?.length) {
    return null;
  }

  return (
    <section className={`rounded-2xl border border-slate-200 bg-white p-6 shadow-sm ${collapsed ? 'opacity-70' : ''}`}>
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-medium text-slate-900">Hypotheses</h3>
        {collapsed ? <p className="text-xs text-slate-500">Hidden in public mode</p> : null}
      </header>
      <div className={`space-y-4 ${collapsed ? 'hidden' : 'block'}`}>
        {hypotheses.map((hypothesis) => {
          const supportingEvidence = hypothesis.evidenceIds
            ?.map((id) => evidenceMap[id])
            .filter(Boolean) as EvidenceItem[];

          return (
            <article key={hypothesis.id} className="rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-base font-semibold text-slate-900">{hypothesis.label}</h4>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${supportLevelStyles[hypothesis.supportLevel]}`}
                >
                  {hypothesis.supportLevel}
                </span>
                <span className="rounded-full border border-slate-300 px-2 py-0.5 text-[11px] text-slate-600">
                  {supportingEvidence.length} sources
                </span>
              </div>
              <p className="mt-2 text-slate-700">{hypothesis.description}</p>
              {hypothesis.notes ? <p className="mt-2 text-xs text-slate-500">{hypothesis.notes}</p> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

