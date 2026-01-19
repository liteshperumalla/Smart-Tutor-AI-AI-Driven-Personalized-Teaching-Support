"""
Security Event Logging

Centralized logging for security-related events to aid in:
- Incident detection
- Forensic analysis
- Compliance reporting
- Anomaly detection

All security events are logged with structured data for easy parsing and analysis.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum

# Configure security logger
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)

# Add file handler for security events
security_handler = logging.FileHandler("logs/security_events.log")
security_handler.setLevel(logging.INFO)

# Use JSON formatter for structured logging
class SecurityLogFormatter(logging.Formatter):
    """Custom formatter that outputs JSON for easy parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "event_type": getattr(record, "event_type", "unknown"),
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data)


security_handler.setFormatter(SecurityLogFormatter())
security_logger.addHandler(security_handler)


class SecurityEventType(str, Enum):
    """Types of security events to log."""

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_FAILED_INVALID_CREDENTIALS = "login_failed_invalid_credentials"
    LOGIN_FAILED_ACCOUNT_LOCKED = "login_failed_account_locked"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"

    # Account management
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    ACCOUNT_DELETED = "account_deleted"

    # Password events
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_RESET_FAILED = "password_reset_failed"

    # Authorization events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    FORBIDDEN_ACCESS = "forbidden_access"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"

    # Security violations
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CSRF_VALIDATION_FAILED = "csrf_validation_failed"
    INVALID_TOKEN = "invalid_token"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # Data access
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"

    # System events
    SECURITY_CONFIGURATION_CHANGED = "security_configuration_changed"
    SECURITY_SCAN_COMPLETED = "security_scan_completed"


class SecurityLogger:
    """Centralized security event logger."""

    @staticmethod
    def log_event(
        event_type: SecurityEventType,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "INFO"
    ):
        """
        Log a security event with structured data.

        Args:
            event_type: Type of security event
            username: Username associated with the event
            ip_address: IP address of the request
            user_agent: User agent string
            success: Whether the action was successful
            details: Additional details about the event
            severity: Log level (INFO, WARNING, ERROR)
        """
        extra_data = {
            "event_type": event_type.value,
            "username": username or "anonymous",
            "ip_address": ip_address or "unknown",
            "user_agent": user_agent or "unknown",
            "success": success,
        }

        if details:
            extra_data["details"] = details

        # Determine log level based on event type and success
        if severity == "ERROR" or not success:
            log_level = logging.ERROR
        elif severity == "WARNING" or event_type in [
            SecurityEventType.UNAUTHORIZED_ACCESS,
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            SecurityEventType.CSRF_VALIDATION_FAILED,
        ]:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO

        # Create log record with extra data
        security_logger.log(
            log_level,
            f"{event_type.value}: {username or 'anonymous'} from {ip_address or 'unknown'}",
            extra={"extra_data": extra_data}
        )

    @staticmethod
    def log_login_success(username: str, ip_address: str, user_agent: str = None):
        """Log successful login."""
        SecurityLogger.log_event(
            SecurityEventType.LOGIN_SUCCESS,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )

    @staticmethod
    def log_login_failed(username: str, ip_address: str, reason: str = "invalid_credentials", user_agent: str = None):
        """Log failed login attempt."""
        if reason == "account_locked":
            event_type = SecurityEventType.LOGIN_FAILED_ACCOUNT_LOCKED
        else:
            event_type = SecurityEventType.LOGIN_FAILED_INVALID_CREDENTIALS

        SecurityLogger.log_event(
            event_type,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details={"reason": reason},
            severity="WARNING"
        )

    @staticmethod
    def log_logout(username: str, ip_address: str):
        """Log user logout."""
        SecurityLogger.log_event(
            SecurityEventType.LOGOUT,
            username=username,
            ip_address=ip_address,
            success=True
        )

    @staticmethod
    def log_password_changed(username: str, ip_address: str):
        """Log password change."""
        SecurityLogger.log_event(
            SecurityEventType.PASSWORD_CHANGED,
            username=username,
            ip_address=ip_address,
            success=True,
            severity="WARNING"  # Important event to track
        )

    @staticmethod
    def log_password_reset_requested(username: str, ip_address: str):
        """Log password reset request."""
        SecurityLogger.log_event(
            SecurityEventType.PASSWORD_RESET_REQUESTED,
            username=username,
            ip_address=ip_address,
            success=True,
            severity="WARNING"
        )

    @staticmethod
    def log_unauthorized_access(username: str, ip_address: str, resource: str, user_agent: str = None):
        """Log unauthorized access attempt."""
        SecurityLogger.log_event(
            SecurityEventType.UNAUTHORIZED_ACCESS,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details={"resource": resource},
            severity="WARNING"
        )

    @staticmethod
    def log_forbidden_access(username: str, ip_address: str, resource: str, user_agent: str = None):
        """Log forbidden access attempt (authenticated but not authorized)."""
        SecurityLogger.log_event(
            SecurityEventType.FORBIDDEN_ACCESS,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details={"resource": resource},
            severity="WARNING"
        )

    @staticmethod
    def log_account_locked(username: str, ip_address: str, reason: str = "too_many_failed_attempts"):
        """Log account being locked."""
        SecurityLogger.log_event(
            SecurityEventType.ACCOUNT_LOCKED,
            username=username,
            ip_address=ip_address,
            success=True,
            details={"reason": reason},
            severity="WARNING"
        )

    @staticmethod
    def log_rate_limit_exceeded(username: str, ip_address: str, endpoint: str):
        """Log rate limit being exceeded."""
        SecurityLogger.log_event(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            username=username,
            ip_address=ip_address,
            success=False,
            details={"endpoint": endpoint},
            severity="WARNING"
        )

    @staticmethod
    def log_csrf_failed(ip_address: str, endpoint: str, user_agent: str = None):
        """Log CSRF validation failure."""
        SecurityLogger.log_event(
            SecurityEventType.CSRF_VALIDATION_FAILED,
            username=None,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details={"endpoint": endpoint},
            severity="WARNING"
        )

    @staticmethod
    def log_account_created(username: str, ip_address: str):
        """Log new account creation."""
        SecurityLogger.log_event(
            SecurityEventType.ACCOUNT_CREATED,
            username=username,
            ip_address=ip_address,
            success=True
        )

    @staticmethod
    def log_account_deleted(username: str, ip_address: str, deleted_by: str):
        """Log account deletion."""
        SecurityLogger.log_event(
            SecurityEventType.ACCOUNT_DELETED,
            username=username,
            ip_address=ip_address,
            success=True,
            details={"deleted_by": deleted_by},
            severity="WARNING"
        )

    @staticmethod
    def log_suspicious_activity(username: str, ip_address: str, description: str, user_agent: str = None):
        """Log suspicious activity."""
        SecurityLogger.log_event(
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details={"description": description},
            severity="ERROR"
        )


# Helper function to get client IP from request
def get_client_ip(request) -> str:
    """
    Extract client IP address from request.

    Checks X-Forwarded-For header (for proxies/load balancers) first,
    then falls back to direct client IP.

    Args:
        request: FastAPI Request object

    Returns:
        str: Client IP address
    """
    # Check X-Forwarded-For header (proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP if multiple proxies
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


# Helper function to get user agent
def get_user_agent(request) -> str:
    """
    Extract user agent from request.

    Args:
        request: FastAPI Request object

    Returns:
        str: User agent string
    """
    return request.headers.get("User-Agent", "unknown")
