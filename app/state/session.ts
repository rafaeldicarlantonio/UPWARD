/**
 * Client-side session state management with role resolution.
 * 
 * Manages user authentication state, role resolution, and feature flag
 * computation based on user capabilities.
 */

import {
  Role,
  ROLE_GENERAL,
  hasCapability,
  getAggregateCapabilities,
  getRoleCapabilities,
  getRoleMetadata,
  getHighestRole,
  CAP_READ_LEDGER_FULL,
  CAP_PROPOSE_HYPOTHESIS,
  CAP_PROPOSE_AURA,
  CAP_WRITE_GRAPH,
  CAP_VIEW_DEBUG,
} from '../lib/roles';
import { UIFlags, resolveUIFlags } from '../config/flags';

// ============================================================================
// Session Types
// ============================================================================

/**
 * User session data.
 */
export interface UserSession {
  /** User ID (from JWT or API key) */
  userId: string | null;
  
  /** User email (if available) */
  email: string | null;
  
  /** Assigned roles */
  roles: string[];
  
  /** Computed UI flags based on roles */
  uiFlags: UIFlags;
  
  /** Whether user is authenticated */
  isAuthenticated: boolean;
  
  /** Whether user is anonymous */
  isAnonymous: boolean;
  
  /** JWT token (if using JWT auth) */
  token: string | null;
  
  /** API key (if using API key auth) */
  apiKey: string | null;
  
  /** Session metadata */
  metadata: {
    /** Highest privilege role */
    primaryRole: Role;
    
    /** Session creation timestamp */
    createdAt: number;
    
    /** Last activity timestamp */
    lastActivityAt: number;
  };
}

/**
 * Anonymous user session.
 */
export const ANONYMOUS_SESSION: UserSession = {
  userId: null,
  email: null,
  roles: [ROLE_GENERAL],
  uiFlags: resolveUIFlags(),
  isAuthenticated: false,
  isAnonymous: true,
  token: null,
  apiKey: null,
  metadata: {
    primaryRole: ROLE_GENERAL,
    createdAt: Date.now(),
    lastActivityAt: Date.now(),
  },
};

// ============================================================================
// JWT Parsing
// ============================================================================

/**
 * JWT payload structure (simplified).
 */
interface JWTPayload {
  sub?: string; // User ID
  email?: string;
  roles?: string[];
  exp?: number;
  iat?: number;
  [key: string]: any;
}

/**
 * Parse JWT token to extract user information.
 * 
 * NOTE: This is basic JWT parsing without signature verification.
 * Signature verification MUST happen server-side.
 * 
 * @param token - JWT token string
 * @returns Parsed JWT payload or null if invalid
 */
export function parseJWT(token: string): JWTPayload | null {
  if (!token) {
    return null;
  }
  
  try {
    // JWT format: header.payload.signature
    const parts = token.split('.');
    if (parts.length !== 3) {
      console.warn("Invalid JWT format: expected 3 parts");
      return null;
    }
    
    // Decode base64url payload
    const payload = parts[1];
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch (error) {
    console.error("Failed to parse JWT:", error);
    return null;
  }
}

/**
 * Check if JWT token is expired.
 * 
 * @param payload - Parsed JWT payload
 * @returns True if token is expired
 */
export function isJWTExpired(payload: JWTPayload): boolean {
  if (!payload.exp) {
    return false; // No expiration claim
  }
  
  const now = Math.floor(Date.now() / 1000);
  return payload.exp < now;
}

// ============================================================================
// Role Resolution
// ============================================================================

/**
 * Get user role from JWT token.
 * 
 * @param token - JWT token string
 * @returns Role name or 'general' for anonymous
 */
export function getUserRole(token: string | null): Role {
  if (!token) {
    return ROLE_GENERAL;
  }
  
  const payload = parseJWT(token);
  if (!payload) {
    return ROLE_GENERAL;
  }
  
  if (isJWTExpired(payload)) {
    console.warn("JWT token expired, falling back to general role");
    return ROLE_GENERAL;
  }
  
  // Check for roles array in JWT
  if (payload.roles && Array.isArray(payload.roles) && payload.roles.length > 0) {
    return getHighestRole(payload.roles);
  }
  
  // Check for role string in JWT
  if (payload.role && typeof payload.role === 'string') {
    return payload.role.toLowerCase() as Role;
  }
  
  return ROLE_GENERAL;
}

/**
 * Get all user roles from JWT token.
 * 
 * @param token - JWT token string
 * @returns Array of role names
 */
export function getUserRoles(token: string | null): string[] {
  if (!token) {
    return [ROLE_GENERAL];
  }
  
  const payload = parseJWT(token);
  if (!payload || isJWTExpired(payload)) {
    return [ROLE_GENERAL];
  }
  
  if (payload.roles && Array.isArray(payload.roles)) {
    return payload.roles.map(r => r.toLowerCase());
  }
  
  if (payload.role && typeof payload.role === 'string') {
    return [payload.role.toLowerCase()];
  }
  
  return [ROLE_GENERAL];
}

/**
 * Resolve UI flags based on user roles.
 * Enables features that the user has capabilities for.
 * 
 * @param roles - Array of user roles
 * @param serverFlags - Optional server-provided flag overrides
 * @returns Computed UI flags
 */
export function resolveUIFlagsForRoles(
  roles: string[],
  serverFlags?: Partial<UIFlags>
): UIFlags {
  const capabilities = getAggregateCapabilities(roles);
  
  // Compute flags based on capabilities
  const computedFlags: UIFlags = {
    show_ledger: capabilities.has(CAP_READ_LEDGER_FULL),
    show_compare: capabilities.has(CAP_READ_LEDGER_FULL), // Pro+ for external compare
    show_badges: true, // Always show role badges
    show_debug: capabilities.has(CAP_VIEW_DEBUG),
    show_graph: capabilities.has(CAP_WRITE_GRAPH),
    show_contradictions: capabilities.has(CAP_READ_LEDGER_FULL),
    show_hypothesis: capabilities.has(CAP_PROPOSE_HYPOTHESIS),
    show_aura: capabilities.has(CAP_PROPOSE_AURA),
  };
  
  // Merge with server-provided overrides
  return {
    ...computedFlags,
    ...serverFlags,
  };
}

// ============================================================================
// Session Management
// ============================================================================

/**
 * Create a user session from JWT token.
 * 
 * @param token - JWT token string
 * @param serverFlags - Optional server-provided flag overrides
 * @returns User session object
 */
export function createSessionFromJWT(
  token: string,
  serverFlags?: Partial<UIFlags>
): UserSession {
  const payload = parseJWT(token);
  
  if (!payload || isJWTExpired(payload)) {
    return { ...ANONYMOUS_SESSION };
  }
  
  const roles = getUserRoles(token);
  const uiFlags = resolveUIFlagsForRoles(roles, serverFlags);
  
  return {
    userId: payload.sub ?? null,
    email: payload.email ?? null,
    roles,
    uiFlags,
    isAuthenticated: true,
    isAnonymous: false,
    token,
    apiKey: null,
    metadata: {
      primaryRole: getHighestRole(roles),
      createdAt: payload.iat ? payload.iat * 1000 : Date.now(),
      lastActivityAt: Date.now(),
    },
  };
}

/**
 * Create a user session from API key.
 * 
 * NOTE: In a real implementation, you'd validate the API key
 * against the server and retrieve associated roles.
 * 
 * @param apiKey - API key string
 * @param roles - Roles associated with the API key
 * @param serverFlags - Optional server-provided flag overrides
 * @returns User session object
 */
export function createSessionFromAPIKey(
  apiKey: string,
  roles: string[],
  serverFlags?: Partial<UIFlags>
): UserSession {
  const uiFlags = resolveUIFlagsForRoles(roles, serverFlags);
  
  return {
    userId: `apikey:${apiKey.substring(0, 8)}`, // Truncated for privacy
    email: null,
    roles,
    uiFlags,
    isAuthenticated: true,
    isAnonymous: false,
    token: null,
    apiKey,
    metadata: {
      primaryRole: getHighestRole(roles),
      createdAt: Date.now(),
      lastActivityAt: Date.now(),
    },
  };
}

/**
 * Update session activity timestamp.
 * 
 * @param session - Current user session
 * @returns Updated session
 */
export function updateSessionActivity(session: UserSession): UserSession {
  return {
    ...session,
    metadata: {
      ...session.metadata,
      lastActivityAt: Date.now(),
    },
  };
}

/**
 * Check if session is still valid.
 * 
 * @param session - User session to check
 * @returns True if session is valid
 */
export function isSessionValid(session: UserSession): boolean {
  if (session.isAnonymous) {
    return true; // Anonymous sessions are always valid
  }
  
  if (session.token) {
    const payload = parseJWT(session.token);
    return payload !== null && !isJWTExpired(payload);
  }
  
  // For API key sessions, assume valid unless explicitly revoked server-side
  return session.apiKey !== null;
}

/**
 * Refresh session from token or API key.
 * 
 * @param session - Current user session
 * @param serverFlags - Optional server-provided flag overrides
 * @returns Refreshed session or anonymous session if invalid
 */
export function refreshSession(
  session: UserSession,
  serverFlags?: Partial<UIFlags>
): UserSession {
  if (!isSessionValid(session)) {
    return { ...ANONYMOUS_SESSION };
  }
  
  if (session.token) {
    return createSessionFromJWT(session.token, serverFlags);
  }
  
  if (session.apiKey) {
    return createSessionFromAPIKey(session.apiKey, session.roles, serverFlags);
  }
  
  return { ...ANONYMOUS_SESSION };
}

// ============================================================================
// Session Storage (Browser)
// ============================================================================

const SESSION_STORAGE_KEY = "upward_session";

/**
 * Save session to browser storage.
 * 
 * @param session - User session to save
 */
export function saveSession(session: UserSession): void {
  try {
    const serialized = JSON.stringify({
      token: session.token,
      apiKey: session.apiKey,
      roles: session.roles,
    });
    localStorage.setItem(SESSION_STORAGE_KEY, serialized);
  } catch (error) {
    console.error("Failed to save session:", error);
  }
}

/**
 * Load session from browser storage.
 * 
 * @param serverFlags - Optional server-provided flag overrides
 * @returns Restored session or anonymous session
 */
export function loadSession(serverFlags?: Partial<UIFlags>): UserSession {
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!stored) {
      return { ...ANONYMOUS_SESSION };
    }
    
    const parsed = JSON.parse(stored);
    
    if (parsed.token) {
      return createSessionFromJWT(parsed.token, serverFlags);
    }
    
    if (parsed.apiKey && parsed.roles) {
      return createSessionFromAPIKey(parsed.apiKey, parsed.roles, serverFlags);
    }
    
    return { ...ANONYMOUS_SESSION };
  } catch (error) {
    console.error("Failed to load session:", error);
    return { ...ANONYMOUS_SESSION };
  }
}

/**
 * Clear session from browser storage.
 */
export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  } catch (error) {
    console.error("Failed to clear session:", error);
  }
}

// ============================================================================
// Exports
// ============================================================================

export default {
  getUserRole,
  getUserRoles,
  createSessionFromJWT,
  createSessionFromAPIKey,
  resolveUIFlagsForRoles,
  isSessionValid,
  refreshSession,
  saveSession,
  loadSession,
  clearSession,
  ANONYMOUS_SESSION,
};
