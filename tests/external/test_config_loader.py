"""
Tests for external source configuration loader.

Verifies validation, error handling, defaults, and edge cases.
"""

import pytest
import json
import yaml
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, Mock

from core.config_loader import (
    ConfigLoader,
    ExternalSource,
    ComparePolicy,
    get_loader,
    reset_loader,
    DEFAULT_WHITELIST,
    DEFAULT_COMPARE_POLICY,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_config_dir():
    """Create temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def valid_whitelist_data():
    """Valid whitelist configuration."""
    return [
        {
            "source_id": "wikipedia",
            "label": "Wikipedia",
            "priority": 10,
            "url_pattern": "https://.*\\.wikipedia\\.org/.*",
            "max_snippet_chars": 480,
            "enabled": True
        },
        {
            "source_id": "arxiv",
            "label": "arXiv",
            "priority": 9,
            "url_pattern": "https://arxiv\\.org/.*",
            "max_snippet_chars": 640,
            "enabled": True
        },
        {
            "source_id": "disabled_source",
            "label": "Disabled",
            "priority": 5,
            "url_pattern": "https://example\\.com/.*",
            "max_snippet_chars": 300,
            "enabled": False
        }
    ]


@pytest.fixture
def valid_policy_data():
    """Valid policy configuration."""
    return {
        "max_external_sources_per_run": 6,
        "max_total_external_chars": 2400,
        "allowed_roles_for_external": ["pro", "scholars", "analytics"],
        "timeout_ms_per_request": 2000,
        "rate_limit_per_domain_per_min": 6,
        "tie_break": "prefer_internal",
        "redact_patterns": [
            "Authorization:\\s+\\S+",
            "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
        ]
    }


@pytest.fixture
def create_config_files(temp_config_dir, valid_whitelist_data, valid_policy_data):
    """Create valid config files in temp directory."""
    whitelist_path = temp_config_dir / "whitelist.json"
    policy_path = temp_config_dir / "policy.yaml"
    
    with open(whitelist_path, 'w') as f:
        json.dump(valid_whitelist_data, f)
    
    with open(policy_path, 'w') as f:
        yaml.dump(valid_policy_data, f)
    
    return whitelist_path, policy_path


@pytest.fixture(autouse=True)
def reset_global_loader():
    """Reset global loader before each test."""
    reset_loader()
    yield
    reset_loader()


# ============================================================================
# ExternalSource Tests
# ============================================================================

class TestExternalSource:
    """Test ExternalSource data class validation."""
    
    def test_valid_source_creation(self):
        """Test creating a valid external source."""
        source = ExternalSource(
            source_id="test",
            label="Test Source",
            priority=5,
            url_pattern="https://test\\.com/.*",
            max_snippet_chars=500,
            enabled=True
        )
        
        assert source.source_id == "test"
        assert source.label == "Test Source"
        assert source.priority == 5
        assert source.max_snippet_chars == 500
        assert source.enabled is True
    
    def test_default_enabled(self):
        """Test enabled defaults to True."""
        source = ExternalSource(
            source_id="test",
            label="Test",
            priority=5,
            url_pattern="https://test\\.com/.*",
            max_snippet_chars=500
        )
        
        assert source.enabled is True
    
    def test_empty_source_id_raises(self):
        """Test empty source_id raises ValueError."""
        with pytest.raises(ValueError, match="source_id cannot be empty"):
            ExternalSource(
                source_id="",
                label="Test",
                priority=5,
                url_pattern="https://test\\.com/.*",
                max_snippet_chars=500
            )
    
    def test_negative_priority_raises(self):
        """Test negative priority raises ValueError."""
        with pytest.raises(ValueError, match="priority must be non-negative"):
            ExternalSource(
                source_id="test",
                label="Test",
                priority=-1,
                url_pattern="https://test\\.com/.*",
                max_snippet_chars=500
            )
    
    def test_zero_max_snippet_chars_raises(self):
        """Test zero max_snippet_chars raises ValueError."""
        with pytest.raises(ValueError, match="max_snippet_chars must be positive"):
            ExternalSource(
                source_id="test",
                label="Test",
                priority=5,
                url_pattern="https://test\\.com/.*",
                max_snippet_chars=0
            )
    
    def test_invalid_regex_pattern_raises(self):
        """Test invalid regex pattern raises ValueError."""
        with pytest.raises(ValueError, match="Invalid url_pattern regex"):
            ExternalSource(
                source_id="test",
                label="Test",
                priority=5,
                url_pattern="[invalid(regex",  # Unclosed bracket
                max_snippet_chars=500
            )
    
    def test_to_dict(self):
        """Test converting source to dictionary."""
        source = ExternalSource(
            source_id="test",
            label="Test Source",
            priority=5,
            url_pattern="https://test\\.com/.*",
            max_snippet_chars=500,
            enabled=False
        )
        
        d = source.to_dict()
        
        assert d["source_id"] == "test"
        assert d["label"] == "Test Source"
        assert d["priority"] == 5
        assert d["enabled"] is False


# ============================================================================
# ComparePolicy Tests
# ============================================================================

class TestComparePolicy:
    """Test ComparePolicy data class validation."""
    
    def test_valid_policy_creation(self):
        """Test creating a valid policy."""
        policy = ComparePolicy(
            max_external_sources_per_run=5,
            max_total_external_chars=2000,
            allowed_roles_for_external=["pro"],
            timeout_ms_per_request=1500,
            rate_limit_per_domain_per_min=10,
            tie_break="prefer_external",
            redact_patterns=["test"]
        )
        
        assert policy.max_external_sources_per_run == 5
        assert policy.tie_break == "prefer_external"
        assert "pro" in policy.allowed_roles_for_external
    
    def test_default_values(self):
        """Test policy default values."""
        policy = ComparePolicy()
        
        assert policy.max_external_sources_per_run == 6
        assert policy.max_total_external_chars == 2400
        assert policy.timeout_ms_per_request == 2000
        assert policy.tie_break == "prefer_internal"
        assert isinstance(policy.allowed_roles_for_external, list)
    
    def test_negative_max_sources_raises(self):
        """Test negative max_external_sources_per_run raises."""
        with pytest.raises(ValueError, match="max_external_sources_per_run must be positive"):
            ComparePolicy(max_external_sources_per_run=0)
    
    def test_negative_max_chars_raises(self):
        """Test negative max_total_external_chars raises."""
        with pytest.raises(ValueError, match="max_total_external_chars must be positive"):
            ComparePolicy(max_total_external_chars=-100)
    
    def test_invalid_tie_break_raises(self):
        """Test invalid tie_break value raises."""
        with pytest.raises(ValueError, match="tie_break must be one of"):
            ComparePolicy(tie_break="invalid_option")
    
    def test_invalid_redact_pattern_raises(self):
        """Test invalid regex in redact_patterns raises."""
        with pytest.raises(ValueError, match="Invalid redact_pattern regex"):
            ComparePolicy(redact_patterns=["[invalid(regex"])
    
    def test_to_dict(self):
        """Test converting policy to dictionary."""
        policy = ComparePolicy(
            max_external_sources_per_run=3,
            tie_break="abstain"
        )
        
        d = policy.to_dict()
        
        assert d["max_external_sources_per_run"] == 3
        assert d["tie_break"] == "abstain"


# ============================================================================
# ConfigLoader Happy Path Tests
# ============================================================================

class TestConfigLoaderHappyPath:
    """Test ConfigLoader with valid configurations."""
    
    def test_load_valid_configs(self, create_config_files):
        """Test loading valid configuration files."""
        whitelist_path, policy_path = create_config_files
        
        loader = ConfigLoader(
            whitelist_path=str(whitelist_path),
            policy_path=str(policy_path)
        )
        
        # Check whitelist loaded
        whitelist = loader.get_whitelist()
        assert len(whitelist) == 2  # Only enabled sources
        assert whitelist[0].source_id == "wikipedia"  # Sorted by priority
        assert whitelist[1].source_id == "arxiv"
        
        # Check all sources (including disabled)
        all_sources = loader.get_whitelist(enabled_only=False)
        assert len(all_sources) == 3
        
        # Check policy loaded
        policy = loader.get_compare_policy()
        assert policy.max_external_sources_per_run == 6
        assert policy.tie_break == "prefer_internal"
        assert "pro" in policy.allowed_roles_for_external
    
    def test_sources_sorted_by_priority(self, temp_config_dir):
        """Test sources are sorted by priority (highest first)."""
        whitelist_data = [
            {
                "source_id": "low",
                "label": "Low Priority",
                "priority": 1,
                "url_pattern": "https://low\\.com/.*",
                "max_snippet_chars": 100,
                "enabled": True
            },
            {
                "source_id": "high",
                "label": "High Priority",
                "priority": 10,
                "url_pattern": "https://high\\.com/.*",
                "max_snippet_chars": 100,
                "enabled": True
            },
            {
                "source_id": "med",
                "label": "Medium Priority",
                "priority": 5,
                "url_pattern": "https://med\\.com/.*",
                "max_snippet_chars": 100,
                "enabled": True
            }
        ]
        
        whitelist_path = temp_config_dir / "whitelist.json"
        with open(whitelist_path, 'w') as f:
            json.dump(whitelist_data, f)
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        sources = loader.get_whitelist()
        
        assert sources[0].source_id == "high"  # priority 10
        assert sources[1].source_id == "med"   # priority 5
        assert sources[2].source_id == "low"   # priority 1
    
    def test_get_source_by_id(self, create_config_files):
        """Test getting source by ID."""
        whitelist_path, policy_path = create_config_files
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        source = loader.get_source_by_id("arxiv")
        assert source is not None
        assert source.label == "arXiv"
        
        not_found = loader.get_source_by_id("nonexistent")
        assert not_found is None
    
    def test_to_dict(self, create_config_files):
        """Test exporting config to dictionary."""
        whitelist_path, policy_path = create_config_files
        loader = ConfigLoader(
            whitelist_path=str(whitelist_path),
            policy_path=str(policy_path)
        )
        
        config_dict = loader.to_dict()
        
        assert "whitelist" in config_dict
        assert "policy" in config_dict
        assert len(config_dict["whitelist"]) == 3
        assert config_dict["policy"]["tie_break"] == "prefer_internal"


# ============================================================================
# ConfigLoader Missing Files Tests
# ============================================================================

class TestConfigLoaderMissingFiles:
    """Test ConfigLoader behavior with missing files."""
    
    def test_missing_whitelist_uses_defaults(self, temp_config_dir, caplog):
        """Test missing whitelist file falls back to defaults."""
        caplog.set_level(logging.WARNING)
        
        nonexistent = temp_config_dir / "nonexistent.json"
        
        loader = ConfigLoader(whitelist_path=str(nonexistent))
        
        # Should log warning
        assert "Whitelist file not found" in caplog.text
        assert "Using default whitelist" in caplog.text
        
        # Should use defaults
        whitelist = loader.get_whitelist()
        assert len(whitelist) >= 1
        assert whitelist[0].source_id == "wikipedia"
    
    def test_missing_policy_uses_defaults(self, temp_config_dir, caplog):
        """Test missing policy file falls back to defaults."""
        caplog.set_level(logging.WARNING)
        
        nonexistent = temp_config_dir / "nonexistent.yaml"
        
        loader = ConfigLoader(policy_path=str(nonexistent))
        
        # Should log warning
        assert "Policy file not found" in caplog.text
        assert "Using default policy" in caplog.text
        
        # Should use defaults
        policy = loader.get_compare_policy()
        assert policy.max_external_sources_per_run == DEFAULT_COMPARE_POLICY["max_external_sources_per_run"]
        assert policy.tie_break == DEFAULT_COMPARE_POLICY["tie_break"]
    
    def test_both_files_missing(self, temp_config_dir, caplog):
        """Test both files missing uses all defaults."""
        caplog.set_level(logging.WARNING)
        
        loader = ConfigLoader(
            whitelist_path=str(temp_config_dir / "missing1.json"),
            policy_path=str(temp_config_dir / "missing2.yaml")
        )
        
        whitelist = loader.get_whitelist()
        policy = loader.get_compare_policy()
        
        assert len(whitelist) >= 1
        assert policy is not None


# ============================================================================
# ConfigLoader Malformed Config Tests
# ============================================================================

class TestConfigLoaderMalformedConfigs:
    """Test ConfigLoader behavior with malformed configurations."""
    
    def test_invalid_json_syntax(self, temp_config_dir, caplog):
        """Test invalid JSON syntax falls back to defaults."""
        caplog.set_level(logging.ERROR)
        
        whitelist_path = temp_config_dir / "bad.json"
        with open(whitelist_path, 'w') as f:
            f.write("{invalid json syntax")
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        assert "Failed to parse whitelist JSON" in caplog.text
        
        whitelist = loader.get_whitelist()
        assert len(whitelist) >= 1  # Should use defaults
    
    def test_invalid_yaml_syntax(self, temp_config_dir, caplog):
        """Test invalid YAML syntax falls back to defaults."""
        caplog.set_level(logging.ERROR)
        
        policy_path = temp_config_dir / "bad.yaml"
        with open(policy_path, 'w') as f:
            f.write("invalid: yaml: syntax: [unclosed")
        
        loader = ConfigLoader(policy_path=str(policy_path))
        
        assert "Failed to parse policy YAML" in caplog.text
        
        policy = loader.get_compare_policy()
        assert policy.tie_break == "prefer_internal"  # Default
    
    def test_whitelist_not_array(self, temp_config_dir, caplog):
        """Test whitelist that's not an array."""
        caplog.set_level(logging.ERROR)
        
        whitelist_path = temp_config_dir / "notarray.json"
        with open(whitelist_path, 'w') as f:
            json.dump({"not": "an array"}, f)
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        assert "Whitelist must be a JSON array" in caplog.text
        
        whitelist = loader.get_whitelist()
        assert len(whitelist) >= 1  # Should use defaults
    
    def test_policy_not_mapping(self, temp_config_dir, caplog):
        """Test policy that's not a mapping."""
        caplog.set_level(logging.ERROR)
        
        policy_path = temp_config_dir / "notmapping.yaml"
        with open(policy_path, 'w') as f:
            yaml.dump(["not", "a", "mapping"], f)
        
        loader = ConfigLoader(policy_path=str(policy_path))
        
        assert "Policy must be a YAML mapping" in caplog.text
        
        policy = loader.get_compare_policy()
        assert policy is not None
    
    def test_whitelist_entry_missing_required_fields(self, temp_config_dir, caplog):
        """Test whitelist entry missing required fields is skipped."""
        caplog.set_level(logging.WARNING)
        
        whitelist_data = [
            {
                "source_id": "incomplete",
                "label": "Missing Fields"
                # Missing: priority, url_pattern, max_snippet_chars
            },
            {
                "source_id": "complete",
                "label": "Complete",
                "priority": 5,
                "url_pattern": "https://test\\.com/.*",
                "max_snippet_chars": 300
            }
        ]
        
        whitelist_path = temp_config_dir / "incomplete.json"
        with open(whitelist_path, 'w') as f:
            json.dump(whitelist_data, f)
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        assert "missing required fields" in caplog.text
        
        whitelist = loader.get_whitelist()
        assert len(whitelist) == 1
        assert whitelist[0].source_id == "complete"
    
    def test_whitelist_entry_invalid_values(self, temp_config_dir, caplog):
        """Test whitelist entry with invalid values is skipped."""
        caplog.set_level(logging.WARNING)
        
        whitelist_data = [
            {
                "source_id": "bad_priority",
                "label": "Bad",
                "priority": -5,  # Invalid: negative
                "url_pattern": "https://test\\.com/.*",
                "max_snippet_chars": 300
            },
            {
                "source_id": "good",
                "label": "Good",
                "priority": 5,
                "url_pattern": "https://test\\.com/.*",
                "max_snippet_chars": 300
            }
        ]
        
        whitelist_path = temp_config_dir / "invalid.json"
        with open(whitelist_path, 'w') as f:
            json.dump(whitelist_data, f)
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        assert "Invalid whitelist entry" in caplog.text
        
        whitelist = loader.get_whitelist()
        assert len(whitelist) == 1
        assert whitelist[0].source_id == "good"
    
    def test_policy_invalid_values(self, temp_config_dir, caplog):
        """Test policy with invalid values falls back to defaults."""
        caplog.set_level(logging.ERROR)
        
        policy_data = {
            "max_external_sources_per_run": -5,  # Invalid: negative
            "tie_break": "invalid_option"  # Invalid: not in allowed list
        }
        
        policy_path = temp_config_dir / "badpolicy.yaml"
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        loader = ConfigLoader(policy_path=str(policy_path))
        
        assert "Invalid policy configuration" in caplog.text
        
        policy = loader.get_compare_policy()
        assert policy.max_external_sources_per_run == 3  # Default
        assert policy.tie_break == "prefer_internal"  # Default
    
    def test_all_whitelist_entries_invalid(self, temp_config_dir, caplog):
        """Test all whitelist entries invalid uses defaults."""
        caplog.set_level(logging.WARNING)
        
        whitelist_data = [
            {"source_id": "bad1", "priority": -1},  # Missing fields, bad priority
            {"source_id": "bad2", "label": "Bad"}   # Missing fields
        ]
        
        whitelist_path = temp_config_dir / "allbad.json"
        with open(whitelist_path, 'w') as f:
            json.dump(whitelist_data, f)
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        assert "No valid sources in whitelist" in caplog.text
        
        whitelist = loader.get_whitelist()
        assert len(whitelist) >= 1  # Should use defaults


# ============================================================================
# ConfigLoader Reload Tests
# ============================================================================

class TestConfigLoaderReload:
    """Test configuration reloading."""
    
    def test_reload_configs(self, temp_config_dir, valid_whitelist_data, valid_policy_data):
        """Test reloading configurations from disk."""
        whitelist_path = temp_config_dir / "whitelist.json"
        policy_path = temp_config_dir / "policy.yaml"
        
        # Write initial config
        with open(whitelist_path, 'w') as f:
            json.dump(valid_whitelist_data[:1], f)  # Only first source
        
        with open(policy_path, 'w') as f:
            yaml.dump({"max_external_sources_per_run": 3}, f)
        
        loader = ConfigLoader(
            whitelist_path=str(whitelist_path),
            policy_path=str(policy_path)
        )
        
        # Check initial state
        assert len(loader.get_whitelist(enabled_only=False)) == 1
        assert loader.get_compare_policy().max_external_sources_per_run == 3
        
        # Update config files
        with open(whitelist_path, 'w') as f:
            json.dump(valid_whitelist_data, f)  # All sources
        
        with open(policy_path, 'w') as f:
            yaml.dump({"max_external_sources_per_run": 10}, f)
        
        # Reload
        loader.reload()
        
        # Check updated state
        assert len(loader.get_whitelist(enabled_only=False)) == 3
        assert loader.get_compare_policy().max_external_sources_per_run == 10


# ============================================================================
# Global Loader Tests
# ============================================================================

class TestGlobalLoader:
    """Test global loader singleton."""
    
    def test_get_loader_singleton(self, create_config_files):
        """Test get_loader returns singleton."""
        whitelist_path, policy_path = create_config_files
        
        loader1 = get_loader(
            whitelist_path=str(whitelist_path),
            policy_path=str(policy_path)
        )
        loader2 = get_loader()  # Should return same instance
        
        assert loader1 is loader2
    
    def test_get_loader_force_reload(self, create_config_files):
        """Test force_reload creates new instance."""
        whitelist_path, policy_path = create_config_files
        
        loader1 = get_loader(
            whitelist_path=str(whitelist_path),
            policy_path=str(policy_path)
        )
        loader2 = get_loader(force_reload=True)
        
        assert loader1 is not loader2
    
    def test_reset_loader(self, create_config_files):
        """Test reset_loader clears singleton."""
        whitelist_path, policy_path = create_config_files
        
        loader1 = get_loader(
            whitelist_path=str(whitelist_path),
            policy_path=str(policy_path)
        )
        
        reset_loader()
        
        loader2 = get_loader()
        assert loader1 is not loader2


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_whitelist_array(self, temp_config_dir, caplog):
        """Test empty whitelist array uses defaults."""
        caplog.set_level(logging.WARNING)
        
        whitelist_path = temp_config_dir / "empty.json"
        with open(whitelist_path, 'w') as f:
            json.dump([], f)
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        assert "No valid sources in whitelist" in caplog.text
        
        whitelist = loader.get_whitelist()
        assert len(whitelist) >= 1  # Should use defaults
    
    def test_policy_partial_override(self, temp_config_dir):
        """Test policy with only some fields overrides defaults for those fields."""
        policy_data = {
            "max_external_sources_per_run": 10,
            "tie_break": "prefer_external"
            # Other fields not specified
        }
        
        policy_path = temp_config_dir / "partial.yaml"
        with open(policy_path, 'w') as f:
            yaml.dump(policy_data, f)
        
        loader = ConfigLoader(policy_path=str(policy_path))
        policy = loader.get_compare_policy()
        
        # Overridden fields
        assert policy.max_external_sources_per_run == 10
        assert policy.tie_break == "prefer_external"
        
        # Default fields
        assert policy.timeout_ms_per_request == DEFAULT_COMPARE_POLICY["timeout_ms_per_request"]
        assert policy.max_total_external_chars == DEFAULT_COMPARE_POLICY["max_total_external_chars"]
    
    def test_source_with_complex_regex(self):
        """Test source with complex but valid regex pattern."""
        source = ExternalSource(
            source_id="complex",
            label="Complex Pattern",
            priority=5,
            url_pattern=r"https://(www\.|en\.)?example\.(com|org)/path/[a-z0-9\-_]+/?",
            max_snippet_chars=500
        )
        
        assert source.source_id == "complex"
    
    def test_policy_with_empty_redact_patterns(self):
        """Test policy with empty redact patterns list."""
        policy = ComparePolicy(redact_patterns=[])
        
        assert policy.redact_patterns == []
    
    def test_workspace_root_custom_path(self, temp_config_dir):
        """Test using custom workspace root."""
        config_dir = temp_config_dir / "custom_config"
        config_dir.mkdir()
        
        whitelist_path = config_dir / "external_sources_whitelist.json"
        with open(whitelist_path, 'w') as f:
            json.dump(DEFAULT_WHITELIST, f)
        
        loader = ConfigLoader(workspace_root=str(temp_config_dir / "custom_config"))
        
        # Should find the config in custom location
        whitelist = loader.get_whitelist()
        assert len(whitelist) >= 1


# ============================================================================
# Summary Test
# ============================================================================

class TestAcceptanceCriteria:
    """Verify all acceptance criteria are met."""
    
    def test_loader_rejects_invalid_shapes(self, temp_config_dir, caplog):
        """Verify loader rejects invalid config shapes."""
        caplog.set_level(logging.WARNING)
        
        # Invalid whitelist entry
        whitelist_data = [
            {"source_id": "bad", "priority": "not_an_int"}  # Bad type
        ]
        
        whitelist_path = temp_config_dir / "bad.json"
        with open(whitelist_path, 'w') as f:
            json.dump(whitelist_data, f)
        
        loader = ConfigLoader(whitelist_path=str(whitelist_path))
        
        # Should log warning and skip
        assert "Invalid whitelist entry" in caplog.text or "missing required fields" in caplog.text
    
    def test_loader_logs_warnings(self, temp_config_dir, caplog):
        """Verify loader logs warnings for issues."""
        caplog.set_level(logging.WARNING)
        
        nonexistent = temp_config_dir / "missing.json"
        
        ConfigLoader(whitelist_path=str(nonexistent))
        
        assert len(caplog.records) > 0
        assert any("Whitelist file not found" in record.message for record in caplog.records)
    
    def test_loader_falls_back_to_safe_defaults(self, temp_config_dir):
        """Verify loader falls back to safe defaults on errors."""
        # Missing files
        loader = ConfigLoader(
            whitelist_path=str(temp_config_dir / "missing1.json"),
            policy_path=str(temp_config_dir / "missing2.yaml")
        )
        
        whitelist = loader.get_whitelist()
        policy = loader.get_compare_policy()
        
        # Should have defaults
        assert len(whitelist) >= 1
        assert policy.max_external_sources_per_run > 0
        assert policy.tie_break in ["prefer_internal", "prefer_external", "abstain"]
    
    def test_happy_path_loads_correctly(self, create_config_files):
        """Verify happy path loads configurations correctly."""
        whitelist_path, policy_path = create_config_files
        
        loader = ConfigLoader(
            whitelist_path=str(whitelist_path),
            policy_path=str(policy_path)
        )
        
        whitelist = loader.get_whitelist()
        policy = loader.get_compare_policy()
        
        # Should load actual configs
        assert len(whitelist) == 2  # Enabled sources
        assert whitelist[0].priority >= whitelist[1].priority  # Sorted
        assert policy.max_external_sources_per_run == 6
    
    def test_missing_file_uses_defaults(self, temp_config_dir):
        """Verify missing files use defaults."""
        loader = ConfigLoader(
            whitelist_path=str(temp_config_dir / "nonexistent.json")
        )
        
        whitelist = loader.get_whitelist()
        
        # Should use defaults, not crash
        assert len(whitelist) >= 1
        assert all(isinstance(s, ExternalSource) for s in whitelist)
    
    def test_malformed_config_uses_defaults(self, temp_config_dir):
        """Verify malformed configs use defaults."""
        # Bad JSON
        bad_path = temp_config_dir / "bad.json"
        with open(bad_path, 'w') as f:
            f.write("{not valid json")
        
        loader = ConfigLoader(whitelist_path=str(bad_path))
        
        whitelist = loader.get_whitelist()
        
        # Should use defaults, not crash
        assert len(whitelist) >= 1
