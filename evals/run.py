#!/usr/bin/env python3
"""
Evaluation runner for implicate lift and contradiction surfacing.
"""

import os
import sys
import json
import time
import statistics
import yaml
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
    
    # Implicate lift metrics
    expected_source_ids: List[str] = field(default_factory=list)
    retrieved_source_ids: List[str] = field(default_factory=list)
    found_in_top_k: List[str] = field(default_factory=list)
    recall_at_k: float = 0.0
    top_k: int = 8
    
    # Contradiction metrics
    expected_contradictions: List[Dict[str, Any]] = field(default_factory=list)
    actual_contradictions: List[Dict[str, Any]] = field(default_factory=list)
    has_badge: bool = False
    badge_data: Dict[str, Any] = field(default_factory=dict)
    contradiction_completeness: float = 0.0
    
    # External compare metrics
    external_mode: str = "off"  # "off" or "on"
    external_used: bool = False
    external_sources: List[str] = field(default_factory=list)
    external_ingested: bool = False
    decision_tiebreak: Optional[str] = None
    expected_parity: Optional[bool] = None
    expected_policy: Optional[str] = None
    
    # Pareto gate metrics
    pareto_score: float = 0.0
    pareto_threshold: float = 0.65
    persisted: bool = False
    expected_persisted: bool = False
    override_enabled: bool = False
    override_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    scoring_latency_ms: float = 0.0

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
        
    def run_single_case(self, case: Dict[str, Any], pipeline: str = None) -> EvalResult:
        """Run a single evaluation case with detailed timing.
        
        Args:
            case: Test case dictionary
            pipeline: Optional pipeline override ('legacy' or 'new')
        """
        case_id = case["id"]
        prompt = case.get("prompt") or case.get("query", "")
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
            
            # Extract retrieved source IDs for implicate lift validation
            retrieved_source_ids = []
            if isinstance(citations, list):
                for citation in citations:
                    if isinstance(citation, dict) and "source_id" in citation:
                        retrieved_source_ids.append(citation["source_id"])
                    elif isinstance(citation, str):
                        retrieved_source_ids.append(citation)
            
            # Check for retrieved_ids in debug metrics
            debug_metrics = data.get("debug", {})
            retrieval_metrics = debug_metrics.get("retrieval_metrics", {})
            if "retrieved_ids" in retrieval_metrics:
                retrieved_source_ids = retrieval_metrics["retrieved_ids"]
            
            # Check basic requirements
            must_include = case.get("must_include", [])
            must_cite_any = case.get("must_cite_any", [])
            
            passed = True
            error_parts = []
            constraint_violations = []
            
            # Implicate lift validation
            expected_source_ids = case.get("expected_source_ids", [])
            expected_in_top_k = case.get("expected_in_top_k", 8)
            found_in_top_k = []
            recall_at_k = 0.0
            
            if expected_source_ids and retrieved_source_ids:
                # Check which expected IDs are in top k
                top_k_ids = retrieved_source_ids[:expected_in_top_k]
                found_in_top_k = [id for id in expected_source_ids if id in top_k_ids]
                recall_at_k = len(found_in_top_k) / len(expected_source_ids) if expected_source_ids else 0.0
                
                # For implicate lift cases, passing means finding all expected IDs
                if category == "implicate_lift" and recall_at_k < 1.0:
                    passed = False
                    missing_ids = [id for id in expected_source_ids if id not in found_in_top_k]
                    error_parts.append(f"Missing expected IDs in top-{expected_in_top_k}: {missing_ids}")
            
            # Contradiction validation
            expected_contradictions = case.get("expected_contradictions", [])
            actual_contradictions = data.get("contradictions", [])
            has_badge = "badge" in data
            badge_data = data.get("badge", {})
            contradiction_completeness = 0.0
            
            if category == "contradictions" and expected_contradictions:
                # Check that contradictions array is non-empty
                if not actual_contradictions:
                    passed = False
                    error_parts.append("Contradictions array is empty")
                else:
                    # Validate each expected contradiction
                    for expected in expected_contradictions:
                        expected_subject = expected.get("subject")
                        claim_a_src = expected.get("claim_a_source")
                        claim_b_src = expected.get("claim_b_source")
                        
                        # Find matching contradiction by subject
                        found_contradiction = None
                        for actual in actual_contradictions:
                            if actual.get("subject") == expected_subject:
                                found_contradiction = actual
                                break
                        
                        if not found_contradiction:
                            passed = False
                            error_parts.append(f"Missing contradiction for subject: {expected_subject}")
                            continue
                        
                        # Validate both evidence IDs present
                        claim_a = found_contradiction.get("claim_a", {})
                        claim_b = found_contradiction.get("claim_b", {})
                        found_a_src = claim_a.get("source_id")
                        found_b_src = claim_b.get("source_id")
                        
                        if not found_a_src or not found_b_src:
                            passed = False
                            error_parts.append(f"Missing source IDs for subject {expected_subject}")
                        elif claim_a_src and claim_b_src:
                            # Check if expected sources are present (in either order)
                            expected_srcs = {claim_a_src, claim_b_src}
                            found_srcs = {found_a_src, found_b_src}
                            if expected_srcs != found_srcs:
                                passed = False
                                error_parts.append(
                                    f"Wrong sources for {expected_subject}: "
                                    f"expected {expected_srcs}, found {found_srcs}"
                                )
                        
                        # Calculate completeness
                        has_subject = "subject" in found_contradiction
                        has_claim_a = "claim_a" in found_contradiction
                        has_claim_b = "claim_b" in found_contradiction
                        has_src_a = found_a_src is not None
                        has_src_b = found_b_src is not None
                        contradiction_completeness = sum([
                            has_subject, has_claim_a, has_claim_b, has_src_a, has_src_b
                        ]) / 5.0
                
                # Check badge presence
                expected_badge = case.get("expected_badge", False)
                if expected_badge and not has_badge:
                    passed = False
                    error_parts.append("Missing badge in answer payload")
                elif has_badge:
                    # Validate badge structure
                    if badge_data.get("type") != "contradiction":
                        passed = False
                        error_parts.append(f"Wrong badge type: {badge_data.get('type')}")
                
                # Check packing latency
                max_packing_latency = case.get("max_packing_latency_ms", 550)
                if packing_latency_ms > max_packing_latency:
                    passed = False
                    error_parts.append(
                        f"Packing latency {packing_latency_ms:.1f}ms exceeds {max_packing_latency}ms"
                    )
            
            # External compare validation
            expected_parity = case.get("expected_parity")
            expected_policy = case.get("expected_policy")
            external_used = data.get("external_used", False)
            external_sources = data.get("external_considered", [])
            decision_data = data.get("decision", {})
            decision_tiebreak = decision_data.get("tiebreak")
            
            # Check for external ingestion (external source IDs in citations)
            external_ingested = False
            if citations:
                citation_ids = [
                    c.get("source_id", "") if isinstance(c, dict) else str(c)
                    for c in citations
                ]
                external_ingested = any(
                    "ext_" in cid or "external" in cid.lower()
                    for cid in citation_ids
                )
            
            if category == "external_compare":
                # For external compare cases, validate based on mode
                external_mode = pipeline if pipeline in ["off", "on"] else "off"
                
                # Check no-persistence (zero ingestion)
                if external_ingested:
                    passed = False
                    error_parts.append("External text ingestion detected")
                
                # Check policy compliance for non-parity cases
                if not expected_parity and expected_policy and decision_tiebreak:
                    if decision_tiebreak != expected_policy:
                        passed = False
                        error_parts.append(
                            f"Policy violation: expected {expected_policy}, "
                            f"got {decision_tiebreak}"
                        )
            
            # Pareto gate validation
            pareto_score = 0.0
            pareto_threshold = 0.65
            persisted = False
            expected_persisted = case.get("expected_persisted", False)
            override_enabled = False
            override_reason = None
            rejection_reason = None
            scoring_latency_ms = 0.0
            expected_status_code = case.get("expected_status_code", 200)
            
            if category == "pareto_gate":
                # Extract score and persistence info from response
                pareto_score = data.get("score", 0.0)
                pareto_threshold = data.get("threshold", 0.65)
                persisted = data.get("persisted", False)
                override_enabled = data.get("override", False)
                override_reason = data.get("override_reason")
                rejection_reason = data.get("reason")
                
                # Extract scoring latency if available
                timing_data = data.get("timing", {})
                scoring_latency_ms = timing_data.get("scoring_ms", 0.0)
                
                # Validate persistence matches expectation
                if persisted != expected_persisted:
                    passed = False
                    error_parts.append(
                        f"Persistence mismatch: expected {expected_persisted}, got {persisted}"
                    )
                
                # Validate status code
                if response.status_code != expected_status_code:
                    passed = False
                    error_parts.append(
                        f"Status code mismatch: expected {expected_status_code}, "
                        f"got {response.status_code}"
                    )
                
                # Validate override behavior
                if case.get("proposal", {}).get("override", {}).get("enabled"):
                    # Override case should persist and log override
                    if not persisted:
                        passed = False
                        error_parts.append("Override case should persist")
                    if not override_enabled:
                        passed = False
                        error_parts.append("Override not logged")
                
                # Validate rejection reason for non-persisted
                if not persisted and not rejection_reason:
                    passed = False
                    error_parts.append("Missing rejection reason for non-persisted proposal")
                
                # Validate scoring latency budget
                max_scoring_latency = case.get("max_scoring_latency_ms", 200)
                if scoring_latency_ms > max_scoring_latency:
                    passed = False
                    error_parts.append(
                        f"Scoring latency {scoring_latency_ms:.1f}ms exceeds {max_scoring_latency}ms"
                    )
            
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
                expected_source_ids=expected_source_ids,
                retrieved_source_ids=retrieved_source_ids,
                found_in_top_k=found_in_top_k,
                recall_at_k=recall_at_k,
                top_k=expected_in_top_k,
                expected_contradictions=expected_contradictions,
                actual_contradictions=actual_contradictions,
                has_badge=has_badge,
                badge_data=badge_data,
                contradiction_completeness=contradiction_completeness,
                external_mode=pipeline if pipeline in ["off", "on"] else "off",
                external_used=external_used,
                external_sources=external_sources,
                external_ingested=external_ingested,
                decision_tiebreak=decision_tiebreak,
                expected_parity=expected_parity,
                expected_policy=expected_policy,
                pareto_score=pareto_score,
                pareto_threshold=pareto_threshold,
                persisted=persisted,
                expected_persisted=expected_persisted,
                override_enabled=override_enabled,
                override_reason=override_reason,
                rejection_reason=rejection_reason,
                scoring_latency_ms=scoring_latency_ms,
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
    
    def run_testset(self, testset_path: str, pipeline: str = None) -> List[EvalResult]:
        """Run all cases in a testset.
        
        Args:
            testset_path: Path to testset file (.json or .jsonl)
            pipeline: Optional pipeline override ('legacy' or 'new')
        """
        print(f"Running testset: {testset_path}")
        
        # Load cases - support both JSON and JSONL formats
        cases = []
        with open(testset_path, 'r') as f:
            if testset_path.endswith('.jsonl'):
                # JSONL format - one case per line
                for line in f:
                    if line.strip():
                        cases.append(json.loads(line))
            else:
                # JSON format - array of cases
                cases = json.load(f)
        
        results = []
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case['id']}")
            result = self.run_single_case(case, pipeline=pipeline)
            results.append(result)
            self.results.append(result)
            
            status = "PASS" if result.passed else "FAIL"
            print(f"    {status} - {result.latency_ms:.1f}ms")
            if result.error:
                print(f"    Error: {result.error}")
            
            # Print recall@k for implicate lift cases
            if case.get("category") == "implicate_lift" and result.expected_source_ids:
                print(f"    Recall@{result.top_k}: {result.recall_at_k:.2f} ({len(result.found_in_top_k)}/{len(result.expected_source_ids)} docs)")
            
            # Print contradiction detection for contradiction cases
            if case.get("category") == "contradictions":
                num_contradictions = len(result.actual_contradictions)
                has_badge_str = "?" if result.has_badge else "?"
                print(f"    Contradictions: {num_contradictions}, Badge: {has_badge_str}, Completeness: {result.contradiction_completeness:.2f}")
            
            # Print external compare metrics
            if case.get("category") == "external_compare":
                ext_used_str = "?" if result.external_used else "?"
                ingested_str = "?" if result.external_ingested else "?"
                policy_str = result.decision_tiebreak or "N/A"
                print(f"    External: {ext_used_str}, Policy: {policy_str}, No-Ingestion: {ingested_str}")
            
            # Print Pareto gate metrics
            if case.get("category") == "pareto_gate":
                persist_str = "?" if result.persisted else "?"
                override_str = f" [OVERRIDE: {result.override_reason}]" if result.override_enabled else ""
                rejection_str = f" (reason: {result.rejection_reason})" if result.rejection_reason else ""
                print(f"    Score: {result.pareto_score:.3f}, Threshold: {result.pareto_threshold:.3f}, Persisted: {persist_str}{override_str}{rejection_str}, Scoring: {result.scoring_latency_ms:.1f}ms")
        
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
        if summary.total_cases > 0:
            print(f"Passed: {summary.passed_cases} ({summary.passed_cases/summary.total_cases*100:.1f}%)")
            print(f"Failed: {summary.failed_cases} ({summary.failed_cases/summary.total_cases*100:.1f}%)")
        else:
            print(f"Passed: 0")
            print(f"Failed: 0")
        
        if summary.total_cases > 0:
            print(f"\n?? Latency Metrics:")
            print(f"  Average: {summary.avg_latency_ms:.1f}ms")
            print(f"  P50: {summary.latency_distribution.get('p50', 0.0):.1f}ms")
            print(f"  P90: {summary.latency_distribution.get('p90', 0.0):.1f}ms")
            print(f"  P95: {summary.p95_latency_ms:.1f}ms")
            print(f"  P99: {summary.latency_distribution.get('p99', 0.0):.1f}ms")
            print(f"  Max: {summary.max_latency_ms:.1f}ms")
        
            print(f"\n??  Timing Breakdown:")
            print(f"  Retrieval: {summary.timing_breakdown['avg_retrieval_ms']:.1f}ms")
            print(f"  Ranking: {summary.timing_breakdown['avg_ranking_ms']:.1f}ms")
            print(f"  Packing: {summary.timing_breakdown['avg_packing_ms']:.1f}ms")
            
            print(f"\n?? Implicate Lift Metrics:")
            print(f"  Total Cases: {summary.implicate_lift_metrics['total_cases']}")
            print(f"  Successful Lifts: {summary.implicate_lift_metrics['successful_lifts']}")
            print(f"  Success Rate: {summary.implicate_lift_metrics['lift_success_rate']*100:.1f}%")
            print(f"  Avg Implicate Rank: {summary.implicate_lift_metrics['avg_implicate_rank']:.2f}")
            
            print(f"\n?? Contradiction Metrics:")
            print(f"  Total Cases: {summary.contradiction_metrics['total_cases']}")
            print(f"  Contradictions Detected: {summary.contradiction_metrics['contradictions_detected']}")
            print(f"  Detection Accuracy: {summary.contradiction_metrics['detection_accuracy']*100:.1f}%")
            print(f"  Avg Contradiction Score: {summary.contradiction_metrics['avg_contradiction_score']:.3f}")
        
        print(f"\n?? Category Breakdown:")
        for category, stats in summary.category_breakdown.items():
            pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {category}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")
        
        print(f"\n??  Constraint Violations:")
        for constraint, count in summary.constraint_violations.items():
            if count > 0:
                print(f"  {constraint}: {count} violations")
        
        if summary.performance_issues:
            print(f"\n?? Performance Issues:")
            for issue in summary.performance_issues:
                print(f"  {issue}")
        
        # Show failed cases
        failed_cases = [r for r in self.results if not r.passed]
        if failed_cases:
            print(f"\n? Failed Cases:")
            for result in failed_cases:
                print(f"  {result.case_id}: {result.error}")
        
        # Performance constraint validation
        print(f"\n? Performance Constraints:")
        p95_ok = summary.p95_latency_ms <= self.max_latency_ms
        print(f"  P95 < {self.max_latency_ms}ms: {'? PASS' if p95_ok else '? FAIL'} ({summary.p95_latency_ms:.1f}ms)")
        
        constraint_violations_total = sum(summary.constraint_violations.values())
        constraints_ok = constraint_violations_total == 0
        print(f"  All Constraints: {'? PASS' if constraints_ok else '? FAIL'} ({constraint_violations_total} violations)")
        
        return summary

def write_json_report(results: List[EvalResult], summary: EvalSummary, output_path: str):
    """Write JSON report of evaluation results."""
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "total_cases": summary.total_cases,
            "passed_cases": summary.passed_cases,
            "failed_cases": summary.failed_cases,
            "pass_rate": summary.passed_cases / summary.total_cases if summary.total_cases > 0 else 0.0,
            "avg_latency_ms": summary.avg_latency_ms,
            "p95_latency_ms": summary.p95_latency_ms,
            "max_latency_ms": summary.max_latency_ms,
            "latency_distribution": summary.latency_distribution,
            "timing_breakdown": summary.timing_breakdown,
            "category_breakdown": summary.category_breakdown,
            "constraint_violations": summary.constraint_violations,
            "implicate_lift_metrics": summary.implicate_lift_metrics,
            "contradiction_metrics": summary.contradiction_metrics,
            "performance_issues": summary.performance_issues
        },
        "results": [
            {
                "case_id": r.case_id,
                "prompt": r.prompt,
                "category": r.category,
                "passed": r.passed,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "retrieved_chunks": r.retrieved_chunks,
                "implicate_rank": r.implicate_rank,
                "contradictions_found": r.contradictions_found,
                "contradiction_score": r.contradiction_score,
                "lift_score": r.lift_score,
                "total_latency_ms": r.total_latency_ms,
                "retrieval_latency_ms": r.retrieval_latency_ms,
                "ranking_latency_ms": r.ranking_latency_ms,
                "packing_latency_ms": r.packing_latency_ms,
                "meets_latency_constraint": r.meets_latency_constraint,
                "meets_implicate_constraint": r.meets_implicate_constraint,
                "meets_contradiction_constraint": r.meets_contradiction_constraint
            }
            for r in results
        ]
    }
    
    # Create output directory if needed
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n?? JSON report written to: {output_path}")

def print_latency_histogram(results: List[EvalResult], buckets: List[int] = None):
    """Print ASCII histogram of latency distribution."""
    if not results:
        return
    
    if buckets is None:
        buckets = [100, 200, 300, 500, 800, 1000]
    
    latencies = [r.latency_ms for r in results]
    
    # Count latencies in each bucket
    bucket_counts = {}
    for bucket in buckets:
        bucket_counts[bucket] = sum(1 for lat in latencies if lat <= bucket and (bucket == buckets[0] or lat > buckets[buckets.index(bucket) - 1]))
    
    # Add overflow bucket
    overflow = sum(1 for lat in latencies if lat > buckets[-1])
    
    print(f"\n?? Latency Histogram:")
    print(f"{'Bucket (ms)':<15} {'Count':<8} {'Percentage':<12} {'Bar'}")
    print("-" * 60)
    
    max_count = max(list(bucket_counts.values()) + [overflow]) if bucket_counts or overflow else 1
    bar_width = 40
    
    prev = 0
    for bucket in buckets:
        count = bucket_counts.get(bucket, 0)
        pct = count / len(latencies) * 100 if latencies else 0
        bar_len = int(count / max_count * bar_width) if max_count > 0 else 0
        bar = "?" * bar_len
        print(f"{prev}-{bucket} ms{' '*(10-len(str(bucket)))}{count:<8} {pct:>5.1f}%       {bar}")
        prev = bucket
    
    if overflow > 0:
        pct = overflow / len(latencies) * 100
        bar_len = int(overflow / max_count * bar_width) if max_count > 0 else 0
        bar = "?" * bar_len
        print(f">{buckets[-1]} ms{' '*(10-len(str(buckets[-1])))}{overflow:<8} {pct:>5.1f}%       {bar}")

def main():
    """Main entry point."""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description="Run evaluations for implicate lift and contradictions")
    parser.add_argument("--config", default="evals/config.yaml", help="Path to config YAML file")
    parser.add_argument("--suite", help="Suite name to run (from config)")
    parser.add_argument("--testsets", default="evals/testsets", help="Directory containing testset JSON files")
    parser.add_argument("--testset", help="Single testset file to run")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"), help="Base URL for API")
    parser.add_argument("--api-key", default=os.getenv("X_API_KEY", ""), help="API key")
    parser.add_argument("--pipeline", choices=["legacy", "new"], help="Force specific pipeline")
    parser.add_argument("--output-json", help="Path for JSON report output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--max-latency", type=int, default=500, help="Maximum P95 latency in ms")
    parser.add_argument("--max-individual-latency", type=int, default=1000, help="Maximum individual request latency in ms")
    parser.add_argument("--explicate-k", type=int, default=16, help="Expected explicate top-k")
    parser.add_argument("--implicate-k", type=int, default=8, help="Expected implicate top-k")
    parser.add_argument("--ci-mode", action="store_true", help="Enable CI mode with stricter constraints")
    parser.add_argument("--skip-flaky", action="store_true", help="Skip tests marked as flaky")
    parser.add_argument("--show-histogram", action="store_true", help="Show latency histogram")
    
    args = parser.parse_args()
    
    # Load config if provided
    config = None
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        print(f"?? Loaded config from: {args.config}")
    
    # Handle suite configuration
    suite_config = None
    if args.suite and config:
        # Find suite in config
        suites = config.get("suites", [])
        for s in suites:
            if s.get("name") == args.suite:
                suite_config = s
                break
        
        if not suite_config:
            print(f"? Suite '{args.suite}' not found in config")
            sys.exit(1)
        
        print(f"?? Running suite: {suite_config['name']}")
        print(f"   Description: {suite_config.get('description', 'N/A')}")
        
        # Override with suite constraints
        if "constraints" in suite_config:
            constraints = suite_config["constraints"]
            if "max_latency_ms" in constraints:
                args.max_latency = constraints["max_latency_ms"]
            if "min_pass_rate" in constraints:
                print(f"   Min pass rate: {constraints['min_pass_rate']*100:.1f}%")
        
        # Set pipeline from suite if not overridden
        if not args.pipeline and "pipeline" in suite_config:
            args.pipeline = suite_config["pipeline"]
    
    # Configure runner with arguments
    runner = EvalRunner(base_url=args.base_url, api_key=args.api_key)
    runner.max_latency_ms = args.max_latency
    runner.max_individual_latency_ms = args.max_individual_latency
    runner.expected_explicate_k = args.explicate_k
    runner.expected_implicate_k = args.implicate_k
    
    if args.ci_mode:
        print("?? CI Mode: Enabling stricter performance constraints")
        runner.max_latency_ms = min(runner.max_latency_ms, 400)  # Stricter in CI
        runner.max_individual_latency_ms = min(runner.max_individual_latency_ms, 800)
    
    if args.skip_flaky:
        print("??  Skipping flaky tests")
    
    # Show pipeline info
    if args.pipeline:
        pipeline_name = "Legacy Pipeline" if args.pipeline == "legacy" else "New REDO Pipeline"
        print(f"?? Pipeline: {pipeline_name}")
    
    print(f"?? Starting evaluation with constraints:")
    print(f"   P95 latency: < {runner.max_latency_ms}ms")
    print(f"   Individual latency: < {runner.max_individual_latency_ms}ms")
    print(f"   Explicate K: {runner.expected_explicate_k}")
    print(f"   Implicate K: {runner.expected_implicate_k}")
    
    try:
        # Determine which testsets to run
        testsets_to_run = []
        
        if suite_config:
            # Run testsets from suite
            for testset_file in suite_config.get("testsets", []):
                testsets_to_run.append(testset_file)
        elif args.testset:
            # Run single testset
            testsets_to_run.append(args.testset)
        else:
            # Run all testsets in directory
            testsets_to_run = None
        
        # Run evaluations
        if testsets_to_run:
            for testset_file in testsets_to_run:
                print(f"\n{'='*60}")
                print(f"Running {testset_file}")
                print(f"{'='*60}")
                runner.run_testset(testset_file)
        else:
            runner.run_all_testsets(args.testsets)
        
        summary = runner.print_summary()
        
        # Show latency histogram if requested
        if args.show_histogram or (config and config.get("reporting", {}).get("console", {}).get("show_latency_histogram")):
            histogram_buckets = None
            if config:
                histogram_buckets = config.get("reporting", {}).get("console", {}).get("histogram_buckets")
            print_latency_histogram(runner.results, buckets=histogram_buckets)
        
        # Write JSON report if requested
        output_json = args.output_json
        if not output_json and config:
            if config.get("reporting", {}).get("json_output"):
                output_json = config.get("reporting", {}).get("json_path", "evals/results/latest.json")
        
        if output_json:
            write_json_report(runner.results, summary, output_json)
        
        # Determine exit status
        exit_code = 0
        
        # Check for failed cases
        if summary.failed_cases > 0:
            print(f"\n? Evaluation failed with {summary.failed_cases} failed cases")
            exit_code = 1
        
        # Check performance constraints
        if summary.p95_latency_ms > runner.max_latency_ms:
            print(f"\n? Performance constraint violated: P95 {summary.p95_latency_ms:.1f}ms > {runner.max_latency_ms}ms")
            exit_code = 1
        
        # Check constraint violations
        constraint_violations_total = sum(summary.constraint_violations.values())
        if constraint_violations_total > 0:
            print(f"\n? Constraint violations: {constraint_violations_total} total")
            if args.ci_mode:
                exit_code = 1  # Fail in CI mode
        
        # Check suite-specific constraints
        if suite_config and "constraints" in suite_config:
            constraints = suite_config["constraints"]
            pass_rate = summary.passed_cases / summary.total_cases if summary.total_cases > 0 else 0.0
            
            if "min_pass_rate" in constraints:
                min_pass_rate = constraints["min_pass_rate"]
                if pass_rate < min_pass_rate:
                    print(f"\n? Pass rate {pass_rate:.1%} below minimum {min_pass_rate:.1%}")
                    exit_code = 1
        
        if exit_code == 0:
            print(f"\n? All evaluations passed!")
        else:
            print(f"\n? Evaluation failed!")
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print(f"\n??  Evaluation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n?? Evaluation failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()