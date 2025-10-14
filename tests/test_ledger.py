# tests/test_ledger.py — tests for rheomode_runs persistence and tracing

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

from core.ledger import (
    ProcessTrace, RheomodeRun, RheomodeLedger, 
    create_process_trace, log_chat_request
)

# Test fixtures
@pytest.fixture
def sample_process_trace():
    """Sample process trace for testing."""
    return ProcessTrace(
        flags={
            "retrieval.dual_index": True,
            "retrieval.liftscore": True,
            "retrieval.contradictions_pack": False
        },
        query="What is the policy on remote work?",
        candidates=[
            {
                "id": "mem-1",
                "title": "Remote Work Policy",
                "type": "semantic",
                "source": "explicate",
                "score": 0.85,
                "lift_score": 0.92,
                "reason": "Direct match: score=0.850",
                "has_contradictions": False
            },
            {
                "id": "mem-2",
                "title": "HR Guidelines",
                "type": "procedural",
                "source": "implicate",
                "score": 0.78,
                "lift_score": 0.88,
                "reason": "Concept expansion: HR Guidelines",
                "has_contradictions": True
            }
        ],
        contradictions=[
            {
                "subject": "Remote Work Policy",
                "claim_a": "Remote work is allowed",
                "claim_b": "Remote work is not allowed",
                "evidence_ids": ["mem-1", "mem-3"],
                "contradiction_type": "entity_predicate",
                "confidence": 0.8
            }
        ],
        timing={
            "total_ms": 1250.5,
            "retrieval_ms": 450.2,
            "graph_expansion_ms": 100.1,
            "llm_ms": 700.2
        },
        strategy_used="dual",
        metadata={
            "explicate_hits": 16,
            "implicate_hits": 8,
            "total_after_dedup": 20
        }
    )

@pytest.fixture
def sample_selection_result():
    """Sample selection result for testing."""
    mock_result = Mock()
    mock_result.context = [
        {
            "id": "mem-1",
            "title": "Remote Work Policy",
            "text": "Remote work is allowed for all employees",
            "type": "semantic",
            "source": "explicate",
            "score": 0.85,
            "lift_score": 0.92
        },
        {
            "id": "mem-2", 
            "title": "HR Guidelines",
            "text": "Follow company policies",
            "type": "procedural",
            "source": "implicate",
            "score": 0.78,
            "lift_score": 0.88
        }
    ]
    mock_result.ranked_ids = ["mem-1", "mem-2"]
    mock_result.reasons = ["Direct match: score=0.850", "Concept expansion: HR Guidelines"]
    mock_result.strategy_used = "dual"
    mock_result.metadata = {
        "explicate_hits": 16,
        "implicate_hits": 8,
        "total_after_dedup": 20
    }
    return mock_result

@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    client = Mock()
    
    # Mock table operations
    table_mock = Mock()
    client.table.return_value = table_mock
    
    # Mock insert operation
    insert_mock = Mock()
    table_mock.insert.return_value = insert_mock
    insert_mock.execute.return_value = Mock(data=[{"id": "test-run-id"}])
    
    # Mock select operation
    select_mock = Mock()
    table_mock.select.return_value = select_mock
    table_mock.eq.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.limit.return_value = table_mock
    
    # Mock query results
    select_mock.execute.return_value = Mock(data=[])
    
    return client

class TestProcessTrace:
    """Test the ProcessTrace dataclass."""
    
    def test_process_trace_creation(self, sample_process_trace):
        """Test creating a ProcessTrace instance."""
        trace = sample_process_trace
        
        assert trace.flags["retrieval.dual_index"] is True
        assert trace.query == "What is the policy on remote work?"
        assert len(trace.candidates) == 2
        assert len(trace.contradictions) == 1
        assert trace.timing["total_ms"] == 1250.5
        assert trace.strategy_used == "dual"
        assert trace.metadata["explicate_hits"] == 16

class TestRheomodeRun:
    """Test the RheomodeRun dataclass."""
    
    def test_rheomode_run_creation(self, sample_process_trace):
        """Test creating a RheomodeRun instance."""
        run = RheomodeRun(
            session_id="session-123",
            message_id="msg-456",
            role="user",
            process_trace=sample_process_trace,
            lift_score=0.9,
            contradiction_score=0.3
        )
        
        assert run.session_id == "session-123"
        assert run.message_id == "msg-456"
        assert run.role == "user"
        assert run.process_trace == sample_process_trace
        assert run.lift_score == 0.9
        assert run.contradiction_score == 0.3

class TestRheomodeLedger:
    """Test the RheomodeLedger class."""
    
    def test_init(self):
        """Test RheomodeLedger initialization."""
        with patch('core.ledger.get_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client
            
            ledger = RheomodeLedger()
            assert ledger.client == mock_client
    
    def test_create_run(self, sample_process_trace):
        """Test creating a rheomode run."""
        with patch('core.ledger.get_client'):
            ledger = RheomodeLedger()
            
            run = ledger.create_run(
                session_id="session-123",
                message_id="msg-456",
                role="user",
                process_trace=sample_process_trace,
                lift_score=0.9,
                contradiction_score=0.3
            )
            
            assert run.session_id == "session-123"
            assert run.message_id == "msg-456"
            assert run.role == "user"
            assert run.process_trace == sample_process_trace
            assert run.lift_score == 0.9
            assert run.contradiction_score == 0.3
            assert run.process_trace_summary is not None
            assert len(run.process_trace_summary.split('\n')) >= 2
    
    def test_persist_run(self, sample_process_trace, mock_supabase_client):
        """Test persisting a rheomode run."""
        with patch('core.ledger.get_client', return_value=mock_supabase_client):
            ledger = RheomodeLedger()
            
            run = ledger.create_run(
                session_id="session-123",
                process_trace=sample_process_trace
            )
            
            run_id = ledger.persist_run(run)
            
            assert run_id == "test-run-id"
            mock_supabase_client.table.assert_called_with("rheomode_runs")
            mock_supabase_client.table.return_value.insert.assert_called_once()
    
    def test_persist_run_failure(self, sample_process_trace):
        """Test persisting a rheomode run with failure."""
        with patch('core.ledger.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.table.return_value.insert.return_value.execute.return_value = Mock(data=[])
            mock_get_client.return_value = mock_client
            
            ledger = RheomodeLedger()
            run = ledger.create_run(session_id="session-123", process_trace=sample_process_trace)
            
            with pytest.raises(RuntimeError, match="Failed to insert rheomode run"):
                ledger.persist_run(run)
    
    def test_get_run_by_message_id(self, mock_supabase_client):
        """Test getting a run by message ID."""
        # Mock database response
        mock_data = [{
            "id": "run-123",
            "session_id": "session-456",
            "message_id": "msg-789",
            "role": "user",
            "process_trace": {
                "flags": {"retrieval.dual_index": True},
                "query": "test query",
                "candidates": [],
                "contradictions": [],
                "timing": {"total_ms": 1000},
                "strategy_used": "dual",
                "metadata": {}
            },
            "process_trace_summary": "Test summary",
            "lift_score": 0.8,
            "contradiction_score": 0.2,
            "created_at": "2024-01-01T00:00:00Z"
        }]
        
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = Mock(data=mock_data)
        
        with patch('core.ledger.get_client', return_value=mock_supabase_client):
            ledger = RheomodeLedger()
            run = ledger.get_run_by_message_id("msg-789")
            
            assert run is not None
            assert run.id == "run-123"
            assert run.session_id == "session-456"
            assert run.message_id == "msg-789"
            assert run.process_trace is not None
            assert run.process_trace.strategy_used == "dual"
    
    def test_get_run_by_message_id_not_found(self, mock_supabase_client):
        """Test getting a run by message ID when not found."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = Mock(data=[])
        
        with patch('core.ledger.get_client', return_value=mock_supabase_client):
            ledger = RheomodeLedger()
            run = ledger.get_run_by_message_id("nonexistent")
            
            assert run is None
    
    def test_get_runs_by_session(self, mock_supabase_client):
        """Test getting runs by session."""
        mock_data = [
            {
                "id": "run-1",
                "session_id": "session-123",
                "message_id": "msg-1",
                "role": "user",
                "process_trace": {},
                "process_trace_summary": "Summary 1",
                "lift_score": 0.8,
                "contradiction_score": 0.2,
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "run-2",
                "session_id": "session-123",
                "message_id": "msg-2",
                "role": "user",
                "process_trace": {},
                "process_trace_summary": "Summary 2",
                "lift_score": 0.9,
                "contradiction_score": 0.1,
                "created_at": "2024-01-01T01:00:00Z"
            }
        ]
        
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = Mock(data=mock_data)
        
        with patch('core.ledger.get_client', return_value=mock_supabase_client):
            ledger = RheomodeLedger()
            runs = ledger.get_runs_by_session("session-123", limit=10)
            
            assert len(runs) == 2
            assert runs[0].id == "run-1"
            assert runs[1].id == "run-2"
    
    def test_generate_trace_summary(self, sample_process_trace):
        """Test generating process trace summary."""
        with patch('core.ledger.get_client'):
            ledger = RheomodeLedger()
            
            summary = ledger._generate_trace_summary(sample_process_trace)
            lines = summary.split('\n')
            
            assert len(lines) >= 2
            assert len(lines) <= 4
            assert "dual strategy" in lines[0]
            assert "candidates" in lines[0]
            assert "contradictions" in lines[1]
            assert "Total:" in lines[2]
            assert "Flags:" in lines[3]

class TestCreateProcessTrace:
    """Test the create_process_trace function."""
    
    def test_create_process_trace(self, sample_selection_result):
        """Test creating a process trace from selection results."""
        with patch('core.ledger.get_feature_flag') as mock_flag:
            mock_flag.side_effect = lambda flag, default: {
                "retrieval.dual_index": True,
                "retrieval.liftscore": True,
                "retrieval.contradictions_pack": False
            }.get(flag, default)
            
            contradictions = [
                {
                    "subject": "Test Subject",
                    "claim_a": "Claim A",
                    "claim_b": "Claim B",
                    "evidence_ids": ["mem-1", "mem-2"],
                    "contradiction_type": "test",
                    "confidence": 0.8
                }
            ]
            
            timing = {
                "total_ms": 1000,
                "retrieval_ms": 400,
                "llm_ms": 600
            }
            
            trace = create_process_trace(
                query="test query",
                selection_result=sample_selection_result,
                contradictions=contradictions,
                timing=timing
            )
            
            assert trace.query == "test query"
            assert trace.strategy_used == "dual"
            assert len(trace.candidates) == 2
            assert len(trace.contradictions) == 1
            assert trace.timing["total_ms"] == 1000
            assert trace.flags["retrieval.dual_index"] is True

class TestLogChatRequest:
    """Test the log_chat_request function."""
    
    def test_log_chat_request_dual_index_enabled(self, sample_selection_result):
        """Test logging chat request when dual_index is enabled."""
        with patch('core.ledger.get_feature_flag') as mock_flag:
            mock_flag.return_value = True
            
            with patch('core.ledger.RheomodeLedger') as mock_ledger_class:
                mock_ledger = Mock()
                mock_ledger_class.return_value = mock_ledger
                mock_ledger.create_run.return_value = Mock()
                mock_ledger.persist_run.return_value = "test-run-id"
                
                result = log_chat_request(
                    session_id="session-123",
                    message_id="msg-456",
                    role="user",
                    query="test query",
                    selection_result=sample_selection_result,
                    contradictions=[],
                    timing={"total_ms": 1000}
                )
                
                assert result == "test-run-id"
                mock_ledger.create_run.assert_called_once()
                mock_ledger.persist_run.assert_called_once()
    
    def test_log_chat_request_dual_index_disabled(self, sample_selection_result):
        """Test logging chat request when dual_index is disabled."""
        with patch('core.ledger.get_feature_flag') as mock_flag:
            mock_flag.return_value = False
            
            result = log_chat_request(
                session_id="session-123",
                message_id="msg-456",
                role="user",
                query="test query",
                selection_result=sample_selection_result,
                contradictions=[],
                timing={"total_ms": 1000}
            )
            
            assert result is None
    
    def test_log_chat_request_exception_handling(self, sample_selection_result):
        """Test logging chat request with exception handling."""
        with patch('core.ledger.get_feature_flag') as mock_flag:
            mock_flag.return_value = True
            
            with patch('core.ledger.RheomodeLedger') as mock_ledger_class:
                mock_ledger = Mock()
                mock_ledger_class.return_value = mock_ledger
                mock_ledger.create_run.side_effect = Exception("Test error")
                
                with patch('builtins.print') as mock_print:
                    result = log_chat_request(
                        session_id="session-123",
                        message_id="msg-456",
                        role="user",
                        query="test query",
                        selection_result=sample_selection_result,
                        contradictions=[],
                        timing={"total_ms": 1000}
                    )
                    
                    assert result is None
                    mock_print.assert_called_with("Failed to log chat request: Test error")

class TestIntegration:
    """Integration tests for the ledger system."""
    
    def test_end_to_end_tracing(self, sample_selection_result):
        """Test end-to-end tracing workflow."""
        with patch('core.ledger.get_feature_flag') as mock_flag:
            mock_flag.return_value = True
            
            with patch('core.ledger.RheomodeLedger') as mock_ledger_class:
                mock_ledger = Mock()
                mock_ledger_class.return_value = mock_ledger
                
                # Mock the ledger methods
                mock_run = Mock()
                mock_ledger.create_run.return_value = mock_run
                mock_ledger.persist_run.return_value = "test-run-id"
                
                # Test the full workflow
                contradictions = [
                    {
                        "subject": "Test Subject",
                        "claim_a": "Claim A",
                        "claim_b": "Claim B",
                        "evidence_ids": ["mem-1", "mem-2"],
                        "contradiction_type": "test",
                        "confidence": 0.8
                    }
                ]
                
                timing = {
                    "total_ms": 1000,
                    "retrieval_ms": 400,
                    "llm_ms": 600
                }
                
                result = log_chat_request(
                    session_id="session-123",
                    message_id="msg-456",
                    role="user",
                    query="test query",
                    selection_result=sample_selection_result,
                    contradictions=contradictions,
                    timing=timing,
                    lift_score=0.85,
                    contradiction_score=0.3
                )
                
                assert result == "test-run-id"
                
                # Verify create_run was called with correct parameters
                mock_ledger.create_run.assert_called_once()
                call_args = mock_ledger.create_run.call_args
                assert call_args[1]["session_id"] == "session-123"
                assert call_args[1]["message_id"] == "msg-456"
                assert call_args[1]["role"] == "user"
                assert call_args[1]["lift_score"] == 0.85
                assert call_args[1]["contradiction_score"] == 0.3
                
                # Verify persist_run was called
                mock_ledger.persist_run.assert_called_once_with(mock_run)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])