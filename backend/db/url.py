"""Helpers for constructing the PostgreSQL SQLAlchemy URL."""

import os

from sqlalchemy.engine import URL


def build_postgres_url() -> URL:
    """Build the SQLAlchemy URL from env vars with config fallbacks."""

    fallback = None
    if not {
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
    }.issubset(os.environ):
        from backend.config import config as fallback

    host = os.getenv("POSTGRES_HOST", str(fallback.POSTGRES_HOST if fallback else "localhost"))
    port = int(os.getenv("POSTGRES_PORT", str(fallback.POSTGRES_PORT if fallback else "5432")))
    database = os.getenv("POSTGRES_DB", str(fallback.POSTGRES_DB if fallback else "smart_tutor"))
    username = os.getenv(
        "POSTGRES_USER", str(fallback.POSTGRES_USER if fallback else "smart_tutor_user")
    )
    password = os.getenv("POSTGRES_PASSWORD", fallback.POSTGRES_PASSWORD if fallback else "")
    sslmode = os.getenv("POSTGRES_SSL_MODE", fallback.POSTGRES_SSL_MODE if fallback else "prefer")
    sslrootcert = os.getenv(
        "POSTGRES_SSL_ROOT_CERT", fallback.POSTGRES_SSL_ROOT_CERT if fallback else ""
    )

    query: dict[str, str] = {}
    if sslmode:
        query["sslmode"] = sslmode
    if sslrootcert:
        query["sslrootcert"] = sslrootcert

    return URL.create(
        "postgresql+psycopg2",
        username=username or None,
        password=password or None,
        host=host or None,
        port=port,
        database=database or None,
        query=query,
    )


def build_postgres_url_string() -> str:
    """Render the SQLAlchemy URL as a string for Alembic."""

    return build_postgres_url().render_as_string(hide_password=False)
