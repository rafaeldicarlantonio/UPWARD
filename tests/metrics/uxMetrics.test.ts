/**
 * UX Metrics Tests
 * 
 * Comprehensive tests for metrics system including one-shot behavior and payload validation.
 */

import {
  MetricsClient,
  MetricEvent,
  initMetrics,
  getMetrics,
  LedgerExpandProps,
  CompareRunProps,
  HypothesisPromoteProps,
  AuraProjectProps,
  ContradictionTooltipProps,
  AnalyticsProvider,
} from '../../app/lib/metrics';
import { ROLE_GENERAL, ROLE_PRO, ROLE_ANALYTICS } from '../../app/lib/roles';

// ============================================================================
// Mock Analytics Provider
// ============================================================================

class MockAnalyticsProvider implements AnalyticsProvider {
  public events: Array<{ event: string; properties: Record<string, any> }> = [];
  
  track(event: string, properties: Record<string, any>): void {
    this.events.push({ event, properties });
  }
  
  reset(): void {
    this.events = [];
  }
  
  getEvent(index: number) {
    return this.events[index];
  }
  
  getEventCount(): number {
    return this.events.length;
  }
  
  findEvent(eventName: string) {
    return this.events.find(e => e.event === eventName);
  }
  
  findEvents(eventName: string) {
    return this.events.filter(e => e.event === eventName);
  }
}

// ============================================================================
// Test Setup
// ============================================================================

let mockProvider: MockAnalyticsProvider;
let metricsClient: MetricsClient;

beforeEach(() => {
  mockProvider = new MockAnalyticsProvider();
  metricsClient = new MetricsClient({
    provider: mockProvider,
    debug: false,
    oneShotEnabled: true,
  });
});

afterEach(() => {
  metricsClient.resetOneShot();
  mockProvider.reset();
});

// ============================================================================
// Tests
// ============================================================================

describe('Metrics System', () => {
  // ==========================================================================
  // One-Shot Behavior Tests
  // ==========================================================================
  
  describe('One-Shot Behavior', () => {
    it('prevents duplicate ledger expand events', () => {
      const props = {
        traceLinesInSummary: 4,
        traceLinesInFull: 8,
        success: true,
      };
      
      // First call should succeed
      const result1 = metricsClient.trackLedgerExpand(ROLE_PRO, props, 'test-123');
      expect(result1).toBe(true);
      expect(mockProvider.getEventCount()).toBe(1);
      
      // Second call should be blocked
      const result2 = metricsClient.trackLedgerExpand(ROLE_PRO, props, 'test-123');
      expect(result2).toBe(false);
      expect(mockProvider.getEventCount()).toBe(1); // Still 1
    });
    
    it('prevents duplicate compare run events', () => {
      const props = {
        allowExternal: true,
        internalEvidenceA: 3,
        internalEvidenceB: 2,
        externalEvidenceB: 1,
        success: true,
      };
      
      const result1 = metricsClient.trackCompareRun(ROLE_PRO, props, 'compare-1');
      const result2 = metricsClient.trackCompareRun(ROLE_PRO, props, 'compare-1');
      
      expect(result1).toBe(true);
      expect(result2).toBe(false);
      expect(mockProvider.getEventCount()).toBe(1);
    });
    
    it('prevents duplicate hypothesis promote events', () => {
      const props = {
        evidenceCount: 5,
        score: 0.95,
        persisted: true,
        success: true,
      };
      
      const result1 = metricsClient.trackHypothesisPromote(ROLE_ANALYTICS, props, 'hyp-1');
      const result2 = metricsClient.trackHypothesisPromote(ROLE_ANALYTICS, props, 'hyp-1');
      
      expect(result1).toBe(true);
      expect(result2).toBe(false);
      expect(mockProvider.getEventCount()).toBe(1);
    });
    
    it('prevents duplicate AURA propose events', () => {
      const props = {
        hypothesisId: 'hyp-123',
        hypothesisPreLinked: true,
        starterTaskCount: 3,
        success: true,
      };
      
      const result1 = metricsClient.trackAuraPropose(ROLE_PRO, props, 'aura-1');
      const result2 = metricsClient.trackAuraPropose(ROLE_PRO, props, 'aura-1');
      
      expect(result1).toBe(true);
      expect(result2).toBe(false);
      expect(mockProvider.getEventCount()).toBe(1);
    });
    
    it('prevents duplicate contradiction tooltip events', () => {
      const props = {
        contradictionCount: 2,
        highestSeverity: 'high' as const,
        evidenceAnchor: 'evidence-1',
      };
      
      const result1 = metricsClient.trackContradictionTooltipOpen(ROLE_GENERAL, props, 'badge-1');
      const result2 = metricsClient.trackContradictionTooltipOpen(ROLE_GENERAL, props, 'badge-1');
      
      expect(result1).toBe(true);
      expect(result2).toBe(false);
      expect(mockProvider.getEventCount()).toBe(1);
    });
    
    it('allows same event with different instance IDs', () => {
      const props = {
        traceLinesInSummary: 4,
        success: true,
      };
      
      const result1 = metricsClient.trackLedgerExpand(ROLE_PRO, props, 'instance-1');
      const result2 = metricsClient.trackLedgerExpand(ROLE_PRO, props, 'instance-2');
      
      expect(result1).toBe(true);
      expect(result2).toBe(true);
      expect(mockProvider.getEventCount()).toBe(2);
    });
    
    it('allows same event after reset', () => {
      const props = {
        traceLinesInSummary: 4,
        success: true,
      };
      
      metricsClient.trackLedgerExpand(ROLE_PRO, props, 'test-123');
      expect(mockProvider.getEventCount()).toBe(1);
      
      // Reset
      metricsClient.resetOneShot(MetricEvent.LEDGER_EXPAND, 'test-123');
      
      // Should work again
      metricsClient.trackLedgerExpand(ROLE_PRO, props, 'test-123');
      expect(mockProvider.getEventCount()).toBe(2);
    });
    
    it('tracks multiple different events', () => {
      metricsClient.trackLedgerExpand(ROLE_PRO, { traceLinesInSummary: 4, success: true }, 'ledger-1');
      metricsClient.trackCompareRun(ROLE_PRO, { allowExternal: true, internalEvidenceA: 1, internalEvidenceB: 1, success: true }, 'compare-1');
      metricsClient.trackHypothesisPromote(ROLE_PRO, { evidenceCount: 5, persisted: true, success: true }, 'hyp-1');
      
      expect(mockProvider.getEventCount()).toBe(3);
    });
  });
  
  // ==========================================================================
  // Payload Shape Tests
  // ==========================================================================
  
  describe('Payload Shapes', () => {
    it('ledger expand has correct shape', () => {
      metricsClient.trackLedgerExpand(ROLE_PRO, {
        traceLinesInSummary: 4,
        traceLinesInFull: 8,
        messageId: 'msg-123',
        success: true,
      }, 'test-1');
      
      const event = mockProvider.getEvent(0);
      expect(event.event).toBe(MetricEvent.LEDGER_EXPAND);
      
      const props = event.properties as LedgerExpandProps;
      expect(props).toHaveProperty('role');
      expect(props).toHaveProperty('timestamp');
      expect(props).toHaveProperty('traceLinesInSummary');
      expect(props).toHaveProperty('traceLinesInFull');
      expect(props).toHaveProperty('messageId');
      expect(props).toHaveProperty('success');
      
      expect(props.role).toBe(ROLE_PRO);
      expect(props.traceLinesInSummary).toBe(4);
      expect(props.traceLinesInFull).toBe(8);
      expect(props.messageId).toBe('msg-123');
      expect(props.success).toBe(true);
      expect(typeof props.timestamp).toBe('string');
    });
    
    it('compare run has correct shape', () => {
      metricsClient.trackCompareRun(ROLE_ANALYTICS, {
        allowExternal: true,
        internalEvidenceA: 3,
        internalEvidenceB: 2,
        externalEvidenceB: 1,
        success: true,
        responseTimeMs: 1500,
      }, 'test-1');
      
      const event = mockProvider.getEvent(0);
      expect(event.event).toBe(MetricEvent.COMPARE_RUN);
      
      const props = event.properties as CompareRunProps;
      expect(props).toHaveProperty('role');
      expect(props).toHaveProperty('timestamp');
      expect(props).toHaveProperty('allowExternal');
      expect(props).toHaveProperty('internalEvidenceA');
      expect(props).toHaveProperty('internalEvidenceB');
      expect(props).toHaveProperty('externalEvidenceB');
      expect(props).toHaveProperty('success');
      expect(props).toHaveProperty('responseTimeMs');
      
      expect(props.role).toBe(ROLE_ANALYTICS);
      expect(props.allowExternal).toBe(true);
      expect(props.internalEvidenceA).toBe(3);
      expect(props.internalEvidenceB).toBe(2);
      expect(props.externalEvidenceB).toBe(1);
      expect(props.success).toBe(true);
      expect(props.responseTimeMs).toBe(1500);
    });
    
    it('hypothesis promote has correct shape', () => {
      metricsClient.trackHypothesisPromote(ROLE_PRO, {
        evidenceCount: 5,
        score: 0.95,
        persisted: true,
        success: true,
        hypothesisId: 'hyp-123',
      }, 'test-1');
      
      const event = mockProvider.getEvent(0);
      expect(event.event).toBe(MetricEvent.HYPOTHESIS_PROMOTE);
      
      const props = event.properties as HypothesisPromoteProps;
      expect(props).toHaveProperty('role');
      expect(props).toHaveProperty('timestamp');
      expect(props).toHaveProperty('evidenceCount');
      expect(props).toHaveProperty('score');
      expect(props).toHaveProperty('persisted');
      expect(props).toHaveProperty('success');
      expect(props).toHaveProperty('hypothesisId');
      
      expect(props.role).toBe(ROLE_PRO);
      expect(props.evidenceCount).toBe(5);
      expect(props.score).toBe(0.95);
      expect(props.persisted).toBe(true);
      expect(props.success).toBe(true);
      expect(props.hypothesisId).toBe('hyp-123');
    });
    
    it('AURA propose has correct shape', () => {
      metricsClient.trackAuraPropose(ROLE_ANALYTICS, {
        hypothesisId: 'hyp-123',
        hypothesisPreLinked: true,
        starterTaskCount: 3,
        success: true,
        projectId: 'proj-456',
      }, 'test-1');
      
      const event = mockProvider.getEvent(0);
      expect(event.event).toBe(MetricEvent.AURA_PROPOSE);
      
      const props = event.properties as AuraProjectProps;
      expect(props).toHaveProperty('role');
      expect(props).toHaveProperty('timestamp');
      expect(props).toHaveProperty('hypothesisId');
      expect(props).toHaveProperty('hypothesisPreLinked');
      expect(props).toHaveProperty('starterTaskCount');
      expect(props).toHaveProperty('success');
      expect(props).toHaveProperty('projectId');
      
      expect(props.role).toBe(ROLE_ANALYTICS);
      expect(props.hypothesisId).toBe('hyp-123');
      expect(props.hypothesisPreLinked).toBe(true);
      expect(props.starterTaskCount).toBe(3);
      expect(props.success).toBe(true);
      expect(props.projectId).toBe('proj-456');
    });
    
    it('contradiction tooltip has correct shape', () => {
      metricsClient.trackContradictionTooltipOpen(ROLE_GENERAL, {
        contradictionCount: 2,
        highestSeverity: 'high',
        evidenceAnchor: 'evidence-1',
      }, 'test-1');
      
      const event = mockProvider.getEvent(0);
      expect(event.event).toBe(MetricEvent.CONTRADICTION_TOOLTIP_OPEN);
      
      const props = event.properties as ContradictionTooltipProps;
      expect(props).toHaveProperty('role');
      expect(props).toHaveProperty('timestamp');
      expect(props).toHaveProperty('contradictionCount');
      expect(props).toHaveProperty('highestSeverity');
      expect(props).toHaveProperty('evidenceAnchor');
      
      expect(props.role).toBe(ROLE_GENERAL);
      expect(props.contradictionCount).toBe(2);
      expect(props.highestSeverity).toBe('high');
      expect(props.evidenceAnchor).toBe('evidence-1');
    });
  });
  
  // ==========================================================================
  // Role Tracking Tests
  // ==========================================================================
  
  describe('Role Tracking', () => {
    it('includes role in all events', () => {
      metricsClient.trackLedgerExpand(ROLE_GENERAL, { traceLinesInSummary: 4, success: true }, '1');
      metricsClient.trackCompareRun(ROLE_PRO, { allowExternal: true, internalEvidenceA: 1, internalEvidenceB: 1, success: true }, '2');
      metricsClient.trackHypothesisPromote(ROLE_ANALYTICS, { evidenceCount: 5, persisted: true, success: true }, '3');
      
      expect(mockProvider.getEvent(0).properties.role).toBe(ROLE_GENERAL);
      expect(mockProvider.getEvent(1).properties.role).toBe(ROLE_PRO);
      expect(mockProvider.getEvent(2).properties.role).toBe(ROLE_ANALYTICS);
    });
    
    it('tracks different roles separately', () => {
      const props = {
        traceLinesInSummary: 4,
        success: true,
      };
      
      metricsClient.trackLedgerExpand(ROLE_GENERAL, props, 'test-1');
      metricsClient.trackLedgerExpand(ROLE_PRO, props, 'test-2');
      
      expect(mockProvider.getEventCount()).toBe(2);
      expect(mockProvider.getEvent(0).properties.role).toBe(ROLE_GENERAL);
      expect(mockProvider.getEvent(1).properties.role).toBe(ROLE_PRO);
    });
  });
  
  // ==========================================================================
  // Count Tracking Tests
  // ==========================================================================
  
  describe('Count Tracking', () => {
    it('tracks trace line counts in ledger expand', () => {
      metricsClient.trackLedgerExpand(ROLE_PRO, {
        traceLinesInSummary: 4,
        traceLinesInFull: 8,
        success: true,
      }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties as LedgerExpandProps;
      expect(props.traceLinesInSummary).toBe(4);
      expect(props.traceLinesInFull).toBe(8);
    });
    
    it('tracks evidence counts in compare run', () => {
      metricsClient.trackCompareRun(ROLE_PRO, {
        allowExternal: true,
        internalEvidenceA: 3,
        internalEvidenceB: 2,
        externalEvidenceB: 1,
        success: true,
      }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties as CompareRunProps;
      expect(props.internalEvidenceA).toBe(3);
      expect(props.internalEvidenceB).toBe(2);
      expect(props.externalEvidenceB).toBe(1);
    });
    
    it('tracks evidence count in hypothesis promote', () => {
      metricsClient.trackHypothesisPromote(ROLE_PRO, {
        evidenceCount: 10,
        persisted: true,
        success: true,
      }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties as HypothesisPromoteProps;
      expect(props.evidenceCount).toBe(10);
    });
    
    it('tracks starter task count in AURA propose', () => {
      metricsClient.trackAuraPropose(ROLE_PRO, {
        hypothesisPreLinked: true,
        starterTaskCount: 5,
        success: true,
      }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties as AuraProjectProps;
      expect(props.starterTaskCount).toBe(5);
    });
    
    it('tracks contradiction count in tooltip open', () => {
      metricsClient.trackContradictionTooltipOpen(ROLE_GENERAL, {
        contradictionCount: 3,
        highestSeverity: 'medium',
      }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties as ContradictionTooltipProps;
      expect(props.contradictionCount).toBe(3);
    });
  });
  
  // ==========================================================================
  // Timestamp Tests
  // ==========================================================================
  
  describe('Timestamps', () => {
    it('includes ISO timestamp in all events', () => {
      metricsClient.trackLedgerExpand(ROLE_PRO, { traceLinesInSummary: 4, success: true }, '1');
      
      const props = mockProvider.getEvent(0).properties;
      expect(props.timestamp).toBeDefined();
      expect(typeof props.timestamp).toBe('string');
      
      // Verify ISO format
      const timestamp = new Date(props.timestamp);
      expect(timestamp.toISOString()).toBe(props.timestamp);
    });
    
    it('timestamps are recent', () => {
      const before = Date.now();
      metricsClient.trackLedgerExpand(ROLE_PRO, { traceLinesInSummary: 4, success: true }, '1');
      const after = Date.now();
      
      const props = mockProvider.getEvent(0).properties;
      const eventTime = new Date(props.timestamp).getTime();
      
      expect(eventTime).toBeGreaterThanOrEqual(before);
      expect(eventTime).toBeLessThanOrEqual(after);
    });
  });
  
  // ==========================================================================
  // Error Tracking Tests
  // ==========================================================================
  
  describe('Error Tracking', () => {
    it('tracks errors in ledger expand', () => {
      metricsClient.trackLedgerExpand(ROLE_PRO, {
        traceLinesInSummary: 4,
        success: false,
        error: 'Network timeout',
      }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties as LedgerExpandProps;
      expect(props.success).toBe(false);
      expect(props.error).toBe('Network timeout');
    });
    
    it('tracks errors in compare run', () => {
      metricsClient.trackCompareRun(ROLE_PRO, {
        allowExternal: true,
        internalEvidenceA: 1,
        internalEvidenceB: 1,
        success: false,
        error: 'API error',
      }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties as CompareRunProps;
      expect(props.success).toBe(false);
      expect(props.error).toBe('API error');
    });
  });
  
  // ==========================================================================
  // Configuration Tests
  // ==========================================================================
  
  describe('Configuration', () => {
    it('respects oneShotEnabled=false', () => {
      const client = new MetricsClient({
        provider: mockProvider,
        oneShotEnabled: false,
      });
      
      const props = { traceLinesInSummary: 4, success: true };
      
      client.trackLedgerExpand(ROLE_PRO, props, 'test-1');
      client.trackLedgerExpand(ROLE_PRO, props, 'test-1');
      
      // Both should fire
      expect(mockProvider.getEventCount()).toBe(2);
    });
    
    it('includes sessionId when provided', () => {
      const client = new MetricsClient({
        provider: mockProvider,
        sessionId: 'session-123',
      });
      
      client.trackLedgerExpand(ROLE_PRO, { traceLinesInSummary: 4, success: true }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties;
      expect(props.sessionId).toBe('session-123');
    });
    
    it('includes userId when provided', () => {
      const client = new MetricsClient({
        provider: mockProvider,
        userId: 'user-456',
      });
      
      client.trackLedgerExpand(ROLE_PRO, { traceLinesInSummary: 4, success: true }, 'test-1');
      
      const props = mockProvider.getEvent(0).properties;
      expect(props.userId).toBe('user-456');
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('events fire exactly once per action', () => {
      const props = { traceLinesInSummary: 4, success: true };
      
      // Fire same event 5 times
      for (let i = 0; i < 5; i++) {
        metricsClient.trackLedgerExpand(ROLE_PRO, props, 'test-instance');
      }
      
      // Should only fire once
      expect(mockProvider.getEventCount()).toBe(1);
    });
    
    it('tests assert payload shapes for all events', () => {
      // Ledger expand
      metricsClient.trackLedgerExpand(ROLE_PRO, {
        traceLinesInSummary: 4,
        traceLinesInFull: 8,
        messageId: 'msg-1',
        success: true,
      }, '1');
      
      const ledgerEvent = mockProvider.findEvent(MetricEvent.LEDGER_EXPAND);
      expect(ledgerEvent).toBeDefined();
      expect(ledgerEvent!.properties).toMatchObject({
        role: ROLE_PRO,
        traceLinesInSummary: 4,
        traceLinesInFull: 8,
        messageId: 'msg-1',
        success: true,
      });
      
      // Compare run
      metricsClient.trackCompareRun(ROLE_ANALYTICS, {
        allowExternal: true,
        internalEvidenceA: 3,
        internalEvidenceB: 2,
        externalEvidenceB: 1,
        success: true,
      }, '2');
      
      const compareEvent = mockProvider.findEvent(MetricEvent.COMPARE_RUN);
      expect(compareEvent).toBeDefined();
      expect(compareEvent!.properties).toMatchObject({
        role: ROLE_ANALYTICS,
        allowExternal: true,
        internalEvidenceA: 3,
        internalEvidenceB: 2,
        externalEvidenceB: 1,
        success: true,
      });
      
      // Hypothesis promote
      metricsClient.trackHypothesisPromote(ROLE_PRO, {
        evidenceCount: 5,
        score: 0.95,
        persisted: true,
        success: true,
        hypothesisId: 'hyp-1',
      }, '3');
      
      const hypothesisEvent = mockProvider.findEvent(MetricEvent.HYPOTHESIS_PROMOTE);
      expect(hypothesisEvent).toBeDefined();
      expect(hypothesisEvent!.properties).toMatchObject({
        role: ROLE_PRO,
        evidenceCount: 5,
        score: 0.95,
        persisted: true,
        success: true,
        hypothesisId: 'hyp-1',
      });
      
      // AURA propose
      metricsClient.trackAuraPropose(ROLE_ANALYTICS, {
        hypothesisId: 'hyp-1',
        hypothesisPreLinked: true,
        starterTaskCount: 3,
        success: true,
        projectId: 'proj-1',
      }, '4');
      
      const auraEvent = mockProvider.findEvent(MetricEvent.AURA_PROPOSE);
      expect(auraEvent).toBeDefined();
      expect(auraEvent!.properties).toMatchObject({
        role: ROLE_ANALYTICS,
        hypothesisId: 'hyp-1',
        hypothesisPreLinked: true,
        starterTaskCount: 3,
        success: true,
        projectId: 'proj-1',
      });
      
      // Contradiction tooltip
      metricsClient.trackContradictionTooltipOpen(ROLE_GENERAL, {
        contradictionCount: 2,
        highestSeverity: 'high',
        evidenceAnchor: 'evidence-1',
      }, '5');
      
      const tooltipEvent = mockProvider.findEvent(MetricEvent.CONTRADICTION_TOOLTIP_OPEN);
      expect(tooltipEvent).toBeDefined();
      expect(tooltipEvent!.properties).toMatchObject({
        role: ROLE_GENERAL,
        contradictionCount: 2,
        highestSeverity: 'high',
        evidenceAnchor: 'evidence-1',
      });
    });
  });
});
