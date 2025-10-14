#!/usr/bin/env python3
"""
Tests for feature flags and configuration validation.
"""

import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from config import load_config, DEFAULTS, REQUIRED
from feature_flags import get_feature_flag, set_feature_flag, get_all_flags, DEFAULT_FLAGS


class TestConfigValidation:
    """Test configuration loading and validation."""
    
    def test_default_values(self):
        """Test that all new config keys have correct default values."""
        # Test defaults are set correctly
        assert DEFAULTS["ORCHESTRATOR_REDO_ENABLED"] is False
        assert DEFAULTS["LEDGER_ENABLED"] is False
        assert DEFAULTS["LEDGER_LEVEL"] == "off"
        assert DEFAULTS["LEDGER_MAX_TRACE_BYTES"] == 100_000
        assert DEFAULTS["LEDGER_SUMMARY_MAX_LINES"] == 4
        assert DEFAULTS["ORCHESTRATION_TIME_BUDGET_MS"] == 400
    
    def test_boolean_config_validation(self):
        """Test boolean config validation."""
        test_cases = [
            ("true", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("", False),
            (None, False),
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {
                "OPENAI_API_KEY": "test",
                "SUPABASE_URL": "test",
                "PINECONE_API_KEY": "test",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
                "ORCHESTRATOR_REDO_ENABLED": str(env_value) if env_value is not None else "",
            }, clear=True):
                config = load_config()
                assert config["ORCHESTRATOR_REDO_ENABLED"] == expected, f"Failed for value: {env_value}"
    
    def test_ledger_level_validation(self):
        """Test LEDGER_LEVEL validation."""
        valid_levels = ["off", "min", "full"]
        invalid_levels = ["invalid", "ON", "maximum", "none", ""]
        
        # Test valid levels
        for level in valid_levels:
            with patch.dict(os.environ, {
                "OPENAI_API_KEY": "test",
                "SUPABASE_URL": "test",
                "PINECONE_API_KEY": "test",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
                "LEDGER_LEVEL": level,
            }, clear=True):
                config = load_config()
                assert config["LEDGER_LEVEL"] == level
        
        # Test invalid levels
        for level in invalid_levels:
            with patch.dict(os.environ, {
                "OPENAI_API_KEY": "test",
                "SUPABASE_URL": "test",
                "PINECONE_API_KEY": "test",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
                "LEDGER_LEVEL": level,
            }, clear=True):
                with pytest.raises(RuntimeError, match="LEDGER_LEVEL must be one of"):
                    load_config()
    
    def test_numeric_config_validation(self):
        """Test numeric config validation."""
        numeric_configs = [
            "LEDGER_MAX_TRACE_BYTES",
            "LEDGER_SUMMARY_MAX_LINES", 
            "ORCHESTRATION_TIME_BUDGET_MS"
        ]
        
        # Test valid values
        for config_key in numeric_configs:
            with patch.dict(os.environ, {
                "OPENAI_API_KEY": "test",
                "SUPABASE_URL": "test",
                "PINECONE_API_KEY": "test",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
                config_key: "123",
            }, clear=True):
                config = load_config()
                assert config[config_key] == 123
        
        # Test invalid values
        for config_key in numeric_configs:
            with patch.dict(os.environ, {
                "OPENAI_API_KEY": "test",
                "SUPABASE_URL": "test",
                "PINECONE_API_KEY": "test",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
                config_key: "invalid",
            }, clear=True):
                with pytest.raises(RuntimeError, match=f"{config_key} must be"):
                    load_config()
        
        # Test negative values
        for config_key in numeric_configs:
            with patch.dict(os.environ, {
                "OPENAI_API_KEY": "test",
                "SUPABASE_URL": "test",
                "PINECONE_API_KEY": "test",
                "PINECONE_INDEX": "test-index",
                "PINECONE_EXPLICATE_INDEX": "test-explicate",
                "PINECONE_IMPLICATE_INDEX": "test-implicate",
                config_key: "-1",
            }, clear=True):
                with pytest.raises(RuntimeError, match=f"{config_key} must be"):
                    load_config()
    
    def test_missing_required_vars(self):
        """Test that missing required environment variables produce helpful errors."""
        required_vars = [
            "OPENAI_API_KEY",
            "SUPABASE_URL", 
            "PINECONE_API_KEY",
            "PINECONE_INDEX",
            "PINECONE_EXPLICATE_INDEX",
            "PINECONE_IMPLICATE_INDEX"
        ]
        
        # Test missing each required variable
        for missing_var in required_vars:
            env_vars = {var: "test" for var in required_vars if var != missing_var}
            with patch.dict(os.environ, env_vars, clear=True):
                with pytest.raises(RuntimeError, match=f"Missing required environment variables.*{missing_var}"):
                    load_config()
    
    def test_pinecone_index_validation(self):
        """Test that Pinecone indices must be different."""
        base_env = {
            "OPENAI_API_KEY": "test",
            "SUPABASE_URL": "test",
            "PINECONE_API_KEY": "test",
        }
        
        # Test same index and explicate index
        with patch.dict(os.environ, {
            **base_env,
            "PINECONE_INDEX": "same-index",
            "PINECONE_EXPLICATE_INDEX": "same-index",
            "PINECONE_IMPLICATE_INDEX": "different-index",
        }, clear=True):
            with pytest.raises(RuntimeError, match="PINECONE_INDEX and PINECONE_EXPLICATE_INDEX must be different"):
                load_config()
        
        # Test same index and implicate index
        with patch.dict(os.environ, {
            **base_env,
            "PINECONE_INDEX": "same-index",
            "PINECONE_EXPLICATE_INDEX": "different-index",
            "PINECONE_IMPLICATE_INDEX": "same-index",
        }, clear=True):
            with pytest.raises(RuntimeError, match="PINECONE_INDEX and PINECONE_IMPLICATE_INDEX must be different"):
                load_config()
        
        # Test same explicate and implicate index
        with patch.dict(os.environ, {
            **base_env,
            "PINECONE_INDEX": "different-index",
            "PINECONE_EXPLICATE_INDEX": "same-index",
            "PINECONE_IMPLICATE_INDEX": "same-index",
        }, clear=True):
            with pytest.raises(RuntimeError, match="PINECONE_EXPLICATE_INDEX and PINECONE_IMPLICATE_INDEX must be different"):
                load_config()


class TestFeatureFlags:
    """Test feature flag functionality."""
    
    def test_default_flags(self):
        """Test that default flags are set correctly."""
        assert DEFAULT_FLAGS["orchestrator.redo_enabled"] is False
        assert DEFAULT_FLAGS["ledger.enabled"] is False
        assert DEFAULT_FLAGS["retrieval.dual_index"] is False
        assert DEFAULT_FLAGS["retrieval.liftscore"] is False
        assert DEFAULT_FLAGS["retrieval.contradictions_pack"] is False
    
    def test_get_feature_flag_default(self):
        """Test getting feature flag with default fallback."""
        # Mock database unavailable
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.side_effect = Exception("Database unavailable")
            
            # Should return default when database is unavailable
            assert get_feature_flag("orchestrator.redo_enabled") is False
            assert get_feature_flag("ledger.enabled") is False
            assert get_feature_flag("nonexistent.flag") is False
            assert get_feature_flag("nonexistent.flag", default=True) is True
    
    def test_get_feature_flag_from_database(self):
        """Test getting feature flag from database."""
        with patch('feature_flags.supabase') as mock_supabase:
            # Mock successful database response
            mock_result = MagicMock()
            mock_result.data = [{"value": {"enabled": True}}]
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            
            assert get_feature_flag("orchestrator.redo_enabled") is True
            assert get_feature_flag("ledger.enabled") is True
    
    def test_set_feature_flag(self):
        """Test setting feature flag."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.upsert.return_value.execute.return_value = None
            
            # Should not raise exception
            set_feature_flag("orchestrator.redo_enabled", True)
            set_feature_flag("ledger.enabled", False)
            
            # Verify upsert was called
            assert mock_supabase.table.return_value.upsert.call_count == 2
    
    def test_set_feature_flag_error(self):
        """Test setting feature flag with database error."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.upsert.return_value.execute.side_effect = Exception("Database error")
            
            with pytest.raises(RuntimeError, match="Failed to set feature flag"):
                set_feature_flag("orchestrator.redo_enabled", True)
    
    def test_get_all_flags(self):
        """Test getting all flags."""
        with patch('feature_flags.supabase') as mock_supabase:
            # Mock database response with some flags
            mock_result = MagicMock()
            mock_result.data = [
                {"key": "orchestrator.redo_enabled", "value": {"enabled": True}},
                {"key": "ledger.enabled", "value": {"enabled": False}},
            ]
            mock_supabase.table.return_value.select.return_value.execute.return_value = mock_result
            
            flags = get_all_flags()
            
            # Should include database flags
            assert flags["orchestrator.redo_enabled"] is True
            assert flags["ledger.enabled"] is False
            
            # Should include all default flags
            for flag_name, default_value in DEFAULT_FLAGS.items():
                assert flag_name in flags
                if flag_name not in ["orchestrator.redo_enabled", "ledger.enabled"]:
                    assert flags[flag_name] == default_value
    
    def test_get_all_flags_database_unavailable(self):
        """Test getting all flags when database is unavailable."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.execute.side_effect = Exception("Database unavailable")
            
            flags = get_all_flags()
            
            # Should return all default flags
            for flag_name, default_value in DEFAULT_FLAGS.items():
                assert flags[flag_name] == default_value


class TestDebugConfigEndpoint:
    """Test the debug config endpoint functionality."""
    
    def test_debug_config_shows_new_keys(self):
        """Test that debug config endpoint shows the new configuration keys."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "SUPABASE_URL": "test-url",
            "PINECONE_API_KEY": "test-pinecone-key",
            "PINECONE_INDEX": "test-index",
            "PINECONE_EXPLICATE_INDEX": "test-explicate",
            "PINECONE_IMPLICATE_INDEX": "test-implicate",
        }, clear=True):
            from router.debug import debug_config
            
            # Mock the API key requirement
            with patch('router.debug._require_key'):
                result = debug_config("test-api-key")
                
                assert result["status"] == "ok"
                config = result["config"]
                
                # Check that new config keys are present
                assert "ORCHESTRATOR_REDO_ENABLED" in config
                assert "LEDGER_ENABLED" in config
                assert "LEDGER_LEVEL" in config
                assert "LEDGER_MAX_TRACE_BYTES" in config
                assert "LEDGER_SUMMARY_MAX_LINES" in config
                assert "ORCHESTRATION_TIME_BUDGET_MS" in config
                
                # Check default values
                assert config["ORCHESTRATOR_REDO_ENABLED"] is False
                assert config["LEDGER_ENABLED"] is False
                assert config["LEDGER_LEVEL"] == "off"
                assert config["LEDGER_MAX_TRACE_BYTES"] == 100_000
                assert config["LEDGER_SUMMARY_MAX_LINES"] == 4
                assert config["ORCHESTRATION_TIME_BUDGET_MS"] == 400
    
    def test_debug_config_shows_feature_flags(self):
        """Test that debug config endpoint shows feature flags."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "SUPABASE_URL": "test-url",
            "PINECONE_API_KEY": "test-pinecone-key",
            "PINECONE_INDEX": "test-index",
            "PINECONE_EXPLICATE_INDEX": "test-explicate",
            "PINECONE_IMPLICATE_INDEX": "test-implicate",
        }, clear=True):
            from router.debug import debug_config
            
            # Mock the API key requirement and feature flags
            with patch('router.debug._require_key'), \
                 patch('router.debug.get_all_flags') as mock_get_flags:
                
                mock_get_flags.return_value = {
                    "orchestrator.redo_enabled": False,
                    "ledger.enabled": False,
                    "retrieval.dual_index": True,
                }
                
                result = debug_config("test-api-key")
                
                assert result["status"] == "ok"
                flags = result["feature_flags"]
                
                # Check that new feature flags are present
                assert "orchestrator.redo_enabled" in flags
                assert "ledger.enabled" in flags
                assert flags["orchestrator.redo_enabled"] is False
                assert flags["ledger.enabled"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])