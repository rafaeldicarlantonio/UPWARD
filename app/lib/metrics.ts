/**
 * Metrics Library
 * 
 * Core metrics/telemetry system for tracking UI actions with one-shot guarantees.
 * Ensures events fire exactly once per action and includes structured payload validation.
 */

import { Role } from './roles';

// ============================================================================
// Types
// ============================================================================

/**
 * Base event properties included in all events
 */
export interface BaseEventProps {
  /** User role at time of event */
  role: Role;
  
  /** ISO timestamp */
  timestamp: string;
  
  /** Session ID (if available) */
  sessionId?: string;
  
  /** User ID (if available) */
  userId?: string;
}

/**
 * Ledger expand event properties
 */
export interface LedgerExpandProps extends BaseEventProps {
  /** Number of trace lines in summary */
  traceLinesInSummary: number;
  
  /** Number of trace lines in full trace (after expand) */
  traceLinesInFull?: number;
  
  /** Message ID */
  messageId?: string;
  
  /** Whether expand was successful */
  success: boolean;
  
  /** Error message if failed */
  error?: string;
}

/**
 * Compare run event properties
 */
export interface CompareRunProps extends BaseEventProps {
  /** Whether external sources were allowed */
  allowExternal: boolean;
  
  /** Number of internal evidence items in stance A */
  internalEvidenceA: number;
  
  /** Number of internal evidence items in stance B */
  internalEvidenceB: number;
  
  /** Number of external evidence items in stance B (if allowed) */
  externalEvidenceB?: number;
  
  /** Whether compare was successful */
  success: boolean;
  
  /** Error message if failed */
  error?: string;
  
  /** Response time in milliseconds */
  responseTimeMs?: number;
}

/**
 * Hypothesis promote event properties
 */
export interface HypothesisPromoteProps extends BaseEventProps {
  /** Number of evidence items used */
  evidenceCount: number;
  
  /** Hypothesis score (0-1) */
  score?: number;
  
  /** Whether hypothesis was persisted (201) or threshold-not-met (202) */
  persisted: boolean;
  
  /** Whether submission was successful */
  success: boolean;
  
  /** Error message if failed */
  error?: string;
  
  /** Hypothesis ID if persisted */
  hypothesisId?: string;
}

/**
 * AURA project propose event properties
 */
export interface AuraProjectProps extends BaseEventProps {
  /** Linked hypothesis ID (pre-linked or selected) */
  hypothesisId?: string;
  
  /** Whether hypothesis was pre-linked */
  hypothesisPreLinked: boolean;
  
  /** Number of starter tasks */
  starterTaskCount: number;
  
  /** Whether proposal was successful */
  success: boolean;
  
  /** Error message if failed */
  error?: string;
  
  /** Project ID if created */
  projectId?: string;
}

/**
 * Contradiction tooltip open event properties
 */
export interface ContradictionTooltipProps extends BaseEventProps {
  /** Number of contradictions in badge */
  contradictionCount: number;
  
  /** Highest severity in set */
  highestSeverity: 'high' | 'medium' | 'low';
  
  /** Evidence anchor ID (if opened from evidence) */
  evidenceAnchor?: string;
}

/**
 * Union of all event property types
 */
export type EventProps = 
  | LedgerExpandProps
  | CompareRunProps
  | HypothesisPromoteProps
  | AuraProjectProps
  | ContradictionTooltipProps;

/**
 * Event names
 */
export enum MetricEvent {
  LEDGER_EXPAND = 'ui.ledger.expand',
  COMPARE_RUN = 'ui.compare.run',
  HYPOTHESIS_PROMOTE = 'ui.hypothesis.promote',
  AURA_PROPOSE = 'ui.aura.propose',
  CONTRADICTION_TOOLTIP_OPEN = 'ui.contradiction.tooltip.open',
}

// ============================================================================
// One-Shot Tracker
// ============================================================================

/**
 * Tracks which events have been fired to prevent duplicates
 */
class OneShotTracker {
  private firedEvents: Set<string>;
  
  constructor() {
    this.firedEvents = new Set();
  }
  
  /**
   * Generate unique key for an event
   */
  private generateKey(event: string, instanceId?: string): string {
    return instanceId ? `${event}:${instanceId}` : event;
  }
  
  /**
   * Check if event has been fired
   */
  hasFired(event: string, instanceId?: string): boolean {
    const key = this.generateKey(event, instanceId);
    return this.firedEvents.has(key);
  }
  
  /**
   * Mark event as fired
   */
  markFired(event: string, instanceId?: string): void {
    const key = this.generateKey(event, instanceId);
    this.firedEvents.add(key);
  }
  
  /**
   * Reset specific event (for testing)
   */
  reset(event?: string, instanceId?: string): void {
    if (event) {
      const key = this.generateKey(event, instanceId);
      this.firedEvents.delete(key);
    } else {
      this.firedEvents.clear();
    }
  }
  
  /**
   * Get all fired events (for debugging)
   */
  getFiredEvents(): string[] {
    return Array.from(this.firedEvents);
  }
}

// Global one-shot tracker
const oneShotTracker = new OneShotTracker();

// ============================================================================
// Metrics Client
// ============================================================================

/**
 * Interface for analytics provider (e.g., Segment, Amplitude, etc.)
 */
export interface AnalyticsProvider {
  track(event: string, properties: Record<string, any>): void;
  identify?(userId: string, traits?: Record<string, any>): void;
}

/**
 * Metrics client configuration
 */
export interface MetricsConfig {
  /** Analytics provider */
  provider?: AnalyticsProvider;
  
  /** Whether to enable console logging */
  debug?: boolean;
  
  /** Whether to enable one-shot protection */
  oneShotEnabled?: boolean;
  
  /** Session ID */
  sessionId?: string;
  
  /** User ID */
  userId?: string;
}

/**
 * Metrics client
 */
export class MetricsClient {
  private config: MetricsConfig;
  private provider?: AnalyticsProvider;
  
  constructor(config: MetricsConfig = {}) {
    this.config = {
      debug: false,
      oneShotEnabled: true,
      ...config,
    };
    this.provider = config.provider || this.getWindowAnalytics();
  }
  
  /**
   * Get analytics provider from window object
   */
  private getWindowAnalytics(): AnalyticsProvider | undefined {
    if (typeof window !== 'undefined' && (window as any).analytics) {
      return (window as any).analytics;
    }
    return undefined;
  }
  
  /**
   * Get base event properties
   */
  private getBaseProps(role: Role): BaseEventProps {
    return {
      role,
      timestamp: new Date().toISOString(),
      sessionId: this.config.sessionId,
      userId: this.config.userId,
    };
  }
  
  /**
   * Track event with one-shot protection
   */
  private trackEvent(
    event: MetricEvent,
    properties: Record<string, any>,
    instanceId?: string
  ): boolean {
    // Check one-shot
    if (this.config.oneShotEnabled && oneShotTracker.hasFired(event, instanceId)) {
      if (this.config.debug) {
        console.warn(`[Metrics] Event already fired: ${event}${instanceId ? ` (${instanceId})` : ''}`);
      }
      return false;
    }
    
    // Mark as fired
    if (this.config.oneShotEnabled) {
      oneShotTracker.markFired(event, instanceId);
    }
    
    // Log if debug
    if (this.config.debug) {
      console.log(`[Metrics] ${event}`, properties);
    }
    
    // Send to provider
    if (this.provider) {
      try {
        this.provider.track(event, properties);
      } catch (error) {
        console.error(`[Metrics] Failed to track event: ${event}`, error);
      }
    }
    
    return true;
  }
  
  /**
   * Track ledger expand
   */
  trackLedgerExpand(
    role: Role,
    props: Omit<LedgerExpandProps, keyof BaseEventProps>,
    instanceId?: string
  ): boolean {
    const eventProps: LedgerExpandProps = {
      ...this.getBaseProps(role),
      ...props,
    };
    
    return this.trackEvent(MetricEvent.LEDGER_EXPAND, eventProps, instanceId);
  }
  
  /**
   * Track compare run
   */
  trackCompareRun(
    role: Role,
    props: Omit<CompareRunProps, keyof BaseEventProps>,
    instanceId?: string
  ): boolean {
    const eventProps: CompareRunProps = {
      ...this.getBaseProps(role),
      ...props,
    };
    
    return this.trackEvent(MetricEvent.COMPARE_RUN, eventProps, instanceId);
  }
  
  /**
   * Track hypothesis promote
   */
  trackHypothesisPromote(
    role: Role,
    props: Omit<HypothesisPromoteProps, keyof BaseEventProps>,
    instanceId?: string
  ): boolean {
    const eventProps: HypothesisPromoteProps = {
      ...this.getBaseProps(role),
      ...props,
    };
    
    return this.trackEvent(MetricEvent.HYPOTHESIS_PROMOTE, eventProps, instanceId);
  }
  
  /**
   * Track AURA project propose
   */
  trackAuraPropose(
    role: Role,
    props: Omit<AuraProjectProps, keyof BaseEventProps>,
    instanceId?: string
  ): boolean {
    const eventProps: AuraProjectProps = {
      ...this.getBaseProps(role),
      ...props,
    };
    
    return this.trackEvent(MetricEvent.AURA_PROPOSE, eventProps, instanceId);
  }
  
  /**
   * Track contradiction tooltip open
   */
  trackContradictionTooltipOpen(
    role: Role,
    props: Omit<ContradictionTooltipProps, keyof BaseEventProps>,
    instanceId?: string
  ): boolean {
    const eventProps: ContradictionTooltipProps = {
      ...this.getBaseProps(role),
      ...props,
    };
    
    return this.trackEvent(MetricEvent.CONTRADICTION_TOOLTIP_OPEN, eventProps, instanceId);
  }
  
  /**
   * Reset one-shot tracker (for testing)
   */
  resetOneShot(event?: MetricEvent, instanceId?: string): void {
    oneShotTracker.reset(event, instanceId);
  }
  
  /**
   * Get fired events (for testing)
   */
  getFiredEvents(): string[] {
    return oneShotTracker.getFiredEvents();
  }
  
  /**
   * Update configuration
   */
  updateConfig(config: Partial<MetricsConfig>): void {
    this.config = { ...this.config, ...config };
    if (config.provider) {
      this.provider = config.provider;
    }
  }
}

// ============================================================================
// Global Instance
// ============================================================================

let globalMetricsClient: MetricsClient | null = null;

/**
 * Initialize global metrics client
 */
export function initMetrics(config: MetricsConfig = {}): MetricsClient {
  globalMetricsClient = new MetricsClient(config);
  return globalMetricsClient;
}

/**
 * Get global metrics client
 */
export function getMetrics(): MetricsClient {
  if (!globalMetricsClient) {
    globalMetricsClient = new MetricsClient();
  }
  return globalMetricsClient;
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Track ledger expand (convenience)
 */
export function trackLedgerExpand(
  role: Role,
  props: Omit<LedgerExpandProps, keyof BaseEventProps>,
  instanceId?: string
): boolean {
  return getMetrics().trackLedgerExpand(role, props, instanceId);
}

/**
 * Track compare run (convenience)
 */
export function trackCompareRun(
  role: Role,
  props: Omit<CompareRunProps, keyof BaseEventProps>,
  instanceId?: string
): boolean {
  return getMetrics().trackCompareRun(role, props, instanceId);
}

/**
 * Track hypothesis promote (convenience)
 */
export function trackHypothesisPromote(
  role: Role,
  props: Omit<HypothesisPromoteProps, keyof BaseEventProps>,
  instanceId?: string
): boolean {
  return getMetrics().trackHypothesisPromote(role, props, instanceId);
}

/**
 * Track AURA propose (convenience)
 */
export function trackAuraPropose(
  role: Role,
  props: Omit<AuraProjectProps, keyof BaseEventProps>,
  instanceId?: string
): boolean {
  return getMetrics().trackAuraPropose(role, props, instanceId);
}

/**
 * Track contradiction tooltip open (convenience)
 */
export function trackContradictionTooltipOpen(
  role: Role,
  props: Omit<ContradictionTooltipProps, keyof BaseEventProps>,
  instanceId?: string
): boolean {
  return getMetrics().trackContradictionTooltipOpen(role, props, instanceId);
}

// ============================================================================
// Exports
// ============================================================================

export default {
  initMetrics,
  getMetrics,
  MetricsClient,
  MetricEvent,
  trackLedgerExpand,
  trackCompareRun,
  trackHypothesisPromote,
  trackAuraPropose,
  trackContradictionTooltipOpen,
};
