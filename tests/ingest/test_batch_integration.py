#!/usr/bin/env python3
"""Integration tests for batch ingest with analysis."""

from __future__ import annotations

import pytest
import time
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock, call

from ingest.pipeline import AnalysisResult
from ingest.commit import CommitResult, slugify
from nlp.frames import EventFrame
from nlp.verbs import PredicateFrame


class TestSlugify:
    """Test slugify function for stable IDs."""
    
    def test_slugify_basic(self):
        """Test basic slugification."""
        from ingest.commit import slugify
        
        assert slugify("Machine Learning") == "machine-learning"
        assert slugify("Natural Language Processing") == "natural-language-processing"
        assert slugify("AI & ML") == "ai-ml"
    
    def test_slugify_removes_special_chars(self):
        """Test that special characters are removed."""
        assert slugify("Test@#$%^&*()") == "test"
        assert slugify("Hello, World!") == "hello-world"
    
    def test_slugify_handles_multiple_spaces(self):
        """Test handling of multiple spaces."""
        assert slugify("test   multiple   spaces") == "test-multiple-spaces"
    
    def test_slugify_handles_consecutive_hyphens(self):
        """Test handling of consecutive hyphens."""
        assert slugify("test---hyphens") == "test-hyphens"
    
    def test_slugify_strips_edges(self):
        """Test stripping hyphens from start/end."""
        assert slugify("-test-") == "test"
        assert slugify("---test---") == "test"
    
    def test_slugify_length_limit(self):
        """Test length limiting."""
        long_text = "a" * 100
        result = slugify(long_text)
        assert len(result) <= 64


class TestIdempotentUpserts:
    """Test idempotent entity and edge upserts."""
    
    @patch("ingest.commit.get_client")
    def test_concept_entity_idempotency(self, mock_get_client):
        """Test that upserting the same concept twice returns the same ID."""
        from ingest.commit import upsert_concept_entity
        
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()
        
        # First call: entity doesn't exist
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value.data = []
        mock_table.select.return_value = mock_query
        
        # Insert returns new entity
        mock_insert_query = Mock()
        mock_insert_query.execute.return_value.data = [{"id": "entity-123"}]
        mock_table.insert.return_value = mock_insert_query
        
        mock_sb.table.return_value = mock_table
        
        # First upsert
        entity_id_1 = upsert_concept_entity(mock_sb, "Machine Learning")
        assert entity_id_1 == "entity-123"
        
        # Second call: entity exists
        mock_query2 = Mock()
        mock_query2.eq.return_value = mock_query2
        mock_query2.limit.return_value = mock_query2
        mock_query2.execute.return_value.data = [{"id": "entity-123"}]
        mock_table.select.return_value = mock_query2
        
        # Second upsert returns same ID
        entity_id_2 = upsert_concept_entity(mock_sb, "Machine Learning")
        assert entity_id_2 == "entity-123"
        assert entity_id_1 == entity_id_2
    
    @patch("ingest.commit.get_client")
    def test_frame_entity_stable_naming(self, mock_get_client):
        """Test that frame entities have stable names."""
        from ingest.commit import upsert_frame_entity
        
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()
        
        # Entity doesn't exist
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value.data = []
        mock_table.select.return_value = mock_query
        
        # Insert returns new entity
        mock_insert_query = Mock()
        mock_insert_query.execute.return_value.data = [{"id": "frame-entity-456"}]
        mock_table.insert.return_value = mock_insert_query
        
        mock_sb.table.return_value = mock_table
        
        # Upsert with file_id and chunk_idx
        entity_id = upsert_frame_entity(
            mock_sb,
            "frame-1",
            "measurement",
            file_id="test-file.pdf",
            chunk_idx=5,
        )
        
        assert entity_id == "frame-entity-456"
        
        # Verify stable naming was used
        insert_call = mock_table.insert.call_args
        payload = insert_call[0][0]
        assert "frame:test-filepdf:5:frame-1" == payload["name"]
    
    @patch("ingest.commit.get_client")
    def test_edge_creation_idempotency(self, mock_get_client):
        """Test that creating the same edge twice returns the same ID."""
        from ingest.commit import create_entity_edge
        
        mock_sb = Mock()
        mock_table = Mock()
        mock_query = Mock()
        
        # First call: edge doesn't exist
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value.data = []
        mock_table.select.return_value = mock_query
        
        # Insert returns new edge
        mock_insert_query = Mock()
        mock_insert_query.execute.return_value.data = [{"id": "edge-789"}]
        mock_table.insert.return_value = mock_insert_query
        
        mock_sb.table.return_value = mock_table
        
        # First create
        edge_id_1 = create_entity_edge(
            mock_sb,
            from_id="entity-1",
            to_id="entity-2",
            rel_type="supports",
        )
        assert edge_id_1 == "edge-789"
        
        # Second call: edge exists
        mock_query2 = Mock()
        mock_query2.eq.return_value = mock_query2
        mock_query2.limit.return_value = mock_query2
        mock_query2.execute.return_value.data = [{"id": "edge-789"}]
        mock_table.select.return_value = mock_query2
        
        # Second create returns same ID
        edge_id_2 = create_entity_edge(
            mock_sb,
            from_id="entity-1",
            to_id="entity-2",
            rel_type="supports",
        )
        assert edge_id_2 == "edge-789"
        assert edge_id_1 == edge_id_2


class TestBatchIngestIntegration:
    """Integration tests for batch ingest with analysis."""
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.commit_analysis")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    def test_batch_ingest_with_analysis_enabled(
        self,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_commit,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test batch ingest with analysis enabled."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        
        # Setup mocks
        mock_get_flag.return_value = True  # Analysis enabled
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 100,
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert response
        mock_upsert.return_value = {
            "upserted": [
                {"idx": 0, "memory_id": "memory-1"},
                {"idx": 1, "memory_id": "memory-2"},
            ],
            "updated": [],
            "skipped": [],
        }
        
        # Mock analysis
        mock_analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[{"name": "Test Concept", "rationale": "test"}],
            contradictions=[],
        )
        mock_analyze.return_value = mock_analysis
        
        # Mock commit
        mock_commit_result = CommitResult(
            concept_entity_ids=["concept-1"],
            frame_entity_ids=[],
            edge_ids=[],
            memory_id="memory-1",
        )
        mock_commit.return_value = mock_commit_result
        
        # Create request
        request = IngestBatchRequest(
            items=[
                IngestItem(text="Test text 1", type="semantic"),
                IngestItem(text="Test text 2", type="semantic"),
            ]
        )
        
        # Call endpoint
        response = ingest_batch_ingest_batch_post(request)
        
        # Verify analysis was called
        assert mock_analyze.call_count == 2
        
        # Verify commit was called
        assert mock_commit.call_count == 2
        
        # Verify response
        assert len(response["upserted"]) == 2
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    def test_batch_ingest_with_analysis_disabled(
        self,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_get_flag,
    ):
        """Test batch ingest with analysis disabled."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        
        # Setup mocks
        mock_get_flag.return_value = False  # Analysis disabled
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert response
        mock_upsert.return_value = {
            "upserted": [{"idx": 0, "memory_id": "memory-1"}],
            "updated": [],
            "skipped": [],
        }
        
        # Create request
        request = IngestBatchRequest(
            items=[IngestItem(text="Test text", type="semantic")]
        )
        
        # Call endpoint
        response = ingest_batch_ingest_batch_post(request)
        
        # Verify upsert was called but no analysis
        assert mock_upsert.call_count == 1
        assert len(response["upserted"]) == 1
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.commit_analysis")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    @patch("router.ingest.time")
    def test_batch_ingest_with_timeout(
        self,
        mock_time_module,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_commit,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test that slow chunks are skipped with timeout warning."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        
        # Setup mocks
        mock_get_flag.return_value = True
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 50,  # 50ms timeout
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert response
        mock_upsert.return_value = {
            "upserted": [{"idx": 0, "memory_id": "memory-1"}],
            "updated": [],
            "skipped": [],
        }
        
        # Mock perf_counter to simulate timeout
        # Start time: 0.0, end time: 0.100 (100ms elapsed)
        mock_time_module.perf_counter.side_effect = [0.0, 0.100]
        
        # Mock analysis
        mock_analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[],
            contradictions=[],
        )
        mock_analyze.return_value = mock_analysis
        
        # Create request
        request = IngestBatchRequest(
            items=[IngestItem(text="Slow chunk", type="semantic")]
        )
        
        # Call endpoint
        with patch("router.ingest.logger") as mock_logger:
            response = ingest_batch_ingest_batch_post(request)
            
            # Verify timeout warning was logged
            assert mock_logger.warning.called
            warning_call = mock_logger.warning.call_args[0][0]
            assert "timeout exceeded" in warning_call.lower()
        
        # Verify commit was NOT called due to timeout
        assert mock_commit.call_count == 0
        
        # Verify skip was recorded
        assert len(response["skipped"]) >= 1
        skip_entry = [s for s in response["skipped"] if s.get("reason") == "analysis_timeout"]
        assert len(skip_entry) > 0
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    def test_batch_ingest_with_analysis_error(
        self,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test that analysis errors are logged and skipped."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        
        # Setup mocks
        mock_get_flag.return_value = True
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 100,
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert response
        mock_upsert.return_value = {
            "upserted": [{"idx": 0, "memory_id": "memory-1"}],
            "updated": [],
            "skipped": [],
        }
        
        # Mock analysis to raise error
        mock_analyze.side_effect = Exception("Analysis failed")
        
        # Create request
        request = IngestBatchRequest(
            items=[IngestItem(text="Error chunk", type="semantic")]
        )
        
        # Call endpoint
        with patch("router.ingest.logger") as mock_logger:
            response = ingest_batch_ingest_batch_post(request)
            
            # Verify error was logged
            assert mock_logger.error.called
            error_call = mock_logger.error.call_args[0][0]
            assert "analysis failed" in error_call.lower()
        
        # Verify skip was recorded
        assert len(response["skipped"]) >= 1
        skip_entry = [s for s in response["skipped"] if s.get("reason") == "analysis_error"]
        assert len(skip_entry) > 0


class TestReingestionIdempotency:
    """Test that re-ingesting the same file doesn't duplicate entities/edges."""
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.commit_analysis")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    def test_reingestion_idempotency(
        self,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_commit,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test that re-ingesting the same file is idempotent."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        
        # Setup mocks
        mock_get_flag.return_value = True
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 100,
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert response (same memory IDs each time)
        mock_upsert.return_value = {
            "upserted": [{"idx": 0, "memory_id": "memory-stable"}],
            "updated": [],
            "skipped": [],
        }
        
        # Mock analysis
        mock_analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[{"name": "Machine Learning", "rationale": "test"}],
            contradictions=[],
        )
        mock_analyze.return_value = mock_analysis
        
        # Mock commit (same entity IDs each time)
        mock_commit_result = CommitResult(
            concept_entity_ids=["concept-machine-learning"],
            frame_entity_ids=[],
            edge_ids=[],
            memory_id="memory-stable",
        )
        mock_commit.return_value = mock_commit_result
        
        # Create request
        request = IngestBatchRequest(
            items=[IngestItem(
                text="Machine learning concepts",
                type="semantic",
                file_id="test-file.pdf",
            )]
        )
        
        # First ingestion
        response1 = ingest_batch_ingest_batch_post(request)
        
        # Second ingestion (same file)
        response2 = ingest_batch_ingest_batch_post(request)
        
        # Verify both completed
        assert len(response1["upserted"]) > 0
        assert len(response2["upserted"]) > 0
        
        # Verify commit was called with stable IDs
        commit_calls = mock_commit.call_args_list
        assert len(commit_calls) == 2
        
        # Both calls should use the same file_id and chunk_idx
        call1_kwargs = commit_calls[0][1]
        call2_kwargs = commit_calls[1][1]
        
        assert call1_kwargs["file_id"] == call2_kwargs["file_id"]
        assert call1_kwargs["chunk_idx"] == call2_kwargs["chunk_idx"]


class TestBatchCompletionWithSkips:
    """Test that batch processing completes even when some chunks are skipped."""
    
    @patch("router.ingest.get_feature_flag")
    @patch("router.ingest.load_config")
    @patch("router.ingest.analyze_chunk")
    @patch("router.ingest.commit_analysis")
    @patch("router.ingest.upsert_memories_from_chunks")
    @patch("router.ingest.ensure_user")
    @patch("router.ingest.get_index")
    @patch("router.ingest.get_client")
    def test_batch_completes_with_mixed_results(
        self,
        mock_get_client,
        mock_get_index,
        mock_ensure_user,
        mock_upsert,
        mock_commit,
        mock_analyze,
        mock_load_config,
        mock_get_flag,
    ):
        """Test that batch completes even with some failures/skips."""
        from router.ingest import ingest_batch_ingest_batch_post, IngestBatchRequest, IngestItem
        
        # Setup mocks
        mock_get_flag.return_value = True
        mock_load_config.return_value = {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 100,
            "INGEST_ANALYSIS_MAX_VERBS": 20,
            "INGEST_ANALYSIS_MAX_FRAMES": 10,
            "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
        }
        mock_ensure_user.return_value = "user-123"
        
        # Mock upsert response with 3 chunks
        mock_upsert.return_value = {
            "upserted": [
                {"idx": 0, "memory_id": "memory-1"},
                {"idx": 1, "memory_id": "memory-2"},
                {"idx": 2, "memory_id": "memory-3"},
            ],
            "updated": [],
            "skipped": [],
        }
        
        # Mock analysis: first succeeds, second fails, third succeeds
        mock_analysis_success = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[{"name": "Test", "rationale": "test"}],
            contradictions=[],
        )
        mock_analyze.side_effect = [
            mock_analysis_success,  # Chunk 0: success
            Exception("Analysis error"),  # Chunk 1: error
            mock_analysis_success,  # Chunk 2: success
        ]
        
        # Mock commit
        mock_commit_result = CommitResult(
            concept_entity_ids=["concept-1"],
            frame_entity_ids=[],
            edge_ids=[],
        )
        mock_commit.return_value = mock_commit_result
        
        # Create request with 3 chunks
        request = IngestBatchRequest(
            items=[
                IngestItem(text="Chunk 1", type="semantic"),
                IngestItem(text="Chunk 2", type="semantic"),
                IngestItem(text="Chunk 3", type="semantic"),
            ]
        )
        
        # Call endpoint
        response = ingest_batch_ingest_batch_post(request)
        
        # Verify batch completed
        assert len(response["upserted"]) == 3
        
        # Verify 2 successful commits (chunk 0 and 2)
        assert mock_commit.call_count == 2
        
        # Verify 1 skip (chunk 1 with error)
        analysis_errors = [s for s in response["skipped"] if s.get("reason") == "analysis_error"]
        assert len(analysis_errors) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
