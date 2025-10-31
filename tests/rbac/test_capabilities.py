"""
Table-driven tests for RBAC capability system.

Verifies role-to-capability mappings and authorization logic.
"""

import pytest
from core.rbac import (
    # Roles
    ROLE_GENERAL,
    ROLE_PRO,
    ROLE_SCHOLARS,
    ROLE_ANALYTICS,
    ROLE_OPS,
    ALL_ROLES,
    # Capabilities
    CAP_READ_PUBLIC,
    CAP_READ_LEDGER_FULL,
    CAP_PROPOSE_HYPOTHESIS,
    CAP_PROPOSE_AURA,
    CAP_WRITE_GRAPH,
    CAP_WRITE_CONTRADICTIONS,
    CAP_MANAGE_ROLES,
    CAP_VIEW_DEBUG,
    ALL_CAPABILITIES,
    # Functions
    has_capability,
    get_role_capabilities,
    validate_role,
)
from core.rbac.capabilities import (
    has_any_capability,
    has_all_capabilities,
    get_missing_capabilities,
)


# ============================================================================
# Capability Matrix Test Data
# ============================================================================

# Table-driven test data: (role, capability, expected_result)
CAPABILITY_TEST_CASES = [
    # GENERAL role - only READ_PUBLIC
    (ROLE_GENERAL, CAP_READ_PUBLIC, True),
    (ROLE_GENERAL, CAP_READ_LEDGER_FULL, False),
    (ROLE_GENERAL, CAP_PROPOSE_HYPOTHESIS, False),
    (ROLE_GENERAL, CAP_PROPOSE_AURA, False),
    (ROLE_GENERAL, CAP_WRITE_GRAPH, False),
    (ROLE_GENERAL, CAP_WRITE_CONTRADICTIONS, False),
    (ROLE_GENERAL, CAP_MANAGE_ROLES, False),
    (ROLE_GENERAL, CAP_VIEW_DEBUG, False),
    
    # PRO role - read + propose
    (ROLE_PRO, CAP_READ_PUBLIC, True),
    (ROLE_PRO, CAP_READ_LEDGER_FULL, True),
    (ROLE_PRO, CAP_PROPOSE_HYPOTHESIS, True),
    (ROLE_PRO, CAP_PROPOSE_AURA, True),
    (ROLE_PRO, CAP_WRITE_GRAPH, False),
    (ROLE_PRO, CAP_WRITE_CONTRADICTIONS, False),
    (ROLE_PRO, CAP_MANAGE_ROLES, False),
    (ROLE_PRO, CAP_VIEW_DEBUG, False),
    
    # SCHOLARS role - same as PRO (read + propose, no writes)
    (ROLE_SCHOLARS, CAP_READ_PUBLIC, True),
    (ROLE_SCHOLARS, CAP_READ_LEDGER_FULL, True),
    (ROLE_SCHOLARS, CAP_PROPOSE_HYPOTHESIS, True),
    (ROLE_SCHOLARS, CAP_PROPOSE_AURA, True),
    (ROLE_SCHOLARS, CAP_WRITE_GRAPH, False),
    (ROLE_SCHOLARS, CAP_WRITE_CONTRADICTIONS, False),
    (ROLE_SCHOLARS, CAP_MANAGE_ROLES, False),
    (ROLE_SCHOLARS, CAP_VIEW_DEBUG, False),
    
    # ANALYTICS role - read + propose + write
    (ROLE_ANALYTICS, CAP_READ_PUBLIC, True),
    (ROLE_ANALYTICS, CAP_READ_LEDGER_FULL, True),
    (ROLE_ANALYTICS, CAP_PROPOSE_HYPOTHESIS, True),
    (ROLE_ANALYTICS, CAP_PROPOSE_AURA, True),
    (ROLE_ANALYTICS, CAP_WRITE_GRAPH, True),
    (ROLE_ANALYTICS, CAP_WRITE_CONTRADICTIONS, True),
    (ROLE_ANALYTICS, CAP_MANAGE_ROLES, False),
    (ROLE_ANALYTICS, CAP_VIEW_DEBUG, False),
    
    # OPS role - read + debug + role management
    (ROLE_OPS, CAP_READ_PUBLIC, True),
    (ROLE_OPS, CAP_READ_LEDGER_FULL, True),
    (ROLE_OPS, CAP_PROPOSE_HYPOTHESIS, False),
    (ROLE_OPS, CAP_PROPOSE_AURA, False),
    (ROLE_OPS, CAP_WRITE_GRAPH, False),
    (ROLE_OPS, CAP_WRITE_CONTRADICTIONS, False),
    (ROLE_OPS, CAP_MANAGE_ROLES, True),  # NEW: Ops can manage roles
    (ROLE_OPS, CAP_VIEW_DEBUG, True),
]


# Test cases for invalid/unknown roles and capabilities
INVALID_TEST_CASES = [
    # Unknown roles should deny all capabilities
    ("unknown_role", CAP_READ_PUBLIC, False),
    ("admin", CAP_MANAGE_ROLES, False),
    ("superuser", CAP_WRITE_GRAPH, False),
    ("", CAP_READ_PUBLIC, False),
    (None, CAP_READ_PUBLIC, False),
    
    # Valid roles with unknown capabilities should return False
    (ROLE_GENERAL, "UNKNOWN_CAPABILITY", False),
    (ROLE_PRO, "READ_EVERYTHING", False),
    (ROLE_ANALYTICS, "", False),
]


# ============================================================================
# Test Classes
# ============================================================================

class TestCapabilityMatrix:
    """Test the complete role-to-capability matrix."""
    
    @pytest.mark.parametrize("role,capability,expected", CAPABILITY_TEST_CASES)
    def test_has_capability_matrix(self, role, capability, expected):
        """Test has_capability for all role/capability combinations."""
        result = has_capability(role, capability)
        assert result == expected, (
            f"Role '{role}' capability '{capability}' should be {expected}, got {result}"
        )
    
    @pytest.mark.parametrize("role,capability,expected", INVALID_TEST_CASES)
    def test_has_capability_invalid_inputs(self, role, capability, expected):
        """Test has_capability with invalid roles and capabilities."""
        result = has_capability(role, capability)
        assert result == expected, (
            f"Invalid input (role='{role}', cap='{capability}') should return {expected}, got {result}"
        )


class TestRoleCapabilitySets:
    """Test getting complete capability sets for roles."""
    
    def test_general_capabilities(self):
        """General role should only have READ_PUBLIC."""
        caps = get_role_capabilities(ROLE_GENERAL)
        assert caps == {CAP_READ_PUBLIC}
    
    def test_pro_capabilities(self):
        """Pro role should have read + propose capabilities."""
        caps = get_role_capabilities(ROLE_PRO)
        assert caps == {
            CAP_READ_PUBLIC,
            CAP_READ_LEDGER_FULL,
            CAP_PROPOSE_HYPOTHESIS,
            CAP_PROPOSE_AURA,
        }
    
    def test_scholars_capabilities(self):
        """Scholars role should match Pro (read + propose, no writes)."""
        scholars_caps = get_role_capabilities(ROLE_SCHOLARS)
        pro_caps = get_role_capabilities(ROLE_PRO)
        
        # Should be identical to Pro
        assert scholars_caps == pro_caps
        
        # Should explicitly NOT have write capabilities
        assert CAP_WRITE_GRAPH not in scholars_caps
        assert CAP_WRITE_CONTRADICTIONS not in scholars_caps
    
    def test_analytics_capabilities(self):
        """Analytics role should have read + propose + write capabilities."""
        caps = get_role_capabilities(ROLE_ANALYTICS)
        assert caps == {
            CAP_READ_PUBLIC,
            CAP_READ_LEDGER_FULL,
            CAP_PROPOSE_HYPOTHESIS,
            CAP_PROPOSE_AURA,
            CAP_WRITE_GRAPH,
            CAP_WRITE_CONTRADICTIONS,
        }
    
    def test_ops_capabilities(self):
        """Ops role should have read + debug + role management capabilities."""
        caps = get_role_capabilities(ROLE_OPS)
        assert caps == {
            CAP_READ_PUBLIC,
            CAP_READ_LEDGER_FULL,
            CAP_VIEW_DEBUG,
            CAP_MANAGE_ROLES,  # NEW: Ops can manage roles
        }
    
    def test_unknown_role_capabilities(self):
        """Unknown role should return empty set."""
        caps = get_role_capabilities("unknown_role")
        assert caps == set()
        
        caps = get_role_capabilities("")
        assert caps == set()


class TestRoleValidation:
    """Test role validation functions."""
    
    @pytest.mark.parametrize("role", [
        ROLE_GENERAL,
        ROLE_PRO,
        ROLE_SCHOLARS,
        ROLE_ANALYTICS,
        ROLE_OPS,
    ])
    def test_validate_known_roles(self, role):
        """All defined roles should validate as True."""
        assert validate_role(role) is True
    
    @pytest.mark.parametrize("role", [
        "unknown",
        "admin",
        "superuser",
        "guest",
        "",
        None,
    ])
    def test_validate_unknown_roles(self, role):
        """Unknown roles should validate as False."""
        assert validate_role(role) is False
    
    def test_role_count(self):
        """Verify we have exactly 5 defined roles."""
        assert len(ALL_ROLES) == 5
        assert ROLE_GENERAL in ALL_ROLES
        assert ROLE_PRO in ALL_ROLES
        assert ROLE_SCHOLARS in ALL_ROLES
        assert ROLE_ANALYTICS in ALL_ROLES
        assert ROLE_OPS in ALL_ROLES


class TestCapabilityConstants:
    """Test capability constant definitions."""
    
    def test_capability_count(self):
        """Verify we have exactly 8 defined capabilities."""
        assert len(ALL_CAPABILITIES) == 8
    
    def test_all_capabilities_defined(self):
        """Verify all expected capabilities are defined."""
        expected_caps = {
            CAP_READ_PUBLIC,
            CAP_READ_LEDGER_FULL,
            CAP_PROPOSE_HYPOTHESIS,
            CAP_PROPOSE_AURA,
            CAP_WRITE_GRAPH,
            CAP_WRITE_CONTRADICTIONS,
            CAP_MANAGE_ROLES,
            CAP_VIEW_DEBUG,
        }
        assert ALL_CAPABILITIES == expected_caps
    
    def test_capability_string_values(self):
        """Verify capability constants have expected string values."""
        assert CAP_READ_PUBLIC == "READ_PUBLIC"
        assert CAP_READ_LEDGER_FULL == "READ_LEDGER_FULL"
        assert CAP_PROPOSE_HYPOTHESIS == "PROPOSE_HYPOTHESIS"
        assert CAP_PROPOSE_AURA == "PROPOSE_AURA"
        assert CAP_WRITE_GRAPH == "WRITE_GRAPH"
        assert CAP_WRITE_CONTRADICTIONS == "WRITE_CONTRADICTIONS"
        assert CAP_MANAGE_ROLES == "MANAGE_ROLES"
        assert CAP_VIEW_DEBUG == "VIEW_DEBUG"


class TestCapabilityDenials:
    """Test that roles are properly denied inappropriate capabilities."""
    
    def test_general_has_no_write_capabilities(self):
        """General role should have no write capabilities."""
        assert not has_capability(ROLE_GENERAL, CAP_WRITE_GRAPH)
        assert not has_capability(ROLE_GENERAL, CAP_WRITE_CONTRADICTIONS)
        assert not has_capability(ROLE_GENERAL, CAP_MANAGE_ROLES)
    
    def test_general_has_no_propose_capabilities(self):
        """General role should have no propose capabilities."""
        assert not has_capability(ROLE_GENERAL, CAP_PROPOSE_HYPOTHESIS)
        assert not has_capability(ROLE_GENERAL, CAP_PROPOSE_AURA)
    
    def test_general_has_no_debug_capabilities(self):
        """General role should not have debug access."""
        assert not has_capability(ROLE_GENERAL, CAP_VIEW_DEBUG)
    
    def test_pro_has_no_write_capabilities(self):
        """Pro role should have no direct write capabilities."""
        assert not has_capability(ROLE_PRO, CAP_WRITE_GRAPH)
        assert not has_capability(ROLE_PRO, CAP_WRITE_CONTRADICTIONS)
    
    def test_scholars_has_no_write_capabilities(self):
        """Scholars role should have no write capabilities (suggest-only)."""
        assert not has_capability(ROLE_SCHOLARS, CAP_WRITE_GRAPH)
        assert not has_capability(ROLE_SCHOLARS, CAP_WRITE_CONTRADICTIONS)
    
    def test_ops_has_no_write_capabilities(self):
        """Ops role should have no write capabilities."""
        assert not has_capability(ROLE_OPS, CAP_WRITE_GRAPH)
        assert not has_capability(ROLE_OPS, CAP_WRITE_CONTRADICTIONS)
    
    def test_ops_has_no_propose_capabilities(self):
        """Ops role should not be able to propose hypotheses or auras."""
        assert not has_capability(ROLE_OPS, CAP_PROPOSE_HYPOTHESIS)
        assert not has_capability(ROLE_OPS, CAP_PROPOSE_AURA)
    
    def test_only_ops_has_manage_roles(self):
        """Only ops role should have MANAGE_ROLES capability."""
        # Ops should have it
        assert has_capability(ROLE_OPS, CAP_MANAGE_ROLES), (
            "Ops role should have MANAGE_ROLES capability"
        )
        
        # No other role should have it
        for role in [ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS]:
            assert not has_capability(role, CAP_MANAGE_ROLES), (
                f"Role '{role}' should not have MANAGE_ROLES capability"
            )


class TestRoleComparisons:
    """Test comparative capabilities between roles."""
    
    def test_pro_vs_scholars_same_capabilities(self):
        """Pro and Scholars should have identical capabilities."""
        pro_caps = get_role_capabilities(ROLE_PRO)
        scholars_caps = get_role_capabilities(ROLE_SCHOLARS)
        assert pro_caps == scholars_caps
    
    def test_analytics_superset_of_pro(self):
        """Analytics should have all Pro capabilities plus write capabilities."""
        pro_caps = get_role_capabilities(ROLE_PRO)
        analytics_caps = get_role_capabilities(ROLE_ANALYTICS)
        
        # Analytics should include all Pro capabilities
        assert pro_caps.issubset(analytics_caps)
        
        # Analytics should have additional write capabilities
        assert CAP_WRITE_GRAPH in analytics_caps
        assert CAP_WRITE_CONTRADICTIONS in analytics_caps
    
    def test_general_minimal_capabilities(self):
        """General should have the smallest capability set."""
        general_caps = get_role_capabilities(ROLE_GENERAL)
        
        for role in [ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS]:
            other_caps = get_role_capabilities(role)
            # General's capabilities should be a subset of or equal to others
            # (except it's actually just READ_PUBLIC which all have)
            assert CAP_READ_PUBLIC in other_caps
        
        # General should only have 1 capability
        assert len(general_caps) == 1


class TestCapabilityHelperFunctions:
    """Test additional capability helper functions."""
    
    def test_has_any_capability(self):
        """Test has_any_capability function."""
        # General has READ_PUBLIC but not WRITE_GRAPH
        assert has_any_capability(ROLE_GENERAL, [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])
        assert not has_any_capability(ROLE_GENERAL, [CAP_WRITE_GRAPH, CAP_MANAGE_ROLES])
        
        # Analytics has both
        assert has_any_capability(ROLE_ANALYTICS, [CAP_WRITE_GRAPH, CAP_MANAGE_ROLES])
    
    def test_has_all_capabilities(self):
        """Test has_all_capabilities function."""
        # Pro has both READ_PUBLIC and READ_LEDGER_FULL
        assert has_all_capabilities(ROLE_PRO, [CAP_READ_PUBLIC, CAP_READ_LEDGER_FULL])
        
        # General doesn't have READ_LEDGER_FULL
        assert not has_all_capabilities(ROLE_GENERAL, [CAP_READ_PUBLIC, CAP_READ_LEDGER_FULL])
        
        # Analytics has all these
        assert has_all_capabilities(ROLE_ANALYTICS, [
            CAP_READ_PUBLIC,
            CAP_WRITE_GRAPH,
            CAP_WRITE_CONTRADICTIONS,
        ])
    
    def test_get_missing_capabilities(self):
        """Test get_missing_capabilities function."""
        # General is missing WRITE_GRAPH
        missing = get_missing_capabilities(ROLE_GENERAL, [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])
        assert missing == {CAP_WRITE_GRAPH}
        
        # Analytics has both
        missing = get_missing_capabilities(ROLE_ANALYTICS, [CAP_READ_PUBLIC, CAP_WRITE_GRAPH])
        assert missing == set()
        
        # Pro is missing write capabilities
        missing = get_missing_capabilities(ROLE_PRO, [
            CAP_READ_PUBLIC,
            CAP_WRITE_GRAPH,
            CAP_WRITE_CONTRADICTIONS,
        ])
        assert missing == {CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS}


class TestCaseSensitivity:
    """Test that role names are case-insensitive."""
    
    @pytest.mark.parametrize("role_variant", [
        "general", "General", "GENERAL", "GeNeRaL"
    ])
    def test_role_case_insensitive(self, role_variant):
        """Role names should be case-insensitive."""
        assert has_capability(role_variant, CAP_READ_PUBLIC)
        assert validate_role(role_variant)
    
    @pytest.mark.parametrize("role,expected_caps", [
        ("PRO", 4),
        ("Pro", 4),
        ("SCHOLARS", 4),
        ("Analytics", 6),
        ("OPS", 4),
    ])
    def test_get_capabilities_case_insensitive(self, role, expected_caps):
        """get_role_capabilities should be case-insensitive."""
        caps = get_role_capabilities(role)
        assert len(caps) == expected_caps


class TestWeirdCombos:
    """Test weird/edge cases and denial of unexpected capability combinations."""
    
    def test_empty_role_denied(self):
        """Empty role string should be denied all capabilities."""
        for cap in ALL_CAPABILITIES:
            assert not has_capability("", cap)
    
    def test_none_role_denied(self):
        """None role should be denied all capabilities."""
        for cap in ALL_CAPABILITIES:
            assert not has_capability(None, cap)
    
    def test_whitespace_role_denied(self):
        """Whitespace-only role should be denied all capabilities."""
        for cap in ALL_CAPABILITIES:
            assert not has_capability("   ", cap)
    
    def test_special_chars_role_denied(self):
        """Roles with special characters should be denied."""
        weird_roles = ["general!", "pro@123", "ops#$%", "DROP TABLE users;"]
        for role in weird_roles:
            for cap in ALL_CAPABILITIES:
                assert not has_capability(role, cap)
    
    def test_no_privilege_escalation(self):
        """Lower privilege roles should not have higher privilege capabilities."""
        # General should not have any Analytics-exclusive capabilities
        general_caps = get_role_capabilities(ROLE_GENERAL)
        analytics_exclusive = {CAP_WRITE_GRAPH, CAP_WRITE_CONTRADICTIONS}
        assert general_caps.isdisjoint(analytics_exclusive)
        
        # Pro/Scholars should not have write capabilities
        pro_caps = get_role_capabilities(ROLE_PRO)
        assert pro_caps.isdisjoint(analytics_exclusive)
        
        # Ops should not have propose or write capabilities
        ops_caps = get_role_capabilities(ROLE_OPS)
        ops_should_not_have = {
            CAP_PROPOSE_HYPOTHESIS,
            CAP_PROPOSE_AURA,
            CAP_WRITE_GRAPH,
            CAP_WRITE_CONTRADICTIONS,
        }
        assert ops_caps.isdisjoint(ops_should_not_have)
    
    def test_unknown_capability_always_false(self):
        """Unknown capabilities should always return False for any role."""
        unknown_caps = ["DELETE_EVERYTHING", "SUDO", "ROOT", "ADMIN"]
        for role in ALL_ROLES:
            for cap in unknown_caps:
                assert not has_capability(role, cap)


class TestRoleMetadata:
    """Test role metadata and description functions."""
    
    def test_all_roles_have_descriptions(self):
        """All roles should have descriptions."""
        from core.rbac.roles import get_role_description, list_all_roles
        
        for role in ALL_ROLES:
            description = get_role_description(role)
            assert description != ""
            assert len(description) > 10  # Should be meaningful
    
    def test_list_all_roles(self):
        """list_all_roles should return complete metadata."""
        from core.rbac.roles import list_all_roles
        
        all_role_data = list_all_roles()
        
        # Should have all 5 roles
        assert len(all_role_data) == 5
        
        # Each role should have description and capabilities
        for role in ALL_ROLES:
            assert role in all_role_data
            assert "description" in all_role_data[role]
            assert "capabilities" in all_role_data[role]
            assert isinstance(all_role_data[role]["capabilities"], list)
            assert len(all_role_data[role]["capabilities"]) > 0


# ============================================================================
# Summary Test
# ============================================================================

class TestCompleteCoverageMatrix:
    """Comprehensive test to verify the entire capability matrix is covered."""
    
    def test_all_role_capability_combinations_tested(self):
        """Verify we test all role × capability combinations."""
        # Count expected combinations: 5 roles × 8 capabilities = 40
        expected_combinations = len(ALL_ROLES) * len(ALL_CAPABILITIES)
        
        # Verify our test data covers all combinations
        tested_combinations = set()
        for role, capability, _ in CAPABILITY_TEST_CASES:
            tested_combinations.add((role, capability))
        
        assert len(tested_combinations) == expected_combinations, (
            f"Expected {expected_combinations} combinations, "
            f"but only tested {len(tested_combinations)}"
        )
    
    def test_test_coverage_summary(self):
        """Generate a summary of test coverage."""
        # This test always passes but prints useful coverage info
        print("\n" + "="*70)
        print("RBAC Test Coverage Summary")
        print("="*70)
        print(f"Roles defined: {len(ALL_ROLES)}")
        print(f"Capabilities defined: {len(ALL_CAPABILITIES)}")
        print(f"Test cases (valid): {len(CAPABILITY_TEST_CASES)}")
        print(f"Test cases (invalid): {len(INVALID_TEST_CASES)}")
        print(f"Total test cases: {len(CAPABILITY_TEST_CASES) + len(INVALID_TEST_CASES)}")
        print("="*70)
        
        # Print capability summary for each role
        for role in sorted(ALL_ROLES):
            caps = get_role_capabilities(role)
            print(f"\n{role.upper()}: {len(caps)} capabilities")
            for cap in sorted(caps):
                print(f"  ✓ {cap}")
        
        print("\n" + "="*70)
        assert True  # Always pass, just for info
