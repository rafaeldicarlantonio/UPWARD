"""
Tests for ledger writer and trace summary generator.
"""

import json
import sys
from typing import Dict, Any, List

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.types import OrchestrationResult, StageTrace, StageMetrics
from core.ledger import write_ledger, LedgerOptions, LedgerEntry, _truncate_trace, _generate_trace_hash
from core.trace_summary import summarize_trace, summarize_trace_from_dict, get_summary_stats, format_summary_for_display


class TestLedgerWriter:
    """Test ledger writer functionality."""
    
    def test_write_ledger_basic(self):
        """Test basic ledger writing functionality."""
        print("Testing basic ledger writing...")
        
        # Create sample trace
        trace = self._create_sample_trace()
        
        # Write to ledger
        entry = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=trace
        )
        
        # Verify entry structure
        assert isinstance(entry, LedgerEntry)
        assert entry.session_id == "test_session_123"
        assert entry.message_id == "test_message_456"
        assert entry.trace_data is not None
        assert entry.original_size > 0
        assert entry.stored_size > 0
        assert entry.stored_size <= entry.original_size
        
        print("✓ Basic ledger writing works")
    
    def test_write_ledger_with_options(self):
        """Test ledger writing with custom options."""
        print("Testing ledger writing with options...")
        
        trace = self._create_sample_trace()
        
        options = LedgerOptions(
            max_trace_bytes=1000,
            enable_hashing=True,
            redact_large_fields=True,
            hash_algorithm="sha256"
        )
        
        entry = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=trace,
            options=options
        )
        
        # Verify options were applied
        assert entry.trace_hash is not None
        assert len(entry.trace_hash) == 64  # SHA256 hash length
        assert entry.stored_size <= options.max_trace_bytes
        
        print("✓ Ledger writing with options works")
    
    def test_write_ledger_size_enforcement(self):
        """Test that size limits are enforced."""
        print("Testing size enforcement...")
        
        # Create large trace
        large_trace = self._create_large_trace()
        
        options = LedgerOptions(max_trace_bytes=5000)
        entry = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=large_trace,
            options=options
        )
        
        # Verify size enforcement
        assert entry.stored_size <= options.max_trace_bytes
        assert entry.is_truncated == (entry.original_size > options.max_trace_bytes)
        
        if entry.is_truncated:
            # Check truncation metadata
            assert "_truncation" in entry.trace_data
            truncation_info = entry.trace_data["_truncation"]
            assert "original_stages_count" in truncation_info
            assert "truncated_stages_count" in truncation_info
            assert truncation_info["truncated_stages_count"] <= truncation_info["original_stages_count"]
        
        print("✓ Size enforcement works")
    
    def test_write_ledger_hashing(self):
        """Test trace hashing functionality."""
        print("Testing trace hashing...")
        
        trace = self._create_sample_trace()
        
        # Test with hashing enabled
        options_with_hash = LedgerOptions(enable_hashing=True, hash_algorithm="sha256")
        entry_with_hash = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=trace,
            options=options_with_hash
        )
        
        # Test with hashing disabled
        options_without_hash = LedgerOptions(enable_hashing=False)
        entry_without_hash = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=trace,
            options=options_without_hash
        )
        
        # Verify hashing behavior
        assert entry_with_hash.trace_hash is not None
        assert entry_without_hash.trace_hash is None
        
        # Verify hash is consistent for same data
        assert len(entry_with_hash.trace_hash) == 64  # SHA256
        
        print("✓ Trace hashing works")
    
    def test_truncate_trace_function(self):
        """Test trace truncation function directly."""
        print("Testing trace truncation...")
        
        # Create large trace data
        large_trace_data = self._create_large_trace_data()
        
        # Test truncation
        truncated_data, was_truncated = _truncate_trace(large_trace_data, 1000)
        
        # Verify truncation
        truncated_size = len(json.dumps(truncated_data, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
        assert truncated_size <= 1000
        assert was_truncated == (len(large_trace_data.get("stages", [])) > len(truncated_data.get("stages", [])))
        
        # Verify structure is preserved
        assert "version" in truncated_data
        assert "stages" in truncated_data
        assert "timestamp" in truncated_data
        
        print("✓ Trace truncation works")
    
    def test_generate_trace_hash(self):
        """Test trace hash generation."""
        print("Testing trace hash generation...")
        
        trace_data = {"test": "data", "number": 123}
        
        # Test SHA256
        hash_sha256 = _generate_trace_hash(trace_data, "sha256")
        assert len(hash_sha256) == 64
        assert hash_sha256.isalnum()
        
        # Test MD5
        hash_md5 = _generate_trace_hash(trace_data, "md5")
        assert len(hash_md5) == 32
        assert hash_md5.isalnum()
        
        # Test consistency
        hash_sha256_2 = _generate_trace_hash(trace_data, "sha256")
        assert hash_sha256 == hash_sha256_2
        
        print("✓ Trace hash generation works")
    
    def _create_sample_trace(self) -> OrchestrationResult:
        """Create a sample trace for testing."""
        stages = [
            StageTrace(
                name="observe",
                input={"query": "test query"},
                output={"intent": "test"},
                metrics=StageMetrics(duration_ms=100.0, tokens_processed=50)
            ),
            StageTrace(
                name="expand",
                input={"entities": ["test"]},
                output={"concepts": ["concept1"]},
                metrics=StageMetrics(duration_ms=200.0, tokens_processed=100)
            )
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test"},
            timings={"total_ms": 300.0},
            warnings=["test warning"],
            selected_context_ids=["ctx1", "ctx2"],
            contradictions=[],
            knobs={"test_knob": "value"}
        )
    
    def _create_large_trace(self) -> OrchestrationResult:
        """Create a large trace for testing size limits."""
        stages = []
        for i in range(50):  # Create many stages
            stages.append(StageTrace(
                name=f"stage_{i}",
                input={"large_data": "x" * 1000},
                output={"large_result": "y" * 1000},
                metrics=StageMetrics(duration_ms=float(i), custom_metrics={"data": "z" * 500})
            ))
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test", "data": "x" * 2000},
            timings={"total_ms": 1000.0},
            warnings=["warning"] * 20,
            selected_context_ids=["ctx"] * 30,
            contradictions=[{"type": "test", "data": "x" * 500}] * 10,
            knobs={"test": "value", "data": "x" * 1000}
        )
    
    def _create_large_trace_data(self) -> Dict[str, Any]:
        """Create large trace data dictionary."""
        stages = []
        for i in range(100):
            stages.append({
                "name": f"stage_{i}",
                "input": {"large_data": "x" * 1000},
                "output": {"large_result": "y" * 1000},
                "metrics": {
                    "duration_ms": float(i),
                    "custom_metrics": {"data": "z" * 500}
                }
            })
        
        return {
            "version": "1.0",
            "stages": stages,
            "knobs": {"test": "value", "data": "x" * 1000},
            "contradictions": [{"type": "test", "data": "x" * 500}] * 20,
            "selected_context_ids": ["ctx"] * 50,
            "final_plan": {"type": "test", "data": "x" * 2000},
            "timings": {"total_ms": 1000.0},
            "warnings": ["warning"] * 30,
            "timestamp": "2024-01-01T00:00:00.000000"
        }


class TestTraceSummary:
    """Test trace summary functionality."""
    
    def test_summarize_trace_basic(self):
        """Test basic trace summarization."""
        print("Testing basic trace summarization...")
        
        trace = self._create_sample_trace()
        summary = summarize_trace(trace, max_lines=4)
        
        # Verify summary structure
        assert isinstance(summary, str)
        lines = summary.split('\n')
        assert 2 <= len(lines) <= 4
        
        # Check for expected content
        summary_text = summary.lower()
        assert "stages" in summary_text
        assert "context" in summary_text
        
        print("✓ Basic trace summarization works")
    
    def test_summarize_trace_with_contradictions(self):
        """Test trace summarization with contradictions."""
        print("Testing trace summarization with contradictions...")
        
        trace = self._create_trace_with_contradictions()
        summary = summarize_trace(trace, max_lines=4)
        
        # Verify contradiction information is included
        assert "contradictions:" in summary.lower()
        assert "3" in summary  # Should show contradiction count
        
        print("✓ Trace summarization with contradictions works")
    
    def test_summarize_trace_with_warnings(self):
        """Test trace summarization with warnings."""
        print("Testing trace summarization with warnings...")
        
        trace = self._create_trace_with_warnings()
        summary = summarize_trace(trace, max_lines=4)
        
        # Verify warning information is included
        assert "warning" in summary.lower()
        
        print("✓ Trace summarization with warnings works")
    
    def test_summarize_trace_max_lines(self):
        """Test trace summarization with different max_lines values."""
        print("Testing trace summarization max_lines...")
        
        trace = self._create_sample_trace()
        
        # Test different max_lines values
        for max_lines in [2, 3, 4]:
            summary = summarize_trace(trace, max_lines=max_lines)
            lines = summary.split('\n')
            assert len(lines) <= max_lines
            assert len(lines) >= 2  # Should always have at least 2 lines
        
        print("✓ Trace summarization max_lines works")
    
    def test_summarize_trace_from_dict(self):
        """Test trace summarization from dictionary."""
        print("Testing trace summarization from dict...")
        
        trace_data = {
            "stages": [
                {"name": "observe", "metrics": {"duration_ms": 100.0}},
                {"name": "expand", "metrics": {"duration_ms": 200.0}}
            ],
            "contradictions": [
                {"type": "factual", "severity": "high"},
                {"type": "temporal", "severity": "medium"}
            ],
            "selected_context_ids": ["ctx1", "ctx2", "ctx3"],
            "warnings": ["test warning"],
            "timings": {"total_ms": 300.0}
        }
        
        summary = summarize_trace_from_dict(trace_data, max_lines=4)
        
        # Verify summary structure
        assert isinstance(summary, str)
        lines = summary.split('\n')
        assert 2 <= len(lines) <= 4
        
        # Check for expected content
        assert "contradictions:" in summary.lower()
        assert "ctx1" in summary
        
        print("✓ Trace summarization from dict works")
    
    def test_get_summary_stats(self):
        """Test summary statistics generation."""
        print("Testing summary statistics...")
        
        trace = self._create_trace_with_contradictions()
        stats = get_summary_stats(trace)
        
        # Verify stats structure
        assert "stage_count" in stats
        assert "stage_types" in stats
        assert "contradiction_counts" in stats
        assert "context_items_selected" in stats
        assert "warning_count" in stats
        assert "timing_breakdown" in stats
        assert "has_high_severity_contradictions" in stats
        assert "has_warnings" in stats
        
        # Verify contradiction counts
        assert stats["contradiction_counts"]["total"] == 3
        assert stats["contradiction_counts"]["high"] == 1
        assert stats["has_high_severity_contradictions"] == True
        
        print("✓ Summary statistics work")
    
    def test_format_summary_for_display(self):
        """Test summary formatting for display."""
        print("Testing summary formatting...")
        
        trace = self._create_sample_trace()
        summary = summarize_trace(trace, max_lines=3)
        formatted = format_summary_for_display(summary, indent="  ")
        
        # Verify formatting
        lines = formatted.split('\n')
        for line in lines:
            assert line.startswith("  ")
        
        print("✓ Summary formatting works")
    
    def test_summary_edge_cases(self):
        """Test summary generation with edge cases."""
        print("Testing summary edge cases...")
        
        # Test with empty trace
        empty_trace = OrchestrationResult()
        summary = summarize_trace(empty_trace, max_lines=4)
        assert isinstance(summary, str)
        assert len(summary.split('\n')) >= 2
        
        # Test with minimal trace
        minimal_trace = OrchestrationResult(
            stages=[StageTrace(name="test", metrics=StageMetrics(duration_ms=100.0))],
            timings={"total_ms": 100.0}
        )
        summary = summarize_trace(minimal_trace, max_lines=4)
        assert isinstance(summary, str)
        
        print("✓ Summary edge cases work")
    
    def _create_sample_trace(self) -> OrchestrationResult:
        """Create a sample trace for testing."""
        stages = [
            StageTrace(
                name="observe",
                input={"query": "test query"},
                output={"intent": "test"},
                metrics=StageMetrics(duration_ms=100.0, tokens_processed=50)
            ),
            StageTrace(
                name="expand",
                input={"entities": ["test"]},
                output={"concepts": ["concept1"]},
                metrics=StageMetrics(duration_ms=200.0, tokens_processed=100)
            )
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test"},
            timings={"total_ms": 300.0},
            warnings=[],
            selected_context_ids=["ctx1", "ctx2", "ctx3"],
            contradictions=[],
            knobs={"test_knob": "value"}
        )
    
    def _create_trace_with_contradictions(self) -> OrchestrationResult:
        """Create a trace with contradictions for testing."""
        stages = [
            StageTrace(
                name="observe",
                metrics=StageMetrics(duration_ms=100.0)
            ),
            StageTrace(
                name="contrast",
                metrics=StageMetrics(duration_ms=200.0)
            )
        ]
        
        contradictions = [
            {"type": "factual", "severity": "high", "subject": "test"},
            {"type": "temporal", "severity": "medium", "subject": "test"},
            {"type": "numerical", "severity": "low", "subject": "test"}
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test"},
            timings={"total_ms": 300.0},
            warnings=[],
            selected_context_ids=["ctx1", "ctx2"],
            contradictions=contradictions,
            knobs={}
        )
    
    def _create_trace_with_warnings(self) -> OrchestrationResult:
        """Create a trace with warnings for testing."""
        stages = [
            StageTrace(
                name="observe",
                metrics=StageMetrics(duration_ms=100.0)
            )
        ]
        
        warnings = [
            "Low relevance scores in retrieval results",
            "Limited retrieval results",
            "High complexity query may require additional processing"
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test"},
            timings={"total_ms": 100.0},
            warnings=warnings,
            selected_context_ids=["ctx1"],
            contradictions=[],
            knobs={}
        )


class TestIntegration:
    """Integration tests for ledger and summary functionality."""
    
    def test_ledger_and_summary_integration(self):
        """Test integration between ledger writing and summary generation."""
        print("Testing ledger and summary integration...")
        
        # Create trace
        trace = self._create_sample_trace()
        
        # Write to ledger
        entry = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=trace
        )
        
        # Generate summary from trace
        summary_from_trace = summarize_trace(trace, max_lines=4)
        
        # Generate summary from ledger entry
        summary_from_dict = summarize_trace_from_dict(entry.trace_data, max_lines=4)
        
        # Verify summaries are similar (may differ due to truncation)
        assert isinstance(summary_from_trace, str)
        assert isinstance(summary_from_dict, str)
        assert len(summary_from_trace.split('\n')) >= 2
        assert len(summary_from_dict.split('\n')) >= 2
        
        print("✓ Ledger and summary integration works")
    
    def test_large_trace_handling(self):
        """Test handling of large traces with size limits."""
        print("Testing large trace handling...")
        
        # Create large trace
        large_trace = self._create_large_trace()
        
        # Write with size limit
        options = LedgerOptions(max_trace_bytes=2000)
        entry = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=large_trace,
            options=options
        )
        
        # Verify size enforcement
        assert entry.stored_size <= options.max_trace_bytes
        assert entry.is_truncated == (entry.original_size > options.max_trace_bytes)
        
        # Generate summary from truncated trace
        summary = summarize_trace_from_dict(entry.trace_data, max_lines=4)
        assert isinstance(summary, str)
        assert len(summary.split('\n')) >= 2
        
        print("✓ Large trace handling works")
    
    def test_contradiction_counting(self):
        """Test that contradiction counting works correctly in summaries."""
        print("Testing contradiction counting...")
        
        # Create trace with contradictions
        trace = self._create_trace_with_contradictions()
        
        # Write to ledger
        entry = write_ledger(
            session_id="test_session_123",
            message_id="test_message_456",
            trace=trace
        )
        
        # Generate summary
        summary = summarize_trace_from_dict(entry.trace_data, max_lines=4)
        
        # Verify contradiction count is included
        assert "contradictions:" in summary.lower()
        assert "3" in summary  # Should show the count
        
        print("✓ Contradiction counting works")
    
    def _create_sample_trace(self) -> OrchestrationResult:
        """Create a sample trace for testing."""
        stages = [
            StageTrace(
                name="observe",
                input={"query": "test query"},
                output={"intent": "test"},
                metrics=StageMetrics(duration_ms=100.0, tokens_processed=50)
            ),
            StageTrace(
                name="expand",
                input={"entities": ["test"]},
                output={"concepts": ["concept1"]},
                metrics=StageMetrics(duration_ms=200.0, tokens_processed=100)
            )
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test"},
            timings={"total_ms": 300.0},
            warnings=[],
            selected_context_ids=["ctx1", "ctx2", "ctx3"],
            contradictions=[],
            knobs={"test_knob": "value"}
        )
    
    def _create_large_trace(self) -> OrchestrationResult:
        """Create a large trace for testing."""
        stages = []
        for i in range(20):  # Create many stages
            stages.append(StageTrace(
                name=f"stage_{i}",
                input={"large_data": "x" * 500},
                output={"large_result": "y" * 500},
                metrics=StageMetrics(duration_ms=float(i), custom_metrics={"data": "z" * 200})
            ))
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test", "data": "x" * 1000},
            timings={"total_ms": 1000.0},
            warnings=["warning"] * 10,
            selected_context_ids=["ctx"] * 15,
            contradictions=[{"type": "test", "data": "x" * 200}] * 5,
            knobs={"test": "value", "data": "x" * 500}
        )
    
    def _create_trace_with_contradictions(self) -> OrchestrationResult:
        """Create a trace with contradictions for testing."""
        stages = [
            StageTrace(
                name="observe",
                metrics=StageMetrics(duration_ms=100.0)
            ),
            StageTrace(
                name="contrast",
                metrics=StageMetrics(duration_ms=200.0)
            )
        ]
        
        contradictions = [
            {"type": "factual", "severity": "high", "subject": "test"},
            {"type": "temporal", "severity": "medium", "subject": "test"},
            {"type": "numerical", "severity": "low", "subject": "test"}
        ]
        
        return OrchestrationResult(
            stages=stages,
            final_plan={"type": "test"},
            timings={"total_ms": 300.0},
            warnings=[],
            selected_context_ids=["ctx1", "ctx2"],
            contradictions=contradictions,
            knobs={}
        )


def main():
    """Run all ledger and summary tests."""
    print("Running ledger and summary tests...\n")
    
    try:
        # Test ledger writer
        test_ledger = TestLedgerWriter()
        test_ledger.test_write_ledger_basic()
        test_ledger.test_write_ledger_with_options()
        test_ledger.test_write_ledger_size_enforcement()
        test_ledger.test_write_ledger_hashing()
        test_ledger.test_truncate_trace_function()
        test_ledger.test_generate_trace_hash()
        
        # Test trace summary
        test_summary = TestTraceSummary()
        test_summary.test_summarize_trace_basic()
        test_summary.test_summarize_trace_with_contradictions()
        test_summary.test_summarize_trace_with_warnings()
        test_summary.test_summarize_trace_max_lines()
        test_summary.test_summarize_trace_from_dict()
        test_summary.test_get_summary_stats()
        test_summary.test_format_summary_for_display()
        test_summary.test_summary_edge_cases()
        
        # Test integration
        test_integration = TestIntegration()
        test_integration.test_ledger_and_summary_integration()
        test_integration.test_large_trace_handling()
        test_integration.test_contradiction_counting()
        
        print("\n🎉 All ledger and summary tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())