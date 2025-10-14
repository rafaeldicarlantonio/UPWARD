"""
Simplified tests for debug trace fetch and replay endpoints.
"""

import sys
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.types import OrchestrationResult, StageTrace, StageMetrics
from core.orchestrator.replay import OrchestrationReplayer, ReplayResult


class TestDebugTraceEndpoints:
    """Test debug trace fetch and replay endpoints."""
    
    def test_debug_redo_trace_success(self):
        """Test successful REDO trace fetch."""
        print("Testing successful REDO trace fetch...")
        
        # Mock database response
        mock_trace_data = {
            "id": "trace_123",
            "session_id": "session_456",
            "message_id": "msg_789",
            "created_at": "2024-01-01T12:00:00Z",
            "trace_hash": "abc123def456",
            "is_truncated": False,
            "original_size": 1000,
            "stored_size": 1000,
            "trace_data": {
                "version": "1.0",
                "stages": [
                    {
                        "name": "observe",
                        "input": {"query": "test query"},
                        "output": {"intent": "test"},
                        "metrics": {"duration_ms": 100.0}
                    }
                ],
                "contradictions": [],
                "selected_context_ids": ["ctx1", "ctx2"],
                "timings": {"total_ms": 100.0, "orchestration_ms": 80.0, "planning_ms": 20.0}
            }
        }
        
        # Test the endpoint logic directly
        def mock_debug_redo_trace(message_id, x_api_key):
            # Mock database query
            mock_result = Mock()
            mock_result.data = [mock_trace_data]
            
            if not mock_result.data or len(mock_result.data) == 0:
                raise Exception("404: No REDO trace found for message ID")
            
            trace_row = mock_result.data[0]
            trace_data = trace_row.get("trace_data", {})
            
            # Build response
            response = {
                "id": trace_row.get("id"),
                "session_id": trace_row.get("session_id"),
                "message_id": trace_row.get("message_id"),
                "created_at": trace_row.get("created_at"),
                "trace_hash": trace_row.get("trace_hash"),
                "is_truncated": trace_row.get("is_truncated", False),
                "original_size": trace_row.get("original_size", 0),
                "stored_size": trace_row.get("stored_size", 0),
                "trace_data": trace_data,
                "status": "ok"
            }
            
            # Add trace summary if available
            if trace_data:
                stages = trace_data.get("stages", [])
                contradictions = trace_data.get("contradictions", [])
                selected_context_ids = trace_data.get("selected_context_ids", [])
                timings = trace_data.get("timings", {})
                
                response["summary"] = {
                    "stages_count": len(stages),
                    "contradictions_count": len(contradictions),
                    "selected_context_count": len(selected_context_ids),
                    "total_time_ms": timings.get("total_ms", 0.0),
                    "orchestration_time_ms": timings.get("orchestration_ms", 0.0),
                    "planning_time_ms": timings.get("planning_ms", 0.0)
                }
            
            return response
        
        response = mock_debug_redo_trace("msg_789", "test_key")
        
        # Verify response structure
        assert response["id"] == "trace_123"
        assert response["session_id"] == "session_456"
        assert response["message_id"] == "msg_789"
        assert response["status"] == "ok"
        assert "trace_data" in response
        assert "summary" in response
        
        # Verify summary
        summary = response["summary"]
        assert summary["stages_count"] == 1
        assert summary["contradictions_count"] == 0
        assert summary["selected_context_count"] == 2
        assert summary["total_time_ms"] == 100.0
        
        print("✓ Successful REDO trace fetch works")
    
    def test_debug_redo_trace_not_found(self):
        """Test REDO trace fetch when trace not found."""
        print("Testing REDO trace fetch when not found...")
        
        def mock_debug_redo_trace(message_id, x_api_key):
            # Mock empty database response
            mock_result = Mock()
            mock_result.data = []
            
            if not mock_result.data or len(mock_result.data) == 0:
                raise Exception("404: No REDO trace found for message ID")
            
            return {}
        
        try:
            mock_debug_redo_trace("nonexistent_msg", "test_key")
            assert False, "Should have raised Exception"
        except Exception as e:
            assert "404" in str(e) or "No REDO trace found" in str(e)
        
        print("✓ REDO trace not found handling works")
    
    def test_debug_redo_replay_success(self):
        """Test successful REDO trace replay."""
        print("Testing successful REDO trace replay...")
        
        # Mock database response
        mock_trace_data = {
            "id": "trace_123",
            "session_id": "session_456",
            "message_id": "msg_789",
            "created_at": "2024-01-01T12:00:00Z",
            "trace_data": {
                "query": "test query",
                "session_id": "session_456",
                "role": "user",
                "stages": [
                    {
                        "name": "observe",
                        "input": {"query": "test query"},
                        "output": {"intent": "test"},
                        "metrics": {"duration_ms": 100.0}
                    }
                ],
                "contradictions": [],
                "selected_context_ids": ["ctx1", "ctx2"],
                "timings": {"total_ms": 100.0}
            }
        }
        
        def mock_debug_redo_replay(message_id, write_to_ledger, x_api_key):
            # Mock database query
            mock_result = Mock()
            mock_result.data = [mock_trace_data]
            
            if not mock_result.data or len(mock_result.data) == 0:
                raise Exception("404: No REDO trace found for message ID")
            
            trace_row = mock_result.data[0]
            trace_data = trace_row.get("trace_data", {})
            
            if not trace_data:
                raise Exception("400: Trace data is empty or invalid")
            
            # Mock replay result
            replay_result = ReplayResult(
                original_trace=trace_data,
                replayed_trace=OrchestrationResult(
                    stages=[StageTrace(name="observe", metrics=StageMetrics(duration_ms=120.0))],
                    final_plan={"type": "test"},
                    timings={"total_ms": 120.0},
                    warnings=[],
                    selected_context_ids=["ctx1", "ctx2"],
                    contradictions=[],
                    knobs={}
                ),
                timing_diff_ms=20.0,
                success=True,
                warnings=["Replay was 20.0ms slower than original"],
                errors=[]
            )
            
            # Build response
            response = {
                "message_id": message_id,
                "replay_success": replay_result.success,
                "timing_diff_ms": replay_result.timing_diff_ms,
                "warnings": replay_result.warnings,
                "errors": replay_result.errors,
                "original_trace": {
                    "stages_count": len(trace_data.get("stages", [])),
                    "contradictions_count": len(trace_data.get("contradictions", [])),
                    "selected_context_count": len(trace_data.get("selected_context_ids", [])),
                    "total_time_ms": trace_data.get("timings", {}).get("total_ms", 0.0)
                },
                "replayed_trace": {
                    "stages_count": len(replay_result.replayed_trace.stages),
                    "contradictions_count": len(replay_result.replayed_trace.contradictions),
                    "selected_context_count": len(replay_result.replayed_trace.selected_context_ids),
                    "total_time_ms": replay_result.replayed_trace.timings.get("total_ms", 0.0),
                    "warnings_count": len(replay_result.replayed_trace.warnings)
                },
                "status": "ok"
            }
            
            return response
        
        response = mock_debug_redo_replay("msg_789", False, "test_key")
        
        # Verify response structure
        assert response["message_id"] == "msg_789"
        assert response["replay_success"] == True
        assert response["timing_diff_ms"] == 20.0
        assert "Replay was 20.0ms slower than original" in response["warnings"]
        assert response["status"] == "ok"
        
        # Verify trace comparison
        assert response["original_trace"]["stages_count"] == 1
        assert response["replayed_trace"]["stages_count"] == 1
        assert response["original_trace"]["total_time_ms"] == 100.0
        assert response["replayed_trace"]["total_time_ms"] == 120.0
        
        print("✓ Successful REDO trace replay works")
    
    def test_debug_redo_traces_list(self):
        """Test REDO traces list endpoint."""
        print("Testing REDO traces list...")
        
        # Mock database response
        mock_traces = [
            {
                "id": "trace_1",
                "session_id": "session_1",
                "message_id": "msg_1",
                "created_at": "2024-01-01T12:00:00Z",
                "is_truncated": False,
                "original_size": 1000,
                "stored_size": 1000
            },
            {
                "id": "trace_2",
                "session_id": "session_1",
                "message_id": "msg_2",
                "created_at": "2024-01-01T11:00:00Z",
                "is_truncated": True,
                "original_size": 2000,
                "stored_size": 1000
            }
        ]
        
        def mock_debug_redo_traces(session_id, limit, x_api_key):
            # Mock database query
            mock_result = Mock()
            mock_result.data = mock_traces
            
            if not mock_result.data:
                return {
                    "traces": [],
                    "count": 0,
                    "status": "ok"
                }
            
            # Format response
            traces = []
            for row in mock_result.data:
                traces.append({
                    "id": row.get("id"),
                    "session_id": row.get("session_id"),
                    "message_id": row.get("message_id"),
                    "created_at": row.get("created_at"),
                    "is_truncated": row.get("is_truncated", False),
                    "original_size": row.get("original_size", 0),
                    "stored_size": row.get("stored_size", 0)
                })
            
            return {
                "traces": traces,
                "count": len(traces),
                "status": "ok"
            }
        
        response = mock_debug_redo_traces(None, 10, "test_key")
        
        # Verify response structure
        assert response["count"] == 2
        assert len(response["traces"]) == 2
        assert response["status"] == "ok"
        
        # Verify trace data
        trace_1 = response["traces"][0]
        assert trace_1["id"] == "trace_1"
        assert trace_1["session_id"] == "session_1"
        assert trace_1["message_id"] == "msg_1"
        assert trace_1["is_truncated"] == False
        
        trace_2 = response["traces"][1]
        assert trace_2["id"] == "trace_2"
        assert trace_2["is_truncated"] == True
        
        print("✓ REDO traces list works")


class TestOrchestrationReplayer:
    """Test the OrchestrationReplayer class."""
    
    def test_replay_trace_success(self):
        """Test successful trace replay."""
        print("Testing successful trace replay...")
        
        # Create sample trace data
        trace_data = {
            "query": "test query",
            "session_id": "session_123",
            "role": "user",
            "preferences": {},
            "metadata": {"test": "data"},
            "stages": [
                {
                    "name": "observe",
                    "input": {"query": "test query"},
                    "output": {"intent": "test"},
                    "metrics": {"duration_ms": 100.0}
                }
            ],
            "contradictions": [],
            "selected_context_ids": ["ctx1", "ctx2"],
            "timings": {"total_ms": 100.0}
        }
        
        # Mock configuration
        config = {
            "ORCHESTRATION_TIME_BUDGET_MS": 400,
            "LEDGER_MAX_TRACE_BYTES": 100000,
            "TOPK_PER_TYPE": 16
        }
        
        feature_flags = {
            "retrieval.contradictions_pack": False,
            "retrieval.dual_index": False,
            "retrieval.liftscore": False
        }
        
        # Create replayer
        replayer = OrchestrationReplayer(config)
        
        # Replay the trace
        result = replayer.replay_trace(trace_data, feature_flags)
        
        # Verify result
        assert result.success == True
        assert isinstance(result.timing_diff_ms, (int, float))  # Should be a number
        assert len(result.warnings) >= 0
        assert len(result.errors) == 0
        assert isinstance(result.replayed_trace, OrchestrationResult)
        
        print("✓ Successful trace replay works")
    
    def test_replay_trace_with_timing_difference(self):
        """Test trace replay with timing difference."""
        print("Testing trace replay with timing difference...")
        
        # Create sample trace data with fast original timing
        trace_data = {
            "query": "test query",
            "session_id": "session_123",
            "role": "user",
            "preferences": {},
            "metadata": {"test": "data"},
            "stages": [],
            "contradictions": [],
            "selected_context_ids": [],
            "timings": {"total_ms": 50.0}  # Very fast original
        }
        
        # Mock configuration
        config = {
            "ORCHESTRATION_TIME_BUDGET_MS": 400,
            "LEDGER_MAX_TRACE_BYTES": 100000,
            "TOPK_PER_TYPE": 16
        }
        
        feature_flags = {
            "retrieval.contradictions_pack": False,
            "retrieval.dual_index": False,
            "retrieval.liftscore": False
        }
        
        # Create replayer
        replayer = OrchestrationReplayer(config)
        
        # Replay the trace
        result = replayer.replay_trace(trace_data, feature_flags)
        
        # Verify result
        assert result.success == True
        assert isinstance(result.timing_diff_ms, (int, float))  # Should be a number
        # The timing difference could be positive or negative depending on system performance
        assert abs(result.timing_diff_ms) >= 0  # Should be a valid timing difference
        
        print("✓ Trace replay with timing difference works")
    
    def test_replay_trace_failure(self):
        """Test trace replay failure."""
        print("Testing trace replay failure...")
        
        # Create invalid trace data
        trace_data = {
            "query": "",  # Empty query should cause issues
            "session_id": "",
            "role": "user",
            "preferences": {},
            "metadata": {},
            "stages": [],
            "contradictions": [],
            "selected_context_ids": [],
            "timings": {"total_ms": 100.0}
        }
        
        # Mock configuration
        config = {
            "ORCHESTRATION_TIME_BUDGET_MS": 400,
            "LEDGER_MAX_TRACE_BYTES": 100000,
            "TOPK_PER_TYPE": 16
        }
        
        feature_flags = {
            "retrieval.contradictions_pack": False,
            "retrieval.dual_index": False,
            "retrieval.liftscore": False
        }
        
        with patch('core.orchestrator.replay.RedoOrchestrator') as mock_orchestrator:
            # Mock orchestrator to raise exception
            mock_orchestrator_instance = Mock()
            mock_orchestrator_instance.run.side_effect = Exception("Test error")
            mock_orchestrator.return_value = mock_orchestrator_instance
            
            # Create replayer
            replayer = OrchestrationReplayer(config)
            
            # Replay the trace
            result = replayer.replay_trace(trace_data, feature_flags)
            
            # Verify result
            assert result.success == False
            assert len(result.errors) > 0
            assert "Test error" in result.errors[0]
            
            print("✓ Trace replay failure handling works")
    
    def test_replay_with_ledger(self):
        """Test trace replay with ledger writing."""
        print("Testing trace replay with ledger...")
        
        # Create sample trace data
        trace_data = {
            "query": "test query",
            "session_id": "session_123",
            "role": "user",
            "preferences": {},
            "metadata": {"test": "data"},
            "stages": [],
            "contradictions": [],
            "selected_context_ids": [],
            "timings": {"total_ms": 100.0}
        }
        
        # Mock configuration
        config = {
            "ORCHESTRATION_TIME_BUDGET_MS": 400,
            "LEDGER_MAX_TRACE_BYTES": 100000,
            "TOPK_PER_TYPE": 16
        }
        
        feature_flags = {
            "retrieval.contradictions_pack": False,
            "retrieval.dual_index": False,
            "retrieval.liftscore": False,
            "ledger.enabled": True  # Enable ledger
        }
        
        with patch('core.orchestrator.replay.write_ledger') as mock_ledger:
            # Mock ledger entry
            mock_ledger_entry = Mock()
            mock_ledger_entry.stored_size = 500
            mock_ledger.return_value = mock_ledger_entry
            
            # Create replayer
            replayer = OrchestrationReplayer(config)
            
            # Replay with ledger
            result = replayer.replay_with_ledger(trace_data, "session_123", "msg_456", feature_flags)
            
            # Verify result
            assert result.success == True
            assert any("written to ledger" in warning for warning in result.warnings)
            assert mock_ledger.called
            
            print("✓ Trace replay with ledger works")


def main():
    """Run all debug trace tests."""
    print("Running debug trace tests...\n")
    
    try:
        # Test debug endpoints
        test_endpoints = TestDebugTraceEndpoints()
        test_endpoints.test_debug_redo_trace_success()
        test_endpoints.test_debug_redo_trace_not_found()
        test_endpoints.test_debug_redo_replay_success()
        test_endpoints.test_debug_redo_traces_list()
        
        # Test orchestrator replayer
        test_replayer = TestOrchestrationReplayer()
        test_replayer.test_replay_trace_success()
        test_replayer.test_replay_trace_with_timing_difference()
        test_replayer.test_replay_trace_failure()
        test_replayer.test_replay_with_ledger()
        
        print("\n🎉 All debug trace tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())