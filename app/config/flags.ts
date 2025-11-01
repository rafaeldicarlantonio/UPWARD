/**
 * Client-side feature flags configuration.
 * 
 * Controls UI rendering and feature availability.
 * These flags can be toggled dynamically based on user roles,
 * server configuration, or A/B testing requirements.
 */

/**
 * UI feature flags configuration.
 */
export interface UIFlags {
  /** Show full ledger details in chat responses */
  show_ledger: boolean;
  
  /** Show external comparison results and controls */
  show_compare: boolean;
  
  /** Show role badges and capability indicators */
  show_badges: boolean;
  
  /** Show debug information and metrics */
  show_debug: boolean;
  
  /** Show graph visualization tools */
  show_graph: boolean;
  
  /** Show contradiction detection results */
  show_contradictions: boolean;
  
  /** Show hypothesis proposal interface */
  show_hypothesis: boolean;
  
  /** Show aura proposal interface */
  show_aura: boolean;
}

/**
 * Default UI flags - conservative defaults for all features disabled.
 * Individual features are enabled based on role capabilities.
 */
export const DEFAULT_UI_FLAGS: UIFlags = {
  show_ledger: false,
  show_compare: false,
  show_badges: false,
  show_debug: false,
  show_graph: false,
  show_contradictions: false,
  show_hypothesis: false,
  show_aura: false,
};

/**
 * Feature flag manager for dynamic flag resolution.
 */
export class FeatureFlagManager {
  private flags: UIFlags;
  
  constructor(initialFlags: Partial<UIFlags> = {}) {
    this.flags = { ...DEFAULT_UI_FLAGS, ...initialFlags };
  }
  
  /**
   * Get current value of a feature flag.
   */
  getFlag(key: keyof UIFlags): boolean {
    return this.flags[key];
  }
  
  /**
   * Set a feature flag value.
   */
  setFlag(key: keyof UIFlags, value: boolean): void {
    this.flags[key] = value;
  }
  
  /**
   * Update multiple flags at once.
   */
  updateFlags(updates: Partial<UIFlags>): void {
    this.flags = { ...this.flags, ...updates };
  }
  
  /**
   * Get all current flags.
   */
  getAllFlags(): UIFlags {
    return { ...this.flags };
  }
  
  /**
   * Reset all flags to defaults.
   */
  reset(): void {
    this.flags = { ...DEFAULT_UI_FLAGS };
  }
  
  /**
   * Check if any of the specified flags are enabled.
   */
  hasAnyEnabled(keys: Array<keyof UIFlags>): boolean {
    return keys.some(key => this.flags[key]);
  }
  
  /**
   * Check if all of the specified flags are enabled.
   */
  hasAllEnabled(keys: Array<keyof UIFlags>): boolean {
    return keys.every(key => this.flags[key]);
  }
}

/**
 * Global feature flag instance.
 * Import and use this singleton for consistent flag access across the app.
 */
export const featureFlags = new FeatureFlagManager();

/**
 * React hook for feature flags (if using React).
 * Usage: const showLedger = useFeatureFlag('show_ledger');
 */
export function useFeatureFlag(key: keyof UIFlags): boolean {
  // This is a placeholder - implement with your state management solution
  // (React Context, Redux, Zustand, etc.)
  return featureFlags.getFlag(key);
}

/**
 * Utility to resolve flags based on server response.
 * Merges server-provided flags with client defaults.
 */
export function resolveUIFlags(serverFlags?: Partial<UIFlags>): UIFlags {
  return {
    ...DEFAULT_UI_FLAGS,
    ...serverFlags,
  };
}
