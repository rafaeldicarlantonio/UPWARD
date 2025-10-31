"""
Tests for external source role gating and feature flag control.

Verifies that external comparison access is properly gated by:
1. Feature flag (flags.external_compare)
2. User roles vs allowed_roles_for_external from policy
"""

import os
import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import patch, Mock

# Set up mock environment variables before importing modules
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
os.environ.setdefault("PINECONE_EXPLICATE_INDEX", "test-explicate")
os.environ.setdefault("PINECONE_IMPLICATE_INDEX", "test-implicate")

from feature_flags import get_feature_flag, set_feature_flag
from core.policy import can_use_external_compare
from core.config_loader import get_loader, reset_loader, ConfigLoader
from core.rbac import ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_config_dir():
    """Create temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def default_policy_config():
    """Default policy with standard allowed roles."""
    return {
        "max_external_sources_per_run": 6,
        "max_total_external_chars": 2400,
        "allowed_roles_for_external": ["pro", "scholars", "analytics"],
        "timeout_ms_per_request": 2000,
        "rate_limit_per_domain_per_min": 6,
        "tie_break": "prefer_internal",
        "redact_patterns": []
    }


@pytest.fixture
def create_policy_file(temp_config_dir, default_policy_config):
    """Create policy file with standard config."""
    policy_path = temp_config_dir / "policy.yaml"
    with open(policy_path, 'w') as f:
        yaml.dump(default_policy_config, f)
    return policy_path


@pytest.fixture(autouse=True)
def reset_feature_flags():
    """Reset feature flags before each test."""
    # Mock the feature flag for testing
    with patch('feature_flags.get_feature_flag') as mock_get:
        # Default to False
        mock_get.return_value = False
        yield mock_get


@pytest.fixture(autouse=True)
def reset_config_loader():
    """Reset config loader before each test."""
    reset_loader()
    yield
    reset_loader()


# ============================================================================
# Feature Flag Tests
# ============================================================================

class TestFeatureFlagControl:
    """Test that feature flag controls access."""
    
    def test_flag_off_denies_all_roles(self, create_policy_file, reset_feature_flags):
        """Test that flag off denies all roles, even allowed ones."""
        # Setup loader with policy
        loader = ConfigLoader(policy_path=str(create_policy_file))
        
        # Flag is off (mock returns False by default)
        reset_feature_flags.return_value = False
        
        # All roles should be denied
        assert can_use_external_compare([ROLE_GENERAL]) is False
        assert can_use_external_compare([ROLE_PRO]) is False
        assert can_use_external_compare([ROLE_SCHOLARS]) is False
        assert can_use_external_compare([ROLE_ANALYTICS]) is False
        assert can_use_external_compare([ROLE_OPS]) is False
    
    def test_flag_on_allows_check(self, create_policy_file, reset_feature_flags):
        """Test that flag on allows role-based check to proceed."""
        # Setup loader with policy
        loader = ConfigLoader(policy_path=str(create_policy_file))
        
        # Turn flag on
        reset_feature_flags.return_value = True
        
        # Allowed roles should pass
        assert can_use_external_compare([ROLE_PRO]) is True
        assert can_use_external_compare([ROLE_SCHOLARS]) is True
        assert can_use_external_compare([ROLE_ANALYTICS]) is True
        
        # Disallowed roles should fail
        assert can_use_external_compare([ROLE_GENERAL]) is False
        assert can_use_external_compare([ROLE_OPS]) is False


# ============================================================================
# Role-Based Access Tests
# ============================================================================

class TestRoleBasedAccess:
    """Test role-based access control."""
    
    def test_general_always_denied(self, create_policy_file, reset_feature_flags):
        """Test that general users are always denied."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # General should be denied
        assert can_use_external_compare([ROLE_GENERAL]) is False
        
        # Even with multiple roles, if none are allowed
        assert can_use_external_compare([ROLE_GENERAL, ROLE_OPS]) is False
    
    def test_pro_allowed_when_flag_on(self, create_policy_file, reset_feature_flags):
        """Test that pro users are allowed when flag is on."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        assert can_use_external_compare([ROLE_PRO]) is True
    
    def test_scholars_allowed_when_flag_on(self, create_policy_file, reset_feature_flags):
        """Test that scholars are allowed when flag is on."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        assert can_use_external_compare([ROLE_SCHOLARS]) is True
    
    def test_analytics_allowed_when_flag_on(self, create_policy_file, reset_feature_flags):
        """Test that analytics users are allowed when flag is on."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        assert can_use_external_compare([ROLE_ANALYTICS]) is True
    
    def test_ops_denied_by_default_policy(self, create_policy_file, reset_feature_flags):
        """Test that ops is denied by default policy."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # Ops not in default allowed_roles_for_external
        assert can_use_external_compare([ROLE_OPS]) is False
    
    def test_multiple_roles_with_one_allowed(self, create_policy_file, reset_feature_flags):
        """Test user with multiple roles where one is allowed."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # User has general + pro roles
        assert can_use_external_compare([ROLE_GENERAL, ROLE_PRO]) is True
        
        # User has ops + analytics roles
        assert can_use_external_compare([ROLE_OPS, ROLE_ANALYTICS]) is True
    
    def test_multiple_roles_none_allowed(self, create_policy_file, reset_feature_flags):
        """Test user with multiple roles but none allowed."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # User has only disallowed roles
        assert can_use_external_compare([ROLE_GENERAL, ROLE_OPS]) is False
    
    def test_empty_roles_list(self, create_policy_file, reset_feature_flags):
        """Test empty roles list is denied."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        assert can_use_external_compare([]) is False


# ============================================================================
# Policy Configuration Tests
# ============================================================================

class TestPolicyConfiguration:
    """Test different policy configurations."""
    
    def test_custom_allowed_roles(self, temp_config_dir, reset_feature_flags):
        """Test policy with custom allowed roles."""
        # Create policy with only analytics allowed
        policy_data = {
            "max_external_sources_per_run": 3,
            "allowed_roles_for_external": ["analytics"],
            "timeout_ms_per_request": 2000,
            "rate_limit_per_domain_per_min": 6,
            "tie_break": "prefer_internal"
        }
        
        policy_path = temp_config_dir / "custom_policy.yaml"
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        # Force a new loader with this policy
        with patch('core.config_loader.get_loader') as mock_loader:
            loader = ConfigLoader(policy_path=str(policy_path))
            mock_loader.return_value = loader
            reset_feature_flags.return_value = True
            
            # Only analytics should be allowed
            assert can_use_external_compare([ROLE_ANALYTICS]) is True
            
            # Others should be denied
            assert can_use_external_compare([ROLE_PRO]) is False
            assert can_use_external_compare([ROLE_SCHOLARS]) is False
            assert can_use_external_compare([ROLE_GENERAL]) is False
    
    def test_policy_allows_all_roles(self, temp_config_dir, reset_feature_flags):
        """Test policy that allows all roles."""
        policy_data = {
            "allowed_roles_for_external": ["general", "pro", "scholars", "analytics", "ops"],
            "timeout_ms_per_request": 2000
        }
        
        policy_path = temp_config_dir / "all_roles_policy.yaml"
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        with patch('core.config_loader.get_loader') as mock_loader:
            loader = ConfigLoader(policy_path=str(policy_path))
            mock_loader.return_value = loader
            reset_feature_flags.return_value = True
            
            # All roles should be allowed
            assert can_use_external_compare([ROLE_GENERAL]) is True
            assert can_use_external_compare([ROLE_PRO]) is True
            assert can_use_external_compare([ROLE_SCHOLARS]) is True
            assert can_use_external_compare([ROLE_ANALYTICS]) is True
            assert can_use_external_compare([ROLE_OPS]) is True
    
    def test_policy_with_empty_allowed_roles(self, temp_config_dir, reset_feature_flags):
        """Test policy with empty allowed roles list."""
        policy_data = {
            "allowed_roles_for_external": [],
            "timeout_ms_per_request": 2000
        }
        
        policy_path = temp_config_dir / "empty_roles_policy.yaml"
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        with patch('core.config_loader.get_loader') as mock_loader:
            loader = ConfigLoader(policy_path=str(policy_path))
            mock_loader.return_value = loader
            reset_feature_flags.return_value = True
            
            # No roles should be allowed
            assert can_use_external_compare([ROLE_PRO]) is False
            assert can_use_external_compare([ROLE_ANALYTICS]) is False


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_missing_policy_file_uses_defaults(self, temp_config_dir, reset_feature_flags):
        """Test that missing policy file uses safe defaults."""
        # Create loader with non-existent policy file
        nonexistent = temp_config_dir / "nonexistent.yaml"
        loader = ConfigLoader(policy_path=str(nonexistent))
        
        reset_feature_flags.return_value = True
        
        # Should use default allowed roles (pro, scholars, analytics)
        assert can_use_external_compare([ROLE_PRO]) is True
        assert can_use_external_compare([ROLE_SCHOLARS]) is True
        assert can_use_external_compare([ROLE_ANALYTICS]) is True
        assert can_use_external_compare([ROLE_GENERAL]) is False
    
    def test_malformed_policy_file_uses_defaults(self, temp_config_dir, reset_feature_flags):
        """Test that malformed policy file uses safe defaults."""
        policy_path = temp_config_dir / "bad_policy.yaml"
        with open(policy_path, 'w') as f:
            f.write("invalid: yaml: syntax: [")
        
        loader = ConfigLoader(policy_path=str(policy_path))
        reset_feature_flags.return_value = True
        
        # Should use default allowed roles
        assert can_use_external_compare([ROLE_PRO]) is True
        assert can_use_external_compare([ROLE_ANALYTICS]) is True
        assert can_use_external_compare([ROLE_GENERAL]) is False
    


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete scenarios."""
    
    def test_typical_production_scenario(self, create_policy_file, reset_feature_flags):
        """Test typical production scenario."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        
        # Initially flag is off
        reset_feature_flags.return_value = False
        assert can_use_external_compare([ROLE_PRO]) is False
        
        # Enable feature
        reset_feature_flags.return_value = True
        
        # Pro users can now access
        assert can_use_external_compare([ROLE_PRO]) is True
        
        # General users still cannot
        assert can_use_external_compare([ROLE_GENERAL]) is False
        
        # Disable feature again
        reset_feature_flags.return_value = False
        assert can_use_external_compare([ROLE_PRO]) is False
    
    def test_gradual_rollout_scenario(self, temp_config_dir, reset_feature_flags):
        """Test gradual rollout to different role tiers."""
        reset_feature_flags.return_value = True
        policy_path = temp_config_dir / "rollout_policy.yaml"
        
        # Phase 1: Only analytics
        policy_data = {
            "allowed_roles_for_external": ["analytics"],
            "timeout_ms_per_request": 2000
        }
        
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        with patch('core.config_loader.get_loader') as mock_loader:
            loader1 = ConfigLoader(policy_path=str(policy_path))
            mock_loader.return_value = loader1
            
            assert can_use_external_compare([ROLE_ANALYTICS]) is True
            assert can_use_external_compare([ROLE_PRO]) is False
        
        # Phase 2: Add scholars
        policy_data["allowed_roles_for_external"] = ["analytics", "scholars"]
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        with patch('core.config_loader.get_loader') as mock_loader:
            loader2 = ConfigLoader(policy_path=str(policy_path))
            mock_loader.return_value = loader2
            
            assert can_use_external_compare([ROLE_ANALYTICS]) is True
            assert can_use_external_compare([ROLE_SCHOLARS]) is True
            assert can_use_external_compare([ROLE_PRO]) is False
        
        # Phase 3: Add pro
        policy_data["allowed_roles_for_external"] = ["analytics", "scholars", "pro"]
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        with patch('core.config_loader.get_loader') as mock_loader:
            loader3 = ConfigLoader(policy_path=str(policy_path))
            mock_loader.return_value = loader3
            
            assert can_use_external_compare([ROLE_ANALYTICS]) is True
            assert can_use_external_compare([ROLE_SCHOLARS]) is True
            assert can_use_external_compare([ROLE_PRO]) is True
            assert can_use_external_compare([ROLE_GENERAL]) is False


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================

class TestAcceptanceCriteria:
    """Verify all acceptance criteria are met."""
    
    def test_general_denied_even_when_flag_on(self, create_policy_file, reset_feature_flags):
        """
        Acceptance: General users denied even when flag is on.
        """
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # General should always be denied with standard policy
        assert can_use_external_compare([ROLE_GENERAL]) is False
    
    def test_pro_allowed_when_flag_and_policy_allow(self, create_policy_file, reset_feature_flags):
        """
        Acceptance: Pro allowed when flag and policy allow.
        """
        loader = ConfigLoader(policy_path=str(create_policy_file))
        
        # Denied when flag off
        reset_feature_flags.return_value = False
        assert can_use_external_compare([ROLE_PRO]) is False
        
        # Allowed when flag on and in policy
        reset_feature_flags.return_value = True
        assert can_use_external_compare([ROLE_PRO]) is True
    
    def test_scholars_allowed_when_flag_and_policy_allow(self, create_policy_file, reset_feature_flags):
        """
        Acceptance: Scholars allowed when flag and policy allow.
        """
        loader = ConfigLoader(policy_path=str(create_policy_file))
        
        # Denied when flag off
        reset_feature_flags.return_value = False
        assert can_use_external_compare([ROLE_SCHOLARS]) is False
        
        # Allowed when flag on and in policy
        reset_feature_flags.return_value = True
        assert can_use_external_compare([ROLE_SCHOLARS]) is True
    
    def test_analytics_allowed_when_flag_and_policy_allow(self, create_policy_file, reset_feature_flags):
        """
        Acceptance: Analytics allowed when flag and policy allow.
        """
        loader = ConfigLoader(policy_path=str(create_policy_file))
        
        # Denied when flag off
        reset_feature_flags.return_value = False
        assert can_use_external_compare([ROLE_ANALYTICS]) is False
        
        # Allowed when flag on and in policy
        reset_feature_flags.return_value = True
        assert can_use_external_compare([ROLE_ANALYTICS]) is True
    
    def test_flag_off_overrides_policy(self, create_policy_file, reset_feature_flags):
        """
        Acceptance: Flag off denies all, regardless of policy.
        """
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = False
        
        # Even allowed roles should be denied
        assert can_use_external_compare([ROLE_PRO]) is False
        assert can_use_external_compare([ROLE_SCHOLARS]) is False
        assert can_use_external_compare([ROLE_ANALYTICS]) is False
    
    def test_policy_not_in_allowed_denies(self, temp_config_dir, reset_feature_flags):
        """
        Acceptance: Roles not in policy.allowed_roles_for_external are denied.
        """
        # Create policy with only pro allowed
        policy_data = {
            "allowed_roles_for_external": ["pro"],
            "timeout_ms_per_request": 2000
        }
        
        policy_path = temp_config_dir / "pro_only_policy.yaml"
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        with patch('core.config_loader.get_loader') as mock_loader:
            loader = ConfigLoader(policy_path=str(policy_path))
            mock_loader.return_value = loader
            reset_feature_flags.return_value = True
            
            # Only pro should be allowed
            assert can_use_external_compare([ROLE_PRO]) is True
            
            # Others should be denied
            assert can_use_external_compare([ROLE_SCHOLARS]) is False
            assert can_use_external_compare([ROLE_ANALYTICS]) is False
            assert can_use_external_compare([ROLE_GENERAL]) is False
            assert can_use_external_compare([ROLE_OPS]) is False


# ============================================================================
# Documentation Tests
# ============================================================================

class TestDocumentationExamples:
    """Test examples from documentation."""
    
    def test_docstring_example_general(self, create_policy_file, reset_feature_flags):
        """Test docstring example for general user."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # From docstring: can_use_external_compare(["general"]) -> False
        assert can_use_external_compare(["general"]) is False
    
    def test_docstring_example_pro(self, create_policy_file, reset_feature_flags):
        """Test docstring example for pro user."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # From docstring: can_use_external_compare(["pro"]) -> True
        assert can_use_external_compare(["pro"]) is True
    
    def test_docstring_example_multiple_roles(self, create_policy_file, reset_feature_flags):
        """Test docstring example for user with multiple roles."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        reset_feature_flags.return_value = True
        
        # From docstring: can_use_external_compare(["analytics", "general"]) -> True
        assert can_use_external_compare(["analytics", "general"]) is True


# ============================================================================
# Summary Test
# ============================================================================

class TestComprehensiveSummary:
    """Comprehensive test verifying all requirements."""
    
    def test_all_role_permutations(self, create_policy_file, reset_feature_flags):
        """Test all role permutations with flag on/off."""
        loader = ConfigLoader(policy_path=str(create_policy_file))
        
        roles_to_test = [
            (ROLE_GENERAL, False),      # Never allowed
            (ROLE_PRO, True),           # Allowed in default policy
            (ROLE_SCHOLARS, True),      # Allowed in default policy
            (ROLE_ANALYTICS, True),     # Allowed in default policy
            (ROLE_OPS, False),          # Not allowed in default policy
        ]
        
        # Test with flag off - all should be denied
        reset_feature_flags.return_value = False
        for role, _ in roles_to_test:
            assert can_use_external_compare([role]) is False, \
                f"Role {role} should be denied when flag is off"
        
        # Test with flag on - check policy
        reset_feature_flags.return_value = True
        for role, expected_allowed in roles_to_test:
            result = can_use_external_compare([role])
            assert result is expected_allowed, \
                f"Role {role} expected {expected_allowed}, got {result}"
