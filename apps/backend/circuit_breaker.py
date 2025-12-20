"""
Sovereign Cognitive Engine - Circuit Breaker
=============================================
Circuit breaker pattern for fault tolerance and graceful degradation.
"""

import time
from enum import Enum
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
try:
    from .logging_config import get_logger
except ImportError:
    # Fallback for direct script execution
    from logging_config import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    success_threshold: int = 2  # Successes in half-open to close
    expected_exception: type = Exception


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    
    Example:
        ```python
        breaker = CircuitBreaker(name="database", failure_threshold=5)
        
        try:
            result = await breaker.call(async_db_operation)
        except CircuitBreakerOpenError:
            # Handle degraded service
            return fallback_response()
        ```
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        expected_exception: type = Exception,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Identifier for logging/metrics
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            success_threshold: Successes needed to close from half-open
            expected_exception: Exception type to track (defaults to all)
        """
        self.name = name
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            expected_exception=expected_exception,
        )
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
    
    @property
    def state(self) -> CircuitState:
        """Get current state (may transition to HALF_OPEN if timeout expired)."""
        if self._state == CircuitState.OPEN and self._should_attempt_reset():
            logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
        
        return self._state
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False
        
        return (time.time() - self._last_failure_time) >= self.config.recovery_timeout
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Result from function
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Original exception: If function fails in closed/half-open state
        """
        current_state = self.state
        
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN - refusing request"
            )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.config.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful request."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            logger.debug(
                f"Circuit breaker '{self.name}' success in HALF_OPEN "
                f"({self._success_count}/{self.config.success_threshold})"
            )
            
            if self._success_count >= self.config.success_threshold:
                logger.info(f"Circuit breaker '{self.name}' closing after recovery")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0
    
    def _on_failure(self):
        """Handle failed request."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            logger.warning(
                f"Circuit breaker '{self.name}' failed in HALF_OPEN - reopening"
            )
            self._state = CircuitState.OPEN
            self._success_count = 0
        
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                logger.error(
                    f"Circuit breaker '{self.name}' opening after "
                    f"{self._failure_count} failures"
                )
                self._state = CircuitState.OPEN
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
    
    def get_stats(self) -> dict:
        """Get current circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and refuses requests."""
    pass
