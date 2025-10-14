"""
Tests for REDO evaluation system.
"""

import sys
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.run_redo import RedoEvalRunner, RedoEvalResult, RedoEvalSummary
from core.orchestrator.deterministic import DeterministicOrchestrator, DeterministicConfig
from core.types import QueryContext, OrchestrationConfig, OrchestrationResult, StageTrace, StageMetrics


class TestRedoEvalRunner:
    """Test REDO evaluation runner."""
    
    def test_deterministic_mode_initialization(self):
        """Test deterministic mode initialization."""
        print("Testing deterministic mode initialization...")
        
        runner = RedoEvalRunner(deterministic_mode=True, seed=12345)
        
        assert runner.deterministic_mode == True
        assert runner.seed == 12345
        assert runner.orchestrator is not None
        assert isinstance(runner.orchestrator, DeterministicOrchestrator)
        
        print("✓ Deterministic mode initialization works")
    
    def test_non_deterministic_mode_initialization(self):
        """Test non-deterministic mode initialization."""
        print("Testing non-deterministic mode initialization...")
        
        runner = RedoEvalRunner(deterministic_mode=False, seed=42)
        
        assert runner.deterministic_mode == False
        assert runner.seed == 42
        assert runner.orchestrator is None
        
        print("✓ Non-deterministic mode initialization works")
    
    def test_load_testset(self):
        """Test loading testset from JSON file."""
        print("Testing testset loading...")
        
        # Create temporary testset file
        testset_data = [
            {
                "id": "test_001",
                "prompt": "Test prompt",
                "category": "test",
                "test_type": "unit_test",
                "must_include": ["test"],
                "fixtures": {"retrieval_results": []}
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(testset_data, f)
            temp_path = f.name
        
        try:
            runner = RedoEvalRunner()
            loaded_cases = runner.load_testset(temp_path)
            
            assert len(loaded_cases) == 1
            assert loaded_cases[0]["id"] == "test_001"
            assert loaded_cases[0]["prompt"] == "Test prompt"
            
        finally:
            os.unlink(temp_path)
        
        print("✓ Testset loading works")
    
    def test_deterministic_case_execution(self):
        """Test deterministic case execution."""
        print("Testing deterministic case execution...")
        
        # Create test case
        case = {
            "id": "deterministic_test_001",
            "prompt": "What are the key factors for project success?",
            "category": "deterministic",
            "test_type": "deterministic_ordering",
            "seed": 12345,
            "must_include": ["project", "success", "factors"],
            "fixtures": {
                "retrieval_results": [
                    {
                        "id": "ctx_001",
                        "content": "Clear project objectives and scope definition",
                        "relevance_score": 0.9,
                        "importance_score": 0.8,
                        "source": "project_management_guide"
                    },
                    {
                        "id": "ctx_002",
                        "content": "Effective team communication and collaboration",
                        "relevance_score": 0.8,
                        "importance_score": 0.9,
                        "source": "team_leadership_handbook"
                    }
                ]
            },
            "expected_outputs": {
                "stage_order": ["observe", "expand", "contrast", "order"],
                "selected_context_ids": ["ctx_002", "ctx_001"],
                "contradictions_count": 0,
                "final_plan_type": "direct_answer"
            }
        }
        
        runner = RedoEvalRunner(deterministic_mode=True, seed=12345)
        result = runner.run_single_case(case)
        
        # Verify basic result structure
        assert result.case_id == "deterministic_test_001"
        assert result.prompt == "What are the key factors for project success?"
        assert result.category == "deterministic"
        assert result.test_type == "deterministic_ordering"
        assert result.deterministic_output == True
        
        # Verify stage execution
        assert result.stages_completed == 4
        assert result.expected_stages == ["observe", "expand", "contrast", "order"]
        assert result.stage_order_correct == True
        
        # Verify timing
        assert result.total_latency_ms > 0
        assert result.observe_latency_ms > 0
        assert result.expand_latency_ms > 0
        assert result.contrast_latency_ms > 0
        assert result.order_latency_ms > 0
        
        print("✓ Deterministic case execution works")
    
    def test_ordering_evaluation(self):
        """Test ordering evaluation."""
        print("Testing ordering evaluation...")
        
        case = {
            "id": "ordering_test_001",
            "prompt": "What are the key factors for successful project management?",
            "category": "ordering",
            "test_type": "priority_ordering",
            "seed": 54321,
            "must_include": ["project", "management", "factors"],
            "fixtures": {
                "retrieval_results": [
                    {
                        "id": "ctx_001",
                        "content": "Budget management is crucial for project success",
                        "relevance_score": 0.9,
                        "importance_score": 0.8,
                        "source": "project_management_guide"
                    },
                    {
                        "id": "ctx_002",
                        "content": "Team communication and collaboration are essential",
                        "relevance_score": 0.8,
                        "importance_score": 0.9,
                        "source": "team_leadership_handbook"
                    },
                    {
                        "id": "ctx_003",
                        "content": "Timeline planning and milestone tracking",
                        "relevance_score": 0.7,
                        "importance_score": 0.7,
                        "source": "project_planning_methodology"
                    }
                ]
            },
            "expected_outputs": {
                "stage_order": ["observe", "expand", "contrast", "order"],
                "selected_context_ids": ["ctx_001", "ctx_002", "ctx_003"],  # Ordered by relevance first
                "contradictions_count": 0,
                "final_plan_type": "direct_answer"
            }
        }
        
        runner = RedoEvalRunner(deterministic_mode=True, seed=54321)
        result = runner.run_single_case(case)
        
        # Verify ordering
        assert result.ordering_correct == True
        assert result.selected_context_ids == ["ctx_001", "ctx_002", "ctx_003"]  # Ordered by relevance first
        assert result.meets_ordering_constraint == True
        
        print("✓ Ordering evaluation works")
    
    def test_contradiction_surfacing_evaluation(self):
        """Test contradiction surfacing evaluation."""
        print("Testing contradiction surfacing evaluation...")
        
        case = {
            "id": "contradiction_test_001",
            "prompt": "What is the company's policy on remote work?",
            "category": "contradiction_surfacing",
            "test_type": "policy_contradiction",
            "seed": 98765,
            "must_include": ["remote", "work", "policy"],
            "expected_contradictions": True,
            "fixtures": {
                "retrieval_results": [
                    {
                        "id": "ctx_001",
                        "content": "Remote work is fully supported and encouraged for all employees",
                        "relevance_score": 0.9,
                        "source": "hr_policy_2024",
                        "timestamp": "2024-01-15"
                    },
                    {
                        "id": "ctx_002",
                        "content": "Remote work is only allowed for senior employees with manager approval",
                        "relevance_score": 0.8,
                        "source": "management_guidelines_2023",
                        "timestamp": "2023-12-01"
                    }
                ]
            },
            "expected_outputs": {
                "stage_order": ["observe", "expand", "contrast", "order"],
                "selected_context_ids": ["ctx_001", "ctx_002"],
                "contradictions_count": 1,
                "final_plan_type": "contradiction_aware"
            }
        }
        
        runner = RedoEvalRunner(deterministic_mode=True, seed=98765)
        result = runner.run_single_case(case)
        
        # Verify contradiction detection
        assert result.contradictions_found > 0
        assert result.expected_contradictions == True
        assert result.contradiction_detection_correct == True
        assert result.meets_contradiction_constraint == True
        
        print("✓ Contradiction surfacing evaluation works")
    
    def test_latency_constraint_evaluation(self):
        """Test latency constraint evaluation."""
        print("Testing latency constraint evaluation...")
        
        case = {
            "id": "latency_test_001",
            "prompt": "Test prompt for latency",
            "category": "performance",
            "test_type": "latency_test",
            "seed": 11111,
            "max_latency_ms": 100,  # Very low latency requirement
            "must_include": ["test"],
            "fixtures": {"retrieval_results": []},
            "expected_outputs": {
                "stage_order": ["observe", "expand", "contrast", "order"],
                "selected_context_ids": [],
                "contradictions_count": 0,
                "final_plan_type": "direct_answer"
            }
        }
        
        runner = RedoEvalRunner(deterministic_mode=True, seed=11111)
        result = runner.run_single_case(case)
        
        # Verify latency constraint
        assert result.total_latency_ms > 0
        assert result.meets_latency_constraint == True  # Should pass with deterministic timing
        
        print("✓ Latency constraint evaluation works")
    
    def test_eval_summary_generation(self):
        """Test evaluation summary generation."""
        print("Testing evaluation summary generation...")
        
        # Create mock results
        results = [
            RedoEvalResult(
                case_id="test_001",
                prompt="Test prompt 1",
                category="ordering",
                test_type="priority_ordering",
                passed=True,
                latency_ms=50.0,
                total_latency_ms=50.0,
                stages_completed=4,
                expected_stages=["observe", "expand", "contrast", "order"],
                stage_order_correct=True,
                selected_context_ids=["ctx_001", "ctx_002"],
                contradictions_found=0,
                expected_contradictions=False,
                contradiction_detection_correct=True,
                ordering_correct=True,
                deterministic_output=True,
                observe_latency_ms=10.0,
                expand_latency_ms=15.0,
                contrast_latency_ms=10.0,
                order_latency_ms=15.0,
                meets_latency_constraint=True,
                meets_ordering_constraint=True,
                meets_contradiction_constraint=True,
                meets_deterministic_constraint=True
            ),
            RedoEvalResult(
                case_id="test_002",
                prompt="Test prompt 2",
                category="contradiction_surfacing",
                test_type="policy_contradiction",
                passed=True,
                latency_ms=75.0,
                total_latency_ms=75.0,
                stages_completed=4,
                expected_stages=["observe", "expand", "contrast", "order"],
                stage_order_correct=True,
                selected_context_ids=["ctx_003", "ctx_004"],
                contradictions_found=1,
                expected_contradictions=True,
                contradiction_detection_correct=True,
                ordering_correct=True,
                deterministic_output=True,
                observe_latency_ms=15.0,
                expand_latency_ms=20.0,
                contrast_latency_ms=15.0,
                order_latency_ms=25.0,
                meets_latency_constraint=True,
                meets_ordering_constraint=True,
                meets_contradiction_constraint=True,
                meets_deterministic_constraint=True
            )
        ]
        
        runner = RedoEvalRunner()
        runner.results = results
        summary = runner.generate_summary()
        
        # Verify basic statistics
        assert summary.total_cases == 2
        assert summary.passed_cases == 2
        assert summary.failed_cases == 0
        
        # Verify latency statistics
        assert summary.avg_latency_ms == 62.5  # (50 + 75) / 2
        assert summary.max_latency_ms == 75.0
        
        # Verify REDO-specific metrics
        assert summary.ordering_accuracy == 1.0  # 2/2 correct
        assert summary.contradiction_detection_accuracy == 1.0  # 2/2 correct
        assert summary.deterministic_consistency == 1.0  # 2/2 deterministic
        assert summary.stage_completion_rate == 1.0  # All stages completed
        
        # Verify category breakdown
        assert "ordering" in summary.category_breakdown
        assert "contradiction_surfacing" in summary.category_breakdown
        assert summary.category_breakdown["ordering"]["passed"] == 1
        assert summary.category_breakdown["contradiction_surfacing"]["passed"] == 1
        
        print("✓ Evaluation summary generation works")
    
    def test_full_eval_run(self):
        """Test full evaluation run with testset."""
        print("Testing full evaluation run...")
        
        # Create temporary testset
        testset_data = [
            {
                "id": "full_test_001",
                "prompt": "What are the key factors for project success?",
                "category": "deterministic",
                "test_type": "deterministic_ordering",
                "seed": 12345,
                "must_include": ["project", "success", "factors"],
                "fixtures": {
                    "retrieval_results": [
                        {
                            "id": "ctx_001",
                            "content": "Clear objectives and scope",
                            "relevance_score": 0.9,
                            "importance_score": 0.8,
                            "source": "project_guide"
                        }
                    ]
                },
                "expected_outputs": {
                    "stage_order": ["observe", "expand", "contrast", "order"],
                    "selected_context_ids": ["ctx_001"],
                    "contradictions_count": 0,
                    "final_plan_type": "direct_answer"
                }
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(testset_data, f)
            temp_path = f.name
        
        try:
            runner = RedoEvalRunner(deterministic_mode=True, seed=12345)
            summary = runner.run_eval(temp_path)
            
            # Verify summary
            assert summary.total_cases == 1
            assert summary.passed_cases == 1
            assert summary.failed_cases == 0
            
        finally:
            os.unlink(temp_path)
        
        print("✓ Full evaluation run works")


class TestDeterministicOrchestrator:
    """Test deterministic orchestrator."""
    
    def test_deterministic_configuration(self):
        """Test deterministic orchestrator configuration."""
        print("Testing deterministic orchestrator configuration...")
        
        orchestrator = DeterministicOrchestrator()
        
        # Configure deterministic behavior
        deterministic_config = DeterministicConfig(
            seed=12345,
            use_fixtures=True,
            fixture_data={"retrieval_results": []},
            deterministic_timing=True,
            base_timing_ms=10.0
        )
        orchestrator.configure_deterministic(deterministic_config)
        
        # Configure orchestration
        orchestration_config = OrchestrationConfig(
            enable_contradiction_detection=True,
            enable_redo=True,
            time_budget_ms=400,
            max_trace_bytes=100_000,
            custom_knobs={}
        )
        orchestrator.configure(orchestration_config)
        
        assert orchestrator.deterministic_config.seed == 12345
        assert orchestrator.deterministic_config.use_fixtures == True
        assert orchestrator.deterministic_config.deterministic_timing == True
        
        print("✓ Deterministic orchestrator configuration works")
    
    def test_deterministic_execution(self):
        """Test deterministic execution with same seed."""
        print("Testing deterministic execution...")
        
        # Create query context
        query_context = QueryContext(
            query="Test query for deterministic execution",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={"test": "data"}
        )
        
        # First execution
        orchestrator1 = DeterministicOrchestrator()
        deterministic_config1 = DeterministicConfig(
            seed=12345,
            use_fixtures=True,
            fixture_data={"retrieval_results": []},
            deterministic_timing=True,
            base_timing_ms=10.0
        )
        orchestrator1.configure_deterministic(deterministic_config1)
        orchestrator1.configure(OrchestrationConfig(enable_contradiction_detection=True, enable_redo=True))
        
        result1 = orchestrator1.run(query_context)
        
        # Second execution with same seed
        orchestrator2 = DeterministicOrchestrator()
        deterministic_config2 = DeterministicConfig(
            seed=12345,
            use_fixtures=True,
            fixture_data={"retrieval_results": []},
            deterministic_timing=True,
            base_timing_ms=10.0
        )
        orchestrator2.configure_deterministic(deterministic_config2)
        orchestrator2.configure(OrchestrationConfig(enable_contradiction_detection=True, enable_redo=True))
        
        result2 = orchestrator2.run(query_context)
        
        # Results should be identical
        assert len(result1.stages) == len(result2.stages)
        assert result1.selected_context_ids == result2.selected_context_ids
        assert len(result1.contradictions) == len(result2.contradictions)
        assert result1.final_plan["type"] == result2.final_plan["type"]
        
        print("✓ Deterministic execution works")
    
    def test_contradiction_detection(self):
        """Test contradiction detection with fixtures."""
        print("Testing contradiction detection...")
        
        # Create query context
        query_context = QueryContext(
            query="What is the policy on remote work?",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={"test": "data"}
        )
        
        # Create orchestrator with contradictory fixtures
        orchestrator = DeterministicOrchestrator()
        deterministic_config = DeterministicConfig(
            seed=12345,
            use_fixtures=True,
            fixture_data={
                "retrieval_results": [
                    {
                        "id": "ctx_001",
                        "content": "Remote work is fully supported and encouraged",
                        "relevance_score": 0.9,
                        "source": "hr_policy_2024"
                    },
                    {
                        "id": "ctx_002",
                        "content": "Remote work is only allowed for senior employees",
                        "relevance_score": 0.8,
                        "source": "management_guidelines_2023"
                    }
                ]
            },
            deterministic_timing=True,
            base_timing_ms=10.0
        )
        orchestrator.configure_deterministic(deterministic_config)
        orchestrator.configure(OrchestrationConfig(enable_contradiction_detection=True, enable_redo=True))
        
        result = orchestrator.run(query_context)
        
        # Should detect contradictions
        assert len(result.contradictions) > 0
        assert result.final_plan["type"] == "contradiction_aware"
        
        print("✓ Contradiction detection works")
    
    def test_context_ordering(self):
        """Test context ordering with fixtures."""
        print("Testing context ordering...")
        
        # Create query context
        query_context = QueryContext(
            query="What are the key factors for project success?",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={"test": "data"}
        )
        
        # Create orchestrator with fixtures
        orchestrator = DeterministicOrchestrator()
        deterministic_config = DeterministicConfig(
            seed=12345,
            use_fixtures=True,
            fixture_data={
                "retrieval_results": [
                    {
                        "id": "ctx_001",
                        "content": "Budget management is crucial",
                        "relevance_score": 0.9,
                        "importance_score": 0.8,
                        "source": "project_guide"
                    },
                    {
                        "id": "ctx_002",
                        "content": "Team communication is essential",
                        "relevance_score": 0.8,
                        "importance_score": 0.9,
                        "source": "team_guide"
                    },
                    {
                        "id": "ctx_003",
                        "content": "Timeline planning is important",
                        "relevance_score": 0.7,
                        "importance_score": 0.7,
                        "source": "planning_guide"
                    }
                ]
            },
            deterministic_timing=True,
            base_timing_ms=10.0
        )
        orchestrator.configure_deterministic(deterministic_config)
        orchestrator.configure(OrchestrationConfig(enable_contradiction_detection=True, enable_redo=True))
        
        result = orchestrator.run(query_context)
        
        # Should order by relevance score first, then importance (ctx_001 has highest relevance)
        assert len(result.selected_context_ids) > 0
        assert result.selected_context_ids[0] == "ctx_001"  # Highest relevance score
        
        print("✓ Context ordering works")


def main():
    """Run all REDO evaluation tests."""
    print("Running REDO evaluation tests...\n")
    
    try:
        # Test REDO eval runner
        test_runner = TestRedoEvalRunner()
        test_runner.test_deterministic_mode_initialization()
        test_runner.test_non_deterministic_mode_initialization()
        test_runner.test_load_testset()
        test_runner.test_deterministic_case_execution()
        test_runner.test_ordering_evaluation()
        test_runner.test_contradiction_surfacing_evaluation()
        test_runner.test_latency_constraint_evaluation()
        test_runner.test_eval_summary_generation()
        test_runner.test_full_eval_run()
        
        # Test deterministic orchestrator
        test_orchestrator = TestDeterministicOrchestrator()
        test_orchestrator.test_deterministic_configuration()
        test_orchestrator.test_deterministic_execution()
        test_orchestrator.test_contradiction_detection()
        test_orchestrator.test_context_ordering()
        
        print("\n🎉 All REDO evaluation tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())