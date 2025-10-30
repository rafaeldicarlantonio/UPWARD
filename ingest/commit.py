# ingest/commit.py — commit phase for analyzed chunks

import os
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from vendors.supabase_client import get_client
from ingest.pipeline import AnalysisResult
from feature_flags import get_feature_flag
from core.metrics import ImplicateRefreshMetrics
from core.policy import get_ingest_policy_manager, IngestPolicy


@dataclass
class CommitResult:
    """Results from committing analysis."""
    concept_entity_ids: List[str]
    frame_entity_ids: List[str]
    edge_ids: List[str]
    memory_id: Optional[str] = None
    jobs_enqueued: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def slugify(text: str) -> str:
    """
    Convert text to a stable slug suitable for IDs.
    
    Args:
        text: Text to slugify
    
    Returns:
        Slugified text (lowercase, alphanumeric + hyphens)
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)
    # Remove non-alphanumeric characters except hyphens
    text = re.sub(r'[^a-z0-9-]', '', text)
    # Remove consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Strip hyphens from start and end
    text = text.strip('-')
    # Limit length
    return text[:64]


def upsert_concept_entity(sb, name: str, stable_id: Optional[str] = None) -> Optional[str]:
    """
    Upsert a concept entity with stable ID and return its ID.
    
    For idempotency, we use stable_id (e.g., 'concept:machine-learning') if provided.
    If the entity already exists with this ID, we return it; otherwise we create it.
    
    Args:
        sb: Supabase client
        name: Entity name
        stable_id: Optional stable UUID-compatible ID for idempotency
    
    Returns:
        Entity ID or None on error
    """
    try:
        # Check if entity exists by name+type (unique constraint)
        sel = sb.table("entities").select("id").eq("name", name).eq("type", "concept").limit(1).execute()
        rows = sel.data if hasattr(sel, "data") else sel.get("data")
        if rows:
            return rows[0]["id"]
        
        # Insert new entity (with stable_id if provided)
        payload = {"name": name, "type": "concept"}
        if stable_id:
            # Note: Supabase/PostgreSQL will auto-generate UUID if not provided
            # For true idempotency, you'd need to use stable_id as the primary key
            # But the unique constraint on (name, type) provides idempotency
            pass
        
        ins = sb.table("entities").insert(payload).execute()
        data = ins.data if hasattr(ins, "data") else ins.get("data")
        if data and len(data) > 0:
            return data[0]["id"]
        
        # Fallback: select again (handles race condition)
        sel2 = sb.table("entities").select("id").eq("name", name).eq("type", "concept").limit(1).execute()
        rows2 = sel2.data if hasattr(sel2, "data") else sel2.get("data")
        return rows2[0]["id"] if rows2 else None
    except Exception as e:
        # Likely duplicate key violation - try to fetch existing
        try:
            sel3 = sb.table("entities").select("id").eq("name", name).eq("type", "concept").limit(1).execute()
            rows3 = sel3.data if hasattr(sel3, "data") else sel3.get("data")
            return rows3[0]["id"] if rows3 else None
        except Exception:
            return None


def upsert_frame_entity(sb, frame_id: str, frame_type: str, file_id: Optional[str] = None, chunk_idx: Optional[int] = None) -> Optional[str]:
    """
    Upsert a frame entity (stored as artifact type) with stable naming and return its ID.
    
    For idempotency, we create stable entity names like:
    - frame:{file_id}:{chunk_idx}:{frame_id} (if file_id and chunk_idx provided)
    - frame:{frame_type}:{frame_id} (fallback)
    
    Args:
        sb: Supabase client
        frame_id: Frame identifier (e.g., 'frame-1')
        frame_type: Frame type (e.g., 'transfer', 'causation', 'measurement', 'claim')
        file_id: Optional file ID for stable naming
        chunk_idx: Optional chunk index for stable naming
    
    Returns:
        Entity ID or None on error
    """
    try:
        # Create stable entity name for idempotency
        if file_id and chunk_idx is not None:
            entity_name = f"frame:{slugify(file_id)}:{chunk_idx}:{frame_id}"
        else:
            entity_name = f"frame:{frame_type}:{frame_id}"
        
        # Check if entity exists
        sel = sb.table("entities").select("id").eq("name", entity_name).eq("type", "artifact").limit(1).execute()
        rows = sel.data if hasattr(sel, "data") else sel.get("data")
        if rows:
            return rows[0]["id"]
        
        # Insert new entity
        ins = sb.table("entities").insert({"name": entity_name, "type": "artifact"}).execute()
        data = ins.data if hasattr(ins, "data") else ins.get("data")
        if data and len(data) > 0:
            return data[0]["id"]
        
        # Fallback: select again (handles race condition)
        sel2 = sb.table("entities").select("id").eq("name", entity_name).eq("type", "artifact").limit(1).execute()
        rows2 = sel2.data if hasattr(sel2, "data") else sel2.get("data")
        return rows2[0]["id"] if rows2 else None
    except Exception as e:
        # Likely duplicate key violation - try to fetch existing
        try:
            sel3 = sb.table("entities").select("id").eq("name", entity_name).eq("type", "artifact").limit(1).execute()
            rows3 = sel3.data if hasattr(sel3, "data") else sel3.get("data")
            return rows3[0]["id"] if rows3 else None
        except Exception:
            return None


def create_entity_edge(sb, from_id: str, to_id: str, rel_type: str, weight: float = 1.0, meta: Optional[Dict] = None) -> Optional[str]:
    """
    Create an entity edge (idempotent - checks for existing edge first).
    
    Args:
        sb: Supabase client
        from_id: Source entity ID
        to_id: Target entity ID
        rel_type: Relationship type (supports, contradicts, evidence_of, etc.)
        weight: Edge weight (default 1.0)
        meta: Optional metadata
    
    Returns:
        Edge ID or None on error
    """
    try:
        meta = meta or {}
        
        # Check if edge already exists (for idempotency)
        sel = (
            sb.table("entity_edges")
            .select("id")
            .eq("from_id", from_id)
            .eq("to_id", to_id)
            .eq("rel_type", rel_type)
            .limit(1)
            .execute()
        )
        rows = sel.data if hasattr(sel, "data") else sel.get("data")
        if rows:
            # Edge already exists, return its ID
            return rows[0]["id"]
        
        # Insert new edge
        payload = {
            "from_id": from_id,
            "to_id": to_id,
            "rel_type": rel_type,
            "weight": weight,
            "meta": meta,
        }
        ins = sb.table("entity_edges").insert(payload).execute()
        data = ins.data if hasattr(ins, "data") else ins.get("data")
        if data and len(data) > 0:
            return data[0]["id"]
        
        # Fallback: select again (handles race condition)
        sel2 = (
            sb.table("entity_edges")
            .select("id")
            .eq("from_id", from_id)
            .eq("to_id", to_id)
            .eq("rel_type", rel_type)
            .limit(1)
            .execute()
        )
        rows2 = sel2.data if hasattr(sel2, "data") else sel2.get("data")
        return rows2[0]["id"] if rows2 else None
    except Exception as e:
        # Likely duplicate - try to fetch existing
        try:
            sel3 = (
                sb.table("entity_edges")
                .select("id")
                .eq("from_id", from_id)
                .eq("to_id", to_id)
                .eq("rel_type", rel_type)
                .limit(1)
                .execute()
            )
            rows3 = sel3.data if hasattr(sel3, "data") else sel3.get("data")
            return rows3[0]["id"] if rows3 else None
        except Exception:
            return None


def update_memory_contradictions(sb, memory_id: str, contradictions: List[Dict[str, Any]]) -> bool:
    """
    Update the contradictions field in the memory row.
    
    Args:
        sb: Supabase client
        memory_id: Memory ID
        contradictions: List of contradiction dicts
    
    Returns:
        True on success, False on error
    """
    try:
        # Serialize contradictions to JSON-compatible format
        contradictions_json = [
            {
                "subject_entity_id": c.get("subject_entity_id"),
                "subject_text": c.get("subject_text", ""),
                "claim_a": c.get("claim_a", ""),
                "claim_b": c.get("claim_b", ""),
                "evidence_ids": list(c.get("evidence_ids", [])),
            }
            for c in contradictions
        ]
        
        sb.table("memories").update({"contradictions": contradictions_json}).eq("id", memory_id).execute()
        return True
    except Exception as e:
        return False


def enqueue_implicate_refresh(sb, entity_ids: List[str]) -> int:
    """
    Enqueue implicate_refresh jobs for the given entity IDs.
    
    Uses the QueueAdapter to enqueue jobs. Entity IDs are batched together
    in a single job for efficiency.
    
    Args:
        sb: Supabase client
        entity_ids: List of entity IDs to refresh
    
    Returns:
        Number of jobs enqueued (1 if successful, 0 if not)
    """
    # Check if the feature flag is enabled
    if not get_feature_flag("ingest.implicate.refresh_enabled", False):
        return 0
    
    if not entity_ids:
        return 0
    
    try:
        from adapters.queue import QueueAdapter
        
        queue = QueueAdapter(sb=sb)
        
        # Enqueue a single job with all entity IDs
        # This is more efficient than creating individual jobs
        job_id = queue.enqueue(
            job_type="implicate_refresh",
            payload={"entity_ids": entity_ids},
            max_retries=3,
        )
        
        # Record enqueue metric
        if job_id:
            ImplicateRefreshMetrics.record_job_enqueued(len(entity_ids))
        
        return 1 if job_id else 0
        
    except Exception as e:
        # Log the error but don't fail the commit
        print(f"Failed to enqueue implicate_refresh job: {e}")
        return 0


def commit_analysis(
    sb,
    analysis: AnalysisResult,
    memory_id: Optional[str] = None,
    file_id: Optional[str] = None,
    chunk_idx: Optional[int] = None,
    user_roles: Optional[List[str]] = None,
) -> CommitResult:
    """
    Commit analysis results to the database (idempotent) with policy enforcement.
    
    This function:
    1. Applies role-based policy caps and tolerances
    2. Upserts concept entities with stable slugified names
    3. Upserts frame entities (as artifact type) with stable names
    4. Creates entity_edges (idempotent):
       - frames evidence_of concepts
       - supports/contradicts edges between entities
    5. Updates memory contradictions (based on policy)
    6. Enqueues implicate_refresh jobs (if flag is enabled)
    
    Args:
        sb: Supabase client
        analysis: AnalysisResult from analyze_chunk
        memory_id: Optional memory ID to update contradictions
        file_id: Optional file ID for stable frame naming
        chunk_idx: Optional chunk index for stable frame naming
        user_roles: List of user roles for policy enforcement
    
    Returns:
        CommitResult with entity IDs, edge IDs, and job counts
    """
    result = CommitResult(
        concept_entity_ids=[],
        frame_entity_ids=[],
        edge_ids=[],
        memory_id=memory_id,
        jobs_enqueued=0,
        errors=[],
    )
    
    # Get and enforce policy
    policy_manager = get_ingest_policy_manager()
    policy = policy_manager.get_policy(user_roles)
    
    # Enforce caps on analysis results
    enforced = policy_manager.enforce_caps(
        concepts=analysis.concepts,
        frames=analysis.frames,
        contradictions=analysis.contradictions,
        policy=policy
    )
    
    # Use the capped/filtered results
    capped_concepts = enforced["concepts"]
    capped_frames = enforced["frames"]
    filtered_contradictions = enforced["contradictions"]
    
    # Log policy application
    print(f"Policy applied (role={policy.role}): {enforced['caps_applied']}")
    
    # 1. Upsert concept entities with stable IDs (using capped list)
    concept_name_to_id: Dict[str, str] = {}
    for concept in capped_concepts:
        concept_name = concept.get("name", "")
        if not concept_name:
            continue
        
        # Create stable ID for idempotency
        stable_id = f"concept:{slugify(concept_name)}"
        entity_id = upsert_concept_entity(sb, concept_name, stable_id=stable_id)
        if entity_id:
            result.concept_entity_ids.append(entity_id)
            concept_name_to_id[concept_name] = entity_id
        else:
            result.errors.append(f"Failed to upsert concept: {concept_name}")
    
    # 2. Upsert frame entities with stable naming (using capped and filtered list)
    frame_id_to_entity_id: Dict[str, str] = {}
    for frame in capped_frames:
        frame_entity_id = upsert_frame_entity(
            sb, 
            frame.frame_id, 
            frame.type,
            file_id=file_id,
            chunk_idx=chunk_idx,
        )
        if frame_entity_id:
            result.frame_entity_ids.append(frame_entity_id)
            frame_id_to_entity_id[frame.frame_id] = frame_entity_id
        else:
            result.errors.append(f"Failed to upsert frame: {frame.frame_id}")
    
    # 3. Create entity_edges
    # 3a. Frames evidence_of concepts (based on frame roles, using capped frames)
    for frame in capped_frames:
        frame_entity_id = frame_id_to_entity_id.get(frame.frame_id)
        if not frame_entity_id:
            continue
        
        # Link frame to concepts mentioned in roles
        for role_name, role_value in frame.roles.items():
            if role_value and isinstance(role_value, str):
                # Check if this role value matches a concept we created
                for concept_name, concept_id in concept_name_to_id.items():
                    if concept_name.lower() in role_value.lower() or role_value.lower() in concept_name.lower():
                        edge_id = create_entity_edge(
                            sb,
                            from_id=frame_entity_id,
                            to_id=concept_id,
                            rel_type="evidence_of",
                            weight=1.0,
                            meta={"role": role_name},
                        )
                        if edge_id:
                            result.edge_ids.append(edge_id)
    
    # 3b. Supports/contradicts edges between entities from predicates
    # Map subject/object entities to concept IDs
    for predicate in analysis.predicates:
        subject = predicate.subject_entity
        obj = predicate.object_entity
        
        # Find matching concept IDs
        subject_id = None
        object_id = None
        
        if subject:
            for concept_name, concept_id in concept_name_to_id.items():
                if concept_name.lower() in subject.lower() or subject.lower() in concept_name.lower():
                    subject_id = concept_id
                    break
        
        if obj:
            for concept_name, concept_id in concept_name_to_id.items():
                if concept_name.lower() in obj.lower() or obj.lower() in concept_name.lower():
                    object_id = concept_id
                    break
        
        # Create edges based on polarity
        if subject_id and object_id:
            rel_type = "supports" if predicate.polarity == "positive" else "contradicts"
            edge_id = create_entity_edge(
                sb,
                from_id=subject_id,
                to_id=object_id,
                rel_type=rel_type,
                weight=1.0,
                meta={"verb": predicate.verb_lemma},
            )
            if edge_id:
                result.edge_ids.append(edge_id)
    
    # 4. Update memory contradictions (using filtered contradictions based on policy)
    if memory_id and filtered_contradictions:
        contradictions_dicts = [
            {
                "subject_entity_id": c.subject_entity_id if hasattr(c, 'subject_entity_id') else c.get("subject_entity_id"),
                "subject_text": c.subject_text if hasattr(c, 'subject_text') else c.get("subject_text", ""),
                "claim_a": c.claim_a if hasattr(c, 'claim_a') else c.get("claim_a", ""),
                "claim_b": c.claim_b if hasattr(c, 'claim_b') else c.get("claim_b", ""),
                "evidence_ids": list(c.evidence_ids) if hasattr(c, 'evidence_ids') else list(c.get("evidence_ids", [])),
            }
            for c in filtered_contradictions
        ]
        
        if not update_memory_contradictions(sb, memory_id, contradictions_dicts):
            result.errors.append(f"Failed to update contradictions for memory: {memory_id}")
    
    # 5. Enqueue implicate_refresh jobs
    all_entity_ids = result.concept_entity_ids + result.frame_entity_ids
    if all_entity_ids:
        result.jobs_enqueued = enqueue_implicate_refresh(sb, all_entity_ids)
    
    return result
