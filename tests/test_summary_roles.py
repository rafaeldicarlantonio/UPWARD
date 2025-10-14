"""
Tests for role-aware trace summarization.
"""

import sys
from typing import Dict, Any, List

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.types import OrchestrationResult, StageTrace, StageMetrics
from core.trace_summary import (
    summarize_for_role, 
    get_role_summary_stats,
    ROLE_LEVELS,
    PII_PATTERNS,
    SOURCE_TEXT_PATTERNS,
    _redact_warning_text,
    _get_contradiction_types,
    _get_performance_summary
)


class TestRoleAwareSummarization:
    """Test role-aware summarization functionality."""
    
    def test_summarize_for_role_general(self):
        """Test general role summarization."""
        print("Testing general role summarization...")
        
        trace = self._create_sample_trace()
        summary = summarize_for_role(trace, "general")
        
        # Verify summary structure
        assert isinstance(summary, str)
        lines = summary.split('\n')
        assert 2 <= len(lines) <= 2  # General should be 2 lines max
        
        # Verify general-specific content
        summary_text = summary.lower()
        assert "steps" in summary_text  # Should use "steps" not "stages"
        assert "sources" in summary_text  # Should use "sources" not "context items"
        assert "source-" in summary_text  # Should redact evidence IDs
        
        # Verify no raw text or PII
        assert not any(pattern in summary for pattern in ["ctx_", "user@", "192.168", "```"])
        
        print("✓ General role summarization works")
    
    def test_summarize_for_role_pro(self):
        """Test pro role summarization."""
        print("Testing pro role summarization...")
        
        trace = self._create_sample_trace()
        summary = summarize_for_role(trace, "pro")
        
        # Verify summary structure
        assert isinstance(summary, str)
        lines = summary.split('\n')
        assert 2 <= len(lines) <= 4  # Pro should be up to 4 lines
        
        # Verify pro-specific content
        summary_text = summary.lower()
        assert "stages" in summary_text  # Should use "stages"
        assert "context items" in summary_text  # Should use "context items"
        assert "ctx_" in summary_text  # Should show actual evidence IDs
        
        # Verify technical details
        assert "professional analysis completed" in summary_text or "warning" in summary_text
        
        print("✓ Pro role summarization works")
    
    def test_summarize_for_role_scholars(self):
        """Test scholars role summarization."""
        print("Testing scholars role summarization...")
        
        trace = self._create_sample_trace()
        summary = summarize_for_role(trace, "scholars")
        
        # Verify summary structure
        assert isinstance(summary, str)
        lines = summary.split('\n')
        assert 2 <= len(lines) <= 4  # Scholars should be up to 4 lines
        
        # Verify scholars-specific content
        summary_text = summary.lower()
        assert "orchestration stages" in summary_text  # Should use academic terminology
        assert "context items" in summary_text
        assert "academic analysis completed" in summary_text or "warning" in summary_text
        
        print("✓ Scholars role summarization works")
    
    def test_summarize_for_role_analytics(self):
        """Test analytics role summarization."""
        print("Testing analytics role summarization...")
        
        trace = self._create_sample_trace()
        summary = summarize_for_role(trace, "analytics")
        
        # Verify summary structure
        assert isinstance(summary, str)
        lines = summary.split('\n')
        assert 2 <= len(lines) <= 4  # Analytics should be up to 4 lines
        
        # Verify analytics-specific content
        summary_text = summary.lower()
        assert "processing stages" in summary_text  # Should use data terminology
        assert "data points" in summary_text  # Should use data terminology
        assert "data processing completed" in summary_text or "warning" in summary_text
        
        print("✓ Analytics role summarization works")
    
    def test_summarize_for_role_ops(self):
        """Test ops role summarization."""
        print("Testing ops role summarization...")
        
        trace = self._create_sample_trace()
        summary = summarize_for_role(trace, "ops")
        
        # Verify summary structure
        assert isinstance(summary, str)
        lines = summary.split('\n')
        assert 2 <= len(lines) <= 6  # Ops should be up to 6 lines
        
        # Verify ops-specific content
        summary_text = summary.lower()
        assert "orchestration:" in summary_text  # Should show detailed timing
        assert "planning:" in summary_text  # Should show detailed timing
        assert "evidence ids:" in summary_text  # Should show more evidence IDs
        assert "stages:" in summary_text  # Should show stage details
        assert "performance:" in summary_text  # Should show performance metrics
        
        print("✓ Ops role summarization works")
    
    def test_summarize_for_role_invalid(self):
        """Test invalid role handling."""
        print("Testing invalid role handling...")
        
        trace = self._create_sample_trace()
        
        try:
            summarize_for_role(trace, "invalid_role")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid role_key" in str(e)
        
        print("✓ Invalid role handling works")
    
    def test_summarize_for_role_max_lines_override(self):
        """Test max_lines override functionality."""
        print("Testing max_lines override...")
        
        trace = self._create_sample_trace()
        
        # Test general with override
        summary = summarize_for_role(trace, "general", max_lines=4)
        lines = summary.split('\n')
        assert len(lines) <= 4
        
        # Test ops with override
        summary = summarize_for_role(trace, "ops", max_lines=2)
        lines = summary.split('\n')
        assert len(lines) <= 2
        
        print("✓ Max lines override works")
    
    def test_role_summary_stats(self):
        """Test role-specific summary statistics."""
        print("Testing role summary stats...")
        
        trace = self._create_sample_trace()
        
        # Test each role
        for role in ["general", "pro", "scholars", "analytics", "ops"]:
            stats = get_role_summary_stats(trace, role)
            
            # Verify base stats are present
            assert "role_key" in stats
            assert "role_level" in stats
            assert "max_lines" in stats
            assert "includes_raw_text" in stats
            assert "includes_pii" in stats
            assert "includes_technical_details" in stats
            assert "includes_performance_metrics" in stats
            
            # Verify role-specific values
            assert stats["role_key"] == role
            assert stats["role_level"] == ROLE_LEVELS[role]
            assert stats["max_lines"] == (2 if role == "general" else (4 if role in ["pro", "scholars", "analytics"] else 6))
            assert stats["includes_raw_text"] == (role != "general")
            assert stats["includes_pii"] == (role == "ops")
            assert stats["includes_technical_details"] == (role in ["pro", "scholars", "analytics", "ops"])
            assert stats["includes_performance_metrics"] == (role == "ops")
        
        print("✓ Role summary stats work")
    
    def test_redaction_functionality(self):
        """Test PII and source text redaction."""
        print("Testing redaction functionality...")
        
        # Test PII redaction
        test_warnings = [
            "User john.doe@example.com reported an issue",
            "Contact support at 555-123-4567 for help",
            "IP address 192.168.1.1 is blocked",
            "SSN 123-45-6789 is invalid"
        ]
        
        for warning in test_warnings:
            redacted = _redact_warning_text(warning)
            assert "[REDACTED]" in redacted
            assert "john.doe@example.com" not in redacted
            assert "555-123-4567" not in redacted
            assert "192.168.1.1" not in redacted
            assert "123-45-6789" not in redacted
        
        # Test source text redaction
        test_source_warnings = [
            'Found long text: "This is a very long quoted text that should be redacted because it contains too much information"',
            "Code block: ```python\ndef hello():\n    print('world')\n```",
            "Inline code: `this_is_a_very_long_function_name_that_should_be_redacted`"
        ]
        
        for warning in test_source_warnings:
            redacted = _redact_warning_text(warning)
            assert "[REDACTED]" in redacted
        
        print("✓ Redaction functionality works")
    
    def test_contradiction_types(self):
        """Test contradiction type extraction."""
        print("Testing contradiction types...")
        
        contradictions = [
            {"type": "factual_contradiction", "severity": "high"},
            {"type": "temporal_contradiction", "severity": "medium"},
            {"type": "numerical_contradiction", "severity": "low"},
            {"type": "factual_contradiction", "severity": "high"}  # Duplicate
        ]
        
        types = _get_contradiction_types(contradictions)
        assert "factual_contradiction" in types
        assert "temporal_contradiction" in types
        assert "numerical_contradiction" in types
        assert types.count("factual_contradiction") == 1  # Should be deduplicated
        
        # Test empty contradictions
        empty_types = _get_contradiction_types([])
        assert empty_types == "none"
        
        print("✓ Contradiction types work")
    
    def test_performance_summary(self):
        """Test performance summary generation."""
        print("Testing performance summary...")
        
        # Test with timing data
        timings = {
            "total_ms": 1000.0,
            "orchestration_ms": 600.0,
            "planning_ms": 400.0
        }
        
        perf_summary = _get_performance_summary(timings)
        assert "orchestration 60%" in perf_summary
        assert "planning 40%" in perf_summary
        
        # Test without timing data
        empty_timings = {}
        empty_perf_summary = _get_performance_summary(empty_timings)
        assert empty_perf_summary == "no timing data"
        
        print("✓ Performance summary works")
    
    def test_role_differences(self):
        """Test that different roles produce different outputs."""
        print("Testing role differences...")
        
        trace = self._create_sample_trace()
        
        # Generate summaries for all roles
        summaries = {}
        for role in ["general", "pro", "scholars", "analytics", "ops"]:
            summaries[role] = summarize_for_role(trace, role)
        
        # Verify all summaries are different
        summary_texts = list(summaries.values())
        for i in range(len(summary_texts)):
            for j in range(i + 1, len(summary_texts)):
                assert summary_texts[i] != summary_texts[j], f"Summaries for roles should be different"
        
        # Verify general is shortest
        general_lines = len(summaries["general"].split('\n'))
        for role in ["pro", "scholars", "analytics", "ops"]:
            role_lines = len(summaries[role].split('\n'))
            assert general_lines <= role_lines, f"General should be shorter than {role}"
        
        # Verify ops is longest
        ops_lines = len(summaries["ops"].split('\n'))
        for role in ["general", "pro", "scholars", "analytics"]:
            role_lines = len(summaries[role].split('\n'))
            assert role_lines <= ops_lines, f"Ops should be longer than {role}"
        
        print("✓ Role differences work")
    
    def test_general_role_no_pii(self):
        """Test that general role never includes PII or raw text."""
        print("Testing general role PII protection...")
        
        # Create trace with PII and raw text
        trace = self._create_trace_with_pii()
        summary = summarize_for_role(trace, "general")
        
        # Verify no PII in summary
        summary_lower = summary.lower()
        assert "user@example.com" not in summary_lower
        assert "555-123-4567" not in summary_lower
        assert "192.168.1.1" not in summary_lower
        assert "123-45-6789" not in summary_lower
        
        # Verify no raw source text
        assert "```" not in summary
        assert "`" not in summary
        assert '"' not in summary  # No quoted text
        
        # Verify evidence IDs are redacted
        assert "ctx_" not in summary
        assert "source-" in summary.lower()
        
        print("✓ General role PII protection works")
    
    def test_professional_roles_include_details(self):
        """Test that professional roles include technical details."""
        print("Testing professional roles details...")
        
        trace = self._create_sample_trace()
        
        for role in ["pro", "scholars", "analytics"]:
            summary = summarize_for_role(trace, role)
            summary_lower = summary.lower()
            
            # Should include technical details
            assert "stages" in summary_lower or "orchestration" in summary_lower or "processing" in summary_lower
            assert "context items" in summary_lower or "data points" in summary_lower
            
            # Should include evidence IDs
            assert "ctx_" in summary_lower
            
            # Should include role-specific completion message (if warnings don't take precedence)
            if role == "scholars":
                assert "academic" in summary_lower or "warning" in summary_lower
            elif role == "analytics":
                assert "data" in summary_lower or "warning" in summary_lower
            else:  # pro
                assert "professional" in summary_lower or "warning" in summary_lower
        
        print("✓ Professional roles details work")
    
    def test_ops_role_full_details(self):
        """Test that ops role includes full details."""
        print("Testing ops role full details...")
        
        trace = self._create_sample_trace()
        summary = summarize_for_role(trace, "ops")
        summary_lower = summary.lower()
        
        # Should include detailed timing
        assert "orchestration:" in summary_lower
        assert "planning:" in summary_lower
        
        # Should include more evidence IDs
        assert "evidence ids:" in summary_lower
        
        # Should include stage details
        assert "stages:" in summary_lower
        
        # Should include performance metrics
        assert "performance:" in summary_lower
        
        print("✓ Ops role full details work")
    
    def _create_sample_trace(self) -> OrchestrationResult:
        """Create a sample trace for testing."""
        stages = [
            StageTrace(
                name="observe",
                input={"query": "What is machine learning?"},
                output={"intent": "information_request", "entities": ["machine learning"]},
                metrics=StageMetrics(duration_ms=150.0, tokens_processed=100)
            ),
            StageTrace(
                name="expand",
                input={"entities": ["machine learning"]},
                output={"concepts": ["artificial intelligence", "algorithms"]},
                metrics=StageMetrics(duration_ms=200.0, tokens_processed=200)
            ),
            StageTrace(
                name="contrast",
                input={"expanded_results": 5},
                output={"contradictions": 2},
                metrics=StageMetrics(duration_ms=100.0, tokens_processed=50)
            ),
            StageTrace(
                name="order",
                input={"priority_ranking": 5},
                output={"final_plan": {"type": "direct_answer"}},
                metrics=StageMetrics(duration_ms=80.0, tokens_processed=30)
            )
        ]
        
        contradictions = [
            {"type": "factual_contradiction", "severity": "high", "subject": "machine learning"},
            {"type": "temporal_contradiction", "severity": "medium", "subject": "AI timeline"}
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "direct_answer", "confidence": 0.85},
            timings={"total_ms": 530.0, "orchestration_ms": 400.0, "planning_ms": 130.0},
            warnings=["High complexity query detected", "Limited retrieval results"],
            selected_context_ids=["ctx_001", "ctx_002", "ctx_003", "ctx_004", "ctx_005"],
            contradictions=contradictions,
            knobs={"retrieval_top_k": 16, "implicate_top_k": 8}
        )
    
    def _create_trace_with_pii(self) -> OrchestrationResult:
        """Create a trace with PII and raw text for testing redaction."""
        stages = [
            StageTrace(
                name="observe",
                input={"query": "User john.doe@example.com asked about SSN 123-45-6789"},
                output={"intent": "information_request"},
                metrics=StageMetrics(duration_ms=150.0)
            )
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "direct_answer"},
            timings={"total_ms": 150.0},
            warnings=[
                "User john.doe@example.com reported an issue",
                "Found code: ```python\ndef hello():\n    print('world')\n```",
                "Long text: \"This is a very long quoted text that should be redacted\""
            ],
            selected_context_ids=["ctx_001", "ctx_002"],
            contradictions=[],
            knobs={}
        )


class TestRoleIntegration:
    """Integration tests for role-aware summarization."""
    
    def test_role_consistency(self):
        """Test that role summaries are consistent across calls."""
        print("Testing role consistency...")
        
        trace = self._create_sample_trace()
        
        # Generate multiple summaries for each role
        for role in ["general", "pro", "scholars", "analytics", "ops"]:
            summary1 = summarize_for_role(trace, role)
            summary2 = summarize_for_role(trace, role)
            
            # Should be identical
            assert summary1 == summary2, f"Role {role} summaries should be consistent"
        
        print("✓ Role consistency works")
    
    def test_role_with_different_traces(self):
        """Test role behavior with different trace types."""
        print("Testing role with different traces...")
        
        # Test with empty trace
        empty_trace = OrchestrationResult()
        for role in ["general", "pro", "scholars", "analytics", "ops"]:
            summary = summarize_for_role(empty_trace, role)
            assert isinstance(summary, str)
            assert len(summary.split('\n')) >= 2
        
        # Test with minimal trace
        minimal_trace = OrchestrationResult(
            stages=[StageTrace(name="test", metrics=StageMetrics(duration_ms=100.0))],
            timings={"total_ms": 100.0}
        )
        for role in ["general", "pro", "scholars", "analytics", "ops"]:
            summary = summarize_for_role(minimal_trace, role)
            assert isinstance(summary, str)
            assert len(summary.split('\n')) >= 2
        
        print("✓ Role with different traces works")
    
    def test_role_edge_cases(self):
        """Test role behavior with edge cases."""
        print("Testing role edge cases...")
        
        # Test with very long trace
        long_trace = self._create_long_trace()
        for role in ["general", "pro", "scholars", "analytics", "ops"]:
            summary = summarize_for_role(long_trace, role)
            assert isinstance(summary, str)
            assert len(summary.split('\n')) >= 2
        
        # Test with many contradictions
        contradiction_trace = self._create_contradiction_trace()
        for role in ["general", "pro", "scholars", "analytics", "ops"]:
            summary = summarize_for_role(contradiction_trace, role)
            assert isinstance(summary, str)
            # Should mention contradictions or conflicting information
            summary_lower = summary.lower()
            assert any(word in summary_lower for word in ["contradiction", "conflicting", "found"])
        
        print("✓ Role edge cases work")
    
    def _create_sample_trace(self) -> OrchestrationResult:
        """Create a sample trace for testing."""
        stages = [
            StageTrace(
                name="observe",
                input={"query": "What is machine learning?"},
                output={"intent": "information_request"},
                metrics=StageMetrics(duration_ms=150.0)
            ),
            StageTrace(
                name="expand",
                input={"entities": ["machine learning"]},
                output={"concepts": ["artificial intelligence"]},
                metrics=StageMetrics(duration_ms=200.0)
            )
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "direct_answer"},
            timings={"total_ms": 350.0, "orchestration_ms": 300.0, "planning_ms": 50.0},
            warnings=[],
            selected_context_ids=["ctx_001", "ctx_002"],
            contradictions=[],
            knobs={}
        )
    
    def _create_long_trace(self) -> OrchestrationResult:
        """Create a long trace for testing."""
        stages = []
        for i in range(20):
            stages.append(StageTrace(
                name=f"stage_{i}",
                input={"data": f"input_{i}"},
                output={"result": f"output_{i}"},
                metrics=StageMetrics(duration_ms=float(i * 10))
            ))
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "complex"},
            timings={"total_ms": 2000.0, "orchestration_ms": 1500.0, "planning_ms": 500.0},
            warnings=["Warning 1", "Warning 2", "Warning 3"],
            selected_context_ids=[f"ctx_{i:03d}" for i in range(50)],
            contradictions=[],
            knobs={}
        )
    
    def _create_contradiction_trace(self) -> OrchestrationResult:
        """Create a trace with many contradictions."""
        stages = [
            StageTrace(
                name="contrast",
                input={"data": "test"},
                output={"contradictions": 10},
                metrics=StageMetrics(duration_ms=100.0)
            )
        ]
        
        contradictions = [
            {"type": "factual_contradiction", "severity": "high"},
            {"type": "temporal_contradiction", "severity": "medium"},
            {"type": "numerical_contradiction", "severity": "low"},
            {"type": "logical_contradiction", "severity": "high"},
            {"type": "semantic_contradiction", "severity": "medium"}
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "complex"},
            timings={"total_ms": 100.0},
            warnings=[],
            selected_context_ids=["ctx_001", "ctx_002"],
            contradictions=contradictions,
            knobs={}
        )


def main():
    """Run all role-aware summarization tests."""
    print("Running role-aware summarization tests...\n")
    
    try:
        # Test role-aware summarization
        test_roles = TestRoleAwareSummarization()
        test_roles.test_summarize_for_role_general()
        test_roles.test_summarize_for_role_pro()
        test_roles.test_summarize_for_role_scholars()
        test_roles.test_summarize_for_role_analytics()
        test_roles.test_summarize_for_role_ops()
        test_roles.test_summarize_for_role_invalid()
        test_roles.test_summarize_for_role_max_lines_override()
        test_roles.test_role_summary_stats()
        test_roles.test_redaction_functionality()
        test_roles.test_contradiction_types()
        test_roles.test_performance_summary()
        test_roles.test_role_differences()
        test_roles.test_general_role_no_pii()
        test_roles.test_professional_roles_include_details()
        test_roles.test_ops_role_full_details()
        
        # Test integration
        test_integration = TestRoleIntegration()
        test_integration.test_role_consistency()
        test_integration.test_role_with_different_traces()
        test_integration.test_role_edge_cases()
        
        print("\n🎉 All role-aware summarization tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())