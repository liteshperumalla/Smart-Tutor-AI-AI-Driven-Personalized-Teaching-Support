"""
Input Validation and Security Utilities
Provides validation for user inputs, passwords, files, and security checks
"""

import re
import bleach
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
        """Validate username format and normalize common characters"""
        if not isinstance(v, str):
            raise ValueError("Username must be a string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Username cannot be empty")
        normalized = re.sub(r'\s+', '_', cleaned)
        if not re.match(r'^[a-zA-Z0-9_.@-]+$', normalized):
            raise ValueError('Username can only contain letters, numbers, underscores, hyphens, periods, or @ symbols')
        return normalized

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
        """Validate query and strip any HTML/script content.

        Blocklist matching alone is trivially bypassable (e.g. `<img onerror =x>`
        with whitespace, SVG event handlers, data URIs). We let `bleach` strip
        all HTML tags after a lightweight blocklist check, so the downstream
        RAG/LLM pipeline never sees executable markup even if the model echoes
        the input back into a browser context.
        """
        dangerous_patterns = ['<script', 'javascript:', 'onerror', 'onload', 'onclick', '<iframe', '<embed', '<object']
        if any(pattern in v.lower() for pattern in dangerous_patterns):
            raise ValueError('Query contains potentially dangerous content')
        sanitized = bleach.clean(v, tags=[], attributes={}, protocols=[], strip=True).strip()
        # Reject input that was entirely HTML — bleach strips it to '' and the
        # downstream LLM/RAG path can't do anything useful with an empty query.
        if not sanitized:
            raise ValueError('Query must not be empty')
        return sanitized


# Curated common-passwords list (subset of HaveIBeenPwned top entries plus
# permutations our users have actually tried, captured from auth telemetry).
# Lowercase comparison; entries with leading/trailing whitespace are excluded.
COMMON_WEAK_PASSWORDS = frozenset({
    "password", "password1", "password!", "password123", "password1234", "password12",
    "passw0rd", "p@ssword", "p@ssw0rd", "p@$$w0rd", "qwerty", "qwerty123", "qwertyuiop",
    "12345678", "123456789", "1234567890", "1234567", "111111", "000000", "654321",
    "121212", "112233", "abcdef", "abc12345", "abc123", "letmein", "letmein123",
    "welcome", "welcome1", "welcome123", "admin", "admin123", "administrator",
    "root", "toor", "test", "test123", "guest", "guest123", "user", "user123",
    "login", "iloveyou", "iloveyou1", "iloveyou123", "monkey", "dragon", "master",
    "shadow", "sunshine", "princess", "football", "baseball", "basketball",
    "superman", "batman", "trustno1", "freedom", "whatever", "qazwsx", "asdfgh",
    "asdfghjkl", "1q2w3e", "1q2w3e4r", "1q2w3e4r5t", "zaq12wsx", "passpass",
    "changeme", "changeme123", "secret", "secret123", "starwars", "pokemon",
    "ninja", "azerty", "michael", "computer", "internet", "samsung", "google",
    "facebook", "tinkle", "killer", "qwerty1", "qwerty12", "asdf", "asdf1234",
    "smarttutor", "smartaitutor", "smarttutor123",
})


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

        # Check for common weak passwords. The HIBP top list has 10k+ entries but
        # embedding all of them here bloats the wheel; the curated set below covers
        # the most common variants typically seen in credential stuffing dumps. For
        # broader coverage, callers can wire in HaveIBeenPwned's k-anonymity API.
        if password.lower() in COMMON_WEAK_PASSWORDS:
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
        # Use bleach to sanitize HTML properly, stripping all tags
        return bleach.clean(text, tags=[], attributes={}, protocols=[], strip=True)


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
