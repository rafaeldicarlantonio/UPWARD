from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel

from vendors.pinecone_client import get_index as _legacy_get_index
from app.settings import get_settings


_ROLE_RANK = {"general": 1, "pro": 2, "scholar": 3, "analytics": 4, "operations": 5}


def _role_rank(role: Optional[str]) -> int:
    return _ROLE_RANK.get((role or "general").lower(), 1)


class VectorStore:
    """
    Thin wrapper around Pinecone for explicate/implicate indices with simple retry.
    """

    def __init__(self) -> None:
        s = get_settings()
        # lazily resolve index names; actual client/Index objects will be created on first use
        self._explicate_name: Optional[str] = s.PINECONE_EXPLICATE_INDEX
        self._implicate_name: Optional[str] = s.PINECONE_IMPLICATE_INDEX
        self._explicate = None
        self._implicate = None

    # ---- client helpers ----
    def _get_explicate(self):
        if self._explicate is None:
            # reuse existing vendor factory which caches a default Index; if names differ, create explicit Index
            idx = _legacy_get_index()
            if self._explicate_name and getattr(idx, "_name", None) != self._explicate_name:
                # construct an Index from the underlying client
                pc = getattr(idx, "_pc_singleton", None) or getattr(idx, "_pinecone", None)
                self._explicate = pc.Index(self._explicate_name) if pc else idx
            else:
                self._explicate = idx
        return self._explicate

    def _get_implicate(self):
        if self._implicate is None:
            idx = _legacy_get_index()
            if self._implicate_name and getattr(idx, "_name", None) != self._implicate_name:
                pc = getattr(idx, "_pc_singleton", None) or getattr(idx, "_pinecone", None)
                self._implicate = pc.Index(self._implicate_name) if pc else idx
            else:
                self._implicate = idx
        return self._implicate

    # ---- retry decorator ----
    @staticmethod
    def _retryable():
        return retry(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type(Exception),
        )

    # ---- filter helper ----
    @staticmethod
    def _role_filter(base: Optional[Dict[str, Any]], caller_role: Optional[str]) -> Dict[str, Any]:
        """
        Enforce role_view rank: allow records where min(role_view_rank) <= caller_rank.
        Implementation assumes metadata contains either:
          - role_rank: number
          - or role_view: list[str] from which we compute a max rank and compare.
        """
        rank = _role_rank(caller_role)
        base = dict(base or {})
        # Prefer explicit numeric rank if present, else derive from role_view strings
        role_cond = {"role_rank": {"$lte": rank}}
        return {"$and": [base, role_cond]} if base else role_cond

    # ---- queries ----
    def query_explicit(self, embedding: List[float], top_k: int = 12, filter: Optional[Dict[str, Any]] = None, caller_role: Optional[str] = None):
        idx = self._get_explicate()
        f = self._role_filter(filter, caller_role)
        return self._query(idx, embedding, top_k, f, namespace=None)

    def query_implicate(self, embedding: List[float], top_k: int = 12, filter: Optional[Dict[str, Any]] = None, caller_role: Optional[str] = None):
        idx = self._get_implicate()
        f = self._role_filter(filter, caller_role)
        return self._query(idx, embedding, top_k, f, namespace=None)

    # ---- upserts ----
    def upsert_explicit(self, id: str, vector: List[float], metadata: Dict[str, Any], namespace: Optional[str] = None):
        idx = self._get_explicate()
        return self._upsert(idx, id, vector, metadata, namespace)

    def upsert_implicate(self, id: str, vector: List[float], metadata: Dict[str, Any], namespace: Optional[str] = None):
        idx = self._get_implicate()
        return self._upsert(idx, id, vector, metadata, namespace)

    # ---- low-level ops (with retry) ----
    @_retryable.__func__()
    def _query(self, index, embedding: List[float], top_k: int, filter: Optional[Dict[str, Any]], namespace: Optional[str]):
        return index.query(vector=embedding, top_k=top_k, include_metadata=True, filter=filter, namespace=namespace)

    @_retryable.__func__()
    def _upsert(self, index, id: str, vector: List[float], metadata: Dict[str, Any], namespace: Optional[str]):
        return index.upsert(vectors=[{"id": id, "values": vector, "metadata": metadata}], namespace=namespace)

    # ---- async queries ----
    async def query_explicit_async(
        self, 
        embedding: List[float], 
        top_k: int = 12, 
        filter: Optional[Dict[str, Any]] = None, 
        caller_role: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """Async version of query_explicit with optional timeout.
        
        Args:
            embedding: Query vector
            top_k: Number of results
            filter: Optional metadata filter
            caller_role: Caller role for RBAC
            timeout: Optional timeout in seconds
            
        Returns:
            Query results
            
        Raises:
            asyncio.TimeoutError: If query exceeds timeout
        """
        idx = self._get_explicate()
        f = self._role_filter(filter, caller_role)
        
        # Run sync query in executor to avoid blocking
        loop = asyncio.get_event_loop()
        query_coro = loop.run_in_executor(
            None,
            lambda: self._query(idx, embedding, top_k, f, namespace=None)
        )
        
        if timeout:
            return await asyncio.wait_for(query_coro, timeout=timeout)
        else:
            return await query_coro

    async def query_implicate_async(
        self, 
        embedding: List[float], 
        top_k: int = 12, 
        filter: Optional[Dict[str, Any]] = None, 
        caller_role: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """Async version of query_implicate with optional timeout.
        
        Args:
            embedding: Query vector
            top_k: Number of results
            filter: Optional metadata filter
            caller_role: Caller role for RBAC
            timeout: Optional timeout in seconds
            
        Returns:
            Query results
            
        Raises:
            asyncio.TimeoutError: If query exceeds timeout
        """
        idx = self._get_implicate()
        f = self._role_filter(filter, caller_role)
        
        # Run sync query in executor to avoid blocking
        loop = asyncio.get_event_loop()
        query_coro = loop.run_in_executor(
            None,
            lambda: self._query(idx, embedding, top_k, f, namespace=None)
        )
        
        if timeout:
            return await asyncio.wait_for(query_coro, timeout=timeout)
        else:
            return await query_coro


# Smoke test (manual)
# from app.services.vector_store import VectorStore
# vs = VectorStore()
# emb = [0.0]*1536
# r1 = vs.query_explicit(emb, top_k=5, filter={"type": {"$eq": "semantic"}}, caller_role="general")
# r2 = vs.query_implicate(emb, top_k=5, filter=None, caller_role="pro")
# vs.upsert_explicit("test-id", emb, {"type": "semantic", "role_rank": 1})
# vs.upsert_implicate("test-id2", emb, {"type": "semantic", "role_rank": 2})
