"""Database metadata and helpers for Alembic migrations.

Avoids top-level SQLAlchemy model imports to prevent circular dependency
chains when other modules import ``backend.db``.
"""

from .models import Base
from .url import build_postgres_url, build_postgres_url_string

# Lazy imports for model classes — only import when actually needed.
# This avoids pulling in sqlalchemy.orm MappedColumn annotations into
# any module that just needs the Base metadata or URL helpers.
__all__ = [
    "Base",
    "build_postgres_url",
    "build_postgres_url_string",
]
