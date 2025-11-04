#!/usr/bin/env python3
"""
Trace freezer for capturing reproducible orchestration artifacts.

Captures:
- Input query/prompt
- Retrieved candidates (top-N)
- Orchestration trace
- Random seeds
- Trace hash for validation
"""

import os
import json
import hashlib
import random
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class FrozenTrace:
    """Frozen orchestration trace for replay."""
    trace_id: str
    timestamp: str
    query: str
    role: str
    
    # Randomness seeds
    random_seed: int
    numpy_seed: Optional[int] = None
    
    # Retrieved candidates
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    top_k: int = 8
    
    # Orchestration trace
    trace: Dict[str, Any] = field(default_factory=dict)
    trace_hash: str = ""
    
    # Additional context
    pipeline: str = "default"
    explicate_k: int = 16
    implicate_k: int = 8
    debug_metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    frozen_by: str = "freezer"
    frozen_version: str = "1.0"
    notes: str = ""


class TraceHasher:
    """Compute deterministic hash of orchestration trace."""
    
    @staticmethod
    def hash_trace(trace: Dict[str, Any]) -> str:
        """
        Compute SHA256 hash of trace structure.
        
        Excludes timing/latency fields for determinism.
        """
        # Create canonical representation
        canonical = TraceHasher._canonicalize(trace)
        
        # Convert to JSON string (sorted keys)
        trace_json = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
        
        # Compute hash
        hash_obj = hashlib.sha256(trace_json.encode('utf-8'))
        return hash_obj.hexdigest()[:16]  # First 16 chars for brevity
    
    @staticmethod
    def _canonicalize(obj: Any) -> Any:
        """
        Create canonical representation by removing non-deterministic fields.
        """
        if isinstance(obj, dict):
            canonical = {}
            for key, value in obj.items():
                # Skip timing/latency fields
                if any(excluded in key.lower() for excluded in ['latency', 'timing', 'timestamp', 'time_ms', 'duration']):
                    continue
                canonical[key] = TraceHasher._canonicalize(value)
            return canonical
        elif isinstance(obj, list):
            return [TraceHasher._canonicalize(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)
    
    @staticmethod
    def hash_candidates(candidates: List[Dict[str, Any]]) -> str:
        """Compute hash of candidate list (IDs only)."""
        # Extract just the IDs in order
        candidate_ids = [c.get('id', c.get('source_id', '')) for c in candidates]
        ids_str = ','.join(candidate_ids)
        hash_obj = hashlib.sha256(ids_str.encode('utf-8'))
        return hash_obj.hexdigest()[:16]


class TraceFreezer:
    """Freeze orchestration traces for reproducible replay."""
    
    def __init__(self, output_dir: str = "evals/frozen_traces"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def freeze(
        self,
        query: str,
        role: str,
        candidates: List[Dict[str, Any]],
        trace: Dict[str, Any],
        trace_id: Optional[str] = None,
        pipeline: str = "default",
        top_k: int = 8,
        explicate_k: int = 16,
        implicate_k: int = 8,
        debug_metrics: Optional[Dict[str, Any]] = None,
        notes: str = ""
    ) -> FrozenTrace:
        """
        Freeze a trace for later replay.
        
        Args:
            query: Input query/prompt
            role: User role
            candidates: Retrieved candidates (full list)
            trace: Orchestration trace
            trace_id: Optional trace ID (generated if not provided)
            pipeline: Pipeline name
            top_k: Number of top candidates to save
            explicate_k: Explicate top-k
            implicate_k: Implicate top-k
            debug_metrics: Additional debug metrics
            notes: Optional notes about this trace
        
        Returns:
            FrozenTrace object
        """
        # Generate trace ID if not provided
        if not trace_id:
            trace_id = self._generate_trace_id(query)
        
        # Capture current random state
        random_seed = random.randint(0, 2**31 - 1)
        
        # Try to capture numpy seed if available
        numpy_seed = None
        try:
            import numpy as np
            numpy_seed = np.random.randint(0, 2**31 - 1)
        except ImportError:
            pass
        
        # Limit candidates to top-k
        top_candidates = candidates[:top_k] if candidates else []
        
        # Compute trace hash
        trace_hash = TraceHasher.hash_trace(trace)
        
        # Create frozen trace
        frozen = FrozenTrace(
            trace_id=trace_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            query=query,
            role=role,
            random_seed=random_seed,
            numpy_seed=numpy_seed,
            candidates=top_candidates,
            top_k=top_k,
            trace=trace,
            trace_hash=trace_hash,
            pipeline=pipeline,
            explicate_k=explicate_k,
            implicate_k=implicate_k,
            debug_metrics=debug_metrics or {},
            frozen_by="freezer",
            frozen_version="1.0",
            notes=notes
        )
        
        # Save to disk
        self._save_frozen_trace(frozen)
        
        return frozen
    
    def _generate_trace_id(self, query: str) -> str:
        """Generate unique trace ID based on query and timestamp."""
        # Use first 50 chars of query + timestamp
        query_snippet = query[:50].lower()
        query_snippet = ''.join(c if c.isalnum() else '_' for c in query_snippet)
        timestamp = int(time.time() * 1000)
        return f"{query_snippet}_{timestamp}"
    
    def _save_frozen_trace(self, frozen: FrozenTrace):
        """Save frozen trace to disk."""
        output_path = self.output_dir / f"{frozen.trace_id}.json"
        
        with open(output_path, 'w') as f:
            json.dump(asdict(frozen), f, indent=2)
        
        print(f"✅ Frozen trace saved: {output_path}")
        print(f"   Trace ID: {frozen.trace_id}")
        print(f"   Trace hash: {frozen.trace_hash}")
        print(f"   Candidates: {len(frozen.candidates)}")
    
    def load(self, trace_id: str) -> FrozenTrace:
        """Load a frozen trace by ID."""
        # Try with and without .json extension
        trace_path = self.output_dir / f"{trace_id}.json"
        if not trace_path.exists():
            trace_path = self.output_dir / trace_id
        
        if not trace_path.exists():
            raise FileNotFoundError(f"Frozen trace not found: {trace_id}")
        
        with open(trace_path, 'r') as f:
            data = json.load(f)
        
        return FrozenTrace(**data)
    
    def list_traces(self) -> List[str]:
        """List all available frozen traces."""
        traces = []
        for path in self.output_dir.glob("*.json"):
            traces.append(path.stem)
        return sorted(traces)
    
    def get_trace_info(self, trace_id: str) -> Dict[str, Any]:
        """Get summary info about a frozen trace."""
        frozen = self.load(trace_id)
        return {
            "trace_id": frozen.trace_id,
            "timestamp": frozen.timestamp,
            "query": frozen.query[:100] + "..." if len(frozen.query) > 100 else frozen.query,
            "role": frozen.role,
            "trace_hash": frozen.trace_hash,
            "candidates_count": len(frozen.candidates),
            "pipeline": frozen.pipeline,
            "notes": frozen.notes
        }


class ReplaySeeder:
    """Seed all randomness sources for deterministic replay."""
    
    @staticmethod
    def seed_all(seed: int):
        """Seed all known randomness sources."""
        # Python random
        random.seed(seed)
        
        # NumPy if available
        try:
            import numpy as np
            np.random.seed(seed)
        except ImportError:
            pass
        
        # PyTorch if available
        try:
            import torch
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except ImportError:
            pass
        
        # Set environment variables for additional determinism
        os.environ['PYTHONHASHSEED'] = str(seed)
    
    @staticmethod
    def get_current_state() -> Dict[str, Any]:
        """Get current random state from all sources."""
        state = {
            "python_random": random.getstate(),
        }
        
        try:
            import numpy as np
            state["numpy_random"] = np.random.get_state()
        except ImportError:
            pass
        
        return state


def freeze_from_response(
    query: str,
    role: str,
    response: Dict[str, Any],
    freezer: Optional[TraceFreezer] = None,
    trace_id: Optional[str] = None,
    notes: str = ""
) -> FrozenTrace:
    """
    Convenience function to freeze a trace from an API response.
    
    Args:
        query: Input query
        role: User role
        response: API response dictionary
        freezer: Optional TraceFreezer instance (creates new if None)
        trace_id: Optional trace ID
        notes: Optional notes
    
    Returns:
        FrozenTrace object
    """
    if freezer is None:
        freezer = TraceFreezer()
    
    # Extract candidates from response
    candidates = []
    if "citations" in response:
        candidates = response["citations"]
    elif "debug" in response and "retrieved_candidates" in response["debug"]:
        candidates = response["debug"]["retrieved_candidates"]
    
    # Extract trace from debug info
    trace = {}
    if "debug" in response:
        trace = response.get("debug", {})
    else:
        # Minimal trace from response
        trace = {
            "answer": response.get("answer", ""),
            "citations": response.get("citations", []),
            "contradictions": response.get("contradictions", []),
        }
    
    # Extract debug metrics
    debug_metrics = response.get("debug", {}).get("metrics", {})
    
    return freezer.freeze(
        query=query,
        role=role,
        candidates=candidates,
        trace=trace,
        trace_id=trace_id,
        debug_metrics=debug_metrics,
        notes=notes
    )


if __name__ == "__main__":
    # Example usage
    freezer = TraceFreezer()
    
    # Create example frozen trace
    example_trace = {
        "answer": "Machine learning models benefit from regularization.",
        "citations": [
            {"source_id": "doc_001", "text": "Regularization prevents overfitting"},
            {"source_id": "doc_002", "text": "Common techniques include L1 and L2"}
        ],
        "orchestration": {
            "retrieved": 10,
            "ranked": 5,
            "selected": 2
        }
    }
    
    frozen = freezer.freeze(
        query="What is regularization in ML?",
        role="researcher",
        candidates=[
            {"id": "doc_001", "score": 0.95},
            {"id": "doc_002", "score": 0.89},
            {"id": "doc_003", "score": 0.75}
        ],
        trace=example_trace,
        notes="Example frozen trace for testing"
    )
    
    print(f"\nCreated example trace: {frozen.trace_id}")
    print(f"To replay: python tools/replay_cli.py {frozen.trace_id}")
