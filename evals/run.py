#!/usr/bin/env python3
"""
Evaluation runner for implicate lift and contradiction surfacing.
"""

import os
import sys
import json
import time
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
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
    details: Dict[str, Any] = None

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

class EvalRunner:
    """Runs evaluations for implicate lift and contradiction surfacing."""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("BASE_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("X_API_KEY", "")
        self.results: List[EvalResult] = []
        
    def run_single_case(self, case: Dict[str, Any]) -> EvalResult:
        """Run a single evaluation case."""
        case_id = case["id"]
        prompt = case["prompt"]
        category = case.get("category", "unknown")
        
        print(f"  Running {case_id}: {prompt[:50]}...")
        
        start_time = time.time()
        
        try:
            # Make API call
            import requests
            response = requests.post(
                f"{self.base_url}/chat",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key
                },
                json={
                    "prompt": prompt,
                    "role": "researcher",
                    "debug": False
                },
                timeout=30
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                return EvalResult(
                    case_id=case_id,
                    prompt=prompt,
                    category=category,
                    passed=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            # Parse response
            data = response.json()
            answer = data.get("answer", "").lower()
            citations = data.get("citations", [])
            
            # Check basic requirements
            must_include = case.get("must_include", [])
            must_cite_any = case.get("must_cite_any", [])
            
            passed = True
            error_parts = []
            
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
            
            # Check latency
            max_latency = case.get("max_latency_ms", 999999)
            if latency_ms > max_latency:
                passed = False
                error_parts.append(f"Latency {latency_ms:.1f}ms exceeds {max_latency}ms")
            
            # Extract additional metrics from response
            retrieved_chunks = len(citations)
            implicate_rank = None
            contradictions_found = 0
            contradiction_score = 0.0
            lift_score = None
            
            # Try to extract metrics from debug info if available
            if "debug" in data:
                debug = data["debug"]
                if "retrieval_metrics" in debug:
                    metrics = debug["retrieval_metrics"]
                    implicate_rank = metrics.get("implicate_rank")
                    contradictions_found = metrics.get("contradictions_found", 0)
                    contradiction_score = metrics.get("contradiction_score", 0.0)
                    lift_score = metrics.get("lift_score")
            
            # Check category-specific requirements
            if category == "implicate_lift":
                expected_rank = case.get("expected_implicate_rank")
                if expected_rank and implicate_rank:
                    if implicate_rank > expected_rank:
                        passed = False
                        error_parts.append(f"Implicate rank {implicate_rank} > expected {expected_rank}")
            
            elif category == "contradictions":
                expected_contradictions = case.get("expected_contradictions", False)
                if expected_contradictions and contradictions_found == 0:
                    passed = False
                    error_parts.append("Expected contradictions but none found")
                elif not expected_contradictions and contradictions_found > 0:
                    passed = False
                    error_parts.append(f"Unexpected contradictions found: {contradictions_found}")
            
            return EvalResult(
                case_id=case_id,
                prompt=prompt,
                category=category,
                passed=passed,
                latency_ms=latency_ms,
                error="; ".join(error_parts) if error_parts else None,
                retrieved_chunks=retrieved_chunks,
                implicate_rank=implicate_rank,
                contradictions_found=contradictions_found,
                contradiction_score=contradiction_score,
                lift_score=lift_score,
                details={
                    "answer": answer[:200] + "..." if len(answer) > 200 else answer,
                    "citations": citations,
                    "response_keys": list(data.keys())
                }
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return EvalResult(
                case_id=case_id,
                prompt=prompt,
                category=category,
                passed=False,
                latency_ms=latency_ms,
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
        """Generate summary of all results."""
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
        
        # Performance issues
        performance_issues = []
        if p95_latency_ms > 500:
            performance_issues.append(f"P95 latency {p95_latency_ms:.1f}ms exceeds 500ms threshold")
        
        slow_cases = [r for r in self.results if r.latency_ms > 500]
        if slow_cases:
            performance_issues.append(f"{len(slow_cases)} cases exceeded 500ms latency")
        
        return EvalSummary(
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            avg_latency_ms=avg_latency_ms,
            p95_latency_ms=p95_latency_ms,
            max_latency_ms=max_latency_ms,
            category_breakdown=category_breakdown,
            performance_issues=performance_issues
        )
    
    def print_summary(self):
        """Print a concise summary of results."""
        summary = self.generate_summary()
        
        print(f"\n{'='*60}")
        print("EVALUATION SUMMARY")
        print(f"{'='*60}")
        
        print(f"Total Cases: {summary.total_cases}")
        print(f"Passed: {summary.passed_cases} ({summary.passed_cases/summary.total_cases*100:.1f}%)")
        print(f"Failed: {summary.failed_cases} ({summary.failed_cases/summary.total_cases*100:.1f}%)")
        
        print(f"\nLatency Metrics:")
        print(f"  Average: {summary.avg_latency_ms:.1f}ms")
        print(f"  P95: {summary.p95_latency_ms:.1f}ms")
        print(f"  Max: {summary.max_latency_ms:.1f}ms")
        
        print(f"\nCategory Breakdown:")
        for category, stats in summary.category_breakdown.items():
            pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {category}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")
        
        if summary.performance_issues:
            print(f"\nPerformance Issues:")
            for issue in summary.performance_issues:
                print(f"  ⚠️  {issue}")
        
        # Show failed cases
        failed_cases = [r for r in self.results if not r.passed]
        if failed_cases:
            print(f"\nFailed Cases:")
            for result in failed_cases:
                print(f"  ❌ {result.case_id}: {result.error}")
        
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
    
    args = parser.parse_args()
    
    runner = EvalRunner(base_url=args.base_url, api_key=args.api_key)
    
    if args.testset:
        # Run single testset
        results = runner.run_testset(args.testset)
    else:
        # Run all testsets
        results = runner.run_all_testsets(args.testsets)
    
    summary = runner.print_summary()
    
    # Exit with error code if there are failures
    if summary.failed_cases > 0:
        print(f"\n❌ Evaluation failed with {summary.failed_cases} failed cases")
        sys.exit(1)
    else:
        print(f"\n✅ All evaluations passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()