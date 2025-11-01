/**
 * Presenters Module Tests
 * 
 * Tests for client-side role-aware redaction, including server misbehavior scenarios.
 */

import {
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
  ProcessTraceLine,
  EvidenceItem,
  ChatResponse,
} from '../../app/lib/presenters';
import { ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS } from '../../app/lib/roles';

// ============================================================================
// Mock Data
// ============================================================================

const mockLongTrace: ProcessTraceLine[] = [
  { step: 'parse_query', duration_ms: 10 },
  { step: 'retrieve', duration_ms: 50, details: 'Found 10 memories' },
  { step: 'rank', duration_ms: 20, tokens: 100 },
  { step: 'generate', duration_ms: 200, model: 'gpt-4', prompt: 'SENSITIVE_PROMPT_TEXT' },
  { step: 'validate', duration_ms: 15, raw_provenance: { source: 'internal' } },
  { step: 'finalize', duration_ms: 5 },
  { step: 'extra_step_7', duration_ms: 5 },
  { step: 'extra_step_8', duration_ms: 5 },
];

const mockInternalEvidence: EvidenceItem[] = [
  {
    text: 'Internal evidence from our knowledge base',
    score: 0.95,
    source: 'memory',
    chunk_id: 'chunk-123',
    memory_id: 'mem-456',
  },
];

const mockExternalEvidence: EvidenceItem[] = [
  {
    text: 'External evidence from Wikipedia. '.repeat(50), // Long text
    score: 0.85,
    source: 'web',
    label: 'Wikipedia',
    url: 'https://en.wikipedia.org/wiki/Example',
    is_external: true,
  },
  {
    text: 'External evidence from arXiv. '.repeat(60), // Very long text
    score: 0.80,
    source: 'web',
    label: 'arXiv',
    url: 'https://arxiv.org/abs/1234.5678',
    is_external: true,
  },
];

const mockMixedEvidence: EvidenceItem[] = [
  ...mockInternalEvidence,
  ...mockExternalEvidence,
];

const mockChatResponse: ChatResponse = {
  answer: 'The answer is 42.',
  process_trace_summary: mockLongTrace,
  evidence: mockMixedEvidence,
  compare_summary: {
    stance_a: 'Position A',
    stance_b: 'Position B',
    evidence_a: mockInternalEvidence,
    evidence_b: mockExternalEvidence,
  },
};

// ============================================================================
// Mock Analytics
// ============================================================================

let mockAnalyticsCalls: any[] = [];

beforeEach(() => {
  mockAnalyticsCalls = [];
  (global as any).window = {
    analytics: {
      track: (event: string, data: any) => {
        mockAnalyticsCalls.push({ event, data });
      },
    },
  };
});

afterEach(() => {
  delete (global as any).window;
});

// ============================================================================
// Tests
// ============================================================================

describe('Presenters Module', () => {
  // ==========================================================================
  // Redaction Policy Tests
  // ==========================================================================
  
  describe('getRedactionPolicy', () => {
    it('returns restrictive policy for General', () => {
      const policy = getRedactionPolicy(ROLE_GENERAL);
      
      expect(policy.maxLedgerLines).toBe(4);
      expect(policy.showRawPrompts).toBe(false);
      expect(policy.showProvenance).toBe(false);
      expect(policy.allowExternal).toBe(false);
      expect(policy.defaultMaxSnippet).toBe(480);
    });
    
    it('returns permissive policy for Pro', () => {
      const policy = getRedactionPolicy(ROLE_PRO);
      
      expect(policy.maxLedgerLines).toBe(Infinity);
      expect(policy.showRawPrompts).toBe(true);
      expect(policy.showProvenance).toBe(true);
      expect(policy.allowExternal).toBe(true);
      expect(policy.defaultMaxSnippet).toBe(800);
    });
    
    it('returns permissive policy for Scholars', () => {
      const policy = getRedactionPolicy(ROLE_SCHOLARS);
      
      expect(policy.showRawPrompts).toBe(true);
      expect(policy.allowExternal).toBe(true);
    });
    
    it('returns permissive policy for Analytics', () => {
      const policy = getRedactionPolicy(ROLE_ANALYTICS);
      
      expect(policy.showRawPrompts).toBe(true);
      expect(policy.allowExternal).toBe(true);
    });
    
    it('defaults to General policy for unknown role', () => {
      const policy = getRedactionPolicy('unknown_role' as any);
      
      expect(policy.maxLedgerLines).toBe(4);
      expect(policy.allowExternal).toBe(false);
    });
  });
  
  // ==========================================================================
  // Ledger Redaction Tests
  // ==========================================================================
  
  describe('redactProcessTrace', () => {
    it('limits ledger to 4 lines for General', () => {
      const redacted = redactProcessTrace(mockLongTrace, ROLE_GENERAL);
      
      expect(redacted).toHaveLength(4);
      expect(redacted![0].step).toBe('parse_query');
      expect(redacted![3].step).toBe('generate');
    });
    
    it('strips prompts for General', () => {
      const redacted = redactProcessTrace(mockLongTrace, ROLE_GENERAL);
      
      const generateStep = redacted!.find(line => line.step === 'generate');
      expect(generateStep?.prompt).toBeUndefined();
    });
    
    it('strips provenance for General', () => {
      const redacted = redactProcessTrace(mockLongTrace, ROLE_GENERAL);
      
      const allSteps = redacted!;
      allSteps.forEach(step => {
        expect(step.raw_provenance).toBeUndefined();
      });
    });
    
    it('preserves safe fields for General', () => {
      const redacted = redactProcessTrace(mockLongTrace, ROLE_GENERAL);
      
      expect(redacted![0].duration_ms).toBe(10);
      expect(redacted![1].details).toBe('Found 10 memories');
      expect(redacted![2].tokens).toBe(100);
      expect(redacted![3].model).toBe('gpt-4');
    });
    
    it('does not redact for Pro', () => {
      const redacted = redactProcessTrace(mockLongTrace, ROLE_PRO);
      
      expect(redacted).toHaveLength(8); // All lines
      
      const generateStep = redacted!.find(line => line.step === 'generate');
      expect(generateStep?.prompt).toBe('SENSITIVE_PROMPT_TEXT');
      
      const validateStep = redacted!.find(line => line.step === 'validate');
      expect(validateStep?.raw_provenance).toEqual({ source: 'internal' });
    });
    
    it('handles undefined trace', () => {
      const redacted = redactProcessTrace(undefined, ROLE_GENERAL);
      expect(redacted).toBeUndefined();
    });
    
    it('handles empty trace', () => {
      const redacted = redactProcessTrace([], ROLE_GENERAL);
      expect(redacted).toEqual([]);
    });
  });
  
  describe('isLedgerRedacted', () => {
    it('returns true for properly redacted General ledger', () => {
      const redacted = redactProcessTrace(mockLongTrace, ROLE_GENERAL);
      expect(isLedgerRedacted(redacted, ROLE_GENERAL)).toBe(true);
    });
    
    it('returns false if ledger too long for General', () => {
      expect(isLedgerRedacted(mockLongTrace, ROLE_GENERAL)).toBe(false);
    });
    
    it('returns false if prompts present for General', () => {
      const trace = [{ step: 'test', prompt: 'SHOULD_NOT_BE_HERE' }];
      expect(isLedgerRedacted(trace, ROLE_GENERAL)).toBe(false);
    });
    
    it('returns false if provenance present for General', () => {
      const trace = [{ step: 'test', raw_provenance: { data: 'secret' } }];
      expect(isLedgerRedacted(trace, ROLE_GENERAL)).toBe(false);
    });
    
    it('returns true for any ledger for Pro', () => {
      expect(isLedgerRedacted(mockLongTrace, ROLE_PRO)).toBe(true);
    });
  });
  
  // ==========================================================================
  // External Evidence Redaction Tests
  // ==========================================================================
  
  describe('getMaxSnippetLength', () => {
    it('returns label-specific length for General', () => {
      expect(getMaxSnippetLength('Wikipedia', ROLE_GENERAL)).toBe(480);
      expect(getMaxSnippetLength('arXiv', ROLE_GENERAL)).toBe(640);
      expect(getMaxSnippetLength('PubMed', ROLE_GENERAL)).toBe(600);
    });
    
    it('returns default length for unknown label', () => {
      expect(getMaxSnippetLength('UnknownSource', ROLE_GENERAL)).toBe(480);
    });
    
    it('returns default length for undefined label', () => {
      expect(getMaxSnippetLength(undefined, ROLE_GENERAL)).toBe(480);
    });
    
    it('returns larger lengths for Pro', () => {
      expect(getMaxSnippetLength('Wikipedia', ROLE_PRO)).toBe(800);
      expect(getMaxSnippetLength('arXiv', ROLE_PRO)).toBe(1200);
    });
  });
  
  describe('truncateText', () => {
    it('truncates text longer than max length', () => {
      const text = 'A'.repeat(1000);
      const truncated = truncateText(text, 100);
      
      expect(truncated.length).toBe(100);
      expect(truncated.endsWith('...')).toBe(true);
      expect(truncated.substring(0, 97)).toBe('A'.repeat(97));
    });
    
    it('does not truncate text shorter than max length', () => {
      const text = 'Short text';
      const truncated = truncateText(text, 100);
      
      expect(truncated).toBe(text);
    });
    
    it('handles exact length', () => {
      const text = 'A'.repeat(100);
      const truncated = truncateText(text, 100);
      
      expect(truncated).toBe(text);
    });
  });
  
  describe('redactEvidenceItem', () => {
    it('strips external evidence for General', () => {
      const item: EvidenceItem = {
        text: 'External text',
        is_external: true,
      };
      
      const redacted = redactEvidenceItem(item, ROLE_GENERAL);
      expect(redacted).toBeNull();
    });
    
    it('keeps internal evidence for General', () => {
      const item: EvidenceItem = {
        text: 'Internal text',
        is_external: false,
      };
      
      const redacted = redactEvidenceItem(item, ROLE_GENERAL);
      expect(redacted).not.toBeNull();
      expect(redacted!.text).toBe('Internal text');
    });
    
    it('truncates external evidence for Pro', () => {
      const longText = 'External '.repeat(200); // Very long
      const item: EvidenceItem = {
        text: longText,
        label: 'Wikipedia',
        is_external: true,
      };
      
      const redacted = redactEvidenceItem(item, ROLE_PRO);
      expect(redacted).not.toBeNull();
      expect(redacted!.text.length).toBeLessThanOrEqual(800);
      expect(redacted!.text.endsWith('...')).toBe(true);
    });
    
    it('strips chunk_id and memory_id from external evidence', () => {
      const item: EvidenceItem = {
        text: 'External text',
        chunk_id: 'chunk-123',
        memory_id: 'mem-456',
        is_external: true,
      };
      
      const redacted = redactEvidenceItem(item, ROLE_PRO);
      expect(redacted?.chunk_id).toBeUndefined();
      expect(redacted?.memory_id).toBeUndefined();
    });
    
    it('preserves metadata for internal evidence', () => {
      const item: EvidenceItem = {
        text: 'Internal text',
        chunk_id: 'chunk-123',
        memory_id: 'mem-456',
        score: 0.95,
      };
      
      const redacted = redactEvidenceItem(item, ROLE_GENERAL);
      expect(redacted?.chunk_id).toBe('chunk-123');
      expect(redacted?.memory_id).toBe('mem-456');
      expect(redacted?.score).toBe(0.95);
    });
  });
  
  describe('redactEvidence', () => {
    it('strips all external evidence for General', () => {
      const redacted = redactEvidence(mockMixedEvidence, ROLE_GENERAL);
      
      expect(redacted).toHaveLength(1); // Only internal
      expect(redacted![0].text).toContain('Internal evidence');
    });
    
    it('truncates external evidence for Pro', () => {
      const redacted = redactEvidence(mockExternalEvidence, ROLE_PRO);
      
      expect(redacted).toHaveLength(2);
      redacted!.forEach(item => {
        expect(item.text.length).toBeLessThanOrEqual(1200); // arXiv max for Pro
      });
    });
    
    it('handles empty evidence array', () => {
      const redacted = redactEvidence([], ROLE_GENERAL);
      expect(redacted).toEqual([]);
    });
    
    it('handles undefined evidence', () => {
      const redacted = redactEvidence(undefined, ROLE_GENERAL);
      expect(redacted).toBeUndefined();
    });
    
    it('returns undefined if all evidence filtered out', () => {
      const redacted = redactEvidence(mockExternalEvidence, ROLE_GENERAL);
      expect(redacted).toBeUndefined();
    });
  });
  
  describe('isEvidenceRedacted', () => {
    it('returns false if external evidence present for General', () => {
      expect(isEvidenceRedacted(mockExternalEvidence, ROLE_GENERAL)).toBe(false);
    });
    
    it('returns false if external snippet too long', () => {
      const longEvidence: EvidenceItem[] = [{
        text: 'A'.repeat(1000),
        label: 'Wikipedia',
        is_external: true,
      }];
      
      expect(isEvidenceRedacted(longEvidence, ROLE_PRO)).toBe(false);
    });
    
    it('returns true if properly redacted', () => {
      const redacted = redactEvidence(mockMixedEvidence, ROLE_GENERAL);
      expect(isEvidenceRedacted(redacted, ROLE_GENERAL)).toBe(true);
    });
  });
  
  // ==========================================================================
  // Compare Summary Redaction Tests
  // ==========================================================================
  
  describe('redactCompareSummary', () => {
    it('preserves stance text', () => {
      const redacted = redactCompareSummary(mockChatResponse.compare_summary, ROLE_GENERAL);
      
      expect(redacted?.stance_a).toBe('Position A');
      expect(redacted?.stance_b).toBe('Position B');
    });
    
    it('redacts evidence arrays for General', () => {
      const redacted = redactCompareSummary(mockChatResponse.compare_summary, ROLE_GENERAL);
      
      // evidence_a is internal, should be kept
      expect(redacted?.evidence_a).toHaveLength(1);
      
      // evidence_b is external, should be stripped
      expect(redacted?.evidence_b).toBeUndefined();
    });
    
    it('handles undefined compare summary', () => {
      const redacted = redactCompareSummary(undefined, ROLE_GENERAL);
      expect(redacted).toBeUndefined();
    });
  });
  
  // ==========================================================================
  // Full Response Redaction Tests
  // ==========================================================================
  
  describe('redactChatResponse', () => {
    it('applies all redaction rules for General', () => {
      const redacted = redactChatResponse(mockChatResponse, ROLE_GENERAL);
      
      // Ledger limited to 4 lines
      expect(redacted.process_trace_summary).toHaveLength(4);
      
      // External evidence stripped
      expect(redacted.evidence).toHaveLength(1);
      
      // Compare summary redacted
      expect(redacted.compare_summary?.evidence_b).toBeUndefined();
      
      // Role tracked
      expect(redacted.role_applied).toBe(ROLE_GENERAL);
    });
    
    it('applies minimal redaction for Pro', () => {
      const redacted = redactChatResponse(mockChatResponse, ROLE_PRO);
      
      // Ledger not limited
      expect(redacted.process_trace_summary!.length).toBeGreaterThan(4);
      
      // External evidence truncated but kept
      expect(redacted.evidence!.length).toBeGreaterThan(1);
    });
    
    it('preserves answer content', () => {
      const redacted = redactChatResponse(mockChatResponse, ROLE_GENERAL);
      expect(redacted.answer).toBe('The answer is 42.');
    });
  });
  
  // ==========================================================================
  // Validation Tests
  // ==========================================================================
  
  describe('validateRedaction', () => {
    it('returns true for properly redacted response', () => {
      const redacted = redactChatResponse(mockChatResponse, ROLE_GENERAL);
      expect(validateRedaction(redacted, ROLE_GENERAL)).toBe(true);
    });
    
    it('returns false if server failed to redact ledger', () => {
      const badResponse = { ...mockChatResponse };
      expect(validateRedaction(badResponse, ROLE_GENERAL)).toBe(false);
    });
    
    it('returns false if server failed to redact evidence', () => {
      const badResponse: ChatResponse = {
        ...mockChatResponse,
        process_trace_summary: mockLongTrace.slice(0, 4), // Ledger OK
        evidence: mockExternalEvidence, // Evidence NOT OK for General
      };
      
      expect(validateRedaction(badResponse, ROLE_GENERAL)).toBe(false);
    });
    
    it('returns false if server failed to redact compare', () => {
      const badResponse: ChatResponse = {
        ...mockChatResponse,
        process_trace_summary: mockLongTrace.slice(0, 4),
        evidence: mockInternalEvidence,
        compare_summary: {
          stance_a: 'A',
          stance_b: 'B',
          evidence_a: mockInternalEvidence,
          evidence_b: mockExternalEvidence, // NOT OK for General
        },
      };
      
      expect(validateRedaction(badResponse, ROLE_GENERAL)).toBe(false);
    });
  });
  
  // ==========================================================================
  // Telemetry Tests
  // ==========================================================================
  
  describe('reportRedactionFailure', () => {
    it('tracks telemetry event', () => {
      reportRedactionFailure(mockChatResponse, ROLE_GENERAL, 'ledger');
      
      expect(mockAnalyticsCalls).toHaveLength(1);
      expect(mockAnalyticsCalls[0].event).toBe('redaction.client_side_applied');
      expect(mockAnalyticsCalls[0].data.role).toBe(ROLE_GENERAL);
      expect(mockAnalyticsCalls[0].data.failureType).toBe('ledger');
    });
    
    it('includes timestamp', () => {
      reportRedactionFailure(mockChatResponse, ROLE_GENERAL, 'evidence');
      
      expect(mockAnalyticsCalls[0].data.timestamp).toBeDefined();
    });
  });
  
  describe('redactChatResponseWithTelemetry', () => {
    it('applies redaction', () => {
      const redacted = redactChatResponseWithTelemetry(mockChatResponse, ROLE_GENERAL);
      
      expect(redacted.process_trace_summary).toHaveLength(4);
      expect(redacted.evidence).toHaveLength(1);
    });
    
    it('reports telemetry if server failed', () => {
      redactChatResponseWithTelemetry(mockChatResponse, ROLE_GENERAL);
      
      // Should detect server failure and report
      expect(mockAnalyticsCalls.length).toBeGreaterThan(0);
    });
    
    it('does not report if server redacted correctly', () => {
      const properlyRedacted = redactChatResponse(mockChatResponse, ROLE_GENERAL);
      
      // Clear previous calls
      mockAnalyticsCalls = [];
      
      redactChatResponseWithTelemetry(properlyRedacted, ROLE_GENERAL);
      
      // No new telemetry events
      expect(mockAnalyticsCalls).toHaveLength(0);
    });
  });
  
  // ==========================================================================
  // Server Misbehavior Scenarios (Acceptance Criteria)
  // ==========================================================================
  
  describe('Server Misbehavior Protection', () => {
    it('protects General from unredacted long ledger', () => {
      // Server misbehaves: sends 8 ledger lines to General
      const badResponse: ChatResponse = {
        answer: 'Answer',
        process_trace_summary: mockLongTrace, // 8 lines, should be 4
      };
      
      const redacted = redactChatResponse(badResponse, ROLE_GENERAL);
      
      // Client-side redaction saves the day
      expect(redacted.process_trace_summary).toHaveLength(4);
    });
    
    it('protects General from unredacted prompts', () => {
      // Server misbehaves: sends prompts to General
      const badResponse: ChatResponse = {
        answer: 'Answer',
        process_trace_summary: [
          { step: 'generate', prompt: 'SENSITIVE_PROMPT' },
        ],
      };
      
      const redacted = redactChatResponse(badResponse, ROLE_GENERAL);
      
      // Client strips prompt
      expect(redacted.process_trace_summary![0].prompt).toBeUndefined();
    });
    
    it('protects General from external evidence snippets', () => {
      // Server misbehaves: sends external evidence to General
      const badResponse: ChatResponse = {
        answer: 'Answer',
        evidence: mockExternalEvidence,
      };
      
      const redacted = redactChatResponse(badResponse, ROLE_GENERAL);
      
      // Client strips all external
      expect(redacted.evidence).toBeUndefined();
    });
    
    it('protects General from long external snippets in compare', () => {
      // Server misbehaves: sends very long external snippets
      const veryLongText = 'External '.repeat(500); // Way too long
      const badResponse: ChatResponse = {
        answer: 'Answer',
        compare_summary: {
          stance_a: 'A',
          stance_b: 'B',
          evidence_a: [],
          evidence_b: [{
            text: veryLongText,
            label: 'Wikipedia',
            is_external: true,
          }],
        },
      };
      
      const redacted = redactChatResponse(badResponse, ROLE_GENERAL);
      
      // Client strips external evidence for General
      expect(redacted.compare_summary?.evidence_b).toBeUndefined();
    });
    
    it('enforces truncation for Pro if server sends too-long snippets', () => {
      // Server misbehaves: sends ultra-long snippet even to Pro
      const ultraLongText = 'A'.repeat(10000);
      const badResponse: ChatResponse = {
        answer: 'Answer',
        evidence: [{
          text: ultraLongText,
          label: 'Wikipedia',
          is_external: true,
        }],
      };
      
      const redacted = redactChatResponse(badResponse, ROLE_PRO);
      
      // Client enforces Pro's policy (800 chars for Wikipedia)
      expect(redacted.evidence![0].text.length).toBe(800);
      expect(redacted.evidence![0].text.endsWith('...')).toBe(true);
    });
    
    it('validates and reports all server failures', () => {
      // Server completely fails redaction
      const badResponse: ChatResponse = {
        answer: 'Answer',
        process_trace_summary: mockLongTrace, // Too long
        evidence: mockExternalEvidence, // External not allowed
        compare_summary: {
          stance_a: 'A',
          stance_b: 'B',
          evidence_a: [],
          evidence_b: mockExternalEvidence, // External not allowed
        },
      };
      
      redactChatResponseWithTelemetry(badResponse, ROLE_GENERAL);
      
      // Should report all 3 failure types
      expect(mockAnalyticsCalls.length).toBeGreaterThanOrEqual(3);
      
      const failureTypes = mockAnalyticsCalls.map(call => call.data.failureType);
      expect(failureTypes).toContain('ledger');
      expect(failureTypes).toContain('evidence');
      expect(failureTypes).toContain('compare');
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('General never sees raw external snippets longer than policy', () => {
      // Simulate server sending long external snippets
      const longSnippets: EvidenceItem[] = [
        {
          text: 'A'.repeat(1000), // Way over 480 limit
          label: 'Wikipedia',
          is_external: true,
        },
        {
          text: 'B'.repeat(2000), // Way over 640 limit
          label: 'arXiv',
          is_external: true,
        },
      ];
      
      const response: ChatResponse = {
        answer: 'Answer',
        evidence: longSnippets,
      };
      
      // Client-side redaction
      const redacted = redactChatResponse(response, ROLE_GENERAL);
      
      // ALL external evidence stripped for General
      expect(redacted.evidence).toBeUndefined();
    });
    
    it('verifies redaction applied even if server misbehaves', () => {
      // Server sends completely unredacted response
      const unredactedResponse: ChatResponse = {
        answer: 'Unredacted answer',
        process_trace_summary: mockLongTrace, // 8 lines
        evidence: mockMixedEvidence, // Has external
        compare_summary: {
          stance_a: 'A',
          stance_b: 'B',
          evidence_a: mockInternalEvidence,
          evidence_b: mockExternalEvidence, // External
        },
      };
      
      // Validation should fail
      expect(validateRedaction(unredactedResponse, ROLE_GENERAL)).toBe(false);
      
      // But client-side redaction fixes it
      const redacted = redactChatResponse(unredactedResponse, ROLE_GENERAL);
      
      // Now validation passes
      expect(validateRedaction(redacted, ROLE_GENERAL)).toBe(true);
      
      // Verify specific redactions
      expect(redacted.process_trace_summary).toHaveLength(4);
      expect(redacted.evidence).toHaveLength(1); // Only internal
      expect(redacted.evidence![0].is_external).toBeFalsy();
      expect(redacted.compare_summary?.evidence_b).toBeUndefined();
    });
    
    it('tests all redaction rules for General', () => {
      const response = redactChatResponse(mockChatResponse, ROLE_GENERAL);
      
      // Ledger: max 4 lines
      expect(response.process_trace_summary!.length).toBeLessThanOrEqual(4);
      
      // Ledger: no prompts
      response.process_trace_summary!.forEach(line => {
        expect(line.prompt).toBeUndefined();
      });
      
      // Ledger: no provenance
      response.process_trace_summary!.forEach(line => {
        expect(line.raw_provenance).toBeUndefined();
      });
      
      // Evidence: no external
      response.evidence?.forEach(item => {
        expect(item.is_external).toBeFalsy();
      });
      
      // Compare: no external
      response.compare_summary?.evidence_a?.forEach(item => {
        expect(item.is_external).toBeFalsy();
      });
      response.compare_summary?.evidence_b?.forEach(item => {
        expect(item.is_external).toBeFalsy();
      });
    });
  });
});
