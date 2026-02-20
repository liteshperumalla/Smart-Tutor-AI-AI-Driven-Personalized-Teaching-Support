"""
Custom Exception Hierarchy
Provides structured error handling with specific exception types
"""

from typing import Optional, Dict, Any


class SmartTutorException(Exception):
    """Base exception for all Smart Tutor errors"""

    def __init__(self, message: str, code: str = "UNKNOWN_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization"""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


# Authentication & Authorization Exceptions
class AuthenticationError(SmartTutorException):
    """Base authentication error"""
    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTH_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password"""
    def __init__(self, message: str = "Invalid username or password"):
        super().__init__(message, "INVALID_CREDENTIALS")


class UserNotFoundError(AuthenticationError):
    """User does not exist"""
    def __init__(self, username: str):
        super().__init__(
            f"User not found",  # Don't reveal which username was attempted
            "USER_NOT_FOUND",
            {"attempted_at": "login"}
        )


class UserAlreadyExistsError(AuthenticationError):
    """User already exists"""
    def __init__(self, username: str):
        super().__init__(
            f"User already exists",
            "USER_EXISTS",
            {"username": username}
        )


class AccountLockedError(AuthenticationError):
    """Account is locked due to too many failed attempts"""
    def __init__(self, unlock_time: str):
        super().__init__(
            f"Account temporarily locked. Try again after {unlock_time}",
            "ACCOUNT_LOCKED",
            {"unlock_time": unlock_time}
        )


class SessionExpiredError(AuthenticationError):
    """User session has expired"""
    def __init__(self):
        super().__init__("Session expired. Please log in again", "SESSION_EXPIRED")


class PasswordValidationError(AuthenticationError):
    """Password does not meet requirements"""
    def __init__(self, requirements: list):
        super().__init__(
            f"Password does not meet requirements",
            "WEAK_PASSWORD",
            {"requirements": requirements}
        )


class TokenInvalidError(AuthenticationError):
    """Token is invalid or expired"""
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message, "INVALID_TOKEN")


class EmailNotVerifiedError(AuthenticationError):
    """Email address has not been verified"""
    def __init__(self, message: str = "Email address is not verified"):
        super().__init__(message, "EMAIL_NOT_VERIFIED")


class PasswordSetupRequiredError(AuthenticationError):
    """Password setup required after OAuth"""
    def __init__(self, message: str = "Password setup required"):
        super().__init__(message, "PASSWORD_SETUP_REQUIRED")


# Database Exceptions
class DatabaseError(SmartTutorException):
    """Base database error"""
    def __init__(self, message: str = "Database operation failed", code: str = "DB_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, details)


class DataNotFoundError(DatabaseError):
    """Requested data not found"""
    def __init__(self, entity: str, identifier: str):
        super().__init__(
            f"{entity} not found",
            "DATA_NOT_FOUND",
            {"entity": entity, "identifier": identifier}
        )


class DataSaveError(DatabaseError):
    """Failed to save data"""
    def __init__(self, entity: str, reason: str):
        super().__init__(
            f"Failed to save {entity}: {reason}",
            "SAVE_FAILED",
            {"entity": entity, "reason": reason}
        )


class DataLoadError(DatabaseError):
    """Failed to load data"""
    def __init__(self, entity: str, reason: str):
        super().__init__(
            f"Failed to load {entity}: {reason}",
            "LOAD_FAILED",
            {"entity": entity, "reason": reason}
        )


class DataCorruptionError(DatabaseError):
    """Data is corrupted or invalid"""
    def __init__(self, entity: str, reason: str):
        super().__init__(
            f"Data corruption detected in {entity}: {reason}",
            "DATA_CORRUPTED",
            {"entity": entity, "reason": reason}
        )


# Validation Exceptions
class ValidationError(SmartTutorException):
    """Base validation error"""
    def __init__(self, message: str = "Validation failed", field: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if field:
            details['field'] = field
        super().__init__(message, "VALIDATION_ERROR", details)


class InvalidInputError(ValidationError):
    """Input data is invalid"""
    def __init__(self, field: str, message: str):
        super().__init__(f"Invalid {field}: {message}", field)


class MissingFieldError(ValidationError):
    """Required field is missing"""
    def __init__(self, field: str):
        super().__init__(f"Required field missing: {field}", field)


class InvalidFileError(ValidationError):
    """Invalid file upload"""
    def __init__(self, reason: str):
        super().__init__(f"Invalid file: {reason}", details={"reason": reason})


# RAG & AI Exceptions
class RAGError(SmartTutorException):
    """Base RAG system error"""
    def __init__(self, message: str = "RAG operation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "RAG_ERROR", details)


class IndexNotFoundError(RAGError):
    """Vector index not found"""
    def __init__(self):
        super().__init__("Vector index not found or not initialized", "INDEX_NOT_FOUND")


class EmbeddingError(RAGError):
    """Failed to generate embeddings"""
    def __init__(self, reason: str):
        super().__init__(f"Embedding generation failed: {reason}", "EMBEDDING_ERROR", {"reason": reason})


class RetrievalError(RAGError):
    """Failed to retrieve relevant documents"""
    def __init__(self, reason: str):
        super().__init__(f"Document retrieval failed: {reason}", "RETRIEVAL_ERROR", {"reason": reason})


class LLMError(RAGError):
    """LLM generation error"""
    def __init__(self, reason: str):
        super().__init__(f"LLM generation failed: {reason}", "LLM_ERROR", {"reason": reason})


class LLMTimeoutError(LLMError):
    """LLM request timed out"""
    def __init__(self):
        super().__init__("LLM request timed out", "LLM_TIMEOUT")


# Rate Limiting Exceptions
class RateLimitError(SmartTutorException):
    """Rate limit exceeded"""
    def __init__(self, retry_after: int):
        super().__init__(
            f"Rate limit exceeded. Try again in {retry_after} seconds",
            "RATE_LIMIT_EXCEEDED",
            {"retry_after": retry_after}
        )


# File System Exceptions
class FileSystemError(SmartTutorException):
    """Base file system error"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "FS_ERROR", details)


class FileNotFoundError(FileSystemError):
    """File not found"""
    def __init__(self, filepath: str):
        super().__init__(f"File not found: {filepath}", "FILE_NOT_FOUND", {"filepath": filepath})


class FileAccessError(FileSystemError):
    """Cannot access file"""
    def __init__(self, filepath: str, reason: str):
        super().__init__(
            f"Cannot access file: {filepath}",
            "FILE_ACCESS_DENIED",
            {"filepath": filepath, "reason": reason}
        )


class DirectoryError(FileSystemError):
    """Directory operation failed"""
    def __init__(self, directory: str, operation: str, reason: str):
        super().__init__(
            f"Directory operation '{operation}' failed for {directory}: {reason}",
            "DIR_ERROR",
            {"directory": directory, "operation": operation, "reason": reason}
        )


# Configuration Exceptions
class ConfigurationError(SmartTutorException):
    """Configuration error"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIG_ERROR", details)


class MissingConfigError(ConfigurationError):
    """Required configuration is missing"""
    def __init__(self, config_key: str):
        super().__init__(
            f"Required configuration missing: {config_key}",
            "CONFIG_MISSING",
            {"config_key": config_key}
        )


# External Service Exceptions
class ExternalServiceError(SmartTutorException):
    """External service error"""
    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details['service'] = service
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details)


class WebSearchError(ExternalServiceError):
    """Web search failed"""
    def __init__(self, reason: str):
        super().__init__("WebSearch", f"Web search failed: {reason}", {"reason": reason})


class EmailError(ExternalServiceError):
    """Email sending failed"""
    def __init__(self, reason: str):
        super().__init__("Email", f"Email sending failed: {reason}", {"reason": reason})


class OAuthError(ExternalServiceError):
    """OAuth authentication failed"""
    def __init__(self, provider: str, reason: str):
        super().__init__("OAuth", f"OAuth with {provider} failed: {reason}",
                        {"provider": provider, "reason": reason})
