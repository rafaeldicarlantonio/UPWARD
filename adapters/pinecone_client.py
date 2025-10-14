# adapters/pinecone_client.py — Pinecone operations for implicate index building

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pinecone import Pinecone, ServerlessSpec

@dataclass
class EmbeddingRecord:
    id: str
    values: List[float]
    metadata: Dict[str, Any]

class PineconeAdapter:
    """Pinecone operations for implicate index building."""
    
    def __init__(self, index_name: Optional[str] = None):
        self.api_key = os.getenv("PINECONE_API_KEY")
        if not self.api_key:
            raise RuntimeError("PINECONE_API_KEY environment variable is required")
        
        self.pc = Pinecone(api_key=self.api_key)
        self.index_name = index_name or os.getenv("PINECONE_IMPLICATE_INDEX")
        if not self.index_name:
            raise RuntimeError("PINECONE_IMPLICATE_INDEX environment variable is required")
        
        self._index = None
    
    @property
    def index(self):
        """Get the Pinecone index, creating it if necessary."""
        if self._index is None:
            self._index = self.pc.Index(self.index_name)
        return self._index
    
    def upsert_embeddings(self, records: List[EmbeddingRecord], batch_size: int = 100) -> Dict[str, Any]:
        """Upsert embeddings to the implicate index.
        
        Args:
            records: List of embedding records to upsert
            batch_size: Number of records to process in each batch
            
        Returns:
            Dictionary with upsert results
        """
        if not records:
            return {"upserted_count": 0}
        
        total_upserted = 0
        errors = []
        
        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            try:
                # Convert to Pinecone format
                vectors = []
                for record in batch:
                    vectors.append({
                        "id": record.id,
                        "values": record.values,
                        "metadata": record.metadata
                    })
                
                # Upsert batch
                result = self.index.upsert(vectors=vectors)
                total_upserted += len(batch)
                
            except Exception as e:
                error_msg = f"Failed to upsert batch {i//batch_size + 1}: {str(e)}"
                errors.append(error_msg)
                print(f"Warning: {error_msg}")
        
        return {
            "upserted_count": total_upserted,
            "errors": errors,
            "success": len(errors) == 0
        }
    
    def query_embeddings(self, vector: List[float], top_k: int = 10, 
                        filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query embeddings from the implicate index.
        
        Args:
            vector: Query vector
            top_k: Number of results to return
            filter_dict: Optional metadata filter
            
        Returns:
            List of query results with id, score, and metadata
        """
        try:
            query_params = {
                "vector": vector,
                "top_k": top_k,
                "include_metadata": True
            }
            
            if filter_dict:
                query_params["filter"] = filter_dict
            
            result = self.index.query(**query_params)
            
            # Normalize the response format
            matches = []
            if hasattr(result, 'matches'):
                for match in result.matches:
                    matches.append({
                        "id": getattr(match, 'id', None),
                        "score": getattr(match, 'score', 0.0),
                        "metadata": getattr(match, 'metadata', {}) or {}
                    })
            
            return matches
            
        except Exception as e:
            print(f"Error querying embeddings: {str(e)}")
            return []
    
    def delete_embeddings(self, ids: List[str]) -> Dict[str, Any]:
        """Delete embeddings by IDs.
        
        Args:
            ids: List of IDs to delete
            
        Returns:
            Dictionary with deletion results
        """
        if not ids:
            return {"deleted_count": 0}
        
        try:
            result = self.index.delete(ids=ids)
            return {
                "deleted_count": len(ids),
                "success": True
            }
        except Exception as e:
            return {
                "deleted_count": 0,
                "success": False,
                "error": str(e)
            }
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the implicate index.
        
        Returns:
            Dictionary with index statistics
        """
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": stats.namespaces
            }
        except Exception as e:
            return {
                "error": str(e),
                "success": False
            }
    
    def check_index_exists(self) -> bool:
        """Check if the implicate index exists.
        
        Returns:
            True if index exists, False otherwise
        """
        try:
            # Try to get index stats - if it succeeds, index exists
            self.get_index_stats()
            return True
        except Exception:
            return False
    
    def create_index_if_not_exists(self, dimension: int = 1536, metric: str = "cosine") -> bool:
        """Create the implicate index if it doesn't exist.
        
        Args:
            dimension: Vector dimension (default 1536 for text-embedding-3-small)
            metric: Distance metric (default "cosine")
            
        Returns:
            True if index was created or already exists, False if creation failed
        """
        try:
            if self.check_index_exists():
                return True
            
            # Create the index
            self.pc.create_index(
                name=self.index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            
            return True
            
        except Exception as e:
            print(f"Error creating index: {str(e)}")
            return False