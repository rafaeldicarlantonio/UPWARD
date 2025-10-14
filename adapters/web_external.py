# adapters/web_external.py — Web external adapter for fetching content

import asyncio
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import re

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

class WebExternalAdapter:
    """Web adapter for fetching external content."""
    
    def __init__(self, timeout: int = 5, max_retries: int = 2):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp is required for WebExternalAdapter")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if self.session is None or self.session.closed:
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
    
    async def fetch_content(self, url: str) -> Optional[str]:
        """
        Fetch content from a URL.
        
        Args:
            url: URL to fetch content from
            
        Returns:
            Extracted text content or None if failed
        """
        if not url or not self._is_valid_url(url):
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
                            return self._extract_text(text)
                        else:
                            return None
                    else:
                        return None
                        
            except asyncio.TimeoutError:
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                return None
            except Exception:
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return None
        
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
    
    async def fetch_multiple(self, urls: list[str]) -> Dict[str, Optional[str]]:
        """
        Fetch content from multiple URLs concurrently.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            Dictionary mapping URLs to their content
        """
        await self._ensure_session()
        
        tasks = []
        for url in urls:
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