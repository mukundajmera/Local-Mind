"""
Sovereign Cognitive Engine - Logging Configuration
===================================================
Centralized structlog setup for production-ready logging.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application-level context to all log entries."""
    event_dict["app"] = "local-mind"
    event_dict["service"] = "backend"
    return event_dict


def sanitize_event(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Sanitize sensitive data from logs.
    
    Redacts passwords, API keys, and other sensitive information.
    """
    sensitive_keys = {
        "password", "api_key", "secret", "token", "authorization",
        "neo4j_password", "milvus_password", "redis_password"
    }
    
    def _sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary values."""
        sanitized = {}
        for key, value in d.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive terms
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = _sanitize_dict(value)
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate very long strings (e.g., full chunk text)
                sanitized[key] = value[:100] + "...[truncated]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    # Sanitize event_dict itself
    return _sanitize_dict(event_dict)


def configure_logging(environment: str = "development") -> None:
    """
    Configure structlog for the application.
    
    Args:
        environment: "development" for console output, "production" for JSON
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_app_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        sanitize_event,
    ]
    
    if environment == "production":
        # JSON output for production (easier to parse)
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Pretty console output for development
        processors = shared_processors + [
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
