# router/ingest.py
import os
import time
import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from vendors.supabase_client import get_client
from vendors.pinecone_client import get_index
from ingest.pipeline import (
    upsert_memories_from_chunks, 
    normalize_text,
    analyze_chunk,
    AnalysisContext,
    AnalysisLimits,
)
from ingest.commit import commit_analysis
from auth.light_identity import ensure_user
from feature_flags import get_feature_flag
from config import load_config
from core.metrics import IngestMetrics

logger = logging.getLogger(__name__)

router = APIRouter()

class IngestItem(BaseModel):
    title: Optional[str] = None
    text: str = Field(..., description="Normalized plain text")
    type: str = Field("semantic", pattern="^(semantic|episodic|procedural)$")
    tags: Optional[List[str]] = None
    source: Optional[str] = "upload"
    role_view: Optional[List[str]] = None
    file_id: Optional[str] = None

class IngestBatchRequest(BaseModel):
    items: List[IngestItem]
    dedupe: bool = True

class IngestBatchResponse(BaseModel):
    upserted: List[Dict[str, Any]]
    updated: List[Dict[str, Any]]
    skipped: List[Dict[str, Any]]

def _auth(x_api_key: Optional[str]):
    expected = os.getenv("X_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

@router.post("/ingest/batch", response_model=IngestBatchResponse)
def ingest_batch_ingest_batch_post(body: IngestBatchRequest, x_api_key: Optional[str] = Header(None), x_user_email: Optional[str] = Header(None),):
    _auth(x_api_key)
    sb = get_client()
    author_user_id = ensure_user(sb=sb, email=x_user_email)
    index = get_index()

    # simple size guard to avoid huge single calls
    MAX_ITEMS = int(os.getenv("INGEST_MAX_ITEMS", "50"))
    if len(body.items) > MAX_ITEMS:
        raise HTTPException(status_code=400, detail=f"Too many items; max {MAX_ITEMS}")

    by_type: Dict[str, List[str]] = {"semantic": [], "episodic": [], "procedural": []}
    titles_by_type: Dict[str, List[str]] = {"semantic": [], "episodic": [], "procedural": []}
    tags, role_view, source, file_id = [], [], "upload", None

    for it in body.items:
        t = normalize_text(it.text)
        if not t:
            continue
        by_type[it.type].append(t)
        titles_by_type[it.type].append(it.title or "Untitled")
        tags = it.tags or tags
        role_view = it.role_view or role_view
        source = it.source or source
        file_id = it.file_id or file_id

    all_upserted: List[Dict[str, Any]] = []
    all_updated: List[Dict[str, Any]] = []
    all_skipped: List[Dict[str, Any]] = []
    
    # Check if analysis is enabled
    analysis_enabled = get_feature_flag("ingest.analysis.enabled", False)
    
    # Load analysis limits from config
    if analysis_enabled:
        try:
            config = load_config()
            max_ms_per_chunk = config.get("INGEST_ANALYSIS_MAX_MS_PER_CHUNK", 40)
            max_verbs = config.get("INGEST_ANALYSIS_MAX_VERBS", 20)
            max_frames = config.get("INGEST_ANALYSIS_MAX_FRAMES", 10)
            max_concepts = config.get("INGEST_ANALYSIS_MAX_CONCEPTS", 10)
        except Exception as e:
            logger.warning(f"Failed to load analysis config, using defaults: {e}")
            max_ms_per_chunk = 40
            max_verbs = 20
            max_frames = 10
            max_concepts = 10

    for ttype, texts in by_type.items():
        if not texts:
            continue
        resp = upsert_memories_from_chunks(
            sb=sb,
            pinecone_index=index,
            embedder=None,
            file_id=file_id,
            title_prefix=", ".join(titles_by_type[ttype][:2])[:80] or "Batch",
            chunks=texts,
            mem_type=ttype,
            tags=tags,
            role_view=role_view,
            source=source,
            text_col_env=os.getenv("MEMORIES_TEXT_COLUMN", "text"),
            author_user_id=author_user_id,
        )
        all_upserted.extend(resp.get("upserted", []))
        all_updated.extend(resp.get("updated", []))
        all_skipped.extend(resp.get("skipped", []))
        
        # If analysis is enabled, analyze and commit each successfully upserted chunk
        if analysis_enabled:
            for item in resp.get("upserted", []):
                chunk_idx = item.get("idx")
                memory_id = item.get("memory_id")
                
                if chunk_idx is not None and memory_id and chunk_idx < len(texts):
                    chunk_text = texts[chunk_idx]
                    
                    # Perform analysis with timeout
                    analysis_start = time.perf_counter()
                    try:
                        analysis = analyze_chunk(
                            chunk_text,
                            ctx=AnalysisContext(backend=None),
                            limits=AnalysisLimits(
                                max_ms_per_chunk=max_ms_per_chunk,
                                max_verbs=max_verbs,
                                max_frames=max_frames,
                                max_concepts=max_concepts,
                            ),
                        )
                        analysis_elapsed_ms = (time.perf_counter() - analysis_start) * 1000
                        
                        # Check if we exceeded timeout
                        if analysis_elapsed_ms > max_ms_per_chunk:
                            logger.warning(
                                f"Analysis timeout exceeded for chunk {chunk_idx} "
                                f"(file_id={file_id}, memory_id={memory_id}): "
                                f"{analysis_elapsed_ms:.1f}ms > {max_ms_per_chunk}ms"
                            )
                            # Record timeout metric
                            IngestMetrics.record_timeout()
                            
                            all_skipped.append({
                                "idx": chunk_idx,
                                "reason": "analysis_timeout",
                                "elapsed_ms": analysis_elapsed_ms,
                                "max_ms": max_ms_per_chunk,
                            })
                            continue
                        
                        # Record successful analysis metrics
                        IngestMetrics.record_chunk_analyzed(
                            verbs_count=len(analysis.predicates),
                            frames_count=len(analysis.frames),
                            concepts_count=len(analysis.concepts),
                            contradictions_count=len(analysis.contradictions),
                            duration_ms=analysis_elapsed_ms,
                            success=True
                        )
                        
                        # Commit analysis results
                        commit_result = commit_analysis(
                            sb,
                            analysis,
                            memory_id=memory_id,
                            file_id=file_id,
                            chunk_idx=chunk_idx,
                        )
                        
                        # Record commit metrics
                        IngestMetrics.record_entities_created(
                            concepts_count=len(commit_result.concept_entity_ids),
                            frames_count=len(commit_result.frame_entity_ids),
                            edges_count=len(commit_result.edge_ids)
                        )
                        
                        # Log any commit errors
                        if commit_result.errors:
                            logger.warning(
                                f"Commit errors for chunk {chunk_idx} "
                                f"(memory_id={memory_id}): {commit_result.errors}"
                            )
                            IngestMetrics.record_commit_errors(len(commit_result.errors))
                        
                        logger.info(
                            f"Analyzed and committed chunk {chunk_idx}: "
                            f"{len(commit_result.concept_entity_ids)} concepts, "
                            f"{len(commit_result.frame_entity_ids)} frames, "
                            f"{len(commit_result.edge_ids)} edges "
                            f"in {analysis_elapsed_ms:.1f}ms"
                        )
                    
                    except Exception as e:
                        logger.error(
                            f"Analysis failed for chunk {chunk_idx} "
                            f"(file_id={file_id}, memory_id={memory_id}): {e}",
                            exc_info=True
                        )
                        # Record error metric
                        IngestMetrics.record_analysis_error(type(e).__name__)
                        
                        all_skipped.append({
                            "idx": chunk_idx,
                            "reason": "analysis_error",
                            "error": str(e),
                        })

    return {"upserted": all_upserted, "updated": all_updated, "skipped": all_skipped}
