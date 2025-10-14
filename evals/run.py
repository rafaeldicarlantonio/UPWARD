#!/usr/bin/env python3
"""
Evaluation runner for implicate lift and contradiction surfacing.
"""

import os
import sys
import json
import time
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/workspace')

@dataclass
class EvalResult:
    """Result of a single evaluation case."""
    case_id: str
    prompt: str
    category: str
    passed: bool
    latency_ms: float
    error: Optional[str] = None
    retrieved_chunks: int = 0
    implicate_rank: Optional[int] = None
    contradictions_found: int = 0
    contradiction_score: float = 0.0
    lift_score: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Enhanced timing metrics
    retrieval_latency_ms: float = 0.0
    ranking_latency_ms: float = 0.0
    packing_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    
    # Performance constraints
    meets_latency_constraint: bool = True
    meets_implicate_constraint: bool = True
    meets_contradiction_constraint: bool = True

@dataclass
class EvalSummary:
    """Summary of evaluation results."""
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float
    category_breakdown: Dict[str, Dict[str, int]]
    performance_issues: List[str]
    
    # Enhanced performance metrics
    latency_distribution: Dict[str, float] = field(default_factory=dict)
    constraint_violations: Dict[str, int] = field(default_factory=dict)
    implicate_lift_metrics: Dict[str, Any] = field(default_factory=dict)
    contradiction_metrics: Dict[str, Any] = field(default_factory=dict)
    timing_breakdown: Dict[str, float] = field(default_factory=dict)

class EvalRunner:
    """Runs evaluations for implicate lift and contradiction surfacing."""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("BASE_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("X_API_KEY", "")
        self.results: List[EvalResult] = []
        
        # Performance constraints
        self.max_latency_ms = 500  # P95 constraint
        self.max_individual_latency_ms = 1000  # Individual request constraint
        self.expected_explicate_k = 16
        self.expected_implicate_k = 8
        
        # Timing infrastructure
        self.timing_enabled = True
        self.performance_warnings = []
        
    def run_single_case(self, case: Dict[str, Any]) -> EvalResult:
        """Run a single evaluation case with detailed timing."""
        case_id = case["id"]
        prompt = case["prompt"]
        category = case.get("category", "unknown")
        
        print(f"  Running {case_id}: {prompt[:50]}...")
        
        # Initialize timing variables
        timing = {
            "total_start": time.time(),
            "retrieval_start": 0,
            "retrieval_end": 0,
            "ranking_start": 0,
            "ranking_end": 0,
            "packing_start": 0,
            "packing_end": 0,
            "total_end": 0
        }
        
        try:
            # Make API call with timing
            import requests
            
            timing["retrieval_start"] = time.time()
            response = requests.post(
                f"{self.base_url}/chat",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key
                },
                json={
                    "prompt": prompt,
                    "role": "researcher",
                    "debug": True,  # Enable debug for detailed metrics
                    "explicate_top_k": self.expected_explicate_k,
                    "implicate_top_k": self.expected_implicate_k
                },
                timeout=30
            )
            timing["retrieval_end"] = time.time()
            timing["total_end"] = time.time()
            
            # Calculate latencies
            total_latency_ms = (timing["total_end"] - timing["total_start"]) * 1000
            retrieval_latency_ms = (timing["retrieval_end"] - timing["retrieval_start"]) * 1000
            
            if response.status_code != 200:
                return EvalResult(
                    case_id=case_id,
                    prompt=prompt,
                    category=category,
                    passed=False,
                    latency_ms=total_latency_ms,
                    total_latency_ms=total_latency_ms,
                    retrieval_latency_ms=retrieval_latency_ms,
                    meets_latency_constraint=total_latency_ms <= self.max_individual_latency_ms,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            # Parse response
            data = response.json()
            answer = data.get("answer", "").lower()
            citations = data.get("citations", [])
            
            # Extract debug metrics if available
            debug_metrics = data.get("debug", {})
            retrieval_metrics = debug_metrics.get("retrieval_metrics", {})
            
            # Check basic requirements
            must_include = case.get("must_include", [])
            must_cite_any = case.get("must_cite_any", [])
            
            passed = True
            error_parts = []
            constraint_violations = []
            
            # Check must_include terms
            if must_include:
                missing_terms = [term for term in must_include if term.lower() not in answer]
                if missing_terms:
                    passed = False
                    error_parts.append(f"Missing terms: {missing_terms}")
            
            # Check citations
            if must_cite_any:
                has_citation = any(
                    any(token in str(citation) for token in must_cite_any)
                    for citation in citations
                )
                if not has_citation:
                    passed = False
                    error_parts.append(f"Missing citations with tokens: {must_cite_any}")
            
            # Check latency constraints
            max_latency = case.get("max_latency_ms", self.max_individual_latency_ms)
            meets_latency_constraint = total_latency_ms <= max_latency
            if not meets_latency_constraint:
                passed = False
                error_parts.append(f"Latency {total_latency_ms:.1f}ms exceeds {max_latency}ms")
                constraint_violations.append("latency")
            
            # Extract additional metrics from response
            retrieved_chunks = len(citations)
            implicate_rank = None
            contradictions_found = 0
            contradiction_score = 0.0
            lift_score = None
            meets_implicate_constraint = True
            meets_contradiction_constraint = True
            
            # Try to extract metrics from debug info if available
            if "debug" in data:
                debug = data["debug"]
                if "retrieval_metrics" in debug:
                    metrics = debug["retrieval_metrics"]
                    implicate_rank = metrics.get("implicate_rank")
                    contradictions_found = metrics.get("contradictions_found", 0)
                    contradiction_score = metrics.get("contradiction_score", 0.0)
                    lift_score = metrics.get("lift_score")
                    
                    # Check implicate lift constraints
                    expected_implicate_rank = case.get("expected_implicate_rank")
                    if expected_implicate_rank and implicate_rank:
                        if implicate_rank > expected_implicate_rank:
                            meets_implicate_constraint = False
                            constraint_violations.append("implicate_rank")
                    
                    # Check contradiction constraints
                    expected_contradictions = case.get("expected_contradictions")
                    if expected_contradictions is not None:
                        if expected_contradictions and contradictions_found == 0:
                            meets_contradiction_constraint = False
                            constraint_violations.append("contradictions_missing")
                        elif not expected_contradictions and contradictions_found > 0:
                            meets_contradiction_constraint = False
                            constraint_violations.append("contradictions_unexpected")
            
            # Update passed status based on constraint violations
            if constraint_violations:
                passed = False
                error_parts.extend([f"Constraint violation: {v}" for v in constraint_violations])
            
            # Calculate additional timing metrics
            ranking_latency_ms = retrieval_metrics.get("ranking_latency_ms", 0.0)
            packing_latency_ms = retrieval_metrics.get("packing_latency_ms", 0.0)
            
            return EvalResult(
                case_id=case_id,
                prompt=prompt,
                category=category,
                passed=passed,
                latency_ms=total_latency_ms,
                total_latency_ms=total_latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                ranking_latency_ms=ranking_latency_ms,
                packing_latency_ms=packing_latency_ms,
                meets_latency_constraint=meets_latency_constraint,
                meets_implicate_constraint=meets_implicate_constraint,
                meets_contradiction_constraint=meets_contradiction_constraint,
                error="; ".join(error_parts) if error_parts else None,
                retrieved_chunks=retrieved_chunks,
                implicate_rank=implicate_rank,
                contradictions_found=contradictions_found,
                contradiction_score=contradiction_score,
                lift_score=lift_score,
                details={
                    "answer": answer[:200] + "..." if len(answer) > 200 else answer,
                    "citations": citations,
                    "response_keys": list(data.keys()),
                    "debug_metrics": retrieval_metrics,
                    "constraint_violations": constraint_violations,
                    "timing": timing
                }
            )
            
        except Exception as e:
            total_latency_ms = (time.time() - timing["total_start"]) * 1000
            return EvalResult(
                case_id=case_id,
                prompt=prompt,
                category=category,
                passed=False,
                latency_ms=total_latency_ms,
                total_latency_ms=total_latency_ms,
                meets_latency_constraint=False,
                error=f"Exception: {str(e)}"
            )
    
    def run_testset(self, testset_path: str) -> List[EvalResult]:
        """Run all cases in a testset."""
        print(f"Running testset: {testset_path}")
        
        with open(testset_path, 'r') as f:
            cases = json.load(f)
        
        results = []
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case['id']}")
            result = self.run_single_case(case)
            results.append(result)
            self.results.append(result)
            
            status = "PASS" if result.passed else "FAIL"
            print(f"    {status} - {result.latency_ms:.1f}ms")
            if result.error:
                print(f"    Error: {result.error}")
        
        return results
    
    def run_all_testsets(self, testsets_dir: str = "evals/testsets") -> List[EvalResult]:
        """Run all testsets in a directory."""
        testsets_dir = Path(testsets_dir)
        all_results = []
        
        for testset_file in testsets_dir.glob("*.json"):
            print(f"\n{'='*60}")
            print(f"Running {testset_file.name}")
            print(f"{'='*60}")
            
            results = self.run_testset(str(testset_file))
            all_results.extend(results)
        
        return all_results
    
    def generate_summary(self) -> EvalSummary:
        """Generate comprehensive summary of all results."""
        if not self.results:
            return EvalSummary(
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                avg_latency_ms=0.0,
                p95_latency_ms=0.0,
                max_latency_ms=0.0,
                category_breakdown={},
                performance_issues=[]
            )
        
        # Basic stats
        total_cases = len(self.results)
        passed_cases = sum(1 for r in self.results if r.passed)
        failed_cases = total_cases - passed_cases
        
        # Latency stats
        latencies = [r.latency_ms for r in self.results]
        avg_latency_ms = statistics.mean(latencies)
        p95_latency_ms = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 1 else latencies[0]
        max_latency_ms = max(latencies)
        
        # Enhanced latency distribution
        latency_distribution = {
            "p50": statistics.quantiles(latencies, n=2)[0] if len(latencies) > 1 else latencies[0],
            "p90": statistics.quantiles(latencies, n=10)[8] if len(latencies) > 1 else latencies[0],
            "p95": p95_latency_ms,
            "p99": statistics.quantiles(latencies, n=100)[98] if len(latencies) > 1 else latencies[0]
        }
        
        # Timing breakdown
        timing_breakdown = {
            "avg_retrieval_ms": statistics.mean([r.retrieval_latency_ms for r in self.results]) if self.results else 0.0,
            "avg_ranking_ms": statistics.mean([r.ranking_latency_ms for r in self.results]) if self.results else 0.0,
            "avg_packing_ms": statistics.mean([r.packing_latency_ms for r in self.results]) if self.results else 0.0
        }
        
        # Constraint violations
        constraint_violations = {
            "latency": sum(1 for r in self.results if not r.meets_latency_constraint),
            "implicate": sum(1 for r in self.results if not r.meets_implicate_constraint),
            "contradiction": sum(1 for r in self.results if not r.meets_contradiction_constraint)
        }
        
        # Category breakdown
        category_breakdown = {}
        for result in self.results:
            cat = result.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {"total": 0, "passed": 0, "failed": 0}
            category_breakdown[cat]["total"] += 1
            if result.passed:
                category_breakdown[cat]["passed"] += 1
            else:
                category_breakdown[cat]["failed"] += 1
        
        # Implicate lift metrics
        implicate_results = [r for r in self.results if r.category == "implicate_lift"]
        implicate_ranks = [r.implicate_rank for r in implicate_results if r.implicate_rank is not None]
        implicate_lift_metrics = {
            "total_cases": len(implicate_results),
            "successful_lifts": sum(1 for r in implicate_results if r.implicate_rank and r.implicate_rank <= 1),
            "avg_implicate_rank": statistics.mean(implicate_ranks) if implicate_ranks else 0,
            "lift_success_rate": sum(1 for r in implicate_results if r.implicate_rank and r.implicate_rank <= 1) / len(implicate_results) if implicate_results else 0
        }
        
        # Contradiction metrics
        contradiction_results = [r for r in self.results if r.category in ["contradictions", "no_contradictions"]]
        contradiction_scores = [r.contradiction_score for r in contradiction_results]
        contradiction_metrics = {
            "total_cases": len(contradiction_results),
            "contradictions_detected": sum(r.contradictions_found for r in contradiction_results),
            "avg_contradiction_score": statistics.mean(contradiction_scores) if contradiction_scores else 0.0,
            "detection_accuracy": sum(1 for r in contradiction_results if r.meets_contradiction_constraint) / len(contradiction_results) if contradiction_results else 0
        }
        
        # Performance issues
        performance_issues = []
        if p95_latency_ms > self.max_latency_ms:
            performance_issues.append(f"P95 latency {p95_latency_ms:.1f}ms exceeds {self.max_latency_ms}ms threshold")
        
        slow_cases = [r for r in self.results if r.latency_ms > self.max_individual_latency_ms]
        if slow_cases:
            performance_issues.append(f"{len(slow_cases)} cases exceeded {self.max_individual_latency_ms}ms latency")
        
        if constraint_violations["latency"] > 0:
            performance_issues.append(f"{constraint_violations['latency']} cases failed latency constraints")
        
        if constraint_violations["implicate"] > 0:
            performance_issues.append(f"{constraint_violations['implicate']} cases failed implicate lift constraints")
        
        if constraint_violations["contradiction"] > 0:
            performance_issues.append(f"{constraint_violations['contradiction']} cases failed contradiction constraints")
        
        return EvalSummary(
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            avg_latency_ms=avg_latency_ms,
            p95_latency_ms=p95_latency_ms,
            max_latency_ms=max_latency_ms,
            category_breakdown=category_breakdown,
            performance_issues=performance_issues,
            latency_distribution=latency_distribution,
            constraint_violations=constraint_violations,
            implicate_lift_metrics=implicate_lift_metrics,
            contradiction_metrics=contradiction_metrics,
            timing_breakdown=timing_breakdown
        )
    
    def print_summary(self):
        """Print a comprehensive summary of results."""
        summary = self.generate_summary()
        
        print(f"\n{'='*80}")
        print("EVALUATION SUMMARY")
        print(f"{'='*80}")
        
        print(f"Total Cases: {summary.total_cases}")
        print(f"Passed: {summary.passed_cases} ({summary.passed_cases/summary.total_cases*100:.1f}%)")
        print(f"Failed: {summary.failed_cases} ({summary.failed_cases/summary.total_cases*100:.1f}%)")
        
        print(f"\n📊 Latency Metrics:")
        print(f"  Average: {summary.avg_latency_ms:.1f}ms")
        print(f"  P50: {summary.latency_distribution['p50']:.1f}ms")
        print(f"  P90: {summary.latency_distribution['p90']:.1f}ms")
        print(f"  P95: {summary.p95_latency_ms:.1f}ms")
        print(f"  P99: {summary.latency_distribution['p99']:.1f}ms")
        print(f"  Max: {summary.max_latency_ms:.1f}ms")
        
        print(f"\n⏱️  Timing Breakdown:")
        print(f"  Retrieval: {summary.timing_breakdown['avg_retrieval_ms']:.1f}ms")
        print(f"  Ranking: {summary.timing_breakdown['avg_ranking_ms']:.1f}ms")
        print(f"  Packing: {summary.timing_breakdown['avg_packing_ms']:.1f}ms")
        
        print(f"\n🎯 Implicate Lift Metrics:")
        print(f"  Total Cases: {summary.implicate_lift_metrics['total_cases']}")
        print(f"  Successful Lifts: {summary.implicate_lift_metrics['successful_lifts']}")
        print(f"  Success Rate: {summary.implicate_lift_metrics['lift_success_rate']*100:.1f}%")
        print(f"  Avg Implicate Rank: {summary.implicate_lift_metrics['avg_implicate_rank']:.2f}")
        
        print(f"\n🔍 Contradiction Metrics:")
        print(f"  Total Cases: {summary.contradiction_metrics['total_cases']}")
        print(f"  Contradictions Detected: {summary.contradiction_metrics['contradictions_detected']}")
        print(f"  Detection Accuracy: {summary.contradiction_metrics['detection_accuracy']*100:.1f}%")
        print(f"  Avg Contradiction Score: {summary.contradiction_metrics['avg_contradiction_score']:.3f}")
        
        print(f"\n📈 Category Breakdown:")
        for category, stats in summary.category_breakdown.items():
            pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {category}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")
        
        print(f"\n⚠️  Constraint Violations:")
        for constraint, count in summary.constraint_violations.items():
            if count > 0:
                print(f"  {constraint}: {count} violations")
        
        if summary.performance_issues:
            print(f"\n🚨 Performance Issues:")
            for issue in summary.performance_issues:
                print(f"  {issue}")
        
        # Show failed cases
        failed_cases = [r for r in self.results if not r.passed]
        if failed_cases:
            print(f"\n❌ Failed Cases:")
            for result in failed_cases:
                print(f"  {result.case_id}: {result.error}")
        
        # Performance constraint validation
        print(f"\n✅ Performance Constraints:")
        p95_ok = summary.p95_latency_ms <= self.max_latency_ms
        print(f"  P95 < {self.max_latency_ms}ms: {'✅ PASS' if p95_ok else '❌ FAIL'} ({summary.p95_latency_ms:.1f}ms)")
        
        constraint_violations_total = sum(summary.constraint_violations.values())
        constraints_ok = constraint_violations_total == 0
        print(f"  All Constraints: {'✅ PASS' if constraints_ok else '❌ FAIL'} ({constraint_violations_total} violations)")
        
        return summary

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run evaluations for implicate lift and contradictions")
    parser.add_argument("--testsets", default="evals/testsets", help="Directory containing testset JSON files")
    parser.add_argument("--testset", help="Single testset file to run")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"), help="Base URL for API")
    parser.add_argument("--api-key", default=os.getenv("X_API_KEY", ""), help="API key")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--max-latency", type=int, default=500, help="Maximum P95 latency in ms")
    parser.add_argument("--max-individual-latency", type=int, default=1000, help="Maximum individual request latency in ms")
    parser.add_argument("--explicate-k", type=int, default=16, help="Expected explicate top-k")
    parser.add_argument("--implicate-k", type=int, default=8, help="Expected implicate top-k")
    parser.add_argument("--ci-mode", action="store_true", help="Enable CI mode with stricter constraints")
    parser.add_argument("--skip-flaky", action="store_true", help="Skip tests marked as flaky")
    
    args = parser.parse_args()
    
    # Configure runner with arguments
    runner = EvalRunner(base_url=args.base_url, api_key=args.api_key)
    runner.max_latency_ms = args.max_latency
    runner.max_individual_latency_ms = args.max_individual_latency
    runner.expected_explicate_k = args.explicate_k
    runner.expected_implicate_k = args.implicate_k
    
    if args.ci_mode:
        print("🔧 CI Mode: Enabling stricter performance constraints")
        runner.max_latency_ms = min(runner.max_latency_ms, 400)  # Stricter in CI
        runner.max_individual_latency_ms = min(runner.max_individual_latency_ms, 800)
    
    if args.skip_flaky:
        print("⏭️  Skipping flaky tests")
    
    print(f"🚀 Starting evaluation with constraints:")
    print(f"   P95 latency: < {runner.max_latency_ms}ms")
    print(f"   Individual latency: < {runner.max_individual_latency_ms}ms")
    print(f"   Explicate K: {runner.expected_explicate_k}")
    print(f"   Implicate K: {runner.expected_implicate_k}")
    
    try:
        if args.testset:
            # Run single testset
            results = runner.run_testset(args.testset)
        else:
            # Run all testsets
            results = runner.run_all_testsets(args.testsets)
        
        summary = runner.print_summary()
        
        # Determine exit status
        exit_code = 0
        
        # Check for failed cases
        if summary.failed_cases > 0:
            print(f"\n❌ Evaluation failed with {summary.failed_cases} failed cases")
            exit_code = 1
        
        # Check performance constraints
        if summary.p95_latency_ms > runner.max_latency_ms:
            print(f"\n❌ Performance constraint violated: P95 {summary.p95_latency_ms:.1f}ms > {runner.max_latency_ms}ms")
            exit_code = 1
        
        # Check constraint violations
        constraint_violations_total = sum(summary.constraint_violations.values())
        if constraint_violations_total > 0:
            print(f"\n❌ Constraint violations: {constraint_violations_total} total")
            if args.ci_mode:
                exit_code = 1  # Fail in CI mode
        
        if exit_code == 0:
            print(f"\n✅ All evaluations passed!")
        else:
            print(f"\n❌ Evaluation failed!")
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Evaluation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Evaluation failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()