# tests/test_implicate_builder.py — tests for implicate index building

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any

from adapters.db import DatabaseAdapter, Entity, Memory, EntityEdge
from adapters.pinecone_client import PineconeAdapter, EmbeddingRecord
from jobs.implicate_builder import ImplicateBuilder, ImplicateSummary

# Test data fixtures
@pytest.fixture
def sample_entity():
    return Entity(
        id="test-entity-1",
        name="Machine Learning",
        type="concept",
        canonical=True,
        created_at="2024-01-01T00:00:00Z"
    )

@pytest.fixture
def sample_memories():
    return [
        Memory(
            id="memory-1",
            type="semantic",
            title="Introduction to ML",
            content="Machine learning is a subset of artificial intelligence...",
            summary="ML overview",
            importance=8,
            meta={},
            created_at="2024-01-01T00:00:00Z"
        ),
        Memory(
            id="memory-2",
            type="episodic",
            title="ML Project Experience",
            content="Worked on a machine learning project using TensorFlow...",
            summary="ML project work",
            importance=7,
            meta={},
            created_at="2024-01-02T00:00:00Z"
        )
    ]

@pytest.fixture
def sample_relations():
    return [
        ("related_to", "Artificial Intelligence", 0.9),
        ("subfield_of", "Computer Science", 0.8),
        ("uses", "Neural Networks", 0.7),
        ("applied_in", "Data Science", 0.6)
    ]

@pytest.fixture
def sample_embedding():
    return [0.1, 0.2, 0.3, 0.4, 0.5]  # Mock embedding vector

class TestImplicateBuilder:
    """Test the ImplicateBuilder class."""
    
    def test_init(self):
        """Test ImplicateBuilder initialization."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            builder = ImplicateBuilder()
            
            assert builder.db is not None
            assert builder.pinecone is not None
            assert builder.openai is not None
    
    def test_generate_entity_summary(self, sample_entity, sample_memories, sample_relations):
        """Test entity summary generation."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock OpenAI response
            mock_openai = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Machine Learning is a subset of artificial intelligence that focuses on algorithms and statistical models."
            mock_openai.chat.completions.create.return_value = mock_response
            mock_openai_class.return_value = mock_openai
            
            builder = ImplicateBuilder(openai_client=mock_openai)
            
            summary = builder.generate_entity_summary(sample_entity, sample_memories, sample_relations)
            
            assert isinstance(summary, str)
            assert len(summary) > 0
            assert "Machine Learning" in summary or "machine learning" in summary.lower()
            
            # Verify OpenAI was called correctly
            mock_openai.chat.completions.create.assert_called_once()
            call_args = mock_openai.chat.completions.create.call_args
            assert call_args[1]["model"] == "gpt-4o-mini"
            assert call_args[1]["max_tokens"] == 300
            assert call_args[1]["temperature"] == 0.3
    
    def test_generate_entity_summary_error_handling(self, sample_entity, sample_memories, sample_relations):
        """Test entity summary generation error handling."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock OpenAI to raise an exception
            mock_openai = Mock()
            mock_openai.chat.completions.create.side_effect = Exception("API Error")
            mock_openai_class.return_value = mock_openai
            
            builder = ImplicateBuilder(openai_client=mock_openai)
            
            summary = builder.generate_entity_summary(sample_entity, sample_memories, sample_relations)
            
            # Should return fallback summary
            assert isinstance(summary, str)
            assert sample_entity.name in summary
            assert "concept" in summary.lower()
    
    def test_embed_text(self, sample_embedding):
        """Test text embedding generation."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key", "EMBED_MODEL": "text-embedding-3-small"}
            
            # Mock OpenAI embedding response
            mock_openai = Mock()
            mock_response = Mock()
            mock_response.data = [Mock()]
            mock_response.data[0].embedding = sample_embedding
            mock_openai.embeddings.create.return_value = mock_response
            mock_openai_class.return_value = mock_openai
            
            builder = ImplicateBuilder(openai_client=mock_openai)
            
            embedding = builder.embed_text("Test text")
            
            assert embedding == sample_embedding
            mock_openai.embeddings.create.assert_called_once_with(
                model="text-embedding-3-small",
                input="Test text"
            )
    
    def test_build_implicate_summary(self, sample_entity, sample_memories, sample_relations):
        """Test building complete implicate summary."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db_class, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock database adapter
            mock_db = Mock()
            mock_db.get_entity_relations.return_value = sample_relations
            mock_db.get_entity_memories.return_value = sample_memories
            mock_db_class.return_value = mock_db
            
            # Mock OpenAI
            mock_openai = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Machine Learning is a subset of AI..."
            mock_openai.chat.completions.create.return_value = mock_response
            mock_openai_class.return_value = mock_openai
            
            builder = ImplicateBuilder(openai_client=mock_openai)
            builder.db = mock_db
            
            summary = builder.build_implicate_summary(sample_entity)
            
            assert isinstance(summary, ImplicateSummary)
            assert summary.entity_id == sample_entity.id
            assert summary.entity_name == sample_entity.name
            assert summary.summary == "Machine Learning is a subset of AI..."
            assert summary.top_relations == sample_relations
            assert summary.source_memory_ids == [m.id for m in sample_memories]
            assert "related_to" in summary.relation_counts
            assert summary.relation_counts["related_to"] == 1
    
    def test_create_embedding_record(self, sample_entity, sample_embedding):
        """Test creating embedding record from summary."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock OpenAI embedding
            mock_openai = Mock()
            mock_response = Mock()
            mock_response.data = [Mock()]
            mock_response.data[0].embedding = sample_embedding
            mock_openai.embeddings.create.return_value = mock_response
            mock_openai_class.return_value = mock_openai
            
            builder = ImplicateBuilder(openai_client=mock_openai)
            
            # Create test summary
            summary = ImplicateSummary(
                entity_id=sample_entity.id,
                entity_name=sample_entity.name,
                summary="Test summary",
                top_relations=[("related_to", "AI", 0.9)],
                source_memory_ids=["mem1", "mem2"],
                relation_counts={"related_to": 1}
            )
            
            record = builder.create_embedding_record(summary)
            
            assert isinstance(record, EmbeddingRecord)
            assert record.id == f"concept:{sample_entity.id}"
            assert record.values == sample_embedding
            assert record.metadata["entity_id"] == sample_entity.id
            assert record.metadata["entity_name"] == sample_entity.name
            assert record.metadata["entity_type"] == "concept"
            assert record.metadata["rel_counts"] == {"related_to": 1}
            assert record.metadata["source_memory_ids"] == ["mem1", "mem2"]
    
    def test_build_full_index(self, sample_entity):
        """Test full index building."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db_class, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone_class, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock database adapter
            mock_db = Mock()
            mock_db.get_high_degree_entities.return_value = [sample_entity]
            mock_db.get_entity_relations.return_value = [("related_to", "AI", 0.9)]
            mock_db.get_entity_memories.return_value = []
            mock_db_class.return_value = mock_db
            
            # Mock Pinecone adapter
            mock_pinecone = Mock()
            mock_pinecone.upsert_embeddings.return_value = {"upserted_count": 1, "errors": []}
            mock_pinecone_class.return_value = mock_pinecone
            
            # Mock OpenAI
            mock_openai = Mock()
            mock_chat_response = Mock()
            mock_chat_response.choices = [Mock()]
            mock_chat_response.choices[0].message.content = "Test summary"
            mock_openai.chat.completions.create.return_value = mock_chat_response
            
            mock_embed_response = Mock()
            mock_embed_response.data = [Mock()]
            mock_embed_response.data[0].embedding = [0.1, 0.2, 0.3]
            mock_openai.embeddings.create.return_value = mock_embed_response
            mock_openai_class.return_value = mock_openai
            
            builder = ImplicateBuilder(openai_client=mock_openai)
            builder.db = mock_db
            builder.pinecone = mock_pinecone
            
            result = builder.build_full_index(min_degree=5, batch_size=1)
            
            assert result["success"] is True
            assert result["processed_count"] == 1
            assert result["upserted_count"] == 1
            assert result["duration_seconds"] > 0
            assert len(result["errors"]) == 0
    
    def test_build_incremental(self, sample_entity):
        """Test incremental index building."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db_class, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone_class, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock database adapter
            mock_db = Mock()
            mock_db.get_entities_by_ids.return_value = [sample_entity]
            mock_db.get_entity_relations.return_value = [("related_to", "AI", 0.9)]
            mock_db.get_entity_memories.return_value = []
            mock_db_class.return_value = mock_db
            
            # Mock Pinecone adapter
            mock_pinecone = Mock()
            mock_pinecone.upsert_embeddings.return_value = {"upserted_count": 1, "errors": []}
            mock_pinecone_class.return_value = mock_pinecone
            
            # Mock OpenAI
            mock_openai = Mock()
            mock_chat_response = Mock()
            mock_chat_response.choices = [Mock()]
            mock_chat_response.choices[0].message.content = "Test summary"
            mock_openai.chat.completions.create.return_value = mock_chat_response
            
            mock_embed_response = Mock()
            mock_embed_response.data = [Mock()]
            mock_embed_response.data[0].embedding = [0.1, 0.2, 0.3]
            mock_openai.embeddings.create.return_value = mock_embed_response
            mock_openai_class.return_value = mock_openai
            
            builder = ImplicateBuilder(openai_client=mock_openai)
            builder.db = mock_db
            builder.pinecone = mock_pinecone
            
            result = builder.build_incremental(["test-entity-1"], batch_size=1)
            
            assert result["success"] is True
            assert result["processed_count"] == 1
            assert result["upserted_count"] == 1
            assert result["duration_seconds"] > 0
            assert len(result["errors"]) == 0
    
    def test_build_incremental_no_entities(self):
        """Test incremental building with no entities found."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db_class, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock database adapter to return no entities
            mock_db = Mock()
            mock_db.get_entities_by_ids.return_value = []
            mock_db_class.return_value = mock_db
            
            builder = ImplicateBuilder()
            builder.db = mock_db
            
            result = builder.build_incremental(["nonexistent-id"])
            
            assert result["success"] is False
            assert "No entities found" in result["error"]
            assert result["processed_count"] == 0
    
    def test_get_build_stats(self):
        """Test getting build statistics."""
        with patch('jobs.implicate_builder.load_config') as mock_config, \
             patch('jobs.implicate_builder.DatabaseAdapter') as mock_db_class, \
             patch('jobs.implicate_builder.PineconeAdapter') as mock_pinecone_class, \
             patch('jobs.implicate_builder.OpenAI') as mock_openai_class:
            
            mock_config.return_value = {"OPENAI_API_KEY": "test-key"}
            
            # Mock database adapter
            mock_db = Mock()
            mock_db.get_entity_statistics.return_value = {
                "entity_counts": {"concept": 10, "person": 5},
                "total_edges": 50,
                "total_memories": 100
            }
            mock_db_class.return_value = mock_db
            
            # Mock Pinecone adapter
            mock_pinecone = Mock()
            mock_pinecone.get_index_stats.return_value = {
                "total_vector_count": 25,
                "dimension": 1536,
                "index_fullness": 0.1
            }
            mock_pinecone.check_index_exists.return_value = True
            mock_pinecone_class.return_value = mock_pinecone
            
            builder = ImplicateBuilder()
            builder.db = mock_db
            builder.pinecone = mock_pinecone
            
            stats = builder.get_build_stats()
            
            assert "database" in stats
            assert "pinecone" in stats
            assert "index_exists" in stats
            assert stats["database"]["entity_counts"]["concept"] == 10
            assert stats["pinecone"]["total_vector_count"] == 25
            assert stats["index_exists"] is True


class TestDatabaseAdapter:
    """Test the DatabaseAdapter class."""
    
    def test_get_concept_entities(self):
        """Test getting concept entities."""
        with patch('adapters.db.get_client') as mock_get_client:
            mock_client = Mock()
            mock_table = Mock()
            mock_query = Mock()
            
            mock_query.eq.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.execute.return_value.data = [
                {
                    "id": "entity-1",
                    "name": "AI",
                    "type": "concept",
                    "canonical": True,
                    "created_at": "2024-01-01T00:00:00Z"
                }
            ]
            
            mock_table.select.return_value = mock_query
            mock_client.table.return_value = mock_table
            mock_get_client.return_value = mock_client
            
            db = DatabaseAdapter()
            entities = db.get_concept_entities(limit=10)
            
            assert len(entities) == 1
            assert entities[0].name == "AI"
            assert entities[0].type == "concept"
    
    def test_get_entity_in_degree(self):
        """Test getting entity in-degree."""
        with patch('adapters.db.get_client') as mock_get_client:
            mock_client = Mock()
            mock_table = Mock()
            mock_query = Mock()
            
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value.count = 5
            
            mock_table.select.return_value = mock_query
            mock_client.table.return_value = mock_table
            mock_get_client.return_value = mock_client
            
            db = DatabaseAdapter()
            degree = db.get_entity_in_degree("entity-1")
            
            assert degree == 5
    
    def test_get_entity_relations(self):
        """Test getting entity relations."""
        with patch('adapters.db.get_client') as mock_get_client:
            mock_client = Mock()
            mock_table = Mock()
            mock_query = Mock()
            
            # Mock both outgoing and incoming edges
            mock_query.eq.return_value = mock_query
            mock_query.or_.return_value = mock_query
            mock_query.execute.return_value.data = [
                {
                    "rel_type": "related_to",
                    "entities": {"name": "AI"},
                    "weight": 0.9
                }
            ]
            
            mock_table.select.return_value = mock_query
            mock_client.table.return_value = mock_table
            mock_get_client.return_value = mock_client
            
            db = DatabaseAdapter()
            relations = db.get_entity_relations("entity-1")
            
            # Should have both outgoing and incoming relations (2 total)
            assert len(relations) == 2
            # Check that we have both outgoing and incoming relations
            rel_types = [rel[0] for rel in relations]
            assert "related_to" in rel_types
            assert "is_related_to_by" in rel_types


class TestPineconeAdapter:
    """Test the PineconeAdapter class."""
    
    def test_upsert_embeddings(self):
        """Test upserting embeddings."""
        with patch('adapters.pinecone_client.Pinecone') as mock_pinecone_class, \
             patch.dict('os.environ', {'PINECONE_API_KEY': 'test-key', 'PINECONE_IMPLICATE_INDEX': 'test-index'}):
            
            mock_pc = Mock()
            mock_index = Mock()
            mock_index.upsert.return_value = {"upserted_count": 2}
            mock_pc.Index.return_value = mock_index
            mock_pinecone_class.return_value = mock_pc
            
            adapter = PineconeAdapter()
            adapter._index = mock_index  # Set the index directly
            
            records = [
                EmbeddingRecord(id="test-1", values=[0.1, 0.2], metadata={"test": "data1"}),
                EmbeddingRecord(id="test-2", values=[0.3, 0.4], metadata={"test": "data2"})
            ]
            
            result = adapter.upsert_embeddings(records)
            
            assert result["upserted_count"] == 2
            assert result["success"] is True
            assert len(result["errors"]) == 0
            
            # Verify upsert was called
            mock_index.upsert.assert_called_once()
            call_args = mock_index.upsert.call_args[1]
            assert len(call_args["vectors"]) == 2
    
    def test_query_embeddings(self):
        """Test querying embeddings."""
        with patch('adapters.pinecone_client.Pinecone') as mock_pinecone_class, \
             patch.dict('os.environ', {'PINECONE_API_KEY': 'test-key', 'PINECONE_IMPLICATE_INDEX': 'test-index'}):
            
            mock_pc = Mock()
            mock_index = Mock()
            
            # Mock query response
            mock_match = Mock()
            mock_match.id = "test-1"
            mock_match.score = 0.95
            mock_match.metadata = {"test": "data"}
            
            mock_response = Mock()
            mock_response.matches = [mock_match]
            mock_index.query.return_value = mock_response
            
            mock_pc.Index.return_value = mock_index
            mock_pinecone_class.return_value = mock_pc
            
            adapter = PineconeAdapter()
            adapter._index = mock_index
            
            results = adapter.query_embeddings([0.1, 0.2], top_k=5)
            
            assert len(results) == 1
            assert results[0]["id"] == "test-1"
            assert results[0]["score"] == 0.95
            assert results[0]["metadata"]["test"] == "data"
    
    def test_delete_embeddings(self):
        """Test deleting embeddings."""
        with patch('adapters.pinecone_client.Pinecone') as mock_pinecone_class, \
             patch.dict('os.environ', {'PINECONE_API_KEY': 'test-key', 'PINECONE_IMPLICATE_INDEX': 'test-index'}):
            
            mock_pc = Mock()
            mock_index = Mock()
            mock_index.delete.return_value = {"deleted_count": 2}
            mock_pc.Index.return_value = mock_index
            mock_pinecone_class.return_value = mock_pc
            
            adapter = PineconeAdapter()
            adapter._index = mock_index
            
            result = adapter.delete_embeddings(["test-1", "test-2"])
            
            assert result["deleted_count"] == 2
            assert result["success"] is True
            
            # Verify delete was called
            mock_index.delete.assert_called_once_with(ids=["test-1", "test-2"])
    
    def test_get_index_stats(self):
        """Test getting index statistics."""
        with patch('adapters.pinecone_client.Pinecone') as mock_pinecone_class, \
             patch.dict('os.environ', {'PINECONE_API_KEY': 'test-key', 'PINECONE_IMPLICATE_INDEX': 'test-index'}):
            
            mock_pc = Mock()
            mock_index = Mock()
            
            mock_stats = Mock()
            mock_stats.total_vector_count = 100
            mock_stats.dimension = 1536
            mock_stats.index_fullness = 0.1
            mock_stats.namespaces = {}
            
            mock_index.describe_index_stats.return_value = mock_stats
            mock_pc.Index.return_value = mock_index
            mock_pinecone_class.return_value = mock_pc
            
            adapter = PineconeAdapter()
            adapter._index = mock_index
            
            stats = adapter.get_index_stats()
            
            assert stats["total_vector_count"] == 100
            assert stats["dimension"] == 1536
            assert stats["index_fullness"] == 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])