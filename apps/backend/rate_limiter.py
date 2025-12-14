"""
Sovereign Cognitive Engine - Rate Limiting
===========================================
Rate limiting and backpressure management.
"""

import time
from typing import Dict, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    
    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.time()
    
    def refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on time elapsed
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        
        Returns:
            True if tokens consumed, False if insufficient
        """
        self.refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait for tokens to be available."""
        self.refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Supports per-client and global rate limiting.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: Optional[int] = None,
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Sustained rate limit
            burst_size: Maximum burst (defaults to requests_per_minute)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        
        # Per-client buckets
        self._buckets: Dict[str, RateLimitBucket] = {}
        
        # Global bucket for system-wide limiting
        self._global_bucket = RateLimitBucket(
            capacity=self.burst_size * 10,
            refill_rate=self.refill_rate * 10,
        )
    
    def _get_bucket(self, client_id: str) -> RateLimitBucket:
        """Get or create bucket for client."""
        if client_id not in self._buckets:
            self._buckets[client_id] = RateLimitBucket(
                capacity=self.burst_size,
                refill_rate=self.refill_rate,
            )
        
        return self._buckets[client_id]
    
    def check_rate_limit(self, client_id: str) -> tuple[bool, Optional[float]]:
        """
        Check if request is allowed under rate limits.
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        # Check global limit first
        if not self._global_bucket.consume():
            wait_time = self._global_bucket.get_wait_time()
            logger.warning(
                "Global rate limit exceeded",
                extra={"wait_time": wait_time}
            )
            return False, wait_time
        
        # Check per-client limit
        bucket = self._get_bucket(client_id)
        if not bucket.consume():
            wait_time = bucket.get_wait_time()
            logger.warning(
                "Client rate limit exceeded",
                extra={"client_id": client_id, "wait_time": wait_time}
            )
            return False, wait_time
        
        return True, None
    
    def cleanup_stale_buckets(self, max_age: float = 3600.0):
        """Remove buckets for clients that haven't been seen recently."""
        now = time.time()
        stale_clients = [
            client_id
            for client_id, bucket in self._buckets.items()
            if now - bucket.last_refill > max_age
        ]
        
        for client_id in stale_clients:
            del self._buckets[client_id]
        
        if stale_clients:
            logger.debug(f"Cleaned up {len(stale_clients)} stale rate limit buckets")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    Applies per-client and global rate limits.
    """
    
    def __init__(self, app, requests_per_minute: int = 60, burst_size: Optional[int] = None):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
            requests_per_minute: Rate limit per client
            burst_size: Burst allowance (defaults to rate limit)
        """
        super().__init__(app)
        self.limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
        )
        self._last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health/metrics endpoints
        if request.url.path in ["/health", "/metrics", "/"]:
            return await call_next(request)
        
        # Get client identifier (IP address)
        client_id = request.client.host if request.client else "unknown"
        
        # Check rate limit
        allowed, retry_after = self.limiter.check_rate_limit(client_id)
        
        if not allowed:
            # Return 429 Too Many Requests
            return HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after,
                }
            )
        
        # Periodic cleanup of stale buckets
        now = time.time()
        if now - self._last_cleanup > 300:  # Every 5 minutes
            self.limiter.cleanup_stale_buckets()
            self._last_cleanup = now
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.limiter.requests_per_minute)
        
        return response
