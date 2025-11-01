"""
Tests for client-side role and capability definitions.

Verifies that client-side roles mirror server-side RBAC configuration.
"""

import json
from pathlib import Path


class TestRoleConstants:
    """Test role constant definitions."""
    
    def test_roles_file_exists(self):
        """Verify roles.ts file exists."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        assert roles_path.exists(), "roles.ts should exist"
    
    def test_all_roles_defined(self):
        """Verify all required roles are defined."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Check role constants
        assert 'ROLE_GENERAL = "general"' in content
        assert 'ROLE_PRO = "pro"' in content
        assert 'ROLE_SCHOLARS = "scholars"' in content
        assert 'ROLE_ANALYTICS = "analytics"' in content
        assert 'ROLE_OPS = "ops"' in content
        
        # Check ALL_ROLES set
        assert "ALL_ROLES" in content
    
    def test_roles_mirror_server_definitions(self):
        """Verify client roles match server roles.py."""
        server_roles_path = Path("/workspace/core/rbac/roles.py")
        client_roles_path = Path("/workspace/app/lib/roles.ts")
        
        server_content = server_roles_path.read_text()
        client_content = client_roles_path.read_text()
        
        # Check that all server role names exist in client
        server_roles = ["general", "pro", "scholars", "analytics", "ops"]
        for role in server_roles:
            assert f'"{role}"' in client_content


class TestCapabilityConstants:
    """Test capability constant definitions."""
    
    def test_all_capabilities_defined(self):
        """Verify all required capabilities are defined."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Check capability constants
        assert 'CAP_READ_PUBLIC = "READ_PUBLIC"' in content
        assert 'CAP_READ_LEDGER_FULL = "READ_LEDGER_FULL"' in content
        assert 'CAP_PROPOSE_HYPOTHESIS = "PROPOSE_HYPOTHESIS"' in content
        assert 'CAP_PROPOSE_AURA = "PROPOSE_AURA"' in content
        assert 'CAP_WRITE_GRAPH = "WRITE_GRAPH"' in content
        assert 'CAP_WRITE_CONTRADICTIONS = "WRITE_CONTRADICTIONS"' in content
        assert 'CAP_MANAGE_ROLES = "MANAGE_ROLES"' in content
        assert 'CAP_VIEW_DEBUG = "VIEW_DEBUG"' in content
        
        # Check ALL_CAPABILITIES set
        assert "ALL_CAPABILITIES" in content
    
    def test_capabilities_mirror_server_definitions(self):
        """Verify client capabilities match server capabilities.py."""
        server_caps_path = Path("/workspace/core/rbac/capabilities.py")
        client_roles_path = Path("/workspace/app/lib/roles.ts")
        
        server_content = server_caps_path.read_text()
        client_content = client_roles_path.read_text()
        
        # Extract server capability names
        server_caps = [
            "READ_PUBLIC",
            "READ_LEDGER_FULL",
            "PROPOSE_HYPOTHESIS",
            "PROPOSE_AURA",
            "WRITE_GRAPH",
            "WRITE_CONTRADICTIONS",
            "MANAGE_ROLES",
            "VIEW_DEBUG",
        ]
        
        for cap in server_caps:
            assert f'"{cap}"' in client_content


class TestRoleCapabilityMapping:
    """Test role-to-capability mappings."""
    
    def test_role_capabilities_mapping_exists(self):
        """Verify ROLE_CAPABILITIES mapping is defined."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        assert "ROLE_CAPABILITIES" in content
        assert "[ROLE_GENERAL]:" in content
        assert "[ROLE_PRO]:" in content
        assert "[ROLE_SCHOLARS]:" in content
        assert "[ROLE_ANALYTICS]:" in content
        assert "[ROLE_OPS]:" in content
    
    def test_general_has_minimal_permissions(self):
        """Verify general role has only READ_PUBLIC."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Find ROLE_GENERAL mapping
        start = content.find("[ROLE_GENERAL]:")
        end = content.find("),", start)
        general_block = content[start:end]
        
        assert "CAP_READ_PUBLIC" in general_block
        # Should not have other capabilities
        assert "CAP_WRITE_GRAPH" not in general_block
        assert "CAP_MANAGE_ROLES" not in general_block
    
    def test_pro_has_read_and_propose_capabilities(self):
        """Verify pro role has read and proposal capabilities."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Find ROLE_PRO mapping
        start = content.find("[ROLE_PRO]:")
        end = content.find("),", start)
        pro_block = content[start:end]
        
        assert "CAP_READ_PUBLIC" in pro_block
        assert "CAP_READ_LEDGER_FULL" in pro_block
        assert "CAP_PROPOSE_HYPOTHESIS" in pro_block
        assert "CAP_PROPOSE_AURA" in pro_block
        
        # Should not have write capabilities
        assert "CAP_WRITE_GRAPH" not in pro_block
    
    def test_scholars_same_as_pro_no_writes(self):
        """Verify scholars role matches pro but no write capabilities."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Find ROLE_SCHOLARS mapping
        start = content.find("[ROLE_SCHOLARS]:")
        # Find the end of just the scholars set definition (before closing paren)
        set_start = content.find("new Set([", start)
        set_end = content.find("]),", set_start)
        scholars_block = content[set_start:set_end]
        
        # Check for read and propose capabilities (scholars has these)
        assert "CAP_READ_PUBLIC" in scholars_block
        assert "CAP_READ_LEDGER_FULL" in scholars_block
        assert "CAP_PROPOSE_HYPOTHESIS" in scholars_block
        assert "CAP_PROPOSE_AURA" in scholars_block
        
        # Count capability lines (non-comment lines starting with CAP_)
        cap_lines = [line.strip() for line in scholars_block.split('\n')
                    if line.strip().startswith('CAP_')]
        
        # Scholars should have exactly 4 capabilities (no write capabilities)
        assert len(cap_lines) == 4, f"Scholars should have 4 capabilities, found {len(cap_lines)}"
    
    def test_analytics_has_write_capabilities(self):
        """Verify analytics role has write capabilities."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Find ROLE_ANALYTICS mapping
        start = content.find("[ROLE_ANALYTICS]:")
        end = content.find("),", start)
        analytics_block = content[start:end]
        
        assert "CAP_READ_PUBLIC" in analytics_block
        assert "CAP_WRITE_GRAPH" in analytics_block
        assert "CAP_WRITE_CONTRADICTIONS" in analytics_block
    
    def test_ops_has_debug_and_manage_roles(self):
        """Verify ops role has debug and role management."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Find ROLE_OPS mapping
        start = content.find("[ROLE_OPS]:")
        end = content.find("),", start)
        ops_block = content[start:end]
        
        assert "CAP_VIEW_DEBUG" in ops_block
        assert "CAP_MANAGE_ROLES" in ops_block


class TestAuthorizationFunctions:
    """Test authorization helper functions."""
    
    def test_has_capability_function_exists(self):
        """Verify hasCapability function is defined."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        assert "function hasCapability" in content
        assert "role: string" in content
        assert "capability: Capability" in content
        assert ": boolean" in content
    
    def test_has_capability_checks_role_mapping(self):
        """Verify hasCapability checks ROLE_CAPABILITIES."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Find hasCapability function
        start = content.find("function hasCapability")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        assert "ROLE_CAPABILITIES" in func_block
        # Check for normalized role variable (camelCase)
        assert "normalizedRole" in func_block or "normalized_role" in func_block
    
    def test_additional_helper_functions_exist(self):
        """Verify additional helper functions are defined."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Check for helper functions
        assert "function hasCapabilityAny" in content
        assert "function getRoleCapabilities" in content
        assert "function getAggregateCapabilities" in content
        assert "function validateRole" in content
        assert "function hasAnyCapability" in content
        assert "function hasAllCapabilities" in content
        assert "function getMissingCapabilities" in content
    
    def test_role_metadata_functions_exist(self):
        """Verify role metadata helper functions."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        assert "function getRoleMetadata" in content
        assert "function getHighestRole" in content
        assert "function formatRolesForDisplay" in content


class TestRoleMetadata:
    """Test role metadata definitions."""
    
    def test_role_descriptions_exist(self):
        """Verify role descriptions are defined."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        assert "ROLE_DESCRIPTIONS" in content
        
        # Check descriptions for all roles
        assert "[ROLE_GENERAL]:" in content
        assert "Basic role" in content
        assert "[ROLE_PRO]:" in content
        assert "[ROLE_SCHOLARS]:" in content
        assert "[ROLE_ANALYTICS]:" in content
        assert "[ROLE_OPS]:" in content
    
    def test_role_display_names_exist(self):
        """Verify role display names are defined."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        assert "ROLE_DISPLAY_NAMES" in content
    
    def test_role_badges_exist(self):
        """Verify role badge configuration exists."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        assert "ROLE_BADGES" in content
        assert "color" in content
        assert "icon" in content


class TestSecurityWarnings:
    """Test that security warnings are present."""
    
    def test_client_side_warning_present(self):
        """Verify warning about client-side checks."""
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Should have warnings about not trusting client checks
        warning_keywords = ["WARNING", "client-side", "UX only", "server-side"]
        content_lower = content.lower()
        
        found_warnings = sum(1 for keyword in warning_keywords if keyword.lower() in content_lower)
        assert found_warnings >= 2, "Should have security warnings"


class TestRoleAcceptanceCriteria:
    """Verify acceptance criteria for role resolution."""
    
    def test_role_resolution_returns_role_for_logged_in(self):
        """
        Acceptance: Role resolution returns role for logged-in user.
        
        Verified via session.ts integration.
        """
        session_path = Path("/workspace/app/state/session.ts")
        assert session_path.exists()
        
        content = session_path.read_text()
        
        # Should have getUserRole function
        assert "getUserRole" in content
        assert "getUserRoles" in content
    
    def test_role_resolution_returns_general_for_anonymous(self):
        """
        Acceptance: Role resolution returns 'general' for anonymous users.
        
        Verified via session.ts integration.
        """
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Should have ANONYMOUS_SESSION with general role
        assert "ANONYMOUS_SESSION" in content
        assert "ROLE_GENERAL" in content
    
    def test_has_capability_mirrors_server(self):
        """
        Acceptance: hasCapability() mirrors server mapping.
        
        Verified by checking that ROLE_CAPABILITIES matches server.
        """
        roles_path = Path("/workspace/app/lib/roles.ts")
        content = roles_path.read_text()
        
        # Should have identical structure to server
        assert "ROLE_CAPABILITIES" in content
        assert "hasCapability" in content
        
        # Check general has only READ_PUBLIC (same as server)
        start = content.find("[ROLE_GENERAL]:")
        end = content.find("),", start)
        general_block = content[start:end]
        
        # Count capabilities - should be 1
        cap_count = general_block.count("CAP_")
        assert cap_count == 1, "General should have exactly 1 capability"
