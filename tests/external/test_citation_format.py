"""
Tests for external evidence citation formatting.

Verifies that external sources are formatted distinctly with proper
truncation, redaction, and provenance information.
"""

import os
import pytest
import tempfile
import yaml
import json
from pathlib import Path
from datetime import datetime, timezone

# Set up mock environment variables
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
os.environ.setdefault("PINECONE_EXPLICATE_INDEX", "test-explicate")
os.environ.setdefault("PINECONE_IMPLICATE_INDEX", "test-implicate")

from core.presenters import format_external_evidence, format_chat_response_with_externals
from core.config_loader import ConfigLoader, reset_loader


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_config_dir():
    """Create temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_whitelist(temp_config_dir):
    """Create sample whitelist configuration."""
    whitelist_data = [
        {
            "source_id": "wikipedia",
            "label": "Wikipedia",
            "priority": 10,
            "url_pattern": "https://.*\\.wikipedia\\.org/.*",
            "max_snippet_chars": 200,
            "enabled": True
        },
        {
            "source_id": "arxiv",
            "label": "arXiv",
            "priority": 9,
            "url_pattern": "https://arxiv\\.org/.*",
            "max_snippet_chars": 300,
            "enabled": True
        }
    ]
    
    whitelist_path = temp_config_dir / "whitelist.json"
    with open(whitelist_path, 'w') as f:
        json.dump(whitelist_data, f)
    
    return whitelist_path


@pytest.fixture
def sample_policy(temp_config_dir):
    """Create sample policy with redaction patterns."""
    policy_data = {
        "max_external_sources_per_run": 6,
        "timeout_ms_per_request": 2000,
        "allowed_roles_for_external": ["pro", "scholars"],
        "redact_patterns": [
            "Authorization:\\s+\\S+",
            "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*",
            "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
        ]
    }
    
    policy_path = temp_config_dir / "policy.yaml"
    with open(policy_path, 'w') as f:
        yaml.dump(policy_data, f)
    
    return policy_path


@pytest.fixture
def config_loader(sample_whitelist, sample_policy):
    """Create configured loader."""
    reset_loader()
    loader = ConfigLoader(
        whitelist_path=str(sample_whitelist),
        policy_path=str(sample_policy)
    )
    yield loader
    reset_loader()


@pytest.fixture
def sample_external_items():
    """Sample external evidence items."""
    return [
        {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Machine_Learning",
            "snippet": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
            "fetched_at": "2025-10-30T12:00:00Z"
        },
        {
            "source_id": "arxiv",
            "url": "https://arxiv.org/abs/1234.5678",
            "snippet": "This paper presents a novel approach to deep learning architectures.",
            "fetched_at": "2025-10-30T12:05:00Z"
        }
    ]


# ============================================================================
# Basic Formatting Tests
# ============================================================================

class TestBasicFormatting:
    """Test basic external evidence formatting."""
    
    def test_format_single_item(self, config_loader, sample_external_items):
        """Test formatting a single external item."""
        result = format_external_evidence(
            [sample_external_items[0]],
            config_loader=config_loader
        )
        
        assert result["heading"] == "External sources"
        assert len(result["items"]) == 1
        
        item = result["items"][0]
        assert item["label"] == "Wikipedia"
        assert item["host"] == "en.wikipedia.org"
        assert "Machine learning" in item["snippet"]
        assert item["provenance"]["url"] == "https://en.wikipedia.org/wiki/Machine_Learning"
        assert item["provenance"]["fetched_at"] == "2025-10-30T12:00:00Z"
    
    def test_format_multiple_items(self, config_loader, sample_external_items):
        """Test formatting multiple external items."""
        result = format_external_evidence(
            sample_external_items,
            config_loader=config_loader
        )
        
        assert result["heading"] == "External sources"
        assert len(result["items"]) == 2
        
        # Check first item
        assert result["items"][0]["label"] == "Wikipedia"
        assert result["items"][0]["host"] == "en.wikipedia.org"
        
        # Check second item
        assert result["items"][1]["label"] == "arXiv"
        assert result["items"][1]["host"] == "arxiv.org"
    
    def test_empty_items_list(self, config_loader):
        """Test formatting empty items list."""
        result = format_external_evidence([], config_loader=config_loader)
        
        assert result["heading"] == "External sources"
        assert result["items"] == []
    
    def test_unknown_source_fallback(self, config_loader):
        """Test handling unknown source ID."""
        item = {
            "source_id": "unknown_source",
            "url": "https://example.com/article",
            "snippet": "Some content here.",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        assert len(result["items"]) == 1
        assert result["items"][0]["label"] == "Unknown Source"  # Titlecased with space
        assert result["items"][0]["host"] == "example.com"


# ============================================================================
# Truncation Tests
# ============================================================================

class TestTruncation:
    """Test snippet truncation."""
    
    def test_truncate_long_snippet(self, config_loader):
        """Test truncation of long snippets."""
        long_text = "This is a very long piece of text. " * 50  # Much longer than 200 chars
        
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": long_text,
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        # Wikipedia max_snippet_chars is 200
        truncated = result["items"][0]["snippet"]
        assert len(truncated) <= 204  # 200 + "..."
        assert truncated.endswith("...")
    
    def test_truncate_at_word_boundary(self, config_loader):
        """Test truncation respects word boundaries."""
        text = "The quick brown fox jumps over the lazy dog. " * 10
        
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": text,
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        truncated = result["items"][0]["snippet"]
        # Should not end with partial word (before "...")
        words = truncated.replace("...", "").strip().split()
        last_word = words[-1]
        assert last_word in text  # Complete word from original
    
    def test_short_snippet_not_truncated(self, config_loader):
        """Test short snippets are not truncated."""
        short_text = "This is short."
        
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": short_text,
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        assert result["items"][0]["snippet"] == short_text
        assert not result["items"][0]["snippet"].endswith("...")
    
    def test_different_max_chars_per_source(self, config_loader):
        """Test different sources have different max_snippet_chars."""
        long_text = "A " * 500  # 1000 chars
        
        items = [
            {
                "source_id": "wikipedia",  # max 200
                "url": "https://en.wikipedia.org/wiki/Test",
                "snippet": long_text,
                "fetched_at": "2025-10-30T12:00:00Z"
            },
            {
                "source_id": "arxiv",  # max 300
                "url": "https://arxiv.org/abs/1234.5678",
                "snippet": long_text,
                "fetched_at": "2025-10-30T12:00:00Z"
            }
        ]
        
        result = format_external_evidence(items, config_loader=config_loader)
        
        wiki_len = len(result["items"][0]["snippet"])
        arxiv_len = len(result["items"][1]["snippet"])
        
        # arXiv should be longer (300 vs 200)
        assert arxiv_len > wiki_len


# ============================================================================
# Redaction Tests
# ============================================================================

class TestRedaction:
    """Test content redaction."""
    
    def test_redact_authorization_header(self, config_loader):
        """Test redaction of Authorization headers."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "Some text Authorization: Bearer token123 more text",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        snippet = result["items"][0]["snippet"]
        assert "token123" not in snippet
        assert "[REDACTED]" in snippet
        assert "Some text" in snippet
        assert "more text" in snippet
    
    def test_redact_bearer_token(self, config_loader):
        """Test redaction of Bearer tokens."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "Token: Bearer abc123xyz-_~+/= in the text",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        snippet = result["items"][0]["snippet"]
        assert "abc123xyz" not in snippet
        assert "[REDACTED]" in snippet
    
    def test_redact_email_addresses(self, config_loader):
        """Test redaction of email addresses."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "Contact user@example.com or admin@test.org for info",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        snippet = result["items"][0]["snippet"]
        assert "user@example.com" not in snippet
        assert "admin@test.org" not in snippet
        assert "[REDACTED]" in snippet
        assert "Contact" in snippet
    
    def test_multiple_redactions(self, config_loader):
        """Test multiple redactions in same snippet."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "Email test@example.com with Authorization: secret123",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        snippet = result["items"][0]["snippet"]
        # Should have redacted both email and auth
        assert snippet.count("[REDACTED]") >= 2
        assert "test@example.com" not in snippet
        assert "secret123" not in snippet


# ============================================================================
# Provenance Tests
# ============================================================================

class TestProvenance:
    """Test provenance information."""
    
    def test_provenance_includes_url(self, config_loader, sample_external_items):
        """Test provenance includes URL."""
        result = format_external_evidence(
            [sample_external_items[0]],
            config_loader=config_loader
        )
        
        provenance = result["items"][0]["provenance"]
        assert provenance["url"] == "https://en.wikipedia.org/wiki/Machine_Learning"
    
    def test_provenance_includes_fetched_at(self, config_loader, sample_external_items):
        """Test provenance includes fetch timestamp."""
        result = format_external_evidence(
            [sample_external_items[0]],
            config_loader=config_loader
        )
        
        provenance = result["items"][0]["provenance"]
        assert provenance["fetched_at"] == "2025-10-30T12:00:00Z"
    
    def test_missing_fetched_at(self, config_loader):
        """Test handling of missing fetched_at."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "Some content",
            # No fetched_at
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        provenance = result["items"][0]["provenance"]
        assert provenance["url"] is not None
        assert provenance["fetched_at"] is None


# ============================================================================
# Host Extraction Tests
# ============================================================================

class TestHostExtraction:
    """Test normalized host extraction."""
    
    def test_extract_host_from_url(self, config_loader):
        """Test host extraction from various URLs."""
        test_cases = [
            ("https://en.wikipedia.org/wiki/Test", "en.wikipedia.org"),
            ("https://arxiv.org/abs/1234.5678", "arxiv.org"),
            ("http://example.com/path/to/page", "example.com"),
            ("https://subdomain.example.com:8080/page", "subdomain.example.com:8080"),
        ]
        
        for url, expected_host in test_cases:
            item = {
                "source_id": "unknown",
                "url": url,
                "snippet": "Test",
                "fetched_at": "2025-10-30T12:00:00Z"
            }
            
            result = format_external_evidence([item], config_loader=config_loader)
            assert result["items"][0]["host"] == expected_host
    
    def test_invalid_url_fallback(self, config_loader):
        """Test handling of invalid URLs."""
        item = {
            "source_id": "unknown",
            "url": "not a valid url",
            "snippet": "Test",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        assert result["items"][0]["host"] == "unknown"
    
    def test_empty_url(self, config_loader):
        """Test handling of empty URL."""
        item = {
            "source_id": "unknown",
            "url": "",
            "snippet": "Test",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        assert result["items"][0]["host"] == "unknown"


# ============================================================================
# Chat Response Integration Tests
# ============================================================================

class TestChatResponseIntegration:
    """Test integration with chat responses."""
    
    def test_format_response_with_externals(self, sample_external_items):
        """Test formatting chat response with external sources."""
        base_response = {
            "answer": "This is the answer",
            "citations": []
        }
        
        result = format_chat_response_with_externals(
            base_response,
            external_items=sample_external_items
        )
        
        assert "external_sources" in result
        assert result["external_sources"]["heading"] == "External sources"
        assert len(result["external_sources"]["items"]) == 2
    
    def test_format_response_without_externals(self):
        """Test formatting chat response without external sources."""
        base_response = {
            "answer": "This is the answer",
            "citations": []
        }
        
        result = format_chat_response_with_externals(base_response)
        
        assert "external_sources" in result
        assert result["external_sources"] is None
    
    def test_format_response_with_empty_externals(self):
        """Test formatting with empty externals list."""
        base_response = {
            "answer": "This is the answer",
            "citations": []
        }
        
        result = format_chat_response_with_externals(
            base_response,
            external_items=[]
        )
        
        assert "external_sources" in result
        assert result["external_sources"] is None


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================

class TestAcceptanceCriteria:
    """Verify all acceptance criteria."""
    
    def test_externals_appear_under_separate_heading(self, config_loader, sample_external_items):
        """
        Acceptance: Externals appear under "External sources" heading.
        """
        result = format_external_evidence(
            sample_external_items,
            config_loader=config_loader
        )
        
        assert result["heading"] == "External sources"
        assert "items" in result
        assert len(result["items"]) > 0
    
    def test_include_label_per_item(self, config_loader, sample_external_items):
        """
        Acceptance: Each item includes [label].
        """
        result = format_external_evidence(
            sample_external_items,
            config_loader=config_loader
        )
        
        for item in result["items"]:
            assert "label" in item
            assert isinstance(item["label"], str)
            assert len(item["label"]) > 0
    
    def test_include_normalized_host(self, config_loader, sample_external_items):
        """
        Acceptance: Each item includes normalized host.
        """
        result = format_external_evidence(
            sample_external_items,
            config_loader=config_loader
        )
        
        for item in result["items"]:
            assert "host" in item
            assert isinstance(item["host"], str)
            # Should not include protocol
            assert not item["host"].startswith("http")
    
    def test_include_provenance_fields(self, config_loader, sample_external_items):
        """
        Acceptance: Each item includes provenance {url, fetched_at}.
        """
        result = format_external_evidence(
            sample_external_items,
            config_loader=config_loader
        )
        
        for item in result["items"]:
            assert "provenance" in item
            provenance = item["provenance"]
            assert "url" in provenance
            assert "fetched_at" in provenance
    
    def test_respect_max_snippet_chars(self, config_loader):
        """
        Acceptance: Snippets truncated to whitelist.max_snippet_chars.
        """
        long_text = "Word " * 1000  # Very long
        
        item = {
            "source_id": "wikipedia",  # max_snippet_chars: 200
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": long_text,
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        snippet = result["items"][0]["snippet"]
        # Should respect 200 char limit (plus "...")
        assert len(snippet) <= 204
    
    def test_apply_redaction_patterns(self, config_loader):
        """
        Acceptance: Snippets sanitized using redact_patterns.
        """
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "Contact admin@example.com with token Bearer abc123",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        snippet = result["items"][0]["snippet"]
        # Should have redacted email and bearer token
        assert "admin@example.com" not in snippet
        assert "abc123" not in snippet
        assert "[REDACTED]" in snippet
    
    def test_grouped_under_external_sources(self, config_loader, sample_external_items):
        """
        Acceptance: Items grouped under "External sources".
        """
        result = format_external_evidence(
            sample_external_items,
            config_loader=config_loader
        )
        
        # All items should be in the items list under the heading
        assert result["heading"] == "External sources"
        assert len(result["items"]) == len(sample_external_items)


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_missing_snippet_field(self, config_loader):
        """Test handling item without snippet."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            # No snippet
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        assert len(result["items"]) == 1
        assert result["items"][0]["snippet"] == ""
    
    def test_missing_url_field(self, config_loader):
        """Test handling item without URL."""
        item = {
            "source_id": "wikipedia",
            # No URL
            "snippet": "Some text",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        assert len(result["items"]) == 1
        assert result["items"][0]["provenance"]["url"] == ""
    
    def test_snippet_with_only_whitespace(self, config_loader):
        """Test handling snippet with only whitespace."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "   \n\t  ",
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        # Should strip to empty string
        assert result["items"][0]["snippet"] == ""
    
    def test_very_short_snippet_for_truncation(self, config_loader):
        """Test truncation with snippet shorter than one word."""
        item = {
            "source_id": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/Test",
            "snippet": "A" * 250,  # 250 'A's
            "fetched_at": "2025-10-30T12:00:00Z"
        }
        
        result = format_external_evidence([item], config_loader=config_loader)
        
        # Should still truncate even if no spaces
        snippet = result["items"][0]["snippet"]
        assert len(snippet) <= 204


# ============================================================================
# Summary Test
# ============================================================================

class TestComprehensiveSummary:
    """Comprehensive test of all requirements."""
    
    def test_complete_formatting_pipeline(self, config_loader):
        """Test complete formatting with all features."""
        items = [
            {
                "source_id": "wikipedia",
                "url": "https://en.wikipedia.org/wiki/Machine_Learning",
                "snippet": "Machine learning is a field of AI. " * 20 + " Contact support@ml.org",  # Long + email
                "fetched_at": "2025-10-30T12:00:00Z"
            },
            {
                "source_id": "arxiv",
                "url": "https://arxiv.org/abs/1234.5678",
                "snippet": "Novel architecture with Authorization: Bearer token123",
                "fetched_at": "2025-10-30T12:05:00Z"
            }
        ]
        
        result = format_external_evidence(items, config_loader=config_loader)
        
        # Check structure
        assert result["heading"] == "External sources"
        assert len(result["items"]) == 2
        
        # Check first item
        wiki = result["items"][0]
        assert wiki["label"] == "Wikipedia"
        assert wiki["host"] == "en.wikipedia.org"
        assert len(wiki["snippet"]) <= 204  # Truncated
        assert "support@ml.org" not in wiki["snippet"]  # Redacted
        assert wiki["provenance"]["url"] is not None
        assert wiki["provenance"]["fetched_at"] is not None
        
        # Check second item
        arxiv = result["items"][1]
        assert arxiv["label"] == "arXiv"
        assert arxiv["host"] == "arxiv.org"
        assert "token123" not in arxiv["snippet"]  # Redacted
        assert "[REDACTED]" in arxiv["snippet"]
