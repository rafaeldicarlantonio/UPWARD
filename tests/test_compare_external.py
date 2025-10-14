# tests/test_compare_external.py — Comprehensive tests for external compare adapter

import unittest
import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

# Add workspace to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the config loading before importing
with patch.dict(os.environ, {
    'OPENAI_API_KEY': 'test-key',
    'SUPABASE_URL': 'https://test.supabase.co',
    'PINECONE_API_KEY': 'test-pinecone-key',
    'PINECONE_INDEX': 'test-index',
    'PINECONE_EXPLICATE_INDEX': 'test-explicate',
    'PINECONE_IMPLICATE_INDEX': 'test-implicate',
}):
    from core.factare.compare_external import (
        ExternalCompareAdapter,
        ExternalAdapterConfig,
        ExternalSnippet,
        RateLimitInfo,
        create_external_adapter,
        compare_with_external_sources
    )
    from core.factare.compare_internal import RetrievalCandidate
    from adapters.web_external import MockWebExternalAdapter

class TestExternalAdapterConfig(unittest.TestCase):
    """Test ExternalAdapterConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ExternalAdapterConfig()
        
        self.assertEqual(config.max_external_snippets, 5)
        self.assertEqual(config.max_snippet_length, 200)
        self.assertEqual(config.rate_limit_per_domain, 3)
        self.assertEqual(config.rate_limit_window_minutes, 1)
        self.assertEqual(config.timeout_seconds, 2)
        self.assertTrue(config.enable_redaction)
        self.assertIsNotNone(config.redaction_patterns)
        self.assertGreater(len(config.redaction_patterns), 0)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ExternalAdapterConfig(
            max_external_snippets=10,
            max_snippet_length=300,
            rate_limit_per_domain=5,
            rate_limit_window_minutes=2,
            timeout_seconds=5,
            enable_redaction=False,
            redaction_patterns=['custom_pattern']
        )
        
        self.assertEqual(config.max_external_snippets, 10)
        self.assertEqual(config.max_snippet_length, 300)
        self.assertEqual(config.rate_limit_per_domain, 5)
        self.assertEqual(config.rate_limit_window_minutes, 2)
        self.assertEqual(config.timeout_seconds, 5)
        self.assertFalse(config.enable_redaction)
        self.assertEqual(config.redaction_patterns, ['custom_pattern'])

class TestExternalSnippet(unittest.TestCase):
    """Test ExternalSnippet dataclass."""
    
    def test_external_snippet_creation(self):
        """Test creating ExternalSnippet with all fields."""
        snippet = ExternalSnippet(
            url="https://example.com/article",
            snippet="This is a test snippet",
            source="External: example.com",
            score=0.8,
            fetched_at=datetime.now(),
            domain="example.com",
            redacted=True,
            metadata={"type": "article"}
        )
        
        self.assertEqual(snippet.url, "https://example.com/article")
        self.assertEqual(snippet.snippet, "This is a test snippet")
        self.assertEqual(snippet.source, "External: example.com")
        self.assertEqual(snippet.score, 0.8)
        self.assertIsInstance(snippet.fetched_at, datetime)
        self.assertEqual(snippet.domain, "example.com")
        self.assertTrue(snippet.redacted)
        self.assertEqual(snippet.metadata["type"], "article")

class TestRateLimitInfo(unittest.TestCase):
    """Test RateLimitInfo dataclass."""
    
    def test_rate_limit_info_creation(self):
        """Test creating RateLimitInfo with all fields."""
        rate_info = RateLimitInfo(
            domain="example.com",
            last_request=datetime.now(),
            request_count=2,
            window_start=datetime.now() - timedelta(minutes=1)
        )
        
        self.assertEqual(rate_info.domain, "example.com")
        self.assertIsInstance(rate_info.last_request, datetime)
        self.assertEqual(rate_info.request_count, 2)
        self.assertIsInstance(rate_info.window_start, datetime)

class TestExternalCompareAdapter(unittest.TestCase):
    """Test ExternalCompareAdapter functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ExternalAdapterConfig(
            max_external_snippets=3,
            max_snippet_length=100,
            rate_limit_per_domain=2,
            rate_limit_window_minutes=1,
            timeout_seconds=1,
            enable_redaction=True
        )
        # Use mock web adapter for testing
        mock_web_adapter = MockWebExternalAdapter()
        self.adapter = ExternalCompareAdapter(self.config, mock_web_adapter)
        self.now = datetime.now()
        
        # Create test internal candidates
        self.internal_candidates = [
            RetrievalCandidate(
                id="internal_001",
                content="Internal research shows positive results",
                source="Internal Database",
                score=0.9,
                timestamp=self.now - timedelta(hours=1)
            )
        ]
    
    def test_adapter_initialization(self):
        """Test adapter initialization."""
        self.assertEqual(self.adapter.config, self.config)
        self.assertIsNotNone(self.adapter.internal_comparator)
        self.assertIsNotNone(self.adapter.web_adapter)
        self.assertEqual(len(self.adapter.rate_limits), 0)
        self.assertEqual(len(self.adapter.whitelist_cache), 0)
    
    def test_group_urls_by_domain(self):
        """Test URL grouping by domain."""
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://test.org/article",
            "https://example.com/page3",
            "invalid-url"
        ]
        
        domain_groups = self.adapter._group_urls_by_domain(urls)
        
        self.assertIn("example.com", domain_groups)
        self.assertIn("test.org", domain_groups)
        self.assertEqual(len(domain_groups["example.com"]), 3)
        self.assertEqual(len(domain_groups["test.org"]), 1)
    
    def test_redact_content(self):
        """Test content redaction."""
        content = "Contact us at test@example.com or call 555-123-4567. Visit us on 2023-12-01."
        
        redacted = self.adapter._redact_content(content)
        
        self.assertIn("[REDACTED]", redacted)
        self.assertNotIn("test@example.com", redacted)
        self.assertNotIn("555-123-4567", redacted)
        self.assertNotIn("2023-12-01", redacted)
    
    def test_redact_content_disabled(self):
        """Test content redaction when disabled."""
        config = ExternalAdapterConfig(enable_redaction=False)
        mock_web_adapter = MockWebExternalAdapter()
        adapter = ExternalCompareAdapter(config, mock_web_adapter)
        
        content = "Contact us at test@example.com or call 555-123-4567."
        redacted = adapter._redact_content(content)
        
        self.assertEqual(redacted, content)
    
    def test_create_snippet(self):
        """Test snippet creation."""
        content = "This is a very long piece of content that should be truncated to fit within the maximum snippet length limit."
        
        snippet = self.adapter._create_snippet(content, "https://example.com")
        
        self.assertIsNotNone(snippet)
        self.assertLessEqual(len(snippet), self.config.max_snippet_length)
        self.assertIn("...", snippet)  # Should be truncated
    
    def test_create_snippet_too_short(self):
        """Test snippet creation with content that's too short."""
        content = "Short"
        
        snippet = self.adapter._create_snippet(content, "https://example.com")
        
        self.assertIsNone(snippet)
    
    def test_create_snippet_empty(self):
        """Test snippet creation with empty content."""
        snippet = self.adapter._create_snippet("", "https://example.com")
        
        self.assertIsNone(snippet)

class TestExternalCompareAdapterAsync(unittest.TestCase):
    """Test ExternalCompareAdapter async functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ExternalAdapterConfig(
            max_external_snippets=3,
            max_snippet_length=100,
            rate_limit_per_domain=2,
            rate_limit_window_minutes=1,
            timeout_seconds=1,
            enable_redaction=True
        )
        # Use mock web adapter for testing
        mock_web_adapter = MockWebExternalAdapter()
        self.adapter = ExternalCompareAdapter(self.config, mock_web_adapter)
        self.now = datetime.now()
        
        # Create test internal candidates
        self.internal_candidates = [
            RetrievalCandidate(
                id="internal_001",
                content="Internal research shows positive results",
                source="Internal Database",
                score=0.9,
                timestamp=self.now - timedelta(hours=1)
            )
        ]
    
    async def test_compare_with_external_disabled(self):
        """Test comparison when external sources are disabled."""
        query = "Should we adopt this approach?"
        external_urls = ["https://example.com/article"]
        feature_flags = {"factare.allow_external": False}
        
        result = await self.adapter.compare_with_external(
            query, self.internal_candidates, external_urls, feature_flags
        )
        
        # Should only use internal candidates
        self.assertEqual(len(result.evidence_items), 1)
        self.assertEqual(result.evidence_items[0].id, "internal_001")
    
    async def test_compare_with_external_no_whitelisted_urls(self):
        """Test comparison when no URLs are whitelisted."""
        query = "Should we adopt this approach?"
        external_urls = ["https://malicious-site.com/article"]
        feature_flags = {"factare.allow_external": True}
        
        # Mock whitelist to return False for all URLs
        with patch('core.factare.compare_external.is_source_whitelisted', return_value=False):
            result = await self.adapter.compare_with_external(
                query, self.internal_candidates, external_urls, feature_flags
            )
        
        # Should only use internal candidates
        self.assertEqual(len(result.evidence_items), 1)
        self.assertEqual(result.evidence_items[0].id, "internal_001")
    
    async def test_compare_with_external_success(self):
        """Test successful comparison with external sources."""
        query = "Should we adopt this approach?"
        external_urls = ["https://example.com/article"]
        feature_flags = {"factare.allow_external": True}
        
        # Mock whitelist to return True
        with patch('core.factare.compare_external.is_source_whitelisted', return_value=True):
            # Mock web adapter
            mock_web_adapter = MockWebExternalAdapter()
            mock_web_adapter.set_mock_response(
                "https://example.com/article",
                "External research shows this approach is highly effective and beneficial for organizations."
            )
            self.adapter.web_adapter = mock_web_adapter
            
            result = await self.adapter.compare_with_external(
                query, self.internal_candidates, external_urls, feature_flags
            )
        
        # Should have both internal and external evidence
        self.assertGreaterEqual(len(result.evidence_items), 1)
        
        # Check that external evidence was added
        external_items = [item for item in result.evidence_items if item.id.startswith("external_")]
        self.assertGreater(len(external_items), 0)
    
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        domain = "example.com"
        
        # First request should be allowed
        allowed = await self.adapter._check_rate_limit(domain)
        self.assertTrue(allowed)
        
        # Second request should be allowed
        allowed = await self.adapter._check_rate_limit(domain)
        self.assertTrue(allowed)
        
        # Third request should be blocked (rate limit is 2)
        allowed = await self.adapter._check_rate_limit(domain)
        self.assertFalse(allowed)
    
    async def test_rate_limit_reset(self):
        """Test rate limit reset after window expires."""
        domain = "example.com"
        
        # Exhaust rate limit
        await self.adapter._check_rate_limit(domain)
        await self.adapter._check_rate_limit(domain)
        
        # Should be blocked
        allowed = await self.adapter._check_rate_limit(domain)
        self.assertFalse(allowed)
        
        # Reset rate limits
        self.adapter.reset_rate_limits()
        
        # Should be allowed again
        allowed = await self.adapter._check_rate_limit(domain)
        self.assertTrue(allowed)
    
    async def test_fetch_domain_snippets_timeout(self):
        """Test fetching snippets with timeout."""
        domain = "example.com"
        urls = ["https://example.com/slow"]
        
        # Mock web adapter with delay
        mock_web_adapter = MockWebExternalAdapter()
        mock_web_adapter.set_mock_delay("https://example.com/slow", 2.0)  # 2 second delay
        self.adapter.web_adapter = mock_web_adapter
        
        snippets = await self.adapter._fetch_domain_snippets(domain, urls)
        
        # Should timeout and return empty list
        self.assertEqual(len(snippets), 0)
    
    async def test_fetch_domain_snippets_error(self):
        """Test fetching snippets with error."""
        domain = "example.com"
        urls = ["https://example.com/error"]
        
        # Mock web adapter with error
        mock_web_adapter = MockWebExternalAdapter()
        mock_web_adapter.set_mock_error("https://example.com/error", Exception("Network error"))
        self.adapter.web_adapter = mock_web_adapter
        
        snippets = await self.adapter._fetch_domain_snippets(domain, urls)
        
        # Should handle error and return empty list
        self.assertEqual(len(snippets), 0)
    
    async def test_fetch_domain_snippets_success(self):
        """Test successful fetching of snippets."""
        domain = "example.com"
        urls = ["https://example.com/article"]
        
        # Mock web adapter with success
        mock_web_adapter = MockWebExternalAdapter()
        mock_web_adapter.set_mock_response(
            "https://example.com/article",
            "This is external content that should be processed and redacted properly."
        )
        self.adapter.web_adapter = mock_web_adapter
        
        snippets = await self.adapter._fetch_domain_snippets(domain, urls)
        
        # Should return one snippet
        self.assertEqual(len(snippets), 1)
        snippet = snippets[0]
        self.assertTrue(snippet.id.startswith("external_"))
        self.assertEqual(snippet.source, f"External: {domain}")
        self.assertEqual(snippet.url, "https://example.com/article")
        self.assertIsNotNone(snippet.timestamp)
        self.assertIsNotNone(snippet.metadata)
    
    async def test_create_compare_summary_with_external(self):
        """Test creating CompareSummary with external sources."""
        query = "Should we adopt this approach?"
        external_urls = ["https://example.com/article"]
        feature_flags = {"factare.allow_external": True}
        
        # Mock whitelist and web adapter
        with patch('core.factare.compare_external.is_source_whitelisted', return_value=True):
            mock_web_adapter = MockWebExternalAdapter()
            mock_web_adapter.set_mock_response(
                "https://example.com/article",
                "External research shows this approach is highly effective."
            )
            self.adapter.web_adapter = mock_web_adapter
            
            summary = await self.adapter.create_compare_summary_with_external(
                query, self.internal_candidates, external_urls, feature_flags
            )
        
        self.assertEqual(summary.query, query)
        self.assertIsNotNone(summary.stance_a)
        self.assertIsNotNone(summary.stance_b)
        self.assertGreaterEqual(len(summary.evidence), 1)
        self.assertIn('external_sources_used', summary.metadata)
        self.assertIn('external_urls_provided', summary.metadata)
        self.assertIn('external_urls_whitelisted', summary.metadata)
    
    def test_get_rate_limit_status(self):
        """Test getting rate limit status."""
        # Add some rate limit data (within limits)
        self.adapter.rate_limits["example.com"] = RateLimitInfo(
            domain="example.com",
            request_count=1,  # Within the limit of 2
            last_request=datetime.now(),
            window_start=datetime.now() - timedelta(minutes=1)
        )
        
        status = self.adapter.get_rate_limit_status()
        
        self.assertIn("example.com", status)
        self.assertEqual(status["example.com"]["request_count"], 1)
        self.assertTrue(status["example.com"]["within_limits"])
    
    def test_reset_rate_limits(self):
        """Test resetting rate limits."""
        # Add some data
        self.adapter.rate_limits["example.com"] = RateLimitInfo(domain="example.com")
        self.adapter.whitelist_cache.add("https://example.com")
        
        self.adapter.reset_rate_limits()
        
        self.assertEqual(len(self.adapter.rate_limits), 0)
        self.assertEqual(len(self.adapter.whitelist_cache), 0)

class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    def test_create_external_adapter(self):
        """Test create_external_adapter function."""
        mock_web_adapter = MockWebExternalAdapter()
        adapter = create_external_adapter(web_adapter=mock_web_adapter)
        
        self.assertIsInstance(adapter, ExternalCompareAdapter)
        self.assertIsNotNone(adapter.config)
    
    def test_create_external_adapter_with_config(self):
        """Test create_external_adapter with custom config."""
        config = ExternalAdapterConfig(max_external_snippets=10)
        mock_web_adapter = MockWebExternalAdapter()
        adapter = create_external_adapter(config, mock_web_adapter)
        
        self.assertIsInstance(adapter, ExternalCompareAdapter)
        self.assertEqual(adapter.config.max_external_snippets, 10)
    
    async def test_compare_with_external_sources(self):
        """Test compare_with_external_sources convenience function."""
        query = "Should we adopt this approach?"
        internal_candidates = [
            RetrievalCandidate(
                id="internal_001",
                content="Internal research shows positive results",
                source="Internal Database",
                score=0.9,
                timestamp=datetime.now()
            )
        ]
        external_urls = ["https://example.com/article"]
        feature_flags = {"factare.allow_external": True}
        
        # Mock whitelist and web adapter
        with patch('core.factare.compare_external.is_source_whitelisted', return_value=True):
            with patch('core.factare.compare_external.WebExternalAdapter') as mock_web_class:
                mock_web_adapter = MockWebExternalAdapter()
                mock_web_adapter.set_mock_response(
                    "https://example.com/article",
                    "External research shows this approach is highly effective."
                )
                mock_web_class.return_value = mock_web_adapter
                
                summary = await compare_with_external_sources(
                    query, internal_candidates, external_urls, feature_flags
                )
        
        self.assertEqual(summary.query, query)
        self.assertIsNotNone(summary.stance_a)
        self.assertIsNotNone(summary.stance_b)
        self.assertGreaterEqual(len(summary.evidence), 1)

class TestMockWebExternalAdapter(unittest.TestCase):
    """Test MockWebExternalAdapter for testing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_adapter = MockWebExternalAdapter()
    
    def test_mock_adapter_initialization(self):
        """Test mock adapter initialization."""
        self.assertEqual(self.mock_adapter.fetch_count, 0)
        self.assertEqual(len(self.mock_adapter.mock_responses), 0)
        self.assertEqual(len(self.mock_adapter.mock_delays), 0)
        self.assertEqual(len(self.mock_adapter.mock_errors), 0)
    
    async def test_mock_fetch_content_success(self):
        """Test mock fetch content with success."""
        url = "https://example.com/article"
        content = "This is test content"
        
        self.mock_adapter.set_mock_response(url, content)
        
        result = await self.mock_adapter.fetch_content(url)
        
        self.assertEqual(result, content)
        self.assertEqual(self.mock_adapter.fetch_count, 1)
    
    async def test_mock_fetch_content_delay(self):
        """Test mock fetch content with delay."""
        url = "https://example.com/slow"
        content = "This is slow content"
        delay = 0.1  # 100ms delay
        
        self.mock_adapter.set_mock_response(url, content)
        self.mock_adapter.set_mock_delay(url, delay)
        
        start_time = time.time()
        result = await self.mock_adapter.fetch_content(url)
        end_time = time.time()
        
        self.assertEqual(result, content)
        self.assertGreaterEqual(end_time - start_time, delay)
    
    async def test_mock_fetch_content_error(self):
        """Test mock fetch content with error."""
        url = "https://example.com/error"
        error = Exception("Network error")
        
        self.mock_adapter.set_mock_error(url, error)
        
        with self.assertRaises(Exception):
            await self.mock_adapter.fetch_content(url)
    
    async def test_mock_fetch_content_no_response(self):
        """Test mock fetch content with no response."""
        url = "https://example.com/empty"
        
        result = await self.mock_adapter.fetch_content(url)
        
        self.assertIsNone(result)
    
    def test_mock_reset(self):
        """Test mock reset functionality."""
        # Set some mock data
        self.mock_adapter.set_mock_response("https://example.com", "content")
        self.mock_adapter.set_mock_delay("https://example.com", 0.1)
        self.mock_adapter.set_mock_error("https://example.com", Exception("error"))
        self.mock_adapter.fetch_count = 5
        
        # Reset
        self.mock_adapter.reset()
        
        # Check reset
        self.assertEqual(len(self.mock_adapter.mock_responses), 0)
        self.assertEqual(len(self.mock_adapter.mock_delays), 0)
        self.assertEqual(len(self.mock_adapter.mock_errors), 0)
        self.assertEqual(self.mock_adapter.fetch_count, 0)

class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios."""
    
    async def test_full_workflow_success(self):
        """Test full workflow with successful external fetching."""
        config = ExternalAdapterConfig(
            max_external_snippets=2,
            max_snippet_length=150,
            rate_limit_per_domain=3,
            timeout_seconds=1
        )
        adapter = ExternalCompareAdapter(config)
        
        query = "Should we implement AI in our system?"
        internal_candidates = [
            RetrievalCandidate(
                id="internal_001",
                content="Internal analysis shows AI implementation is beneficial",
                source="Internal Research",
                score=0.9,
                timestamp=datetime.now()
            )
        ]
        external_urls = [
            "https://example.com/ai-benefits",
            "https://test.org/ai-risks"
        ]
        feature_flags = {"factare.allow_external": True}
        
        # Mock whitelist and web adapter
        with patch('core.factare.compare_external.is_source_whitelisted', return_value=True):
            mock_web_adapter = MockWebExternalAdapter()
            mock_web_adapter.set_mock_response(
                "https://example.com/ai-benefits",
                "AI implementation provides significant benefits including improved efficiency and cost savings."
            )
            mock_web_adapter.set_mock_response(
                "https://test.org/ai-risks",
                "AI systems pose risks including job displacement and ethical concerns that must be addressed."
            )
            adapter.web_adapter = mock_web_adapter
            
            summary = await adapter.create_compare_summary_with_external(
                query, internal_candidates, external_urls, feature_flags
            )
        
        # Verify results
        self.assertEqual(summary.query, query)
        self.assertIsNotNone(summary.stance_a)
        self.assertIsNotNone(summary.stance_b)
        self.assertGreaterEqual(len(summary.evidence), 1)
        
        # Check metadata
        self.assertIn('external_sources_used', summary.metadata)
        self.assertEqual(summary.metadata['external_urls_provided'], 2)
        self.assertEqual(summary.metadata['external_urls_whitelisted'], 2)
    
    async def test_full_workflow_timeout_fallback(self):
        """Test full workflow with timeout fallback to internal only."""
        config = ExternalAdapterConfig(
            max_external_snippets=2,
            timeout_seconds=0.1  # Very short timeout
        )
        adapter = ExternalCompareAdapter(config)
        
        query = "Should we implement AI in our system?"
        internal_candidates = [
            RetrievalCandidate(
                id="internal_001",
                content="Internal analysis shows AI implementation is beneficial",
                source="Internal Research",
                score=0.9,
                timestamp=datetime.now()
            )
        ]
        external_urls = ["https://example.com/slow"]
        feature_flags = {"factare.allow_external": True}
        
        # Mock whitelist and web adapter with delay
        with patch('core.factare.compare_external.is_source_whitelisted', return_value=True):
            mock_web_adapter = MockWebExternalAdapter()
            mock_web_adapter.set_mock_delay("https://example.com/slow", 1.0)  # 1 second delay
            adapter.web_adapter = mock_web_adapter
            
            summary = await adapter.create_compare_summary_with_external(
                query, internal_candidates, external_urls, feature_flags
            )
        
        # Should fall back to internal only
        self.assertEqual(summary.query, query)
        self.assertIsNotNone(summary.stance_a)
        self.assertIsNotNone(summary.stance_b)
        
        # Should only have internal evidence
        internal_evidence = [item for item in summary.evidence if not item.is_external]
        self.assertEqual(len(internal_evidence), 1)
    
    async def test_full_workflow_no_whitelisted_urls(self):
        """Test full workflow with no whitelisted URLs."""
        adapter = ExternalCompareAdapter()
        
        query = "Should we implement AI in our system?"
        internal_candidates = [
            RetrievalCandidate(
                id="internal_001",
                content="Internal analysis shows AI implementation is beneficial",
                source="Internal Research",
                score=0.9,
                timestamp=datetime.now()
            )
        ]
        external_urls = ["https://malicious-site.com/article"]
        feature_flags = {"factare.allow_external": True}
        
        # Mock whitelist to return False
        with patch('core.factare.compare_external.is_source_whitelisted', return_value=False):
            summary = await adapter.create_compare_summary_with_external(
                query, internal_candidates, external_urls, feature_flags
            )
        
        # Should fall back to internal only
        self.assertEqual(summary.query, query)
        self.assertIsNotNone(summary.stance_a)
        self.assertIsNotNone(summary.stance_b)
        
        # Should only have internal evidence
        internal_evidence = [item for item in summary.evidence if not item.is_external]
        self.assertEqual(len(internal_evidence), 1)
        
        # Check metadata
        self.assertEqual(summary.metadata['external_sources_used'], 0)
        self.assertEqual(summary.metadata['external_urls_whitelisted'], 0)


def main():
    """Run all tests."""
    print("Running external compare adapter tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestExternalAdapterConfig,
        TestExternalSnippet,
        TestRateLimitInfo,
        TestExternalCompareAdapter,
        TestExternalCompareAdapterAsync,
        TestConvenienceFunctions,
        TestMockWebExternalAdapter,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All external compare adapter tests passed!")
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