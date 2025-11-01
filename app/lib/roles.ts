/**
 * Client-side role and capability definitions.
 * 
 * Mirrors server-side RBAC system for consistent authorization
 * checks in the UI.
 * 
 * WARNING: These checks are for UX only. All authorization must be
 * enforced server-side. Never trust client-side role checks for security.
 */

// ============================================================================
// Capability Constants
// ============================================================================

export const CAP_READ_PUBLIC = "READ_PUBLIC";
export const CAP_READ_LEDGER_FULL = "READ_LEDGER_FULL";
export const CAP_PROPOSE_HYPOTHESIS = "PROPOSE_HYPOTHESIS";
export const CAP_PROPOSE_AURA = "PROPOSE_AURA";
export const CAP_WRITE_GRAPH = "WRITE_GRAPH";
export const CAP_WRITE_CONTRADICTIONS = "WRITE_CONTRADICTIONS";
export const CAP_MANAGE_ROLES = "MANAGE_ROLES";
export const CAP_VIEW_DEBUG = "VIEW_DEBUG";

export type Capability =
  | typeof CAP_READ_PUBLIC
  | typeof CAP_READ_LEDGER_FULL
  | typeof CAP_PROPOSE_HYPOTHESIS
  | typeof CAP_PROPOSE_AURA
  | typeof CAP_WRITE_GRAPH
  | typeof CAP_WRITE_CONTRADICTIONS
  | typeof CAP_MANAGE_ROLES
  | typeof CAP_VIEW_DEBUG;

export const ALL_CAPABILITIES: ReadonlySet<Capability> = new Set([
  CAP_READ_PUBLIC,
  CAP_READ_LEDGER_FULL,
  CAP_PROPOSE_HYPOTHESIS,
  CAP_PROPOSE_AURA,
  CAP_WRITE_GRAPH,
  CAP_WRITE_CONTRADICTIONS,
  CAP_MANAGE_ROLES,
  CAP_VIEW_DEBUG,
]);

// ============================================================================
// Role Constants
// ============================================================================

export const ROLE_GENERAL = "general";
export const ROLE_PRO = "pro";
export const ROLE_SCHOLARS = "scholars";
export const ROLE_ANALYTICS = "analytics";
export const ROLE_OPS = "ops";

export type Role =
  | typeof ROLE_GENERAL
  | typeof ROLE_PRO
  | typeof ROLE_SCHOLARS
  | typeof ROLE_ANALYTICS
  | typeof ROLE_OPS;

export const ALL_ROLES: ReadonlySet<Role> = new Set([
  ROLE_GENERAL,
  ROLE_PRO,
  ROLE_SCHOLARS,
  ROLE_ANALYTICS,
  ROLE_OPS,
]);

// ============================================================================
// Role-to-Capability Mapping
// ============================================================================

export const ROLE_CAPABILITIES: Readonly<Record<Role, ReadonlySet<Capability>>> = {
  [ROLE_GENERAL]: new Set([
    CAP_READ_PUBLIC,
  ]),
  
  [ROLE_PRO]: new Set([
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_PROPOSE_AURA,
  ]),
  
  [ROLE_SCHOLARS]: new Set([
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_PROPOSE_AURA,
    // Explicitly NO: CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS
  ]),
  
  [ROLE_ANALYTICS]: new Set([
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_PROPOSE_AURA,
    CAP_WRITE_GRAPH,
    CAP_WRITE_CONTRADICTIONS,
  ]),
  
  [ROLE_OPS]: new Set([
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_VIEW_DEBUG,
    CAP_MANAGE_ROLES,
  ]),
};

// ============================================================================
// Role Metadata
// ============================================================================

export const ROLE_DESCRIPTIONS: Readonly<Record<Role, string>> = {
  [ROLE_GENERAL]: "Basic role with read-only access to public content",
  [ROLE_PRO]: "Professional role with full read access and proposal capabilities",
  [ROLE_SCHOLARS]: "Academic role with read and proposal access but no write permissions",
  [ROLE_ANALYTICS]: "Analytics role with read, propose, and write capabilities",
  [ROLE_OPS]: "Operations role with read access and debug/monitoring capabilities",
};

export const ROLE_DISPLAY_NAMES: Readonly<Record<Role, string>> = {
  [ROLE_GENERAL]: "General",
  [ROLE_PRO]: "Pro",
  [ROLE_SCHOLARS]: "Scholars",
  [ROLE_ANALYTICS]: "Analytics",
  [ROLE_OPS]: "Operations",
};

export const ROLE_BADGES: Readonly<Record<Role, { color: string; icon: string }>> = {
  [ROLE_GENERAL]: { color: "gray", icon: "👤" },
  [ROLE_PRO]: { color: "blue", icon: "⭐" },
  [ROLE_SCHOLARS]: { color: "purple", icon: "🎓" },
  [ROLE_ANALYTICS]: { color: "green", icon: "📊" },
  [ROLE_OPS]: { color: "orange", icon: "⚙️" },
};

// ============================================================================
// Authorization Functions
// ============================================================================

/**
 * Check if a role has a specific capability.
 * 
 * WARNING: This is for UI/UX only. Never rely on client-side checks for security.
 * All authorization must be enforced server-side.
 * 
 * @param role - Role name
 * @param capability - Capability to check
 * @returns True if role has the capability
 */
export function hasCapability(role: string, capability: Capability): boolean {
  if (!role) {
    console.warn("hasCapability called with empty role");
    return false;
  }
  
  if (!ALL_CAPABILITIES.has(capability)) {
    console.warn(`Unknown capability: ${capability}`);
    return false;
  }
  
  const normalizedRole = role.toLowerCase() as Role;
  
  if (!ALL_ROLES.has(normalizedRole)) {
    console.warn(`Unknown role: ${role}`);
    return false;
  }
  
  return ROLE_CAPABILITIES[normalizedRole]?.has(capability) ?? false;
}

/**
 * Check if any of the user's roles has a specific capability.
 * 
 * @param roles - Array of role names
 * @param capability - Capability to check
 * @returns True if any role has the capability
 */
export function hasCapabilityAny(roles: string[], capability: Capability): boolean {
  return roles.some(role => hasCapability(role, capability));
}

/**
 * Get all capabilities for a role.
 * 
 * @param role - Role name
 * @returns Set of capabilities for the role
 */
export function getRoleCapabilities(role: string): Set<Capability> {
  if (!role) {
    return new Set();
  }
  
  const normalizedRole = role.toLowerCase() as Role;
  return new Set(ROLE_CAPABILITIES[normalizedRole] ?? []);
}

/**
 * Get all capabilities across multiple roles.
 * 
 * @param roles - Array of role names
 * @returns Set of all capabilities from all roles
 */
export function getAggregateCapabilities(roles: string[]): Set<Capability> {
  const capabilities = new Set<Capability>();
  
  roles.forEach(role => {
    getRoleCapabilities(role).forEach(cap => capabilities.add(cap));
  });
  
  return capabilities;
}

/**
 * Check if a role is valid.
 * 
 * @param role - Role name to validate
 * @returns True if the role exists
 */
export function validateRole(role: string): boolean {
  if (!role) {
    return false;
  }
  
  return ALL_ROLES.has(role.toLowerCase() as Role);
}

/**
 * Check if user has any of the specified capabilities.
 * 
 * @param roles - Array of role names
 * @param capabilities - Array of capabilities to check
 * @returns True if user has at least one capability
 */
export function hasAnyCapability(roles: string[], capabilities: Capability[]): boolean {
  return capabilities.some(cap => hasCapabilityAny(roles, cap));
}

/**
 * Check if user has all of the specified capabilities.
 * 
 * @param roles - Array of role names
 * @param capabilities - Array of capabilities to check
 * @returns True if user has all capabilities
 */
export function hasAllCapabilities(roles: string[], capabilities: Capability[]): boolean {
  return capabilities.every(cap => hasCapabilityAny(roles, cap));
}

/**
 * Get missing capabilities from a required set.
 * 
 * @param roles - Array of role names
 * @param requiredCapabilities - Array of required capabilities
 * @returns Set of missing capabilities
 */
export function getMissingCapabilities(
  roles: string[],
  requiredCapabilities: Capability[]
): Set<Capability> {
  const userCapabilities = getAggregateCapabilities(roles);
  return new Set(
    requiredCapabilities.filter(cap => !userCapabilities.has(cap))
  );
}

/**
 * Get role metadata.
 * 
 * @param role - Role name
 * @returns Role metadata object
 */
export function getRoleMetadata(role: string): {
  description: string;
  displayName: string;
  badge: { color: string; icon: string };
  capabilities: Capability[];
} | null {
  const normalizedRole = role.toLowerCase() as Role;
  
  if (!ALL_ROLES.has(normalizedRole)) {
    return null;
  }
  
  return {
    description: ROLE_DESCRIPTIONS[normalizedRole],
    displayName: ROLE_DISPLAY_NAMES[normalizedRole],
    badge: ROLE_BADGES[normalizedRole],
    capabilities: Array.from(ROLE_CAPABILITIES[normalizedRole]),
  };
}

/**
 * Get the highest privilege role from a list of roles.
 * Privilege order: ops > analytics > scholars/pro > general
 * 
 * @param roles - Array of role names
 * @returns Highest privilege role
 */
export function getHighestRole(roles: string[]): Role {
  const roleOrder: Role[] = [
    ROLE_OPS,
    ROLE_ANALYTICS,
    ROLE_SCHOLARS,
    ROLE_PRO,
    ROLE_GENERAL,
  ];
  
  const normalizedRoles = roles.map(r => r.toLowerCase() as Role);
  
  for (const role of roleOrder) {
    if (normalizedRoles.includes(role)) {
      return role;
    }
  }
  
  return ROLE_GENERAL;
}

/**
 * Format roles for display in UI.
 * 
 * @param roles - Array of role names
 * @returns Comma-separated display names
 */
export function formatRolesForDisplay(roles: string[]): string {
  return roles
    .map(role => {
      const normalized = role.toLowerCase() as Role;
      return ROLE_DISPLAY_NAMES[normalized] ?? role;
    })
    .join(", ");
}
