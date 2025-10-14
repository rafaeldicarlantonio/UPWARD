# core/factare/compare_external.py — External compare adapter with whitelist and rate limits

import asyncio
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse
import re

from core.factare.compare_internal import InternalComparator, RetrievalCandidate, ComparisonResult
from core.factare.summary import CompareSummary
from core.policy import is_source_whitelisted, get_external_timeout_ms
from adapters.web_external import WebExternalAdapter

@dataclass
class ExternalSnippet:
    """External snippet with provenance information."""
    url: str
    snippet: str
    source: str
    score: float
    fetched_at: datetime
    domain: str
    redacted: bool = False
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class RateLimitInfo:
    """Rate limiting information for a domain."""
    domain: str
    last_request: Optional[datetime] = None
    request_count: int = 0
    window_start: Optional[datetime] = None

@dataclass
class ExternalAdapterConfig:
    """Configuration for external adapter."""
    max_external_snippets: int = 5
    max_snippet_length: int = 200
    rate_limit_per_domain: int = 3  # requests per minute
    rate_limit_window_minutes: int = 1
    timeout_seconds: int = 2
    enable_redaction: bool = True
    redaction_patterns: List[str] = None

    def __post_init__(self):
        if self.redaction_patterns is None:
            self.redaction_patterns = [
                r'\b\d{4}-\d{2}-\d{2}\b',  # Dates
                r'\b\d{3}-\d{3}-\d{4}\b',  # Phone numbers
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
                r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # IP addresses
                r'\b[A-Z]{2,}\b',  # Acronyms (potential PII)
            ]

class ExternalCompareAdapter:
    """External compare adapter with whitelist, rate limits, and redaction."""
    
    def __init__(self, config: Optional[ExternalAdapterConfig] = None, web_adapter=None):
        self.config = config or ExternalAdapterConfig()
        self.internal_comparator = InternalComparator()
        self.web_adapter = web_adapter or WebExternalAdapter()
        self.rate_limits: Dict[str, RateLimitInfo] = {}
        self.whitelist_cache: Set[str] = set()
        self._lock = asyncio.Lock()
    
    async def compare_with_external(
        self, 
        query: str, 
        internal_candidates: List[RetrievalCandidate],
        external_urls: List[str],
        feature_flags: Dict[str, bool]
    ) -> ComparisonResult:
        """
        Compare with both internal and external sources.
        
        Args:
            query: The query being analyzed
            internal_candidates: Internal retrieval candidates
            external_urls: URLs to fetch external content from
            feature_flags: Feature flags including factare.allow_external
            
        Returns:
            ComparisonResult with both internal and external evidence
        """
        # Check if external sources are allowed
        if not feature_flags.get('factare.allow_external', False):
            return self.internal_comparator.compare(query, internal_candidates)
        
        # Filter URLs by whitelist
        whitelisted_urls = await self._filter_whitelisted_urls(external_urls)
        
        if not whitelisted_urls:
            # No whitelisted URLs, use internal only
            return self.internal_comparator.compare(query, internal_candidates)
        
        # Fetch external snippets with rate limiting
        external_snippets = await self._fetch_external_snippets(whitelisted_urls)
        
        # Combine internal and external candidates
        all_candidates = internal_candidates + external_snippets
        
        # Run internal comparison with combined candidates
        return self.internal_comparator.compare(query, all_candidates)
    
    async def _filter_whitelisted_urls(self, urls: List[str]) -> List[str]:
        """Filter URLs to only include whitelisted ones."""
        whitelisted = []
        
        for url in urls:
            if not url:
                continue
                
            # Check cache first
            if url in self.whitelist_cache:
                whitelisted.append(url)
                continue
            
            # Check whitelist
            if is_source_whitelisted(url):
                whitelisted.append(url)
                self.whitelist_cache.add(url)
        
        return whitelisted
    
    async def _fetch_external_snippets(self, urls: List[str]) -> List[RetrievalCandidate]:
        """Fetch external snippets with rate limiting and timeout."""
        snippets = []
        
        # Limit number of external snippets
        limited_urls = urls[:self.config.max_external_snippets]
        
        # Group URLs by domain for rate limiting
        domain_groups = self._group_urls_by_domain(limited_urls)
        
        for domain, domain_urls in domain_groups.items():
            # Check rate limit for this domain
            if not await self._check_rate_limit(domain):
                continue
            
            # Fetch snippets for this domain
            domain_snippets = await self._fetch_domain_snippets(domain, domain_urls)
            snippets.extend(domain_snippets)
        
        return snippets
    
    def _group_urls_by_domain(self, urls: List[str]) -> Dict[str, List[str]]:
        """Group URLs by domain for rate limiting."""
        domain_groups = {}
        
        for url in urls:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                if domain:
                    if domain not in domain_groups:
                        domain_groups[domain] = []
                    domain_groups[domain].append(url)
            except Exception:
                # Skip invalid URLs
                continue
        
        return domain_groups
    
    async def _check_rate_limit(self, domain: str) -> bool:
        """Check if domain is within rate limits."""
        async with self._lock:
            now = datetime.now()
            
            if domain not in self.rate_limits:
                self.rate_limits[domain] = RateLimitInfo(domain=domain)
            
            rate_info = self.rate_limits[domain]
            
            # Reset window if needed
            if (rate_info.window_start is None or 
                now - rate_info.window_start > timedelta(minutes=self.config.rate_limit_window_minutes)):
                rate_info.window_start = now
                rate_info.request_count = 0
            
            # Check if we're within limits
            if rate_info.request_count >= self.config.rate_limit_per_domain:
                return False
            
            # Update rate limit info
            rate_info.request_count += 1
            rate_info.last_request = now
            
            return True
    
    async def _fetch_domain_snippets(self, domain: str, urls: List[str]) -> List[RetrievalCandidate]:
        """Fetch snippets for a specific domain."""
        snippets = []
        
        for url in urls:
            try:
                # Fetch content with timeout
                content = await asyncio.wait_for(
                    self.web_adapter.fetch_content(url),
                    timeout=self.config.timeout_seconds
                )
                
                if content:
                    # Redact content
                    redacted_content = self._redact_content(content)
                    
                    # Create snippet
                    snippet = self._create_snippet(redacted_content, url)
                    
                    if snippet:
                        # Create retrieval candidate
                        candidate = RetrievalCandidate(
                            id=f"external_{hash(url)}",
                            content=snippet,
                            source=f"External: {domain}",
                            score=0.7,  # Default score for external content
                            url=url,
                            timestamp=datetime.now(),
                            metadata={
                                'domain': domain,
                                'fetched_at': datetime.now().isoformat(),
                                'redacted': len(snippet) < len(redacted_content),
                                'original_length': len(content)
                            }
                        )
                        snippets.append(candidate)
                
            except asyncio.TimeoutError:
                # Skip on timeout
                continue
            except Exception:
                # Skip on any other error
                continue
        
        return snippets
    
    def _redact_content(self, content: str) -> str:
        """Redact sensitive content from text."""
        if not self.config.enable_redaction:
            return content
        
        redacted = content
        
        for pattern in self.config.redaction_patterns:
            redacted = re.sub(pattern, '[REDACTED]', redacted, flags=re.IGNORECASE)
        
        return redacted
    
    def _create_snippet(self, content: str, url: str) -> Optional[str]:
        """Create a snippet from content."""
        if not content:
            return None
        
        # Clean content
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Truncate to max length
        if len(content) > self.config.max_snippet_length:
            content = content[:self.config.max_snippet_length].rsplit(' ', 1)[0] + "..."
        
        # Ensure minimum length
        if len(content) < 20:
            return None
        
        return content
    
    async def create_compare_summary_with_external(
        self,
        query: str,
        internal_candidates: List[RetrievalCandidate],
        external_urls: List[str],
        feature_flags: Dict[str, bool]
    ) -> CompareSummary:
        """
        Create CompareSummary with external sources.
        
        Args:
            query: The query being analyzed
            internal_candidates: Internal retrieval candidates
            external_urls: URLs to fetch external content from
            feature_flags: Feature flags including factare.allow_external
            
        Returns:
            CompareSummary with both internal and external evidence
        """
        result = await self.compare_with_external(
            query, internal_candidates, external_urls, feature_flags
        )
        
        # Convert evidence items to the format expected by create_compare_summary
        evidence_items_data = []
        for item in result.evidence_items:
            evidence_items_data.append({
                'id': item.id,
                'snippet': item.snippet,
                'source': item.source,
                'score': item.score,
                'url': item.url,
                'timestamp': item.timestamp.isoformat() if item.timestamp else None,
                'metadata': item.metadata
            })
        
        if not result.has_binary_contrast:
            # Create a neutral summary
            return CompareSummary(
                query=query,
                stance_a="No clear stance A identified",
                stance_b="No clear stance B identified",
                evidence=result.evidence_items,
                decision=result.decision,
                created_at=datetime.now(),
                metadata={
                    **result.metadata,
                    'external_sources_used': len([item for item in result.evidence_items if item.is_external]),
                    'external_urls_provided': len(external_urls),
                    'external_urls_whitelisted': len([url for url in external_urls if is_source_whitelisted(url)])
                }
            )
        
        return CompareSummary(
            query=query,
            stance_a=result.stance_a or "Stance A not identified",
            stance_b=result.stance_b or "Stance B not identified",
            evidence=result.evidence_items,
            decision=result.decision,
            created_at=datetime.now(),
            metadata={
                **result.metadata,
                'external_sources_used': len([item for item in result.evidence_items if item.is_external]),
                'external_urls_provided': len(external_urls),
                'external_urls_whitelisted': len([url for url in external_urls if is_source_whitelisted(url)])
            }
        )
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status for all domains."""
        now = datetime.now()
        status = {}
        
        for domain, rate_info in self.rate_limits.items():
            status[domain] = {
                'request_count': rate_info.request_count,
                'last_request': rate_info.last_request.isoformat() if rate_info.last_request else None,
                'window_start': rate_info.window_start.isoformat() if rate_info.window_start else None,
                'within_limits': rate_info.request_count < self.config.rate_limit_per_domain
            }
        
        return status
    
    def reset_rate_limits(self):
        """Reset all rate limits."""
        self.rate_limits.clear()
        self.whitelist_cache.clear()

# Convenience function for synchronous usage
def create_external_adapter(config: Optional[ExternalAdapterConfig] = None, web_adapter=None) -> ExternalCompareAdapter:
    """Create an external compare adapter."""
    return ExternalCompareAdapter(config, web_adapter)

# Async convenience function
async def compare_with_external_sources(
    query: str,
    internal_candidates: List[RetrievalCandidate],
    external_urls: List[str],
    feature_flags: Dict[str, bool],
    config: Optional[ExternalAdapterConfig] = None
) -> CompareSummary:
    """
    Compare with external sources (convenience function).
    
    Args:
        query: The query being analyzed
        internal_candidates: Internal retrieval candidates
        external_urls: URLs to fetch external content from
        feature_flags: Feature flags including factare.allow_external
        config: Optional adapter configuration
        
    Returns:
        CompareSummary with both internal and external evidence
    """
    adapter = ExternalCompareAdapter(config)
    return await adapter.create_compare_summary_with_external(
        query, internal_candidates, external_urls, feature_flags
    )