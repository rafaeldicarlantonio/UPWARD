#!/usr/bin/env python3
"""
adapters/vector_fallback.py — Pgvector fallback adapter for Pinecone outages.

Provides degraded mode retrieval using pgvector when Pinecone is unavailable:
- Reduced k values (explicate=8, implicate=4)
- Direct Postgres queries
- No cross-namespace merging
- Marks responses with fallback flag
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from vendors.supabase_client import supabase
from core.metrics import increment_counter, observe_histogram


@dataclass
class FallbackQueryResult:
    """Result from fallback vector query."""
    matches: List[Any]
    fallback_used: bool = True
    latency_ms: float = 0.0
    source: str = "pgvector"


class MockMatch:
    """Mock match object to mimic Pinecone response."""
    def __init__(self, id: str, score: float, metadata: Dict[str, Any]):
        self.id = id
        self.score = score
        self.metadata = metadata


class PgvectorFallbackAdapter:
    """Fallback vector store using pgvector when Pinecone is unavailable."""
    
    # Reduced k values for fallback mode
    FALLBACK_EXPLICATE_K = 8
    FALLBACK_IMPLICATE_K = 4
    
    # Timeout for fallback queries
    FALLBACK_TIMEOUT_MS = 350
    
    def __init__(self):
        """Initialize pgvector fallback adapter."""
        self.client = supabase
        self._health_check_cache = {
            'last_check': 0,
            'is_healthy': True,
            'cache_ttl': 30  # Cache health status for 30 seconds
        }
    
    def check_pinecone_health(self) -> Tuple[bool, Optional[str]]:
        """
        Check if Pinecone is healthy.
        
        Returns:
            Tuple of (is_healthy, error_reason)
        """
        # Check cache first
        now = time.time()
        if (now - self._health_check_cache['last_check']) < self._health_check_cache['cache_ttl']:
            cached_health = self._health_check_cache['is_healthy']
            if cached_health:
                return (True, None)
        
        try:
            # Try to import and access Pinecone
            from vendors.pinecone_client import get_index
            
            # Try a basic operation
            idx = get_index()
            
            # Try to get stats (lightweight operation)
            stats = idx.describe_index_stats()
            
            # Update cache
            self._health_check_cache['last_check'] = now
            self._health_check_cache['is_healthy'] = True
            
            return (True, None)
            
        except ImportError as e:
            error_msg = f"Pinecone import failed: {str(e)}"
            self._health_check_cache['is_healthy'] = False
            return (False, error_msg)
            
        except Exception as e:
            error_msg = f"Pinecone health check failed: {str(e)}"
            self._health_check_cache['is_healthy'] = False
            self._health_check_cache['last_check'] = now
            
            # Record health check failure
            increment_counter("vector.health_check.failed", labels={
                "backend": "pinecone",
                "reason": type(e).__name__
            })
            
            return (False, error_msg)
    
    def should_use_fallback(self) -> Tuple[bool, Optional[str]]:
        """
        Determine if fallback should be used.
        
        Returns:
            Tuple of (use_fallback, reason)
        """
        # Check if pgvector is enabled
        try:
            from config import load_config
            cfg = load_config()
            if not cfg.get('PERF_PGVECTOR_ENABLED', True):
                return (False, "pgvector_disabled")
        except Exception:
            pass
        
        # Check if fallbacks are enabled
        try:
            from config import load_config
            cfg = load_config()
            if not cfg.get('PERF_FALLBACKS_ENABLED', True):
                return (False, "fallbacks_disabled")
        except Exception:
            pass
        
        # Check Pinecone health
        is_healthy, error_reason = self.check_pinecone_health()
        
        if not is_healthy:
            increment_counter("vector.fallback.triggered", labels={
                "reason": "pinecone_unhealthy"
            })
            return (True, f"pinecone_unhealthy: {error_reason}")
        
        return (False, None)
    
    def query_explicate_fallback(
        self,
        embedding: List[float],
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
        caller_role: Optional[str] = None
    ) -> FallbackQueryResult:
        """
        Query explicate index using pgvector fallback.
        
        Args:
            embedding: Query vector
            top_k: Number of results (defaults to FALLBACK_EXPLICATE_K)
            filter: Optional metadata filter
            caller_role: Caller role for RBAC
            
        Returns:
            FallbackQueryResult with matches
        """
        start_time = time.time()
        
        # Use reduced k for fallback
        k = top_k if top_k is not None else self.FALLBACK_EXPLICATE_K
        k = min(k, self.FALLBACK_EXPLICATE_K)  # Cap at fallback max
        
        try:
            # Query pgvector table
            # Assuming table: memories with embedding column
            # Using cosine similarity via pgvector
            
            # Build filter conditions
            filter_conditions = []
            if caller_role:
                # Simple role filter (adjust based on schema)
                filter_conditions.append(f"role_rank <= {self._get_role_rank(caller_role)}")
            
            # Execute query
            # Note: This is a simplified example - adjust SQL based on actual schema
            query = f"""
                SELECT 
                    id,
                    title,
                    text,
                    created_at,
                    type,
                    role_view_level,
                    metadata,
                    1 - (embedding <=> '{self._format_vector(embedding)}') as score
                FROM memories
                WHERE 1=1
                {' AND ' + ' AND '.join(filter_conditions) if filter_conditions else ''}
                ORDER BY embedding <=> '{self._format_vector(embedding)}'
                LIMIT {k}
            """
            
            result = self.client.rpc('execute_sql', {'query': query}).execute()
            
            # Convert to matches
            matches = []
            if result.data:
                for row in result.data:
                    match = MockMatch(
                        id=row.get('id', ''),
                        score=float(row.get('score', 0.0)),
                        metadata={
                            'text': row.get('text', ''),
                            'title': row.get('title', ''),
                            'created_at': row.get('created_at'),
                            'type': row.get('type', 'semantic'),
                            'role_view_level': row.get('role_view_level', 0),
                            **(row.get('metadata', {}) or {})
                        }
                    )
                    matches.append(match)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Record metrics
            increment_counter("vector.fallback.queries", labels={
                "index": "explicate",
                "backend": "pgvector"
            })
            observe_histogram("vector.fallback.latency_ms", elapsed_ms, labels={
                "index": "explicate"
            })
            
            return FallbackQueryResult(
                matches=matches,
                fallback_used=True,
                latency_ms=elapsed_ms,
                source="pgvector"
            )
            
        except Exception as e:
            # Record error
            increment_counter("vector.fallback.errors", labels={
                "index": "explicate",
                "error": type(e).__name__
            })
            
            # Return empty result
            elapsed_ms = (time.time() - start_time) * 1000
            return FallbackQueryResult(
                matches=[],
                fallback_used=True,
                latency_ms=elapsed_ms,
                source="pgvector_error"
            )
    
    def query_implicate_fallback(
        self,
        embedding: List[float],
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
        caller_role: Optional[str] = None
    ) -> FallbackQueryResult:
        """
        Query implicate index using pgvector fallback.
        
        Args:
            embedding: Query vector
            top_k: Number of results (defaults to FALLBACK_IMPLICATE_K)
            filter: Optional metadata filter
            caller_role: Caller role for RBAC
            
        Returns:
            FallbackQueryResult with matches
        """
        start_time = time.time()
        
        # Use reduced k for fallback
        k = top_k if top_k is not None else self.FALLBACK_IMPLICATE_K
        k = min(k, self.FALLBACK_IMPLICATE_K)  # Cap at fallback max
        
        try:
            # Query implicate/concept embeddings
            # Assuming table: entity_embeddings
            
            filter_conditions = []
            if caller_role:
                filter_conditions.append(f"role_rank <= {self._get_role_rank(caller_role)}")
            
            query = f"""
                SELECT 
                    entity_id as id,
                    entity_name,
                    created_at,
                    role_view_level,
                    metadata,
                    1 - (embedding <=> '{self._format_vector(embedding)}') as score
                FROM entity_embeddings
                WHERE 1=1
                {' AND ' + ' AND '.join(filter_conditions) if filter_conditions else ''}
                ORDER BY embedding <=> '{self._format_vector(embedding)}'
                LIMIT {k}
            """
            
            result = self.client.rpc('execute_sql', {'query': query}).execute()
            
            # Convert to matches
            matches = []
            if result.data:
                for row in result.data:
                    match = MockMatch(
                        id=row.get('id', ''),
                        score=float(row.get('score', 0.0)),
                        metadata={
                            'entity_id': row.get('id', ''),
                            'entity_name': row.get('entity_name', ''),
                            'created_at': row.get('created_at'),
                            'role_view_level': row.get('role_view_level', 0),
                            **(row.get('metadata', {}) or {})
                        }
                    )
                    matches.append(match)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Record metrics
            increment_counter("vector.fallback.queries", labels={
                "index": "implicate",
                "backend": "pgvector"
            })
            observe_histogram("vector.fallback.latency_ms", elapsed_ms, labels={
                "index": "implicate"
            })
            
            return FallbackQueryResult(
                matches=matches,
                fallback_used=True,
                latency_ms=elapsed_ms,
                source="pgvector"
            )
            
        except Exception as e:
            # Record error
            increment_counter("vector.fallback.errors", labels={
                "index": "implicate",
                "error": type(e).__name__
            })
            
            # Return empty result
            elapsed_ms = (time.time() - start_time) * 1000
            return FallbackQueryResult(
                matches=[],
                fallback_used=True,
                latency_ms=elapsed_ms,
                source="pgvector_error"
            )
    
    def _get_role_rank(self, role: Optional[str]) -> int:
        """Get numeric rank for role."""
        role_ranks = {
            'general': 1,
            'pro': 2,
            'researcher': 2,
            'scholar': 3,
            'analytics': 4,
            'operations': 5
        }
        return role_ranks.get((role or 'general').lower(), 1)
    
    def _format_vector(self, embedding: List[float]) -> str:
        """Format vector for pgvector SQL query."""
        return '[' + ','.join(str(x) for x in embedding) + ']'


# Global fallback adapter instance
_fallback_adapter = None


def get_fallback_adapter() -> PgvectorFallbackAdapter:
    """Get or create fallback adapter singleton."""
    global _fallback_adapter
    if _fallback_adapter is None:
        _fallback_adapter = PgvectorFallbackAdapter()
    return _fallback_adapter


def query_with_fallback(
    embedding: List[float],
    index_type: str,  # "explicate" or "implicate"
    top_k: Optional[int] = None,
    filter: Optional[Dict[str, Any]] = None,
    caller_role: Optional[str] = None,
    force_fallback: bool = False
) -> Tuple[Any, bool, Optional[str]]:
    """
    Query vector store with automatic fallback to pgvector.
    
    Args:
        embedding: Query vector
        index_type: "explicate" or "implicate"
        top_k: Number of results
        filter: Optional metadata filter
        caller_role: Caller role for RBAC
        force_fallback: Force use of fallback (for testing)
        
    Returns:
        Tuple of (result, fallback_used, fallback_reason)
    """
    adapter = get_fallback_adapter()
    
    # Check if fallback should be used
    use_fallback = force_fallback
    fallback_reason = "forced" if force_fallback else None
    
    if not force_fallback:
        should_fallback, reason = adapter.should_use_fallback()
        use_fallback = should_fallback
        fallback_reason = reason
    
    if use_fallback:
        # Use fallback
        if index_type == "explicate":
            result = adapter.query_explicate_fallback(
                embedding=embedding,
                top_k=top_k,
                filter=filter,
                caller_role=caller_role
            )
        else:  # implicate
            result = adapter.query_implicate_fallback(
                embedding=embedding,
                top_k=top_k,
                filter=filter,
                caller_role=caller_role
            )
        
        return (result, True, fallback_reason)
    
    # Use normal Pinecone
    try:
        from app.services.vector_store import VectorStore
        vs = VectorStore()
        
        if index_type == "explicate":
            result = vs.query_explicit(
                embedding=embedding,
                top_k=top_k or 16,
                filter=filter,
                caller_role=caller_role
            )
        else:  # implicate
            result = vs.query_implicate(
                embedding=embedding,
                top_k=top_k or 8,
                filter=filter,
                caller_role=caller_role
            )
        
        return (result, False, None)
        
    except Exception as e:
        # Pinecone failed, fall back to pgvector
        increment_counter("vector.fallback.triggered", labels={
            "reason": "pinecone_error",
            "error": type(e).__name__
        })
        
        if index_type == "explicate":
            result = adapter.query_explicate_fallback(
                embedding=embedding,
                top_k=top_k,
                filter=filter,
                caller_role=caller_role
            )
        else:
            result = adapter.query_implicate_fallback(
                embedding=embedding,
                top_k=top_k,
                filter=filter,
                caller_role=caller_role
            )
        
        return (result, True, f"pinecone_error: {str(e)}")
