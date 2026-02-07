"""
Service layer initialization utilities.

Provides helpers to fetch the configured storage backend so that different
parts of the application (FastAPI, tests) can share the same
implementation while allowing us to swap in DynamoDB/S3 adapters later.
"""

from typing import Optional

from backend.config import config
from backend.logger import get_logger

from .storage.base import BaseStorageBackend
from .storage.filesystem import FileSystemStorageBackend

logger = get_logger(__name__)

_storage_backend: Optional[BaseStorageBackend] = None


def get_storage_backend() -> BaseStorageBackend:
    """Return a singleton storage backend instance."""
    global _storage_backend
    if _storage_backend is None:
        backend_name = getattr(config, "STORAGE_BACKEND", "filesystem").lower()

        if backend_name == "filesystem":
            _storage_backend = FileSystemStorageBackend()
            logger.info("Using FileSystem storage backend")

        elif backend_name == "hybrid":
            try:
                from .storage.hybrid import get_hybrid_backend
                _storage_backend = get_hybrid_backend()
                logger.info("Using Hybrid storage backend (PostgreSQL + DynamoDB)")
            except Exception as e:
                logger.warning(f"Failed to initialize hybrid backend, falling back to filesystem: {e}")
                _storage_backend = FileSystemStorageBackend()

        elif backend_name == "postgres":
            try:
                from .storage.postgres import get_postgres_backend
                _storage_backend = get_postgres_backend()
                logger.info("Using PostgreSQL storage backend")
            except Exception as e:
                logger.warning(f"Failed to initialize postgres backend, falling back to filesystem: {e}")
                _storage_backend = FileSystemStorageBackend()

        elif backend_name == "dynamodb":
            try:
                from .storage.dynamodb import get_dynamodb_backend
                _storage_backend = get_dynamodb_backend()
                logger.info("Using DynamoDB storage backend")
            except Exception as e:
                logger.warning(f"Failed to initialize dynamodb backend, falling back to filesystem: {e}")
                _storage_backend = FileSystemStorageBackend()
        else:
            raise ValueError(f"Unsupported storage backend: {backend_name}")

    return _storage_backend
