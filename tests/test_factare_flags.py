# tests/test_factare_flags.py — Comprehensive tests for Factare flags and policy

import unittest
import sys
import os
import re
from unittest.mock import patch, MagicMock

# Add workspace to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the config loading before importing policy
with patch.dict(os.environ, {
    "OPENAI_API_KEY": "test-key",
    "SUPABASE_URL": "https://test.supabase.co",
    "PINECONE_API_KEY": "test-pinecone-key",
    "PINECONE_INDEX": "test-index",
    "PINECONE_EXPLICATE_INDEX": "test-explicate",
    "PINECONE_IMPLICATE_INDEX": "test-implicate",
}):
    from core.policy import (
        is_external_allowed,
        is_source_whitelisted,
        can_access_factare,
        get_max_sources,
        get_external_timeout_ms,
        get_pareto_threshold,
        validate_source_url,
        get_user_policy_summary,
        ROLE_PERMISSIONS,
        EXTERNAL_WHITELIST_PATTERNS
    )

class TestFactarePolicy(unittest.TestCase):
    """Test Factare policy helpers and access control."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.admin_roles = ["admin"]
        self.ops_roles = ["ops"]
        self.pro_roles = ["pro"]
        self.scholars_roles = ["scholars"]
        self.analytics_roles = ["analytics"]
        self.general_roles = ["general"]
        self.user_roles = ["user"]
        self.mixed_roles = ["pro", "analytics"]
        self.unknown_roles = ["unknown_role"]
    
    def test_is_external_allowed_feature_flag_disabled(self):
        """Test that external access is denied when feature flag is disabled."""
        # All roles should be denied when feature flag is False
        for roles in [self.admin_roles, self.ops_roles, self.pro_roles, self.scholars_roles, self.analytics_roles]:
            with self.subTest(roles=roles):
                result = is_external_allowed(roles, False)
                self.assertFalse(result, f"External access should be denied for {roles} when feature flag is disabled")
    
    def test_is_external_allowed_feature_flag_enabled(self):
        """Test external access when feature flag is enabled."""
        # Admin, ops, pro, scholars should be allowed
        for roles in [self.admin_roles, self.ops_roles, self.pro_roles, self.scholars_roles]:
            with self.subTest(roles=roles):
                result = is_external_allowed(roles, True)
                self.assertTrue(result, f"External access should be allowed for {roles} when feature flag is enabled")
        
        # Analytics should be denied (internal only)
        result = is_external_allowed(self.analytics_roles, True)
        self.assertFalse(result, "Analytics should not have external access even when feature flag is enabled")
        
        # General and user should be denied
        for roles in [self.general_roles, self.user_roles]:
            with self.subTest(roles=roles):
                result = is_external_allowed(roles, True)
                self.assertFalse(result, f"External access should be denied for {roles} even when feature flag is enabled")
    
    def test_is_external_allowed_mixed_roles(self):
        """Test external access with mixed roles."""
        # Mixed roles with at least one allowed role should be allowed
        result = is_external_allowed(self.mixed_roles, True)
        self.assertTrue(result, "Mixed roles with pro should allow external access")
        
        # Mixed roles with only denied roles should be denied
        result = is_external_allowed(["analytics", "general"], True)
        self.assertFalse(result, "Mixed roles with only analytics and general should deny external access")
    
    def test_is_source_whitelisted_valid_urls(self):
        """Test whitelisting of valid URLs."""
        valid_urls = [
            "https://arxiv.org/abs/1234.5678",
            "https://www.nature.com/articles/s41586-020-1234-5",
            "https://scholar.google.com/scholar?q=test",
            "https://www.bbc.com/news",
            "https://docs.python.org/3/",
            "https://github.com/user/repo",
            "https://university.edu/research",
            "https://www.gov.uk/guidance",
            "https://who.int/emergencies",
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                result = is_source_whitelisted(url)
                self.assertTrue(result, f"URL {url} should be whitelisted")
    
    def test_is_source_whitelisted_invalid_urls(self):
        """Test that invalid URLs are not whitelisted."""
        invalid_urls = [
            "",
            None,
            "not-a-url",
            "ftp://example.com",  # Wrong protocol
            "https://",  # No domain
            "https://malicious-site.com",
            "https://random-blog.com",
            "https://social-media.com",
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                result = is_source_whitelisted(url)
                self.assertFalse(result, f"URL {url} should not be whitelisted")
    
    def test_can_access_factare_feature_flag_disabled(self):
        """Test that Factare access is denied when feature flag is disabled."""
        # All roles should be denied when feature flag is False
        for roles in [self.admin_roles, self.ops_roles, self.pro_roles, self.scholars_roles, self.analytics_roles]:
            with self.subTest(roles=roles):
                result = can_access_factare(roles, False)
                self.assertFalse(result, f"Factare access should be denied for {roles} when feature flag is disabled")
    
    def test_can_access_factare_feature_flag_enabled(self):
        """Test Factare access when feature flag is enabled."""
        # Admin, ops, pro, scholars, analytics should be allowed
        for roles in [self.admin_roles, self.ops_roles, self.pro_roles, self.scholars_roles, self.analytics_roles]:
            with self.subTest(roles=roles):
                result = can_access_factare(roles, True)
                self.assertTrue(result, f"Factare access should be allowed for {roles} when feature flag is enabled")
        
        # General and user should be denied
        for roles in [self.general_roles, self.user_roles]:
            with self.subTest(roles=roles):
                result = can_access_factare(roles, True)
                self.assertFalse(result, f"Factare access should be denied for {roles} even when feature flag is enabled")
    
    def test_get_max_sources_internal(self):
        """Test maximum internal sources for different roles."""
        # Admin, ops, pro, scholars should get full internal limits
        for roles in [self.admin_roles, self.ops_roles, self.pro_roles, self.scholars_roles]:
            with self.subTest(roles=roles):
                result = get_max_sources(roles, False)
                self.assertEqual(result, 24, f"Internal sources should be 24 for {roles}")
        
        # Analytics should get internal limits
        result = get_max_sources(self.analytics_roles, False)
        self.assertEqual(result, 24, "Analytics should get internal sources")
        
        # General and user should get no access
        for roles in [self.general_roles, self.user_roles]:
            with self.subTest(roles=roles):
                result = get_max_sources(roles, False)
                self.assertEqual(result, 0, f"Internal sources should be 0 for {roles}")
    
    def test_get_max_sources_external(self):
        """Test maximum external sources for different roles."""
        # Admin, ops, pro, scholars should get full external limits
        for roles in [self.admin_roles, self.ops_roles, self.pro_roles, self.scholars_roles]:
            with self.subTest(roles=roles):
                result = get_max_sources(roles, True)
                self.assertEqual(result, 8, f"External sources should be 8 for {roles}")
        
        # Analytics should get no external sources
        result = get_max_sources(self.analytics_roles, True)
        self.assertEqual(result, 0, "Analytics should get no external sources")
        
        # General and user should get no access
        for roles in [self.general_roles, self.user_roles]:
            with self.subTest(roles=roles):
                result = get_max_sources(roles, True)
                self.assertEqual(result, 0, f"External sources should be 0 for {roles}")
    
    def test_get_external_timeout_ms(self):
        """Test external timeout configuration."""
        result = get_external_timeout_ms()
        self.assertEqual(result, 2000, "External timeout should be 2000ms")
    
    def test_get_pareto_threshold(self):
        """Test Pareto threshold configuration."""
        result = get_pareto_threshold()
        self.assertEqual(result, 0.65, "Pareto threshold should be 0.65")
    
    def test_validate_source_url_valid_whitelisted(self):
        """Test URL validation for valid whitelisted URLs."""
        url = "https://arxiv.org/abs/1234.5678"
        result = validate_source_url(url)
        
        self.assertTrue(result["valid"], "URL should be valid")
        self.assertTrue(result["whitelisted"], "URL should be whitelisted")
        self.assertEqual(result["domain"], "arxiv.org", "Domain should be extracted correctly")
        self.assertEqual(result["error"], "", "No error should be present")
    
    def test_validate_source_url_valid_not_whitelisted(self):
        """Test URL validation for valid but not whitelisted URLs."""
        url = "https://example.com/page"
        result = validate_source_url(url)
        
        self.assertTrue(result["valid"], "URL should be valid")
        self.assertFalse(result["whitelisted"], "URL should not be whitelisted")
        self.assertEqual(result["domain"], "example.com", "Domain should be extracted correctly")
        self.assertEqual(result["error"], "", "No error should be present")
    
    def test_validate_source_url_invalid(self):
        """Test URL validation for invalid URLs."""
        test_cases = [
            ("", "URL is empty"),
            ("not-a-url", "Invalid URL format"),
            ("https://", "Invalid URL format"),
        ]
        
        for url, expected_error in test_cases:
            with self.subTest(url=url):
                result = validate_source_url(url)
                self.assertFalse(result["valid"], f"URL {url} should be invalid")
                self.assertFalse(result["whitelisted"], f"URL {url} should not be whitelisted")
                self.assertEqual(result["error"], expected_error, f"Error message should match for {url}")
    
    def test_get_user_policy_summary_admin(self):
        """Test policy summary for admin user."""
        result = get_user_policy_summary(self.admin_roles, True, True)
        
        self.assertTrue(result["can_access_factare"], "Admin should access Factare")
        self.assertTrue(result["external_allowed"], "Admin should have external access")
        self.assertEqual(result["max_internal_sources"], 24, "Admin should have 24 internal sources")
        self.assertEqual(result["max_external_sources"], 8, "Admin should have 8 external sources")
        self.assertEqual(result["external_timeout_ms"], 2000, "External timeout should be 2000ms")
        self.assertEqual(result["pareto_threshold"], 0.65, "Pareto threshold should be 0.65")
        self.assertEqual(result["roles"], self.admin_roles, "Roles should match")
        self.assertIn("admin", result["permissions"], "Admin permissions should be present")
    
    def test_get_user_policy_summary_analytics(self):
        """Test policy summary for analytics user."""
        result = get_user_policy_summary(self.analytics_roles, True, True)
        
        self.assertTrue(result["can_access_factare"], "Analytics should access Factare")
        self.assertFalse(result["external_allowed"], "Analytics should not have external access")
        self.assertEqual(result["max_internal_sources"], 24, "Analytics should have 24 internal sources")
        self.assertEqual(result["max_external_sources"], 0, "Analytics should have 0 external sources")
        self.assertEqual(result["roles"], self.analytics_roles, "Roles should match")
    
    def test_get_user_policy_summary_general(self):
        """Test policy summary for general user."""
        result = get_user_policy_summary(self.general_roles, True, True)
        
        self.assertFalse(result["can_access_factare"], "General should not access Factare")
        self.assertFalse(result["external_allowed"], "General should not have external access")
        self.assertEqual(result["max_internal_sources"], 0, "General should have 0 internal sources")
        self.assertEqual(result["max_external_sources"], 0, "General should have 0 external sources")
        self.assertEqual(result["roles"], self.general_roles, "Roles should match")
    
    def test_get_user_policy_summary_feature_flags_disabled(self):
        """Test policy summary when feature flags are disabled."""
        result = get_user_policy_summary(self.admin_roles, False, False)
        
        self.assertFalse(result["can_access_factare"], "Factare access should be disabled")
        self.assertFalse(result["external_allowed"], "External access should be disabled")
        self.assertEqual(result["max_internal_sources"], 0, "Internal sources should be 0")
        self.assertEqual(result["max_external_sources"], 0, "External sources should be 0")
    
    def test_role_permissions_structure(self):
        """Test that role permissions have the correct structure."""
        required_keys = ["factare_enabled", "external_allowed", "bypass_whitelist"]
        
        for role, permissions in ROLE_PERMISSIONS.items():
            with self.subTest(role=role):
                for key in required_keys:
                    self.assertIn(key, permissions, f"Role {role} should have {key} permission")
                    self.assertIsInstance(permissions[key], bool, f"Role {role} {key} should be boolean")
    
    def test_whitelist_patterns_compilation(self):
        """Test that whitelist patterns compile correctly."""
        self.assertGreater(len(EXTERNAL_WHITELIST_PATTERNS), 0, "Should have whitelist patterns")
        
        for pattern in EXTERNAL_WHITELIST_PATTERNS:
            with self.subTest(pattern=pattern):
                # Test that pattern compiles
                compiled = re.compile(pattern, re.IGNORECASE)
                self.assertIsNotNone(compiled, f"Pattern {pattern} should compile")
    
    def test_mixed_roles_priority(self):
        """Test that mixed roles work correctly with priority."""
        # Test with roles that have different permissions
        mixed_roles = ["general", "pro", "analytics"]
        result = get_user_policy_summary(mixed_roles, True, True)
        
        # Should have access because of "pro" role
        self.assertTrue(result["can_access_factare"], "Mixed roles with pro should access Factare")
        self.assertTrue(result["external_allowed"], "Mixed roles with pro should have external access")
        self.assertEqual(result["max_internal_sources"], 24, "Mixed roles should have internal sources")
        self.assertEqual(result["max_external_sources"], 8, "Mixed roles should have external sources")
    
    def test_unknown_roles(self):
        """Test behavior with unknown roles."""
        result = get_user_policy_summary(self.unknown_roles, True, True)
        
        # Unknown roles should be treated as having no permissions
        self.assertFalse(result["can_access_factare"], "Unknown roles should not access Factare")
        self.assertFalse(result["external_allowed"], "Unknown roles should not have external access")
        self.assertEqual(result["max_internal_sources"], 0, "Unknown roles should have 0 internal sources")
        self.assertEqual(result["max_external_sources"], 0, "Unknown roles should have 0 external sources")


class TestFactareConfig(unittest.TestCase):
    """Test Factare configuration loading and validation."""
    
    def test_config_defaults(self):
        """Test that configuration has correct defaults."""
        from config import load_config
        
        with patch.dict(os.environ, {}, clear=True):
            # Set required environment variables
            env_vars = {
                "OPENAI_API_KEY": "test-key",
                "SUPABASE_URL": "https://test.supabase.co",
                "PINECONE_API_KEY": "test-pinecone-key",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
            }
            
            with patch.dict(os.environ, env_vars):
                config = load_config()
                
                # Test Factare defaults
                self.assertFalse(config.get("FACTARE_ENABLED", True), "FACTARE_ENABLED should default to False")
                self.assertFalse(config.get("FACTARE_ALLOW_EXTERNAL", True), "FACTARE_ALLOW_EXTERNAL should default to False")
                self.assertEqual(config.get("FACTARE_EXTERNAL_TIMEOUT_MS", 0), 2000, "FACTARE_EXTERNAL_TIMEOUT_MS should default to 2000")
                self.assertEqual(config.get("FACTARE_MAX_SOURCES_INTERNAL", 0), 24, "FACTARE_MAX_SOURCES_INTERNAL should default to 24")
                self.assertEqual(config.get("FACTARE_MAX_SOURCES_EXTERNAL", 0), 8, "FACTARE_MAX_SOURCES_EXTERNAL should default to 8")
                self.assertEqual(config.get("HYPOTHESES_PARETO_THRESHOLD", 0.0), 0.65, "HYPOTHESES_PARETO_THRESHOLD should default to 0.65")
    
    def test_config_validation_boolean(self):
        """Test boolean configuration validation."""
        from config import load_config
        
        with patch.dict(os.environ, {}, clear=True):
            # Set required environment variables
            env_vars = {
                "OPENAI_API_KEY": "test-key",
                "SUPABASE_URL": "https://test.supabase.co",
                "PINECONE_API_KEY": "test-pinecone-key",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
            }
            
            # Test various boolean values
            boolean_tests = [
                ("FACTARE_ENABLED", "true", True),
                ("FACTARE_ENABLED", "1", True),
                ("FACTARE_ENABLED", "yes", True),
                ("FACTARE_ENABLED", "on", True),
                ("FACTARE_ENABLED", "false", False),
                ("FACTARE_ENABLED", "0", False),
                ("FACTARE_ENABLED", "no", False),
                ("FACTARE_ENABLED", "off", False),
            ]
            
            for key, value, expected in boolean_tests:
                with self.subTest(key=key, value=value):
                    test_env = {**env_vars, key: value}
                    with patch.dict(os.environ, test_env):
                        config = load_config()
                        self.assertEqual(config.get(key), expected, f"{key}={value} should be {expected}")
    
    def test_config_validation_integers(self):
        """Test integer configuration validation."""
        from config import load_config
        
        with patch.dict(os.environ, {}, clear=True):
            # Set required environment variables
            env_vars = {
                "OPENAI_API_KEY": "test-key",
                "SUPABASE_URL": "https://test.supabase.co",
                "PINECONE_API_KEY": "test-pinecone-key",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
            }
            
            # Test valid integer values
            integer_tests = [
                ("FACTARE_EXTERNAL_TIMEOUT_MS", "1000", 1000),
                ("FACTARE_MAX_SOURCES_INTERNAL", "30", 30),
                ("FACTARE_MAX_SOURCES_EXTERNAL", "10", 10),
            ]
            
            for key, value, expected in integer_tests:
                with self.subTest(key=key, value=value):
                    test_env = {**env_vars, key: value}
                    with patch.dict(os.environ, test_env):
                        config = load_config()
                        self.assertEqual(config.get(key), expected, f"{key}={value} should be {expected}")
            
            # Test invalid integer values
            invalid_tests = [
                ("FACTARE_EXTERNAL_TIMEOUT_MS", "not-a-number"),
                ("FACTARE_MAX_SOURCES_INTERNAL", "-5"),
                ("FACTARE_MAX_SOURCES_EXTERNAL", "abc"),
            ]
            
            for key, value in invalid_tests:
                with self.subTest(key=key, value=value):
                    test_env = {**env_vars, key: value}
                    with patch.dict(os.environ, test_env):
                        with self.assertRaises(RuntimeError, msg=f"{key}={value} should raise RuntimeError"):
                            load_config()
    
    def test_config_validation_float(self):
        """Test float configuration validation."""
        from config import load_config
        
        with patch.dict(os.environ, {}, clear=True):
            # Set required environment variables
            env_vars = {
                "OPENAI_API_KEY": "test-key",
                "SUPABASE_URL": "https://test.supabase.co",
                "PINECONE_API_KEY": "test-pinecone-key",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
            }
            
            # Test valid float values
            float_tests = [
                ("HYPOTHESES_PARETO_THRESHOLD", "0.5", 0.5),
                ("HYPOTHESES_PARETO_THRESHOLD", "0.8", 0.8),
                ("HYPOTHESES_PARETO_THRESHOLD", "1.0", 1.0),
                ("HYPOTHESES_PARETO_THRESHOLD", "0.0", 0.0),
            ]
            
            for key, value, expected in float_tests:
                with self.subTest(key=key, value=value):
                    test_env = {**env_vars, key: value}
                    with patch.dict(os.environ, test_env):
                        config = load_config()
                        self.assertEqual(config.get(key), expected, f"{key}={value} should be {expected}")
            
            # Test invalid float values
            invalid_tests = [
                ("HYPOTHESES_PARETO_THRESHOLD", "1.5"),  # > 1.0
                ("HYPOTHESES_PARETO_THRESHOLD", "-0.1"),  # < 0.0
                ("HYPOTHESES_PARETO_THRESHOLD", "not-a-number"),
            ]
            
            for key, value in invalid_tests:
                with self.subTest(key=key, value=value):
                    test_env = {**env_vars, key: value}
                    with patch.dict(os.environ, test_env):
                        with self.assertRaises(RuntimeError, msg=f"{key}={value} should raise RuntimeError"):
                            load_config()


def main():
    """Run all tests."""
    print("Running Factare flags and policy tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestFactarePolicy))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestFactareConfig))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All Factare tests passed!")
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        for failure in result.failures:
            print(f"FAIL: {failure[0]}")
            print(failure[1])
        for error in result.errors:
            print(f"ERROR: {error[0]}")
            print(error[1])
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)