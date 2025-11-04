#!/usr/bin/env python3
"""
Unit tests for performance flags and budgets.

Tests:
1. Default flag values
2. Type validation
3. Budget validation
4. Config loading
5. Debug endpoint exposure
"""

import os
import sys
import unittest
from unittest.mock import patch

# Add workspace to path
sys.path.insert(0, '/workspace')

import config


class TestPerformanceFlagDefaults(unittest.TestCase):
    """Test default values for performance flags."""
    
    def test_retrieval_parallel_default(self):
        """Test PERF_RETRIEVAL_PARALLEL defaults to True."""
        default = config.DEFAULTS.get("PERF_RETRIEVAL_PARALLEL")
        self.assertTrue(default)
        self.assertIsInstance(default, bool)
    
    def test_retrieval_timeout_default(self):
        """Test PERF_RETRIEVAL_TIMEOUT_MS defaults to 450."""
        default = config.DEFAULTS.get("PERF_RETRIEVAL_TIMEOUT_MS")
        self.assertEqual(default, 450)
        self.assertIsInstance(default, int)
    
    def test_graph_timeout_default(self):
        """Test PERF_GRAPH_TIMEOUT_MS defaults to 150."""
        default = config.DEFAULTS.get("PERF_GRAPH_TIMEOUT_MS")
        self.assertEqual(default, 150)
        self.assertIsInstance(default, int)
    
    def test_compare_timeout_default(self):
        """Test PERF_COMPARE_TIMEOUT_MS defaults to 400."""
        default = config.DEFAULTS.get("PERF_COMPARE_TIMEOUT_MS")
        self.assertEqual(default, 400)
        self.assertIsInstance(default, int)
    
    def test_reviewer_enabled_default(self):
        """Test PERF_REVIEWER_ENABLED defaults to True."""
        default = config.DEFAULTS.get("PERF_REVIEWER_ENABLED")
        self.assertTrue(default)
        self.assertIsInstance(default, bool)
    
    def test_reviewer_budget_default(self):
        """Test PERF_REVIEWER_BUDGET_MS defaults to 500."""
        default = config.DEFAULTS.get("PERF_REVIEWER_BUDGET_MS")
        self.assertEqual(default, 500)
        self.assertIsInstance(default, int)
    
    def test_pgvector_enabled_default(self):
        """Test PERF_PGVECTOR_ENABLED defaults to True."""
        default = config.DEFAULTS.get("PERF_PGVECTOR_ENABLED")
        self.assertTrue(default)
        self.assertIsInstance(default, bool)
    
    def test_fallbacks_enabled_default(self):
        """Test PERF_FALLBACKS_ENABLED defaults to True."""
        default = config.DEFAULTS.get("PERF_FALLBACKS_ENABLED")
        self.assertTrue(default)
        self.assertIsInstance(default, bool)


class TestPerformanceFlagTypes(unittest.TestCase):
    """Test type validation for performance flags."""
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_PARALLEL": "true"
    })
    def test_boolean_flag_true(self):
        """Test boolean flag parsing for 'true'."""
        cfg = config.load_config()
        self.assertTrue(cfg["PERF_RETRIEVAL_PARALLEL"])
        self.assertIsInstance(cfg["PERF_RETRIEVAL_PARALLEL"], bool)
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_PARALLEL": "false"
    })
    def test_boolean_flag_false(self):
        """Test boolean flag parsing for 'false'."""
        cfg = config.load_config()
        self.assertFalse(cfg["PERF_RETRIEVAL_PARALLEL"])
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_PARALLEL": "1"
    })
    def test_boolean_flag_numeric(self):
        """Test boolean flag parsing for '1'."""
        cfg = config.load_config()
        self.assertTrue(cfg["PERF_RETRIEVAL_PARALLEL"])
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_TIMEOUT_MS": "600"
    })
    def test_timeout_integer_parsing(self):
        """Test timeout budget parsing as integer."""
        cfg = config.load_config()
        self.assertEqual(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], 600)
        self.assertIsInstance(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], int)
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_TIMEOUT_MS": "invalid"
    })
    def test_timeout_invalid_raises(self):
        """Test that invalid timeout value raises error."""
        with self.assertRaises(RuntimeError) as cm:
            config.load_config()
        
        self.assertIn("must be a positive integer", str(cm.exception))
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_TIMEOUT_MS": "-100"
    })
    def test_timeout_negative_raises(self):
        """Test that negative timeout value raises error."""
        with self.assertRaises(RuntimeError) as cm:
            config.load_config()
        
        self.assertIn("must be a positive integer", str(cm.exception))
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_TIMEOUT_MS": "0"
    })
    def test_timeout_zero_raises(self):
        """Test that zero timeout value raises error."""
        with self.assertRaises(RuntimeError) as cm:
            config.load_config()
        
        self.assertIn("must be a positive integer", str(cm.exception))


class TestAllPerformanceFlags(unittest.TestCase):
    """Test all performance flags load correctly."""
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3"
    })
    def test_all_perf_flags_present(self):
        """Test all performance flags are present in config."""
        cfg = config.load_config()
        
        # Boolean flags
        self.assertIn("PERF_RETRIEVAL_PARALLEL", cfg)
        self.assertIn("PERF_REVIEWER_ENABLED", cfg)
        self.assertIn("PERF_PGVECTOR_ENABLED", cfg)
        self.assertIn("PERF_FALLBACKS_ENABLED", cfg)
        
        # Timeout/budget flags
        self.assertIn("PERF_RETRIEVAL_TIMEOUT_MS", cfg)
        self.assertIn("PERF_GRAPH_TIMEOUT_MS", cfg)
        self.assertIn("PERF_COMPARE_TIMEOUT_MS", cfg)
        self.assertIn("PERF_REVIEWER_BUDGET_MS", cfg)
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3"
    })
    def test_all_perf_flags_have_correct_types(self):
        """Test all performance flags have correct types."""
        cfg = config.load_config()
        
        # Boolean flags should be bool
        self.assertIsInstance(cfg["PERF_RETRIEVAL_PARALLEL"], bool)
        self.assertIsInstance(cfg["PERF_REVIEWER_ENABLED"], bool)
        self.assertIsInstance(cfg["PERF_PGVECTOR_ENABLED"], bool)
        self.assertIsInstance(cfg["PERF_FALLBACKS_ENABLED"], bool)
        
        # Timeout/budget flags should be int
        self.assertIsInstance(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], int)
        self.assertIsInstance(cfg["PERF_GRAPH_TIMEOUT_MS"], int)
        self.assertIsInstance(cfg["PERF_COMPARE_TIMEOUT_MS"], int)
        self.assertIsInstance(cfg["PERF_REVIEWER_BUDGET_MS"], int)
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3"
    })
    def test_default_values_are_sensible(self):
        """Test default values are within reasonable ranges."""
        cfg = config.load_config()
        
        # Timeouts should be positive
        self.assertGreater(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], 0)
        self.assertGreater(cfg["PERF_GRAPH_TIMEOUT_MS"], 0)
        self.assertGreater(cfg["PERF_COMPARE_TIMEOUT_MS"], 0)
        self.assertGreater(cfg["PERF_REVIEWER_BUDGET_MS"], 0)
        
        # Timeouts should be under 1 second for most operations
        self.assertLessEqual(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], 1000)
        self.assertLessEqual(cfg["PERF_GRAPH_TIMEOUT_MS"], 300)
        self.assertLessEqual(cfg["PERF_COMPARE_TIMEOUT_MS"], 1000)
        self.assertLessEqual(cfg["PERF_REVIEWER_BUDGET_MS"], 1000)


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation functions."""
    
    def test_validate_perf_config_valid(self):
        """Test validation passes for valid config."""
        valid_config = {
            "PERF_RETRIEVAL_TIMEOUT_MS": 450,
            "PERF_GRAPH_TIMEOUT_MS": 150,
            "PERF_COMPARE_TIMEOUT_MS": 400,
            "PERF_REVIEWER_BUDGET_MS": 500,
            "PERF_RETRIEVAL_PARALLEL": True,
            "PERF_PGVECTOR_ENABLED": True
        }
        
        errors = config.validate_perf_config(valid_config)
        self.assertEqual(len(errors), 0)
    
    def test_validate_perf_config_retrieval_too_high(self):
        """Test validation warns on excessive retrieval timeout."""
        invalid_config = {
            "PERF_RETRIEVAL_TIMEOUT_MS": 1500,  # Too high
            "PERF_GRAPH_TIMEOUT_MS": 150,
            "PERF_COMPARE_TIMEOUT_MS": 400,
            "PERF_REVIEWER_BUDGET_MS": 500,
            "PERF_RETRIEVAL_PARALLEL": True,
            "PERF_PGVECTOR_ENABLED": True
        }
        
        errors = config.validate_perf_config(invalid_config)
        self.assertIn("PERF_RETRIEVAL_TIMEOUT_MS", errors)
    
    def test_validate_perf_config_graph_too_high(self):
        """Test validation warns on excessive graph timeout."""
        invalid_config = {
            "PERF_RETRIEVAL_TIMEOUT_MS": 450,
            "PERF_GRAPH_TIMEOUT_MS": 500,  # Too high
            "PERF_COMPARE_TIMEOUT_MS": 400,
            "PERF_REVIEWER_BUDGET_MS": 500,
            "PERF_RETRIEVAL_PARALLEL": True,
            "PERF_PGVECTOR_ENABLED": True
        }
        
        errors = config.validate_perf_config(invalid_config)
        self.assertIn("PERF_GRAPH_TIMEOUT_MS", errors)
    
    def test_validate_perf_config_parallel_without_pgvector(self):
        """Test validation catches parallel retrieval without pgvector."""
        invalid_config = {
            "PERF_RETRIEVAL_TIMEOUT_MS": 450,
            "PERF_GRAPH_TIMEOUT_MS": 150,
            "PERF_COMPARE_TIMEOUT_MS": 400,
            "PERF_REVIEWER_BUDGET_MS": 500,
            "PERF_RETRIEVAL_PARALLEL": True,
            "PERF_PGVECTOR_ENABLED": False  # Conflict
        }
        
        errors = config.validate_perf_config(invalid_config)
        self.assertIn("PERF_RETRIEVAL_PARALLEL", errors)


class TestDebugConfigEndpoint(unittest.TestCase):
    """Test debug config endpoint exposure."""
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3"
    })
    def test_get_debug_config(self):
        """Test get_debug_config returns sanitized config."""
        debug_cfg = config.get_debug_config()
        
        self.assertIn("_metadata", debug_cfg)
        self.assertNotIn("OPENAI_API_KEY", debug_cfg)  # Should be removed
        self.assertNotIn("PINECONE_API_KEY", debug_cfg)  # Should be removed
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3"
    })
    def test_perf_flags_in_debug_config(self):
        """Test performance flags appear in debug config."""
        debug_cfg = config.get_debug_config()
        
        # Performance flags should be present
        self.assertIn("PERF_RETRIEVAL_PARALLEL", debug_cfg)
        self.assertIn("PERF_RETRIEVAL_TIMEOUT_MS", debug_cfg)
        self.assertIn("PERF_GRAPH_TIMEOUT_MS", debug_cfg)
        self.assertIn("PERF_COMPARE_TIMEOUT_MS", debug_cfg)
        self.assertIn("PERF_REVIEWER_ENABLED", debug_cfg)
        self.assertIn("PERF_REVIEWER_BUDGET_MS", debug_cfg)
        self.assertIn("PERF_PGVECTOR_ENABLED", debug_cfg)
        self.assertIn("PERF_FALLBACKS_ENABLED", debug_cfg)


class TestEnvironmentOverrides(unittest.TestCase):
    """Test environment variable overrides."""
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_TIMEOUT_MS": "600"
    })
    def test_env_override_timeout(self):
        """Test environment variable overrides default timeout."""
        cfg = config.load_config()
        self.assertEqual(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], 600)
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_FALLBACKS_ENABLED": "false"
    })
    def test_env_override_boolean(self):
        """Test environment variable overrides default boolean."""
        cfg = config.load_config()
        self.assertFalse(cfg["PERF_FALLBACKS_ENABLED"])
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3",
        "PERF_RETRIEVAL_TIMEOUT_MS": "100",
        "PERF_GRAPH_TIMEOUT_MS": "50",
        "PERF_COMPARE_TIMEOUT_MS": "200",
        "PERF_REVIEWER_BUDGET_MS": "300"
    })
    def test_all_timeouts_overridable(self):
        """Test all timeout budgets can be overridden."""
        cfg = config.load_config()
        
        self.assertEqual(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], 100)
        self.assertEqual(cfg["PERF_GRAPH_TIMEOUT_MS"], 50)
        self.assertEqual(cfg["PERF_COMPARE_TIMEOUT_MS"], 200)
        self.assertEqual(cfg["PERF_REVIEWER_BUDGET_MS"], 300)


class TestBudgetRanges(unittest.TestCase):
    """Test that budgets are within expected ranges."""
    
    def test_default_budgets_ordered(self):
        """Test that default budgets are sensibly ordered."""
        defaults = config.DEFAULTS
        
        # Graph should be fastest (part of retrieval)
        self.assertLess(
            defaults["PERF_GRAPH_TIMEOUT_MS"],
            defaults["PERF_RETRIEVAL_TIMEOUT_MS"]
        )
        
        # Compare should be reasonable
        self.assertLess(
            defaults["PERF_COMPARE_TIMEOUT_MS"],
            defaults["PERF_REVIEWER_BUDGET_MS"]
        )
    
    def test_budgets_sum_reasonably(self):
        """Test that budget sums allow for reasonable total latency."""
        defaults = config.DEFAULTS
        
        # Typical request: retrieval + compare + review
        typical_total = (
            defaults["PERF_RETRIEVAL_TIMEOUT_MS"] +
            defaults["PERF_COMPARE_TIMEOUT_MS"] +
            defaults["PERF_REVIEWER_BUDGET_MS"]
        )
        
        # Should be under 2 seconds for good UX
        self.assertLess(typical_total, 2000)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3"
    })
    def test_defaults_validated(self):
        """Test that default values are validated."""
        # Should load without errors
        cfg = config.load_config()
        
        # All perf flags should be present and valid
        self.assertTrue(cfg["PERF_RETRIEVAL_PARALLEL"])
        self.assertEqual(cfg["PERF_RETRIEVAL_TIMEOUT_MS"], 450)
        self.assertEqual(cfg["PERF_GRAPH_TIMEOUT_MS"], 150)
        self.assertEqual(cfg["PERF_COMPARE_TIMEOUT_MS"], 400)
        self.assertTrue(cfg["PERF_REVIEWER_ENABLED"])
        self.assertEqual(cfg["PERF_REVIEWER_BUDGET_MS"], 500)
        self.assertTrue(cfg["PERF_PGVECTOR_ENABLED"])
        self.assertTrue(cfg["PERF_FALLBACKS_ENABLED"])
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "SUPABASE_URL": "http://test",
        "PINECONE_API_KEY": "test",
        "PINECONE_INDEX": "index1",
        "PINECONE_EXPLICATE_INDEX": "index2",
        "PINECONE_IMPLICATE_INDEX": "index3"
    })
    def test_debug_config_shows_keys(self):
        """Test that /debug/config endpoint shows performance keys."""
        # Test the debug config function directly
        debug_cfg = config.get_debug_config()
        
        # Performance flags should be present
        self.assertIn("PERF_RETRIEVAL_PARALLEL", debug_cfg)
        self.assertIn("PERF_RETRIEVAL_TIMEOUT_MS", debug_cfg)
        self.assertIn("PERF_GRAPH_TIMEOUT_MS", debug_cfg)
        self.assertIn("PERF_COMPARE_TIMEOUT_MS", debug_cfg)
        self.assertIn("PERF_REVIEWER_ENABLED", debug_cfg)
        self.assertIn("PERF_REVIEWER_BUDGET_MS", debug_cfg)
        self.assertIn("PERF_PGVECTOR_ENABLED", debug_cfg)
        self.assertIn("PERF_FALLBACKS_ENABLED", debug_cfg)


if __name__ == "__main__":
    unittest.main()
