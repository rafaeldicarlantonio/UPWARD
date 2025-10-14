#!/usr/bin/env python3
"""
Enhanced evaluation runner for REDO ordering and contradiction surfacing with deterministic mode.
"""

import os
import sys
import json
import time
import statistics
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.orchestrator.deterministic import DeterministicOrchestrator, DeterministicConfig
from core.types import QueryContext, OrchestrationConfig

@dataclass
class RedoEvalResult:
    """Result of a single REDO evaluation case."""
    case_id: str
    prompt: str
    category: str
    test_type: str
    passed: bool
    latency_ms: float
    error: Optional[str] = None
    
    # REDO-specific metrics
    stages_completed: int = 0
    expected_stages: List[str] = field(default_factory=list)
    stage_order_correct: bool = True
    selected_context_ids: List[str] = field(default_factory=list)
    contradictions_found: int = 0
    expected_contradictions: bool = False
    contradiction_detection_correct: bool = True
    ordering_correct: bool = True
    deterministic_output: bool = True
    
    # Timing breakdown
    observe_latency_ms: float = 0.0
    expand_latency_ms: float = 0.0
    contrast_latency_ms: float = 0.0
    order_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    
    # Performance constraints
    meets_latency_constraint: bool = True
    meets_ordering_constraint: bool = True
    meets_contradiction_constraint: bool = True
    meets_deterministic_constraint: bool = True
    
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RedoEvalSummary:
    """Summary of REDO evaluation results."""
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float
    category_breakdown: Dict[str, Dict[str, int]]
    test_type_breakdown: Dict[str, Dict[str, int]]
    performance_issues: List[str]
    
    # REDO-specific metrics
    ordering_accuracy: float = 0.0
    contradiction_detection_accuracy: float = 0.0
    deterministic_consistency: float = 0.0
    stage_completion_rate: float = 0.0
    
    # Enhanced performance metrics
    latency_distribution: Dict[str, float] = field(default_factory=dict)
    constraint_violations: Dict[str, int] = field(default_factory=dict)
    stage_timing_breakdown: Dict[str, float] = field(default_factory=dict)

class RedoEvalRunner:
    """Runs evaluations for REDO ordering and contradiction surfacing."""
    
    def __init__(self, deterministic_mode: bool = False, seed: int = 42):
        self.deterministic_mode = deterministic_mode
        self.seed = seed
        self.results: List[RedoEvalResult] = []
        
        # Performance constraints
        self.max_latency_ms = 500  # P95 constraint
        self.max_individual_latency_ms = 1000  # Individual request constraint
        
        # Deterministic mode setup
        if deterministic_mode:
            random.seed(seed)
            self.orchestrator = DeterministicOrchestrator()
        else:
            self.orchestrator = None
        
        # Timing infrastructure
        self.timing_enabled = True
        self.performance_warnings = []
    
    def run_single_case(self, case: Dict[str, Any]) -> RedoEvalResult:
        """Run a single REDO evaluation case."""
        case_id = case["id"]
        prompt = case["prompt"]
        category = case.get("category", "unknown")
        test_type = case.get("test_type", "unknown")
        
        print(f"  Running {case_id} ({test_type}): {prompt[:50]}...")
        
        # Initialize timing variables
        timing = {
            "total_start": time.time(),
            "observe_start": 0,
            "observe_end": 0,
            "expand_start": 0,
            "expand_end": 0,
            "contrast_start": 0,
            "contrast_end": 0,
            "order_start": 0,
            "order_end": 0,
            "total_end": 0
        }
        
        try:
            if self.deterministic_mode:
                return self._run_deterministic_case(case, timing)
            else:
                return self._run_live_case(case, timing)
                
        except Exception as e:
            timing["total_end"] = time.time()
            total_latency_ms = (timing["total_end"] - timing["total_start"]) * 1000
            
            return RedoEvalResult(
                case_id=case_id,
                prompt=prompt,
                category=category,
                test_type=test_type,
                passed=False,
                latency_ms=total_latency_ms,
                total_latency_ms=total_latency_ms,
                error=f"Evaluation failed: {str(e)}"
            )
    
    def _run_deterministic_case(self, case: Dict[str, Any], timing: Dict[str, float]) -> RedoEvalResult:
        """Run a case in deterministic mode using fixtures."""
        case_id = case["id"]
        prompt = case["prompt"]
        category = case.get("category", "unknown")
        test_type = case.get("test_type", "unknown")
        seed = case.get("seed", self.seed)
        fixtures = case.get("fixtures", {})
        expected_outputs = case.get("expected_outputs", {})
        
        # Configure deterministic orchestrator
        deterministic_config = DeterministicConfig(
            seed=seed,
            use_fixtures=True,
            fixture_data=fixtures,
            deterministic_timing=True,
            base_timing_ms=10.0
        )
        self.orchestrator.configure_deterministic(deterministic_config)
        
        # Configure orchestrator
        orchestration_config = OrchestrationConfig(
            enable_contradiction_detection=True,
            enable_redo=True,
            time_budget_ms=400,
            max_trace_bytes=100_000,
            custom_knobs={}
        )
        self.orchestrator.configure(orchestration_config)
        
        # Create query context
        query_context = QueryContext(
            query=prompt,
            session_id=f"eval_{case_id}",
            user_id="eval_user",
            role="user",
            preferences={},
            metadata={"test_case": case_id}
        )
        
        # Run orchestration
        timing["observe_start"] = time.time()
        result = self.orchestrator.run(query_context)
        timing["total_end"] = time.time()
        
        # Calculate timing
        total_latency_ms = (timing["total_end"] - timing["total_start"]) * 1000
        
        # Extract stage timings
        stage_timings = {}
        for stage in result.stages:
            stage_timings[f"{stage.name}_latency_ms"] = stage.metrics.duration_ms
        
        # Check results against expected outputs
        expected_stages = expected_outputs.get("stage_order", ["observe", "expand", "contrast", "order"])
        expected_context_ids = expected_outputs.get("selected_context_ids", [])
        expected_contradictions = expected_outputs.get("contradictions_count", 0)
        expected_plan_type = expected_outputs.get("final_plan_type", "direct_answer")
        
        # Validate results
        stage_order_correct = [stage.name for stage in result.stages] == expected_stages
        ordering_correct = result.selected_context_ids == expected_context_ids
        contradiction_detection_correct = len(result.contradictions) == expected_contradictions
        plan_type_correct = result.final_plan.get("type") == expected_plan_type
        
        # Check basic requirements
        must_include = case.get("must_include", [])
        answer = result.final_plan.get("answer", result.final_plan.get("type", "")).lower()
        
        passed = True
        error_parts = []
        constraint_violations = []
        
        # Check must_include terms
        if must_include:
            missing_terms = [term for term in must_include if term.lower() not in answer]
            if missing_terms:
                passed = False
                error_parts.append(f"Missing terms: {missing_terms}")
        
        # Check stage order
        if not stage_order_correct:
            passed = False
            error_parts.append(f"Stage order incorrect: {[stage.name for stage in result.stages]} != {expected_stages}")
            constraint_violations.append("stage_order")
        
        # Check ordering
        if not ordering_correct:
            passed = False
            error_parts.append(f"Context ordering incorrect: {result.selected_context_ids} != {expected_context_ids}")
            constraint_violations.append("ordering")
        
        # Check contradiction detection
        if not contradiction_detection_correct:
            passed = False
            error_parts.append(f"Contradiction detection incorrect: {len(result.contradictions)} != {expected_contradictions}")
            constraint_violations.append("contradiction_detection")
        
        # Check latency constraints
        max_latency = case.get("max_latency_ms", self.max_individual_latency_ms)
        meets_latency_constraint = total_latency_ms <= max_latency
        if not meets_latency_constraint:
            passed = False
            error_parts.append(f"Latency {total_latency_ms:.1f}ms exceeds {max_latency}ms")
            constraint_violations.append("latency")
        
        # Update passed status based on constraint violations
        if constraint_violations:
            passed = False
            error_parts.extend([f"Constraint violation: {v}" for v in constraint_violations])
        
        return RedoEvalResult(
            case_id=case_id,
            prompt=prompt,
            category=category,
            test_type=test_type,
            passed=passed,
            latency_ms=total_latency_ms,
            total_latency_ms=total_latency_ms,
            error="; ".join(error_parts) if error_parts else None,
            stages_completed=len(result.stages),
            expected_stages=expected_stages,
            stage_order_correct=stage_order_correct,
            selected_context_ids=result.selected_context_ids,
            contradictions_found=len(result.contradictions),
            expected_contradictions=expected_contradictions > 0,
            contradiction_detection_correct=contradiction_detection_correct,
            ordering_correct=ordering_correct,
            deterministic_output=True,
            observe_latency_ms=stage_timings.get("observe_latency_ms", 0.0),
            expand_latency_ms=stage_timings.get("expand_latency_ms", 0.0),
            contrast_latency_ms=stage_timings.get("contrast_latency_ms", 0.0),
            order_latency_ms=stage_timings.get("order_latency_ms", 0.0),
            meets_latency_constraint=meets_latency_constraint,
            meets_ordering_constraint=ordering_correct,
            meets_contradiction_constraint=contradiction_detection_correct,
            meets_deterministic_constraint=True,
            details={
                "final_plan": result.final_plan,
                "stages": [{"name": stage.name, "duration_ms": stage.metrics.duration_ms} for stage in result.stages],
                "contradictions": result.contradictions,
                "warnings": result.warnings
            }
        )
    
    def _run_live_case(self, case: Dict[str, Any], timing: Dict[str, float]) -> RedoEvalResult:
        """Run a case against live API (for non-deterministic testing)."""
        case_id = case["id"]
        prompt = case["prompt"]
        category = case.get("category", "unknown")
        test_type = case.get("test_type", "unknown")
        
        # This would integrate with the live API
        # For now, return a placeholder result
        timing["total_end"] = time.time()
        total_latency_ms = (timing["total_end"] - timing["total_start"]) * 1000
        
        return RedoEvalResult(
            case_id=case_id,
            prompt=prompt,
            category=category,
            test_type=test_type,
            passed=False,
            latency_ms=total_latency_ms,
            total_latency_ms=total_latency_ms,
            error="Live API integration not implemented yet"
        )
    
    def load_testset(self, testset_path: str) -> List[Dict[str, Any]]:
        """Load a testset from JSON file."""
        with open(testset_path, 'r') as f:
            return json.load(f)
    
    def run_eval(self, testset_path: str) -> RedoEvalSummary:
        """Run evaluation on a testset."""
        print(f"Loading testset: {testset_path}")
        cases = self.load_testset(testset_path)
        
        print(f"Running {len(cases)} cases...")
        self.results = []
        
        for i, case in enumerate(cases, 1):
            print(f"Case {i}/{len(cases)}: {case['id']}")
            result = self.run_single_case(case)
            self.results.append(result)
            
            if result.passed:
                print(f"  ✓ PASSED ({result.latency_ms:.1f}ms)")
            else:
                print(f"  ✗ FAILED: {result.error}")
        
        return self.generate_summary()
    
    def generate_summary(self) -> RedoEvalSummary:
        """Generate summary of evaluation results."""
        if not self.results:
            return RedoEvalSummary(
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                avg_latency_ms=0.0,
                p95_latency_ms=0.0,
                max_latency_ms=0.0,
                category_breakdown={},
                test_type_breakdown={},
                performance_issues=[]
            )
        
        # Basic statistics
        total_cases = len(self.results)
        passed_cases = sum(1 for r in self.results if r.passed)
        failed_cases = total_cases - passed_cases
        
        # Latency statistics
        latencies = [r.latency_ms for r in self.results]
        avg_latency_ms = statistics.mean(latencies) if latencies else 0.0
        p95_latency_ms = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies) if latencies else 0.0
        max_latency_ms = max(latencies) if latencies else 0.0
        
        # Category breakdown
        category_breakdown = {}
        for result in self.results:
            cat = result.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {"passed": 0, "failed": 0}
            if result.passed:
                category_breakdown[cat]["passed"] += 1
            else:
                category_breakdown[cat]["failed"] += 1
        
        # Test type breakdown
        test_type_breakdown = {}
        for result in self.results:
            test_type = result.test_type
            if test_type not in test_type_breakdown:
                test_type_breakdown[test_type] = {"passed": 0, "failed": 0}
            if result.passed:
                test_type_breakdown[test_type]["passed"] += 1
            else:
                test_type_breakdown[test_type]["failed"] += 1
        
        # REDO-specific metrics
        ordering_correct = sum(1 for r in self.results if r.ordering_correct)
        contradiction_correct = sum(1 for r in self.results if r.contradiction_detection_correct)
        deterministic_consistent = sum(1 for r in self.results if r.deterministic_output)
        stages_completed = sum(r.stages_completed for r in self.results)
        
        ordering_accuracy = ordering_correct / total_cases if total_cases > 0 else 0.0
        contradiction_detection_accuracy = contradiction_correct / total_cases if total_cases > 0 else 0.0
        deterministic_consistency = deterministic_consistent / total_cases if total_cases > 0 else 0.0
        stage_completion_rate = stages_completed / (total_cases * 4) if total_cases > 0 else 0.0  # 4 stages expected
        
        # Constraint violations
        constraint_violations = {}
        for result in self.results:
            if not result.meets_latency_constraint:
                constraint_violations["latency"] = constraint_violations.get("latency", 0) + 1
            if not result.meets_ordering_constraint:
                constraint_violations["ordering"] = constraint_violations.get("ordering", 0) + 1
            if not result.meets_contradiction_constraint:
                constraint_violations["contradiction"] = constraint_violations.get("contradiction", 0) + 1
            if not result.meets_deterministic_constraint:
                constraint_violations["deterministic"] = constraint_violations.get("deterministic", 0) + 1
        
        # Performance issues
        performance_issues = []
        if p95_latency_ms > self.max_latency_ms:
            performance_issues.append(f"P95 latency {p95_latency_ms:.1f}ms exceeds {self.max_latency_ms}ms")
        if ordering_accuracy < 0.9:
            performance_issues.append(f"Ordering accuracy {ordering_accuracy:.2%} below 90%")
        if contradiction_detection_accuracy < 0.8:
            performance_issues.append(f"Contradiction detection accuracy {contradiction_detection_accuracy:.2%} below 80%")
        if deterministic_consistency < 1.0:
            performance_issues.append(f"Deterministic consistency {deterministic_consistency:.2%} below 100%")
        
        return RedoEvalSummary(
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            avg_latency_ms=avg_latency_ms,
            p95_latency_ms=p95_latency_ms,
            max_latency_ms=max_latency_ms,
            category_breakdown=category_breakdown,
            test_type_breakdown=test_type_breakdown,
            performance_issues=performance_issues,
            ordering_accuracy=ordering_accuracy,
            contradiction_detection_accuracy=contradiction_detection_accuracy,
            deterministic_consistency=deterministic_consistency,
            stage_completion_rate=stage_completion_rate,
            constraint_violations=constraint_violations
        )

def main():
    """Main evaluation runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run REDO evaluations")
    parser.add_argument("--testset", required=True, help="Path to testset JSON file")
    parser.add_argument("--deterministic", action="store_true", help="Run in deterministic mode")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic mode")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Run evaluation
    runner = RedoEvalRunner(deterministic_mode=args.deterministic, seed=args.seed)
    summary = runner.run_eval(args.testset)
    
    # Print summary
    print("\n" + "="*60)
    print("REDO EVALUATION SUMMARY")
    print("="*60)
    print(f"Total cases: {summary.total_cases}")
    print(f"Passed: {summary.passed_cases}")
    print(f"Failed: {summary.failed_cases}")
    print(f"Success rate: {summary.passed_cases/summary.total_cases:.1%}")
    print()
    print(f"Average latency: {summary.avg_latency_ms:.1f}ms")
    print(f"P95 latency: {summary.p95_latency_ms:.1f}ms")
    print(f"Max latency: {summary.max_latency_ms:.1f}ms")
    print()
    print("REDO-SPECIFIC METRICS:")
    print(f"Ordering accuracy: {summary.ordering_accuracy:.1%}")
    print(f"Contradiction detection accuracy: {summary.contradiction_detection_accuracy:.1%}")
    print(f"Deterministic consistency: {summary.deterministic_consistency:.1%}")
    print(f"Stage completion rate: {summary.stage_completion_rate:.1%}")
    print()
    
    if summary.performance_issues:
        print("PERFORMANCE ISSUES:")
        for issue in summary.performance_issues:
            print(f"  - {issue}")
        print()
    
    if summary.constraint_violations:
        print("CONSTRAINT VIOLATIONS:")
        for constraint, count in summary.constraint_violations.items():
            print(f"  - {constraint}: {count}")
        print()
    
    # Print category breakdown
    if summary.category_breakdown:
        print("CATEGORY BREAKDOWN:")
        for category, stats in summary.category_breakdown.items():
            total = stats["passed"] + stats["failed"]
            success_rate = stats["passed"] / total if total > 0 else 0
            print(f"  {category}: {stats['passed']}/{total} ({success_rate:.1%})")
        print()
    
    # Print test type breakdown
    if summary.test_type_breakdown:
        print("TEST TYPE BREAKDOWN:")
        for test_type, stats in summary.test_type_breakdown.items():
            total = stats["passed"] + stats["failed"]
            success_rate = stats["passed"] / total if total > 0 else 0
            print(f"  {test_type}: {stats['passed']}/{total} ({success_rate:.1%})")
        print()
    
    # Exit with error code if any failures
    if summary.failed_cases > 0:
        print(f"❌ Evaluation failed with {summary.failed_cases} failures")
        sys.exit(1)
    else:
        print("✅ All evaluations passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()