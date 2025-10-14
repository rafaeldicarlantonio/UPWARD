"""
Tests for REDO fallback system.
"""

import sys
import time
import logging
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.fallbacks import (
    RedoFallbackManager, FallbackConfig, HealthStatus,
    is_redo_active, safe_orchestrator_execution, safe_ledger_execution,
    execute_with_fallback, simulate_db_failure, simulate_orchestrator_failure,
    reset_fallback_state, get_fallback_manager
)
from core.types import QueryContext, OrchestrationResult, OrchestrationConfig
from core.orchestrator.interfaces import Orchestrator
from core.ledger import LedgerOptions

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


class TestRedoFallbackManager:
    """Test REDO fallback manager."""
    
    def test_initialization(self):
        """Test fallback manager initialization."""
        print("Testing fallback manager initialization...")
        
        config = FallbackConfig(
            enable_health_checks=True,
            health_check_interval_seconds=10.0,
            max_consecutive_failures=5
        )
        manager = RedoFallbackManager(config)
        
        assert manager.config.enable_health_checks == True
        assert manager.config.health_check_interval_seconds == 10.0
        assert manager.config.max_consecutive_failures == 5
        assert manager.health_status.consecutive_failures == 0
        assert manager.health_status.orchestrator_healthy == True
        assert manager.health_status.ledger_healthy == True
        
        print("✓ Fallback manager initialization works")
    
    def test_is_redo_active_with_flags(self):
        """Test is_redo_active with feature flags."""
        print("Testing is_redo_active with feature flags...")
        
        manager = RedoFallbackManager()
        
        # Test with REDO disabled
        feature_flags = {"orchestrator.redo_enabled": False}
        assert manager.is_redo_active(feature_flags) == False
        
        # Test with REDO enabled
        feature_flags = {"orchestrator.redo_enabled": True}
        assert manager.is_redo_active(feature_flags) == True
        
        # Test with no flags (defaults to False)
        assert manager.is_redo_active() == False
        
        print("✓ is_redo_active with feature flags works")
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        print("Testing circuit breaker functionality...")
        
        config = FallbackConfig(
            enable_circuit_breaker=True,
            enable_health_checks=False,  # Disable health checks for this test
            max_consecutive_failures=2,
            circuit_breaker_reset_seconds=0.1  # Short reset for testing
        )
        manager = RedoFallbackManager(config)
        
        feature_flags = {"orchestrator.redo_enabled": True}
        
        # Initially should be active
        assert manager.is_redo_active(feature_flags) == True
        
        # Record failures to trigger circuit breaker
        manager.record_orchestrator_failure(Exception("Test error 1"))
        assert manager.is_redo_active(feature_flags) == True  # Still under limit
        
        manager.record_orchestrator_failure(Exception("Test error 2"))
        assert manager.is_redo_active(feature_flags) == False  # Circuit breaker open
        
        # Wait for reset
        time.sleep(0.2)
        assert manager.is_redo_active(feature_flags) == True  # Circuit breaker reset
        
        print("✓ Circuit breaker functionality works")
    
    def test_consecutive_failures(self):
        """Test consecutive failure handling."""
        print("Testing consecutive failure handling...")
        
        config = FallbackConfig(
            max_consecutive_failures=3,
            enable_health_checks=False,  # Disable health checks for this test
            enable_circuit_breaker=False  # Disable circuit breaker for this test
        )
        manager = RedoFallbackManager(config)
        
        feature_flags = {"orchestrator.redo_enabled": True}
        
        # Record failures
        manager.record_orchestrator_failure(Exception("Error 1"))
        assert manager.health_status.consecutive_failures == 1
        assert manager.is_redo_active(feature_flags) == True
        
        manager.record_orchestrator_failure(Exception("Error 2"))
        assert manager.health_status.consecutive_failures == 2
        assert manager.is_redo_active(feature_flags) == True
        
        manager.record_orchestrator_failure(Exception("Error 3"))
        assert manager.health_status.consecutive_failures == 3
        assert manager.is_redo_active(feature_flags) == False
        
        # Record success should reset
        manager.record_success()
        assert manager.health_status.consecutive_failures == 0
        assert manager.is_redo_active(feature_flags) == True
        
        print("✓ Consecutive failure handling works")
    
    def test_health_status_tracking(self):
        """Test health status tracking."""
        print("Testing health status tracking...")
        
        manager = RedoFallbackManager()
        
        # Initially healthy
        status = manager.get_health_status()
        assert status["orchestrator_healthy"] == True
        assert status["ledger_healthy"] == True
        assert status["consecutive_failures"] == 0
        assert status["circuit_breaker_open"] == False
        
        # Record orchestrator failure
        manager.record_orchestrator_failure(Exception("Orchestrator error"))
        status = manager.get_health_status()
        assert status["orchestrator_healthy"] == False
        assert status["last_orchestrator_error"] == "Orchestrator error"
        assert status["consecutive_failures"] == 1
        
        # Record ledger failure
        manager.record_ledger_failure(Exception("Ledger error"))
        status = manager.get_health_status()
        assert status["ledger_healthy"] == False
        assert status["last_ledger_error"] == "Ledger error"
        assert status["consecutive_failures"] == 2
        
        print("✓ Health status tracking works")


class TestGlobalFunctions:
    """Test global fallback functions."""
    
    def test_is_redo_active_global(self):
        """Test global is_redo_active function."""
        print("Testing global is_redo_active function...")
        
        # Reset state
        reset_fallback_state()
        
        # Test with REDO disabled
        feature_flags = {"orchestrator.redo_enabled": False}
        assert is_redo_active(feature_flags) == False
        
        # Test with REDO enabled
        feature_flags = {"orchestrator.redo_enabled": True}
        assert is_redo_active(feature_flags) == True
        
        print("✓ Global is_redo_active function works")
    
    def test_safe_orchestrator_execution(self):
        """Test safe orchestrator execution context manager."""
        print("Testing safe orchestrator execution...")
        
        reset_fallback_state()
        
        # Mock orchestrator
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.run.return_value = Mock(spec=OrchestrationResult)
        
        query_context = QueryContext(
            query="Test query",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={}
        )
        
        feature_flags = {"orchestrator.redo_enabled": True}
        
        # Test successful execution
        with safe_orchestrator_execution(orchestrator, query_context, feature_flags) as (success, result, error):
            assert success == True
            assert result is not None
            assert error is None
            orchestrator.run.assert_called_once_with(query_context)
        
        # Test execution with REDO disabled
        feature_flags = {"orchestrator.redo_enabled": False}
        with safe_orchestrator_execution(orchestrator, query_context, feature_flags) as (success, result, error):
            assert success == False
            assert result is None
            assert error is None
            # Should not call orchestrator.run
        
        print("✓ Safe orchestrator execution works")
    
    def test_safe_orchestrator_execution_failure(self):
        """Test safe orchestrator execution with failure."""
        print("Testing safe orchestrator execution with failure...")
        
        reset_fallback_state()
        
        # Mock orchestrator that raises exception
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.run.side_effect = Exception("Orchestrator failed")
        
        query_context = QueryContext(
            query="Test query",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={}
        )
        
        feature_flags = {"orchestrator.redo_enabled": True}
        
        with safe_orchestrator_execution(orchestrator, query_context, feature_flags) as (success, result, error):
            assert success == False
            assert result is None
            assert error is not None
            assert str(error) == "Orchestrator failed"
        
        # Check that failure was recorded
        manager = get_fallback_manager()
        assert manager.health_status.consecutive_failures == 1
        assert manager.health_status.orchestrator_healthy == False
        
        print("✓ Safe orchestrator execution with failure works")
    
    def test_safe_ledger_execution(self):
        """Test safe ledger execution context manager."""
        print("Testing safe ledger execution...")
        
        reset_fallback_state()
        
        session_id = "test_session"
        message_id = "test_message"
        trace_data = {"test": "data"}
        ledger_options = LedgerOptions()
        
        feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": True}
        
        # Test successful execution
        with patch('core.fallbacks.write_ledger') as mock_write_ledger:
            with safe_ledger_execution(session_id, message_id, trace_data, ledger_options, feature_flags) as (success, error):
                assert success == True
                assert error is None
                mock_write_ledger.assert_called_once_with(session_id, message_id, trace_data, ledger_options)
        
        # Test execution with ledger disabled
        feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": False}
        with safe_ledger_execution(session_id, message_id, trace_data, ledger_options, feature_flags) as (success, error):
            assert success == False
            assert error is None
            # Should not call write_ledger
        
        print("✓ Safe ledger execution works")
    
    def test_safe_ledger_execution_failure(self):
        """Test safe ledger execution with failure."""
        print("Testing safe ledger execution with failure...")
        
        reset_fallback_state()
        
        session_id = "test_session"
        message_id = "test_message"
        trace_data = {"test": "data"}
        ledger_options = LedgerOptions()
        
        feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": True}
        
        # Test execution with ledger failure
        with patch('core.fallbacks.write_ledger', side_effect=Exception("Ledger failed")):
            with safe_ledger_execution(session_id, message_id, trace_data, ledger_options, feature_flags) as (success, error):
                assert success == False
                assert error is not None
                assert str(error) == "Ledger failed"
        
        # Check that failure was recorded
        manager = get_fallback_manager()
        assert manager.health_status.consecutive_failures == 1
        assert manager.health_status.ledger_healthy == False
        
        print("✓ Safe ledger execution with failure works")
    
    def test_execute_with_fallback(self):
        """Test comprehensive execute_with_fallback function."""
        print("Testing execute_with_fallback...")
        
        reset_fallback_state()
        
        # Mock orchestrator
        orchestrator = Mock(spec=Orchestrator)
        mock_result = Mock(spec=OrchestrationResult)
        orchestrator.run.return_value = mock_result
        
        query_context = QueryContext(
            query="Test query",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={}
        )
        
        session_id = "test_session"
        message_id = "test_message"
        trace_data = {"test": "data"}
        ledger_options = LedgerOptions()
        feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": True}
        
        # Test successful execution
        with patch('core.fallbacks.write_ledger') as mock_write_ledger:
            success, result, error = execute_with_fallback(
                orchestrator, query_context, session_id, message_id, 
                trace_data, ledger_options, feature_flags
            )
            
            assert success == True
            assert result == mock_result
            assert error is None
            orchestrator.run.assert_called_once_with(query_context)
            mock_write_ledger.assert_called_once_with(session_id, message_id, trace_data, ledger_options)
        
        print("✓ Execute with fallback works")
    
    def test_execute_with_fallback_orchestrator_failure(self):
        """Test execute_with_fallback with orchestrator failure."""
        print("Testing execute_with_fallback with orchestrator failure...")
        
        reset_fallback_state()
        
        # Mock orchestrator that fails
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.run.side_effect = Exception("Orchestrator failed")
        
        query_context = QueryContext(
            query="Test query",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={}
        )
        
        session_id = "test_session"
        message_id = "test_message"
        trace_data = {"test": "data"}
        ledger_options = LedgerOptions()
        feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": True}
        
        success, result, error = execute_with_fallback(
            orchestrator, query_context, session_id, message_id, 
            trace_data, ledger_options, feature_flags
        )
        
        assert success == False
        assert result is None
        assert error is not None
        assert str(error) == "Orchestrator failed"
        
        print("✓ Execute with fallback orchestrator failure works")
    
    def test_execute_with_fallback_ledger_failure(self):
        """Test execute_with_fallback with ledger failure."""
        print("Testing execute_with_fallback with ledger failure...")
        
        reset_fallback_state()
        
        # Mock orchestrator that succeeds
        orchestrator = Mock(spec=Orchestrator)
        mock_result = Mock(spec=OrchestrationResult)
        orchestrator.run.return_value = mock_result
        
        query_context = QueryContext(
            query="Test query",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={}
        )
        
        session_id = "test_session"
        message_id = "test_message"
        trace_data = {"test": "data"}
        ledger_options = LedgerOptions()
        feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": True}
        
        # Test with ledger failure
        with patch('core.fallbacks.write_ledger', side_effect=Exception("Ledger failed")):
            success, result, error = execute_with_fallback(
                orchestrator, query_context, session_id, message_id, 
                trace_data, ledger_options, feature_flags
            )
            
            # Orchestrator should succeed, ledger should fail but not affect overall success
            assert success == True
            assert result == mock_result
            assert error is None  # Ledger failure doesn't fail the whole operation
        
        print("✓ Execute with fallback ledger failure works")


class TestSimulationFunctions:
    """Test simulation functions for testing."""
    
    def test_simulate_db_failure(self):
        """Test database failure simulation."""
        print("Testing database failure simulation...")
        
        reset_fallback_state()
        
        # Simulate DB failure
        simulate_db_failure()
        
        manager = get_fallback_manager()
        assert manager.health_status.ledger_healthy == False
        assert manager.health_status.consecutive_failures == 1
        assert "Simulated database failure" in manager.health_status.last_ledger_error
        
        print("✓ Database failure simulation works")
    
    def test_simulate_orchestrator_failure(self):
        """Test orchestrator failure simulation."""
        print("Testing orchestrator failure simulation...")
        
        reset_fallback_state()
        
        # Simulate orchestrator failure
        simulate_orchestrator_failure()
        
        manager = get_fallback_manager()
        assert manager.health_status.orchestrator_healthy == False
        assert manager.health_status.consecutive_failures == 1
        assert "Simulated orchestrator failure" in manager.health_status.last_orchestrator_error
        
        print("✓ Orchestrator failure simulation works")
    
    def test_reset_fallback_state(self):
        """Test fallback state reset."""
        print("Testing fallback state reset...")
        
        # Get initial state
        manager_before = get_fallback_manager()
        initial_failures = manager_before.health_status.consecutive_failures
        
        # Simulate some failures
        simulate_db_failure()
        simulate_orchestrator_failure()
        
        manager_after_failures = get_fallback_manager()
        assert manager_after_failures.health_status.consecutive_failures > initial_failures
        
        # Reset state
        reset_fallback_state()
        
        manager_after_reset = get_fallback_manager()
        assert manager_after_reset.health_status.consecutive_failures == 0
        assert manager_after_reset.health_status.orchestrator_healthy == True
        assert manager_after_reset.health_status.ledger_healthy == True
        
        print("✓ Fallback state reset works")


class TestIntegrationScenarios:
    """Test integration scenarios."""
    
    def test_clean_fallback_scenario(self):
        """Test clean fallback scenario with simulated DB failure."""
        print("Testing clean fallback scenario...")
        
        reset_fallback_state()
        
        # Create a fallback manager with health checks disabled
        from core.fallbacks import RedoFallbackManager, FallbackConfig
        config = FallbackConfig(enable_health_checks=False)
        manager = RedoFallbackManager(config)
        
        # Mock orchestrator
        orchestrator = Mock(spec=Orchestrator)
        mock_result = Mock(spec=OrchestrationResult)
        orchestrator.run.return_value = mock_result
        
        query_context = QueryContext(
            query="Test query",
            session_id="test_session",
            user_id="test_user",
            role="user",
            preferences={},
            metadata={}
        )
        
        session_id = "test_session"
        message_id = "test_message"
        trace_data = {"test": "data"}
        ledger_options = LedgerOptions()
        feature_flags = {"orchestrator.redo_enabled": True, "ledger.enabled": True}
        
        # Execute with fallback - should succeed despite DB failure
        with patch('core.fallbacks.write_ledger', side_effect=Exception("Database connection failed")):
            success, result, error = execute_with_fallback(
                orchestrator, query_context, session_id, message_id, 
                trace_data, ledger_options, feature_flags
            )
            
            # Should succeed because orchestrator works
            assert success == True
            assert result == mock_result
            assert error is None
        
        print("✓ Clean fallback scenario works")
    
    def test_circuit_breaker_scenario(self):
        """Test circuit breaker scenario."""
        print("Testing circuit breaker scenario...")
        
        reset_fallback_state()
        
        config = FallbackConfig(
            enable_circuit_breaker=True,
            enable_health_checks=False,  # Disable health checks for this test
            max_consecutive_failures=2,
            circuit_breaker_reset_seconds=0.1
        )
        manager = RedoFallbackManager(config)
        
        feature_flags = {"orchestrator.redo_enabled": True}
        
        # Initially active
        assert manager.is_redo_active(feature_flags) == True
        
        # Trigger circuit breaker
        manager.record_orchestrator_failure(Exception("Error 1"))
        assert manager.is_redo_active(feature_flags) == True
        
        manager.record_orchestrator_failure(Exception("Error 2"))
        assert manager.is_redo_active(feature_flags) == False  # Circuit breaker open
        
        # Wait for reset
        time.sleep(0.2)
        assert manager.is_redo_active(feature_flags) == True  # Circuit breaker reset
        
        print("✓ Circuit breaker scenario works")


def main():
    """Run all fallback tests."""
    print("Running REDO fallback system tests...\n")
    
    try:
        # Test fallback manager
        test_manager = TestRedoFallbackManager()
        test_manager.test_initialization()
        test_manager.test_is_redo_active_with_flags()
        test_manager.test_circuit_breaker()
        test_manager.test_consecutive_failures()
        test_manager.test_health_status_tracking()
        
        # Test global functions
        test_global = TestGlobalFunctions()
        test_global.test_is_redo_active_global()
        test_global.test_safe_orchestrator_execution()
        test_global.test_safe_orchestrator_execution_failure()
        test_global.test_safe_ledger_execution()
        test_global.test_safe_ledger_execution_failure()
        test_global.test_execute_with_fallback()
        test_global.test_execute_with_fallback_orchestrator_failure()
        test_global.test_execute_with_fallback_ledger_failure()
        
        # Test simulation functions
        test_simulation = TestSimulationFunctions()
        test_simulation.test_simulate_db_failure()
        test_simulation.test_simulate_orchestrator_failure()
        test_simulation.test_reset_fallback_state()
        
        # Test integration scenarios
        test_integration = TestIntegrationScenarios()
        test_integration.test_clean_fallback_scenario()
        test_integration.test_circuit_breaker_scenario()
        
        print("\n🎉 All REDO fallback system tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())