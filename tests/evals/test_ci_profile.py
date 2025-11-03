#!/usr/bin/env python3
"""
Unit tests for CI profile configuration and latency slack.

Tests verify:
1. CI profile configuration loading
2. Latency slack application
3. Environment variable handling
4. Profile-based test selection
"""

import os
import sys
import unittest
import yaml
from unittest.mock import Mock, patch

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.latency import LatencyGate, LatencyBudget


class TestLatencySlack(unittest.TestCase):
    """Test latency slack configuration."""
    
    def setUp(self):
        """Set up test environment."""
        # Save original env var
        self.original_slack = os.getenv("EVAL_LATENCY_SLACK_PERCENT")
    
    def tearDown(self):
        """Restore original environment."""
        if self.original_slack is not None:
            os.environ["EVAL_LATENCY_SLACK_PERCENT"] = self.original_slack
        elif "EVAL_LATENCY_SLACK_PERCENT" in os.environ:
            del os.environ["EVAL_LATENCY_SLACK_PERCENT"]
    
    def test_no_slack_by_default(self):
        """Test that slack is 0% by default."""
        os.environ["EVAL_LATENCY_SLACK_PERCENT"] = "0"
        gate = LatencyGate()
        
        self.assertEqual(gate.slack_percent, 0.0)
        self.assertEqual(gate.get_budget("retrieval"), 500.0)
    
    def test_slack_from_env(self):
        """Test reading slack from environment variable."""
        os.environ["EVAL_LATENCY_SLACK_PERCENT"] = "10"
        gate = LatencyGate()
        
        self.assertEqual(gate.slack_percent, 10.0)
    
    def test_slack_from_constructor(self):
        """Test setting slack via constructor."""
        gate = LatencyGate(slack_percent=15.0)
        
        self.assertEqual(gate.slack_percent, 15.0)
    
    def test_slack_applied_to_budget(self):
        """Test that slack is correctly applied to budgets."""
        gate = LatencyGate(slack_percent=10.0)
        
        # Base budget: 500ms
        # With 10% slack: 500 * 1.1 = 550ms
        budget_with_slack = gate.get_budget("retrieval", apply_slack=True)
        self.assertEqual(budget_with_slack, 550.0)
    
    def test_slack_not_applied_when_disabled(self):
        """Test that slack can be disabled."""
        gate = LatencyGate(slack_percent=10.0)
        
        # Get budget without slack
        budget_no_slack = gate.get_budget("retrieval", apply_slack=False)
        self.assertEqual(budget_no_slack, 500.0)
    
    def test_slack_validation_negative(self):
        """Test that negative slack is clamped to 0."""
        gate = LatencyGate(slack_percent=-5.0)
        
        self.assertEqual(gate.slack_percent, 0.0)
    
    def test_slack_validation_exceeds_max(self):
        """Test that slack exceeding 50% is clamped."""
        gate = LatencyGate(slack_percent=75.0)
        
        self.assertEqual(gate.slack_percent, 50.0)
    
    def test_slack_validation_at_max(self):
        """Test that 50% slack is allowed."""
        gate = LatencyGate(slack_percent=50.0)
        
        self.assertEqual(gate.slack_percent, 50.0)
    
    def test_invalid_env_slack(self):
        """Test handling of invalid slack environment variable."""
        os.environ["EVAL_LATENCY_SLACK_PERCENT"] = "invalid"
        gate = LatencyGate()
        
        # Should default to 0 on invalid input
        self.assertEqual(gate.slack_percent, 0.0)
    
    def test_slack_affects_all_operations(self):
        """Test that slack applies to all operations."""
        gate = LatencyGate(slack_percent=20.0)
        
        # Retrieval: 500 * 1.2 = 600
        self.assertEqual(gate.get_budget("retrieval"), 600.0)
        
        # Packing: 550 * 1.2 = 660
        self.assertEqual(gate.get_budget("packing"), 660.0)
        
        # Internal compare: 400 * 1.2 = 480
        self.assertEqual(gate.get_budget("internal_compare"), 480.0)
        
        # External compare: 2000 * 1.2 = 2400
        self.assertEqual(gate.get_budget("external_compare"), 2400.0)


class TestCIProfileConfiguration(unittest.TestCase):
    """Test CI profile configuration loading."""
    
    def test_load_ci_profile_yaml(self):
        """Test loading CI profile YAML."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Verify profiles exist
        self.assertIn("profiles", config)
        profiles = config["profiles"]
        
        self.assertIn("pr", profiles)
        self.assertIn("nightly", profiles)
        self.assertIn("full", profiles)
    
    def test_pr_profile_configuration(self):
        """Test PR profile has correct configuration."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        pr_profile = config["profiles"]["pr"]
        
        # PR should have relaxed constraints
        self.assertEqual(pr_profile["test_selection"], "subset")
        self.assertEqual(pr_profile["max_cases_per_suite"], 10)
        self.assertTrue(pr_profile["skip_flaky"])
        self.assertEqual(pr_profile["latency_slack_percent"], 15)
    
    def test_nightly_profile_configuration(self):
        """Test nightly profile has correct configuration."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        nightly_profile = config["profiles"]["nightly"]
        
        # Nightly should run full tests
        self.assertEqual(nightly_profile["test_selection"], "full")
        self.assertIsNone(nightly_profile["max_cases_per_suite"])
        self.assertFalse(nightly_profile["skip_flaky"])
        self.assertEqual(nightly_profile["latency_slack_percent"], 10)
    
    def test_full_profile_configuration(self):
        """Test full profile has strictest configuration."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        full_profile = config["profiles"]["full"]
        
        # Full should be most strict
        self.assertEqual(full_profile["test_selection"], "all")
        self.assertEqual(full_profile["latency_slack_percent"], 5)
        
        constraints = full_profile["constraints"]
        self.assertEqual(constraints["min_pass_rate"], 0.98)
    
    def test_suite_configurations_exist(self):
        """Test that all expected suites are configured."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        suites = config["suites"]
        
        # Verify all suites exist
        expected_suites = [
            "implicate_lift",
            "contradictions",
            "external_compare",
            "pareto_gate"
        ]
        
        for suite in expected_suites:
            self.assertIn(suite, suites)
    
    def test_suite_pr_subset_configuration(self):
        """Test that suites have PR subset configuration."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        suites = config["suites"]
        
        # Each suite should have PR subset config
        for suite_name, suite_config in suites.items():
            self.assertIn("pr_subset", suite_config)
            
            pr_subset = suite_config["pr_subset"]
            self.assertIn("enabled", pr_subset)
            self.assertIn("selection_strategy", pr_subset)
            self.assertIn("max_cases", pr_subset)
            self.assertIn("required_scenarios", pr_subset)
    
    def test_latency_budget_configuration(self):
        """Test latency budget configuration."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        budgets = config["latency_budgets"]
        
        # Verify base budgets
        base = budgets["base"]
        self.assertEqual(base["retrieval_p95_ms"], 500)
        self.assertEqual(base["packing_p95_ms"], 550)
        self.assertEqual(base["internal_compare_p95_ms"], 400)
        self.assertEqual(base["external_compare_p95_ms"], 2000)
        
        # Verify slack configuration
        slack = budgets["slack"]
        self.assertEqual(slack["default_percent"], 10)
        self.assertEqual(slack["max_percent"], 50)
        self.assertIn("pr", slack["apply_to_profiles"])
        self.assertIn("nightly", slack["apply_to_profiles"])


class TestSlackInValidation(unittest.TestCase):
    """Test slack application in latency validation."""
    
    def test_validation_with_slack_passes(self):
        """Test that validation passes with slack applied."""
        # Latencies slightly over base budget but under with slack
        latencies = [520, 530, 540, 545, 550]  # p95 ~545ms
        
        # Without slack: Should fail (base budget 500ms)
        gate_no_slack = LatencyGate(slack_percent=0)
        result = gate_no_slack.validate_retrieval(latencies)
        self.assertFalse(result.passed)
        
        # With 10% slack: Should pass (budget 550ms)
        gate_with_slack = LatencyGate(slack_percent=10)
        result = gate_with_slack.validate_retrieval(latencies)
        self.assertTrue(result.passed)
    
    def test_validation_still_fails_beyond_slack(self):
        """Test that validation fails even with slack if way over budget."""
        # Latencies well over budget even with slack
        latencies = [600, 650, 700, 750, 800]  # p95 ~750ms
        
        # With 10% slack: Should still fail (budget 550ms, measured ~750ms)
        gate = LatencyGate(slack_percent=10)
        result = gate.validate_retrieval(latencies)
        self.assertFalse(result.passed)


class TestCIBehavior(unittest.TestCase):
    """Test CI-specific behavior."""
    
    def test_flaky_test_configuration(self):
        """Test flaky test configuration."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        flaky = config.get("flaky_tests", {})
        
        # Should have skip list
        self.assertIn("skip_in_pr", flaky)
        self.assertIsInstance(flaky["skip_in_pr"], list)
        
        # Should have retry config
        self.assertIn("retry_on_failure", flaky)
        retry_config = flaky["retry_on_failure"]
        self.assertIn("max_retries", retry_config)
        self.assertIn("patterns", retry_config)
    
    def test_ci_behavior_configuration(self):
        """Test CI behavior configuration."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        ci_behavior = config.get("ci_behavior", {})
        
        # Should define failure conditions
        self.assertIn("fail_pr_on", ci_behavior)
        fail_on = ci_behavior["fail_pr_on"]
        
        self.assertIn("functional_failures", fail_on)
        self.assertIn("constraint_violations", fail_on)
        self.assertIn("latency_violations", fail_on)


class TestEnvironmentConfiguration(unittest.TestCase):
    """Test environment variable configuration."""
    
    def test_environment_variables_defined(self):
        """Test environment variables are defined in config."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        env = config.get("environment", {})
        variables = env.get("variables", [])
        
        # Find EVAL_LATENCY_SLACK_PERCENT
        slack_var = None
        for var in variables:
            if var["name"] == "EVAL_LATENCY_SLACK_PERCENT":
                slack_var = var
                break
        
        self.assertIsNotNone(slack_var)
        self.assertEqual(slack_var["default"], "10")
    
    def test_required_variables_defined(self):
        """Test required environment variables."""
        config_path = "/workspace/evals/ci_profile.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        env = config.get("environment", {})
        required = env.get("required", [])
        
        self.assertIn("BASE_URL", required)
        self.assertIn("X_API_KEY", required)


if __name__ == "__main__":
    unittest.main()
