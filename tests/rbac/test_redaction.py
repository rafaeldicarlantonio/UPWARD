"""
Tests for role-aware redaction of chat payloads.

Verifies that sensitive information is properly redacted based on user roles
and that role_applied field is included for audit purposes.
"""

import pytest
from copy import deepcopy

from core.presenters import (
    redact_message,
    redact_chat_response,
    redact_ledger,
    redact_provenance,
    redact_sensitive_text,
    get_max_ledger_lines,
    should_show_provenance,
)
from core.rbac import (
    ROLE_GENERAL,
    ROLE_PRO,
    ROLE_SCHOLARS,
    ROLE_ANALYTICS,
    ROLE_OPS,
)


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_provenance():
    """Sample provenance data with sensitive information."""
    return {
        "source_type": "database",
        "db_ref": "memories.id:abc-123-def",
        "internal_id": "uuid:550e8400-e29b-41d4-a716-446655440000",
        "processing_trace": ["step1", "step2", "step3"],
        "metadata": {
            "timestamp": "2025-10-30T12:00:00Z",
            "processor": "internal:v2/processor",
            "trace_id": "__trace_123__"
        }
    }


@pytest.fixture
def sample_ledger():
    """Sample ledger data."""
    return [
        "Step 1: Query received",
        "Step 2: Embedding generated",
        "Step 3: Vector search id:abc-123",
        "Step 4: Reranking with db.memories ref:xyz-789",
        "Step 5: LLM invocation internal:gpt-4",
        "Step 6: Response generated __marker_456__",
        "Step 7: Post-processing",
        "Step 8: Final validation",
        "Step 9: Response formatted",
        "Step 10: Delivery prepared",
        "Step 11: Audit log written",
        "Step 12: Complete"
    ]


@pytest.fixture
def sample_message(sample_provenance, sample_ledger):
    """Sample message with all fields."""
    return {
        "id": "msg-123",
        "content": "This is a test message with id:abc-123 and db.table_ref",
        "role": "assistant",
        "provenance": sample_provenance,
        "ledger": sample_ledger,
        "process_trace": sample_ledger[:5],
        "metadata": {
            "timestamp": "2025-10-30T12:00:00Z",
            "internal_id": "internal-456",
            "db_ref": "messages:msg-123",
            "processing_id": "proc-789",
            "public_field": "visible"
        }
    }


@pytest.fixture
def sample_chat_response(sample_message):
    """Sample chat response structure."""
    return {
        "session_id": "session-123",
        "answer": "This is the answer",
        "citations": ["mem-1", "mem-2"],
        "message": sample_message,
        "messages": [sample_message, deepcopy(sample_message)],
        "context": [
            {
                "id": "mem-1",
                "text": "Context with id:xyz-789",
                "provenance": {"source": "db.memories"}
            },
            {
                "id": "mem-2",
                "text": "More context",
                "ledger": ["Step 1", "Step 2", "Step 3"]
            }
        ],
        "metrics": {
            "latency_ms": 250,
            "retrieval_ms": 100
        }
    }


# ============================================================================
# Ledger Redaction Tests
# ============================================================================

class TestLedgerRedaction:
    """Test ledger redaction based on role."""
    
    def test_general_gets_complete_redaction(self, sample_ledger):
        """General users should see complete ledger redaction."""
        result = redact_ledger(sample_ledger, [ROLE_GENERAL])
        
        assert isinstance(result, str)
        assert "REDACTED" in result
        assert "Upgrade to Pro" in result
        assert "id:abc-123" not in str(result)
    
    def test_pro_gets_limited_ledger(self, sample_ledger):
        """Pro users should see limited ledger (10 lines)."""
        result = redact_ledger(sample_ledger, [ROLE_PRO])
        
        assert isinstance(result, list)
        assert len(result) <= 11  # 10 lines + "more entries" message
        assert result[0] == sample_ledger[0]
        if len(result) == 11:
            assert "more entries" in result[-1]
    
    def test_scholars_gets_limited_ledger(self, sample_ledger):
        """Scholars users should see limited ledger (10 lines)."""
        result = redact_ledger(sample_ledger, [ROLE_SCHOLARS])
        
        assert isinstance(result, list)
        assert len(result) <= 11
    
    def test_analytics_gets_full_ledger(self, sample_ledger):
        """Analytics users should see full ledger."""
        result = redact_ledger(sample_ledger, [ROLE_ANALYTICS])
        
        assert result == sample_ledger
        assert len(result) == len(sample_ledger)
    
    def test_ops_gets_full_ledger(self, sample_ledger):
        """Ops users should see full ledger."""
        result = redact_ledger(sample_ledger, [ROLE_OPS])
        
        assert result == sample_ledger
    
    def test_string_ledger_redaction(self):
        """Test redaction of string ledger."""
        string_ledger = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        
        # General gets redacted
        result = redact_ledger(string_ledger, [ROLE_GENERAL])
        assert "REDACTED" in result
        
        # Analytics gets full
        result = redact_ledger(string_ledger, [ROLE_ANALYTICS])
        assert result == string_ledger
    
    def test_none_ledger_handling(self):
        """Test handling of None ledger."""
        result = redact_ledger(None, [ROLE_GENERAL])
        assert result is None
        
        result = redact_ledger(None, [ROLE_ANALYTICS])
        assert result is None


# ============================================================================
# Provenance Redaction Tests
# ============================================================================

class TestProvenanceRedaction:
    """Test provenance redaction based on role."""
    
    def test_general_gets_redacted_provenance(self, sample_provenance):
        """General users should see redacted provenance."""
        result = redact_provenance(sample_provenance, [ROLE_GENERAL])
        
        assert result is not None
        assert result.get("redacted") is True
        assert "Upgrade to Pro" in result.get("message", "")
        assert "db_ref" not in result
        assert "internal_id" not in result
    
    def test_pro_gets_full_provenance(self, sample_provenance):
        """Pro users should see full provenance."""
        result = redact_provenance(sample_provenance, [ROLE_PRO])
        
        assert result is not None
        assert result.get("redacted") is not True
        assert "db_ref" in result
        assert result["db_ref"] == sample_provenance["db_ref"]
    
    def test_scholars_gets_full_provenance(self, sample_provenance):
        """Scholars users should see full provenance."""
        result = redact_provenance(sample_provenance, [ROLE_SCHOLARS])
        
        assert result is not None
        assert "db_ref" in result
    
    def test_analytics_gets_full_provenance(self, sample_provenance):
        """Analytics users should see full provenance."""
        result = redact_provenance(sample_provenance, [ROLE_ANALYTICS])
        
        assert result == sample_provenance
    
    def test_none_provenance_handling(self):
        """Test handling of None provenance."""
        result = redact_provenance(None, [ROLE_GENERAL])
        assert result is None
        
        result = redact_provenance(None, [ROLE_ANALYTICS])
        assert result is None


# ============================================================================
# Sensitive Text Redaction Tests
# ============================================================================

class TestSensitiveTextRedaction:
    """Test sensitive pattern redaction."""
    
    def test_redact_database_ids(self):
        """Test redaction of database IDs."""
        text = "Found record id:abc-123-def in database"
        result = redact_sensitive_text(text)
        
        assert "id:abc-123-def" not in result
        assert "[REDACTED]" in result
    
    def test_redact_uuids(self):
        """Test redaction of UUIDs."""
        text = "UUID: uuid:550e8400-e29b-41d4-a716-446655440000"
        result = redact_sensitive_text(text)
        
        assert "uuid:550e8400" not in result
        assert "[REDACTED]" in result
    
    def test_redact_db_references(self):
        """Test redaction of database references."""
        text = "Query db.memories for results"
        result = redact_sensitive_text(text)
        
        assert "db.memories" not in result
        assert "[REDACTED]" in result
    
    def test_redact_internal_paths(self):
        """Test redaction of internal paths."""
        text = "Processing with internal:v2/processor/main"
        result = redact_sensitive_text(text)
        
        assert "internal:v2" not in result
        assert "[REDACTED]" in result
    
    def test_redact_internal_markers(self):
        """Test redaction of internal markers."""
        text = "Trace __marker_123__ captured"
        result = redact_sensitive_text(text)
        
        assert "__marker_123__" not in result
        assert "[REDACTED]" in result
    
    def test_preserves_normal_text(self):
        """Test that normal text is preserved."""
        text = "This is normal text without sensitive data"
        result = redact_sensitive_text(text)
        
        assert result == text
    
    def test_handles_empty_text(self):
        """Test handling of empty text."""
        assert redact_sensitive_text("") == ""
        assert redact_sensitive_text(None) is None


# ============================================================================
# Message Redaction Tests
# ============================================================================

class TestMessageRedaction:
    """Test complete message redaction."""
    
    def test_general_message_redaction(self, sample_message):
        """Test complete redaction for general users."""
        result = redact_message(sample_message, [ROLE_GENERAL])
        
        # role_applied should be set
        assert result["role_applied"] == ROLE_GENERAL
        
        # Ledger should be redacted
        assert isinstance(result["ledger"], str)
        assert "REDACTED" in result["ledger"]
        
        # Provenance should be redacted
        assert result["provenance"]["redacted"] is True
        
        # Sensitive metadata should be removed
        assert "internal_id" not in result["metadata"]
        assert "db_ref" not in result["metadata"]
        assert "processing_id" not in result["metadata"]
        assert "public_field" in result["metadata"]  # Public fields preserved
    
    def test_pro_message_redaction(self, sample_message):
        """Test redaction for pro users."""
        result = redact_message(sample_message, [ROLE_PRO])
        
        assert result["role_applied"] == ROLE_PRO
        
        # Ledger should be limited
        assert isinstance(result["ledger"], list)
        assert len(result["ledger"]) <= 11
        
        # Provenance should be visible (not redacted)
        assert result["provenance"].get("redacted") is not True
        assert "db_ref" in result["provenance"]
    
    def test_analytics_message_redaction(self, sample_message):
        """Test minimal redaction for analytics users."""
        result = redact_message(sample_message, [ROLE_ANALYTICS])
        
        assert result["role_applied"] == ROLE_ANALYTICS
        
        # Ledger should be full
        assert isinstance(result["ledger"], list)
        assert len(result["ledger"]) == len(sample_message["ledger"])
        
        # Provenance should be full
        assert result["provenance"] == sample_message["provenance"]
        
        # All metadata should be present
        assert "internal_id" in result["metadata"]
    
    def test_role_applied_field_always_present(self, sample_message):
        """Test that role_applied is always included."""
        for role in [ROLE_GENERAL, ROLE_PRO, ROLE_SCHOLARS, ROLE_ANALYTICS, ROLE_OPS]:
            result = redact_message(sample_message, [role])
            assert "role_applied" in result
            assert result["role_applied"] == role


# ============================================================================
# Chat Response Redaction Tests
# ============================================================================

class TestChatResponseRedaction:
    """Test complete chat response redaction."""
    
    def test_general_chat_response_redaction(self, sample_chat_response):
        """Test chat response redaction for general users."""
        result = redact_chat_response(sample_chat_response, [ROLE_GENERAL])
        
        # Top-level role_applied
        assert result["role_applied"] == ROLE_GENERAL
        
        # Single message redacted
        assert result["message"]["role_applied"] == ROLE_GENERAL
        assert "REDACTED" in str(result["message"]["ledger"])
        
        # All messages in list redacted
        for msg in result["messages"]:
            assert msg["role_applied"] == ROLE_GENERAL
            assert "REDACTED" in str(msg["ledger"])
        
        # Context redacted
        for ctx in result["context"]:
            assert ctx["role_applied"] == ROLE_GENERAL
    
    def test_analytics_chat_response_minimal_redaction(self, sample_chat_response):
        """Test chat response for analytics users."""
        result = redact_chat_response(sample_chat_response, [ROLE_ANALYTICS])
        
        assert result["role_applied"] == ROLE_ANALYTICS
        
        # Messages should have full data
        assert isinstance(result["message"]["ledger"], list)
        assert len(result["message"]["ledger"]) > 10
    
    def test_response_structure_preserved(self, sample_chat_response):
        """Test that response structure is preserved."""
        result = redact_chat_response(sample_chat_response, [ROLE_GENERAL])
        
        # All top-level fields should still be present
        assert "session_id" in result
        assert "answer" in result
        assert "citations" in result
        assert "message" in result
        assert "messages" in result
        assert "context" in result
        assert "metrics" in result
        
        # Values should be preserved (except redacted parts)
        assert result["session_id"] == sample_chat_response["session_id"]
        assert result["answer"] == sample_chat_response["answer"]
        assert result["citations"] == sample_chat_response["citations"]
    
    def test_empty_chat_response(self):
        """Test redaction of empty response."""
        empty_response = {
            "session_id": "test",
            "answer": "",
            "citations": []
        }
        
        result = redact_chat_response(empty_response, [ROLE_GENERAL])
        
        assert result["role_applied"] == ROLE_GENERAL
        assert result["session_id"] == "test"


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Test helper functions."""
    
    def test_get_max_ledger_lines(self):
        """Test max ledger lines by role."""
        assert get_max_ledger_lines([ROLE_GENERAL]) == 0  # Redacted
        assert get_max_ledger_lines([ROLE_PRO]) == 10  # Limited
        assert get_max_ledger_lines([ROLE_SCHOLARS]) == 10  # Limited
        assert get_max_ledger_lines([ROLE_ANALYTICS]) == -1  # Unlimited
        assert get_max_ledger_lines([ROLE_OPS]) == -1  # Unlimited
    
    def test_should_show_provenance(self):
        """Test provenance visibility by role."""
        assert should_show_provenance([ROLE_GENERAL]) is False
        assert should_show_provenance([ROLE_PRO]) is True
        assert should_show_provenance([ROLE_SCHOLARS]) is True
        assert should_show_provenance([ROLE_ANALYTICS]) is True
        assert should_show_provenance([ROLE_OPS]) is True
    
    def test_multiple_roles_uses_highest(self):
        """Test that multiple roles use the highest level."""
        # General + Pro should use Pro level
        assert get_max_ledger_lines([ROLE_GENERAL, ROLE_PRO]) == 10
        assert should_show_provenance([ROLE_GENERAL, ROLE_PRO]) is True
        
        # Pro + Analytics should use Analytics level
        assert get_max_ledger_lines([ROLE_PRO, ROLE_ANALYTICS]) == -1


# ============================================================================
# Data Leakage Tests
# ============================================================================

class TestDataLeakage:
    """Test for data leakage vulnerabilities."""
    
    def test_no_sensitive_patterns_in_general_response(self, sample_chat_response):
        """Verify no sensitive patterns leak to general users."""
        result = redact_chat_response(sample_chat_response, [ROLE_GENERAL])
        
        # Convert entire response to string for pattern checking
        response_str = str(result)
        
        # These patterns should NOT appear in general user responses
        sensitive_patterns = [
            "db.memories",
            "id:abc-123",
            "uuid:",
            "internal:",
            "__marker",
            "__trace",
        ]
        
        for pattern in sensitive_patterns:
            assert pattern not in response_str, (
                f"Sensitive pattern '{pattern}' leaked in general user response"
            )
    
    def test_metadata_stripped_for_general(self, sample_message):
        """Verify sensitive metadata is removed for general users."""
        result = redact_message(sample_message, [ROLE_GENERAL])
        
        # Sensitive metadata should be removed
        assert "internal_id" not in result["metadata"]
        assert "db_ref" not in result["metadata"]
        assert "processing_id" not in result["metadata"]
        assert "trace_id" not in result.get("metadata", {})
        
        # Public metadata should remain
        assert "public_field" in result["metadata"]
    
    def test_full_ledger_not_exposed_to_general(self, sample_message):
        """Verify full ledger is not exposed to general users."""
        original_length = len(sample_message["ledger"])
        result = redact_message(sample_message, [ROLE_GENERAL])
        
        # Should be completely redacted for general
        assert isinstance(result["ledger"], str)
        assert "REDACTED" in result["ledger"]
        
        # Original data should not be present
        for ledger_entry in sample_message["ledger"]:
            assert ledger_entry not in str(result["ledger"])
    
    def test_provenance_completely_redacted_for_general(self, sample_message):
        """Verify provenance is completely redacted for general users."""
        result = redact_message(sample_message, [ROLE_GENERAL])
        
        # Should only have redaction message
        assert result["provenance"]["redacted"] is True
        assert "db_ref" not in result["provenance"]
        assert "internal_id" not in result["provenance"]
        assert "processing_trace" not in result["provenance"]


# ============================================================================
# Role Permutation Tests
# ============================================================================

class TestRolePermutations:
    """Test all role permutations for correct behavior."""
    
    @pytest.mark.parametrize("role,has_provenance,ledger_type", [
        (ROLE_GENERAL, False, str),  # Redacted provenance, redacted ledger
        (ROLE_PRO, True, list),  # Full provenance, limited ledger
        (ROLE_SCHOLARS, True, list),  # Full provenance, limited ledger
        (ROLE_ANALYTICS, True, list),  # Full provenance, full ledger
        (ROLE_OPS, True, list),  # Full provenance, full ledger
    ])
    def test_role_redaction_matrix(self, sample_message, role, has_provenance, ledger_type):
        """Test redaction matrix for all roles."""
        result = redact_message(sample_message, [role])
        
        # Check role_applied
        assert result["role_applied"] == role
        
        # Check provenance
        if has_provenance:
            assert result["provenance"].get("redacted") is not True
            assert "db_ref" in result["provenance"]
        else:
            assert result["provenance"]["redacted"] is True
        
        # Check ledger type
        assert isinstance(result["ledger"], ledger_type)
        
        # Check ledger content
        if ledger_type is str:
            assert "REDACTED" in result["ledger"]
        else:
            # List ledger should have content
            assert len(result["ledger"]) > 0


# ============================================================================
# Audit Field Tests
# ============================================================================

class TestAuditFields:
    """Test role_applied field for audit purposes."""
    
    def test_role_applied_in_message(self, sample_message):
        """Test role_applied field in message."""
        for role in [ROLE_GENERAL, ROLE_PRO, ROLE_ANALYTICS]:
            result = redact_message(sample_message, [role])
            assert "role_applied" in result
            assert result["role_applied"] == role
    
    def test_role_applied_in_response(self, sample_chat_response):
        """Test role_applied field in chat response."""
        result = redact_chat_response(sample_chat_response, [ROLE_PRO])
        
        # Top-level role_applied
        assert result["role_applied"] == ROLE_PRO
        
        # Message-level role_applied
        assert result["message"]["role_applied"] == ROLE_PRO
        
        # All messages have role_applied
        for msg in result["messages"]:
            assert "role_applied" in msg
            assert msg["role_applied"] == ROLE_PRO
        
        # All context items have role_applied
        for ctx in result["context"]:
            assert "role_applied" in ctx
    
    def test_role_applied_survives_deep_copy(self, sample_message):
        """Test that role_applied field persists through processing."""
        result1 = redact_message(sample_message, [ROLE_GENERAL])
        result2 = deepcopy(result1)
        
        assert result2["role_applied"] == ROLE_GENERAL
