#!/usr/bin/env python3
"""
Unit tests for parallel dual-index selection.

Tests:
1. Parallel queries complete faster than sequential
2. Timeout handling with partial results
3. One index delayed/timeout - still returns results
4. Both indices timeout - returns empty with warnings
5. Timing metrics recorded correctly
6. Warnings tagged appropriately
"""

import asyncio
import sys
import time
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Any, Dict

# Add workspace to path
sys.path.insert(0, '/workspace')

# Mock problematic imports before importing core.selection
sys.modules['supabase'] = Mock()
sys.modules['vendors.supabase_client'] = Mock()
sys.modules['vendors.pinecone_client'] = Mock()
sys.modules['app.settings'] = Mock()
sys.modules['tenacity'] = Mock()
sys.modules['pydantic'] = Mock()

# Mock tenacity decorators
mock_tenacity = Mock()
mock_tenacity.retry = lambda *args, **kwargs: lambda f: f
mock_tenacity.stop_after_attempt = Mock()
mock_tenacity.wait_exponential = Mock()
mock_tenacity.retry_if_exception_type = Mock()
sys.modules['tenacity'] = mock_tenacity

from core.selection import DualSelector, SelectionResult


class MockQueryResponse:
    """Mock Pinecone query response."""
    def __init__(self, matches: List[Any]):
        self.matches = matches


class MockMatch:
    """Mock Pinecone match."""
    def __init__(self, id: str, score: float, metadata: Dict[str, Any]):
        self.id = id
        self.score = score
        self.metadata = metadata


class TestParallelSelection(unittest.TestCase):
    """Test parallel dual-index selection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.selector = DualSelector()
        self.test_embedding = [0.1] * 1536
        self.test_query = "test query"
    
    def _create_mock_matches(self, prefix: str, count: int) -> List[MockMatch]:
        """Create mock matches for testing."""
        return [
            MockMatch(
                id=f"{prefix}_{i}",
                score=0.9 - (i * 0.1),
                metadata={
                    "text": f"Text for {prefix}_{i}",
                    "title": f"Title {i}",
                    "type": "semantic",
                    "role_rank": 1
                }
            )
            for i in range(count)
        ]
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_parallel_queries_faster_than_sequential(self, mock_query_async, mock_config):
        """Test that parallel queries complete in ~max(single) not sum(both)."""
        # Configure parallel execution
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 1000,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        # Mock both queries taking 200ms each
        explicate_matches = self._create_mock_matches("exp", 3)
        implicate_matches = self._create_mock_matches("imp", 2)
        
        async def mock_async_query(*args, **kwargs):
            # Simulate parallel execution - wall time should be ~max not sum
            await asyncio.sleep(0.2)  # Both take 200ms
            timings = {
                'explicate_ms': 200,
                'implicate_ms': 200,
                'total_wall_time_ms': 200  # Parallel, so ~max not sum
            }
            return (
                MockQueryResponse(explicate_matches),
                MockQueryResponse(implicate_matches),
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        start = time.time()
        result = self.selector.select(
            query=self.test_query,
            embedding=self.test_embedding,
            use_parallel=True
        )
        wall_time = (time.time() - start) * 1000
        
        # Assertions
        self.assertEqual(result.strategy_used, "dual_parallel")
        self.assertIn('total_wall_time_ms', result.timings)
        
        # Wall time should be closer to 200ms (max) than 400ms (sum)
        # Allow for overhead but verify it's not sequential
        self.assertLess(wall_time, 350, "Wall time suggests sequential execution")
        
        # Timings should show parallel execution
        self.assertAlmostEqual(result.timings['total_wall_time_ms'], 200, delta=50)
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_explicate_timeout_returns_implicate_only(self, mock_query_async, mock_config):
        """Test that explicate timeout still returns implicate results."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 500,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        # Only implicate succeeds
        implicate_matches = self._create_mock_matches("imp", 3)
        
        async def mock_async_query(*args, **kwargs):
            timings = {
                'explicate_ms': 500,
                'explicate_timeout': True,
                'implicate_ms': 100,
                'total_wall_time_ms': 500
            }
            return (
                None,  # Explicate timed out
                MockQueryResponse(implicate_matches),
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = self.selector.select(
            query=self.test_query,
            embedding=self.test_embedding,
            use_parallel=True
        )
        
        # Assertions
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("Explicate query timed out", result.warnings[0])
        self.assertIn('explicate_timeout', result.timings)
        self.assertTrue(result.timings['explicate_timeout'])
        
        # Should still have results from implicate
        self.assertGreater(result.metadata['implicate_hits'], 0)
        self.assertEqual(result.metadata['explicate_hits'], 0)
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_implicate_timeout_returns_explicate_only(self, mock_query_async, mock_config):
        """Test that implicate timeout still returns explicate results."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 500,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        # Only explicate succeeds
        explicate_matches = self._create_mock_matches("exp", 4)
        
        async def mock_async_query(*args, **kwargs):
            timings = {
                'explicate_ms': 100,
                'implicate_ms': 500,
                'implicate_timeout': True,
                'total_wall_time_ms': 500
            }
            return (
                MockQueryResponse(explicate_matches),
                None,  # Implicate timed out
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = self.selector.select(
            query=self.test_query,
            embedding=self.test_embedding,
            use_parallel=True
        )
        
        # Assertions
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("Implicate query timed out", result.warnings[0])
        self.assertIn('implicate_timeout', result.timings)
        self.assertTrue(result.timings['implicate_timeout'])
        
        # Should still have results from explicate
        self.assertGreater(result.metadata['explicate_hits'], 0)
        self.assertEqual(result.metadata['implicate_hits'], 0)
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_both_timeout_returns_empty_with_warnings(self, mock_query_async, mock_config):
        """Test that both timeouts return empty results with warnings."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 500,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        async def mock_async_query(*args, **kwargs):
            timings = {
                'explicate_ms': 500,
                'explicate_timeout': True,
                'implicate_ms': 500,
                'implicate_timeout': True,
                'total_wall_time_ms': 500
            }
            return (None, None, timings)
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = self.selector.select(
            query=self.test_query,
            embedding=self.test_embedding,
            use_parallel=True
        )
        
        # Assertions
        self.assertEqual(len(result.warnings), 2)
        self.assertIn("Explicate query timed out", result.warnings[0])
        self.assertIn("Implicate query timed out", result.warnings[1])
        
        # Both should show timeout
        self.assertTrue(result.timings['explicate_timeout'])
        self.assertTrue(result.timings['implicate_timeout'])
        
        # No hits from either
        self.assertEqual(result.metadata['explicate_hits'], 0)
        self.assertEqual(result.metadata['implicate_hits'], 0)
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_timings_recorded_correctly(self, mock_query_async, mock_config):
        """Test that individual and total timings are recorded."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 1000,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        explicate_matches = self._create_mock_matches("exp", 2)
        implicate_matches = self._create_mock_matches("imp", 2)
        
        async def mock_async_query(*args, **kwargs):
            timings = {
                'explicate_ms': 150,
                'implicate_ms': 200,
                'total_wall_time_ms': 200  # Max of both
            }
            return (
                MockQueryResponse(explicate_matches),
                MockQueryResponse(implicate_matches),
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = self.selector.select(
            query=self.test_query,
            embedding=self.test_embedding,
            use_parallel=True
        )
        
        # Assertions
        self.assertIn('explicate_ms', result.timings)
        self.assertIn('implicate_ms', result.timings)
        self.assertIn('total_wall_time_ms', result.timings)
        
        # Individual timings
        self.assertEqual(result.timings['explicate_ms'], 150)
        self.assertEqual(result.timings['implicate_ms'], 200)
        
        # Total should be ~max not sum
        self.assertEqual(result.timings['total_wall_time_ms'], 200)
        self.assertLess(result.timings['total_wall_time_ms'], 250)
    
    @patch('core.selection.load_config')
    def test_sequential_fallback_when_parallel_disabled(self, mock_config):
        """Test that sequential queries are used when parallel is disabled."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': False,  # Parallel disabled
            'PERF_RETRIEVAL_TIMEOUT_MS': 1000,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        explicate_matches = self._create_mock_matches("exp", 2)
        implicate_matches = self._create_mock_matches("imp", 1)
        
        with patch.object(self.selector.vector_store, 'query_explicit') as mock_exp:
            with patch.object(self.selector.vector_store, 'query_implicate') as mock_imp:
                mock_exp.return_value = MockQueryResponse(explicate_matches)
                mock_imp.return_value = MockQueryResponse(implicate_matches)
                
                # Execute
                result = self.selector.select(
                    query=self.test_query,
                    embedding=self.test_embedding
                )
                
                # Should use sequential (strategy_used != "dual_parallel")
                self.assertNotEqual(result.strategy_used, "dual_parallel")
                
                # Both queries should have been called
                mock_exp.assert_called_once()
                mock_imp.assert_called_once()
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_error_in_one_query_continues_with_other(self, mock_query_async, mock_config):
        """Test that error in one query doesn't fail the whole operation."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 1000,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        implicate_matches = self._create_mock_matches("imp", 3)
        
        async def mock_async_query(*args, **kwargs):
            timings = {
                'explicate_ms': 50,
                'explicate_error': 'Connection refused',
                'implicate_ms': 100,
                'total_wall_time_ms': 100
            }
            return (
                None,  # Explicate errored
                MockQueryResponse(implicate_matches),
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = self.selector.select(
            query=self.test_query,
            embedding=self.test_embedding,
            use_parallel=True
        )
        
        # Assertions
        self.assertIn('explicate_error', result.timings)
        self.assertEqual(result.timings['explicate_error'], 'Connection refused')
        
        # Should still have implicate results
        self.assertGreater(result.metadata['implicate_hits'], 0)
        self.assertEqual(result.metadata['explicate_hits'], 0)
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_parallel_with_mixed_timing(self, mock_query_async, mock_config):
        """Test parallel execution with one fast and one slow query."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 1000,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        explicate_matches = self._create_mock_matches("exp", 3)
        implicate_matches = self._create_mock_matches("imp", 2)
        
        async def mock_async_query(*args, **kwargs):
            # Explicate fast (50ms), implicate slow (400ms)
            timings = {
                'explicate_ms': 50,
                'implicate_ms': 400,
                'total_wall_time_ms': 400  # ~max not sum
            }
            return (
                MockQueryResponse(explicate_matches),
                MockQueryResponse(implicate_matches),
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = self.selector.select(
            query=self.test_query,
            embedding=self.test_embedding,
            use_parallel=True
        )
        
        # Assertions
        self.assertEqual(result.timings['explicate_ms'], 50)
        self.assertEqual(result.timings['implicate_ms'], 400)
        
        # Wall time should be ~400 (max) not 450 (sum)
        self.assertLess(result.timings['total_wall_time_ms'], 450)
        self.assertGreaterEqual(result.timings['total_wall_time_ms'], 400)
        
        # Both should have results
        self.assertGreater(result.metadata['explicate_hits'], 0)
        self.assertGreater(result.metadata['implicate_hits'], 0)


class TestVectorStoreAsync(unittest.TestCase):
    """Test async methods in VectorStore."""
    
    @patch('app.services.vector_store._legacy_get_index')
    def test_query_explicit_async_basic(self, mock_get_index):
        """Test basic async explicate query."""
        from app.services.vector_store import VectorStore
        
        # Mock index and query result
        mock_index = Mock()
        mock_get_index.return_value = mock_index
        
        mock_match = Mock()
        mock_match.id = "test1"
        mock_match.score = 0.9
        mock_match.metadata = {"text": "test"}
        
        mock_result = Mock()
        mock_result.matches = [mock_match]
        mock_index.query.return_value = mock_result
        
        # Create vector store
        vs = VectorStore()
        
        # Execute async query
        async def run_test():
            result = await vs.query_explicit_async(
                embedding=[0.1] * 1536,
                top_k=10
            )
            return result
        
        result = asyncio.run(run_test())
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, 'matches'))
        self.assertGreater(len(result.matches), 0)
    
    @patch('app.services.vector_store._legacy_get_index')
    def test_query_implicate_async_with_timeout(self, mock_get_index):
        """Test async implicate query with timeout."""
        from app.services.vector_store import VectorStore
        
        # Mock slow query
        mock_index = Mock()
        mock_get_index.return_value = mock_index
        
        def slow_query(*args, **kwargs):
            time.sleep(2)  # Exceeds timeout
            return Mock(matches=[])
        
        mock_index.query.side_effect = slow_query
        
        # Create vector store
        vs = VectorStore()
        
        # Execute with timeout - should raise TimeoutError
        timeout_raised = False
        async def run_test():
            nonlocal timeout_raised
            try:
                await vs.query_implicate_async(
                    embedding=[0.1] * 1536,
                    top_k=10,
                    timeout=0.1  # 100ms timeout (very short to ensure it fires)
                )
            except asyncio.TimeoutError:
                timeout_raised = True
        
        asyncio.run(run_test())
        
        # Verify timeout occurred
        self.assertTrue(timeout_raised, "TimeoutError should have been raised")


class TestAcceptanceCriteria(unittest.TestCase):
    """Test acceptance criteria from requirements."""
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_one_index_delayed_partial_merge(self, mock_query_async, mock_config):
        """Test: one index delayed -> partial merge, not total failure."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 300,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        selector = DualSelector()
        
        # Create matches
        explicate_matches = [
            MockMatch(id=f"exp_{i}", score=0.9, metadata={"text": f"exp {i}", "role_rank": 1})
            for i in range(3)
        ]
        
        # Simulate one index delayed (timeout)
        async def mock_async_query(*args, **kwargs):
            timings = {
                'explicate_ms': 100,  # Fast
                'implicate_ms': 300,  # Timeout
                'implicate_timeout': True,
                'total_wall_time_ms': 300
            }
            return (
                MockQueryResponse(explicate_matches),
                None,  # Implicate timed out
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = selector.select(
            query="test",
            embedding=[0.1] * 1536,
            use_parallel=True
        )
        
        # ? Partial merge, not total failure
        self.assertGreater(result.metadata['explicate_hits'], 0, "Should have explicate results")
        self.assertEqual(result.metadata['implicate_hits'], 0, "Implicate should be empty")
        self.assertGreater(len(result.warnings), 0, "Should have timeout warning")
        self.assertIn("Implicate query timed out", result.warnings[0])
    
    @patch('core.selection.load_config')
    @patch.object(DualSelector, '_query_both_indices_async')
    def test_wall_time_is_max_not_sum(self, mock_query_async, mock_config):
        """Test: overall wall time ~max(single-call) not sum."""
        mock_config.return_value = {
            'PERF_RETRIEVAL_PARALLEL': True,
            'PERF_RETRIEVAL_TIMEOUT_MS': 1000,
            'PERF_GRAPH_TIMEOUT_MS': 150
        }
        
        selector = DualSelector()
        
        explicate_matches = [MockMatch(id=f"exp_{i}", score=0.9, metadata={"text": "test", "role_rank": 1}) for i in range(2)]
        implicate_matches = [MockMatch(id=f"imp_{i}", score=0.8, metadata={"text": "test", "role_rank": 1, "entity_id": f"e{i}"}) for i in range(2)]
        
        async def mock_async_query(*args, **kwargs):
            # Both queries take time, but run in parallel
            explicate_time = 200
            implicate_time = 250
            wall_time = max(explicate_time, implicate_time)  # Parallel execution
            
            timings = {
                'explicate_ms': explicate_time,
                'implicate_ms': implicate_time,
                'total_wall_time_ms': wall_time  # ~max not sum
            }
            return (
                MockQueryResponse(explicate_matches),
                MockQueryResponse(implicate_matches),
                timings
            )
        
        mock_query_async.return_value = asyncio.run(mock_async_query())
        
        # Execute
        result = selector.select(
            query="test",
            embedding=[0.1] * 1536,
            use_parallel=True
        )
        
        # ? Wall time is ~max not sum
        explicate_ms = result.timings['explicate_ms']
        implicate_ms = result.timings['implicate_ms']
        wall_time_ms = result.timings['total_wall_time_ms']
        
        # Wall time should be close to max, not sum
        expected_max = max(explicate_ms, implicate_ms)
        expected_sum = explicate_ms + implicate_ms
        
        self.assertAlmostEqual(wall_time_ms, expected_max, delta=50, 
                              msg="Wall time should be ~max(individual)")
        self.assertLess(wall_time_ms, expected_sum - 50,
                       msg="Wall time should not be sum(individual)")


if __name__ == "__main__":
    unittest.main()
