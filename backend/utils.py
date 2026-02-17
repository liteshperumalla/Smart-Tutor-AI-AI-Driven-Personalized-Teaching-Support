"""
Backend Utilities
Common utility functions for backend operations
"""

import os
import hashlib
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from pathlib import Path

from .logger import get_logger
from .config import config
from .validators import PathValidator

logger = get_logger(__name__)


class FileUtils:
    """File operation utilities"""

    @staticmethod
    def ensure_directory(directory: str) -> None:
        """
        Ensure directory exists

        Args:
            directory: Directory path
        """
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            raise

    @staticmethod
    def get_file_hash(filepath: str, algorithm: str = "md5") -> str:
        """
        Get file hash

        Args:
            filepath: Path to file
            algorithm: Hash algorithm (md5, sha1, sha256)

        Returns:
            File hash as hex string
        """
        hash_func = hashlib.new(algorithm)
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash file {filepath}: {e}")
            raise

    @staticmethod
    def get_file_mimetype(filepath: str) -> Optional[str]:
        """
        Get file MIME type

        Args:
            filepath: Path to file

        Returns:
            MIME type string or None
        """
        mime_type, _ = mimetypes.guess_type(filepath)
        return mime_type

    @staticmethod
    def get_file_size(filepath: str) -> int:
        """
        Get file size in bytes

        Args:
            filepath: Path to file

        Returns:
            File size in bytes
        """
        return os.path.getsize(filepath)

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    @staticmethod
    def safe_delete(filepath: str) -> bool:
        """
        Safely delete a file

        Args:
            filepath: Path to file

        Returns:
            True if deleted, False otherwise
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Deleted file: {filepath}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {filepath}: {e}")
            return False

    @staticmethod
    def get_user_data_path(user_id: str, *subdirs: str) -> str:
        """
        Get path to user data directory

        Args:
            user_id: User identifier
            *subdirs: Optional subdirectories

        Returns:
            Full path to user data directory
        """
        sanitized_user = PathValidator.sanitize_path_component(user_id)
        path_parts = [config.USER_DATA_ROOT, sanitized_user] + list(subdirs)
        full_path = os.path.join(*path_parts)
        FileUtils.ensure_directory(full_path)
        return full_path


class DateUtils:
    """Date and time utilities"""

    @staticmethod
    def now_iso() -> str:
        """Get current UTC time in ISO format"""
        return datetime.utcnow().isoformat() + 'Z'

    @staticmethod
    def parse_iso(iso_string: str) -> datetime:
        """Parse ISO format datetime string"""
        # Handle both with and without 'Z' suffix
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1]
        return datetime.fromisoformat(iso_string)

    @staticmethod
    def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format datetime object"""
        return dt.strftime(format_str)

    @staticmethod
    def time_ago(dt: datetime) -> str:
        """
        Get human-readable time ago string

        Args:
            dt: Datetime object

        Returns:
            String like "2 hours ago"
        """
        now = datetime.utcnow()
        diff = now - dt

        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds / 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"

    @staticmethod
    def add_days(dt: datetime, days: int) -> datetime:
        """Add days to datetime"""
        return dt + timedelta(days=days)

    @staticmethod
    def add_hours(dt: datetime, hours: int) -> datetime:
        """Add hours to datetime"""
        return dt + timedelta(hours=hours)


class StringUtils:
    """String manipulation utilities"""

    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to max length

        Args:
            text: Input text
            max_length: Maximum length
            suffix: Suffix to add when truncated

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def slugify(text: str) -> str:
        """
        Convert text to URL-friendly slug

        Args:
            text: Input text

        Returns:
            Slugified text
        """
        import re
        # Convert to lowercase
        text = text.lower()
        # Replace spaces and special chars with hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        # Remove leading/trailing hyphens
        return text.strip('-')

    @staticmethod
    def mask_sensitive(text: str, visible_chars: int = 4) -> str:
        """
        Mask sensitive information

        Args:
            text: Sensitive text
            visible_chars: Number of visible characters at start

        Returns:
            Masked text
        """
        if len(text) <= visible_chars:
            return '*' * len(text)
        return text[:visible_chars] + '*' * (len(text) - visible_chars)


class DictUtils:
    """Dictionary manipulation utilities"""

    @staticmethod
    def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries

        Args:
            dict1: First dictionary
            dict2: Second dictionary (overwrites dict1)

        Returns:
            Merged dictionary
        """
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DictUtils.deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def filter_none(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove None values from dictionary

        Args:
            data: Input dictionary

        Returns:
            Dictionary without None values
        """
        return {k: v for k, v in data.items() if v is not None}

    @staticmethod
    def get_nested(data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """
        Get nested dictionary value using dot notation

        Args:
            data: Dictionary
            path: Dot-separated path (e.g., "user.profile.name")
            default: Default value if not found

        Returns:
            Value at path or default
        """
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


class TokenGenerator:
    """Token generation utilities"""

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Generate random token

        Args:
            length: Token length

        Returns:
            Random token string
        """
        import secrets
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_numeric_code(length: int = 6) -> str:
        """
        Generate numeric code

        Args:
            length: Code length

        Returns:
            Numeric code string
        """
        import secrets
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


class RetryHelper:
    """Retry helper for operations that may fail"""

    @staticmethod
    def retry(func, max_attempts: int = 3, delay: float = 1.0,
             exceptions: tuple = (Exception,)):
        """
        Retry function execution

        Args:
            func: Function to retry
            max_attempts: Maximum number of attempts
            delay: Delay between attempts in seconds
            exceptions: Tuple of exceptions to catch

        Returns:
            Function result

        Raises:
            Last exception if all attempts fail
        """
        import time
        last_exception = None

        for attempt in range(max_attempts):
            try:
                return func()
            except exceptions as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_attempts} attempts failed")

        raise last_exception


class HealthCheck:
    """System health check utilities"""

    @staticmethod
    def check_disk_space(path: str = ".", min_free_gb: float = 1.0) -> Dict[str, Any]:
        """
        Check disk space

        Args:
            path: Path to check
            min_free_gb: Minimum free space in GB

        Returns:
            Dictionary with disk space info
        """
        import shutil
        total, used, free = shutil.disk_usage(path)

        free_gb = free / (1024 ** 3)
        is_healthy = free_gb >= min_free_gb

        return {
            'healthy': is_healthy,
            'total_gb': total / (1024 ** 3),
            'used_gb': used / (1024 ** 3),
            'free_gb': free_gb,
            'percent_used': (used / total) * 100
        }

    @staticmethod
    def check_directory_writable(directory: str) -> bool:
        """
        Check if directory is writable

        Args:
            directory: Directory path

        Returns:
            True if writable
        """
        test_file = os.path.join(directory, '.write_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except Exception:
            return False

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get basic system information"""
        import platform
        import sys

        return {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': sys.version,
            'architecture': platform.machine()
        }
