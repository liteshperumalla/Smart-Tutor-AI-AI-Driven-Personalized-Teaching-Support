from .base import BaseStorageBackend
from .filesystem import FileSystemStorageBackend

# Lazy imports for backends that require optional dependencies (psycopg2, boto3).
# This allows pytest and lightweight environments to import this package without
# those dependencies installed.


def __getattr__(name: str):
    """Lazy-load storage backends on first access."""
    if name in ("PostgresStorageBackend", "get_postgres_backend"):
        from .postgres import PostgresStorageBackend, get_postgres_backend
        globals()["PostgresStorageBackend"] = PostgresStorageBackend
        globals()["get_postgres_backend"] = get_postgres_backend
        return globals()[name]
    if name in ("DynamoDBStorageBackend", "get_dynamodb_backend"):
        from .dynamodb import DynamoDBStorageBackend, get_dynamodb_backend
        globals()["DynamoDBStorageBackend"] = DynamoDBStorageBackend
        globals()["get_dynamodb_backend"] = get_dynamodb_backend
        return globals()[name]
    if name in ("HybridStorageBackend", "get_hybrid_backend"):
        from .hybrid import HybridStorageBackend, get_hybrid_backend
        globals()["HybridStorageBackend"] = HybridStorageBackend
        globals()["get_hybrid_backend"] = get_hybrid_backend
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseStorageBackend",
    "FileSystemStorageBackend",
    "PostgresStorageBackend",
    "get_postgres_backend",
    "DynamoDBStorageBackend",
    "get_dynamodb_backend",
    "HybridStorageBackend",
    "get_hybrid_backend",
]
