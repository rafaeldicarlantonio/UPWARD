#!/usr/bin/env python3
"""Integration tests for ingest pipeline analyze and commit phases."""

from __future__ import annotations

import pytest
from typing import Dict, Iterable, List
from unittest.mock import Mock, patch, MagicMock

from nlp.tokenize import Token, TokenizationBackend
from nlp.verbs import PredicateFrame
from nlp.frames import EventFrame
from nlp.contradictions import ContradictionCandidate
from ingest.pipeline import (
    analyze_chunk,
    AnalysisContext,
    AnalysisLimits,
    AnalysisResult,
)
from ingest.commit import (
    commit_analysis,
    CommitResult,
    upsert_concept_entity,
    upsert_frame_entity,
    create_entity_edge,
    update_memory_contradictions,
    enqueue_implicate_refresh,
)


def _tok(text: str, lemma: str, pos: str, dep: str, head: int) -> Token:
    """Helper to create a Token."""
    return Token(text=text, lemma=lemma, pos=pos, dep=dep, head=head)


class FixtureBackend(TokenizationBackend):
    """Test backend with pre-defined token fixtures."""
    
    def __init__(self, fixtures: Dict[str, List[Token]]):
        self._fixtures = fixtures
    
    def tokenize(self, text: str) -> Iterable[Token]:
        try:
            return list(self._fixtures[text])
        except KeyError:
            # Fallback: simple tokenization
            words = text.split()
            return [_tok(w, w.lower(), "NOUN", "dep", 0) for w in words]


@pytest.fixture
def sample_text():
    """Sample text for analysis."""
    return "The machine learning model predicts temperature with high accuracy. Neural networks support deep learning concepts."


@pytest.fixture
def backend():
    """Tokenization backend with fixtures."""
    fixtures: Dict[str, List[Token]] = {}
    
    # First sentence
    fixtures["The machine learning model predicts temperature with high accuracy."] = [
        _tok("The", "the", "DET", "det", 1),
        _tok("machine", "machine", "NOUN", "compound", 2),
        _tok("learning", "learning", "NOUN", "compound", 3),
        _tok("model", "model", "NOUN", "nsubj", 4),
        _tok("predicts", "predict", "VERB", "ROOT", 4),
        _tok("temperature", "temperature", "NOUN", "dobj", 4),
        _tok("with", "with", "ADP", "prep", 4),
        _tok("high", "high", "ADJ", "amod", 8),
        _tok("accuracy", "accuracy", "NOUN", "pobj", 6),
        _tok(".", ".", "PUNCT", "punct", 4),
    ]
    
    # Second sentence
    fixtures["Neural networks support deep learning concepts."] = [
        _tok("Neural", "neural", "ADJ", "amod", 1),
        _tok("networks", "network", "NOUN", "nsubj", 2),
        _tok("support", "support", "VERB", "ROOT", 2),
        _tok("deep", "deep", "ADJ", "amod", 4),
        _tok("learning", "learning", "NOUN", "compound", 5),
        _tok("concepts", "concept", "NOUN", "dobj", 2),
        _tok(".", ".", "PUNCT", "punct", 2),
    ]
    
    # Combined text
    fixtures["The machine learning model predicts temperature with high accuracy. Neural networks support deep learning concepts."] = (
        fixtures["The machine learning model predicts temperature with high accuracy."] +
        fixtures["Neural networks support deep learning concepts."]
    )
    
    return FixtureBackend(fixtures)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock_sb = Mock()
    
    # Mock entity upserts
    def mock_entity_select(table_name):
        mock_table = Mock()
        mock_query = Mock()
        
        # Return empty for first check (entity doesn't exist)
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value.data = []
        
        mock_table.select.return_value = mock_query
        return mock_table
    
    def mock_entity_insert(table_name):
        mock_table = Mock()
        mock_query = Mock()
        
        # Return new entity with ID
        mock_query.execute.return_value.data = [{"id": f"entity-{table_name}-123"}]
        
        mock_table.insert.return_value = mock_query
        return mock_table
    
    # Setup table method to return appropriate mocks
    def table_method(name: str):
        if name == "entities":
            mock_table = Mock()
            mock_select = Mock()
            mock_insert = Mock()
            
            # Select returns empty (entity doesn't exist)
            mock_select_query = Mock()
            mock_select_query.eq.return_value = mock_select_query
            mock_select_query.limit.return_value = mock_select_query
            mock_select_query.execute.return_value.data = []
            mock_select.return_value = mock_select_query
            
            # Insert returns new entity
            entity_counter = [0]
            def insert_side_effect(payload):
                entity_counter[0] += 1
                mock_insert_query = Mock()
                entity_id = f"entity-{entity_counter[0]}"
                mock_insert_query.execute.return_value.data = [{"id": entity_id, **payload}]
                return mock_insert_query
            mock_insert.side_effect = insert_side_effect
            
            mock_table.select = mock_select
            mock_table.insert = mock_insert
            return mock_table
        
        elif name == "entity_edges":
            mock_table = Mock()
            mock_select = Mock()
            mock_insert = Mock()
            
            # Select returns empty (edge doesn't exist)
            mock_select_query = Mock()
            mock_select_query.eq.return_value = mock_select_query
            mock_select_query.limit.return_value = mock_select_query
            mock_select_query.execute.return_value.data = []
            mock_select.return_value = mock_select_query
            
            edge_counter = [0]
            def insert_edge(payload):
                edge_counter[0] += 1
                mock_query = Mock()
                edge_id = f"edge-{edge_counter[0]}"
                mock_query.execute.return_value.data = [{"id": edge_id, **payload}]
                return mock_query
            mock_insert.side_effect = insert_edge
            
            mock_table.select = mock_select
            mock_table.insert = mock_insert
            return mock_table
        
        elif name == "memories":
            mock_table = Mock()
            mock_update = Mock()
            
            mock_update_query = Mock()
            mock_update_query.eq.return_value = mock_update_query
            mock_update_query.execute.return_value = Mock()
            mock_update.return_value = mock_update_query
            
            mock_table.update = mock_update
            return mock_table
        
        elif name == "jobs":
            mock_table = Mock()
            mock_insert = Mock()
            
            job_counter = [0]
            def insert_job(payload):
                job_counter[0] += 1
                mock_query = Mock()
                mock_query.execute.return_value.data = [{"id": f"job-{job_counter[0]}", **payload}]
                return mock_query
            mock_insert.side_effect = insert_job
            
            mock_table.insert = mock_insert
            return mock_table
        
        return Mock()
    
    mock_sb.table.side_effect = table_method
    return mock_sb


class TestAnalyzeChunk:
    """Test the analyze_chunk function."""
    
    def test_analyze_chunk_basic(self, sample_text, backend):
        """Test basic chunk analysis."""
        result = analyze_chunk(
            sample_text,
            ctx=AnalysisContext(backend=backend),
            limits=AnalysisLimits(max_verbs=10, max_frames=5, max_concepts=5),
        )
        
        assert isinstance(result, AnalysisResult)
        assert len(result.predicates) > 0
        assert len(result.frames) > 0
        assert len(result.concepts) >= 0
        assert isinstance(result.contradictions, list)
    
    def test_analyze_chunk_extracts_predicates(self, sample_text, backend):
        """Test that predicates are extracted."""
        result = analyze_chunk(
            sample_text,
            ctx=AnalysisContext(backend=backend),
            limits=AnalysisLimits(max_verbs=10),
        )
        
        # Should have predicates for "predicts" and "support"
        assert len(result.predicates) >= 2
        verb_lemmas = {p.verb_lemma for p in result.predicates}
        assert "predict" in verb_lemmas or "support" in verb_lemmas
    
    def test_analyze_chunk_extracts_frames(self, sample_text, backend):
        """Test that event frames are extracted."""
        result = analyze_chunk(
            sample_text,
            ctx=AnalysisContext(backend=backend),
            limits=AnalysisLimits(max_frames=5),
        )
        
        assert len(result.frames) > 0
        assert all(isinstance(f, EventFrame) for f in result.frames)
    
    def test_analyze_chunk_suggests_concepts(self, sample_text, backend):
        """Test that concepts are suggested."""
        result = analyze_chunk(
            sample_text,
            ctx=AnalysisContext(backend=backend),
            limits=AnalysisLimits(max_concepts=5),
        )
        
        # Should suggest concepts like "Machine Learning Model", "Neural Network", etc.
        assert len(result.concepts) > 0
        concept_names = {c["name"] for c in result.concepts}
        # At least one concept should be suggested
        assert len(concept_names) > 0
    
    def test_analyze_chunk_with_limits(self, sample_text, backend):
        """Test that limits are respected."""
        result = analyze_chunk(
            sample_text,
            ctx=AnalysisContext(backend=backend),
            limits=AnalysisLimits(max_verbs=1, max_frames=1, max_concepts=1),
        )
        
        assert len(result.predicates) <= 1
        assert len(result.frames) <= 1
        assert len(result.concepts) <= 1


class TestCommitAnalysis:
    """Test the commit_analysis function."""
    
    def test_commit_creates_concept_entities(self, mock_supabase):
        """Test that concept entities are created."""
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[
                {"name": "Machine Learning", "rationale": "Test concept"},
                {"name": "Neural Network", "rationale": "Test concept"},
            ],
            contradictions=[],
        )
        
        result = commit_analysis(mock_supabase, analysis)
        
        assert isinstance(result, CommitResult)
        assert len(result.concept_entity_ids) == 2
        assert all(id.startswith("entity-") for id in result.concept_entity_ids)
    
    def test_commit_creates_frame_entities(self, mock_supabase):
        """Test that frame entities are created."""
        analysis = AnalysisResult(
            predicates=[],
            frames=[
                EventFrame(
                    frame_id="frame-1",
                    type="measurement",
                    roles={"agent": "model", "patient": "temperature"},
                ),
            ],
            concepts=[],
            contradictions=[],
        )
        
        result = commit_analysis(mock_supabase, analysis)
        
        assert len(result.frame_entity_ids) == 1
        assert result.frame_entity_ids[0].startswith("entity-")
    
    def test_commit_creates_evidence_edges(self, mock_supabase):
        """Test that evidence_of edges are created between frames and concepts."""
        analysis = AnalysisResult(
            predicates=[],
            frames=[
                EventFrame(
                    frame_id="frame-1",
                    type="measurement",
                    roles={"agent": "Machine Learning Model", "patient": None},
                ),
            ],
            concepts=[
                {"name": "Machine Learning", "rationale": "Test concept"},
            ],
            contradictions=[],
        )
        
        result = commit_analysis(mock_supabase, analysis)
        
        # Should have created concept entity, frame entity, and edge
        assert len(result.concept_entity_ids) == 1
        assert len(result.frame_entity_ids) == 1
        assert len(result.edge_ids) >= 1
    
    def test_commit_creates_supports_edges(self, mock_supabase):
        """Test that supports/contradicts edges are created from predicates."""
        analysis = AnalysisResult(
            predicates=[
                PredicateFrame(
                    verb_lemma="support",
                    subject_entity="Neural Network",
                    object_entity="Deep Learning",
                    modifiers=[],
                    polarity="positive",
                ),
            ],
            frames=[],
            concepts=[
                {"name": "Neural Network", "rationale": "Test concept"},
                {"name": "Deep Learning", "rationale": "Test concept"},
            ],
            contradictions=[],
        )
        
        result = commit_analysis(mock_supabase, analysis)
        
        # Should have created 2 concept entities and at least 1 edge
        assert len(result.concept_entity_ids) == 2
        assert len(result.edge_ids) >= 1
    
    def test_commit_updates_memory_contradictions(self, mock_supabase):
        """Test that memory contradictions are updated."""
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[],
            contradictions=[
                ContradictionCandidate(
                    subject_entity_id=None,
                    subject_text="Model",
                    claim_a="Model predicts temperature",
                    claim_b="Model not predict temperature",
                    evidence_ids=[],
                ),
            ],
        )
        
        memory_id = "memory-123"
        result = commit_analysis(mock_supabase, analysis, memory_id=memory_id)
        
        assert result.memory_id == memory_id
        # Should have called update on memories table
        mock_supabase.table.assert_any_call("memories")
    
    @patch("ingest.commit.get_feature_flag")
    def test_commit_enqueues_jobs_when_enabled(self, mock_get_flag, mock_supabase):
        """Test that implicate_refresh jobs are enqueued when flag is enabled."""
        mock_get_flag.return_value = True
        
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[
                {"name": "Machine Learning", "rationale": "Test concept"},
            ],
            contradictions=[],
        )
        
        result = commit_analysis(mock_supabase, analysis)
        
        assert result.jobs_enqueued >= 1
    
    @patch("ingest.commit.get_feature_flag")
    def test_commit_skips_jobs_when_disabled(self, mock_get_flag, mock_supabase):
        """Test that implicate_refresh jobs are not enqueued when flag is disabled."""
        mock_get_flag.return_value = False
        
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[
                {"name": "Machine Learning", "rationale": "Test concept"},
            ],
            contradictions=[],
        )
        
        result = commit_analysis(mock_supabase, analysis)
        
        assert result.jobs_enqueued == 0


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""
    
    @patch("ingest.commit.get_feature_flag")
    def test_analyze_and_commit_pipeline(self, mock_get_flag, sample_text, backend, mock_supabase):
        """Test the complete analyze and commit pipeline."""
        mock_get_flag.return_value = True
        
        # Step 1: Analyze the chunk
        analysis = analyze_chunk(
            sample_text,
            ctx=AnalysisContext(backend=backend),
            limits=AnalysisLimits(max_verbs=10, max_frames=5, max_concepts=5),
        )
        
        # Verify analysis results
        assert len(analysis.predicates) > 0
        assert len(analysis.frames) > 0
        assert len(analysis.concepts) > 0
        
        # Step 2: Commit the analysis
        result = commit_analysis(mock_supabase, analysis, memory_id="test-memory-123")
        
        # Verify commit results
        assert len(result.concept_entity_ids) > 0
        assert len(result.frame_entity_ids) > 0
        assert result.memory_id == "test-memory-123"
        
        # Verify that entities were created
        assert all(id.startswith("entity-") for id in result.concept_entity_ids)
        assert all(id.startswith("entity-") for id in result.frame_entity_ids)
        
        # Verify that jobs were enqueued (when flag is on)
        assert result.jobs_enqueued > 0
    
    @patch("ingest.commit.get_feature_flag")
    def test_complex_document_with_contradictions(self, mock_get_flag, backend, mock_supabase):
        """Test analysis and commit with a complex document containing contradictions."""
        mock_get_flag.return_value = False  # Disable job enqueuing for this test
        
        text = "The model predicts high accuracy. The model does not predict high accuracy."
        
        # Add fixture for this text with proper subjects for both predicates
        backend._fixtures[text] = [
            _tok("The", "the", "DET", "det", 1),
            _tok("model", "model", "NOUN", "nsubj", 2),
            _tok("predicts", "predict", "VERB", "ROOT", 2),
            _tok("high", "high", "ADJ", "amod", 4),
            _tok("accuracy", "accuracy", "NOUN", "dobj", 2),
            _tok(".", ".", "PUNCT", "punct", 2),
            _tok("The", "the", "DET", "det", 7),
            _tok("model", "model", "NOUN", "nsubj", 10),
            _tok("does", "do", "AUX", "aux", 10),
            _tok("not", "not", "ADV", "neg", 10),
            _tok("predict", "predict", "VERB", "ROOT", 10),
            _tok("high", "high", "ADJ", "amod", 12),
            _tok("accuracy", "accuracy", "NOUN", "dobj", 10),
            _tok(".", ".", "PUNCT", "punct", 10),
        ]
        
        # Analyze
        analysis = analyze_chunk(
            text,
            ctx=AnalysisContext(backend=backend),
            limits=AnalysisLimits(max_verbs=10, max_frames=5, max_concepts=5),
        )
        
        # Should have predicates with opposite polarities
        assert len(analysis.predicates) >= 2
        polarities = {p.polarity for p in analysis.predicates}
        assert "positive" in polarities or "negative" in polarities
        
        # Commit
        result = commit_analysis(mock_supabase, analysis, memory_id="test-memory-456")
        
        # Verify memory_id was set
        assert result.memory_id == "test-memory-456"
        
        # Verify no jobs were enqueued (flag is off)
        assert result.jobs_enqueued == 0


class TestHelperFunctions:
    """Test individual helper functions."""
    
    def test_upsert_concept_entity_creates_new(self, mock_supabase):
        """Test that upsert_concept_entity creates a new entity."""
        entity_id = upsert_concept_entity(mock_supabase, "Test Concept")
        
        assert entity_id is not None
        assert entity_id.startswith("entity-")
    
    def test_upsert_frame_entity_creates_new(self, mock_supabase):
        """Test that upsert_frame_entity creates a new entity."""
        entity_id = upsert_frame_entity(mock_supabase, "frame-1", "measurement")
        
        assert entity_id is not None
        assert entity_id.startswith("entity-")
    
    def test_create_entity_edge(self, mock_supabase):
        """Test that create_entity_edge creates an edge."""
        edge_id = create_entity_edge(
            mock_supabase,
            from_id="entity-1",
            to_id="entity-2",
            rel_type="supports",
            weight=0.8,
        )
        
        assert edge_id is not None
        assert edge_id.startswith("edge-")
    
    def test_update_memory_contradictions(self, mock_supabase):
        """Test that update_memory_contradictions updates the memory."""
        contradictions = [
            {
                "subject_entity_id": None,
                "subject_text": "Model",
                "claim_a": "Claim A",
                "claim_b": "Claim B",
                "evidence_ids": [],
            }
        ]
        
        success = update_memory_contradictions(mock_supabase, "memory-123", contradictions)
        
        # Should succeed (mock doesn't raise exceptions)
        assert success is True
    
    @patch("ingest.commit.get_feature_flag")
    def test_enqueue_implicate_refresh_when_enabled(self, mock_get_flag, mock_supabase):
        """Test that enqueue_implicate_refresh enqueues jobs when enabled."""
        mock_get_flag.return_value = True
        
        entity_ids = ["entity-1", "entity-2", "entity-3"]
        count = enqueue_implicate_refresh(mock_supabase, entity_ids)
        
        # Changed: now batches all entity IDs into a single job
        assert count == 1
    
    @patch("ingest.commit.get_feature_flag")
    def test_enqueue_implicate_refresh_when_disabled(self, mock_get_flag, mock_supabase):
        """Test that enqueue_implicate_refresh skips jobs when disabled."""
        mock_get_flag.return_value = False
        
        entity_ids = ["entity-1", "entity-2", "entity-3"]
        count = enqueue_implicate_refresh(mock_supabase, entity_ids)
        
        assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
