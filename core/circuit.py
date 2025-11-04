#!/usr/bin/env python3
"""
core/circuit.py — Circuit breaker implementation with rolling failure counts.

Provides circuit breaker pattern for external services (Pinecone, reviewer LLM):
- Tracks consecutive failures
- Opens after threshold exceeded
- Half-open state after cooldown
- Prevents spamming failed services
"""

import time
from enum import Enum
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass, field
from threading import Lock

from core.metrics import increment_counter, observe_histogram


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests allowed
    OPEN = "open"          # Too many failures, requests blocked
    HALF_OPEN = "half_open"  # Cooldown expired, testing with probe


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    name: str
    failure_threshold: int = 5          # Failures before opening
    cooldown_seconds: float = 60.0      # Time before half-open
    success_threshold: int = 2          # Successes to close from half-open
    timeout_seconds: Optional[float] = None  # Optional timeout for calls


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    opened_at: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)


class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    States:
    - CLOSED: Normal operation, all calls allowed
    - OPEN: Too many failures, all calls rejected immediately
    - HALF_OPEN: Cooldown expired, single probe call allowed
    
    Transitions:
    - CLOSED → OPEN: After failure_threshold consecutive failures
    - OPEN → HALF_OPEN: After cooldown_seconds elapsed
    - HALF_OPEN → CLOSED: After success_threshold consecutive successes
    - HALF_OPEN → OPEN: On any failure during half-open
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        """Initialize circuit breaker with configuration."""
        self.config = config
        self.stats = CircuitBreakerStats()
        self._lock = Lock()
        self._half_open_probe_in_flight = False
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from the function call
        """
        # Check if we can make the call
        if not self.can_execute():
            self._record_rejected()
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.config.name}' is OPEN. "
                f"Last opened at {self.stats.opened_at}, "
                f"cooldown: {self.config.cooldown_seconds}s"
            )
        
        # Mark probe in flight for half-open state
        is_probe = False
        with self._lock:
            if self.stats.state == CircuitState.HALF_OPEN and not self._half_open_probe_in_flight:
                self._half_open_probe_in_flight = True
                is_probe = True
        
        try:
            start_time = time.time()
            
            # Execute the function
            result = func(*args, **kwargs)
            
            # Record success
            elapsed = time.time() - start_time
            self._record_success(elapsed)
            
            # Clear probe flag
            if is_probe:
                with self._lock:
                    self._half_open_probe_in_flight = False
            
            return result
            
        except Exception as e:
            # Record failure
            elapsed = time.time() - start_time
            self._record_failure(elapsed, e)
            
            # Clear probe flag
            if is_probe:
                with self._lock:
                    self._half_open_probe_in_flight = False
            
            raise
    
    def can_execute(self) -> bool:
        """
        Check if circuit breaker allows execution.
        
        Returns:
            True if call is allowed, False if blocked
        """
        with self._lock:
            current_state = self.stats.state
            
            # CLOSED: Always allow
            if current_state == CircuitState.CLOSED:
                return True
            
            # OPEN: Check if cooldown expired
            if current_state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                    return True
                return False
            
            # HALF_OPEN: Allow if no probe in flight
            if current_state == CircuitState.HALF_OPEN:
                return not self._half_open_probe_in_flight
            
            return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.stats.opened_at is None:
            return True
        
        elapsed = time.time() - self.stats.opened_at
        return elapsed >= self.config.cooldown_seconds
    
    def _record_success(self, elapsed: float):
        """Record successful call."""
        with self._lock:
            self.stats.success_count += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = time.time()
            
            current_state = self.stats.state
            
            # Transition logic based on state
            if current_state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to_closed()
            
            # Record metrics
            increment_counter("circuit_breaker.success", labels={
                "breaker": self.config.name,
                "state": current_state.value
            })
            observe_histogram("circuit_breaker.call_duration_ms", elapsed * 1000, labels={
                "breaker": self.config.name,
                "result": "success"
            })
    
    def _record_failure(self, elapsed: float, error: Exception):
        """Record failed call."""
        with self._lock:
            self.stats.failure_count += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()
            
            current_state = self.stats.state
            
            # Transition logic based on state
            if current_state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to_open()
            
            elif current_state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self._transition_to_open()
            
            # Record metrics
            increment_counter("circuit_breaker.failure", labels={
                "breaker": self.config.name,
                "state": current_state.value,
                "error_type": type(error).__name__
            })
            observe_histogram("circuit_breaker.call_duration_ms", elapsed * 1000, labels={
                "breaker": self.config.name,
                "result": "failure"
            })
    
    def _record_rejected(self):
        """Record rejected call (circuit open)."""
        increment_counter("circuit_breaker.rejected", labels={
            "breaker": self.config.name
        })
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.stats.state = CircuitState.OPEN
        self.stats.opened_at = time.time()
        self.stats.last_state_change = time.time()
        self.stats.consecutive_successes = 0
        
        increment_counter("circuit_breaker.state_change", labels={
            "breaker": self.config.name,
            "to_state": "open"
        })
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.last_state_change = time.time()
        self.stats.consecutive_failures = 0
        self.stats.consecutive_successes = 0
        self._half_open_probe_in_flight = False
        
        increment_counter("circuit_breaker.state_change", labels={
            "breaker": self.config.name,
            "to_state": "half_open"
        })
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.stats.state = CircuitState.CLOSED
        self.stats.last_state_change = time.time()
        self.stats.consecutive_failures = 0
        self.stats.opened_at = None
        
        increment_counter("circuit_breaker.state_change", labels={
            "breaker": self.config.name,
            "to_state": "closed"
        })
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to_closed()
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes = 0
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        with self._lock:
            return self.stats.state
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.config.name,
                "state": self.stats.state.value,
                "consecutive_failures": self.stats.consecutive_failures,
                "consecutive_successes": self.stats.consecutive_successes,
                "total_failures": self.stats.failure_count,
                "total_successes": self.stats.success_count,
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
                "opened_at": self.stats.opened_at,
                "last_state_change": self.stats.last_state_change,
                "failure_threshold": self.config.failure_threshold,
                "cooldown_seconds": self.config.cooldown_seconds
            }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejects a call."""
    pass


# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = Lock()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.
    
    Args:
        name: Circuit breaker name
        config: Configuration (only used when creating new breaker)
        
    Returns:
        CircuitBreaker instance
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            if config is None:
                # Create default config
                config = CircuitBreakerConfig(name=name)
            _circuit_breakers[name] = CircuitBreaker(config)
        
        return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """Get all registered circuit breakers."""
    with _registry_lock:
        return dict(_circuit_breakers)


def reset_all_circuit_breakers():
    """Reset all circuit breakers (useful for testing)."""
    with _registry_lock:
        for breaker in _circuit_breakers.values():
            breaker.reset()
        _circuit_breakers.clear()
