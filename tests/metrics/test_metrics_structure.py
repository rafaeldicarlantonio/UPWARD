"""
Python structure tests for metrics implementation.
"""

from pathlib import Path


class TestMetricsLibStructure:
    """Test metrics.ts structure."""
    
    def test_metrics_file_exists(self):
        assert Path("/workspace/app/lib/metrics.ts").exists()
    
    def test_defines_event_types(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "interface LedgerExpandProps" in content
        assert "interface CompareRunProps" in content
        assert "interface HypothesisPromoteProps" in content
        assert "interface AuraProjectProps" in content
        assert "interface ContradictionTooltipProps" in content
    
    def test_defines_base_event_props(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "interface BaseEventProps" in content
        assert "role: Role" in content
        assert "timestamp: string" in content
    
    def test_defines_metric_events(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "enum MetricEvent" in content or "MetricEvent" in content
        assert "ui.ledger.expand" in content
        assert "ui.compare.run" in content
        assert "ui.hypothesis.promote" in content
        assert "ui.aura.propose" in content
        assert "ui.contradiction.tooltip.open" in content
    
    def test_implements_one_shot_tracker(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "OneShotTracker" in content or "oneShot" in content
        assert "hasFired" in content or "has_fired" in content.lower()
        assert "markFired" in content or "mark_fired" in content.lower()
    
    def test_implements_metrics_client(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "class MetricsClient" in content
        assert "trackLedgerExpand" in content
        assert "trackCompareRun" in content
        assert "trackHypothesisPromote" in content
        assert "trackAuraPropose" in content
        assert "trackContradictionTooltipOpen" in content


class TestMetricsProps:
    """Test metrics property definitions."""
    
    def test_ledger_expand_props(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "traceLinesInSummary" in content
        assert "traceLinesInFull" in content
        assert "messageId" in content
    
    def test_compare_run_props(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "allowExternal" in content
        assert "internalEvidenceA" in content
        assert "internalEvidenceB" in content
        assert "externalEvidenceB" in content
    
    def test_hypothesis_promote_props(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "evidenceCount" in content
        assert "score" in content
        assert "persisted" in content
    
    def test_aura_project_props(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "hypothesisId" in content
        assert "hypothesisPreLinked" in content
        assert "starterTaskCount" in content
    
    def test_contradiction_tooltip_props(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "contradictionCount" in content
        assert "highestSeverity" in content
        assert "evidenceAnchor" in content


class TestUseMetricsHook:
    """Test useMetrics hook structure."""
    
    def test_hook_file_exists(self):
        assert Path("/workspace/app/hooks/useMetrics.ts").exists()
    
    def test_imports_metrics_lib(self):
        content = Path("/workspace/app/hooks/useMetrics.ts").read_text()
        assert "from '../lib/metrics'" in content
    
    def test_exports_use_metrics(self):
        content = Path("/workspace/app/hooks/useMetrics.ts").read_text()
        assert "export function useMetrics" in content
    
    def test_has_specialized_hooks(self):
        content = Path("/workspace/app/hooks/useMetrics.ts").read_text()
        assert "useLedgerMetrics" in content
        assert "useCompareMetrics" in content
        assert "useHypothesisMetrics" in content
        assert "useAuraMetrics" in content
        assert "useContradictionMetrics" in content
    
    def test_uses_role_from_session(self):
        content = Path("/workspace/app/hooks/useMetrics.ts").read_text()
        assert "getUserRole" in content
    
    def test_generates_instance_id(self):
        content = Path("/workspace/app/hooks/useMetrics.ts").read_text()
        assert "instanceId" in content


class TestMetricsTests:
    """Test uxMetrics.test.ts structure."""
    
    def test_test_file_exists(self):
        assert Path("/workspace/tests/metrics/uxMetrics.test.ts").exists()
    
    def test_imports_metrics_lib(self):
        content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "from '../../app/lib/metrics'" in content
    
    def test_has_mock_analytics_provider(self):
        content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "MockAnalyticsProvider" in content or "mock" in content.lower()
    
    def test_has_one_shot_tests(self):
        content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "One-Shot" in content or "one shot" in content.lower()
        assert "duplicate" in content.lower()
    
    def test_has_payload_shape_tests(self):
        content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "Payload Shape" in content or "payload" in content.lower()
        assert "toHaveProperty" in content or "shape" in content.lower()
    
    def test_has_role_tracking_tests(self):
        content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "Role Tracking" in content or "role" in content.lower()
    
    def test_has_count_tracking_tests(self):
        content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "Count Tracking" in content or "count" in content.lower()


class TestOneShotBehavior:
    """Test one-shot behavior implementation."""
    
    def test_prevents_duplicates(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "hasFired" in content or "fired" in content.lower()
        
    def test_uses_instance_id(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "instanceId" in content
    
    def test_has_reset_method(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "reset" in content.lower()


class TestEventDefinitions:
    """Test all 5 required events are defined."""
    
    def test_ledger_expand_event(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "ui.ledger.expand" in content
    
    def test_compare_run_event(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "ui.compare.run" in content
    
    def test_hypothesis_promote_event(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "ui.hypothesis.promote" in content
    
    def test_aura_propose_event(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "ui.aura.propose" in content
    
    def test_contradiction_tooltip_event(self):
        content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "ui.contradiction.tooltip.open" in content


class TestAcceptanceCriteria:
    """Verify acceptance criteria."""
    
    def test_events_fire_once(self):
        test_content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "fire exactly once" in test_content.lower() or "once per action" in test_content.lower()
    
    def test_payload_shapes_asserted(self):
        test_content = Path("/workspace/tests/metrics/uxMetrics.test.ts").read_text()
        assert "payload shape" in test_content.lower() or "toMatchObject" in test_content
    
    def test_role_included(self):
        metrics_content = Path("/workspace/app/lib/metrics.ts").read_text()
        assert "role: Role" in metrics_content
    
    def test_counts_included(self):
        metrics_content = Path("/workspace/app/lib/metrics.ts").read_text()
        # Check for various count fields
        assert "contradictionCount" in metrics_content or "Count" in metrics_content
        assert "evidenceCount" in metrics_content or "evidence" in metrics_content.lower()
