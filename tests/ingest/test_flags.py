#!/usr/bin/env python3
"""Tests covering ingest-related flags and configuration."""

import os
from unittest.mock import patch

import pytest

from config import load_config, DEFAULTS
from feature_flags import DEFAULT_FLAGS


def _required_env():
    """Minimal required env vars for loading config."""
    return {
        "OPENAI_API_KEY": "test-key",
        "SUPABASE_URL": "https://example.supabase.co",
        "PINECONE_API_KEY": "pinecone-key",
        "PINECONE_INDEX": "test-index",
        "PINECONE_EXPLICATE_INDEX": "test-explicate",
        "PINECONE_IMPLICATE_INDEX": "test-implicate",
    }


class TestIngestConfigDefaults:
    """Defaults and validation for ingest configuration."""

    def test_defaults_are_present(self):
        with patch.dict(os.environ, _required_env(), clear=True):
            config = load_config()

        assert config["INGEST_ANALYSIS_ENABLED"] is False
        assert config["INGEST_ANALYSIS_MAX_MS_PER_CHUNK"] == 40
        assert config["INGEST_ANALYSIS_MAX_VERBS"] == 20
        assert config["INGEST_ANALYSIS_MAX_FRAMES"] == 10
        assert config["INGEST_ANALYSIS_MAX_CONCEPTS"] == 10
        assert config["INGEST_CONTRADICTIONS_ENABLED"] is False
        assert config["INGEST_IMPLICATE_REFRESH_ENABLED"] is False

    @pytest.mark.parametrize(
        "env_key",
        [
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK",
            "INGEST_ANALYSIS_MAX_VERBS",
            "INGEST_ANALYSIS_MAX_FRAMES",
            "INGEST_ANALYSIS_MAX_CONCEPTS",
        ],
    )
    def test_positive_integer_validation(self, env_key):
        base_env = _required_env()

        with patch.dict(os.environ, {**base_env, env_key: "not-a-number"}, clear=True):
            with pytest.raises(RuntimeError, match=f"{env_key} must be a positive integer"):
                load_config()

        with patch.dict(os.environ, {**base_env, env_key: "0"}, clear=True):
            with pytest.raises(RuntimeError, match=f"{env_key} must be a positive integer"):
                load_config()

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
            (None, False),
        ],
    )
    def test_boolean_validation(self, env_value, expected):
        base_env = _required_env()
        env = {**base_env}
        env["INGEST_ANALYSIS_ENABLED"] = "" if env_value is None else str(env_value)
        env["INGEST_CONTRADICTIONS_ENABLED"] = "" if env_value is None else str(env_value)
        env["INGEST_IMPLICATE_REFRESH_ENABLED"] = "" if env_value is None else str(env_value)

        with patch.dict(os.environ, env, clear=True):
            config = load_config()

        assert config["INGEST_ANALYSIS_ENABLED"] is expected
        assert config["INGEST_CONTRADICTIONS_ENABLED"] is expected
        assert config["INGEST_IMPLICATE_REFRESH_ENABLED"] is expected


class TestIngestFeatureFlags:
    """Ensure ingest feature flags are discoverable."""

    def test_default_flags_are_false(self):
        assert DEFAULT_FLAGS["ingest.analysis.enabled"] is False
        assert DEFAULT_FLAGS["ingest.contradictions.enabled"] is False
        assert DEFAULT_FLAGS["ingest.implicate.refresh_enabled"] is False


class TestDebugConfigExposure:
    """/debug/config should expose ingest keys."""

    def test_debug_config_lists_ingest_config_and_flags(self):
        base_env = _required_env()

        with patch.dict(os.environ, base_env, clear=True):
            from router.debug import debug_config

            with patch("router.debug._require_key"), patch(
                "router.debug.get_all_flags", return_value=DEFAULT_FLAGS.copy()
            ):
                response = debug_config("fake-key")

        assert response["status"] == "ok"

        config = response["config"]
        assert config["INGEST_ANALYSIS_ENABLED"] is False
        assert config["INGEST_ANALYSIS_MAX_MS_PER_CHUNK"] == 40
        assert config["INGEST_ANALYSIS_MAX_VERBS"] == 20
        assert config["INGEST_ANALYSIS_MAX_FRAMES"] == 10
        assert config["INGEST_ANALYSIS_MAX_CONCEPTS"] == 10
        assert config["INGEST_CONTRADICTIONS_ENABLED"] is False
        assert config["INGEST_IMPLICATE_REFRESH_ENABLED"] is False

        flags = response["feature_flags"]
        assert flags["ingest.analysis.enabled"] is False
        assert flags["ingest.contradictions.enabled"] is False
        assert flags["ingest.implicate.refresh_enabled"] is False


def test_defaults_dictionary_contains_ingest_keys():
    """Sanity check: shared defaults dict exposes ingest keys for discoverability."""
    assert DEFAULTS["INGEST_ANALYSIS_ENABLED"] is False
    assert DEFAULTS["INGEST_ANALYSIS_MAX_MS_PER_CHUNK"] == 40
    assert DEFAULTS["INGEST_ANALYSIS_MAX_VERBS"] == 20
    assert DEFAULTS["INGEST_ANALYSIS_MAX_FRAMES"] == 10
    assert DEFAULTS["INGEST_ANALYSIS_MAX_CONCEPTS"] == 10
    assert DEFAULTS["INGEST_CONTRADICTIONS_ENABLED"] is False
    assert DEFAULTS["INGEST_IMPLICATE_REFRESH_ENABLED"] is False
