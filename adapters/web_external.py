# adapters/web_external.py — Web external adapter for fetching content

import asyncio
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

class WebExternalAdapter:
    """Web adapter for fetching external content with whitelist and rate limiting."""
    
    def __init__(
        self, 
        timeout: int = 5,
        timeout_ms: Optional[int] = None,
        max_retries: int = 2,
        url_matcher: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        continue_on_failure: bool = True
    ):
        """
        Initialize web external adapter.
        
        Args:
            timeout: Request timeout in seconds (deprecated, use timeout_ms)
            timeout_ms: Request timeout in milliseconds (preferred)
            max_retries: Maximum retry attempts
            url_matcher: URLMatcher instance for whitelist checking
            rate_limiter: RateLimiter instance for rate limiting
            continue_on_failure: If True, continue with other sources on failure
        """
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp is required for WebExternalAdapter")
        
        # Use timeout_ms if provided, otherwise convert timeout seconds to ms
        if timeout_ms is not None:
            self.timeout_ms = timeout_ms
            self.timeout = timeout_ms / 1000.0
        else:
            self.timeout = timeout
            self.timeout_ms = int(timeout * 1000)
        
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self.url_matcher = url_matcher
        self.rate_limiter = rate_limiter
        self.continue_on_failure = continue_on_failure
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'whitelisted': 0,
            'not_whitelisted': 0,
            'rate_limited': 0,
            'successful': 0,
            'failed': 0,
            'timeouts': 0
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure HTTP session is created with configured timeout."""
        if self.session is None or self.session.closed:
            # Create timeout from milliseconds
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Factare-External-Adapter/1.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
            )
            logger.debug(f"Created HTTP session with timeout={self.timeout}s ({self.timeout_ms}ms)")
    
    async def fetch_content(self, url: str) -> Optional[str]:
        """
        Fetch content from a URL with whitelist and rate limit checks.
        
        IMPORTANT: This fetches external content for display/comparison ONLY.
        External content must NEVER be persisted to memories/entities/edges.
        All results should be marked with provenance.url to prevent auto-ingestion.
        
        Args:
            url: URL to fetch content from
            
        Returns:
            Extracted text content or None if failed/blocked
        """
        self.stats['total_requests'] += 1
        
        logger.info(f"Fetching external content from {url} (display only, will not persist)")
        
        # Basic validation
        if not url or not self._is_valid_url(url):
            self.stats['failed'] += 1
            return None
        
        # Check whitelist if matcher provided
        if self.url_matcher is not None:
            if not self.url_matcher.is_whitelisted(url):
                logger.warning(f"URL not whitelisted: {url}")
                self.stats['not_whitelisted'] += 1
                return None
            self.stats['whitelisted'] += 1
        
        # Check rate limit if limiter provided
        if self.rate_limiter is not None:
            allowed, reason = self.rate_limiter.acquire(url)
            if not allowed:
                logger.warning(f"Rate limit exceeded for {url}: {reason}")
                self.stats['rate_limited'] += 1
                return None
        
        await self._ensure_session()
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '').lower()
                        
                        # Only process text content
                        if 'text/html' in content_type or 'text/plain' in content_type:
                            text = await response.text()
                            extracted = self._extract_text(text)
                            self.stats['successful'] += 1
                            return extracted
                        else:
                            self.stats['failed'] += 1
                            return None
                    else:
                        self.stats['failed'] += 1
                        return None
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{self.max_retries + 1})")
                self.stats['timeouts'] += 1
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                self.stats['failed'] += 1
                return None
            except Exception as e:
                logger.warning(f"Error fetching {url}: {type(e).__name__} (attempt {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                self.stats['failed'] += 1
                return None
        
        self.stats['failed'] += 1
        return None
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and safe to fetch."""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ['http', 'https'] and
                parsed.netloc and
                not parsed.netloc.startswith('localhost') and
                not parsed.netloc.startswith('127.0.0.1') and
                not parsed.netloc.startswith('0.0.0.0') and
                not parsed.netloc.startswith('::1')
            )
        except Exception:
            return False
    
    def _extract_text(self, html: str) -> str:
        """Extract text content from HTML."""
        if not html:
            return ""
        
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # Decode HTML entities
        text = self._decode_html_entities(text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _decode_html_entities(self, text: str) -> str:
        """Decode common HTML entities."""
        entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' ',
            '&ndash;': '-',
            '&mdash;': '--',
            '&hellip;': '...',
            '&copy;': '(c)',
            '&reg;': '(R)',
            '&trade;': '(TM)',
        }
        
        for entity, replacement in entities.items():
            text = text.replace(entity, replacement)
        
        return text
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def fetch_multiple(
        self, 
        urls: List[str],
        prioritize: bool = True
    ) -> Dict[str, Optional[str]]:
        """
        Fetch content from multiple URLs concurrently with priority ordering.
        
        Args:
            urls: List of URLs to fetch
            prioritize: If True, sort by priority from url_matcher
            
        Returns:
            Dictionary mapping URLs to their content
        """
        await self._ensure_session()
        
        # Sort URLs by priority if matcher available and prioritize enabled
        fetch_urls = urls[:]
        if prioritize and self.url_matcher is not None:
            # Get source info for each URL
            url_priorities = []
            for url in urls:
                match = self.url_matcher.match(url)
                priority = match.priority if match else 0
                url_priorities.append((url, priority))
            
            # Sort by priority (higher first)
            url_priorities.sort(key=lambda x: x[1], reverse=True)
            fetch_urls = [url for url, _ in url_priorities]
        
        tasks = []
        for url in fetch_urls:
            task = asyncio.create_task(self.fetch_content(url))
            tasks.append((url, task))
        
        results = {}
        for url, task in tasks:
            try:
                content = await task
                results[url] = content
            except Exception:
                results[url] = None
        
        return results
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get adapter statistics.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset adapter statistics."""
        self.stats = {
            'total_requests': 0,
            'whitelisted': 0,
            'not_whitelisted': 0,
            'rate_limited': 0,
            'successful': 0,
            'failed': 0,
            'timeouts': 0
        }
    
    def get_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    def is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain."""
        domain1 = self.get_domain(url1)
        domain2 = self.get_domain(url2)
        return domain1 is not None and domain1 == domain2

# Mock adapter for testing
class MockWebExternalAdapter:
    """Mock web adapter for testing."""
    
    def __init__(self, mock_responses: Optional[Dict[str, str]] = None, 
                 mock_delays: Optional[Dict[str, float]] = None,
                 mock_errors: Optional[Dict[str, Exception]] = None):
        self.mock_responses = mock_responses or {}
        self.mock_delays = mock_delays or {}
        self.mock_errors = mock_errors or {}
        self.fetch_count = 0
    
    async def fetch_content(self, url: str) -> Optional[str]:
        """Mock fetch content with configurable responses."""
        self.fetch_count += 1
        
        # Check for mock errors
        if url in self.mock_errors:
            raise self.mock_errors[url]
        
        # Check for mock delays
        if url in self.mock_delays:
            await asyncio.sleep(self.mock_delays[url])
        
        # Return mock response
        return self.mock_responses.get(url)
    
    def set_mock_response(self, url: str, content: str):
        """Set mock response for a URL."""
        self.mock_responses[url] = content
    
    def set_mock_delay(self, url: str, delay: float):
        """Set mock delay for a URL."""
        self.mock_delays[url] = delay
    
    def set_mock_error(self, url: str, error: Exception):
        """Set mock error for a URL."""
        self.mock_errors[url] = error
    
    def reset(self):
        """Reset mock state."""
        self.mock_responses.clear()
        self.mock_delays.clear()
        self.mock_errors.clear()
        self.fetch_count = 0