# jobs/implicate_builder.py — build implicate index from entities and memories

import os
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI

from adapters.db import DatabaseAdapter, Entity, Memory
from adapters.pinecone_client import PineconeAdapter, EmbeddingRecord
from config import load_config

@dataclass
class ImplicateSummary:
    entity_id: str
    entity_name: str
    summary: str
    top_relations: List[Tuple[str, str, float]]
    source_memory_ids: List[str]
    relation_counts: Dict[str, int]

class ImplicateBuilder:
    """Build implicate index from entities, entity_edges, and memories."""
    
    def __init__(self, openai_client: Optional[OpenAI] = None):
        self.config = load_config()
        self.db = DatabaseAdapter()
        self.pinecone = PineconeAdapter()
        self.openai = openai_client or OpenAI(api_key=self.config["OPENAI_API_KEY"])
        self.embed_model = self.config.get("EMBED_MODEL", "text-embedding-3-small")
    
    def generate_entity_summary(self, entity: Entity, memories: List[Memory], 
                              relations: List[Tuple[str, str, float]]) -> str:
        """Generate a 1-paragraph summary for an entity based on its memories and relations."""
        
        # Prepare context from memories
        memory_contexts = []
        for memory in memories[:10]:  # Limit to top 10 memories
            context = f"Memory: {memory.title or 'Untitled'}\n{memory.content[:500]}..."
            memory_contexts.append(context)
        
        # Prepare relations context
        relations_text = []
        for rel_type, related_entity, weight in relations[:5]:  # Top 5 relations
            relations_text.append(f"- {rel_type}: {related_entity} (weight: {weight:.2f})")
        
        # Create prompt for summary generation
        prompt = f"""Generate a concise 1-paragraph summary for the concept entity "{entity.name}".

Entity Type: {entity.type}
Canonical: {entity.canonical}

Key Relations:
{chr(10).join(relations_text) if relations_text else "No relations found"}

Relevant Memories:
{chr(10).join(memory_contexts) if memory_contexts else "No memories found"}

Please synthesize this information into a coherent paragraph that captures:
1. What this concept represents
2. Its key relationships and connections
3. Important context from the memories

Keep it concise but informative (2-4 sentences). Focus on the most important and distinctive aspects."""

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at synthesizing information about concepts and entities. Create clear, concise summaries that capture the essence and key relationships."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating summary for {entity.name}: {str(e)}")
            return f"Concept: {entity.name}. This is a {entity.type} entity with {len(relations)} key relationships and {len(memories)} associated memories."
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI."""
        try:
            response = self.openai.embeddings.create(
                model=self.embed_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            raise
    
    def build_implicate_summary(self, entity: Entity) -> ImplicateSummary:
        """Build a complete implicate summary for an entity."""
        
        # Get entity relations
        relations = self.db.get_entity_relations(entity.id, limit=10)
        
        # Get entity memories
        memories = self.db.get_entity_memories(entity.id, limit=50)
        
        # Count relations by type
        relation_counts = {}
        for rel_type, _, _ in relations:
            relation_counts[rel_type] = relation_counts.get(rel_type, 0) + 1
        
        # Generate summary
        summary = self.generate_entity_summary(entity, memories, relations)
        
        return ImplicateSummary(
            entity_id=entity.id,
            entity_name=entity.name,
            summary=summary,
            top_relations=relations,
            source_memory_ids=[m.id for m in memories],
            relation_counts=relation_counts
        )
    
    def create_embedding_record(self, summary: ImplicateSummary) -> EmbeddingRecord:
        """Create an embedding record from an implicate summary."""
        
        # Generate embedding
        embedding = self.embed_text(summary.summary)
        
        # Create metadata
        metadata = {
            "entity_id": summary.entity_id,
            "entity_name": summary.entity_name,
            "entity_type": "concept",
            "rel_counts": summary.relation_counts,
            "source_memory_ids": summary.source_memory_ids,
            "relation_count": len(summary.top_relations),
            "memory_count": len(summary.source_memory_ids),
            "created_at": int(time.time())
        }
        
        # Create ID in format: concept:{uuid}
        record_id = f"concept:{summary.entity_id}"
        
        return EmbeddingRecord(
            id=record_id,
            values=embedding,
            metadata=metadata
        )
    
    def build_full_index(self, min_degree: int = 5, batch_size: int = 50) -> Dict[str, Any]:
        """Build the complete implicate index from all concept entities.
        
        Args:
            min_degree: Minimum in-degree for entities to include
            batch_size: Number of entities to process in each batch
            
        Returns:
            Dictionary with build results
        """
        print("Starting full implicate index build...")
        start_time = time.time()
        
        # Get high-degree concept entities
        print(f"Finding concept entities with in-degree >= {min_degree}...")
        entities = self.db.get_high_degree_entities(min_degree=min_degree, entity_type="concept")
        print(f"Found {len(entities)} high-degree concept entities")
        
        if not entities:
            return {
                "success": False,
                "error": "No high-degree concept entities found",
                "processed_count": 0,
                "duration_seconds": 0
            }
        
        # Process entities in batches
        total_processed = 0
        total_upserted = 0
        errors = []
        
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(entities) + batch_size - 1)//batch_size} ({len(batch)} entities)")
            
            batch_records = []
            
            for entity in batch:
                try:
                    # Build implicate summary
                    summary = self.build_implicate_summary(entity)
                    
                    # Create embedding record
                    record = self.create_embedding_record(summary)
                    batch_records.append(record)
                    
                    total_processed += 1
                    
                except Exception as e:
                    error_msg = f"Error processing entity {entity.name} ({entity.id}): {str(e)}"
                    errors.append(error_msg)
                    print(f"Warning: {error_msg}")
            
            # Upsert batch to Pinecone
            if batch_records:
                try:
                    result = self.pinecone.upsert_embeddings(batch_records, batch_size=100)
                    total_upserted += result["upserted_count"]
                    
                    if result["errors"]:
                        errors.extend(result["errors"])
                        
                except Exception as e:
                    error_msg = f"Error upserting batch: {str(e)}"
                    errors.append(error_msg)
                    print(f"Warning: {error_msg}")
        
        duration = time.time() - start_time
        
        return {
            "success": len(errors) == 0,
            "processed_count": total_processed,
            "upserted_count": total_upserted,
            "duration_seconds": duration,
            "errors": errors
        }
    
    def build_incremental(self, entity_ids: List[str], batch_size: int = 50) -> Dict[str, Any]:
        """Build implicate index for specific entities (incremental mode).
        
        Args:
            entity_ids: List of entity IDs to process
            batch_size: Number of entities to process in each batch
            
        Returns:
            Dictionary with build results
        """
        print(f"Starting incremental implicate index build for {len(entity_ids)} entities...")
        start_time = time.time()
        
        # Get entities by IDs
        entities = self.db.get_entities_by_ids(entity_ids)
        print(f"Found {len(entities)} entities to process")
        
        if not entities:
            return {
                "success": False,
                "error": "No entities found for provided IDs",
                "processed_count": 0,
                "duration_seconds": 0
            }
        
        # Process entities in batches
        total_processed = 0
        total_upserted = 0
        errors = []
        
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(entities) + batch_size - 1)//batch_size} ({len(batch)} entities)")
            
            batch_records = []
            
            for entity in batch:
                try:
                    # Build implicate summary
                    summary = self.build_implicate_summary(entity)
                    
                    # Create embedding record
                    record = self.create_embedding_record(summary)
                    batch_records.append(record)
                    
                    total_processed += 1
                    
                except Exception as e:
                    error_msg = f"Error processing entity {entity.name} ({entity.id}): {str(e)}"
                    errors.append(error_msg)
                    print(f"Warning: {error_msg}")
            
            # Upsert batch to Pinecone
            if batch_records:
                try:
                    result = self.pinecone.upsert_embeddings(batch_records, batch_size=100)
                    total_upserted += result["upserted_count"]
                    
                    if result["errors"]:
                        errors.extend(result["errors"])
                        
                except Exception as e:
                    error_msg = f"Error upserting batch: {str(e)}"
                    errors.append(error_msg)
                    print(f"Warning: {error_msg}")
        
        duration = time.time() - start_time
        
        return {
            "success": len(errors) == 0,
            "processed_count": total_processed,
            "upserted_count": total_upserted,
            "duration_seconds": duration,
            "errors": errors
        }
    
    def get_build_stats(self) -> Dict[str, Any]:
        """Get statistics about the current implicate index."""
        db_stats = self.db.get_entity_statistics()
        pinecone_stats = self.pinecone.get_index_stats()
        
        return {
            "database": db_stats,
            "pinecone": pinecone_stats,
            "index_exists": self.pinecone.check_index_exists()
        }

def main():
    """Main entry point for the implicate builder."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build implicate index from entities and memories")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full",
                       help="Build mode: full or incremental")
    parser.add_argument("--entity-ids", nargs="+", 
                       help="Entity IDs for incremental mode (comma-separated)")
    parser.add_argument("--min-degree", type=int, default=5,
                       help="Minimum in-degree for entities in full mode")
    parser.add_argument("--batch-size", type=int, default=50,
                       help="Batch size for processing")
    
    args = parser.parse_args()
    
    try:
        builder = ImplicateBuilder()
        
        if args.mode == "full":
            result = builder.build_full_index(
                min_degree=args.min_degree,
                batch_size=args.batch_size
            )
        else:  # incremental
            if not args.entity_ids:
                print("Error: --entity-ids required for incremental mode")
                return 1
            
            result = builder.build_incremental(
                entity_ids=args.entity_ids,
                batch_size=args.batch_size
            )
        
        # Print results
        print("\n" + "="*50)
        print("BUILD RESULTS")
        print("="*50)
        print(f"Success: {result['success']}")
        print(f"Processed: {result['processed_count']} entities")
        print(f"Upserted: {result['upserted_count']} embeddings")
        print(f"Duration: {result['duration_seconds']:.2f} seconds")
        
        if result['errors']:
            print(f"Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(result['errors']) > 5:
                print(f"  ... and {len(result['errors']) - 5} more errors")
        
        return 0 if result['success'] else 1
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())