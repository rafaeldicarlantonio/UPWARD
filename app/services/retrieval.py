from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    # optional at import time to avoid hard dependency
    from app.services.vector_store import VectorStore
except Exception:  # pragma: no cover - import-safe fallback
    VectorStore = None  # type: ignore


Candidate = Dict[str, Any]


def build_query_expansions(query: str) -> Dict[str, Any]:
    """Return canonical query and placeholder expansions."""
    return {"canonical": query, "expansions": []}


def _embed_stub(text: str, dim: int = 1536) -> List[float]:
    """Temporary embedding stub returning zero vector."""
    return [0.0] * dim


def _apply_role_filter(cands: List[Candidate], role: Optional[str]) -> List[Candidate]:
    """Placeholder role filter; pass-through until auth wired."""
    return cands


def retrieve_dual(expansions: Dict[str, Any], role: Optional[str]) -> List[Candidate]:
    """
    - Embed canonical query (stub)
    - Query explicate/implicate indices
    - Merge, dedupe by id, pass through role filter
    - Return List[Candidate] = {id, kind, score, meta}
    """
    canonical = (expansions or {}).get("canonical") or ""
    emb = _embed_stub(canonical)

    vs = VectorStore() if VectorStore else None
    explicit_matches = []
    implicate_matches = []

    if vs:
        try:
            r1 = vs.query_explicit(emb, top_k=12, filter=None, caller_role=role)
            explicit_matches = getattr(r1, "matches", r1.get("matches") if isinstance(r1, dict) else []) or []
        except Exception:
            explicit_matches = []
        try:
            r2 = vs.query_implicate(emb, top_k=12, filter=None, caller_role=role)
            implicate_matches = getattr(r2, "matches", r2.get("matches") if isinstance(r2, dict) else []) or []
        except Exception:
            implicate_matches = []

    # normalize to Candidate
    out: List[Candidate] = []
    def to_cand(m, kind: str) -> Candidate:
        md = getattr(m, "metadata", None) if not isinstance(m, dict) else m.get("metadata")
        return {
            "id": getattr(m, "id", None) if not isinstance(m, dict) else m.get("id"),
            "kind": kind,
            "score": getattr(m, "score", 0.0) if not isinstance(m, dict) else m.get("score", 0.0),
            "meta": md or {},
        }

    for m in explicit_matches:
        out.append(to_cand(m, "explicit"))
    for m in implicate_matches:
        out.append(to_cand(m, "implicate"))

    # dedupe by id keeping max score
    by_id: Dict[str, Candidate] = {}
    for c in out:
        cid = c.get("id")
        if not cid:
            continue
        prev = by_id.get(cid)
        if not prev or float(c.get("score", 0)) > float(prev.get("score", 0)):
            by_id[cid] = c

    merged = list(by_id.values())
    merged = _apply_role_filter(merged, role)
    return merged


def score_lift(candidates: List[Candidate]) -> List[Candidate]:
    """Placeholder: return candidates unchanged."""
    return candidates
