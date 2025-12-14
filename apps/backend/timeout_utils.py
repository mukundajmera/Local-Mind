"""
Sovereign Cognitive Engine - Timeout Utilities
===============================================
Timeout enforcement for async operations.
"""

import asyncio
from typing import TypeVar, Callable, Any
from functools import wraps
from logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""
    pass


def with_timeout(seconds: float):
    """
    Decorator to enforce timeout on async functions.
    
    Args:
        seconds: Maximum execution time in seconds
        
    Example:
        ```python
        @with_timeout(30.0)
        async def slow_operation():
            await asyncio.sleep(60)  # Will raise TimeoutError
        ```
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError as e:
                logger.warning(
                    f"Operation '{func.__name__}' timed out after {seconds}s",
                    extra={"function": func.__name__, "timeout": seconds}
                )
                raise TimeoutError(
                    f"Operation '{func.__name__}' exceeded timeout of {seconds}s"
                ) from e
        
        return wrapper
    
    return decorator


async def run_with_timeout(coro, timeout: float, operation_name: str = "operation"):
    """
    Run a coroutine with a timeout.
    
    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        operation_name: Name for logging
        
    Returns:
        Result from coroutine
        
    Raises:
        TimeoutError: If operation exceeds timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as e:
        logger.warning(
            f"Operation '{operation_name}' timed out after {timeout}s",
            extra={"operation": operation_name, "timeout": timeout}
        )
        raise TimeoutError(
            f"Operation '{operation_name}' exceeded timeout of {timeout}s"
        ) from e
