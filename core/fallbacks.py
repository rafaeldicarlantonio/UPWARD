"""
Central fallback system for REDO functionality.
"""

import logging
import time
from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

from core.types import QueryContext, OrchestrationResult
from core.orchestrator.interfaces import Orchestrator
from core.ledger import write_ledger, LedgerOptions

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    """Health status for REDO components."""
    orchestrator_healthy: bool = True
    ledger_healthy: bool = True
    last_orchestrator_error: Optional[str] = None
    last_ledger_error: Optional[str] = None
    last_health_check: float = 0.0
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3

@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""
    enable_health_checks: bool = True
    health_check_interval_seconds: float = 30.0
    max_consecutive_failures: int = 3
    fallback_timeout_seconds: float = 5.0
    enable_circuit_breaker: bool = True
    circuit_breaker_reset_seconds: float = 60.0

class RedoFallbackManager:
    """Manages fallback behavior for REDO functionality."""
    
    def __init__(self, config: FallbackConfig = None):
        self.config = config or FallbackConfig()
        self.health_status = HealthStatus()
        self._circuit_breaker_open = False
        self._circuit_breaker_opened_at = 0.0
        
    def is_redo_active(self, feature_flags: Dict[str, bool] = None) -> bool:
        """
        Central guard function to determine if REDO is active.
        
        Considers:
        - Feature flags (orchestrator.redo_enabled, ledger.enabled)
        - Health status of components
        - Circuit breaker state
        - Consecutive failure count
        
        Args:
            feature_flags: Dictionary of feature flags
            
        Returns:
            True if REDO should be active, False otherwise
        """
        if not feature_flags:
            feature_flags = {}
        
        # Check if REDO is enabled via feature flags
        orchestrator_enabled = feature_flags.get("orchestrator.redo_enabled", False)
        ledger_enabled = feature_flags.get("ledger.enabled", False)
        
        if not orchestrator_enabled:
            logger.debug("REDO inactive: orchestrator.redo_enabled=False")
            return False
        
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            logger.warning("REDO inactive: circuit breaker open")
            return False
        
        # Check health status if enabled
        if self.config.enable_health_checks:
            if not self._is_healthy():
                logger.warning("REDO inactive: health checks failed")
                return False
        
        # Check consecutive failures
        if self.health_status.consecutive_failures >= self.config.max_consecutive_failures:
            logger.warning(f"REDO inactive: {self.health_status.consecutive_failures} consecutive failures")
            return False
        
        logger.debug("REDO active: all checks passed")
        return True
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.config.enable_circuit_breaker:
            return False
        
        if not self._circuit_breaker_open:
            return False
        
        # Check if reset time has passed
        if time.time() - self._circuit_breaker_opened_at > self.config.circuit_breaker_reset_seconds:
            logger.info("Circuit breaker reset: attempting to close")
            self._circuit_breaker_open = False
            self.health_status.consecutive_failures = 0
            return False
        
        return True
    
    def _is_healthy(self) -> bool:
        """Check if components are healthy."""
        current_time = time.time()
        
        # Only check health if enough time has passed
        if current_time - self.health_status.last_health_check < self.config.health_check_interval_seconds:
            return self.health_status.orchestrator_healthy and self.health_status.ledger_healthy
        
        # Update health check time
        self.health_status.last_health_check = current_time
        
        # For now, assume healthy unless we have recent errors
        # In a real implementation, this would check actual component health
        return True
    
    def record_orchestrator_failure(self, error: Exception) -> None:
        """Record an orchestrator failure."""
        self.health_status.orchestrator_healthy = False
        self.health_status.last_orchestrator_error = str(error)
        self.health_status.consecutive_failures += 1
        
        logger.error(f"Orchestrator failure recorded: {error}")
        
        # Open circuit breaker if too many failures
        if self.health_status.consecutive_failures >= self.config.max_consecutive_failures:
            self._open_circuit_breaker()
    
    def record_ledger_failure(self, error: Exception) -> None:
        """Record a ledger failure."""
        self.health_status.ledger_healthy = False
        self.health_status.last_ledger_error = str(error)
        self.health_status.consecutive_failures += 1
        
        logger.error(f"Ledger failure recorded: {error}")
        
        # Open circuit breaker if too many failures
        if self.health_status.consecutive_failures >= self.config.max_consecutive_failures:
            self._open_circuit_breaker()
    
    def record_success(self) -> None:
        """Record a successful operation."""
        self.health_status.orchestrator_healthy = True
        self.health_status.ledger_healthy = True
        self.health_status.consecutive_failures = 0
        self.health_status.last_orchestrator_error = None
        self.health_status.last_ledger_error = None
        
        logger.debug("Success recorded: resetting failure counters")
    
    def _open_circuit_breaker(self) -> None:
        """Open the circuit breaker."""
        self._circuit_breaker_open = True
        self._circuit_breaker_opened_at = time.time()
        logger.warning("Circuit breaker opened due to consecutive failures")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return {
            "orchestrator_healthy": self.health_status.orchestrator_healthy,
            "ledger_healthy": self.health_status.ledger_healthy,
            "consecutive_failures": self.health_status.consecutive_failures,
            "circuit_breaker_open": self._circuit_breaker_open,
            "last_orchestrator_error": self.health_status.last_orchestrator_error,
            "last_ledger_error": self.health_status.last_ledger_error,
            "last_health_check": self.health_status.last_health_check
        }

# Global fallback manager instance
_fallback_manager = RedoFallbackManager()

def get_fallback_manager() -> RedoFallbackManager:
    """Get the global fallback manager instance."""
    return _fallback_manager

def is_redo_active(feature_flags: Dict[str, bool] = None) -> bool:
    """
    Central guard function to determine if REDO is active.
    
    This is the main entry point for checking if REDO functionality
    should be enabled based on feature flags and health status.
    
    Args:
        feature_flags: Dictionary of feature flags
        
    Returns:
        True if REDO should be active, False otherwise
    """
    return _fallback_manager.is_redo_active(feature_flags)

@contextmanager
def safe_orchestrator_execution(orchestrator: Orchestrator, query_context: QueryContext, 
                               feature_flags: Dict[str, bool] = None):
    """
    Context manager for safe orchestrator execution with fallback.
    
    Args:
        orchestrator: The orchestrator to execute
        query_context: The query context
        feature_flags: Feature flags dictionary
        
    Yields:
        Tuple of (success: bool, result: Optional[OrchestrationResult], error: Optional[Exception])
    """
    success = False
    result = None
    error = None
    
    try:
        # Check if REDO is active
        if not is_redo_active(feature_flags):
            logger.info("REDO inactive: skipping orchestrator execution")
            yield success, result, error
            return
        
        # Execute orchestrator
        logger.debug("Executing orchestrator")
        result = orchestrator.run(query_context)
        success = True
        
        # Record success
        _fallback_manager.record_success()
        
        logger.debug("Orchestrator execution successful")
        yield success, result, error
        
    except Exception as e:
        error = e
        logger.error(f"Orchestrator execution failed: {e}")
        
        # Record failure
        _fallback_manager.record_orchestrator_failure(e)
        
        yield success, result, error

@contextmanager
def safe_ledger_execution(session_id: str, message_id: str, trace_data: Dict[str, Any], 
                         ledger_options: LedgerOptions, feature_flags: Dict[str, bool] = None):
    """
    Context manager for safe ledger execution with fallback.
    
    Args:
        session_id: Session ID
        message_id: Message ID
        trace_data: Trace data to write
        ledger_options: Ledger options
        feature_flags: Feature flags dictionary
        
    Yields:
        Tuple of (success: bool, error: Optional[Exception])
    """
    success = False
    error = None
    
    try:
        # Check if REDO is active and ledger is enabled
        if not is_redo_active(feature_flags):
            logger.info("REDO inactive: skipping ledger execution")
            yield success, error
            return
        
        if not feature_flags.get("ledger.enabled", False):
            logger.info("Ledger disabled: skipping ledger execution")
            yield success, error
            return
        
        # Execute ledger write
        logger.debug("Writing to ledger")
        write_ledger(session_id, message_id, trace_data, ledger_options)
        success = True
        
        # Record success
        _fallback_manager.record_success()
        
        logger.debug("Ledger execution successful")
        yield success, error
        
    except Exception as e:
        error = e
        logger.error(f"Ledger execution failed: {e}")
        
        # Record failure
        _fallback_manager.record_ledger_failure(e)
        
        yield success, error

def execute_with_fallback(orchestrator: Orchestrator, query_context: QueryContext,
                         session_id: str, message_id: str, trace_data: Dict[str, Any],
                         ledger_options: LedgerOptions, feature_flags: Dict[str, bool] = None) -> Tuple[bool, Optional[OrchestrationResult], Optional[Exception]]:
    """
    Execute REDO with comprehensive fallback handling.
    
    Args:
        orchestrator: The orchestrator to execute
        query_context: The query context
        session_id: Session ID for ledger
        message_id: Message ID for ledger
        trace_data: Trace data for ledger
        ledger_options: Ledger options
        feature_flags: Feature flags dictionary
        
    Returns:
        Tuple of (orchestrator_success: bool, result: Optional[OrchestrationResult], error: Optional[Exception])
    """
    orchestrator_success = False
    result = None
    error = None
    
    try:
        # Execute orchestrator with fallback
        with safe_orchestrator_execution(orchestrator, query_context, feature_flags) as (success, orchestration_result, orchestration_error):
            orchestrator_success = success
            result = orchestration_result
            error = orchestration_error
            
            if not success:
                logger.warning("Orchestrator failed: falling back to legacy path")
                return orchestrator_success, result, error
        
        # Execute ledger with fallback (if orchestrator succeeded)
        if orchestrator_success and result:
            with safe_ledger_execution(session_id, message_id, trace_data, ledger_options, feature_flags) as (ledger_success, ledger_error):
                if not ledger_success:
                    logger.warning(f"Ledger failed but orchestrator succeeded: {ledger_error}")
                    # Don't fail the entire operation if ledger fails
        
        return orchestrator_success, result, error
        
    except Exception as e:
        logger.error(f"Unexpected error in execute_with_fallback: {e}")
        return False, None, e

def simulate_db_failure() -> None:
    """Simulate a database failure for testing."""
    logger.warning("Simulating database failure")
    _fallback_manager.record_ledger_failure(Exception("Simulated database failure"))

def simulate_orchestrator_failure() -> None:
    """Simulate an orchestrator failure for testing."""
    logger.warning("Simulating orchestrator failure")
    _fallback_manager.record_orchestrator_failure(Exception("Simulated orchestrator failure"))

def reset_fallback_state() -> None:
    """Reset the fallback state for testing."""
    global _fallback_manager
    _fallback_manager = RedoFallbackManager()
    logger.info("Fallback state reset")