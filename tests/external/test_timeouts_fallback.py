"""
Tests for timeout enforcement and graceful fallback behavior.

Verifies that:
- Timeout per request is enforced
- On timeout, system logs and continues with remaining sources
- On total failure, system returns internal-only with used_external=false
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from core.factare.compare_external import (
    ExternalComparer,
    ExternalResult,
    fetch_with_fallback
)

try:
    from adapters.web_external import WebExternalAdapter, MockWebExternalAdapter
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    WebExternalAdapter = None
    MockWebExternalAdapter = None

requires_aiohttp = pytest.mark.skipif(
    not AIOHTTP_AVAILABLE,
    reason="aiohttp not installed"
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_adapter():
    """Create mock adapter for testing."""
    if not AIOHTTP_AVAILABLE:
        pytest.skip("aiohttp not available")
    
    adapter = MockWebExternalAdapter({
        'https://fast.example.com/page': 'Fast content',
        'https://slow.example.com/page': 'Slow content',
        'https://example.com/page1': 'Content 1',
        'https://example.com/page2': 'Content 2',
        'https://example.com/page3': 'Content 3',
    })
    
    # Add delays to simulate slow responses
    adapter.set_mock_delay('https://slow.example.com/page', 5.0)  # Very slow
    
    return adapter


@pytest.fixture
def mock_adapter_all_slow():
    """Create adapter where all requests timeout."""
    if not AIOHTTP_AVAILABLE:
        pytest.skip("aiohttp not available")
    
    adapter = MockWebExternalAdapter({
        'https://slow1.example.com/page': 'Content 1',
        'https://slow2.example.com/page': 'Content 2',
        'https://slow3.example.com/page': 'Content 3',
    })
    
    # All requests are slow
    adapter.set_mock_delay('https://slow1.example.com/page', 5.0)
    adapter.set_mock_delay('https://slow2.example.com/page', 5.0)
    adapter.set_mock_delay('https://slow3.example.com/page', 5.0)
    
    return adapter


@pytest.fixture
def mock_adapter_with_errors():
    """Create adapter with various error conditions."""
    if not AIOHTTP_AVAILABLE:
        pytest.skip("aiohttp not available")
    
    adapter = MockWebExternalAdapter({
        'https://error.example.com/page': None,  # Returns None
        'https://good.example.com/page': 'Good content',
    })
    
    # Add error for one URL
    adapter.set_mock_error('https://error.example.com/page', Exception("Network error"))
    
    return adapter


@pytest.fixture
def internal_results():
    """Sample internal search results."""
    return [
        {'id': 'mem_1', 'text': 'Internal result 1', 'score': 0.9},
        {'id': 'mem_2', 'text': 'Internal result 2', 'score': 0.8}
    ]


# ============================================================================
# Test: Timeout Enforcement
# ============================================================================

class TestTimeoutEnforcement:
    """Test that timeout per request is enforced."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_timeout_enforced_per_request(self, mock_adapter):
        """
        Acceptance: Timeout per request is enforced.
        """
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500,  # 500ms timeout
            continue_on_timeout=True
        )
        
        # This URL has 5 second delay, should timeout
        urls = ['https://slow.example.com/page']
        
        start_time = time.time()
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        elapsed = time.time() - start_time
        
        # Should timeout quickly (not wait 5 seconds)
        assert elapsed < 1.0  # Should be around 0.5s
        assert result.timeout_count == 1
        assert not result.used_external
        assert len(result.external_items) == 0
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_fast_request_succeeds(self, mock_adapter):
        """Test that fast requests complete successfully."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=2000,  # 2 second timeout
            continue_on_timeout=True
        )
        
        # This URL is fast
        urls = ['https://fast.example.com/page']
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        assert result.timeout_count == 0
        assert result.used_external
        assert len(result.external_items) == 1
        assert result.external_items[0]['url'] == 'https://fast.example.com/page'
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_timeout_per_request_independent(self, mock_adapter):
        """Test that timeout applies independently to each request."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500,
            continue_on_timeout=True
        )
        
        # Mix of fast and slow URLs
        urls = [
            'https://fast.example.com/page',
            'https://slow.example.com/page',  # Will timeout
            'https://example.com/page1',
        ]
        
        start_time = time.time()
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (not 5+ seconds for slow URL)
        assert elapsed < 2.0
        
        # Should have 1 timeout and 2 successes
        assert result.timeout_count == 1
        assert result.used_external  # At least some succeeded
        assert len(result.external_items) >= 2


# ============================================================================
# Test: Continue-on-Failure Behavior
# ============================================================================

class TestContinueOnFailure:
    """Test continue-on-failure semantics."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_continue_after_timeout(self, mock_adapter):
        """
        Acceptance: On timeout, log and continue with remaining sources.
        """
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500,
            continue_on_timeout=True
        )
        
        urls = [
            'https://slow.example.com/page',  # Will timeout
            'https://example.com/page1',       # Should succeed
            'https://example.com/page2',       # Should succeed
        ]
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        # Should have 1 timeout but continue with others
        assert result.timeout_count == 1
        assert result.used_external
        assert len(result.external_items) == 2  # 2 successful
        
        # Check errors logged
        assert len(result.errors) >= 1
        assert any('Timeout' in err for err in result.errors)
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_continue_after_error(self, mock_adapter_with_errors):
        """Test that processing continues after non-timeout errors."""
        comparer = ExternalComparer(
            adapter=mock_adapter_with_errors,
            timeout_ms_per_request=2000,
            continue_on_timeout=True
        )
        
        urls = [
            'https://error.example.com/page',  # Will error
            'https://good.example.com/page',    # Should succeed
        ]
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        # Should have 1 error but continue
        assert result.error_count >= 1
        assert result.used_external  # Good one succeeded
        assert len(result.external_items) >= 1
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_stop_on_timeout_when_configured(self, mock_adapter):
        """Test that processing stops on timeout when continue_on_timeout=False."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500,
            continue_on_timeout=False  # Stop on timeout
        )
        
        urls = [
            'https://slow.example.com/page',  # Will timeout
            'https://example.com/page1',       # Should not try
            'https://example.com/page2',       # Should not try
        ]
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        # Should stop after first timeout
        assert result.timeout_count == 1
        assert not result.used_external
        assert len(result.external_items) == 0


# ============================================================================
# Test: Graceful Fallback
# ============================================================================

class TestGracefulFallback:
    """Test graceful fallback to internal-only."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_total_failure_returns_internal_only(
        self, 
        mock_adapter_all_slow,
        internal_results
    ):
        """
        Acceptance: On total failure, return internal-only with used_external=false.
        """
        comparer = ExternalComparer(
            adapter=mock_adapter_all_slow,
            timeout_ms_per_request=500,
            continue_on_timeout=True
        )
        
        urls = [
            'https://slow1.example.com/page',
            'https://slow2.example.com/page',
            'https://slow3.example.com/page',
        ]
        
        comparison = await comparer.compare(
            query="test query",
            internal_results=internal_results,
            external_urls=urls
        )
        
        # Should fall back to internal-only
        assert comparison['used_external'] is False
        assert len(comparison['external']) == 0
        assert len(comparison['internal']) == 2  # Internal results preserved
        assert comparison['timeout_count'] == 3
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_no_urls_returns_internal_only(self, mock_adapter, internal_results):
        """Test that empty URL list returns internal-only."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=2000
        )
        
        comparison = await comparer.compare(
            query="test query",
            internal_results=internal_results,
            external_urls=[]  # No external URLs
        )
        
        # Should be internal-only
        assert comparison['used_external'] is False
        assert len(comparison['external']) == 0
        assert len(comparison['internal']) == 2
        assert comparison['timeout_count'] == 0
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_internal_always_present(self, mock_adapter, internal_results):
        """Test that internal results are always present, even with external success."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=2000
        )
        
        urls = ['https://fast.example.com/page']
        
        comparison = await comparer.compare(
            query="test query",
            internal_results=internal_results,
            external_urls=urls
        )
        
        # Both internal and external should be present
        assert len(comparison['internal']) == 2  # Internal preserved
        assert len(comparison['external']) == 1  # External added
        assert comparison['used_external'] is True
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_partial_success_includes_internal_and_external(
        self,
        mock_adapter,
        internal_results
    ):
        """Test that partial external success includes both internal and external."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500
        )
        
        urls = [
            'https://slow.example.com/page',  # Timeout
            'https://fast.example.com/page',  # Success
        ]
        
        comparison = await comparer.compare(
            query="test query",
            internal_results=internal_results,
            external_urls=urls
        )
        
        # Should have both
        assert len(comparison['internal']) == 2
        assert len(comparison['external']) == 1  # Only the successful one
        assert comparison['used_external'] is True
        assert comparison['timeout_count'] == 1


# ============================================================================
# Test: External Item Structure
# ============================================================================

class TestExternalItemStructure:
    """Test that external items have correct structure."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_external_item_has_required_fields(self, mock_adapter):
        """Test that external items have all required fields."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=2000
        )
        
        urls = ['https://fast.example.com/page']
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        assert len(result.external_items) == 1
        item = result.external_items[0]
        
        # Required fields
        assert 'url' in item
        assert 'snippet' in item
        assert 'fetched_at' in item
        assert 'provenance' in item
        assert 'external' in item
        assert item['external'] is True
        
        # Provenance structure
        assert 'url' in item['provenance']
        assert 'fetched_at' in item['provenance']
        
        # Metadata
        assert 'metadata' in item
        assert item['metadata']['external'] is True
        assert 'url' in item['metadata']
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_snippet_truncation(self, mock_adapter):
        """Test that snippets are truncated to reasonable length."""
        # Create adapter with long content
        long_content = 'A' * 1000
        adapter = MockWebExternalAdapter({
            'https://long.example.com/page': long_content
        })
        
        comparer = ExternalComparer(
            adapter=adapter,
            timeout_ms_per_request=2000
        )
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=['https://long.example.com/page']
        )
        
        assert len(result.external_items) == 1
        item = result.external_items[0]
        
        # Snippet should be truncated
        assert len(item['snippet']) <= 500
        assert len(item['snippet']) < len(long_content)


# ============================================================================
# Test: fetch_with_fallback Convenience Function
# ============================================================================

class TestFetchWithFallbackFunction:
    """Test the convenience function."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_fetch_with_fallback_success(self, mock_adapter):
        """Test successful fetch with convenience function."""
        urls = ['https://fast.example.com/page', 'https://example.com/page1']
        
        items, used_external = await fetch_with_fallback(
            adapter=mock_adapter,
            urls=urls,
            timeout_ms_per_request=2000
        )
        
        assert used_external is True
        assert len(items) == 2
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_fetch_with_fallback_total_failure(self, mock_adapter_all_slow):
        """Test total failure with convenience function."""
        urls = [
            'https://slow1.example.com/page',
            'https://slow2.example.com/page'
        ]
        
        items, used_external = await fetch_with_fallback(
            adapter=mock_adapter_all_slow,
            urls=urls,
            timeout_ms_per_request=500
        )
        
        assert used_external is False
        assert len(items) == 0


# ============================================================================
# Test: Max Sources Limit
# ============================================================================

class TestMaxSourcesLimit:
    """Test max_sources limiting."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_max_sources_enforced(self, mock_adapter):
        """Test that max_sources limit is enforced."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=2000,
            max_sources=2  # Only fetch 2
        )
        
        urls = [
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/page3',  # Should not fetch
        ]
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        # Should only fetch first 2
        assert len(result.external_items) <= 2
        assert result.fetch_count == 2


# ============================================================================
# Test: Statistics Tracking
# ============================================================================

class TestStatisticsTracking:
    """Test that statistics are tracked correctly."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_timeout_statistics(self, mock_adapter):
        """Test that timeout statistics are tracked."""
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500
        )
        
        urls = [
            'https://slow.example.com/page',  # Timeout
            'https://fast.example.com/page',  # Success
        ]
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        assert result.timeout_count == 1
        assert result.fetch_count == 1
        assert result.error_count == 0
        assert result.fetch_time_ms > 0
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_error_statistics(self, mock_adapter_with_errors):
        """Test that error statistics are tracked."""
        comparer = ExternalComparer(
            adapter=mock_adapter_with_errors,
            timeout_ms_per_request=2000
        )
        
        urls = [
            'https://error.example.com/page',  # Error
            'https://good.example.com/page',   # Success
        ]
        
        result = await comparer.fetch_external_sources(
            query="test",
            urls=urls
        )
        
        assert result.error_count >= 1
        assert result.timeout_count == 0
        assert result.fetch_count >= 1


# ============================================================================
# Test: Acceptance Criteria
# ============================================================================

class TestAcceptanceCriteria:
    """Direct verification of all acceptance criteria."""
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_acceptance_timeout_enforced(self, mock_adapter):
        """
        Acceptance: Enforce timeout_ms_per_request.
        """
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500
        )
        
        urls = ['https://slow.example.com/page']
        
        start = time.time()
        result = await comparer.fetch_external_sources("test", urls)
        elapsed = time.time() - start
        
        # Should timeout quickly
        assert elapsed < 1.0
        assert result.timeout_count > 0
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_acceptance_continue_on_timeout(self, mock_adapter):
        """
        Acceptance: On timeout, log and continue with remaining sources.
        """
        comparer = ExternalComparer(
            adapter=mock_adapter,
            timeout_ms_per_request=500,
            continue_on_timeout=True
        )
        
        urls = [
            'https://slow.example.com/page',
            'https://fast.example.com/page'
        ]
        
        result = await comparer.fetch_external_sources("test", urls)
        
        # Should have timeout and success
        assert result.timeout_count == 1
        assert result.fetch_count == 1
        assert result.used_external is True
    
    @requires_aiohttp
    @pytest.mark.anyio
    async def test_acceptance_internal_only_fallback(
        self,
        mock_adapter_all_slow,
        internal_results
    ):
        """
        Acceptance: On total failure, return internal-only with used_external=false.
        """
        comparer = ExternalComparer(
            adapter=mock_adapter_all_slow,
            timeout_ms_per_request=500
        )
        
        urls = [
            'https://slow1.example.com/page',
            'https://slow2.example.com/page'
        ]
        
        comparison = await comparer.compare(
            query="test",
            internal_results=internal_results,
            external_urls=urls
        )
        
        # Should fall back to internal-only
        assert comparison['used_external'] is False
        assert len(comparison['internal']) > 0  # Internal preserved
        assert len(comparison['external']) == 0  # External failed
