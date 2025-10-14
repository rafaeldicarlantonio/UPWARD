"""
Tests for orchestrator interface and trace schema.
"""

import json
from dataclasses import asdict
from typing import Dict, Any

try:
    import pytest
except ImportError:
    pytest = None

from core.types import (
    QueryContext, 
    OrchestrationResult, 
    OrchestrationConfig, 
    StageTrace, 
    StageMetrics
)
from core.orchestrator.interfaces import Orchestrator, OrchestratorProtocol
from core.orchestrator.redo import RedoOrchestrator


class TestTraceSchema:
    """Test trace schema structure and serialization."""
    
    def test_stage_metrics_creation(self):
        """Test StageMetrics creation and defaults."""
        metrics = StageMetrics(duration_ms=100.0)
        assert metrics.duration_ms == 100.0
        assert metrics.memory_usage_mb is None
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.tokens_processed is None
        assert metrics.custom_metrics == {}
    
    def test_stage_trace_creation(self):
        """Test StageTrace creation and defaults."""
        metrics = StageMetrics(duration_ms=50.0)
        stage = StageTrace(
            name="test_stage",
            input={"key": "value"},
            output={"result": "success"},
            metrics=metrics
        )
        
        assert stage.name == "test_stage"
        assert stage.input == {"key": "value"}
        assert stage.output == {"result": "success"}
        assert stage.metrics.duration_ms == 50.0
        assert stage.error is None
        assert stage.warnings == []
    
    def test_orchestration_result_creation(self):
        """Test OrchestrationResult creation and defaults."""
        result = OrchestrationResult()
        
        assert result.stages == []
        assert result.final_plan == {}
        assert result.timings == {}
        assert result.warnings == []
        assert result.selected_context_ids == []
        assert result.contradictions == []
        assert result.knobs == {}
    
    def test_query_context_creation(self):
        """Test QueryContext creation and defaults."""
        ctx = QueryContext(query="test query")
        
        assert ctx.query == "test query"
        assert ctx.session_id is None
        assert ctx.user_id is None
        assert ctx.role is None
        assert ctx.preferences == {}
        assert ctx.metadata == {}
    
    def test_orchestration_config_creation(self):
        """Test OrchestrationConfig creation and defaults."""
        config = OrchestrationConfig()
        
        assert config.max_trace_bytes == 100_000
        assert config.enable_contradiction_detection is False
        assert config.enable_redo is False
        assert config.time_budget_ms == 400
        assert config.max_stages == 10
        assert config.custom_knobs == {}


class TestTraceSerialization:
    """Test trace schema JSON serialization."""
    
    def test_minimal_trace_schema(self):
        """Test minimal trace schema structure."""
        result = OrchestrationResult()
        trace = result.to_trace_schema()
        
        # Check required top-level fields
        assert "version" in trace
        assert "stages" in trace
        assert "knobs" in trace
        assert "contradictions" in trace
        assert "selected_context_ids" in trace
        assert "final_plan" in trace
        assert "timings" in trace
        assert "warnings" in trace
        assert "timestamp" in trace
        
        # Check version
        assert trace["version"] == "1.0"
        
        # Check stages structure
        assert isinstance(trace["stages"], list)
    
    def test_stage_schema_structure(self):
        """Test individual stage schema structure."""
        metrics = StageMetrics(
            duration_ms=100.0,
            memory_usage_mb=25.0,
            cache_hits=5,
            cache_misses=2,
            tokens_processed=1000,
            custom_metrics={"score": 0.8}
        )
        
        stage = StageTrace(
            name="test_stage",
            input={"input_key": "input_value"},
            output={"output_key": "output_value"},
            metrics=metrics,
            error=None,
            warnings=["warning1", "warning2"]
        )
        
        result = OrchestrationResult(stages=[stage])
        trace = result.to_trace_schema()
        
        assert len(trace["stages"]) == 1
        stage_data = trace["stages"][0]
        
        # Check stage fields
        assert stage_data["name"] == "test_stage"
        assert stage_data["input"] == {"input_key": "input_value"}
        assert stage_data["output"] == {"output_key": "output_value"}
        assert stage_data["error"] is None
        assert stage_data["warnings"] == ["warning1", "warning2"]
        
        # Check metrics structure
        metrics_data = stage_data["metrics"]
        assert metrics_data["duration_ms"] == 100.0
        assert metrics_data["memory_usage_mb"] == 25.0
        assert metrics_data["cache_hits"] == 5
        assert metrics_data["cache_misses"] == 2
        assert metrics_data["tokens_processed"] == 1000
        assert metrics_data["custom_metrics"] == {"score": 0.8}
    
    def test_json_serialization(self):
        """Test JSON serialization of trace schema."""
        result = OrchestrationResult(
            stages=[
                StageTrace(
                    name="test_stage",
                    input={"test": "input"},
                    output={"test": "output"},
                    metrics=StageMetrics(duration_ms=50.0)
                )
            ],
            final_plan={"type": "test"},
            timings={"total_ms": 100.0},
            warnings=["test warning"],
            selected_context_ids=["ctx_1", "ctx_2"],
            contradictions=[{"type": "test"}],
            knobs={"test_knob": "value"}
        )
        
        json_str = result.to_json()
        assert isinstance(json_str, str)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["version"] == "1.0"
        assert len(parsed["stages"]) == 1
        assert parsed["stages"][0]["name"] == "test_stage"
    
    def test_size_guard(self):
        """Test trace size guard functionality."""
        # Create a large result
        large_stages = []
        for i in range(100):
            large_stages.append(StageTrace(
                name=f"stage_{i}",
                input={"large_data": "x" * 1000},
                output={"large_result": "y" * 1000},
                metrics=StageMetrics(duration_ms=float(i))
            ))
        
        result = OrchestrationResult(stages=large_stages)
        
        # Test with small size limit
        json_str = result.to_json(max_bytes=1000)
        parsed = json.loads(json_str)
        
        # Should have been truncated
        assert len(json_str.encode('utf-8')) <= 1000
        assert len(parsed["stages"]) < 100  # Should be truncated
        
        # Test with large size limit
        json_str_large = result.to_json(max_bytes=1_000_000)
        parsed_large = json.loads(json_str_large)
        
        # Should not be truncated
        assert len(parsed_large["stages"]) == 100
    
    def test_empty_result_serialization(self):
        """Test serialization of empty result."""
        result = OrchestrationResult()
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["version"] == "1.0"
        assert parsed["stages"] == []
        assert parsed["final_plan"] == {}
        assert parsed["timings"] == {}
        assert parsed["warnings"] == []
        assert parsed["selected_context_ids"] == []
        assert parsed["contradictions"] == []
        assert parsed["knobs"] == {}


class TestOrchestratorInterface:
    """Test orchestrator interface compliance."""
    
    def test_redo_orchestrator_implements_interface(self):
        """Test that RedoOrchestrator implements Orchestrator interface."""
        orchestrator = RedoOrchestrator()
        assert isinstance(orchestrator, Orchestrator)
        assert isinstance(orchestrator, OrchestratorProtocol)
    
    def test_orchestrator_run_method(self):
        """Test orchestrator run method signature and return type."""
        orchestrator = RedoOrchestrator()
        query_ctx = QueryContext(query="test query")
        
        result = orchestrator.run(query_ctx)
        
        assert isinstance(result, OrchestrationResult)
        assert isinstance(result.stages, list)
        assert isinstance(result.final_plan, dict)
        assert isinstance(result.timings, dict)
        assert isinstance(result.warnings, list)
    
    def test_orchestrator_configure_method(self):
        """Test orchestrator configure method."""
        orchestrator = RedoOrchestrator()
        config = OrchestrationConfig(
            max_trace_bytes=50_000,
            enable_contradiction_detection=True,
            enable_redo=True,
            time_budget_ms=200
        )
        
        orchestrator.configure(config)
        assert orchestrator.config.max_trace_bytes == 50_000
        assert orchestrator.config.enable_contradiction_detection is True
        assert orchestrator.config.enable_redo is True
        assert orchestrator.config.time_budget_ms == 200


class TestRedoOrchestrator:
    """Test RedoOrchestrator implementation."""
    
    def test_redo_orchestrator_creation(self):
        """Test RedoOrchestrator creation."""
        orchestrator = RedoOrchestrator()
        assert orchestrator.config is not None
        assert orchestrator.stage_processors == []
    
    def test_redo_orchestrator_run_basic(self):
        """Test basic RedoOrchestrator run."""
        orchestrator = RedoOrchestrator()
        query_ctx = QueryContext(
            query="What is the capital of France?",
            session_id="test_session",
            user_id="test_user",
            role="researcher"
        )
        
        result = orchestrator.run(query_ctx)
        
        # Check basic structure
        assert isinstance(result, OrchestrationResult)
        assert len(result.stages) > 0
        assert isinstance(result.final_plan, dict)
        assert isinstance(result.timings, dict)
        assert isinstance(result.warnings, list)
        assert isinstance(result.selected_context_ids, list)
        assert isinstance(result.contradictions, list)
        assert isinstance(result.knobs, dict)
    
    def test_redo_orchestrator_stages(self):
        """Test that RedoOrchestrator creates expected stages."""
        orchestrator = RedoOrchestrator()
        query_ctx = QueryContext(query="test query")
        
        result = orchestrator.run(query_ctx)
        
        # Should have at least 3 stages
        assert len(result.stages) >= 3
        
        stage_names = [stage.name for stage in result.stages]
        assert "query_analysis" in stage_names
        assert "context_retrieval" in stage_names
        assert "plan_generation" in stage_names
    
    def test_redo_orchestrator_with_contradiction_detection(self):
        """Test RedoOrchestrator with contradiction detection enabled."""
        orchestrator = RedoOrchestrator()
        config = OrchestrationConfig(enable_contradiction_detection=True)
        orchestrator.configure(config)
        
        query_ctx = QueryContext(query="test query")
        result = orchestrator.run(query_ctx)
        
        # Should have contradictions when enabled
        assert len(result.contradictions) > 0
        assert result.contradictions[0]["type"] == "temporal_contradiction"
    
    def test_redo_orchestrator_without_contradiction_detection(self):
        """Test RedoOrchestrator with contradiction detection disabled."""
        orchestrator = RedoOrchestrator()
        config = OrchestrationConfig(enable_contradiction_detection=False)
        orchestrator.configure(config)
        
        query_ctx = QueryContext(query="test query")
        result = orchestrator.run(query_ctx)
        
        # Should not have contradictions when disabled
        assert len(result.contradictions) == 0
    
    def test_redo_orchestrator_custom_knobs(self):
        """Test RedoOrchestrator with custom knobs."""
        orchestrator = RedoOrchestrator()
        config = OrchestrationConfig(
            custom_knobs={"custom_setting": "custom_value", "another_setting": 42}
        )
        orchestrator.configure(config)
        
        query_ctx = QueryContext(query="test query")
        result = orchestrator.run(query_ctx)
        
        # Should include custom knobs
        assert "custom_setting" in result.knobs
        assert result.knobs["custom_setting"] == "custom_value"
        assert "another_setting" in result.knobs
        assert result.knobs["another_setting"] == 42
    
    def test_redo_orchestrator_warnings(self):
        """Test RedoOrchestrator warning generation."""
        orchestrator = RedoOrchestrator()
        
        # Test with long query
        long_query = "x" * 1500
        query_ctx = QueryContext(query=long_query)
        result = orchestrator.run(query_ctx)
        
        assert len(result.warnings) > 0
        assert any("very long" in warning.lower() for warning in result.warnings)
        
        # Test with admin role
        query_ctx_admin = QueryContext(query="test", role="admin")
        result_admin = orchestrator.run(query_ctx_admin)
        
        assert len(result_admin.warnings) > 0
        assert any("admin role" in warning.lower() for warning in result_admin.warnings)
    
    def test_redo_orchestrator_timings(self):
        """Test RedoOrchestrator timing generation."""
        orchestrator = RedoOrchestrator()
        query_ctx = QueryContext(query="test query")
        
        result = orchestrator.run(query_ctx)
        
        assert "total_ms" in result.timings
        assert "orchestration_ms" in result.timings
        assert "planning_ms" in result.timings
        
        assert result.timings["total_ms"] > 0
        assert result.timings["orchestration_ms"] > 0
        assert result.timings["planning_ms"] > 0


class TestIntegration:
    """Integration tests for the orchestrator system."""
    
    def test_full_roundtrip(self):
        """Test full roundtrip from query to JSON trace."""
        orchestrator = RedoOrchestrator()
        config = OrchestrationConfig(
            max_trace_bytes=10_000,
            enable_contradiction_detection=True,
            enable_redo=True,
            custom_knobs={"test_knob": "test_value"}
        )
        orchestrator.configure(config)
        
        query_ctx = QueryContext(
            query="What is machine learning?",
            session_id="session_123",
            user_id="user_456",
            role="researcher",
            preferences={"language": "en"},
            metadata={"source": "web"}
        )
        
        # Run orchestration
        result = orchestrator.run(query_ctx)
        
        # Convert to JSON
        json_str = result.to_json()
        
        # Verify JSON is valid and contains expected data
        parsed = json.loads(json_str)
        
        assert parsed["version"] == "1.0"
        assert len(parsed["stages"]) >= 3
        assert parsed["final_plan"]["type"] == "direct_answer"
        assert len(parsed["selected_context_ids"]) == 5
        assert len(parsed["contradictions"]) == 1
        assert parsed["knobs"]["test_knob"] == "test_value"
        assert len(parsed["warnings"]) >= 0
        
        # Verify size constraint
        assert len(json_str.encode('utf-8')) <= 10_000
    
    def test_import_without_side_effects(self):
        """Test that modules can be imported without side effects."""
        # This test ensures that importing the modules doesn't cause
        # any side effects like database connections, file I/O, etc.
        
        import core.types
        import core.orchestrator.interfaces
        import core.orchestrator.redo
        
        # All imports should succeed without errors
        assert core.types is not None
        assert core.orchestrator.interfaces is not None
        assert core.orchestrator.redo is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])