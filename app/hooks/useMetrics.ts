/**
 * useMetrics Hook
 * 
 * React hook for tracking UI metrics with one-shot guarantees.
 * Provides convenient methods for tracking component-level events.
 */

import { useCallback, useRef, useMemo } from 'react';
import { getUserRole } from '../state/session';
import {
  getMetrics,
  MetricEvent,
  LedgerExpandProps,
  CompareRunProps,
  HypothesisPromoteProps,
  AuraProjectProps,
  ContradictionTooltipProps,
  BaseEventProps,
} from '../lib/metrics';
import { Role } from '../lib/roles';

// ============================================================================
// Types
// ============================================================================

/**
 * Hook return type
 */
export interface UseMetricsReturn {
  /**
   * Track ledger expand event
   */
  trackLedgerExpand: (
    props: Omit<LedgerExpandProps, keyof BaseEventProps>
  ) => boolean;
  
  /**
   * Track compare run event
   */
  trackCompareRun: (
    props: Omit<CompareRunProps, keyof BaseEventProps>
  ) => boolean;
  
  /**
   * Track hypothesis promote event
   */
  trackHypothesisPromote: (
    props: Omit<HypothesisPromoteProps, keyof BaseEventProps>
  ) => boolean;
  
  /**
   * Track AURA propose event
   */
  trackAuraPropose: (
    props: Omit<AuraProjectProps, keyof BaseEventProps>
  ) => boolean;
  
  /**
   * Track contradiction tooltip open event
   */
  trackContradictionTooltipOpen: (
    props: Omit<ContradictionTooltipProps, keyof BaseEventProps>
  ) => boolean;
  
  /**
   * Current user role
   */
  role: Role;
  
  /**
   * Component instance ID (for one-shot tracking)
   */
  instanceId: string;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * useMetrics hook
 * 
 * Provides metrics tracking functions with automatic role injection
 * and component-level one-shot protection.
 * 
 * @param componentName - Name of component (for instance ID generation)
 * @param explicitInstanceId - Explicit instance ID (optional, auto-generated if not provided)
 * 
 * @example
 * ```typescript
 * function MyComponent({ id }: Props) {
 *   const metrics = useMetrics('MyComponent', id);
 *   
 *   const handleClick = () => {
 *     metrics.trackLedgerExpand({
 *       traceLinesInSummary: 4,
 *       success: true,
 *     });
 *   };
 * }
 * ```
 */
export function useMetrics(
  componentName: string = 'unknown',
  explicitInstanceId?: string
): UseMetricsReturn {
  // Get user role
  const role = getUserRole();
  
  // Generate unique instance ID for this component mount
  const instanceIdRef = useRef<string>(
    explicitInstanceId || `${componentName}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  );
  const instanceId = instanceIdRef.current;
  
  // Get metrics client
  const metricsClient = useMemo(() => getMetrics(), []);
  
  /**
   * Track ledger expand
   */
  const trackLedgerExpand = useCallback((
    props: Omit<LedgerExpandProps, keyof BaseEventProps>
  ): boolean => {
    return metricsClient.trackLedgerExpand(role, props, instanceId);
  }, [metricsClient, role, instanceId]);
  
  /**
   * Track compare run
   */
  const trackCompareRun = useCallback((
    props: Omit<CompareRunProps, keyof BaseEventProps>
  ): boolean => {
    return metricsClient.trackCompareRun(role, props, instanceId);
  }, [metricsClient, role, instanceId]);
  
  /**
   * Track hypothesis promote
   */
  const trackHypothesisPromote = useCallback((
    props: Omit<HypothesisPromoteProps, keyof BaseEventProps>
  ): boolean => {
    return metricsClient.trackHypothesisPromote(role, props, instanceId);
  }, [metricsClient, role, instanceId]);
  
  /**
   * Track AURA propose
   */
  const trackAuraPropose = useCallback((
    props: Omit<AuraProjectProps, keyof BaseEventProps>
  ): boolean => {
    return metricsClient.trackAuraPropose(role, props, instanceId);
  }, [metricsClient, role, instanceId]);
  
  /**
   * Track contradiction tooltip open
   */
  const trackContradictionTooltipOpen = useCallback((
    props: Omit<ContradictionTooltipProps, keyof BaseEventProps>
  ): boolean => {
    return metricsClient.trackContradictionTooltipOpen(role, props, instanceId);
  }, [metricsClient, role, instanceId]);
  
  return {
    trackLedgerExpand,
    trackCompareRun,
    trackHypothesisPromote,
    trackAuraPropose,
    trackContradictionTooltipOpen,
    role,
    instanceId,
  };
}

// ============================================================================
// Specialized Hooks
// ============================================================================

/**
 * Hook specifically for ProcessLedger component
 */
export function useLedgerMetrics(messageId?: string) {
  const metrics = useMetrics('ProcessLedger', messageId);
  
  return {
    trackExpand: (
      traceLinesInSummary: number,
      traceLinesInFull?: number,
      success: boolean = true,
      error?: string
    ) => {
      return metrics.trackLedgerExpand({
        traceLinesInSummary,
        traceLinesInFull,
        messageId,
        success,
        error,
      });
    },
    ...metrics,
  };
}

/**
 * Hook specifically for CompareCard component
 */
export function useCompareMetrics(instanceId?: string) {
  const metrics = useMetrics('CompareCard', instanceId);
  
  return {
    trackRun: (
      allowExternal: boolean,
      internalEvidenceA: number,
      internalEvidenceB: number,
      externalEvidenceB?: number,
      success: boolean = true,
      error?: string,
      responseTimeMs?: number
    ) => {
      return metrics.trackCompareRun({
        allowExternal,
        internalEvidenceA,
        internalEvidenceB,
        externalEvidenceB,
        success,
        error,
        responseTimeMs,
      });
    },
    ...metrics,
  };
}

/**
 * Hook specifically for PromoteHypothesisButton component
 */
export function useHypothesisMetrics(instanceId?: string) {
  const metrics = useMetrics('PromoteHypothesisButton', instanceId);
  
  return {
    trackPromote: (
      evidenceCount: number,
      persisted: boolean,
      success: boolean = true,
      score?: number,
      hypothesisId?: string,
      error?: string
    ) => {
      return metrics.trackHypothesisPromote({
        evidenceCount,
        score,
        persisted,
        success,
        error,
        hypothesisId,
      });
    },
    ...metrics,
  };
}

/**
 * Hook specifically for ProposeAuraButton component
 */
export function useAuraMetrics(instanceId?: string) {
  const metrics = useMetrics('ProposeAuraButton', instanceId);
  
  return {
    trackPropose: (
      hypothesisPreLinked: boolean,
      starterTaskCount: number,
      success: boolean = true,
      hypothesisId?: string,
      projectId?: string,
      error?: string
    ) => {
      return metrics.trackAuraPropose({
        hypothesisId,
        hypothesisPreLinked,
        starterTaskCount,
        success,
        error,
        projectId,
      });
    },
    ...metrics,
  };
}

/**
 * Hook specifically for ContradictionBadge component
 */
export function useContradictionMetrics(instanceId?: string) {
  const metrics = useMetrics('ContradictionBadge', instanceId);
  
  return {
    trackTooltipOpen: (
      contradictionCount: number,
      highestSeverity: 'high' | 'medium' | 'low',
      evidenceAnchor?: string
    ) => {
      return metrics.trackContradictionTooltipOpen({
        contradictionCount,
        highestSeverity,
        evidenceAnchor,
      });
    },
    ...metrics,
  };
}

// ============================================================================
// Exports
// ============================================================================

export default useMetrics;
