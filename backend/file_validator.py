"""
File Upload Validation
Provides secure file upload validation with content-type checking
"""

import os
import mimetypes
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import python-magic for content-type detection
# Falls back to extension-based checking if not available
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    logger.warning(
        "python-magic not installed. File validation will use extension-only checking. "
        "Install with: pip install python-magic"
    )


class FileValidator:
    """
    Secure file upload validation with MIME type checking.

    Security Features:
    - File size limits
    - Extension validation
    - MIME type verification (if python-magic available)
    - Content-type matching with extension
    """

    # Allowed MIME types mapped to their valid extensions
    ALLOWED_MIME_TYPES = {
        'application/pdf': ['.pdf'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
        'application/msword': ['.doc'],
        'application/vnd.ms-powerpoint': ['.ppt'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'text/plain': ['.txt'],
    }

    # Maximum file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

    @classmethod
    def validate_file(cls, file_path: str, max_size: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate an uploaded file for security

        Args:
            file_path: Path to the file to validate
            max_size: Optional override for max file size (bytes)

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
                - (True, "Valid") if file passes all checks
                - (False, error_message) if validation fails
        """
        path = Path(file_path)

        # Check if file exists
        if not path.exists():
            return False, "File does not exist"

        # Check if it's a file (not a directory)
        if not path.is_file():
            return False, "Path is not a file"

        # Check file size
        max_allowed = max_size if max_size is not None else cls.MAX_FILE_SIZE
        file_size = path.stat().st_size

        if file_size > max_allowed:
            return False, f"File too large: {file_size} bytes (max: {max_allowed} bytes)"

        if file_size == 0:
            return False, "File is empty"

        # Check extension
        extension = path.suffix.lower()
        allowed_extensions = set()
        for exts in cls.ALLOWED_MIME_TYPES.values():
            allowed_extensions.update(exts)

        if extension not in allowed_extensions:
            return False, f"File type not allowed: {extension}. Allowed: {', '.join(sorted(allowed_extensions))}"

        # Check MIME type if python-magic is available
        if HAS_MAGIC:
            try:
                mime_type = magic.from_file(str(path), mime=True)

                # Check if MIME type is allowed
                if mime_type not in cls.ALLOWED_MIME_TYPES:
                    return False, f"Invalid file type detected: {mime_type}"

                # Verify extension matches MIME type
                allowed_exts = cls.ALLOWED_MIME_TYPES[mime_type]
                if extension not in allowed_exts:
                    return False, f"File extension {extension} doesn't match content type {mime_type}"

                logger.info(f"File validated: {path.name} ({mime_type}, {file_size} bytes)")

            except Exception as e:
                logger.error(f"MIME type detection error: {e}")
                return False, f"Unable to verify file type: {e}"
        else:
            # Fallback: Use mimetypes library (less secure, extension-based)
            guessed_type, _ = mimetypes.guess_type(str(path))

            if guessed_type and guessed_type not in cls.ALLOWED_MIME_TYPES:
                return False, f"File type not allowed: {guessed_type}"

            logger.warning(
                f"File validated with extension-only checking: {path.name} "
                f"(Install python-magic for stronger validation)"
            )

        return True, "Valid"

    @classmethod
    def get_safe_filename(cls, filename: str) -> str:
        """
        Sanitize filename to prevent directory traversal attacks

        Args:
            filename: The original filename

        Returns:
            str: Sanitized filename safe for storage
        """
        # Remove any path components (prevent directory traversal)
        filename = os.path.basename(filename)

        # Replace potentially dangerous characters
        dangerous_chars = ['..', '/', '\\', '\0', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')

        # Limit filename length
        max_length = 255
        if len(filename) > max_length:
            # Keep extension, truncate name
            name, ext = os.path.splitext(filename)
            filename = name[:max_length - len(ext)] + ext

        return filename

    @classmethod
    def validate_upload(
        cls,
        file_content: bytes,
        filename: str,
        save_path: str,
        max_size: Optional[int] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validate and save an uploaded file

        Args:
            file_content: The file content (bytes)
            filename: Original filename
            save_path: Directory to save the file
            max_size: Optional max file size override

        Returns:
            Tuple[bool, str, Optional[str]]: (success, message, saved_path)
        """
        # Check file size
        max_allowed = max_size if max_size is not None else cls.MAX_FILE_SIZE
        if len(file_content) > max_allowed:
            return False, f"File too large: {len(file_content)} bytes", None

        if len(file_content) == 0:
            return False, "File is empty", None

        # Sanitize filename
        safe_filename = cls.get_safe_filename(filename)

        # Create save directory if it doesn't exist
        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename if file already exists
        file_path = save_dir / safe_filename
        counter = 1
        while file_path.exists():
            name, ext = os.path.splitext(safe_filename)
            file_path = save_dir / f"{name}_{counter}{ext}"
            counter += 1

        # Save file temporarily for validation
        try:
            file_path.write_bytes(file_content)
        except Exception as e:
            return False, f"Failed to save file: {e}", None

        # Validate the saved file
        is_valid, error_message = cls.validate_file(str(file_path), max_size=max_size)

        if not is_valid:
            # Remove invalid file
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to remove invalid file: {e}")

            return False, error_message, None

        logger.info(f"File upload validated and saved: {file_path}")
        return True, "File uploaded successfully", str(file_path)
