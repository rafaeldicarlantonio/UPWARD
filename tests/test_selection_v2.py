# tests/test_selection_v2.py — tests for the new selection system

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from core.selection import (
    SelectionStrategy, LegacySelector, DualSelector, SelectionFactory, 
    select_content, SelectionResult
)
from core.ranking import LiftScoreRanker, LiftScoreWeights, LegacyRanker

# Test fixtures
@pytest.fixture
def sample_embedding():
    return [0.1, 0.2, 0.3, 0.4, 0.5] * 300  # Mock 1536-dim embedding

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('app.services.vector_store.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            PINECONE_EXPLICATE_INDEX="test-explicate",
            PINECONE_IMPLICATE_INDEX="test-implicate"
        )
        yield mock_settings

@pytest.fixture
def sample_explicate_hits():
    """Mock explicate index hits."""
    hits = []
    for i in range(3):
        hit = Mock()
        hit.id = f"explicate-{i}"
        hit.score = 0.9 - i * 0.1
        hit.metadata = {
            "text": f"Explicate content {i}",
            "title": f"Explicate Title {i}",
            "created_at": "2024-01-01T00:00:00Z",
            "type": "semantic"
        }
        hits.append(hit)
    return hits

@pytest.fixture
def sample_implicate_hits():
    """Mock implicate index hits."""
    hits = []
    for i in range(2):
        hit = Mock()
        hit.id = f"concept:entity-{i}"
        hit.score = 0.8 - i * 0.1
        hit.metadata = {
            "entity_id": f"entity-{i}",
            "entity_name": f"Concept {i}",
            "created_at": "2024-01-01T00:00:00Z",
            "relations": [("related_to", f"Related {i}", 0.9)],
            "source_memory_ids": [f"memory-{i}-1", f"memory-{i}-2"]
        }
        hits.append(hit)
    return hits

@pytest.fixture
def sample_records():
    """Sample records for testing."""
    return [
        {
            "id": "record-1",
            "text": "Test content 1",
            "title": "Test Title 1",
            "created_at": "2024-01-01T00:00:00Z",
            "type": "semantic",
            "score": 0.9,
            "metadata": {"role_view": "general"}
        },
        {
            "id": "record-2", 
            "text": "Test content 2",
            "title": "Test Title 2",
            "created_at": "2024-01-02T00:00:00Z",
            "type": "episodic",
            "score": 0.8,
            "metadata": {"role_view": "pro"}
        }
    ]

class TestLegacySelector:
    """Test the LegacySelector class."""
    
    def test_init(self, mock_settings):
        """Test LegacySelector initialization."""
        selector = LegacySelector()
        assert selector.vector_store is not None
    
    def test_select_basic(self, sample_embedding, sample_explicate_hits, mock_settings):
        """Test basic selection functionality."""
        with patch.object(LegacySelector, '_legacy_rank_and_pack') as mock_rank:
            mock_rank.return_value = {
                "context": [{"id": "test", "title": "Test", "text": "content"}],
                "ranked_ids": ["test"]
            }
            
            selector = LegacySelector()
            selector.vector_store = Mock()
            selector.vector_store.query_explicit.return_value.matches = sample_explicate_hits
            
            result = selector.select("test query", sample_embedding, "general")
            
            assert isinstance(result, SelectionResult)
            assert result.strategy_used == "legacy"
            assert len(result.context) == 1
            assert len(result.reasons) == 1
            assert "Legacy ranking" in result.reasons[0]
    
    def test_legacy_rank_and_pack(self, mock_settings):
        """Test legacy ranking and packing."""
        selector = LegacySelector()
        
        records = [
            {
                "id": "r1",
                "text": "Content 1",
                "title": "Title 1", 
                "created_at": "2024-01-01T00:00:00Z",
                "score": 0.9,
                "type": "semantic"
            },
            {
                "id": "r2",
                "text": "Content 2",
                "title": "Title 2",
                "created_at": "2024-01-02T00:00:00Z", 
                "score": 0.8,
                "type": "episodic"
            }
        ]
        
        result = selector._legacy_rank_and_pack(records, "test query")
        
        assert "context" in result
        assert "ranked_ids" in result
        assert len(result["context"]) == 2
        assert len(result["ranked_ids"]) == 2
        assert result["ranked_ids"][0] == "r1"  # Higher score first

class TestDualSelector:
    """Test the DualSelector class."""
    
    def test_init(self, mock_settings):
        """Test DualSelector initialization."""
        selector = DualSelector()
        assert selector.vector_store is not None
        assert selector.ranker is not None
        assert selector._db_adapter is None  # Lazy loaded
    
    def test_select_basic(self, sample_embedding, sample_explicate_hits, sample_implicate_hits, mock_settings):
        """Test basic dual selection functionality."""
        with patch.object(DualSelector, '_process_explicate_hits') as mock_explicate, \
             patch.object(DualSelector, '_process_implicate_hits') as mock_implicate, \
             patch.object(DualSelector, '_deduplicate_records') as mock_dedup:
            
            mock_explicate.return_value = [{"id": "ex-1", "source": "explicate"}]
            mock_implicate.return_value = [{"id": "im-1", "source": "implicate"}]
            mock_dedup.return_value = [{"id": "ex-1"}, {"id": "im-1"}]
            
            selector = DualSelector()
            selector.vector_store = Mock()
            selector.vector_store.query_explicit.return_value.matches = sample_explicate_hits
            selector.vector_store.query_implicate.return_value.matches = sample_implicate_hits
            
            # Mock the ranker
            selector.ranker = Mock()
            selector.ranker.rank_and_pack.return_value = {
                "context": [{"id": "ex-1", "title": "Test"}],
                "ranked_ids": ["ex-1"]
            }
            
            result = selector.select("test query", sample_embedding, "general")
            
            assert isinstance(result, SelectionResult)
            assert result.strategy_used == "dual"
            assert "explicate_hits" in result.metadata
            assert "implicate_hits" in result.metadata
    
    def test_process_explicate_hits(self, sample_explicate_hits, mock_settings):
        """Test processing explicate hits."""
        selector = DualSelector()
        records = selector._process_explicate_hits(sample_explicate_hits)
        
        assert len(records) == 3
        assert records[0]["id"] == "explicate-0"
        assert records[0]["source"] == "explicate"
        assert records[0]["score"] == 0.9
    
    def test_process_implicate_hits(self, sample_implicate_hits, mock_settings):
        """Test processing implicate hits."""
        with patch.object(DualSelector, '_expand_implicate_content') as mock_expand:
            mock_expand.return_value = {
                "summary": "Test concept summary",
                "relations": [("related_to", "AI", 0.9)],
                "memories": [{"id": "mem-1", "title": "Memory 1"}]
            }
            
            selector = DualSelector()
            records = selector._process_implicate_hits(sample_implicate_hits, "general")
            
            assert len(records) == 2
            assert records[0]["id"] == "implicate:entity-0"
            assert records[0]["source"] == "implicate"
            assert records[0]["text"] == "Test concept summary"
    
    def test_deduplicate_records(self, mock_settings):
        """Test record deduplication."""
        selector = DualSelector()
        
        records = [
            {"id": "r1", "metadata": {"file_id": "f1"}},
            {"id": "r2", "metadata": {"file_id": "f1"}},  # Same file
            {"id": "r3", "metadata": {"file_id": "f2"}},
            {"id": "r1", "metadata": {"file_id": "f1"}}   # Duplicate
        ]
        
        deduplicated = selector._deduplicate_records(records)
        assert len(deduplicated) == 3  # r1, r2, r3
    
    def test_generate_reasons(self, sample_explicate_hits, sample_implicate_hits, mock_settings):
        """Test reason generation."""
        selector = DualSelector()
        
        context = [
            {"id": "explicate-0", "title": "Test Explicate"},
            {"id": "implicate:entity-0", "title": "Test Concept"}
        ]
        
        reasons = selector._generate_reasons(context, sample_explicate_hits, sample_implicate_hits)
        
        assert len(reasons) == 2
        assert "Direct match" in reasons[0]
        assert "Concept expansion" in reasons[1]

class TestLiftScoreRanker:
    """Test the LiftScoreRanker class."""
    
    def test_init(self):
        """Test LiftScoreRanker initialization."""
        ranker = LiftScoreRanker()
        assert ranker.weights.alpha == 0.15
        assert ranker.weights.beta == 0.25
        assert ranker.weights.gamma == 0.35
        assert ranker.weights.delta == 0.25
    
    def test_init_custom_weights(self):
        """Test LiftScoreRanker with custom weights."""
        weights = LiftScoreWeights(alpha=0.2, beta=0.3, gamma=0.4, delta=0.1)
        ranker = LiftScoreRanker(weights)
        assert ranker.weights.alpha == 0.2
        assert ranker.weights.beta == 0.3
    
    def test_rank_and_pack(self, sample_records):
        """Test ranking and packing."""
        ranker = LiftScoreRanker()
        result = ranker.rank_and_pack(sample_records, "test query", "general")
        
        assert "context" in result
        assert "ranked_ids" in result
        assert len(result["context"]) == 2
        assert len(result["ranked_ids"]) == 2
        
        # Check that scoring breakdown is included
        for item in result["context"]:
            assert "scoring" in item
            assert "lift_score" in item["scoring"]
    
    def test_calculate_recency_score(self):
        """Test recency score calculation."""
        ranker = LiftScoreRanker()
        
        # Recent date
        recent_score = ranker._calculate_recency_score("2024-01-01T00:00:00Z")
        assert 0.0 <= recent_score <= 1.0
        
        # Old date
        old_score = ranker._calculate_recency_score("2020-01-01T00:00:00Z")
        assert old_score < recent_score
        
        # Invalid date
        invalid_score = ranker._calculate_recency_score("invalid")
        assert invalid_score == 0.5
    
    def test_calculate_graph_coherence(self):
        """Test graph coherence calculation."""
        ranker = LiftScoreRanker()
        
        # Non-implicate record
        non_implicate = {"source": "explicate"}
        assert ranker._calculate_graph_coherence(non_implicate) == 0.0
        
        # Implicate record with relations and memories
        implicate_record = {
            "source": "implicate",
            "metadata": {
                "relations": [("rel1", "entity1", 0.9), ("rel2", "entity2", 0.8)],
                "expanded_memories": [{"id": "mem1"}, {"id": "mem2"}]
            }
        }
        coherence = ranker._calculate_graph_coherence(implicate_record)
        assert 0.0 <= coherence <= 1.0
    
    def test_calculate_contradiction_penalty(self):
        """Test contradiction penalty calculation."""
        with patch('core.ranking.get_feature_flag') as mock_flag:
            mock_flag.return_value = True  # Enable contradictions_pack flag
            
            ranker = LiftScoreRanker()
            
            # No contradictions
            no_contradictions = {"metadata": {}}
            assert ranker._calculate_contradiction_penalty(no_contradictions) == 0.0
            
            # With contradictions
            with_contradictions = {
                "metadata": {
                    "contradictions": [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]
                }
            }
            penalty = ranker._calculate_contradiction_penalty(with_contradictions)
            assert penalty > 0.0
    
    def test_calculate_role_fit(self):
        """Test role fit calculation."""
        ranker = LiftScoreRanker()
        
        # No caller role
        assert ranker._calculate_role_fit({"metadata": {}}, None) == 0.5
        
        # Matching role
        record = {"metadata": {"role_view": "general"}}
        assert ranker._calculate_role_fit(record, "general") == 1.0
        
        # Higher privilege role
        assert ranker._calculate_role_fit(record, "pro") == 1.0
        
        # Lower privilege role (scholar is higher than general in hierarchy)
        assert ranker._calculate_role_fit(record, "scholar") == 1.0
        
        # Role view as list
        record_list = {"metadata": {"role_view": ["general", "pro"]}}
        assert ranker._calculate_role_fit(record_list, "general") == 1.0
        # Scholar should have access because "general" is in the list
        assert ranker._calculate_role_fit(record_list, "scholar") == 1.0
        
        # Test case where scholar should not have access
        record_restricted = {"metadata": {"role_view": ["pro", "analytics"]}}
        assert ranker._calculate_role_fit(record_restricted, "scholar") == 0.0

class TestLegacyRanker:
    """Test the LegacyRanker class."""
    
    def test_rank_and_pack(self, sample_records):
        """Test legacy ranking and packing."""
        ranker = LegacyRanker()
        result = ranker.rank_and_pack(sample_records, "test query", "general")
        
        assert "context" in result
        assert "ranked_ids" in result
        assert len(result["context"]) == 2
        assert len(result["ranked_ids"]) == 2

class TestSelectionFactory:
    """Test the SelectionFactory class."""
    
    def test_create_selector_legacy(self, mock_settings):
        """Test creating legacy selector when dual_index is off."""
        with patch('core.selection.get_feature_flag') as mock_flag:
            mock_flag.return_value = False
            
            selector = SelectionFactory.create_selector()
            assert isinstance(selector, LegacySelector)
    
    def test_create_selector_dual(self, mock_settings):
        """Test creating dual selector when dual_index is on."""
        with patch('core.selection.get_feature_flag') as mock_flag:
            mock_flag.return_value = True
            
            selector = SelectionFactory.create_selector()
            assert isinstance(selector, DualSelector)

class TestSelectContentFunction:
    """Test the convenience select_content function."""
    
    def test_select_content_legacy(self, sample_embedding):
        """Test select_content with legacy strategy."""
        with patch('core.selection.get_feature_flag') as mock_flag, \
             patch('core.selection.LegacySelector') as mock_selector_class:
            
            mock_flag.return_value = False
            mock_selector = Mock()
            mock_selector.select.return_value = SelectionResult(
                context=[{"id": "test"}],
                ranked_ids=["test"],
                reasons=["test reason"],
                strategy_used="legacy",
                metadata={}
            )
            mock_selector_class.return_value = mock_selector
            
            result = select_content("test query", sample_embedding, "general")
            
            assert isinstance(result, SelectionResult)
            assert result.strategy_used == "legacy"
            mock_selector.select.assert_called_once_with("test query", sample_embedding, "general")
    
    def test_select_content_dual(self, sample_embedding):
        """Test select_content with dual strategy."""
        with patch('core.selection.get_feature_flag') as mock_flag, \
             patch('core.selection.DualSelector') as mock_selector_class:
            
            mock_flag.return_value = True
            mock_selector = Mock()
            mock_selector.select.return_value = SelectionResult(
                context=[{"id": "test"}],
                ranked_ids=["test"],
                reasons=["test reason"],
                strategy_used="dual",
                metadata={}
            )
            mock_selector_class.return_value = mock_selector
            
            result = select_content("test query", sample_embedding, "general")
            
            assert isinstance(result, SelectionResult)
            assert result.strategy_used == "dual"
            mock_selector.select.assert_called_once_with("test query", sample_embedding, "general")

class TestIntegration:
    """Integration tests for the selection system."""
    
    def test_legacy_path_unchanged(self, sample_embedding):
        """Test that legacy path maintains existing behavior."""
        with patch('core.selection.get_feature_flag') as mock_flag, \
             patch('core.selection.LegacySelector') as mock_selector_class:
            
            mock_flag.return_value = False
            mock_selector = Mock()
            mock_selector.select.return_value = SelectionResult(
                context=[{"id": "legacy-test", "title": "Legacy", "text": "content"}],
                ranked_ids=["legacy-test"],
                reasons=["Legacy ranking: score=0.900"],
                strategy_used="legacy",
                metadata={"total_hits": 1}
            )
            mock_selector_class.return_value = mock_selector
            
            result = select_content("test query", sample_embedding, "general")
            
            # Verify legacy behavior is maintained
            assert result.strategy_used == "legacy"
            assert len(result.context) == 1
            assert result.context[0]["id"] == "legacy-test"
            assert "Legacy ranking" in result.reasons[0]
    
    def test_dual_path_new_behavior(self, sample_embedding):
        """Test that dual path provides new behavior."""
        with patch('core.selection.get_feature_flag') as mock_flag, \
             patch('core.selection.DualSelector') as mock_selector_class:
            
            mock_flag.return_value = True
            mock_selector = Mock()
            mock_selector.select.return_value = SelectionResult(
                context=[
                    {"id": "explicate-1", "title": "Direct Match", "text": "content"},
                    {"id": "implicate:entity-1", "title": "Concept: AI", "text": "AI concept"}
                ],
                ranked_ids=["explicate-1", "implicate:entity-1"],
                reasons=["Direct match: score=0.900", "Concept expansion: Concept: AI"],
                strategy_used="dual",
                metadata={"explicate_hits": 1, "implicate_hits": 1, "total_after_dedup": 2}
            )
            mock_selector_class.return_value = mock_selector
            
            result = select_content("test query", sample_embedding, "general")
            
            # Verify dual behavior
            assert result.strategy_used == "dual"
            assert len(result.context) == 2
            assert "explicate_hits" in result.metadata
            assert "implicate_hits" in result.metadata
            assert "Direct match" in result.reasons[0]
            assert "Concept expansion" in result.reasons[1]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])