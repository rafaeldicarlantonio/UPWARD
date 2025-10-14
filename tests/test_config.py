# tests/test_config.py — unit tests for configuration and feature flags

import os
import pytest
from unittest.mock import patch, MagicMock
from config import load_config, REQUIRED
from feature_flags import get_feature_flag, get_all_flags, DEFAULT_FLAGS, set_feature_flag


class TestConfig:
    """Test configuration loading and validation."""
    
    def test_missing_required_env_vars_raises_exception(self):
        """Test that missing required environment variables raise a helpful exception."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                load_config()
            
            error_msg = str(exc_info.value)
            assert "Missing required environment variables" in error_msg
            assert "See env.sample for reference" in error_msg
            
            # Check that all required vars are mentioned
            for var in REQUIRED:
                assert var in error_msg
    
    def test_duplicate_pinecone_indices_raises_exception(self):
        """Test that duplicate Pinecone indices raise validation errors."""
        base_env = {
            "OPENAI_API_KEY": "test-key",
            "SUPABASE_URL": "test-url",
            "PINECONE_API_KEY": "test-key",
            "PINECONE_INDEX": "main-index",
            "PINECONE_EXPLICATE_INDEX": "explicate-index",
            "PINECONE_IMPLICATE_INDEX": "implicate-index",
        }
        
        # Test duplicate main and explicate
        with patch.dict(os.environ, {**base_env, "PINECONE_INDEX": "same-index", "PINECONE_EXPLICATE_INDEX": "same-index"}):
            with pytest.raises(RuntimeError) as exc_info:
                load_config()
            assert "PINECONE_INDEX and PINECONE_EXPLICATE_INDEX must be different" in str(exc_info.value)
        
        # Test duplicate main and implicate
        with patch.dict(os.environ, {**base_env, "PINECONE_INDEX": "same-index", "PINECONE_IMPLICATE_INDEX": "same-index"}):
            with pytest.raises(RuntimeError) as exc_info:
                load_config()
            assert "PINECONE_INDEX and PINECONE_IMPLICATE_INDEX must be different" in str(exc_info.value)
        
        # Test duplicate explicate and implicate
        with patch.dict(os.environ, {**base_env, "PINECONE_EXPLICATE_INDEX": "same-index", "PINECONE_IMPLICATE_INDEX": "same-index"}):
            with pytest.raises(RuntimeError) as exc_info:
                load_config()
            assert "PINECONE_EXPLICATE_INDEX and PINECONE_IMPLICATE_INDEX must be different" in str(exc_info.value)
    
    def test_valid_config_loads_successfully(self):
        """Test that valid configuration loads without errors."""
        env_vars = {
            "OPENAI_API_KEY": "test-key",
            "SUPABASE_URL": "test-url",
            "PINECONE_API_KEY": "test-key",
            "PINECONE_INDEX": "main-index",
            "PINECONE_EXPLICATE_INDEX": "explicate-index",
            "PINECONE_IMPLICATE_INDEX": "implicate-index",
        }
        
        with patch.dict(os.environ, env_vars):
            config = load_config()
            
            # Check that all required vars are present
            for var in REQUIRED:
                assert var in config
                assert config[var] == env_vars[var]
    
    def test_embed_dim_validation(self):
        """Test that EMBED_DIM is properly validated as integer."""
        base_env = {
            "OPENAI_API_KEY": "test-key",
            "SUPABASE_URL": "test-url",
            "PINECONE_API_KEY": "test-key",
            "PINECONE_INDEX": "main-index",
            "PINECONE_EXPLICATE_INDEX": "explicate-index",
            "PINECONE_IMPLICATE_INDEX": "implicate-index",
        }
        
        # Test valid integer
        with patch.dict(os.environ, {**base_env, "EMBED_DIM": "512"}):
            config = load_config()
            assert config["EMBED_DIM"] == 512
        
        # Test invalid non-integer
        with patch.dict(os.environ, {**base_env, "EMBED_DIM": "not-a-number"}):
            with pytest.raises(RuntimeError) as exc_info:
                load_config()
            assert "EMBED_DIM must be an integer" in str(exc_info.value)


class TestFeatureFlags:
    """Test feature flag functionality."""
    
    def test_default_flags_are_false(self):
        """Test that all default flags default to False."""
        for flag_name, default_value in DEFAULT_FLAGS.items():
            assert default_value is False, f"Flag {flag_name} should default to False"
    
    def test_get_feature_flag_with_database_failure(self):
        """Test that get_feature_flag falls back to default when database fails."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")
            
            result = get_feature_flag("retrieval.dual_index", default=True)
            assert result is True  # Should fall back to default
    
    def test_get_feature_flag_with_database_success(self):
        """Test that get_feature_flag returns database value when available."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_result = MagicMock()
            mock_result.data = [{"value": {"enabled": True}}]
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            
            result = get_feature_flag("retrieval.dual_index", default=False)
            assert result is True
    
    def test_get_all_flags_includes_defaults(self):
        """Test that get_all_flags includes all default flags."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.execute.return_value.data = []
            
            flags = get_all_flags()
            
            # All default flags should be present
            for flag_name in DEFAULT_FLAGS:
                assert flag_name in flags
                assert flags[flag_name] is False
    
    def test_set_feature_flag_success(self):
        """Test that set_feature_flag works correctly."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.upsert.return_value.execute.return_value = None
            
            # Should not raise an exception
            set_feature_flag("retrieval.dual_index", True)
            
            # Verify the call was made correctly
            mock_supabase.table.assert_called_with("feature_flags")
            mock_supabase.table.return_value.upsert.assert_called_with({
                "key": "retrieval.dual_index",
                "value": {"enabled": True}
            })
    
    def test_set_feature_flag_database_error(self):
        """Test that set_feature_flag raises exception on database error."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.upsert.return_value.execute.side_effect = Exception("DB error")
            
            with pytest.raises(RuntimeError) as exc_info:
                set_feature_flag("retrieval.dual_index", True)
            
            assert "Failed to set feature flag" in str(exc_info.value)
    
    def test_initialize_default_flags_success(self):
        """Test that initialize_default_flags works correctly."""
        with patch('feature_flags.supabase') as mock_supabase:
            # Mock that no flags exist initially
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
            mock_supabase.table.return_value.upsert.return_value.execute.return_value = None
            
            # Should not raise an exception
            from feature_flags import initialize_default_flags
            initialize_default_flags()
            
            # Should have called upsert for each default flag
            assert mock_supabase.table.return_value.upsert.call_count == len(DEFAULT_FLAGS)
    
    def test_initialize_default_flags_database_error(self):
        """Test that initialize_default_flags raises exception on database error."""
        with patch('feature_flags.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")
            
            with pytest.raises(RuntimeError) as exc_info:
                from feature_flags import initialize_default_flags
                initialize_default_flags()
            
            assert "Failed to initialize default flags" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__])