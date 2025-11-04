#!/usr/bin/env python3
"""
tools/load_smoke.py — Smoke load test for /chat endpoint.

Fires parallel chat requests with canned prompts, measures p50/p95 latencies,
tracks fallback rates, and asserts against performance budgets.

Features:
- Parallel request execution with configurable concurrency
- p50/p95 latency calculation
- Budget assertions (exit non-zero on failure)
- --pinecone-down mode to simulate Pinecone failures
- Fallback rate tracking
- Detailed metrics output

Usage:
    python tools/load_smoke.py --requests 50 --concurrency 10
    python tools/load_smoke.py --pinecone-down
    python tools/load_smoke.py --budget-p95 2000 --budget-fallback 0.2
"""

import argparse
import sys
import time
import threading
import statistics
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("WARNING: 'requests' library not available. Install with: pip install requests")


@dataclass
class RequestResult:
    """Result of a single request."""
    request_id: int
    prompt: str
    success: bool
    latency_ms: float
    status_code: int
    error: Optional[str] = None
    used_fallback: bool = False
    response_data: Optional[Dict[str, Any]] = None


@dataclass
class LoadTestConfig:
    """Configuration for load test."""
    num_requests: int = 50
    concurrency: int = 10
    base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0
    pinecone_down: bool = False
    
    # Performance budgets
    budget_p50_ms: float = 800.0
    budget_p95_ms: float = 1500.0
    budget_p99_ms: float = 2500.0
    budget_error_rate: float = 0.05  # 5% error rate
    budget_fallback_rate: float = 0.30  # 30% fallback rate (when not simulating failure)
    
    # Canned prompts for testing
    prompts: List[str] = field(default_factory=lambda: [
        "What is machine learning?",
        "Explain neural networks",
        "How does backpropagation work?",
        "What are transformers in deep learning?",
        "Explain reinforcement learning",
        "What is supervised learning?",
        "How do convolutional neural networks work?",
        "What is the difference between AI and ML?",
        "Explain gradient descent",
        "What are recurrent neural networks?",
    ])


class LoadTestRunner:
    """Runs smoke load tests against /chat endpoint."""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[RequestResult] = []
        self.results_lock = threading.Lock()
        
    def _make_request(self, request_id: int, prompt: str) -> RequestResult:
        """
        Make a single chat request.
        
        Args:
            request_id: Unique request identifier
            prompt: Chat prompt to send
            
        Returns:
            RequestResult with timing and outcome
        """
        if not REQUESTS_AVAILABLE:
            return RequestResult(
                request_id=request_id,
                prompt=prompt,
                success=False,
                latency_ms=0.0,
                status_code=0,
                error="requests library not available"
            )
        
        url = f"{self.config.base_url}/chat"
        headers = {}
        
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        
        payload = {
            "prompt": prompt,
            "session_id": f"load_test_{request_id}",
            "debug": True  # Enable debug for fallback detection
        }
        
        # Simulate Pinecone down by setting a flag (would need server support)
        # For now, we'll detect fallbacks in the response
        if self.config.pinecone_down:
            # Add header to signal Pinecone failure simulation
            headers["X-Simulate-Pinecone-Failure"] = "true"
        
        start_time = time.perf_counter()
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            
            success = response.status_code == 200
            response_data = response.json() if success else None
            
            # Detect fallback usage from response
            used_fallback = False
            if response_data:
                metrics = response_data.get("metrics", {})
                # Check for fallback indicators
                if metrics.get("pgvector_fallback_used"):
                    used_fallback = True
                elif metrics.get("retrieval_fallback"):
                    used_fallback = True
                elif "fallback" in str(metrics).lower():
                    used_fallback = True
            
            return RequestResult(
                request_id=request_id,
                prompt=prompt,
                success=success,
                latency_ms=latency_ms,
                status_code=response.status_code,
                used_fallback=used_fallback,
                response_data=response_data
            )
            
        except requests.Timeout:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return RequestResult(
                request_id=request_id,
                prompt=prompt,
                success=False,
                latency_ms=latency_ms,
                status_code=408,
                error="Request timeout"
            )
        except requests.RequestException as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return RequestResult(
                request_id=request_id,
                prompt=prompt,
                success=False,
                latency_ms=latency_ms,
                status_code=0,
                error=str(e)
            )
    
    def _worker(self, request_queue: List[tuple]):
        """
        Worker thread to process requests.
        
        Args:
            request_queue: List of (request_id, prompt) tuples
        """
        for request_id, prompt in request_queue:
            result = self._make_request(request_id, prompt)
            
            with self.results_lock:
                self.results.append(result)
    
    def run(self) -> Dict[str, Any]:
        """
        Run load test with configured parameters.
        
        Returns:
            Dict with test results and metrics
        """
        print(f"\n{'='*80}")
        print(f"SMOKE LOAD TEST")
        print(f"{'='*80}")
        print(f"Configuration:")
        print(f"  Base URL: {self.config.base_url}")
        print(f"  Requests: {self.config.num_requests}")
        print(f"  Concurrency: {self.config.concurrency}")
        print(f"  Timeout: {self.config.timeout_seconds}s")
        print(f"  Pinecone Down Mode: {self.config.pinecone_down}")
        print(f"\nBudgets:")
        print(f"  p50 ≤ {self.config.budget_p50_ms:.0f}ms")
        print(f"  p95 ≤ {self.config.budget_p95_ms:.0f}ms")
        print(f"  p99 ≤ {self.config.budget_p99_ms:.0f}ms")
        print(f"  Error rate ≤ {self.config.budget_error_rate*100:.1f}%")
        print(f"  Fallback rate ≤ {self.config.budget_fallback_rate*100:.1f}%")
        print(f"\n{'='*80}\n")
        
        # Create work queue
        work_queue = []
        for i in range(self.config.num_requests):
            prompt = self.config.prompts[i % len(self.config.prompts)]
            work_queue.append((i, prompt))
        
        # Split work among threads
        chunk_size = max(1, len(work_queue) // self.config.concurrency)
        chunks = [
            work_queue[i:i+chunk_size]
            for i in range(0, len(work_queue), chunk_size)
        ]
        
        # Start timer
        test_start = time.perf_counter()
        
        # Launch worker threads
        threads = []
        for chunk in chunks:
            thread = threading.Thread(target=self._worker, args=(chunk,))
            thread.start()
            threads.append(thread)
        
        # Wait for completion with progress indicator
        completed = 0
        while any(t.is_alive() for t in threads):
            with self.results_lock:
                completed = len(self.results)
            
            progress = (completed / self.config.num_requests) * 100
            print(f"\rProgress: {completed}/{self.config.num_requests} ({progress:.1f}%)", end="", flush=True)
            time.sleep(0.1)
        
        # Ensure all threads complete
        for thread in threads:
            thread.join()
        
        test_duration = time.perf_counter() - test_start
        
        print(f"\n\nCompleted {len(self.results)} requests in {test_duration:.2f}s")
        
        # Calculate metrics
        return self._calculate_metrics(test_duration)
    
    def _calculate_metrics(self, test_duration: float) -> Dict[str, Any]:
        """
        Calculate test metrics and check budgets.
        
        Args:
            test_duration: Total test duration in seconds
            
        Returns:
            Dict with calculated metrics
        """
        total_requests = len(self.results)
        successful_requests = [r for r in self.results if r.success]
        failed_requests = [r for r in self.results if not r.success]
        fallback_requests = [r for r in self.results if r.used_fallback]
        
        # Latency statistics (only successful requests)
        latencies = [r.latency_ms for r in successful_requests]
        
        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = statistics.median(latencies)
            p95 = self._percentile(latencies_sorted, 95)
            p99 = self._percentile(latencies_sorted, 99)
            mean = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
        else:
            p50 = p95 = p99 = mean = min_latency = max_latency = 0.0
        
        # Rates
        success_rate = len(successful_requests) / total_requests if total_requests > 0 else 0.0
        error_rate = len(failed_requests) / total_requests if total_requests > 0 else 0.0
        fallback_rate = len(fallback_requests) / total_requests if total_requests > 0 else 0.0
        
        # Throughput
        throughput = total_requests / test_duration if test_duration > 0 else 0.0
        
        metrics = {
            "test_duration_s": test_duration,
            "total_requests": total_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "fallback_requests": len(fallback_requests),
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "latency_p99_ms": p99,
            "latency_mean_ms": mean,
            "latency_min_ms": min_latency,
            "latency_max_ms": max_latency,
            "success_rate": success_rate,
            "error_rate": error_rate,
            "fallback_rate": fallback_rate,
            "throughput_rps": throughput
        }
        
        # Print metrics
        self._print_metrics(metrics)
        
        # Check budgets
        budget_results = self._check_budgets(metrics)
        
        return {
            "metrics": metrics,
            "budgets": budget_results,
            "results": [
                {
                    "request_id": r.request_id,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "status_code": r.status_code,
                    "used_fallback": r.used_fallback,
                    "error": r.error
                }
                for r in self.results
            ]
        }
    
    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
        
        k = (len(sorted_values) - 1) * (percentile / 100.0)
        f = int(k)
        c = min(f + 1, len(sorted_values) - 1)
        
        if f == c:
            return sorted_values[f]
        
        return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)
    
    def _print_metrics(self, metrics: Dict[str, Any]):
        """Print formatted metrics."""
        print(f"\n{'='*80}")
        print("METRICS")
        print(f"{'='*80}")
        
        print(f"\nThroughput:")
        print(f"  Requests: {metrics['total_requests']}")
        print(f"  Duration: {metrics['test_duration_s']:.2f}s")
        print(f"  Throughput: {metrics['throughput_rps']:.2f} req/s")
        
        print(f"\nSuccess Rates:")
        print(f"  Successful: {metrics['successful_requests']}/{metrics['total_requests']} ({metrics['success_rate']*100:.1f}%)")
        print(f"  Failed: {metrics['failed_requests']}/{metrics['total_requests']} ({metrics['error_rate']*100:.1f}%)")
        print(f"  Fallbacks: {metrics['fallback_requests']}/{metrics['total_requests']} ({metrics['fallback_rate']*100:.1f}%)")
        
        print(f"\nLatency (successful requests):")
        print(f"  p50: {metrics['latency_p50_ms']:.2f}ms")
        print(f"  p95: {metrics['latency_p95_ms']:.2f}ms")
        print(f"  p99: {metrics['latency_p99_ms']:.2f}ms")
        print(f"  Mean: {metrics['latency_mean_ms']:.2f}ms")
        print(f"  Min: {metrics['latency_min_ms']:.2f}ms")
        print(f"  Max: {metrics['latency_max_ms']:.2f}ms")
    
    def _check_budgets(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check metrics against budgets.
        
        Args:
            metrics: Calculated metrics
            
        Returns:
            Dict with budget check results
        """
        budget_results = {
            "all_passed": True,
            "checks": []
        }
        
        # Check p50
        p50_passed = metrics['latency_p50_ms'] <= self.config.budget_p50_ms
        budget_results["checks"].append({
            "name": "p50_latency",
            "passed": p50_passed,
            "actual": metrics['latency_p50_ms'],
            "budget": self.config.budget_p50_ms,
            "unit": "ms"
        })
        if not p50_passed:
            budget_results["all_passed"] = False
        
        # Check p95
        p95_passed = metrics['latency_p95_ms'] <= self.config.budget_p95_ms
        budget_results["checks"].append({
            "name": "p95_latency",
            "passed": p95_passed,
            "actual": metrics['latency_p95_ms'],
            "budget": self.config.budget_p95_ms,
            "unit": "ms"
        })
        if not p95_passed:
            budget_results["all_passed"] = False
        
        # Check p99
        p99_passed = metrics['latency_p99_ms'] <= self.config.budget_p99_ms
        budget_results["checks"].append({
            "name": "p99_latency",
            "passed": p99_passed,
            "actual": metrics['latency_p99_ms'],
            "budget": self.config.budget_p99_ms,
            "unit": "ms"
        })
        if not p99_passed:
            budget_results["all_passed"] = False
        
        # Check error rate
        error_rate_passed = metrics['error_rate'] <= self.config.budget_error_rate
        budget_results["checks"].append({
            "name": "error_rate",
            "passed": error_rate_passed,
            "actual": metrics['error_rate'] * 100,
            "budget": self.config.budget_error_rate * 100,
            "unit": "%"
        })
        if not error_rate_passed:
            budget_results["all_passed"] = False
        
        # Check fallback rate (only when not simulating Pinecone down)
        if not self.config.pinecone_down:
            fallback_rate_passed = metrics['fallback_rate'] <= self.config.budget_fallback_rate
            budget_results["checks"].append({
                "name": "fallback_rate",
                "passed": fallback_rate_passed,
                "actual": metrics['fallback_rate'] * 100,
                "budget": self.config.budget_fallback_rate * 100,
                "unit": "%"
            })
            if not fallback_rate_passed:
                budget_results["all_passed"] = False
        
        # Print budget results
        self._print_budget_results(budget_results)
        
        return budget_results
    
    def _print_budget_results(self, budget_results: Dict[str, Any]):
        """Print budget check results."""
        print(f"\n{'='*80}")
        print("BUDGET CHECKS")
        print(f"{'='*80}\n")
        
        for check in budget_results["checks"]:
            status = "✅ PASS" if check["passed"] else "❌ FAIL"
            name = check["name"].replace("_", " ").title()
            actual = check["actual"]
            budget = check["budget"]
            unit = check["unit"]
            
            print(f"{status}: {name}")
            print(f"  Actual: {actual:.2f}{unit}")
            print(f"  Budget: {budget:.2f}{unit}")
            
            if not check["passed"]:
                overage = actual - budget
                print(f"  Overage: +{overage:.2f}{unit}")
            print()
        
        if budget_results["all_passed"]:
            print("✅ ALL BUDGETS PASSED")
        else:
            print("❌ SOME BUDGETS FAILED")
        
        print(f"{'='*80}\n")


def main():
    """Main entry point for load smoke test."""
    parser = argparse.ArgumentParser(
        description="Smoke load test for /chat endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/load_smoke.py --requests 50 --concurrency 10
  python tools/load_smoke.py --pinecone-down
  python tools/load_smoke.py --budget-p95 2000 --budget-error 0.1
  python tools/load_smoke.py --url http://api.example.com --api-key secret123
        """
    )
    
    # Request configuration
    parser.add_argument(
        "--requests", "-n",
        type=int,
        default=50,
        help="Number of requests to send (default: 50)"
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=10,
        help="Number of concurrent threads (default: 10)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for authentication"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30.0)"
    )
    
    # Simulation modes
    parser.add_argument(
        "--pinecone-down",
        action="store_true",
        help="Simulate Pinecone being down (verify fallback paths)"
    )
    
    # Budget configuration
    parser.add_argument(
        "--budget-p50",
        type=float,
        default=800.0,
        help="p50 latency budget in ms (default: 800)"
    )
    parser.add_argument(
        "--budget-p95",
        type=float,
        default=1500.0,
        help="p95 latency budget in ms (default: 1500)"
    )
    parser.add_argument(
        "--budget-p99",
        type=float,
        default=2500.0,
        help="p99 latency budget in ms (default: 2500)"
    )
    parser.add_argument(
        "--budget-error",
        type=float,
        default=0.05,
        help="Error rate budget as decimal (default: 0.05 = 5%%)"
    )
    parser.add_argument(
        "--budget-fallback",
        type=float,
        default=0.30,
        help="Fallback rate budget as decimal (default: 0.30 = 30%%)"
    )
    
    # Output options
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write results to file"
    )
    
    args = parser.parse_args()
    
    # Create config
    config = LoadTestConfig(
        num_requests=args.requests,
        concurrency=args.concurrency,
        base_url=args.url,
        api_key=args.api_key,
        timeout_seconds=args.timeout,
        pinecone_down=args.pinecone_down,
        budget_p50_ms=args.budget_p50,
        budget_p95_ms=args.budget_p95,
        budget_p99_ms=args.budget_p99,
        budget_error_rate=args.budget_error,
        budget_fallback_rate=args.budget_fallback
    )
    
    # Run test
    runner = LoadTestRunner(config)
    
    try:
        results = runner.run()
        
        # Output JSON if requested
        if args.json:
            print("\nJSON Results:")
            print(json.dumps(results, indent=2))
        
        # Write to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dumps(results, f, indent=2)
            print(f"\nResults written to {args.output}")
        
        # Exit with non-zero code if budgets failed
        if not results["budgets"]["all_passed"]:
            print("\n❌ Exiting with code 1 (budgets failed)")
            sys.exit(1)
        else:
            print("\n✅ Exiting with code 0 (all budgets passed)")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
