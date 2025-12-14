"""
Unit Tests - Circuit Breaker
=============================
Test circuit breaker fault tolerance patterns.
"""

import pytest
import asyncio
from apps.backend.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
)


class TestCircuitBreaker:
    """Test circuit breaker state machine and fault handling."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_circuit_starts_closed(self):
        """Circuit breaker should start in CLOSED state."""
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_call_keeps_closed(self):
        """Successful calls should keep circuit CLOSED."""
        breaker = CircuitBreaker(name="test")
        
        async def success():
            return "ok"
        
        result = await breaker.call(success)
        assert result == "ok"
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_failures_open_circuit(self):
        """Circuit should open after threshold failures."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)
        
        async def failing():
            raise Exception("Service down")
        
        # Fail 3 times to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing)
        
        assert breaker.state == CircuitState.OPEN
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_circuit_rejects_requests(self):
        """OPEN circuit should reject requests immediately."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)
        
        async def failing():
            raise Exception("Service down")
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing)
        
        # Next request should be rejected without calling function
        async def should_not_run():
            pytest.fail("Function should not be called when circuit is open")
        
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(should_not_run)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms for testing
        )
        
        async def failing():
            raise Exception("Service down")
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Circuit should now be HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Successful calls in HALF_OPEN should close circuit."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        
        async def failing():
            raise Exception("Service down")
        
        async def success():
            return "ok"
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing)
        
        # Wait for recovery
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Succeed twice to close
        await breaker.call(success)
        await breaker.call(success)
        
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Failure in HALF_OPEN should reopen circuit."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
        )
        
        async def failing():
            raise Exception("Service down")
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing)
        
        # Wait for recovery
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Fail again - should reopen
        with pytest.raises(Exception):
            await breaker.call(failing)
        
        assert breaker.state == CircuitState.OPEN
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_manual_reset(self):
        """Manual reset should close circuit."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)
        
        async def failing():
            raise Exception("Service down")
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing)
        
        assert breaker.state == CircuitState.OPEN
        
        # Manual reset
        breaker.reset()
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Stats should reflect circuit breaker state."""
        breaker = CircuitBreaker(name="test-service", failure_threshold=3)
        
        stats = breaker.get_stats()
        
        assert stats["name"] == "test-service"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_resets_failure_count_in_closed(self):
        """Success in CLOSED should reset failure count."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        
        async def failing():
            raise Exception("Transient error")
        
        async def success():
            return "ok"
        
        # Fail twice (not enough to open)
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing)
        
        assert breaker._failure_count == 2
        
        # Success should reset
        await breaker.call(success)
        
        assert breaker._failure_count == 0
        assert breaker.state == CircuitState.CLOSED
