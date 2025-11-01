/**
 * Presenters Module
 * 
 * Client-side role-aware redaction and formatting for chat responses.
 * 
 * This module provides last-mile defensive redaction in case the server
 * fails to properly redact sensitive content. It ensures that General users
 * never see content they shouldn't, even if server-side redaction fails.
 * 
 * Security Philosophy:
 * - Defense in depth: Client-side as backup to server-side redaction
 * - Fail-safe: Over-redact rather than under-redact
 * - Role-aware: Different redaction policies per role
 */

import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, Role } from './roles';

// ============================================================================
// Types
// ============================================================================

/**
 * Process trace line from server
 */
export interface ProcessTraceLine {
  step: string;
  duration_ms?: number;
  details?: string;
  tokens?: number;
  model?: string;
  prompt?: string;
  raw_provenance?: any;
}

/**
 * Evidence item from server
 */
export interface EvidenceItem {
  text: string;
  score?: number;
  source?: string;
  label?: string;
  url?: string;
  is_external?: boolean;
  chunk_id?: string;
  memory_id?: string;
}

/**
 * Chat response structure
 */
export interface ChatResponse {
  answer: string;
  process_trace_summary?: ProcessTraceLine[];
  evidence?: EvidenceItem[];
  compare_summary?: {
    stance_a?: string;
    stance_b?: string;
    evidence_a?: EvidenceItem[];
    evidence_b?: EvidenceItem[];
  };
  contradictions?: any[];
  role_applied?: string;
}

/**
 * Redaction policy configuration
 */
export interface RedactionPolicy {
  /** Maximum ledger lines for this role */
  maxLedgerLines: number;
  
  /** Whether to show raw prompts */
  showRawPrompts: boolean;
  
  /** Whether to show provenance */
  showProvenance: boolean;
  
  /** Whether to allow external evidence */
  allowExternal: boolean;
  
  /** Max snippet length by source label */
  maxSnippetLengths: Record<string, number>;
  
  /** Default max snippet length */
  defaultMaxSnippet: number;
}

// ============================================================================
// Redaction Policies by Role
// ============================================================================

/**
 * Get redaction policy for a role
 */
export function getRedactionPolicy(role: Role): RedactionPolicy {
  switch (role) {
    case ROLE_GENERAL:
      return {
        maxLedgerLines: 4,
        showRawPrompts: false,
        showProvenance: false,
        allowExternal: false,
        maxSnippetLengths: {
          'Wikipedia': 480,
          'arXiv': 640,
          'PubMed': 600,
          'GitHub': 500,
        },
        defaultMaxSnippet: 480,
      };
    
    case ROLE_PRO:
    case ROLE_SCHOLARS:
    case ROLE_ANALYTICS:
      return {
        maxLedgerLines: Infinity,
        showRawPrompts: true,
        showProvenance: true,
        allowExternal: true,
        maxSnippetLengths: {
          'Wikipedia': 800,
          'arXiv': 1200,
          'PubMed': 1000,
          'GitHub': 800,
        },
        defaultMaxSnippet: 800,
      };
    
    default:
      // Defensive: treat unknown roles as General
      return getRedactionPolicy(ROLE_GENERAL);
  }
}

// ============================================================================
// Ledger Redaction
// ============================================================================

/**
 * Redact process trace (ledger) based on role
 * 
 * For General users:
 * - Limit to first 4 lines
 * - Strip raw prompts
 * - Strip provenance
 * 
 * For higher roles:
 * - No redaction (show everything)
 */
export function redactProcessTrace(
  trace: ProcessTraceLine[] | undefined,
  role: Role
): ProcessTraceLine[] | undefined {
  if (!trace || trace.length === 0) {
    return trace;
  }
  
  const policy = getRedactionPolicy(role);
  
  // Limit number of lines
  let redactedTrace = trace.slice(0, policy.maxLedgerLines);
  
  // Strip sensitive fields if not allowed
  if (!policy.showRawPrompts || !policy.showProvenance) {
    redactedTrace = redactedTrace.map(line => {
      const redactedLine: ProcessTraceLine = {
        step: line.step,
        duration_ms: line.duration_ms,
        tokens: line.tokens,
        model: line.model,
      };
      
      // Keep details if allowed
      if (line.details) {
        redactedLine.details = line.details;
      }
      
      // Strip prompt if not allowed
      if (policy.showRawPrompts && line.prompt) {
        redactedLine.prompt = line.prompt;
      }
      
      // Strip provenance if not allowed
      if (policy.showProvenance && line.raw_provenance) {
        redactedLine.raw_provenance = line.raw_provenance;
      }
      
      return redactedLine;
    });
  }
  
  return redactedTrace;
}

/**
 * Check if a ledger is properly redacted for the given role
 * (Used in tests to verify server behavior)
 */
export function isLedgerRedacted(
  trace: ProcessTraceLine[] | undefined,
  role: Role
): boolean {
  if (!trace) return true;
  
  const policy = getRedactionPolicy(role);
  
  // Check length
  if (trace.length > policy.maxLedgerLines) {
    return false;
  }
  
  // Check for forbidden fields
  if (!policy.showRawPrompts) {
    const hasPrompts = trace.some(line => line.prompt !== undefined);
    if (hasPrompts) return false;
  }
  
  if (!policy.showProvenance) {
    const hasProvenance = trace.some(line => line.raw_provenance !== undefined);
    if (hasProvenance) return false;
  }
  
  return true;
}

// ============================================================================
// External Evidence Redaction
// ============================================================================

/**
 * Get maximum snippet length for a source label
 */
export function getMaxSnippetLength(label: string | undefined, role: Role): number {
  const policy = getRedactionPolicy(role);
  
  if (!label) {
    return policy.defaultMaxSnippet;
  }
  
  return policy.maxSnippetLengths[label] || policy.defaultMaxSnippet;
}

/**
 * Truncate text to maximum length
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  
  // Truncate and add ellipsis
  return text.substring(0, maxLength - 3) + '...';
}

/**
 * Redact a single evidence item based on role
 * 
 * For external evidence:
 * - General: Strip completely or truncate to policy length
 * - Higher roles: Truncate to generous policy length
 */
export function redactEvidenceItem(
  item: EvidenceItem,
  role: Role
): EvidenceItem | null {
  const policy = getRedactionPolicy(role);
  
  // If external and role doesn't allow external, strip completely
  if (item.is_external && !policy.allowExternal) {
    return null;
  }
  
  // For external evidence, enforce truncation
  if (item.is_external) {
    const maxLength = getMaxSnippetLength(item.label, role);
    const redactedItem: EvidenceItem = {
      ...item,
      text: truncateText(item.text, maxLength),
    };
    
    // Strip internal identifiers for external sources
    delete redactedItem.chunk_id;
    delete redactedItem.memory_id;
    
    return redactedItem;
  }
  
  // Internal evidence: no redaction needed
  return item;
}

/**
 * Redact evidence array based on role
 */
export function redactEvidence(
  evidence: EvidenceItem[] | undefined,
  role: Role
): EvidenceItem[] | undefined {
  if (!evidence || evidence.length === 0) {
    return evidence;
  }
  
  const redacted = evidence
    .map(item => redactEvidenceItem(item, role))
    .filter((item): item is EvidenceItem => item !== null);
  
  return redacted.length > 0 ? redacted : undefined;
}

/**
 * Check if evidence is properly redacted
 */
export function isEvidenceRedacted(
  evidence: EvidenceItem[] | undefined,
  role: Role
): boolean {
  if (!evidence) return true;
  
  const policy = getRedactionPolicy(role);
  
  for (const item of evidence) {
    // Check if external evidence is allowed
    if (item.is_external && !policy.allowExternal) {
      return false;
    }
    
    // Check external snippet length
    if (item.is_external) {
      const maxLength = getMaxSnippetLength(item.label, role);
      if (item.text.length > maxLength) {
        return false;
      }
    }
  }
  
  return true;
}

// ============================================================================
// Compare Summary Redaction
// ============================================================================

/**
 * Redact compare summary based on role
 */
export function redactCompareSummary(
  compareSummary: ChatResponse['compare_summary'] | undefined,
  role: Role
): ChatResponse['compare_summary'] | undefined {
  if (!compareSummary) {
    return compareSummary;
  }
  
  return {
    stance_a: compareSummary.stance_a,
    stance_b: compareSummary.stance_b,
    evidence_a: redactEvidence(compareSummary.evidence_a, role),
    evidence_b: redactEvidence(compareSummary.evidence_b, role),
  };
}

// ============================================================================
// Full Response Redaction
// ============================================================================

/**
 * Apply full client-side redaction to a chat response
 * 
 * This is the main entry point for defensive redaction.
 * Call this on every response before displaying to the user.
 */
export function redactChatResponse(
  response: ChatResponse,
  role: Role
): ChatResponse {
  return {
    ...response,
    process_trace_summary: redactProcessTrace(response.process_trace_summary, role),
    evidence: redactEvidence(response.evidence, role),
    compare_summary: redactCompareSummary(response.compare_summary, role),
    role_applied: role, // Track which role was applied
  };
}

/**
 * Validate that a response is properly redacted for the given role
 * 
 * Returns true if properly redacted, false if server failed to redact.
 * Use this in telemetry to track server redaction failures.
 */
export function validateRedaction(
  response: ChatResponse,
  role: Role
): boolean {
  const traceOk = isLedgerRedacted(response.process_trace_summary, role);
  const evidenceOk = isEvidenceRedacted(response.evidence, role);
  const compareAOk = isEvidenceRedacted(response.compare_summary?.evidence_a, role);
  const compareBOk = isEvidenceRedacted(response.compare_summary?.evidence_b, role);
  
  return traceOk && evidenceOk && compareAOk && compareBOk;
}

// ============================================================================
// Telemetry Helpers
// ============================================================================

/**
 * Report redaction failure to telemetry
 */
export function reportRedactionFailure(
  response: ChatResponse,
  role: Role,
  failureType: 'ledger' | 'evidence' | 'compare'
): void {
  if (typeof window !== 'undefined' && window.analytics) {
    window.analytics.track('redaction.client_side_applied', {
      role,
      failureType,
      messageId: (response as any).message_id,
      timestamp: new Date().toISOString(),
    });
  }
  
  // Also log to console in development
  if (process.env.NODE_ENV === 'development') {
    console.warn(
      `[Presenters] Client-side redaction applied for ${role}. ` +
      `Server failed to redact ${failureType}. This should not happen in production.`
    );
  }
}

/**
 * Apply redaction with telemetry
 */
export function redactChatResponseWithTelemetry(
  response: ChatResponse,
  role: Role
): ChatResponse {
  // Check if server properly redacted
  const isValid = validateRedaction(response, role);
  
  if (!isValid) {
    // Determine failure type
    if (!isLedgerRedacted(response.process_trace_summary, role)) {
      reportRedactionFailure(response, role, 'ledger');
    }
    if (!isEvidenceRedacted(response.evidence, role)) {
      reportRedactionFailure(response, role, 'evidence');
    }
    if (
      !isEvidenceRedacted(response.compare_summary?.evidence_a, role) ||
      !isEvidenceRedacted(response.compare_summary?.evidence_b, role)
    ) {
      reportRedactionFailure(response, role, 'compare');
    }
  }
  
  // Apply client-side redaction regardless
  return redactChatResponse(response, role);
}

// ============================================================================
// Exports
// ============================================================================

export default {
  getRedactionPolicy,
  redactProcessTrace,
  redactEvidence,
  redactEvidenceItem,
  redactCompareSummary,
  redactChatResponse,
  redactChatResponseWithTelemetry,
  validateRedaction,
  isLedgerRedacted,
  isEvidenceRedacted,
  getMaxSnippetLength,
  truncateText,
  reportRedactionFailure,
};
