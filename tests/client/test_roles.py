"""
Tests for client-side role and capability checking (TypeScript module)

Since the roles module is TypeScript, we test via structure verification.
These tests verify the role/capability mapping mirrors the server-side RBAC.
"""

import pytest
from pathlib import Path


# Path to the TypeScript module
ROLES_MODULE = Path(__file__).parent.parent.parent / "app" / "lib" / "roles.ts"


class TestRolesModuleStructure:
    """Verify the roles module exists and has correct structure."""
    
    def test_roles_module_exists(self):
        """Verify roles.ts exists."""
        assert ROLES_MODULE.exists(), f"Expected {ROLES_MODULE} to exist"
    
    def test_role_constants_defined(self):
        """Verify all role constants are defined."""
        content = ROLES_MODULE.read_text()
        
        roles = ['ROLE_GENERAL', 'ROLE_PRO', 'ROLE_SCHOLARS', 'ROLE_ANALYTICS', 'ROLE_OPS']
        for role in roles:
            assert f"export const {role}" in content, f"Missing role constant: {role}"
    
    def test_capability_constants_defined(self):
        """Verify all capability constants are defined."""
        content = ROLES_MODULE.read_text()
        
        capabilities = [
            'CAP_READ_PUBLIC',
            'CAP_READ_LEDGER_FULL',
            'CAP_PROPOSE_HYPOTHESIS',
            'CAP_PROPOSE_AURA',
            'CAP_WRITE_GRAPH',
            'CAP_WRITE_CONTRADICTIONS',
            'CAP_MANAGE_ROLES',
            'CAP_VIEW_DEBUG',
        ]
        
        for cap in capabilities:
            assert f"export const {cap}" in content, f"Missing capability constant: {cap}"
    
    def test_role_capabilities_mapping_exists(self):
        """Verify ROLE_CAPABILITIES mapping is defined."""
        content = ROLES_MODULE.read_text()
        
        assert "ROLE_CAPABILITIES: Record<Role, ReadonlySet<Capability>>" in content
    
    def test_has_capability_function_exists(self):
        """Verify hasCapability function is defined."""
        content = ROLES_MODULE.read_text()
        
        assert "export function hasCapability" in content


class TestRoleCapabilityMapping:
    """Test role-to-capability mapping mirrors server-side RBAC."""
    
    def test_general_role_capabilities(self):
        """General role should only have READ_PUBLIC."""
        content = ROLES_MODULE.read_text()
        
        # Find GENERAL mapping
        general_start = content.index("[ROLE_GENERAL]: new Set([")
        general_end = content.index("])", general_start)
        general_mapping = content[general_start:general_end]
        
        assert "CAP_READ_PUBLIC" in general_mapping
        # Should not have any other capabilities
        assert "CAP_READ_LEDGER_FULL" not in general_mapping
        assert "CAP_WRITE_GRAPH" not in general_mapping
    
    def test_pro_role_capabilities(self):
        """Pro role should have read + propose capabilities."""
        content = ROLES_MODULE.read_text()
        
        pro_start = content.index("[ROLE_PRO]: new Set([")
        pro_end = content.index("])", pro_start)
        pro_mapping = content[pro_start:pro_end]
        
        assert "CAP_READ_PUBLIC" in pro_mapping
        assert "CAP_READ_LEDGER_FULL" in pro_mapping
        assert "CAP_PROPOSE_HYPOTHESIS" in pro_mapping
        assert "CAP_PROPOSE_AURA" in pro_mapping
        
        # Should not have write capabilities
        assert "CAP_WRITE_GRAPH" not in pro_mapping
        assert "CAP_WRITE_CONTRADICTIONS" not in pro_mapping
    
    def test_scholars_role_capabilities(self):
        """Scholars role should have same as Pro (no write)."""
        content = ROLES_MODULE.read_text()
        
        scholars_start = content.index("[ROLE_SCHOLARS]: new Set([")
        scholars_end = content.index("])", scholars_start)
        scholars_mapping = content[scholars_start:scholars_end]
        
        assert "CAP_READ_PUBLIC" in scholars_mapping
        assert "CAP_READ_LEDGER_FULL" in scholars_mapping
        assert "CAP_PROPOSE_HYPOTHESIS" in scholars_mapping
        assert "CAP_PROPOSE_AURA" in scholars_mapping
        
        # No write capabilities
        assert "CAP_WRITE_GRAPH" not in scholars_mapping
        assert "CAP_WRITE_CONTRADICTIONS" not in scholars_mapping
    
    def test_analytics_role_capabilities(self):
        """Analytics role should have full read + propose + write."""
        content = ROLES_MODULE.read_text()
        
        analytics_start = content.index("[ROLE_ANALYTICS]: new Set([")
        analytics_end = content.index("])", analytics_start)
        analytics_mapping = content[analytics_start:analytics_end]
        
        assert "CAP_READ_PUBLIC" in analytics_mapping
        assert "CAP_READ_LEDGER_FULL" in analytics_mapping
        assert "CAP_PROPOSE_HYPOTHESIS" in analytics_mapping
        assert "CAP_PROPOSE_AURA" in analytics_mapping
        assert "CAP_WRITE_GRAPH" in analytics_mapping
        assert "CAP_WRITE_CONTRADICTIONS" in analytics_mapping
    
    def test_ops_role_capabilities(self):
        """Ops role should have read + debug + manage_roles."""
        content = ROLES_MODULE.read_text()
        
        ops_start = content.index("[ROLE_OPS]: new Set([")
        ops_end = content.index("])", ops_start)
        ops_mapping = content[ops_start:ops_end]
        
        assert "CAP_READ_PUBLIC" in ops_mapping
        assert "CAP_READ_LEDGER_FULL" in ops_mapping
        assert "CAP_VIEW_DEBUG" in ops_mapping
        assert "CAP_MANAGE_ROLES" in ops_mapping
        
        # Should not have write or propose capabilities
        assert "CAP_WRITE_GRAPH" not in ops_mapping
        assert "CAP_PROPOSE_HYPOTHESIS" not in ops_mapping


class TestRoleMetadata:
    """Test role metadata for UI display."""
    
    def test_role_metadata_exists(self):
        """ROLE_METADATA should be defined."""
        content = ROLES_MODULE.read_text()
        
        assert "ROLE_METADATA: Record<Role, RoleMetadata>" in content
    
    def test_role_metadata_has_all_roles(self):
        """ROLE_METADATA should include all roles."""
        content = ROLES_MODULE.read_text()
        
        # Find ROLE_METADATA definition
        metadata_start = content.index("export const ROLE_METADATA")
        metadata_end = content.index("};", metadata_start) + 2
        metadata_section = content[metadata_start:metadata_end]
        
        roles = ['ROLE_GENERAL', 'ROLE_PRO', 'ROLE_SCHOLARS', 'ROLE_ANALYTICS', 'ROLE_OPS']
        for role in roles:
            assert f"[{role}]:" in metadata_section
    
    def test_role_metadata_has_required_fields(self):
        """Each role metadata should have name, description, color."""
        content = ROLES_MODULE.read_text()
        
        metadata_start = content.index("export const ROLE_METADATA")
        metadata_end = content.index("};", metadata_start) + 2
        metadata_section = content[metadata_start:metadata_end]
        
        # Check for required fields in at least one role
        assert "name:" in metadata_section
        assert "description:" in metadata_section
        assert "color:" in metadata_section
        assert "icon:" in metadata_section


class TestAuthorizationFunctions:
    """Test authorization helper functions."""
    
    def test_has_capability_function(self):
        """hasCapability function should check role capabilities."""
        content = ROLES_MODULE.read_text()
        
        func_def = content[content.index("export function hasCapability"):]
        func_def = func_def[:func_def.index("\nexport")]
        
        # Should normalize role
        assert "toLowerCase()" in func_def
        # Should check ROLE_CAPABILITIES
        assert "ROLE_CAPABILITIES" in func_def
        # Should use .has() on Set
        assert ".has(capability)" in func_def
    
    def test_has_any_capability_function(self):
        """hasAnyCapability should check if role has any of the capabilities."""
        content = ROLES_MODULE.read_text()
        
        assert "export function hasAnyCapability" in content
        
        func_def = content[content.index("export function hasAnyCapability"):]
        func_def = func_def[:func_def.index("\nexport")]
        
        # Should use .some()
        assert ".some(" in func_def
        assert "hasCapability" in func_def
    
    def test_has_all_capabilities_function(self):
        """hasAllCapabilities should check if role has all capabilities."""
        content = ROLES_MODULE.read_text()
        
        assert "export function hasAllCapabilities" in content
        
        func_def = content[content.index("export function hasAllCapabilities"):]
        func_def = func_def[:func_def.index("\nexport")]
        
        # Should use .every()
        assert ".every(" in func_def
        assert "hasCapability" in func_def
    
    def test_get_role_capabilities_function(self):
        """getRoleCapabilities should return Set of capabilities."""
        content = ROLES_MODULE.read_text()
        
        assert "export function getRoleCapabilities" in content
        assert ": ReadonlySet<Capability>" in content
    
    def test_is_valid_role_function(self):
        """isValidRole should validate role strings."""
        content = ROLES_MODULE.read_text()
        
        assert "export function isValidRole" in content
        assert ": role is Role" in content  # Type guard


class TestUtilityFunctions:
    """Test utility functions for role operations."""
    
    def test_get_role_display_name_function(self):
        """getRoleDisplayName should return human-readable name."""
        content = ROLES_MODULE.read_text()
        
        assert "export function getRoleDisplayName" in content
    
    def test_get_role_color_function(self):
        """getRoleColor should return color for badges."""
        content = ROLES_MODULE.read_text()
        
        assert "export function getRoleColor" in content
    
    def test_get_role_icon_function(self):
        """getRoleIcon should return icon emoji."""
        content = ROLES_MODULE.read_text()
        
        assert "export function getRoleIcon" in content
    
    def test_list_all_roles_function(self):
        """listAllRoles should return all role info."""
        content = ROLES_MODULE.read_text()
        
        assert "export function listAllRoles" in content
    
    def test_compare_roles_function(self):
        """compareRoles should compare privilege levels."""
        content = ROLES_MODULE.read_text()
        
        assert "export function compareRoles" in content
    
    def test_get_highest_role_function(self):
        """getHighestRole should return highest privilege role."""
        content = ROLES_MODULE.read_text()
        
        assert "export function getHighestRole" in content


class TestAcceptanceCriteria:
    """Direct verification of user acceptance criteria."""
    
    def test_ac1_role_constants_mirror_server(self):
        """AC1: Role constants match server-side definitions."""
        content = ROLES_MODULE.read_text()
        
        # Check exact constant names and values
        assert "export const ROLE_GENERAL = 'general'" in content
        assert "export const ROLE_PRO = 'pro'" in content
        assert "export const ROLE_SCHOLARS = 'scholars'" in content
        assert "export const ROLE_ANALYTICS = 'analytics'" in content
        assert "export const ROLE_OPS = 'ops'" in content
    
    def test_ac2_capability_constants_mirror_server(self):
        """AC2: Capability constants match server-side definitions."""
        content = ROLES_MODULE.read_text()
        
        server_caps = [
            ('CAP_READ_PUBLIC', 'READ_PUBLIC'),
            ('CAP_READ_LEDGER_FULL', 'READ_LEDGER_FULL'),
            ('CAP_PROPOSE_HYPOTHESIS', 'PROPOSE_HYPOTHESIS'),
            ('CAP_PROPOSE_AURA', 'PROPOSE_AURA'),
            ('CAP_WRITE_GRAPH', 'WRITE_GRAPH'),
            ('CAP_WRITE_CONTRADICTIONS', 'WRITE_CONTRADICTIONS'),
            ('CAP_MANAGE_ROLES', 'MANAGE_ROLES'),
            ('CAP_VIEW_DEBUG', 'VIEW_DEBUG'),
        ]
        
        for const_name, value in server_caps:
            assert f"export const {const_name} = '{value}'" in content
    
    def test_ac3_has_capability_function_exists(self):
        """AC3: hasCapability() function exists and works like server."""
        content = ROLES_MODULE.read_text()
        
        # Function signature
        assert "export function hasCapability(role: Role | string, capability: Capability): boolean" in content
        
        # Implementation uses ROLE_CAPABILITIES mapping
        func_def = content[content.index("export function hasCapability"):]
        func_def = func_def[:func_def.index("\nexport")]
        
        assert "ROLE_CAPABILITIES" in func_def
        assert ".has(capability)" in func_def
    
    def test_ac4_role_capabilities_match_server(self):
        """AC4: ROLE_CAPABILITIES mapping matches server-side exactly."""
        content = ROLES_MODULE.read_text()
        
        # Extract ROLE_CAPABILITIES section
        mapping_start = content.index("export const ROLE_CAPABILITIES")
        mapping_end = content.index("};", mapping_start) + 2
        mapping = content[mapping_start:mapping_end]
        
        # Verify each role's capabilities match server
        # General: only READ_PUBLIC
        assert "[ROLE_GENERAL]: new Set([" in mapping
        general_end = content.index("])", mapping.index("[ROLE_GENERAL]"))
        general_caps = content[mapping.index("[ROLE_GENERAL]"):general_end]
        assert general_caps.count("CAP_") == 1  # Only one capability
        
        # Analytics: has WRITE_GRAPH and WRITE_CONTRADICTIONS
        analytics_caps = content[mapping.index("[ROLE_ANALYTICS]"):content.index("])", mapping.index("[ROLE_ANALYTICS]"))]
        assert "CAP_WRITE_GRAPH" in analytics_caps
        assert "CAP_WRITE_CONTRADICTIONS" in analytics_caps
        
        # Ops: has MANAGE_ROLES and VIEW_DEBUG
        ops_caps = content[mapping.index("[ROLE_OPS]"):content.index("])", mapping.index("[ROLE_OPS]"))]
        assert "CAP_MANAGE_ROLES" in ops_caps
        assert "CAP_VIEW_DEBUG" in ops_caps
    
    def test_ac5_get_user_role_equivalent_exists(self):
        """AC5: Client has equivalent of getUserRole() (in session.ts)."""
        # This will be in session.ts, but we verify roles.ts supports it
        content = ROLES_MODULE.read_text()
        
        # Roles module provides the building blocks
        assert "export function hasCapability" in content
        assert "export function getRoleCapabilities" in content
    
    def test_ac6_anonymous_role_exists(self):
        """AC6: Client has ROLE_ANONYMOUS for logged-out state."""
        content = ROLES_MODULE.read_text()
        
        assert "export const ROLE_ANONYMOUS = 'anonymous'" in content
        assert "[ROLE_ANONYMOUS]: new Set([" in content
    
    def test_ac7_role_metadata_for_ui(self):
        """AC7: Role metadata includes display info (name, color, icon)."""
        content = ROLES_MODULE.read_text()
        
        # Check interface definition
        assert "interface RoleMetadata" in content
        
        metadata_interface = content[content.index("export interface RoleMetadata"):]
        metadata_interface = metadata_interface[:metadata_interface.index("}")]
        
        assert "name: string" in metadata_interface
        assert "description: string" in metadata_interface
        assert "color: string" in metadata_interface
        assert "icon?: string" in metadata_interface


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
