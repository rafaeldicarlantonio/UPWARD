# ingest/commit.py — commit phase for analyzed chunks

import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from vendors.supabase_client import get_client
from ingest.pipeline import AnalysisResult
from feature_flags import get_feature_flag


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


def upsert_concept_entity(sb, name: str) -> Optional[str]:
    """
    Upsert a concept entity and return its ID.
    
    Args:
        sb: Supabase client
        name: Entity name
    
    Returns:
        Entity ID or None on error
    """
    try:
        # Check if entity exists
        sel = sb.table("entities").select("id").eq("name", name).eq("type", "concept").limit(1).execute()
        rows = sel.data if hasattr(sel, "data") else sel.get("data")
        if rows:
            return rows[0]["id"]
        
        # Insert new entity
        ins = sb.table("entities").insert({"name": name, "type": "concept"}).execute()
        data = ins.data if hasattr(ins, "data") else ins.get("data")
        if data and len(data) > 0:
            return data[0]["id"]
        
        # Fallback: select again
        sel2 = sb.table("entities").select("id").eq("name", name).eq("type", "concept").limit(1).execute()
        rows2 = sel2.data if hasattr(sel2, "data") else sel2.get("data")
        return rows2[0]["id"] if rows2 else None
    except Exception as e:
        return None


def upsert_frame_entity(sb, frame_id: str, frame_type: str) -> Optional[str]:
    """
    Upsert a frame entity (stored as artifact type) and return its ID.
    
    Args:
        sb: Supabase client
        frame_id: Frame identifier (e.g., 'frame-1')
        frame_type: Frame type (e.g., 'transfer', 'causation', 'measurement', 'claim')
    
    Returns:
        Entity ID or None on error
    """
    try:
        # Use frame_id as the entity name for uniqueness
        entity_name = f"{frame_type}_{frame_id}"
        
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
        
        # Fallback: select again
        sel2 = sb.table("entities").select("id").eq("name", entity_name).eq("type", "artifact").limit(1).execute()
        rows2 = sel2.data if hasattr(sel2, "data") else sel2.get("data")
        return rows2[0]["id"] if rows2 else None
    except Exception as e:
        return None


def create_entity_edge(sb, from_id: str, to_id: str, rel_type: str, weight: float = 1.0, meta: Optional[Dict] = None) -> Optional[str]:
    """
    Create an entity edge.
    
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
        return None
    except Exception as e:
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
    
    Note: This is a placeholder implementation. In a production system,
    you would use a proper job queue (e.g., Celery, RQ, or a database-backed queue).
    For now, we'll store job requests in a simple JSONB column or a dedicated table.
    
    Args:
        sb: Supabase client
        entity_ids: List of entity IDs to refresh
    
    Returns:
        Number of jobs enqueued
    """
    # Check if the feature flag is enabled
    if not get_feature_flag("ingest.implicate.refresh_enabled", False):
        return 0
    
    try:
        # For now, we'll create a simple job record in a 'jobs' table
        # If the table doesn't exist, we'll fail silently
        # In production, you'd have a proper job queue table
        count = 0
        for entity_id in entity_ids:
            try:
                job_payload = {
                    "job_type": "implicate_refresh",
                    "entity_id": entity_id,
                    "status": "pending",
                    "created_at": "now()",
                }
                # Try to insert into jobs table (may not exist in test/dev)
                # If it doesn't exist, we'll just skip it
                sb.table("jobs").insert(job_payload).execute()
                count += 1
            except Exception:
                # Table might not exist, continue
                pass
        return count
    except Exception:
        return 0


def commit_analysis(
    sb,
    analysis: AnalysisResult,
    memory_id: Optional[str] = None,
) -> CommitResult:
    """
    Commit analysis results to the database.
    
    This function:
    1. Upserts concept entities
    2. Upserts frame entities (as artifact type)
    3. Creates entity_edges:
       - frames evidence_of concepts
       - supports/contradicts edges between entities
    4. Updates memory contradictions
    5. Enqueues implicate_refresh jobs (if flag is enabled)
    
    Args:
        sb: Supabase client
        analysis: AnalysisResult from analyze_chunk
        memory_id: Optional memory ID to update contradictions
    
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
    
    # 1. Upsert concept entities
    concept_name_to_id: Dict[str, str] = {}
    for concept in analysis.concepts:
        concept_name = concept.get("name", "")
        if not concept_name:
            continue
        
        entity_id = upsert_concept_entity(sb, concept_name)
        if entity_id:
            result.concept_entity_ids.append(entity_id)
            concept_name_to_id[concept_name] = entity_id
        else:
            result.errors.append(f"Failed to upsert concept: {concept_name}")
    
    # 2. Upsert frame entities
    frame_id_to_entity_id: Dict[str, str] = {}
    for frame in analysis.frames:
        frame_entity_id = upsert_frame_entity(sb, frame.frame_id, frame.type)
        if frame_entity_id:
            result.frame_entity_ids.append(frame_entity_id)
            frame_id_to_entity_id[frame.frame_id] = frame_entity_id
        else:
            result.errors.append(f"Failed to upsert frame: {frame.frame_id}")
    
    # 3. Create entity_edges
    # 3a. Frames evidence_of concepts (based on frame roles)
    for frame in analysis.frames:
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
    
    # 4. Update memory contradictions
    if memory_id and analysis.contradictions:
        contradictions_dicts = [
            {
                "subject_entity_id": c.subject_entity_id,
                "subject_text": c.subject_text,
                "claim_a": c.claim_a,
                "claim_b": c.claim_b,
                "evidence_ids": list(c.evidence_ids),
            }
            for c in analysis.contradictions
        ]
        
        if not update_memory_contradictions(sb, memory_id, contradictions_dicts):
            result.errors.append(f"Failed to update contradictions for memory: {memory_id}")
    
    # 5. Enqueue implicate_refresh jobs
    all_entity_ids = result.concept_entity_ids + result.frame_entity_ids
    if all_entity_ids:
        result.jobs_enqueued = enqueue_implicate_refresh(sb, all_entity_ids)
    
    return result
