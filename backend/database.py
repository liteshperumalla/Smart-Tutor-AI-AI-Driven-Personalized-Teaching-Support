"""
Database Service Layer
Provides abstraction for data storage with proper error handling and thread safety
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path
from contextlib import contextmanager

from .config import config
from .logger import get_logger
from .exceptions import (
    DataNotFoundError, DataSaveError, DataLoadError,
    DataCorruptionError, UserNotFoundError, UserAlreadyExistsError
)
from .validators import PathValidator

logger = get_logger(__name__)


class JSONDatabase:
    """Thread-safe JSON file database with proper error handling"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._lock = threading.RLock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure database file exists"""
        if not os.path.exists(self.file_path):
            try:
                dir_path = os.path.dirname(self.file_path)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)
                self._write_data({})
                logger.info(f"Created new database file: {self.file_path}")
            except Exception as e:
                logger.error(f"Failed to create database file: {e}", exc_info=True)
                raise DataSaveError("database", str(e))

    def _read_data(self) -> Dict[str, Any]:
        """Read data from JSON file"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {self.file_path}: {e}")
            raise DataCorruptionError(self.file_path, "Invalid JSON format")
        except Exception as e:
            logger.error(f"Error reading {self.file_path}: {e}")
            raise DataLoadError(self.file_path, str(e))

    def _write_data(self, data: Dict[str, Any]) -> None:
        """Write data to JSON file"""
        try:
            # Write to temporary file first
            temp_file = f"{self.file_path}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            # Atomic rename
            os.replace(temp_file, self.file_path)
        except Exception as e:
            logger.error(f"Error writing to {self.file_path}: {e}")
            raise DataSaveError(self.file_path, str(e))

    @contextmanager
    def transaction(self):
        """Context manager for transactional operations"""
        with self._lock:
            data = self._read_data()
            try:
                yield data
                self._write_data(data)
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                raise

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key"""
        with self._lock:
            data = self._read_data()
            return data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value by key"""
        with self._lock:
            data = self._read_data()
            data[key] = value
            self._write_data(data)

    def delete(self, key: str) -> bool:
        """Delete key"""
        with self._lock:
            data = self._read_data()
            if key in data:
                del data[key]
                self._write_data(data)
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        with self._lock:
            data = self._read_data()
            return key in data

    def get_all(self) -> Dict[str, Any]:
        """Get all data"""
        with self._lock:
            return self._read_data()


class UserDatabase:
    """User database with enhanced functionality"""

    def __init__(self, users_file: Optional[str] = None):
        self.users_file = users_file or config.USERS_FILE
        self.db = JSONDatabase(self.users_file)
        logger.info(f"UserDatabase initialized with file: {self.users_file}")

    def create_user(
        self,
        username: str,
        password_hash: Optional[str] = None,
        email: Optional[str] = None,
        *,
        hashed_password: Optional[str] = None,
        **additional_fields,
    ) -> Dict[str, Any]:
        """
        Create a new user

        Args:
            username: Username
            password_hash: Hashed password
            email: Optional email
            **additional_fields: Additional user fields

        Returns:
            Created user data

        Raises:
            UserAlreadyExistsError: If user already exists
        """
        hash_value = password_hash or hashed_password
        if not hash_value:
            raise ValueError("password_hash is required")

        with self.db.transaction() as users:
            if username in users:
                logger.warning(f"Attempt to create existing user: {username}")
                raise UserAlreadyExistsError(username)

            normalized_hash = hash_value if isinstance(hash_value, str) else hash_value.decode('utf-8')
            user_data = {
                # Only `password_hash` is canonical; the read paths still tolerate
                # legacy users that have `hashed_password` set, so removing the
                # duplicate write is backward-compatible.
                'password_hash': normalized_hash,
                'email': email or '',
                'display_name': '',
                'phone_number': '',
                'role': 'User',
                'last_login': '',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'theme': 'light',
                'notes': '',
                'profile_picture_path': '',
                'login_attempts': 0,
                'locked_until': None,
                **additional_fields
            }

            users[username] = user_data
            logger.info(f"User created successfully: {username}")

            return user_data

    def get_user(self, username: str) -> Dict[str, Any]:
        """
        Get user data

        Args:
            username: Username

        Returns:
            User data dictionary

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user_data = self.db.get(username)
        if not user_data:
            logger.warning(f"User not found: {username}")
            raise UserNotFoundError(username)
        if "password_hash" not in user_data and "hashed_password" in user_data:
            user_data = dict(user_data)
            user_data["password_hash"] = user_data["hashed_password"]
        return user_data

    def get_user_safe(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user data without raising exception if not found"""
        user_data = self.db.get(username)
        if not user_data:
            return None
        if "password_hash" not in user_data and "hashed_password" in user_data:
            user_data = dict(user_data)
            user_data["password_hash"] = user_data["hashed_password"]
        return user_data

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find a user by email address."""
        if not email:
            return None
        all_users = self.db.get_all()
        for username, user_data in all_users.items():
            if user_data.get("email") == email:
                user = dict(user_data)
                user["username"] = username
                return user
        return None

    def update_user(self, username: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user data

        Args:
            username: Username
            updates: Dictionary of fields to update

        Returns:
            Updated user data

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        with self.db.transaction() as users:
            if username not in users:
                raise UserNotFoundError(username)

            # Update only provided fields. We intentionally no longer mirror
            # password_hash -> hashed_password; the legacy `hashed_password`
            # field stays readable for old users but new writes are single-keyed.
            normalized_updates = dict(updates)

            for key, value in normalized_updates.items():
                if key != 'username':  # Don't allow username change
                    users[username][key] = value

            users[username]['updated_at'] = datetime.now(timezone.utc).isoformat()
            logger.info(f"User updated: {username}, fields: {list(updates.keys())}")

            return users[username]

    def delete_user(self, username: str) -> bool:
        """
        Delete user

        Args:
            username: Username to delete

        Returns:
            True if deleted, False if not found
        """
        success = self.db.delete(username)
        if success:
            logger.info(f"User deleted: {username}")
        else:
            logger.warning(f"Attempted to delete non-existent user: {username}")
        return success

    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        return self.db.exists(username)

    def update_last_login(self, username: str) -> None:
        """Update last login timestamp"""
        try:
            self.update_user(username, {
                'last_login': datetime.now(timezone.utc).isoformat(),
                'login_attempts': 0  # Reset login attempts on successful login
            })
        except UserNotFoundError:
            logger.error(f"Cannot update last login for non-existent user: {username}")

    def increment_login_attempts(self, username: str) -> int:
        """
        Increment failed login attempts

        Returns:
            Current number of attempts
        """
        try:
            user = self.get_user(username)
            attempts = user.get('login_attempts', 0) + 1
            self.update_user(username, {'login_attempts': attempts})
            return attempts
        except UserNotFoundError:
            return 0

    def reset_login_attempts(self, username: str) -> None:
        """Reset failed login attempts to zero"""
        try:
            self.update_user(username, {'login_attempts': 0})
            logger.debug(f"Reset login attempts for user: {username}")
        except UserNotFoundError:
            pass

    def lock_account(self, username: str, until: datetime) -> None:
        """Lock user account until specified time"""
        try:
            self.update_user(username, {
                'locked_until': until.isoformat()
            })
            logger.warning(f"Account locked: {username} until {until}")
        except UserNotFoundError:
            pass

    def is_account_locked(self, username: str) -> bool:
        """Check if account is locked"""
        try:
            user = self.get_user(username)
            locked_until = user.get('locked_until')
            if locked_until:
                unlock_time = datetime.fromisoformat(locked_until)
                if datetime.now(timezone.utc) < unlock_time:
                    return True
                else:
                    # Unlock account
                    self.update_user(username, {
                        'locked_until': None,
                        'login_attempts': 0
                    })
            return False
        except UserNotFoundError:
            return False

    def list_users(self) -> List[Dict[str, Any]]:
        """Get list of all users (without passwords)"""
        all_users = self.db.get_all()
        user_list = []
        for username, user_data in all_users.items():
            safe_data = {
                k: v for k, v in user_data.items()
                if k not in ['hashed_password', 'password_hash']
            }
            safe_data['username'] = username
            user_list.append(safe_data)
        return user_list


class ChatSessionDatabase:
    """Chat session database"""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or config.USER_DATA_ROOT
        logger.info(f"ChatSessionDatabase initialized with base: {self.base_dir}")

    def _get_user_chat_dir(self, user_id: str) -> str:
        """Get user's chat directory"""
        sanitized_user = PathValidator.sanitize_path_component(user_id)
        chat_dir = os.path.join(self.base_dir, sanitized_user, "chats")
        os.makedirs(chat_dir, exist_ok=True)
        return chat_dir

    def _get_chat_path(self, user_id: str, chat_id: str) -> str:
        """Get path to specific chat file"""
        chat_dir = self._get_user_chat_dir(user_id)
        sanitized_chat_id = PathValidator.sanitize_path_component(chat_id)
        return os.path.join(chat_dir, f"{sanitized_chat_id}.json")

    def save_chat(self, user_id: str, chat_id: str, messages: List[Dict[str, Any]],
                 title: Optional[str] = None) -> None:
        """Save chat session"""
        chat_path = self._get_chat_path(user_id, chat_id)

        chat_data = {
            'chat_id': chat_id,
            'user_id': user_id,
            'title': title or 'New Chat',
            'messages': messages,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        # Write to a temp file then atomically rename to avoid corruption on crash
        # mid-write. Matches the pattern used by JSONDatabase._write_data().
        try:
            tmp_path = f"{chat_path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, chat_path)
            logger.debug(f"Chat saved: user={user_id}, chat={chat_id}")
        except Exception as e:
            logger.error(f"Failed to save chat: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise DataSaveError("chat", str(e))

    def load_chat(self, user_id: str, chat_id: str) -> Dict[str, Any]:
        """Load chat session"""
        chat_path = self._get_chat_path(user_id, chat_id)

        if not os.path.exists(chat_path):
            raise DataNotFoundError("chat", chat_id)

        try:
            with open(chat_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted chat file: {chat_path}")
            raise DataCorruptionError(chat_path, "Invalid JSON")
        except Exception as e:
            logger.error(f"Failed to load chat: {e}")
            raise DataLoadError("chat", str(e))

    def list_user_chats(self, user_id: str) -> List[Dict[str, Any]]:
        """List all chats for a user"""
        chat_dir = self._get_user_chat_dir(user_id)
        chats = []

        for filename in os.listdir(chat_dir):
            if filename.endswith('.json') and filename != 'index.json':
                chat_id = filename[:-5]
                try:
                    chat_data = self.load_chat(user_id, chat_id)
                    chats.append({
                        'chat_id': chat_id,
                        'title': chat_data.get('title', 'Untitled'),
                        'updated_at': chat_data.get('updated_at', ''),
                        'message_count': len(chat_data.get('messages', []))
                    })
                except Exception as e:
                    logger.warning(f"Failed to load chat {chat_id}: {e}")

        # Sort by updated_at descending
        chats.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return chats

    def delete_chat(self, user_id: str, chat_id: str) -> bool:
        """Delete a chat session"""
        chat_path = self._get_chat_path(user_id, chat_id)
        try:
            if os.path.exists(chat_path):
                os.remove(chat_path)
                logger.info(f"Chat deleted: user={user_id}, chat={chat_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete chat: {e}")
            return False


# Singleton instances
_user_db = None
_chat_db = None
_user_db_lock = threading.Lock()
_chat_db_lock = threading.Lock()


def get_user_db():
    """
    Get user database instance - returns appropriate backend based on config.

    In production:
      - filesystem backend is REFUSED (JSON file is a multi-worker corruption
        risk and provides no encryption at rest).
      - if the configured backend (postgres/hybrid) fails to initialize, we
        fail loud rather than silently dropping to filesystem.

    In non-production we keep the legacy filesystem fallback so local dev
    works without spinning up Postgres.
    """
    global _user_db
    if _user_db is None:
        with _user_db_lock:
            if _user_db is not None:
                return _user_db
            return _init_user_db()
    return _user_db


def _init_user_db():
    global _user_db
    backend_name = getattr(config, "STORAGE_BACKEND", "filesystem").lower()
    is_production = getattr(config, "ENVIRONMENT", "").lower() == "production"

    if is_production and backend_name not in ("postgres", "hybrid"):
        raise RuntimeError(
            f"STORAGE_BACKEND={backend_name!r} is not allowed in production. "
            "Set STORAGE_BACKEND=postgres or hybrid."
        )

    if backend_name == "hybrid":
        try:
            from .services.storage.hybrid import get_hybrid_backend
            _user_db = get_hybrid_backend()
            logger.info("Using hybrid storage backend (PostgreSQL + DynamoDB)")
        except Exception as e:
            if is_production:
                raise RuntimeError(
                    "Failed to initialize hybrid storage backend in production "
                    "(refusing to fall back to filesystem)."
                ) from e
            logger.warning(f"Failed to initialize hybrid backend, falling back to filesystem: {e}")
            _user_db = UserDatabase()
    elif backend_name == "postgres":
        try:
            from .services.storage.postgres import get_postgres_backend
            _user_db = get_postgres_backend()
            logger.info("Using PostgreSQL storage backend for users")
        except Exception as e:
            if is_production:
                raise RuntimeError(
                    "Failed to initialize Postgres storage backend in production "
                    "(refusing to fall back to filesystem)."
                ) from e
            logger.warning(f"Failed to initialize postgres backend, falling back to filesystem: {e}")
            _user_db = UserDatabase()
    else:
        # Non-production only: legacy filesystem backend
        _user_db = UserDatabase()
    return _user_db


def get_chat_db() -> ChatSessionDatabase:
    """Get singleton chat database instance (double-checked locking)."""
    global _chat_db
    if _chat_db is None:
        with _chat_db_lock:
            if _chat_db is None:
                _chat_db = ChatSessionDatabase()
    return _chat_db
