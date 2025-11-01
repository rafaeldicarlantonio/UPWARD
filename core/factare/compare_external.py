"""
External source comparison with timeout handling and graceful fallback.

Fetches content from external sources with:
- Timeout enforcement per request
- Continue-on-failure for remaining sources
- Graceful fallback to internal-only on total failure
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExternalResult:
    """Result from external source comparison."""
    success: bool
    used_external: bool
    external_items: List[Dict[str, Any]] = field(default_factory=list)
    fetch_time_ms: float = 0.0
    fetch_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)


class ExternalComparer:
    """
    Compare internal results with external sources.
    
    Handles timeouts gracefully and provides internal-only fallback.
    """
    
    def __init__(
        self,
        adapter,
        timeout_ms_per_request: int = 2000,
        max_sources: int = 5,
        continue_on_timeout: bool = True
    ):
        """
        Initialize external comparer.
        
        Args:
            adapter: WebExternalAdapter instance
            timeout_ms_per_request: Timeout per request in milliseconds
            max_sources: Maximum number of external sources to fetch
            continue_on_timeout: If True, continue with other sources on timeout
        """
        self.adapter = adapter
        self.timeout_ms_per_request = timeout_ms_per_request
        self.timeout_seconds = timeout_ms_per_request / 1000.0
        self.max_sources = max_sources
        self.continue_on_timeout = continue_on_timeout
    
    async def fetch_external_sources(
        self,
        query: str,
        urls: List[str],
        internal_results: Optional[List[Dict[str, Any]]] = None
    ) -> ExternalResult:
        """
        Fetch content from external sources with timeout handling.
        
        Args:
            query: Search query
            urls: List of URLs to fetch
            internal_results: Internal search results (for comparison)
            
        Returns:
            ExternalResult with fetched items and metadata
        """
        start_time = time.time()
        
        result = ExternalResult(
            success=False,
            used_external=False
        )
        
        if not urls:
            logger.info("No external URLs provided, using internal-only")
            return result
        
        # Limit to max sources
        urls_to_fetch = urls[:self.max_sources]
        logger.info(f"Fetching from {len(urls_to_fetch)} external sources (max={self.max_sources})")
        
        # Fetch each URL with individual timeout
        external_items = []
        
        for url in urls_to_fetch:
            try:
                # Fetch with timeout
                content = await asyncio.wait_for(
                    self.adapter.fetch_content(url),
                    timeout=self.timeout_seconds
                )
                
                if content:
                    # Create external item
                    external_item = {
                        'url': url,
                        'snippet': content[:500] if len(content) > 500 else content,
                        'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        'provenance': {
                            'url': url,
                            'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                        },
                        'external': True,
                        'metadata': {
                            'external': True,
                            'url': url
                        }
                    }
                    
                    # Try to get source info from adapter
                    if hasattr(self.adapter, 'url_matcher') and self.adapter.url_matcher:
                        match = self.adapter.url_matcher.match(url)
                        if match:
                            external_item['source_id'] = match.source_id
                            external_item['label'] = match.label
                    
                    external_items.append(external_item)
                    logger.info(f"Successfully fetched external content from {url}")
                else:
                    logger.warning(f"No content returned from {url}")
                    result.error_count += 1
                    result.errors.append(f"No content from {url}")
                    
                    if not self.continue_on_timeout:
                        break
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url} (limit: {self.timeout_ms_per_request}ms)")
                result.timeout_count += 1
                result.errors.append(f"Timeout: {url}")
                
                if not self.continue_on_timeout:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching {url}: {type(e).__name__}: {e}")
                result.error_count += 1
                result.errors.append(f"Error fetching {url}: {type(e).__name__}")
                
                if not self.continue_on_timeout:
                    break
        
        # Calculate stats
        result.fetch_time_ms = (time.time() - start_time) * 1000
        result.fetch_count = len(external_items)
        result.external_items = external_items
        
        # Determine success
        if external_items:
            result.success = True
            result.used_external = True
            logger.info(f"External fetch succeeded: {len(external_items)} items in {result.fetch_time_ms:.1f}ms")
        else:
            result.success = False
            result.used_external = False
            logger.warning(f"External fetch failed: {result.timeout_count} timeouts, {result.error_count} errors")
        
        return result
    
    async def compare(
        self,
        query: str,
        internal_results: List[Dict[str, Any]],
        external_urls: List[str]
    ) -> Dict[str, Any]:
        """
        Compare internal results with external sources.
        
        Args:
            query: Search query
            internal_results: Internal search results
            external_urls: External URLs to fetch and compare
            
        Returns:
            Comparison results with internal results always present
        """
        logger.info(f"Starting comparison: {len(internal_results)} internal, {len(external_urls)} external URLs")
        
        # Always include internal results
        comparison = {
            'query': query,
            'internal': internal_results,
            'external': [],
            'used_external': False,
            'external_fetch_time_ms': 0.0,
            'external_fetch_count': 0,
            'timeout_count': 0,
            'error_count': 0,
            'errors': []
        }
        
        # Try to fetch external sources
        external_result = await self.fetch_external_sources(
            query=query,
            urls=external_urls,
            internal_results=internal_results
        )
        
        # Update comparison with external results
        comparison['external'] = external_result.external_items
        comparison['used_external'] = external_result.used_external
        comparison['external_fetch_time_ms'] = external_result.fetch_time_ms
        comparison['external_fetch_count'] = external_result.fetch_count
        comparison['timeout_count'] = external_result.timeout_count
        comparison['error_count'] = external_result.error_count
        comparison['errors'] = external_result.errors
        
        # Log final status
        if external_result.used_external:
            logger.info(f"Comparison complete: used external sources ({external_result.fetch_count} items)")
        else:
            logger.info(f"Comparison complete: internal-only fallback (external failed)")
        
        return comparison


async def fetch_with_fallback(
    adapter,
    urls: List[str],
    timeout_ms_per_request: int = 2000,
    max_sources: int = 5
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Fetch from external sources with graceful fallback.
    
    Convenience function for simple fetch-with-fallback behavior.
    
    Args:
        adapter: WebExternalAdapter instance
        urls: List of URLs to fetch
        timeout_ms_per_request: Timeout per request in milliseconds
        max_sources: Maximum sources to fetch
        
    Returns:
        Tuple of (external_items, used_external)
        - external_items: List of fetched items (empty if all failed)
        - used_external: True if any external fetch succeeded
    """
    comparer = ExternalComparer(
        adapter=adapter,
        timeout_ms_per_request=timeout_ms_per_request,
        max_sources=max_sources,
        continue_on_timeout=True
    )
    
    result = await comparer.fetch_external_sources(
        query="",
        urls=urls
    )
    
    return result.external_items, result.used_external
