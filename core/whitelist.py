"""
URL whitelist matching and token-bucket rate limiting for external sources.

Provides fast pattern matching against whitelisted sources and enforces
rate limits both per-domain and globally.
"""

import re
import time
import fnmatch
import threading
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass, field


@dataclass
class SourceMatch:
    """Result of a successful URL match."""
    source_id: str
    label: str
    priority: int
    max_snippet_chars: int
    enabled: bool
    url_pattern: str


class URLMatcher:
    """
    Fast URL pattern matcher using compiled regex and glob patterns.
    
    Matches URLs against whitelist patterns and returns source configuration.
    Patterns are compiled once for efficiency.
    """
    
    def __init__(self, sources: List[Dict]):
        """
        Initialize matcher with source configurations.
        
        Args:
            sources: List of source dicts from whitelist config
        """
        self.sources = sources
        self._compiled_patterns: List[Tuple[re.Pattern, SourceMatch]] = []
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all URL patterns for fast matching."""
        self._compiled_patterns = []
        
        for source in self.sources:
            pattern = source.get('url_pattern', '')
            if not pattern:
                continue
            
            # Convert glob pattern to regex
            # Support both glob-style (* wildcards) and regex
            if '*' in pattern and not pattern.startswith('^'):
                # Glob-style pattern - convert to regex
                regex_pattern = fnmatch.translate(pattern)
                compiled = re.compile(regex_pattern, re.IGNORECASE)
            else:
                # Already a regex or exact match
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                except re.error:
                    # If regex compilation fails, treat as literal string
                    escaped = re.escape(pattern)
                    compiled = re.compile(escaped, re.IGNORECASE)
            
            match_info = SourceMatch(
                source_id=source.get('source_id', 'unknown'),
                label=source.get('label', 'Unknown'),
                priority=source.get('priority', 0),
                max_snippet_chars=source.get('max_snippet_chars', 400),
                enabled=source.get('enabled', True),
                url_pattern=pattern
            )
            
            self._compiled_patterns.append((compiled, match_info))
        
        # Sort by priority (higher first) for consistent ordering
        self._compiled_patterns.sort(key=lambda x: x[1].priority, reverse=True)
    
    def match(self, url: str) -> Optional[SourceMatch]:
        """
        Match URL against whitelist patterns.
        
        Args:
            url: Full URL to check
            
        Returns:
            SourceMatch if whitelisted, None otherwise
        """
        if not url:
            return None
        
        # Try each pattern in priority order
        for pattern, match_info in self._compiled_patterns:
            if not match_info.enabled:
                continue
            
            if pattern.search(url):
                return match_info
        
        return None
    
    def is_whitelisted(self, url: str) -> bool:
        """
        Check if URL is whitelisted (convenience method).
        
        Args:
            url: Full URL to check
            
        Returns:
            True if whitelisted and enabled, False otherwise
        """
        match = self.match(url)
        return match is not None and match.enabled
    
    def get_enabled_sources(self) -> List[SourceMatch]:
        """
        Get all enabled sources sorted by priority.
        
        Returns:
            List of SourceMatch objects for enabled sources
        """
        return [match for _, match in self._compiled_patterns if match.enabled]


class TokenBucket:
    """
    Token bucket implementation for rate limiting.
    
    Tokens refill at a constant rate. Each request consumes one token.
    If no tokens available, request is denied.
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False if insufficient tokens
        """
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def get_available_tokens(self) -> float:
        """
        Get current number of available tokens.
        
        Returns:
            Current token count
        """
        with self._lock:
            self._refill()
            return self.tokens
    
    def reset(self):
        """Reset bucket to full capacity."""
        with self._lock:
            self.tokens = float(self.capacity)
            self.last_refill = time.time()


class RateLimiter:
    """
    Multi-domain rate limiter using token buckets.
    
    Enforces both per-domain and global rate limits.
    """
    
    def __init__(
        self,
        per_domain_limit: int = 6,
        per_domain_window_seconds: float = 60.0,
        global_limit: Optional[int] = None
    ):
        """
        Initialize rate limiter.
        
        Args:
            per_domain_limit: Max requests per domain per window
            per_domain_window_seconds: Time window for per-domain limit
            global_limit: Max total requests (optional)
        """
        self.per_domain_limit = per_domain_limit
        self.per_domain_window_seconds = per_domain_window_seconds
        self.global_limit = global_limit
        
        # Per-domain token buckets
        self._domain_buckets: Dict[str, TokenBucket] = {}
        self._buckets_lock = threading.Lock()
        
        # Global token bucket
        if global_limit is not None:
            # Global limit is per session/run, so no refill
            self._global_bucket = TokenBucket(
                capacity=global_limit,
                refill_rate=0.0  # No refill for global limit
            )
        else:
            self._global_bucket = None
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc or parsed.hostname or 'unknown'
        except Exception:
            return 'unknown'
    
    def _get_or_create_bucket(self, domain: str) -> TokenBucket:
        """Get or create token bucket for domain."""
        with self._buckets_lock:
            if domain not in self._domain_buckets:
                # Calculate refill rate: tokens per second
                refill_rate = self.per_domain_limit / self.per_domain_window_seconds
                
                self._domain_buckets[domain] = TokenBucket(
                    capacity=self.per_domain_limit,
                    refill_rate=refill_rate
                )
            
            return self._domain_buckets[domain]
    
    def acquire(self, url: str) -> Tuple[bool, str]:
        """
        Try to acquire permission to fetch URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Tuple of (success, reason)
            - (True, 'ok') if allowed
            - (False, reason) if denied
        """
        # Check global limit first
        if self._global_bucket is not None:
            if not self._global_bucket.acquire():
                return False, 'global_limit_exceeded'
        
        # Check per-domain limit
        domain = self._get_domain(url)
        bucket = self._get_or_create_bucket(domain)
        
        if not bucket.acquire():
            return False, f'domain_limit_exceeded:{domain}'
        
        return True, 'ok'
    
    def can_acquire(self, url: str) -> bool:
        """
        Check if URL can be acquired without actually acquiring.
        
        Args:
            url: URL to check
            
        Returns:
            True if tokens available, False otherwise
        """
        # Check global
        if self._global_bucket is not None:
            if self._global_bucket.get_available_tokens() < 1:
                return False
        
        # Check domain
        domain = self._get_domain(url)
        bucket = self._get_or_create_bucket(domain)
        return bucket.get_available_tokens() >= 1
    
    def get_domain_tokens(self, url: str) -> float:
        """
        Get available tokens for URL's domain.
        
        Args:
            url: URL to check
            
        Returns:
            Available token count
        """
        domain = self._get_domain(url)
        bucket = self._get_or_create_bucket(domain)
        return bucket.get_available_tokens()
    
    def get_global_tokens(self) -> Optional[float]:
        """
        Get available global tokens.
        
        Returns:
            Available global token count, or None if no global limit
        """
        if self._global_bucket is None:
            return None
        return self._global_bucket.get_available_tokens()
    
    def reset_domain(self, url: str):
        """
        Reset rate limit for URL's domain.
        
        Args:
            url: URL whose domain to reset
        """
        domain = self._get_domain(url)
        with self._buckets_lock:
            if domain in self._domain_buckets:
                self._domain_buckets[domain].reset()
    
    def reset_global(self):
        """Reset global rate limit."""
        if self._global_bucket is not None:
            self._global_bucket.reset()
    
    def reset_all(self):
        """Reset all rate limits."""
        with self._buckets_lock:
            for bucket in self._domain_buckets.values():
                bucket.reset()
        
        if self._global_bucket is not None:
            self._global_bucket.reset()


def create_matcher_and_limiter(config_loader) -> Tuple[URLMatcher, RateLimiter]:
    """
    Create URLMatcher and RateLimiter from config.
    
    Args:
        config_loader: ConfigLoader instance
        
    Returns:
        Tuple of (URLMatcher, RateLimiter)
    """
    # Get whitelist and policy
    whitelist = config_loader.get_whitelist(enabled_only=False)
    policy = config_loader.get_compare_policy()
    
    # Create matcher from whitelist
    sources = [
        {
            'source_id': s.source_id,
            'label': s.label,
            'priority': s.priority,
            'url_pattern': s.url_pattern,
            'max_snippet_chars': s.max_snippet_chars,
            'enabled': s.enabled
        }
        for s in whitelist
    ]
    matcher = URLMatcher(sources)
    
    # Create rate limiter from policy
    limiter = RateLimiter(
        per_domain_limit=policy.rate_limit_per_domain_per_min,
        per_domain_window_seconds=60.0,  # Per minute
        global_limit=policy.max_external_sources_per_run
    )
    
    return matcher, limiter
