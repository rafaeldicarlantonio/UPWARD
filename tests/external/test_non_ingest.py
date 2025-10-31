"""
Tests for external content persistence prevention.

Verifies that external content (with provenance URLs) cannot be persisted
to internal storage (memories, entities, edges).
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import logging

# Set up mock environment variables
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
os.environ.setdefault("PINECONE_EXPLICATE_INDEX", "test-explicate")
os.environ.setdefault("PINECONE_IMPLICATE_INDEX", "test-implicate")

from core.guards import (
    forbid_external_persistence,
    ExternalPersistenceError,
    check_for_external_content,
    filter_external_items,
    _is_external_item,
    _extract_url
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def internal_items():
    """Sample internal items (no external markers)."""
    return [
        {
            "id": "mem_123",
            "text": "Internal content",
            "type": "memory"
        },
        {
            "id": "ent_456",
            "name": "Internal Entity",
            "type": "entity"
        }
    ]


@pytest.fixture
def external_items():
    """Sample external items (with provenance URLs)."""
    return [
        {
            "id": "ext_1",
            "text": "Wikipedia content",
            "provenance": {
                "url": "https://en.wikipedia.org/wiki/Test",
                "fetched_at": "2025-10-30T12:00:00Z"
            }
        },
        {
            "id": "ext_2",
            "text": "arXiv content",
            "provenance": {
                "url": "https://arxiv.org/abs/1234.5678",
                "fetched_at": "2025-10-30T12:05:00Z"
            }
        }
    ]


@pytest.fixture
def mixed_items(internal_items, external_items):
    """Mix of internal and external items."""
    return internal_items + external_items


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    with patch('core.guards.audit_logger') as mock_logger:
        yield mock_logger


# ============================================================================
# Basic Guard Tests
# ============================================================================

class TestForbidExternalPersistence:
    """Test basic forbid_external_persistence function."""
    
    def test_allows_internal_items_only(self, internal_items):
        """Test that internal items pass the guard."""
        result = forbid_external_persistence(internal_items)
        
        assert result["checked"] == 2
        assert result["external_count"] == 0
        assert result["internal_count"] == 2
        assert result["allowed"] is True
        assert result["external_items"] == []
    
    def test_blocks_external_items(self, external_items, mock_audit_logger):
        """Test that external items are blocked and raise exception."""
        with pytest.raises(ExternalPersistenceError) as exc_info:
            forbid_external_persistence(external_items)
        
        assert "Cannot persist external content" in str(exc_info.value)
        assert "2 external" in str(exc_info.value)
        
        # Verify audit log was called
        assert mock_audit_logger.warning.called
    
    def test_blocks_mixed_items(self, mixed_items, mock_audit_logger):
        """Test that mixed items (with any external) are blocked."""
        with pytest.raises(ExternalPersistenceError) as exc_info:
            forbid_external_persistence(mixed_items)
        
        assert "2 external" in str(exc_info.value)
    
    def test_empty_list_allowed(self):
        """Test that empty list is allowed."""
        result = forbid_external_persistence([])
        
        assert result["checked"] == 0
        assert result["allowed"] is True
    
    def test_no_raise_mode_returns_report(self, external_items, mock_audit_logger):
        """Test that raise_on_external=False returns report without raising."""
        result = forbid_external_persistence(
            external_items,
            raise_on_external=False
        )
        
        assert result["checked"] == 2
        assert result["external_count"] == 2
        assert result["allowed"] is False
        assert len(result["external_items"]) == 2
        
        # Still logs audit
        assert mock_audit_logger.warning.called


# ============================================================================
# External Item Detection Tests
# ============================================================================

class TestExternalItemDetection:
    """Test detection of external items."""
    
    def test_detects_provenance_url(self):
        """Test detection via provenance.url."""
        item = {
            "id": "test",
            "provenance": {"url": "https://example.com"}
        }
        assert _is_external_item(item) is True
    
    def test_detects_source_url(self):
        """Test detection via source_url field."""
        item = {
            "id": "test",
            "source_url": "https://example.com"
        }
        assert _is_external_item(item) is True
    
    def test_detects_external_flag(self):
        """Test detection via external=True flag."""
        item = {
            "id": "test",
            "external": True
        }
        assert _is_external_item(item) is True
    
    def test_detects_metadata_external(self):
        """Test detection via metadata.external."""
        item = {
            "id": "test",
            "metadata": {"external": True}
        }
        assert _is_external_item(item) is True
    
    def test_detects_metadata_url(self):
        """Test detection via metadata.url."""
        item = {
            "id": "test",
            "metadata": {"url": "https://example.com"}
        }
        assert _is_external_item(item) is True
    
    def test_internal_item_not_detected(self):
        """Test that internal items are not detected as external."""
        item = {
            "id": "mem_123",
            "text": "Internal content",
            "metadata": {"source": "upload"}
        }
        assert _is_external_item(item) is False
    
    def test_external_false_not_detected(self):
        """Test that external=False is not detected as external."""
        item = {
            "id": "test",
            "external": False
        }
        assert _is_external_item(item) is False


# ============================================================================
# URL Extraction Tests
# ============================================================================

class TestURLExtraction:
    """Test URL extraction from external items."""
    
    def test_extract_from_provenance(self):
        """Test extraction from provenance.url."""
        item = {
            "provenance": {"url": "https://example.com/page"}
        }
        assert _extract_url(item) == "https://example.com/page"
    
    def test_extract_from_source_url(self):
        """Test extraction from source_url."""
        item = {
            "source_url": "https://example.com/page"
        }
        assert _extract_url(item) == "https://example.com/page"
    
    def test_extract_from_metadata(self):
        """Test extraction from metadata.url."""
        item = {
            "metadata": {"url": "https://example.com/page"}
        }
        assert _extract_url(item) == "https://example.com/page"
    
    def test_no_url_returns_none(self):
        """Test that items without URLs return None."""
        item = {"id": "test"}
        assert _extract_url(item) is None
    
    def test_provenance_priority(self):
        """Test that provenance.url takes priority."""
        item = {
            "provenance": {"url": "https://primary.com"},
            "source_url": "https://secondary.com"
        }
        assert _extract_url(item) == "https://primary.com"


# ============================================================================
# Multiple Content Types Tests
# ============================================================================

class TestCheckForExternalContent:
    """Test checking multiple content types."""
    
    def test_check_all_internal(self, internal_items):
        """Test checking all internal content."""
        result = check_for_external_content(
            memories=internal_items,
            entities=internal_items,
            edges=internal_items
        )
        
        assert result["total_external"] == 0
        assert result["allowed"] is True
        assert result["memories"]["external_count"] == 0
        assert result["entities"]["external_count"] == 0
        assert result["edges"]["external_count"] == 0
    
    def test_check_external_memories(self, internal_items, external_items):
        """Test blocking external memories."""
        with pytest.raises(ExternalPersistenceError):
            check_for_external_content(
                memories=external_items,
                entities=internal_items,
                edges=internal_items
            )
    
    def test_check_external_entities(self, internal_items, external_items):
        """Test blocking external entities."""
        with pytest.raises(ExternalPersistenceError):
            check_for_external_content(
                memories=internal_items,
                entities=external_items,
                edges=internal_items
            )
    
    def test_check_external_edges(self, internal_items, external_items):
        """Test blocking external edges."""
        with pytest.raises(ExternalPersistenceError):
            check_for_external_content(
                memories=internal_items,
                entities=internal_items,
                edges=external_items
            )
    
    def test_check_no_raise_mode(self, internal_items, external_items):
        """Test no-raise mode returns complete report."""
        result = check_for_external_content(
            memories=internal_items,
            entities=external_items,
            edges=internal_items,
            raise_on_external=False
        )
        
        assert result["total_external"] == 2
        assert result["allowed"] is False
        assert result["memories"]["allowed"] is True
        assert result["entities"]["allowed"] is False
        assert result["edges"]["allowed"] is True
    
    def test_check_none_types_skipped(self):
        """Test that None types are skipped."""
        result = check_for_external_content(
            memories=None,
            entities=None,
            edges=None
        )
        
        assert result["total_external"] == 0
        assert result["allowed"] is True
        assert "memories" not in result
        assert "entities" not in result
        assert "edges" not in result


# ============================================================================
# Filter Items Tests
# ============================================================================

class TestFilterExternalItems:
    """Test filtering internal vs external items."""
    
    def test_filter_all_internal(self, internal_items):
        """Test filtering when all items are internal."""
        internal, external = filter_external_items(internal_items)
        
        assert len(internal) == 2
        assert len(external) == 0
    
    def test_filter_all_external(self, external_items):
        """Test filtering when all items are external."""
        internal, external = filter_external_items(external_items)
        
        assert len(internal) == 0
        assert len(external) == 2
    
    def test_filter_mixed_items(self, mixed_items):
        """Test filtering mixed items."""
        internal, external = filter_external_items(mixed_items)
        
        assert len(internal) == 2
        assert len(external) == 2
    
    def test_filter_empty_list(self):
        """Test filtering empty list."""
        internal, external = filter_external_items([])
        
        assert len(internal) == 0
        assert len(external) == 0


# ============================================================================
# Audit Logging Tests
# ============================================================================

class TestAuditLogging:
    """Test audit logging functionality."""
    
    def test_audit_log_on_block(self, external_items, mock_audit_logger):
        """Test that audit log is created when blocking."""
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items)
        
        # Verify audit logger was called
        assert mock_audit_logger.warning.called
        
        # Check call arguments
        call_args = mock_audit_logger.warning.call_args
        assert "BLOCKED" in call_args[0][0]
        
        # Check extra fields
        extra = call_args[1]["extra"]
        assert extra["event"] == "external_persistence_blocked"
        assert extra["external_count"] == 2
        assert extra["severity"] == "high"
        assert len(extra["external_items"]) == 2
    
    def test_audit_includes_urls(self, external_items, mock_audit_logger):
        """Test that audit log includes URLs of blocked items."""
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items, item_type="memory")
        
        call_args = mock_audit_logger.warning.call_args
        extra = call_args[1]["extra"]
        external_items_logged = extra["external_items"]
        
        # Check URLs are present
        urls = [item["url"] for item in external_items_logged]
        assert "https://en.wikipedia.org/wiki/Test" in urls
        assert "https://arxiv.org/abs/1234.5678" in urls
    
    def test_audit_includes_item_type(self, external_items, mock_audit_logger):
        """Test that audit log includes item type."""
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items, item_type="entity")
        
        call_args = mock_audit_logger.warning.call_args
        extra = call_args[1]["extra"]
        assert extra["item_type"] == "entity"


# ============================================================================
# Integration with Ingest Pipeline Tests
# ============================================================================

class TestIngestPipelineIntegration:
    """Test integration with ingest pipeline."""
    
    def test_commit_analysis_guards_external(self):
        """Test that commit_analysis calls the guard."""
        from ingest.commit import commit_analysis, AnalysisResult
        from core.guards import ExternalPersistenceError
        from nlp.frames import EventFrame
        
        # Create mock Supabase client
        mock_sb = Mock()
        mock_sb.table = Mock(return_value=Mock(
            select=Mock(return_value=Mock(
                eq=Mock(return_value=Mock(
                    execute=Mock(return_value=Mock(data=[]))
                ))
            )),
            insert=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[{"id": "test"}]))
            )),
            upsert=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[{"id": "test"}]))
            ))
        ))
        
        # Create sample analysis
        analysis = AnalysisResult(
            predicates=[],
            frames=[],
            concepts=[],
            contradictions=[]
        )
        
        # Source items with external marker
        source_items = [
            {
                "id": "ext_1",
                "provenance": {"url": "https://example.com"}
            }
        ]
        
        # Should raise when external items present
        with pytest.raises(ExternalPersistenceError) as exc_info:
            commit_analysis(
                mock_sb,
                analysis,
                source_items=source_items
            )
        
        # Verify error message
        assert "Cannot persist external content" in str(exc_info.value)
    
    def test_upsert_memories_guards_external(self):
        """Test that upsert_memories_from_chunks calls the guard."""
        from ingest.pipeline import upsert_memories_from_chunks
        from core.guards import ExternalPersistenceError
        
        # Create mocks
        mock_sb = Mock()
        mock_pinecone = Mock()
        mock_embedder = Mock()
        
        # Source metadata with external marker
        source_metadata = {
            "source": "external",
            "provenance": {"url": "https://example.com"}
        }
        
        # Should raise when external metadata present
        with pytest.raises(ExternalPersistenceError) as exc_info:
            upsert_memories_from_chunks(
                sb=mock_sb,
                pinecone_index=mock_pinecone,
                embedder=mock_embedder,
                file_id="test",
                title_prefix="Test",
                chunks=["Test chunk"],
                source_metadata=source_metadata
            )
        
        # Verify error message
        assert "Cannot persist external content" in str(exc_info.value)


# ============================================================================
# Error Message Tests
# ============================================================================

class TestErrorMessages:
    """Test error message content."""
    
    def test_error_message_includes_count(self, external_items):
        """Test that error message includes item count."""
        with pytest.raises(ExternalPersistenceError) as exc_info:
            forbid_external_persistence(external_items)
        
        error_msg = str(exc_info.value)
        assert "2 external" in error_msg
    
    def test_error_message_includes_type(self, external_items):
        """Test that error message includes item type."""
        with pytest.raises(ExternalPersistenceError) as exc_info:
            forbid_external_persistence(external_items, item_type="entity")
        
        error_msg = str(exc_info.value)
        assert "entity" in error_msg
    
    def test_error_message_explains_restriction(self, external_items):
        """Test that error message explains the restriction."""
        with pytest.raises(ExternalPersistenceError) as exc_info:
            forbid_external_persistence(external_items)
        
        error_msg = str(exc_info.value)
        assert "Cannot persist external content" in error_msg
        assert "provenance URLs" in error_msg


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================

class TestAcceptanceCriteria:
    """Verify all acceptance criteria."""
    
    def test_external_write_blocked(self, external_items, mock_audit_logger):
        """
        Acceptance: External items with provenance.url are blocked.
        """
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items)
    
    def test_internal_write_succeeds(self, internal_items):
        """
        Acceptance: Internal-only writes still succeed.
        """
        result = forbid_external_persistence(internal_items)
        assert result["allowed"] is True
    
    def test_audit_log_recorded(self, external_items, mock_audit_logger):
        """
        Acceptance: Audit log entry is recorded on block.
        """
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items)
        
        # Verify audit entry created
        assert mock_audit_logger.warning.called
        
        # Verify audit contains required fields
        call_args = mock_audit_logger.warning.call_args
        extra = call_args[1]["extra"]
        assert "event" in extra
        assert "external_count" in extra
        assert "external_items" in extra
        assert "severity" in extra
    
    def test_guard_prevents_memory_writes(self, external_items):
        """
        Acceptance: Guard prevents external items from being written to memories.
        """
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items, item_type="memory")
    
    def test_guard_prevents_entity_writes(self, external_items):
        """
        Acceptance: Guard prevents external items from being written to entities.
        """
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items, item_type="entity")
    
    def test_guard_prevents_edge_writes(self, external_items):
        """
        Acceptance: Guard prevents external items from being written to edges.
        """
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items, item_type="edge")


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_item_without_id(self):
        """Test handling items without id field."""
        items = [
            {
                "text": "Content",
                "provenance": {"url": "https://example.com"}
            }
        ]
        
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(items)
    
    def test_provenance_without_url(self):
        """Test that provenance without URL is not flagged as external."""
        items = [
            {
                "id": "test",
                "provenance": {"fetched_at": "2025-10-30T12:00:00Z"}
            }
        ]
        
        result = forbid_external_persistence(items)
        assert result["allowed"] is True
    
    def test_empty_url_string(self):
        """Test that empty URL string is not flagged as external."""
        items = [
            {
                "id": "test",
                "provenance": {"url": ""}
            }
        ]
        
        result = forbid_external_persistence(items)
        assert result["allowed"] is True
    
    def test_null_provenance(self):
        """Test handling of null provenance."""
        items = [
            {
                "id": "test",
                "provenance": None
            }
        ]
        
        result = forbid_external_persistence(items)
        assert result["allowed"] is True
    
    def test_large_batch_of_external_items(self):
        """Test handling large batches of external items."""
        items = [
            {
                "id": f"ext_{i}",
                "provenance": {"url": f"https://example.com/{i}"}
            }
            for i in range(100)
        ]
        
        with pytest.raises(ExternalPersistenceError) as exc_info:
            forbid_external_persistence(items)
        
        assert "100 external" in str(exc_info.value)


# ============================================================================
# Summary Test
# ============================================================================

class TestComprehensiveSummary:
    """Comprehensive test of all guardrail requirements."""
    
    def test_complete_guardrail_flow(self, internal_items, external_items, mock_audit_logger):
        """Test complete flow: detect, block, audit."""
        # 1. Internal items should pass
        result_internal = forbid_external_persistence(internal_items)
        assert result_internal["allowed"] is True
        
        # 2. External items should be blocked
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(external_items)
        
        # 3. Audit should be logged
        assert mock_audit_logger.warning.called
        
        # 4. Mixed items should be blocked
        mixed = internal_items + external_items
        with pytest.raises(ExternalPersistenceError):
            forbid_external_persistence(mixed)
        
        # 5. Filter should separate correctly
        internal_filtered, external_filtered = filter_external_items(mixed)
        assert len(internal_filtered) == 2
        assert len(external_filtered) == 2
        
        # 6. Filtered internal items should pass
        result_filtered = forbid_external_persistence(internal_filtered)
        assert result_filtered["allowed"] is True
