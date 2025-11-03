#!/usr/bin/env python3
"""
Unit tests for replay CLI and trace freezer.

Tests verify:
1. Trace freezing captures all necessary data
2. Replay produces identical trace hash
3. Candidate IDs match on replay
4. Randomness seeding is deterministic
5. Offline replay works without API
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

# Add workspace to path
sys.path.insert(0, '/workspace')

from evals.freezer import (
    TraceFreezer,
    TraceHasher,
    ReplaySeeder,
    FrozenTrace,
    freeze_from_response
)
from tools.replay_cli import ReplayRunner


class TestTraceHasher(unittest.TestCase):
    """Test trace hashing for determinism."""
    
    def test_hash_deterministic(self):
        """Test that same trace produces same hash."""
        trace = {
            "answer": "Test answer",
            "citations": [{"id": "doc_001"}, {"id": "doc_002"}],
            "orchestration": {"retrieved": 10}
        }
        
        hash1 = TraceHasher.hash_trace(trace)
        hash2 = TraceHasher.hash_trace(trace)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 16)  # Should be 16 chars
    
    def test_hash_excludes_timing(self):
        """Test that timing fields don't affect hash."""
        trace1 = {
            "answer": "Test",
            "latency_ms": 100,
            "timing": {"retrieval": 50}
        }
        
        trace2 = {
            "answer": "Test",
            "latency_ms": 200,
            "timing": {"retrieval": 150}
        }
        
        hash1 = TraceHasher.hash_trace(trace1)
        hash2 = TraceHasher.hash_trace(trace2)
        
        # Hashes should be equal (timing excluded)
        self.assertEqual(hash1, hash2)
    
    def test_hash_different_for_different_traces(self):
        """Test that different traces produce different hashes."""
        trace1 = {"answer": "Answer 1"}
        trace2 = {"answer": "Answer 2"}
        
        hash1 = TraceHasher.hash_trace(trace1)
        hash2 = TraceHasher.hash_trace(trace2)
        
        self.assertNotEqual(hash1, hash2)
    
    def test_hash_candidates(self):
        """Test candidate list hashing."""
        candidates = [
            {"id": "doc_001", "score": 0.95},
            {"id": "doc_002", "score": 0.89}
        ]
        
        hash1 = TraceHasher.hash_candidates(candidates)
        hash2 = TraceHasher.hash_candidates(candidates)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 16)
    
    def test_hash_candidates_order_matters(self):
        """Test that candidate order affects hash."""
        candidates1 = [{"id": "doc_001"}, {"id": "doc_002"}]
        candidates2 = [{"id": "doc_002"}, {"id": "doc_001"}]
        
        hash1 = TraceHasher.hash_candidates(candidates1)
        hash2 = TraceHasher.hash_candidates(candidates2)
        
        self.assertNotEqual(hash1, hash2)


class TestReplaySeeder(unittest.TestCase):
    """Test randomness seeding."""
    
    def test_seed_all_python_random(self):
        """Test seeding Python's random module."""
        import random
        
        ReplaySeeder.seed_all(12345)
        val1 = random.random()
        
        ReplaySeeder.seed_all(12345)
        val2 = random.random()
        
        self.assertEqual(val1, val2)
    
    def test_seed_all_numpy_random(self):
        """Test seeding NumPy's random (if available)."""
        try:
            import numpy as np
            
            ReplaySeeder.seed_all(12345)
            val1 = np.random.random()
            
            ReplaySeeder.seed_all(12345)
            val2 = np.random.random()
            
            self.assertEqual(val1, val2)
        except ImportError:
            self.skipTest("NumPy not available")
    
    def test_get_current_state(self):
        """Test capturing current random state."""
        state = ReplaySeeder.get_current_state()
        
        self.assertIn("python_random", state)
        self.assertIsNotNone(state["python_random"])


class TestTraceFreezer(unittest.TestCase):
    """Test trace freezing functionality."""
    
    def setUp(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.freezer = TraceFreezer(output_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_freeze_creates_frozen_trace(self):
        """Test that freeze creates FrozenTrace object."""
        frozen = self.freezer.freeze(
            query="Test query",
            role="researcher",
            candidates=[{"id": "doc_001"}],
            trace={"answer": "Test answer"}
        )
        
        self.assertIsInstance(frozen, FrozenTrace)
        self.assertEqual(frozen.query, "Test query")
        self.assertEqual(frozen.role, "researcher")
        self.assertGreater(len(frozen.trace_hash), 0)
    
    def test_freeze_saves_to_disk(self):
        """Test that freeze saves trace to disk."""
        frozen = self.freezer.freeze(
            query="Test query",
            role="researcher",
            candidates=[],
            trace={}
        )
        
        trace_path = Path(self.temp_dir) / f"{frozen.trace_id}.json"
        self.assertTrue(trace_path.exists())
    
    def test_freeze_limits_candidates_to_top_k(self):
        """Test that only top-k candidates are saved."""
        candidates = [{"id": f"doc_{i:03d}"} for i in range(20)]
        
        frozen = self.freezer.freeze(
            query="Test",
            role="researcher",
            candidates=candidates,
            trace={},
            top_k=5
        )
        
        self.assertEqual(len(frozen.candidates), 5)
        self.assertEqual(frozen.candidates[0]["id"], "doc_000")
        self.assertEqual(frozen.candidates[4]["id"], "doc_004")
    
    def test_load_frozen_trace(self):
        """Test loading a frozen trace."""
        # Create and save a trace
        frozen = self.freezer.freeze(
            query="Test query",
            role="researcher",
            candidates=[{"id": "doc_001"}],
            trace={"answer": "Test answer"}
        )
        
        # Load it back
        loaded = self.freezer.load(frozen.trace_id)
        
        self.assertEqual(loaded.trace_id, frozen.trace_id)
        self.assertEqual(loaded.query, frozen.query)
        self.assertEqual(loaded.trace_hash, frozen.trace_hash)
    
    def test_load_nonexistent_trace_raises(self):
        """Test that loading nonexistent trace raises error."""
        with self.assertRaises(FileNotFoundError):
            self.freezer.load("nonexistent_trace_id")
    
    def test_list_traces(self):
        """Test listing available traces."""
        # Create multiple traces
        for i in range(3):
            self.freezer.freeze(
                query=f"Query {i}",
                role="researcher",
                candidates=[],
                trace={},
                trace_id=f"test_trace_{i}"
            )
        
        traces = self.freezer.list_traces()
        
        self.assertEqual(len(traces), 3)
        self.assertIn("test_trace_0", traces)
        self.assertIn("test_trace_1", traces)
        self.assertIn("test_trace_2", traces)
    
    def test_get_trace_info(self):
        """Test getting trace info."""
        frozen = self.freezer.freeze(
            query="Test query for info",
            role="researcher",
            candidates=[{"id": "doc_001"}, {"id": "doc_002"}],
            trace={"answer": "Test"},
            notes="Test notes"
        )
        
        info = self.freezer.get_trace_info(frozen.trace_id)
        
        self.assertEqual(info["trace_id"], frozen.trace_id)
        self.assertIn("Test query", info["query"])
        self.assertEqual(info["trace_hash"], frozen.trace_hash)
        self.assertEqual(info["candidates_count"], 2)
        self.assertEqual(info["notes"], "Test notes")


class TestFreezeFromResponse(unittest.TestCase):
    """Test convenience function for freezing from API response."""
    
    def setUp(self):
        """Set up temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_freeze_from_response_with_citations(self):
        """Test freezing from response with citations."""
        response = {
            "answer": "Test answer",
            "citations": [
                {"source_id": "doc_001", "text": "Citation 1"},
                {"source_id": "doc_002", "text": "Citation 2"}
            ],
            "debug": {
                "metrics": {"retrieved": 10}
            }
        }
        
        freezer = TraceFreezer(output_dir=self.temp_dir)
        frozen = freeze_from_response(
            query="Test query",
            role="researcher",
            response=response,
            freezer=freezer
        )
        
        self.assertEqual(frozen.query, "Test query")
        self.assertEqual(len(frozen.candidates), 2)
        self.assertEqual(frozen.candidates[0]["source_id"], "doc_001")
    
    def test_freeze_from_response_with_debug_candidates(self):
        """Test freezing when candidates are in debug section."""
        response = {
            "answer": "Test",
            "debug": {
                "retrieved_candidates": [
                    {"id": "doc_001"},
                    {"id": "doc_002"}
                ],
                "metrics": {}
            }
        }
        
        freezer = TraceFreezer(output_dir=self.temp_dir)
        frozen = freeze_from_response(
            query="Test",
            role="researcher",
            response=response,
            freezer=freezer
        )
        
        self.assertEqual(len(frozen.candidates), 2)


class TestReplayRunner(unittest.TestCase):
    """Test replay functionality."""
    
    def setUp(self):
        """Set up temporary directory and freezer."""
        self.temp_dir = tempfile.mkdtemp()
        self.freezer = TraceFreezer(output_dir=self.temp_dir)
        self.runner = ReplayRunner(freezer=self.freezer)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_replay_offline_matches_hash(self):
        """Test that offline replay produces matching hash."""
        # Create a frozen trace
        # Include candidates in the trace itself
        candidates = [{"id": "doc_001"}]
        trace = {
            "answer": "Test answer",
            "citations": [{"id": "doc_001"}],
            "orchestration": {"retrieved": 5},
            "candidates": candidates  # Include in trace for determinism
        }
        
        frozen = self.freezer.freeze(
            query="Test query",
            role="researcher",
            candidates=candidates,
            trace=trace,
            trace_id="test_replay_001"
        )
        
        # Replay it
        result = self.runner.replay(
            trace_id="test_replay_001",
            offline_mode=True,
            verbose=False
        )
        
        self.assertTrue(result["success"], f"Replay failed: {result.get('validation', {})}")
        self.assertTrue(result["validation"]["trace_hash_match"], 
                       f"Hash mismatch: {result['validation']['hash_original']} != {result['validation']['hash_replay']}")
    
    def test_replay_matches_candidate_ids(self):
        """Test that replay produces matching candidate IDs."""
        candidates = [
            {"id": "doc_001"},
            {"id": "doc_002"},
            {"id": "doc_003"}
        ]
        
        trace = {
            "answer": "Test",
            "candidates": candidates
        }
        
        frozen = self.freezer.freeze(
            query="Test",
            role="researcher",
            candidates=candidates,
            trace=trace,
            trace_id="test_replay_002"
        )
        
        result = self.runner.replay(
            trace_id="test_replay_002",
            offline_mode=True,
            verbose=False
        )
        
        self.assertTrue(result["success"], f"Replay failed: {result.get('validation', {})}")
        self.assertTrue(result["validation"]["candidate_ids_match"],
                       f"Candidate ID mismatch: {result['validation'].get('original_candidate_ids')} != {result['validation'].get('replay_candidate_ids')}")
    
    def test_replay_nonexistent_trace_fails(self):
        """Test that replaying nonexistent trace fails gracefully."""
        result = self.runner.replay(
            trace_id="nonexistent",
            verbose=False
        )
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_list_traces(self):
        """Test listing traces through runner."""
        # Create some traces
        for i in range(3):
            self.freezer.freeze(
                query=f"Query {i}",
                role="researcher",
                candidates=[],
                trace={},
                trace_id=f"trace_{i}"
            )
        
        traces = self.runner.list_traces(verbose=False)
        
        self.assertEqual(len(traces), 3)
    
    def test_get_info(self):
        """Test getting trace info through runner."""
        frozen = self.freezer.freeze(
            query="Test query",
            role="researcher",
            candidates=[],
            trace={},
            trace_id="info_test"
        )
        
        info = self.runner.get_info("info_test", verbose=False)
        
        self.assertNotIn("error", info)
        self.assertEqual(info["trace_id"], "info_test")


class TestDeterminism(unittest.TestCase):
    """Test determinism of replay system."""
    
    def setUp(self):
        """Set up temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.freezer = TraceFreezer(output_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_same_seed_produces_same_trace(self):
        """Test that same seed produces identical trace."""
        import random
        
        def create_trace_with_randomness(seed):
            """Create a trace with some randomness."""
            ReplaySeeder.seed_all(seed)
            
            # Generate some random data
            random_vals = [random.random() for _ in range(10)]
            random_ints = [random.randint(0, 100) for _ in range(10)]
            
            trace = {
                "random_floats": random_vals,
                "random_ints": random_ints,
                "computed": sum(random_vals)
            }
            
            return trace
        
        # Create two traces with same seed
        trace1 = create_trace_with_randomness(42)
        trace2 = create_trace_with_randomness(42)
        
        # They should be identical
        self.assertEqual(trace1, trace2)
        
        # Hash should match
        hash1 = TraceHasher.hash_trace(trace1)
        hash2 = TraceHasher.hash_trace(trace2)
        self.assertEqual(hash1, hash2)
    
    def test_different_seeds_produce_different_traces(self):
        """Test that different seeds produce different traces."""
        import random
        
        ReplaySeeder.seed_all(42)
        val1 = random.random()
        
        ReplaySeeder.seed_all(43)
        val2 = random.random()
        
        self.assertNotEqual(val1, val2)
    
    def test_multiple_replays_produce_same_hash(self):
        """Test that multiple replays produce same hash."""
        candidates = [{"id": "doc_001"}]
        trace = {
            "answer": "Test",
            "candidates": candidates  # Include in trace for determinism
        }
        
        frozen = self.freezer.freeze(
            query="Test",
            role="researcher",
            candidates=candidates,
            trace=trace,
            trace_id="multi_replay_test"
        )
        
        runner = ReplayRunner(freezer=self.freezer)
        
        # Replay multiple times
        hashes = []
        for _ in range(5):
            result = runner.replay(
                trace_id="multi_replay_test",
                offline_mode=True,
                verbose=False
            )
            hashes.append(result["validation"]["hash_replay"])
        
        # All hashes should be identical
        self.assertEqual(len(set(hashes)), 1, f"Hashes not identical: {hashes}")
        self.assertEqual(hashes[0], frozen.trace_hash, 
                        f"Replay hash {hashes[0]} doesn't match original {frozen.trace_hash}")


class TestOfflineReplay(unittest.TestCase):
    """Test offline replay without API calls."""
    
    def setUp(self):
        """Set up."""
        self.temp_dir = tempfile.mkdtemp()
        self.freezer = TraceFreezer(output_dir=self.temp_dir)
        self.runner = ReplayRunner(freezer=self.freezer)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_offline_replay_uses_frozen_candidates(self):
        """Test that offline replay uses frozen candidates."""
        candidates = [
            {"id": "doc_001", "score": 0.95},
            {"id": "doc_002", "score": 0.89}
        ]
        
        trace = {
            "answer": "Test answer",
            "candidates": candidates
        }
        
        frozen = self.freezer.freeze(
            query="Test",
            role="researcher",
            candidates=candidates,
            trace=trace,
            trace_id="offline_test"
        )
        
        # Replay offline (no API calls)
        result = self.runner.replay(
            trace_id="offline_test",
            offline_mode=True,
            verbose=False
        )
        
        # Should succeed without any API calls
        self.assertTrue(result["success"])
        self.assertEqual(
            result["replay_trace"]["candidates"],
            candidates
        )
    
    def test_offline_replay_no_network_required(self):
        """Test that offline replay works without network."""
        candidates = [{"id": "doc_001"}]
        trace = {
            "answer": "Test",
            "candidates": candidates  # Include in trace for determinism
        }
        
        frozen = self.freezer.freeze(
            query="Test",
            role="researcher",
            candidates=candidates,
            trace=trace,
            trace_id="no_network_test"
        )
        
        # Patch requests to ensure no network calls
        with patch('requests.post') as mock_post:
            result = self.runner.replay(
                trace_id="no_network_test",
                offline_mode=True,
                verbose=False
            )
            
            # Should succeed
            self.assertTrue(result["success"], f"Replay failed: {result.get('validation', {})}")
            
            # No network calls should have been made
            mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
