# core/factare/service.py — Core factare service with internal and external comparison

import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from core.factare.compare_internal import InternalComparator, RetrievalCandidate
from core.factare.compare_external import ExternalCompareAdapter, ExternalAdapterConfig
from core.factare.summary import CompareSummary
from core.policy import can_access_factare, is_external_allowed, get_user_policy_summary
from feature_flags import get_feature_flag

@dataclass
class ComparisonOptions:
    """Options for factare comparison."""
    allow_external: bool = False
    max_external_snippets: int = 5
    max_snippet_length: int = 200
    timeout_seconds: int = 2
    enable_redaction: bool = True

@dataclass
class ComparisonResult:
    """Result of factare comparison."""
    compare_summary: CompareSummary
    contradictions: List[Dict[str, Any]]
    used_external: bool
    timings: Dict[str, float]
    metadata: Dict[str, Any]

@dataclass
class ComparisonTimings:
    """Timing information for comparison."""
    internal_ms: float
    external_ms: float
    total_ms: float
    redaction_ms: float = 0.0

class FactareService:
    """Core factare service for internal and external comparison."""
    
    def __init__(self):
        self.internal_comparator = InternalComparator()
        self.external_adapter = None  # Lazy initialization
        self._external_config = None
    
    def _get_external_adapter(self, options: ComparisonOptions) -> ExternalCompareAdapter:
        """Get or create external adapter with configuration."""
        if self.external_adapter is None or self._external_config != options:
            config = ExternalAdapterConfig(
                max_external_snippets=options.max_external_snippets,
                max_snippet_length=options.max_snippet_length,
                timeout_seconds=options.timeout_seconds,
                enable_redaction=options.enable_redaction
            )
            self.external_adapter = ExternalCompareAdapter(config)
            self._external_config = options
        return self.external_adapter
    
    async def compare(
        self,
        query: str,
        retrieval_candidates: List[RetrievalCandidate],
        external_urls: List[str],
        user_roles: List[str],
        options: ComparisonOptions
    ) -> ComparisonResult:
        """
        Perform factare comparison with internal and optional external sources.
        
        Args:
            query: The query to compare
            retrieval_candidates: Internal retrieval candidates
            external_urls: External URLs to fetch content from
            user_roles: User roles for access control
            options: Comparison options
            
        Returns:
            ComparisonResult with summary, contradictions, and metadata
        """
        start_time = time.time()
        
        # Check if factare is enabled
        if not get_feature_flag('factare.enabled'):
            raise ValueError("Factare is not enabled")
        
        # Check if user can access factare
        if not can_access_factare(user_roles, get_feature_flag('factare.enabled')):
            raise ValueError("User does not have permission to access factare")
        
        # Determine if external sources should be used
        use_external = (
            options.allow_external and
            get_feature_flag('factare.allow_external') and
            is_external_allowed(user_roles, get_feature_flag('factare.allow_external')) and
            external_urls
        )
        
        # Run internal comparison
        internal_start = time.time()
        internal_result = self.internal_comparator.compare(query, retrieval_candidates)
        internal_ms = (time.time() - internal_start) * 1000
        
        # Initialize timings
        external_ms = 0.0
        redaction_ms = 0.0
        used_external = False
        final_summary = None
        contradictions = []
        
        if use_external:
            # Run external comparison
            external_start = time.time()
            try:
                external_adapter = self._get_external_adapter(options)
                feature_flags = {
                    'factare.allow_external': get_feature_flag('factare.allow_external')
                }
                
                final_summary = await external_adapter.create_compare_summary_with_external(
                    query, retrieval_candidates, external_urls, feature_flags
                )
                
                # Extract contradictions from external result
                external_result = await external_adapter.compare_with_external(
                    query, retrieval_candidates, external_urls, feature_flags
                )
                contradictions = [
                    {
                        'claim_a': c.claim_a,
                        'claim_b': c.claim_b,
                        'evidence_a': c.evidence_a,
                        'evidence_b': c.evidence_b,
                        'confidence': c.confidence,
                        'contradiction_type': c.contradiction_type
                    }
                    for c in external_result.contradictions
                ]
                
                used_external = True
                
            except Exception as e:
                # Fall back to internal-only on external failure
                print(f"External comparison failed, falling back to internal: {e}")
                final_summary = self.internal_comparator.create_compare_summary(
                    query, retrieval_candidates
                )
                contradictions = [
                    {
                        'claim_a': c.claim_a,
                        'claim_b': c.claim_b,
                        'evidence_a': c.evidence_a,
                        'evidence_b': c.evidence_b,
                        'confidence': c.confidence,
                        'contradiction_type': c.contradiction_type
                    }
                    for c in internal_result.contradictions
                ]
            
            external_ms = (time.time() - external_start) * 1000
        else:
            # Use internal-only result
            final_summary = self.internal_comparator.create_compare_summary(
                query, retrieval_candidates
            )
            contradictions = [
                {
                    'claim_a': c.claim_a,
                    'claim_b': c.claim_b,
                    'evidence_a': c.evidence_a,
                    'evidence_b': c.evidence_b,
                    'confidence': c.confidence,
                    'contradiction_type': c.contradiction_type
                }
                for c in internal_result.contradictions
            ]
        
        total_ms = (time.time() - start_time) * 1000
        
        # Create timings
        timings = {
            'internal_ms': internal_ms,
            'external_ms': external_ms,
            'total_ms': total_ms,
            'redaction_ms': redaction_ms
        }
        
        # Create metadata
        metadata = {
            'user_roles': user_roles,
            'options': {
                'allow_external': options.allow_external,
                'max_external_snippets': options.max_external_snippets,
                'max_snippet_length': options.max_snippet_length,
                'timeout_seconds': options.timeout_seconds,
                'enable_redaction': options.enable_redaction
            },
            'external_urls_provided': len(external_urls),
            'external_urls_used': len([url for url in external_urls if used_external]),
            'internal_candidates_count': len(retrieval_candidates),
            'contradictions_count': len(contradictions),
            'processing_timestamp': datetime.now().isoformat(),
            'policy_summary': get_user_policy_summary(
                user_roles, 
                get_feature_flag('factare.enabled'),
                get_feature_flag('factare.allow_external')
            )
        }
        
        return ComparisonResult(
            compare_summary=final_summary,
            contradictions=contradictions,
            used_external=used_external,
            timings=timings,
            metadata=metadata
        )
    
    def create_retrieval_candidates_from_dicts(
        self, 
        candidates_data: List[Dict[str, Any]]
    ) -> List[RetrievalCandidate]:
        """Create RetrievalCandidate objects from dictionary data."""
        candidates = []
        
        for data in candidates_data:
            candidate = RetrievalCandidate(
                id=data.get('id', ''),
                content=data.get('content', ''),
                source=data.get('source', ''),
                score=float(data.get('score', 0.0)),
                metadata=data.get('metadata'),
                url=data.get('url'),
                timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else None
            )
            candidates.append(candidate)
        
        return candidates
    
    def validate_options(self, options_data: Dict[str, Any]) -> ComparisonOptions:
        """Validate and create ComparisonOptions from dictionary data."""
        return ComparisonOptions(
            allow_external=bool(options_data.get('allow_external', False)),
            max_external_snippets=int(options_data.get('max_external_snippets', 5)),
            max_snippet_length=int(options_data.get('max_snippet_length', 200)),
            timeout_seconds=int(options_data.get('timeout_seconds', 2)),
            enable_redaction=bool(options_data.get('enable_redaction', True))
        )
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status and configuration."""
        return {
            'factare_enabled': get_feature_flag('factare.enabled'),
            'external_allowed': get_feature_flag('factare.allow_external'),
            'internal_comparator_available': self.internal_comparator is not None,
            'external_adapter_available': self.external_adapter is not None,
            'external_config': self._external_config.__dict__ if self._external_config else None
        }

# Global service instance
_factare_service = None

def get_factare_service() -> FactareService:
    """Get the global factare service instance."""
    global _factare_service
    if _factare_service is None:
        _factare_service = FactareService()
    return _factare_service

# Convenience function for direct comparison
async def compare_factare(
    query: str,
    retrieval_candidates: List[RetrievalCandidate],
    external_urls: List[str],
    user_roles: List[str],
    options: ComparisonOptions
) -> ComparisonResult:
    """
    Convenience function for factare comparison.
    
    Args:
        query: The query to compare
        retrieval_candidates: Internal retrieval candidates
        external_urls: External URLs to fetch content from
        user_roles: User roles for access control
        options: Comparison options
        
    Returns:
        ComparisonResult with summary, contradictions, and metadata
    """
    service = get_factare_service()
    return await service.compare(
        query, retrieval_candidates, external_urls, user_roles, options
    )