export type Mode = 'public' | 'scholar' | 'staff';

export interface EvidenceItem {
  id: string;
  title: string;
  sourceType: string;
  date?: string;
  reliability?: 'low' | 'medium' | 'high';
  status?: 'new' | 'under_review' | 'accepted' | 'deprecated';
  snippet?: string;
  originSummary?: string;
}

export interface Hypothesis {
  id: string;
  label: string;
  description: string;
  supportLevel: 'speculative' | 'plausible' | 'strong';
  evidenceIds: string[];
  notes?: string;
}

export interface ProcessTrace {
  relevate: string[];
  evidentiate: EvidenceItem[];
  divide: string[];
  ordinate: string;
}

export interface ChatResponse {
  answer: string;
  evidence: EvidenceItem[];
  hypotheses: Hypothesis[];
  uncertainty: string;
  processTrace?: ProcessTrace;
  mode: Mode;
  sessionId?: string;
  contradictionsCount?: number;
}

