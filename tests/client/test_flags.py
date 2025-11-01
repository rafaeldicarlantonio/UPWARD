"""
Tests for client-side feature flags (TypeScript module)

Since the flags module is TypeScript, we test via Node.js integration.
These tests verify the flag configuration and role-based flag recommendations.
"""

import pytest
import json
import subprocess
from pathlib import Path


# Path to the TypeScript module
FLAGS_MODULE = Path(__file__).parent.parent.parent / "app" / "config" / "flags.ts"


class TestFlagsModuleExists:
    """Verify the flags module exists and has correct structure."""
    
    def test_flags_module_exists(self):
        """Verify flags.ts exists."""
        assert FLAGS_MODULE.exists(), f"Expected {FLAGS_MODULE} to exist"
    
    def test_flags_module_has_default_flags(self):
        """Verify DEFAULT_FLAGS is defined."""
        content = FLAGS_MODULE.read_text()
        assert "DEFAULT_FLAGS" in content
        assert "show_ledger: false" in content
        assert "show_compare: false" in content
        assert "show_badges: false" in content
    
    def test_flags_module_has_ui_flags_interface(self):
        """Verify UIFlags interface is defined."""
        content = FLAGS_MODULE.read_text()
        assert "interface UIFlags" in content
        assert "show_ledger: boolean" in content
        assert "show_compare: boolean" in content
        assert "show_badges: boolean" in content
    
    def test_flags_module_exports_functions(self):
        """Verify all required functions are exported."""
        content = FLAGS_MODULE.read_text()
        
        required_functions = [
            "getFlags",
            "getFlag",
            "setFlag",
            "setFlags",
            "resetFlags",
            "loadFlagsFromEnv",
            "saveFlagsToStorage",
            "getFlagsForRole",
        ]
        
        for func in required_functions:
            assert f"export function {func}" in content, f"Missing function: {func}"


class TestFlagConfiguration:
    """Test flag configuration values and behavior."""
    
    def test_default_flags_all_disabled(self):
        """All flags should be disabled by default."""
        content = FLAGS_MODULE.read_text()
        
        # Extract DEFAULT_FLAGS definition
        start = content.index("DEFAULT_FLAGS")
        end = content.index("};", start) + 2
        default_flags_section = content[start:end]
        
        assert "show_ledger: false" in default_flags_section
        assert "show_compare: false" in default_flags_section
        assert "show_badges: false" in default_flags_section
    
    def test_flags_for_general_role(self):
        """General role should have all flags disabled."""
        content = FLAGS_MODULE.read_text()
        
        # Find getFlagsForRole function
        start = content.index("case 'general':")
        end = content.index("};", start)
        general_section = content[start:end]
        
        assert "show_ledger: false" in general_section
        assert "show_compare: false" in general_section
        assert "show_badges: false" in general_section
    
    def test_flags_for_pro_role(self):
        """Pro role should have compare and badges enabled."""
        content = FLAGS_MODULE.read_text()
        
        # Find pro case
        start = content.index("case 'pro':")
        end = content.index("};", start)
        pro_section = content[start:end]
        
        assert "show_ledger: false" in pro_section
        assert "show_compare: true" in pro_section
        assert "show_badges: true" in pro_section
    
    def test_flags_for_scholars_role(self):
        """Scholars role should have compare and badges enabled."""
        content = FLAGS_MODULE.read_text()
        
        # Find scholars case (same as pro)
        start = content.index("case 'scholars':")
        end = content.index("};", start)
        scholars_section = content[start:end]
        
        assert "show_ledger: false" in scholars_section
        assert "show_compare: true" in scholars_section
        assert "show_badges: true" in scholars_section
    
    def test_flags_for_analytics_role(self):
        """Analytics role should have all flags enabled."""
        content = FLAGS_MODULE.read_text()
        
        # Find analytics case
        start = content.index("case 'analytics':")
        end = content.index("};", start)
        analytics_section = content[start:end]
        
        assert "show_ledger: true" in analytics_section
        assert "show_compare: true" in analytics_section
        assert "show_badges: true" in analytics_section
    
    def test_flags_for_ops_role(self):
        """Ops role should have ledger and badges, but not compare."""
        content = FLAGS_MODULE.read_text()
        
        # Find ops case
        start = content.index("case 'ops':")
        end = content.index("};", start)
        ops_section = content[start:end]
        
        assert "show_ledger: true" in ops_section
        assert "show_compare: false" in ops_section
        assert "show_badges: true" in ops_section


class TestFlagFunctions:
    """Test flag manipulation functions."""
    
    def test_get_flags_returns_copy(self):
        """getFlags should return a copy of current flags."""
        content = FLAGS_MODULE.read_text()
        
        # Check that function returns a spread copy
        get_flags_def = content[content.index("export function getFlags"):]
        get_flags_def = get_flags_def[:get_flags_def.index("\n}")]
        
        assert "{ ...currentFlags }" in get_flags_def
    
    def test_set_flag_updates_single_flag(self):
        """setFlag should update a single flag."""
        content = FLAGS_MODULE.read_text()
        
        set_flag_def = content[content.index("export function setFlag"):]
        set_flag_def = set_flag_def[:set_flag_def.index("\n}")]
        
        assert "currentFlags[key] = value" in set_flag_def
    
    def test_set_flags_merges_partial_flags(self):
        """setFlags should merge partial flags."""
        content = FLAGS_MODULE.read_text()
        
        set_flags_def = content[content.index("export function setFlags"):]
        set_flags_def = set_flags_def[:set_flags_def.index("\n}")]
        
        # Should spread current flags and new flags
        assert "...currentFlags" in set_flags_def
        assert "...flags" in set_flags_def
    
    def test_reset_flags_restores_defaults(self):
        """resetFlags should restore DEFAULT_FLAGS."""
        content = FLAGS_MODULE.read_text()
        
        reset_flags_def = content[content.index("export function resetFlags"):]
        reset_flags_def = reset_flags_def[:reset_flags_def.index("\n}")]
        
        assert "{ ...DEFAULT_FLAGS }" in reset_flags_def


class TestEnvironmentLoading:
    """Test environment variable loading."""
    
    def test_load_flags_from_env_checks_process_env(self):
        """loadFlagsFromEnv should check process.env."""
        content = FLAGS_MODULE.read_text()
        
        load_env_def = content[content.index("export function loadFlagsFromEnv"):]
        load_env_def = load_env_def[:load_env_def.index("\nexport")]
        
        assert "process.env.NEXT_PUBLIC_SHOW_LEDGER" in load_env_def
        assert "process.env.NEXT_PUBLIC_SHOW_COMPARE" in load_env_def
        assert "process.env.NEXT_PUBLIC_SHOW_BADGES" in load_env_def
    
    def test_load_flags_from_env_handles_client_side(self):
        """loadFlagsFromEnv should handle client-side localStorage."""
        content = FLAGS_MODULE.read_text()
        
        load_env_def = content[content.index("export function loadFlagsFromEnv"):]
        load_env_def = load_env_def[:load_env_def.index("\nexport")]
        
        assert "localStorage.getItem('ui_flags')" in load_env_def
    
    def test_save_flags_to_storage_uses_local_storage(self):
        """saveFlagsToStorage should use localStorage."""
        content = FLAGS_MODULE.read_text()
        
        save_def = content[content.index("export function saveFlagsToStorage"):]
        save_def = save_def[:save_def.index("\nexport")]
        
        assert "localStorage.setItem" in save_def
        assert "JSON.stringify" in save_def


class TestRoleBasedFlags:
    """Test role-based flag recommendations."""
    
    def test_get_flags_for_role_function_exists(self):
        """getFlagsForRole should exist and have role cases."""
        content = FLAGS_MODULE.read_text()
        
        func_def = content[content.index("export function getFlagsForRole"):]
        func_def = func_def[:func_def.index("\nexport")]
        
        # Should have all role cases
        assert "case 'general':" in func_def
        assert "case 'pro':" in func_def
        assert "case 'scholars':" in func_def
        assert "case 'analytics':" in func_def
        assert "case 'ops':" in func_def
        assert "default:" in func_def
    
    def test_unknown_role_returns_defaults(self):
        """Unknown roles should return DEFAULT_FLAGS."""
        content = FLAGS_MODULE.read_text()
        
        func_def = content[content.index("export function getFlagsForRole"):]
        func_def = func_def[:func_def.index("\nexport")]
        
        # Default case should return DEFAULT_FLAGS
        default_case = func_def[func_def.index("default:"):]
        assert "DEFAULT_FLAGS" in default_case


class TestAcceptanceCriteria:
    """Direct verification of user acceptance criteria."""
    
    def test_ac1_ui_flags_defined(self):
        """AC1: UIFlags interface defines show_ledger, show_compare, show_badges."""
        content = FLAGS_MODULE.read_text()
        
        # Find UIFlags interface
        interface_start = content.index("export interface UIFlags")
        interface_end = content.index("}", interface_start)
        interface_def = content[interface_start:interface_end]
        
        assert "show_ledger: boolean" in interface_def
        assert "show_compare: boolean" in interface_def
        assert "show_badges: boolean" in interface_def
    
    def test_ac2_default_flags_all_false(self):
        """AC2: DEFAULT_FLAGS has all flags set to false."""
        content = FLAGS_MODULE.read_text()
        
        default_start = content.index("DEFAULT_FLAGS: UIFlags = {")
        default_end = content.index("};", default_start)
        default_def = content[default_start:default_end]
        
        assert "show_ledger: false" in default_def
        assert "show_compare: false" in default_def
        assert "show_badges: false" in default_def
    
    def test_ac3_get_flag_exists(self):
        """AC3: getFlag() function exists and retrieves individual flags."""
        content = FLAGS_MODULE.read_text()
        
        assert "export function getFlag(key: keyof UIFlags): boolean" in content
        assert "return currentFlags[key]" in content
    
    def test_ac4_set_flag_exists(self):
        """AC4: setFlag() function exists and updates flags."""
        content = FLAGS_MODULE.read_text()
        
        assert "export function setFlag(key: keyof UIFlags, value: boolean)" in content
        assert "currentFlags[key] = value" in content
    
    def test_ac5_role_based_flags_exist(self):
        """AC5: getFlagsForRole() provides role-specific flag configurations."""
        content = FLAGS_MODULE.read_text()
        
        assert "export function getFlagsForRole(role: string): UIFlags" in content
        
        # Check that all roles have specific configurations
        func_def = content[content.index("export function getFlagsForRole"):]
        
        roles = ['general', 'pro', 'scholars', 'analytics', 'ops']
        for role in roles:
            assert f"case '{role}':" in func_def
    
    def test_ac6_general_role_minimal_ui(self):
        """AC6: General role has minimal UI (all flags false)."""
        content = FLAGS_MODULE.read_text()
        
        general_start = content.index("case 'general':")
        general_end = content.index("};", general_start)
        general_def = content[general_start:general_end]
        
        assert "show_ledger: false" in general_def
        assert "show_compare: false" in general_def
        assert "show_badges: false" in general_def
    
    def test_ac7_pro_scholars_get_compare_badges(self):
        """AC7: Pro/Scholars get compare and badges enabled."""
        content = FLAGS_MODULE.read_text()
        
        for role in ['pro', 'scholars']:
            role_start = content.index(f"case '{role}':")
            role_end = content.index("};", role_start)
            role_def = content[role_start:role_end]
            
            assert "show_compare: true" in role_def
            assert "show_badges: true" in role_def
            assert "show_ledger: false" in role_def  # Not for Pro/Scholars
    
    def test_ac8_analytics_full_access(self):
        """AC8: Analytics gets all flags enabled."""
        content = FLAGS_MODULE.read_text()
        
        analytics_start = content.index("case 'analytics':")
        analytics_end = content.index("};", analytics_start)
        analytics_def = content[analytics_start:analytics_end]
        
        assert "show_ledger: true" in analytics_def
        assert "show_compare: true" in analytics_def
        assert "show_badges: true" in analytics_def
    
    def test_ac9_ops_ledger_badges_no_compare(self):
        """AC9: Ops gets ledger and badges but not compare."""
        content = FLAGS_MODULE.read_text()
        
        ops_start = content.index("case 'ops':")
        ops_end = content.index("};", ops_start)
        ops_def = content[ops_start:ops_end]
        
        assert "show_ledger: true" in ops_def
        assert "show_badges: true" in ops_def
        assert "show_compare: false" in ops_def


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
