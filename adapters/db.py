# adapters/db.py — database operations for implicate index building

import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from vendors.supabase_client import get_client

@dataclass
class Entity:
    id: str
    name: str
    type: str
    canonical: bool
    created_at: str

@dataclass
class EntityEdge:
    id: str
    from_id: str
    to_id: str
    rel_type: str
    weight: float
    meta: Dict[str, Any]
    created_at: str

@dataclass
class Memory:
    id: str
    type: str
    title: Optional[str]
    content: str
    summary: Optional[str]
    importance: int
    meta: Dict[str, Any]
    created_at: str

@dataclass
class EntityMention:
    entity_id: str
    memory_id: str
    weight: float

class DatabaseAdapter:
    """Database operations for implicate index building."""
    
    def __init__(self):
        self.client = get_client()
    
    def get_concept_entities(self, limit: Optional[int] = None) -> List[Entity]:
        """Get all entities of type 'concept'."""
        query = self.client.table("entities").select("*").eq("type", "concept")
        if limit:
            query = query.limit(limit)
        
        result = query.execute()
        return [Entity(**row) for row in result.data]
    
    def get_entities_by_ids(self, entity_ids: List[str]) -> List[Entity]:
        """Get entities by their IDs."""
        if not entity_ids:
            return []
        
        result = self.client.table("entities").select("*").in_("id", entity_ids).execute()
        return [Entity(**row) for row in result.data]
    
    def get_entity_in_degree(self, entity_id: str) -> int:
        """Get the in-degree (number of incoming edges) for an entity."""
        result = self.client.table("entity_edges").select("id", count="exact").eq("to_id", entity_id).execute()
        return result.count or 0
    
    def get_entity_edges(self, entity_id: str, direction: str = "both") -> List[EntityEdge]:
        """Get edges for an entity.
        
        Args:
            entity_id: The entity ID
            direction: 'in', 'out', or 'both'
        """
        if direction == "in":
            query = self.client.table("entity_edges").select("*").eq("to_id", entity_id)
        elif direction == "out":
            query = self.client.table("entity_edges").select("*").eq("from_id", entity_id)
        else:  # both
            query = self.client.table("entity_edges").select("*").or_(f"from_id.eq.{entity_id},to_id.eq.{entity_id}")
        
        result = query.execute()
        return [EntityEdge(**row) for row in result.data]
    
    def get_entity_relations(self, entity_id: str, limit: int = 10) -> List[Tuple[str, str, float]]:
        """Get top relations for an entity (relation_type, related_entity_name, weight).
        
        Returns relations sorted by weight descending.
        """
        # Get outgoing edges
        out_edges = self.client.table("entity_edges").select(
            "rel_type,entities!entity_edges_to_id_fkey(name),weight"
        ).eq("from_id", entity_id).execute()
        
        # Get incoming edges  
        in_edges = self.client.table("entity_edges").select(
            "rel_type,entities!entity_edges_from_id_fkey(name),weight"
        ).eq("to_id", entity_id).execute()
        
        relations = []
        
        # Process outgoing edges
        for edge in out_edges.data:
            if edge.get("entities") and edge["entities"].get("name"):
                relations.append((
                    edge["rel_type"],
                    edge["entities"]["name"],
                    edge.get("weight", 1.0)
                ))
        
        # Process incoming edges
        for edge in in_edges.data:
            if edge.get("entities") and edge["entities"].get("name"):
                relations.append((
                    f"is_{edge['rel_type']}_by",  # Reverse relation
                    edge["entities"]["name"],
                    edge.get("weight", 1.0)
                ))
        
        # Sort by weight descending and limit
        relations.sort(key=lambda x: x[2], reverse=True)
        return relations[:limit]
    
    def get_entity_memories(self, entity_id: str, limit: int = 50) -> List[Memory]:
        """Get memories that mention an entity."""
        # First get memory IDs from entity_mentions
        mentions_result = self.client.table("entity_mentions").select("memory_id").eq("entity_id", entity_id).execute()
        memory_ids = [mention["memory_id"] for mention in mentions_result.data]
        
        if not memory_ids:
            return []
        
        # Get the actual memories
        memories_result = self.client.table("memories").select("*").in_("id", memory_ids).limit(limit).execute()
        return [Memory(**row) for row in memories_result.data]
    
    def get_high_degree_entities(self, min_degree: int = 5, entity_type: str = "concept") -> List[Entity]:
        """Get entities with high in-degree (many incoming connections)."""
        # This is a complex query that requires a subquery or raw SQL
        # For now, we'll get all entities and filter in Python
        # In production, you might want to use a raw SQL query for better performance
        
        entities = self.get_concept_entities()
        high_degree_entities = []
        
        for entity in entities:
            degree = self.get_entity_in_degree(entity.id)
            if degree >= min_degree:
                high_degree_entities.append(entity)
        
        return high_degree_entities
    
    def get_entity_statistics(self) -> Dict[str, Any]:
        """Get statistics about entities and their connections."""
        # Count entities by type
        entities_result = self.client.table("entities").select("type", count="exact").execute()
        entity_counts = {}
        for row in entities_result.data:
            entity_counts[row["type"]] = row.get("count", 0)
        
        # Count total edges
        edges_result = self.client.table("entity_edges").select("id", count="exact").execute()
        total_edges = edges_result.count or 0
        
        # Count total memories
        memories_result = self.client.table("memories").select("id", count="exact").execute()
        total_memories = memories_result.count or 0
        
        return {
            "entity_counts": entity_counts,
            "total_edges": total_edges,
            "total_memories": total_memories
        }
    
    def get_memories_by_ids(self, memory_ids: List[str]) -> List[Memory]:
        """Get memories by their IDs."""
        if not memory_ids:
            return []
        
        result = self.client.table("memories").select("*").in_("id", memory_ids).execute()
        return [Memory(**row) for row in result.data]