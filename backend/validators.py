"""
Input Validation and Security Utilities
Provides validation for user inputs, passwords, files, and security checks
"""

import re
import os
from typing import Optional, List, Tuple
from pathlib import Path
from pydantic import BaseModel, Field, validator, EmailStr
from .config import config
from .exceptions import ValidationError, InvalidInputError, PasswordValidationError, InvalidFileError


# Pydantic Models for Validation
class UserRegistration(BaseModel):
    """User registration data validation"""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=config.PASSWORD_MIN_LENGTH)
    confirm_password: str

    @validator('username')
    def validate_username(cls, v):
        """Validate username format"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Ensure passwords match"""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class UserLogin(BaseModel):
    """User login data validation"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1)


class ProfileUpdate(BaseModel):
    """User profile update validation"""
    display_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)

    @validator('phone_number')
    def validate_phone(cls, v):
        """Validate phone number format"""
        if v and not re.match(r'^\+?[0-9\s\-\(\)]{7,20}$', v):
            raise ValueError('Invalid phone number format')
        return v


class ChatMessage(BaseModel):
    """Chat message validation"""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None


class QueryInput(BaseModel):
    """Query input validation"""
    query: str = Field(..., min_length=1, max_length=2000)

    @validator('query')
    def validate_query(cls, v):
        """Validate query for malicious content"""
        # Basic XSS prevention
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']
        if any(pattern in v.lower() for pattern in dangerous_patterns):
            raise ValueError('Query contains potentially dangerous content')
        return v.strip()


# Password Validation
class PasswordValidator:
    """Password strength validation"""

    @staticmethod
    def validate_password(password: str) -> Tuple[bool, List[str]]:
        """
        Validate password against security requirements

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []

        # Check minimum length
        if len(password) < config.PASSWORD_MIN_LENGTH:
            violations.append(f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters long")

        # Check for uppercase letter
        if config.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            violations.append("Password must contain at least one uppercase letter")

        # Check for lowercase letter
        if config.PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            violations.append("Password must contain at least one lowercase letter")

        # Check for digit
        if config.PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
            violations.append("Password must contain at least one digit")

        # Check for special character
        if config.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            violations.append("Password must contain at least one special character")

        # Check for common weak passwords
        weak_passwords = ['password', '12345678', 'qwerty', 'abc123', 'password123', 'admin']
        if password.lower() in weak_passwords:
            violations.append("Password is too common and easily guessable")

        return len(violations) == 0, violations

    @staticmethod
    def validate_or_raise(password: str) -> None:
        """Validate password or raise exception"""
        is_valid, violations = PasswordValidator.validate_password(password)
        if not is_valid:
            raise PasswordValidationError(violations)


# Path Sanitization
class PathValidator:
    """Path validation and sanitization to prevent path traversal attacks"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove any directory components
        filename = os.path.basename(filename)

        # Remove dangerous characters
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')

        # Ensure filename is not empty after sanitization
        if not filename:
            filename = "unnamed_file"

        return filename

    @staticmethod
    def sanitize_path_component(component: str) -> str:
        """
        Sanitize a path component (directory or file name)

        Args:
            component: Path component to sanitize

        Returns:
            Sanitized component
        """
        # Remove path separators and dangerous characters
        component = re.sub(r'[/\\<>:"|?*\x00-\x1f]', '_', component)

        # Remove leading/trailing dots and spaces
        component = component.strip('. ')

        # Prevent directory traversal
        if component in ('..', '.'):
            component = '_'

        return component

    @staticmethod
    def validate_path(path: str, base_dir: Optional[str] = None) -> str:
        """
        Validate path is within allowed directory

        Args:
            path: Path to validate
            base_dir: Base directory that path must be within

        Returns:
            Resolved absolute path

        Raises:
            InvalidInputError: If path is outside base directory
        """
        path = Path(path).resolve()

        if base_dir:
            base_dir = Path(base_dir).resolve()
            try:
                path.relative_to(base_dir)
            except ValueError:
                raise InvalidInputError("path", "Path is outside allowed directory")

        return str(path)


# File Upload Validation
class FileValidator:
    """File upload validation"""

    @staticmethod
    def validate_file_size(file_size: int, max_size: Optional[int] = None) -> None:
        """
        Validate file size

        Args:
            file_size: Size of file in bytes
            max_size: Maximum allowed size in bytes

        Raises:
            InvalidFileError: If file is too large
        """
        max_size = max_size or config.MAX_UPLOAD_SIZE
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise InvalidFileError(f"File size exceeds maximum allowed size of {max_mb:.1f}MB")

    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: Optional[List[str]] = None) -> None:
        """
        Validate file extension

        Args:
            filename: Name of the file
            allowed_extensions: List of allowed extensions (with dots)

        Raises:
            InvalidFileError: If extension is not allowed
        """
        allowed_extensions = allowed_extensions or config.ALLOWED_EXTENSIONS
        ext = os.path.splitext(filename)[1].lower()

        if ext not in allowed_extensions:
            raise InvalidFileError(
                f"File type {ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )

    @staticmethod
    def validate_file(filename: str, file_size: int,
                     allowed_extensions: Optional[List[str]] = None,
                     max_size: Optional[int] = None) -> str:
        """
        Validate file upload

        Args:
            filename: Original filename
            file_size: Size of file in bytes
            allowed_extensions: List of allowed extensions
            max_size: Maximum file size in bytes

        Returns:
            Sanitized filename

        Raises:
            InvalidFileError: If file validation fails
        """
        # Validate extension
        FileValidator.validate_file_extension(filename, allowed_extensions)

        # Validate size
        FileValidator.validate_file_size(file_size, max_size)

        # Sanitize filename
        sanitized = PathValidator.sanitize_filename(filename)

        return sanitized


# SQL Injection Prevention (for future database integration)
class SQLValidator:
    """SQL injection prevention utilities"""

    @staticmethod
    def sanitize_sql_identifier(identifier: str) -> str:
        """
        Sanitize SQL identifier (table/column name)

        Args:
            identifier: SQL identifier

        Returns:
            Sanitized identifier
        """
        # Only allow alphanumeric and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', identifier):
            raise InvalidInputError("sql_identifier", "Invalid SQL identifier")
        return identifier


# XSS Prevention
class XSSValidator:
    """Cross-site scripting prevention"""

    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Basic HTML sanitization (removes dangerous tags)

        Args:
            text: Input text

        Returns:
            Sanitized text
        """
        # Remove script tags and their content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove event handlers
        text = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*on\w+\s*=\s*\S+', '', text, flags=re.IGNORECASE)

        # Remove javascript: protocol
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)

        return text


# Rate Limiting Validator
class RateLimitValidator:
    """Rate limiting validation utilities"""

    def __init__(self):
        self.request_counts: dict = {}

    def check_rate_limit(self, identifier: str, max_requests: int, period: int) -> Tuple[bool, int]:
        """
        Check if rate limit is exceeded

        Args:
            identifier: Unique identifier (user_id, IP, etc.)
            max_requests: Maximum requests allowed
            period: Time period in seconds

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        from datetime import datetime, timedelta

        now = datetime.now()

        if identifier not in self.request_counts:
            self.request_counts[identifier] = []

        # Remove old requests outside the period
        cutoff = now - timedelta(seconds=period)
        self.request_counts[identifier] = [
            req_time for req_time in self.request_counts[identifier]
            if req_time > cutoff
        ]

        # Check if limit exceeded
        if len(self.request_counts[identifier]) >= max_requests:
            oldest = self.request_counts[identifier][0]
            retry_after = int((oldest + timedelta(seconds=period) - now).total_seconds())
            return False, retry_after

        # Add current request
        self.request_counts[identifier].append(now)
        return True, 0
