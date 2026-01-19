"""
Enhanced Logging System
Provides structured logging with context, log levels, and proper formatting
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler
from .config import config


class JsonFormatter(logging.Formatter):
    """Custom formatter for JSON logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields from extra parameter
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Custom formatter for human-readable text logging"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


class ContextLogger:
    """Logger with context support for user_id, session_id, etc."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}

    def set_context(self, **kwargs):
        """Set context for all subsequent log messages"""
        self.context.update(kwargs)

    def clear_context(self):
        """Clear all context"""
        self.context.clear()

    def _log(self, level: int, msg: str, extra_data: Optional[Dict[str, Any]] = None, **kwargs):
        """Internal logging method with context"""
        # Extract exc_info if present (it's a logging kwarg, not extra)
        exc_info = kwargs.pop('exc_info', False)

        extra = {**self.context}
        if extra_data:
            extra['extra_data'] = extra_data

        # Add context as extra fields
        for key, value in extra.items():
            kwargs.setdefault(key, value)

        self.logger.log(level, msg, extra=kwargs, exc_info=exc_info)

    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        self._log(logging.DEBUG, msg, extra)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message"""
        self._log(logging.INFO, msg, extra)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        self._log(logging.WARNING, msg, extra)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log error message"""
        self._log(logging.ERROR, msg, extra, exc_info=exc_info)

    def critical(self, msg: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log critical message"""
        self._log(logging.CRITICAL, msg, extra, exc_info=exc_info)

    def exception(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        """Log exception with traceback"""
        self._log(logging.ERROR, msg, extra, exc_info=True)


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> None:
    """
    Setup logging configuration for the application

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        log_format: Format type ('json' or 'text')
    """
    log_level = log_level or config.LOG_LEVEL
    log_file = log_file or config.LOG_FILE
    log_format = log_format or config.LOG_FORMAT

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set root logger level
    root_logger.setLevel(numeric_level)

    # Choose formatter based on format type
    if log_format.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter()

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log file is specified)
    if log_file:
        try:
            # Create log directory if it doesn't exist
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Rotating file handler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=config.LOG_MAX_BYTES,
                backupCount=config.LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.error(f"Failed to setup file logging: {e}")

    # Log initial message
    root_logger.info(f"Logging initialized - Level: {log_level}, Format: {log_format}")


def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        ContextLogger instance
    """
    return ContextLogger(name)


# Module-level logger instances for common components
auth_logger = get_logger("smart_tutor.auth")
db_logger = get_logger("smart_tutor.database")
rag_logger = get_logger("smart_tutor.rag")
api_logger = get_logger("smart_tutor.api")
security_logger = get_logger("smart_tutor.security")


class LoggerAdapter:
    """Adapter for transitioning from print/logging to structured logger"""

    def __init__(self, logger: ContextLogger):
        self.logger = logger

    def __call__(self, msg: str, level: str = "info"):
        """Allow logger to be called like print()"""
        getattr(self.logger, level.lower())(msg)


# Initialize logging on module import
setup_logging()
