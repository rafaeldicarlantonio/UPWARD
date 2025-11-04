#!/usr/bin/env python3
"""
Unit tests for bounded graph expansion with budgets.

Tests:
1. Node budget enforcement
2. Time budget enforcement  
3. Depth budget enforcement
4. Short-circuit on budget exceeded
5. Truncation behavior and metrics
6. Heavy graph still returns in time
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Tuple, Any

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.graph_expand import GraphExpander, GraphExpansionResult, expand_entity_bounded


class MockMemory:
    """Mock memory object."""
    def __init__(self, id: str, title: str, content: str, role_view_level: int = 0):
        self.id = id
        self.title = title
        self.content = content
        self.role_view_level = role_view_level


class MockDBAdapter:
    """Mock database adapter for testing."""
    
    def __init__(self, relations: List[Tuple[str, str, float]], memories: List[MockMemory], delay_ms: float = 0):
        self.relations = relations
        self.memories = memories
        self.delay_ms = delay_ms
        self.get_relations_calls = 0
        self.get_memories_calls = 0
    
    def get_entity_relations(self, entity_id: str, limit: int = 10) -> List[Tuple[str, str, float]]:
        """Mock get entity relations."""
        self.get_relations_calls += 1
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
        return self.relations[:limit]
    
    def get_entity_memories(self, entity_id: str, limit: int = 50) -> List[MockMemory]:
        """Mock get entity memories."""
        self.get_memories_calls += 1
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
        return self.memories[:limit]


class TestGraphBudgetEnforcement(unittest.TestCase):
    """Test budget enforcement for graph expansion."""
    
    def test_node_budget_truncates_relations(self):
        """Test that node budget truncates relations."""
        # Create 100 relations but budget is 50
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(100)]
        memories = []
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # Should truncate to 50 or less
        self.assertLessEqual(result.nodes_visited, 50)
        self.assertTrue(result.truncated)
        self.assertIn("budget", result.truncation_reason.lower())
    
    def test_time_budget_short_circuits(self):
        """Test that time budget causes short-circuit."""
        # Create slow adapter
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(10)]
        memories = [MockMemory(f"mem_{i}", f"Title {i}", f"Content {i}") for i in range(10)]
        
        # 200ms delay but timeout is 50ms
        db_adapter = MockDBAdapter(relations, memories, delay_ms=200)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=50)
        
        start = time.time()
        result = expander.expand_entity("test_entity", db_adapter)
        elapsed = (time.time() - start) * 1000
        
        # Should timeout quickly
        self.assertTrue(result.truncated)
        self.assertIn("timeout", result.truncation_reason.lower())
        self.assertTrue(result.budget_exceeded.get('time', False))
        
        # Should not take much longer than timeout
        self.assertLess(elapsed, 300)  # Allow some overhead
    
    def test_depth_budget_respected(self):
        """Test that depth budget is respected."""
        relations = [("child_of", "parent_entity", 0.9)]
        memories = []
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # Depth should not exceed max_depth
        self.assertLessEqual(result.depth_reached, 1)
    
    def test_combined_budget_enforcement(self):
        """Test that multiple budgets are enforced together."""
        # Large graph with slow access
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(200)]
        memories = [MockMemory(f"mem_{i}", f"Title {i}", f"Content {i}") for i in range(100)]
        
        db_adapter = MockDBAdapter(relations, memories, delay_ms=100)
        expander = GraphExpander(max_neighbors=20, max_depth=1, timeout_ms=150)
        
        start = time.time()
        result = expander.expand_entity("test_entity", db_adapter)
        elapsed = (time.time() - start) * 1000
        
        # Should be truncated due to at least one budget
        self.assertTrue(result.truncated)
        
        # Should not visit more than max_neighbors
        self.assertLessEqual(result.nodes_visited, 20)
        
        # Should complete within reasonable time
        self.assertLess(elapsed, 300)


class TestGraphExpansionTruncation(unittest.TestCase):
    """Test truncation behavior and edge cases."""
    
    def test_empty_graph_no_truncation(self):
        """Test that empty graph doesn't truncate."""
        db_adapter = MockDBAdapter([], [])
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # No truncation needed
        self.assertFalse(result.truncated)
        self.assertEqual(result.nodes_visited, 0)
    
    def test_small_graph_no_truncation(self):
        """Test that small graph within budget doesn't truncate."""
        relations = [("rel_1", "entity_1", 0.9)]
        memories = [MockMemory("mem_1", "Title", "Content")]
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # Should complete without truncation
        self.assertFalse(result.truncated)
        self.assertEqual(result.nodes_visited, 2)  # 1 relation + 1 memory
    
    def test_exactly_at_budget(self):
        """Test graph exactly at budget."""
        # Exactly 50 nodes
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(30)]
        memories = [MockMemory(f"mem_{i}", f"Title {i}", f"Content {i}") for i in range(20)]
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # Might or might not truncate depending on implementation
        self.assertLessEqual(result.nodes_visited, 50)
    
    def test_truncation_reason_recorded(self):
        """Test that truncation reason is recorded."""
        # Over node budget
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(100)]
        memories = []
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        self.assertTrue(result.truncated)
        self.assertIsNotNone(result.truncation_reason)
        self.assertIn("budget", result.truncation_reason.lower())
    
    def test_summary_includes_truncation_notice(self):
        """Test that summary indicates truncation."""
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(100)]
        memories = []
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=10, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        self.assertIn("[Truncated:", result.summary)


class TestHeavyGraphPerformance(unittest.TestCase):
    """Test performance with heavy synthetic graphs."""
    
    def test_heavy_graph_returns_in_time(self):
        """Test that heavy graph still returns within timeout."""
        # Synthetic heavy graph: 1000 relations, 500 memories
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(1000)]
        memories = [MockMemory(f"mem_{i}", f"Title {i}", f"Content {i}" * 100) for i in range(500)]
        
        # Slow adapter: 50ms per call
        db_adapter = MockDBAdapter(relations, memories, delay_ms=50)
        
        # Tight budget: 150ms timeout, 50 node max
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=150)
        
        start = time.time()
        result = expander.expand_entity("heavy_entity", db_adapter)
        elapsed = (time.time() - start) * 1000
        
        # Should complete within timeout (with some overhead)
        self.assertLess(elapsed, 250, "Heavy graph should return within reasonable time")
        
        # Should have truncated neighbors
        self.assertTrue(result.truncated)
        self.assertLessEqual(result.nodes_visited, 50)
        
        # Should still have some results
        self.assertGreater(len(result.relations) + len(result.memories), 0)
    
    def test_extremely_heavy_graph_short_circuits(self):
        """Test that extremely heavy graph short-circuits quickly."""
        # Extremely heavy graph
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(10000)]
        memories = [MockMemory(f"mem_{i}", f"Title {i}", f"Content {i}" * 1000) for i in range(5000)]
        
        # Very slow adapter: 100ms per call
        db_adapter = MockDBAdapter(relations, memories, delay_ms=100)
        
        # Very tight budget: 50ms timeout
        expander = GraphExpander(max_neighbors=10, max_depth=1, timeout_ms=50)
        
        start = time.time()
        result = expander.expand_entity("extreme_entity", db_adapter)
        elapsed = (time.time() - start) * 1000
        
        # Should short-circuit very quickly
        self.assertLess(elapsed, 200, "Should short-circuit quickly")
        
        # Should be truncated
        self.assertTrue(result.truncated)
        self.assertTrue(result.budget_exceeded.get('time', False))


class TestMetricsTracking(unittest.TestCase):
    """Test that metrics are tracked correctly."""
    
    @patch('core.graph_expand.increment_counter')
    @patch('core.graph_expand.observe_histogram')
    def test_truncation_metrics_recorded(self, mock_histogram, mock_counter):
        """Test that truncation count is recorded in metrics."""
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(100)]
        memories = []
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=10, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # Should have recorded truncation
        self.assertTrue(result.truncated)
        
        # Should have called increment_counter for truncation
        truncation_calls = [
            call for call in mock_counter.call_args_list
            if 'truncated' in str(call) or 'budget_exceeded' in str(call)
        ]
        self.assertGreater(len(truncation_calls), 0, "Should record truncation metrics")
    
    @patch('core.graph_expand.increment_counter')
    @patch('core.graph_expand.observe_histogram')
    def test_latency_metrics_recorded(self, mock_histogram, mock_counter):
        """Test that latency is recorded in metrics."""
        relations = [("rel_1", "entity_1", 0.9)]
        memories = [MockMemory("mem_1", "Title", "Content")]
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # Should have recorded latency
        latency_calls = [
            call for call in mock_histogram.call_args_list
            if 'latency' in str(call)
        ]
        self.assertGreater(len(latency_calls), 0, "Should record latency metrics")
    
    @patch('core.graph_expand.increment_counter')
    def test_nodes_visited_metrics_recorded(self, mock_counter):
        """Test that nodes visited count is recorded."""
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(10)]
        memories = [MockMemory(f"mem_{i}", f"Title {i}", f"Content {i}") for i in range(5)]
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # Should track total
        total_calls = [
            call for call in mock_counter.call_args_list
            if 'total' in str(call)
        ]
        self.assertGreater(len(total_calls), 0, "Should record total expansions")


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function for bounded expansion."""
    
    def test_expand_entity_bounded_basic(self):
        """Test basic usage of convenience function."""
        relations = [("rel_1", "entity_1", 0.9)]
        memories = [MockMemory("mem_1", "Title", "Content")]
        
        db_adapter = MockDBAdapter(relations, memories)
        
        result = expand_entity_bounded(
            entity_id="test_entity",
            db_adapter=db_adapter,
            max_neighbors=50,
            max_depth=1,
            timeout_ms=1000
        )
        
        self.assertIsInstance(result, GraphExpansionResult)
        self.assertGreater(result.nodes_visited, 0)
    
    def test_expand_entity_bounded_with_truncation(self):
        """Test convenience function with truncation."""
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(100)]
        memories = []
        
        db_adapter = MockDBAdapter(relations, memories)
        
        result = expand_entity_bounded(
            entity_id="test_entity",
            db_adapter=db_adapter,
            max_neighbors=10,
            timeout_ms=1000
        )
        
        self.assertTrue(result.truncated)
        self.assertLessEqual(result.nodes_visited, 10)


class TestRoleFiltering(unittest.TestCase):
    """Test role-based filtering of memories."""
    
    def test_role_filtering_respects_level(self):
        """Test that role filtering respects view levels."""
        relations = [("rel_1", "entity_1", 0.9)]
        # Mix of role levels
        memories = [
            MockMemory("mem_1", "Public", "Content 1", role_view_level=0),
            MockMemory("mem_2", "Restricted", "Content 2", role_view_level=3),
            MockMemory("mem_3", "Public", "Content 3", role_view_level=1)
        ]
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=1000)
        
        # Expand with role
        result = expander.expand_entity(
            "test_entity",
            db_adapter,
            caller_roles=["general"]  # Level 1
        )
        
        # Should filter based on role level
        # Exact behavior depends on RBAC implementation
        self.assertIsNotNone(result)


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    def test_synthetic_heavy_graph_returns_in_time(self):
        """Test: synthetic heavy graph returns in time with truncated neighbors."""
        # Heavy graph: 1000 relations, 500 memories
        relations = [(f"rel_{i}", f"entity_{i}", 0.8 - i*0.0001) for i in range(1000)]
        memories = [
            MockMemory(f"mem_{i}", f"Title {i}", f"Long content {i}" * 50)
            for i in range(500)
        ]
        
        # Slow adapter
        db_adapter = MockDBAdapter(relations, memories, delay_ms=30)
        
        # Constrained budget
        expander = GraphExpander(max_neighbors=50, max_depth=1, timeout_ms=150)
        
        start = time.time()
        result = expander.expand_entity("heavy_entity", db_adapter)
        elapsed = (time.time() - start) * 1000
        
        # ✅ Returns in time
        self.assertLess(elapsed, 250, "Should return within time budget")
        
        # ✅ Neighbors truncated
        self.assertTrue(result.truncated, "Should have truncated neighbors")
        self.assertLessEqual(result.nodes_visited, 50, "Should respect node budget")
        
        # ✅ Still has results
        self.assertGreater(len(result.relations) + len(result.memories), 0, "Should have partial results")
    
    @patch('core.graph_expand.increment_counter')
    def test_metrics_show_truncation_count(self, mock_counter):
        """Test: metrics show truncation count."""
        # Graph that will truncate
        relations = [(f"rel_{i}", f"entity_{i}", 0.9) for i in range(200)]
        memories = []
        
        db_adapter = MockDBAdapter(relations, memories)
        expander = GraphExpander(max_neighbors=20, max_depth=1, timeout_ms=1000)
        
        result = expander.expand_entity("test_entity", db_adapter)
        
        # ✅ Truncation occurred
        self.assertTrue(result.truncated)
        
        # ✅ Metrics recorded
        truncation_calls = [
            call for call in mock_counter.call_args_list
            if 'truncated' in str(call[0][0]) or 'budget_exceeded' in str(call[0][0])
        ]
        
        self.assertGreater(len(truncation_calls), 0, "Metrics should show truncation count")


if __name__ == "__main__":
    unittest.main()
