'use client';

import type { ChatResponse, EvidenceItem } from '@/lib/types';
import { useMode } from '@/app/context/mode-context';
import { AnswerPanel } from './panels/AnswerPanel';
import { EvidencePanel } from './panels/EvidencePanel';
import { HypothesesPanel } from './panels/HypothesesPanel';
import { UncertaintyPanel } from './panels/UncertaintyPanel';

interface AssistantMessageProps {
  content: string;
  meta?: ChatResponse;
}

const buildEvidenceMap = (items: EvidenceItem[] = []) =>
  items.reduce<Record<string, EvidenceItem>>((acc, item) => {
    acc[item.id] = item;
    return acc;
  }, {});

export function AssistantMessage({ content, meta }: AssistantMessageProps) {
  const { mode } = useMode();

  if (!meta) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-slate-900/90 p-4 text-sm text-white shadow-md">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-200">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Assistant
        </div>
        <p className="mt-2 text-base leading-relaxed text-slate-50">{content}</p>
      </div>
    );
  }

  const evidenceMap = buildEvidenceMap(meta.evidence);
  const isPublic = mode === 'public';

  return (
    <div className="space-y-5">
      <AnswerPanel answer={meta.answer} />
      <EvidencePanel evidence={meta.evidence} collapsed={isPublic} />
      <HypothesesPanel hypotheses={meta.hypotheses} evidenceMap={evidenceMap} collapsed={isPublic} />
      <UncertaintyPanel text={meta.uncertainty} />
    </div>
  );
}

