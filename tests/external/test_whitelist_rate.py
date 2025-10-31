"""
Tests for URL whitelist matching and token-bucket rate limiting.

Verifies that non-whitelisted URLs are skipped, rate limits are respected,
and higher-priority sources are selected first.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from core.whitelist import URLMatcher, TokenBucket, RateLimiter, SourceMatch

try:
    from adapters.web_external import WebExternalAdapter
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    WebExternalAdapter = None

# Skip integration tests if aiohttp not available
requires_aiohttp = pytest.mark.skipif(
    not AIOHTTP_AVAILABLE,
    reason="aiohttp not installed"
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_sources():
    """Sample source configurations for testing."""
    return [
        {
            'source_id': 'wikipedia',
            'label': 'Wikipedia',
            'priority': 10,
            'url_pattern': 'https://*.wikipedia.org/*',
            'max_snippet_chars': 500,
            'enabled': True
        },
        {
            'source_id': 'arxiv',
            'label': 'arXiv',
            'priority': 9,
            'url_pattern': 'https://arxiv.org/*',
            'max_snippet_chars': 600,
            'enabled': True
        },
        {
            'source_id': 'github',
            'label': 'GitHub',
            'priority': 7,
            'url_pattern': 'https://github.com/*',
            'max_snippet_chars': 400,
            'enabled': True
        },
        {
            'source_id': 'disabled_source',
            'label': 'Disabled',
            'priority': 8,
            'url_pattern': 'https://disabled.example.com/*',
            'max_snippet_chars': 300,
            'enabled': False
        }
    ]


@pytest.fixture
def url_matcher(sample_sources):
    """Create URLMatcher with sample sources."""
    return URLMatcher(sample_sources)


@pytest.fixture
def rate_limiter():
    """Create RateLimiter with test settings."""
    return RateLimiter(
        per_domain_limit=3,
        per_domain_window_seconds=60.0,
        global_limit=10
    )


@pytest.fixture
def mock_adapter():
    """Create mock web adapter for testing."""
    from adapters.web_external import MockWebExternalAdapter
    return MockWebExternalAdapter({
        'https://en.wikipedia.org/wiki/Test': 'Wikipedia content',
        'https://arxiv.org/abs/1234.5678': 'arXiv content',
        'https://github.com/test/repo': 'GitHub content',
        'https://not-whitelisted.com/page': 'Should not fetch'
    })


# ============================================================================
# Test: URLMatcher - Pattern Matching
# ============================================================================

class TestURLMatcherPatterns:
    """Test URL pattern matching functionality."""
    
    def test_exact_match(self, url_matcher):
        """Test exact URL matching."""
        # Wikipedia should match
        match = url_matcher.match('https://en.wikipedia.org/wiki/Test')
        assert match is not None
        assert match.source_id == 'wikipedia'
        assert match.priority == 10
    
    def test_glob_wildcard_matching(self, url_matcher):
        """Test glob-style wildcard matching."""
        # Wikipedia with subdomain wildcard
        match = url_matcher.match('https://en.wikipedia.org/wiki/Machine_Learning')
        assert match is not None
        assert match.source_id == 'wikipedia'
        
        match = url_matcher.match('https://fr.wikipedia.org/wiki/Test')
        assert match is not None
        assert match.source_id == 'wikipedia'
    
    def test_path_wildcard_matching(self, url_matcher):
        """Test path wildcard matching."""
        # arXiv pattern
        match = url_matcher.match('https://arxiv.org/abs/1234.5678')
        assert match is not None
        assert match.source_id == 'arxiv'
        
        match = url_matcher.match('https://arxiv.org/pdf/1234.5678.pdf')
        assert match is not None
        assert match.source_id == 'arxiv'
    
    def test_no_match(self, url_matcher):
        """Test URLs that don't match any pattern."""
        match = url_matcher.match('https://example.com/page')
        assert match is None
        
        match = url_matcher.match('https://not-in-whitelist.org/test')
        assert match is None
    
    def test_disabled_source_not_matched(self, url_matcher):
        """Test that disabled sources are not matched."""
        match = url_matcher.match('https://disabled.example.com/page')
        assert match is None
    
    def test_is_whitelisted_convenience(self, url_matcher):
        """Test is_whitelisted convenience method."""
        assert url_matcher.is_whitelisted('https://en.wikipedia.org/wiki/Test')
        assert url_matcher.is_whitelisted('https://arxiv.org/abs/123')
        assert not url_matcher.is_whitelisted('https://example.com/page')
        assert not url_matcher.is_whitelisted('https://disabled.example.com/page')
    
    def test_priority_ordering(self, url_matcher):
        """Test that patterns are checked in priority order."""
        enabled_sources = url_matcher.get_enabled_sources()
        
        # Should be sorted by priority (descending)
        priorities = [s.priority for s in enabled_sources]
        assert priorities == sorted(priorities, reverse=True)
        
        # Wikipedia should be first (highest priority)
        assert enabled_sources[0].source_id == 'wikipedia'
        assert enabled_sources[0].priority == 10
    
    def test_case_insensitive_matching(self, url_matcher):
        """Test that matching is case-insensitive."""
        match1 = url_matcher.match('https://EN.WIKIPEDIA.ORG/wiki/Test')
        match2 = url_matcher.match('https://en.wikipedia.org/wiki/Test')
        
        assert match1 is not None
        assert match2 is not None
        assert match1.source_id == match2.source_id
    
    def test_empty_or_invalid_url(self, url_matcher):
        """Test handling of empty or invalid URLs."""
        assert url_matcher.match('') is None
        assert url_matcher.match(None) is None
        assert not url_matcher.is_whitelisted('')


# ============================================================================
# Test: TokenBucket - Basic Operations
# ============================================================================

class TestTokenBucket:
    """Test token bucket rate limiting."""
    
    def test_initial_capacity(self):
        """Test that bucket starts at full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.get_available_tokens() == 10.0
    
    def test_acquire_tokens(self):
        """Test acquiring tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        # Should successfully acquire
        assert bucket.acquire(1) is True
        assert abs(bucket.get_available_tokens() - 9.0) < 0.01
        
        assert bucket.acquire(3) is True
        assert abs(bucket.get_available_tokens() - 6.0) < 0.01
    
    def test_insufficient_tokens(self):
        """Test that acquisition fails when insufficient tokens."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        
        assert bucket.acquire(3) is True  # 2 left
        assert bucket.acquire(2) is True  # 0 left
        assert bucket.acquire(1) is False  # Insufficient
    
    def test_token_refill(self):
        """Test that tokens refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens per second
        
        # Consume all tokens
        bucket.acquire(10)
        assert abs(bucket.get_available_tokens()) < 0.01  # Approximately 0
        
        # Wait for refill
        time.sleep(1.0)
        
        # Should have ~2 tokens (2 tokens per second * 1 second)
        available = bucket.get_available_tokens()
        assert 1.8 <= available <= 2.2  # Allow for timing variance
    
    def test_refill_does_not_exceed_capacity(self):
        """Test that refill doesn't exceed bucket capacity."""
        bucket = TokenBucket(capacity=5, refill_rate=10.0)  # Fast refill
        
        # Wait for potential overfill
        time.sleep(1.0)
        
        # Should not exceed capacity
        available = bucket.get_available_tokens()
        assert available <= 5.0
    
    def test_reset(self):
        """Test bucket reset."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        bucket.acquire(8)
        assert abs(bucket.get_available_tokens() - 2.0) < 0.01
        
        bucket.reset()
        assert abs(bucket.get_available_tokens() - 10.0) < 0.01
    
    def test_thread_safety(self):
        """Test that token bucket is thread-safe."""
        import threading
        
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        results = []
        
        def acquire_tokens():
            for _ in range(10):
                result = bucket.acquire(1)
                results.append(result)
        
        threads = [threading.Thread(target=acquire_tokens) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All 100 tokens should be acquired exactly once
        successful = sum(1 for r in results if r)
        assert successful == 100


# ============================================================================
# Test: RateLimiter - Per-Domain and Global Limits
# ============================================================================

class TestRateLimiter:
    """Test multi-domain rate limiter."""
    
    def test_per_domain_limit(self):
        """Test per-domain rate limiting."""
        limiter = RateLimiter(per_domain_limit=3, per_domain_window_seconds=60.0)
        
        url = 'https://example.com/page'
        
        # Should allow up to 3 requests
        assert limiter.acquire(url) == (True, 'ok')
        assert limiter.acquire(url) == (True, 'ok')
        assert limiter.acquire(url) == (True, 'ok')
        
        # 4th request should be rate limited
        success, reason = limiter.acquire(url)
        assert success is False
        assert 'domain_limit_exceeded' in reason
    
    def test_different_domains_independent(self):
        """Test that different domains have independent limits."""
        limiter = RateLimiter(per_domain_limit=2, per_domain_window_seconds=60.0)
        
        url1 = 'https://example.com/page'
        url2 = 'https://other.com/page'
        
        # Each domain can make its own requests
        assert limiter.acquire(url1) == (True, 'ok')
        assert limiter.acquire(url1) == (True, 'ok')
        assert limiter.acquire(url2) == (True, 'ok')
        assert limiter.acquire(url2) == (True, 'ok')
        
        # Both domains now exhausted
        assert limiter.acquire(url1)[0] is False
        assert limiter.acquire(url2)[0] is False
    
    def test_global_limit(self):
        """Test global rate limiting across all domains."""
        limiter = RateLimiter(
            per_domain_limit=10,
            per_domain_window_seconds=60.0,
            global_limit=5
        )
        
        urls = [
            'https://example1.com/page',
            'https://example2.com/page',
            'https://example3.com/page',
            'https://example4.com/page',
            'https://example5.com/page',
            'https://example6.com/page'
        ]
        
        # First 5 should succeed
        for url in urls[:5]:
            assert limiter.acquire(url) == (True, 'ok')
        
        # 6th should fail due to global limit
        success, reason = limiter.acquire(urls[5])
        assert success is False
        assert reason == 'global_limit_exceeded'
    
    def test_global_limit_checked_first(self):
        """Test that global limit is checked before per-domain limit."""
        limiter = RateLimiter(
            per_domain_limit=10,
            per_domain_window_seconds=60.0,
            global_limit=2
        )
        
        url = 'https://example.com/page'
        
        # Exhaust global limit
        assert limiter.acquire(url) == (True, 'ok')
        assert limiter.acquire(url) == (True, 'ok')
        
        # Should fail with global limit
        success, reason = limiter.acquire(url)
        assert success is False
        assert reason == 'global_limit_exceeded'
    
    def test_domain_token_refill(self):
        """Test that per-domain tokens refill over time."""
        limiter = RateLimiter(
            per_domain_limit=2,
            per_domain_window_seconds=1.0  # 1 second window for fast test
        )
        
        url = 'https://example.com/page'
        
        # Exhaust domain limit
        assert limiter.acquire(url) == (True, 'ok')
        assert limiter.acquire(url) == (True, 'ok')
        assert limiter.acquire(url)[0] is False
        
        # Wait for refill (at least 1 token should refill in 1 second)
        time.sleep(0.6)
        
        # Should be able to acquire again
        assert limiter.acquire(url) == (True, 'ok')
    
    def test_can_acquire_check(self):
        """Test can_acquire check without actually acquiring."""
        limiter = RateLimiter(per_domain_limit=2, per_domain_window_seconds=60.0)
        
        url = 'https://example.com/page'
        
        # Should be able to acquire
        assert limiter.can_acquire(url) is True
        
        # Check doesn't consume tokens
        assert limiter.can_acquire(url) is True
        
        # Actually acquire
        limiter.acquire(url)
        limiter.acquire(url)
        
        # Now cannot acquire
        assert limiter.can_acquire(url) is False
    
    def test_reset_domain(self, rate_limiter):
        """Test resetting rate limit for specific domain."""
        url = 'https://example.com/page'
        
        # Exhaust limit
        rate_limiter.acquire(url)
        rate_limiter.acquire(url)
        rate_limiter.acquire(url)
        assert rate_limiter.acquire(url)[0] is False
        
        # Reset domain
        rate_limiter.reset_domain(url)
        
        # Should be able to acquire again
        assert rate_limiter.acquire(url) == (True, 'ok')
    
    def test_reset_global(self):
        """Test resetting global rate limit."""
        limiter = RateLimiter(
            per_domain_limit=10,
            per_domain_window_seconds=60.0,
            global_limit=2
        )
        
        url1 = 'https://example1.com/page'
        url2 = 'https://example2.com/page'
        
        # Exhaust global limit
        limiter.acquire(url1)
        limiter.acquire(url2)
        assert limiter.acquire(url1)[0] is False
        
        # Reset global
        limiter.reset_global()
        
        # Should be able to acquire again
        assert limiter.acquire(url1) == (True, 'ok')
    
    def test_reset_all(self, rate_limiter):
        """Test resetting all rate limits."""
        url1 = 'https://example1.com/page'
        url2 = 'https://example2.com/page'
        
        # Exhaust both domain and global limits
        rate_limiter.acquire(url1)
        rate_limiter.acquire(url1)
        rate_limiter.acquire(url1)
        rate_limiter.acquire(url2)
        
        assert rate_limiter.acquire(url1)[0] is False
        assert rate_limiter.get_global_tokens() < 10
        
        # Reset all
        rate_limiter.reset_all()
        
        # Both should work again
        assert rate_limiter.acquire(url1) == (True, 'ok')
        assert rate_limiter.get_global_tokens() == 9.0


# ============================================================================
# Test: WebExternalAdapter Integration
# ============================================================================

@requires_aiohttp
class TestWebAdapterIntegration:
    """Test web adapter with whitelist and rate limiting."""
    
    @pytest.mark.anyio
    async def test_non_whitelisted_url_skipped(self, url_matcher, mock_adapter):
        """
        Acceptance: Non-whitelisted URLs are skipped.
        """
        # Create adapter with whitelist (using MockWebExternalAdapter for testing)
        # We need to create a real adapter for this test
        adapter = WebExternalAdapter(url_matcher=url_matcher, rate_limiter=None)
        
        # Mock the actual fetch to avoid network calls
        original_fetch = adapter.fetch_content
        
        async def mock_fetch_after_checks(url):
            # This simulates that we passed whitelist check
            # In reality, non-whitelisted URLs never get here
            if url == 'https://not-whitelisted.com/page':
                return "Should not see this"
            return "Allowed content"
        
        # Non-whitelisted URL should return None
        result = await adapter.fetch_content('https://not-whitelisted.com/page')
        assert result is None
        assert adapter.stats['not_whitelisted'] == 1
        assert adapter.stats['successful'] == 0
    
    @pytest.mark.anyio
    async def test_whitelisted_url_passes(self, url_matcher):
        """Test that whitelisted URLs pass the check."""
        adapter = WebExternalAdapter(url_matcher=url_matcher, rate_limiter=None)
        
        # Mock the session and response
        with patch.object(adapter, '_ensure_session'):
            with patch.object(adapter, 'session') as mock_session:
                # Create mock response
                mock_response = Mock()
                mock_response.status = 200
                mock_response.headers = {'content-type': 'text/html'}
                mock_response.text = asyncio.coroutine(lambda: '<html>Test content</html>')()
                
                mock_session.get.return_value.__aenter__.return_value = mock_response
                
                result = await adapter.fetch_content('https://en.wikipedia.org/wiki/Test')
                
                # Should have attempted fetch (not blocked by whitelist)
                assert adapter.stats['whitelisted'] == 1
                assert adapter.stats['not_whitelisted'] == 0
    
    @pytest.mark.anyio
    async def test_rate_limit_respected(self, rate_limiter):
        """
        Acceptance: Rate limit is respected.
        """
        adapter = WebExternalAdapter(url_matcher=None, rate_limiter=rate_limiter)
        
        url = 'https://example.com/page'
        
        # Mock the session
        with patch.object(adapter, '_ensure_session'):
            with patch.object(adapter, 'session') as mock_session:
                mock_response = Mock()
                mock_response.status = 200
                mock_response.headers = {'content-type': 'text/html'}
                mock_response.text = asyncio.coroutine(lambda: '<html>Test</html>')()
                mock_session.get.return_value.__aenter__.return_value = mock_response
                
                # First 3 requests should succeed (per-domain limit = 3)
                for i in range(3):
                    result = await adapter.fetch_content(url)
                    # Would succeed if not for other failures
                
                # 4th request should be rate limited
                result = await adapter.fetch_content(url)
                assert result is None
                assert adapter.stats['rate_limited'] == 1
    
    @pytest.mark.anyio
    async def test_priority_ordering_in_fetch_multiple(self, url_matcher):
        """
        Acceptance: Selection prioritizes higher-priority sources first.
        """
        adapter = WebExternalAdapter(url_matcher=url_matcher, rate_limiter=None)
        
        urls = [
            'https://github.com/test/repo',  # priority 7
            'https://en.wikipedia.org/wiki/Test',  # priority 10
            'https://arxiv.org/abs/1234',  # priority 9
        ]
        
        # Mock fetch to track order
        fetch_order = []
        original_fetch = adapter.fetch_content
        
        async def tracking_fetch(url):
            fetch_order.append(url)
            return None
        
        adapter.fetch_content = tracking_fetch
        
        await adapter.fetch_multiple(urls, prioritize=True)
        
        # Should be fetched in priority order: Wikipedia (10), arXiv (9), GitHub (7)
        assert fetch_order[0] == 'https://en.wikipedia.org/wiki/Test'
        assert fetch_order[1] == 'https://arxiv.org/abs/1234'
        assert fetch_order[2] == 'https://github.com/test/repo'
    
    @pytest.mark.anyio
    async def test_fetch_multiple_without_prioritization(self, url_matcher):
        """Test fetch_multiple without priority ordering."""
        adapter = WebExternalAdapter(url_matcher=url_matcher, rate_limiter=None)
        
        urls = [
            'https://github.com/test/repo',
            'https://en.wikipedia.org/wiki/Test',
            'https://arxiv.org/abs/1234',
        ]
        
        fetch_order = []
        
        async def tracking_fetch(url):
            fetch_order.append(url)
            return None
        
        adapter.fetch_content = tracking_fetch
        
        await adapter.fetch_multiple(urls, prioritize=False)
        
        # Should maintain original order
        assert fetch_order == urls
    
    def test_adapter_statistics(self, url_matcher, rate_limiter):
        """Test that adapter tracks statistics correctly."""
        adapter = WebExternalAdapter(
            url_matcher=url_matcher,
            rate_limiter=rate_limiter
        )
        
        stats = adapter.get_stats()
        assert stats['total_requests'] == 0
        assert stats['whitelisted'] == 0
        assert stats['not_whitelisted'] == 0
        assert stats['rate_limited'] == 0
        
        adapter.reset_stats()
        stats = adapter.get_stats()
        assert all(v == 0 for v in stats.values())


# ============================================================================
# Test: Acceptance Criteria
# ============================================================================

class TestAcceptanceCriteria:
    """Direct verification of all acceptance criteria."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_acceptance_non_whitelisted_skipped(self, url_matcher):
        """
        Acceptance: Tests prove non-whitelisted URLs are skipped.
        """
        adapter = WebExternalAdapter(url_matcher=url_matcher, rate_limiter=None)
        
        # Non-whitelisted URL
        result = await adapter.fetch_content('https://random-site.com/page')
        assert result is None
        assert adapter.stats['not_whitelisted'] > 0
    
    def test_acceptance_rate_limit_respected(self):
        """
        Acceptance: Rate limit respected.
        """
        limiter = RateLimiter(per_domain_limit=2, per_domain_window_seconds=60.0)
        
        url = 'https://example.com/page'
        
        # Succeed twice
        assert limiter.acquire(url) == (True, 'ok')
        assert limiter.acquire(url) == (True, 'ok')
        
        # Fail on third
        success, reason = limiter.acquire(url)
        assert success is False
        assert 'domain_limit_exceeded' in reason
    
    def test_acceptance_priority_selection(self, url_matcher):
        """
        Acceptance: Selection prioritizes higher-priority sources first.
        """
        enabled = url_matcher.get_enabled_sources()
        
        # Should be in descending priority order
        priorities = [s.priority for s in enabled]
        assert priorities == sorted(priorities, reverse=True)
        
        # Highest priority source should be Wikipedia (10)
        assert enabled[0].source_id == 'wikipedia'
        assert enabled[0].priority == 10
    
    def test_acceptance_combined_whitelist_and_rate_limit(
        self, 
        url_matcher, 
        rate_limiter
    ):
        """
        Test combined whitelist and rate limiting behavior.
        """
        if not AIOHTTP_AVAILABLE:
            pytest.skip("aiohttp not available")
        
        adapter = WebExternalAdapter(
            url_matcher=url_matcher,
            rate_limiter=rate_limiter
        )
        
        # Should have both components
        assert adapter.url_matcher is not None
        assert adapter.rate_limiter is not None
        
        # Statistics should track both
        assert 'whitelisted' in adapter.stats
        assert 'not_whitelisted' in adapter.stats
        assert 'rate_limited' in adapter.stats


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_sources_list(self):
        """Test matcher with empty sources list."""
        matcher = URLMatcher([])
        
        assert matcher.match('https://example.com') is None
        assert not matcher.is_whitelisted('https://example.com')
        assert matcher.get_enabled_sources() == []
    
    def test_malformed_url_pattern(self):
        """Test handling of malformed regex patterns."""
        sources = [
            {
                'source_id': 'bad_pattern',
                'label': 'Bad',
                'priority': 5,
                'url_pattern': '[invalid(regex',  # Invalid regex
                'max_snippet_chars': 300,
                'enabled': True
            }
        ]
        
        # Should not crash, treat as literal string
        matcher = URLMatcher(sources)
        assert matcher is not None
    
    def test_zero_capacity_bucket(self):
        """Test token bucket with zero capacity."""
        bucket = TokenBucket(capacity=0, refill_rate=1.0)
        
        # Should never be able to acquire
        assert bucket.acquire(1) is False
        assert bucket.get_available_tokens() == 0.0
    
    def test_zero_refill_rate(self):
        """Test token bucket with zero refill rate."""
        bucket = TokenBucket(capacity=5, refill_rate=0.0)
        
        # Can acquire initial tokens
        assert bucket.acquire(2) is True
        
        # Wait - no refill should happen
        time.sleep(0.5)
        assert bucket.get_available_tokens() == 3.0  # Still 3
    
    def test_no_global_limit(self):
        """Test rate limiter without global limit."""
        limiter = RateLimiter(
            per_domain_limit=2,
            per_domain_window_seconds=60.0,
            global_limit=None  # No global limit
        )
        
        # Should only enforce per-domain
        url1 = 'https://example1.com/page'
        url2 = 'https://example2.com/page'
        
        # Can make many requests across domains
        for i in range(10):
            url = f'https://example{i}.com/page'
            for _ in range(2):  # Per-domain limit
                assert limiter.acquire(url) == (True, 'ok')
        
        # Global tokens should be None
        assert limiter.get_global_tokens() is None
