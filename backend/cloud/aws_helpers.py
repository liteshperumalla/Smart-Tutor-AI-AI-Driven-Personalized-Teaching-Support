"""
Shared AWS boto3 client factory.

Centralizes region + credential configuration so individual backends
don't duplicate the same boilerplate.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


def _build_client_kwargs() -> dict[str, Any]:
    """Build shared kwargs for boto3 clients from config or env."""
    import os

    try:
        from backend.config import config
        region = getattr(config, "AWS_REGION", None) or os.getenv("AWS_REGION", "us-east-1")
        access_key = getattr(config, "AWS_ACCESS_KEY_ID", None) or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = getattr(config, "AWS_SECRET_ACCESS_KEY", None) or os.getenv("AWS_SECRET_ACCESS_KEY")
        session_token = getattr(config, "AWS_SESSION_TOKEN", None) or os.getenv("AWS_SESSION_TOKEN")
    except (ImportError, AttributeError):
        region = os.getenv("AWS_REGION", "us-east-1")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        session_token = os.getenv("AWS_SESSION_TOKEN")

    kwargs: dict[str, Any] = {"region_name": region}
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
        if session_token:
            kwargs["aws_session_token"] = session_token
    return kwargs


def get_boto3_client(service: str, **overrides: Any) -> Any:
    """
    Create a boto3 client for the given AWS service.

    Uses centralized region + credentials from config, with optional
    overrides for service-specific settings (e.g. signature_version).

    Args:
        service: AWS service name (e.g. "s3", "secretsmanager", "sts")
        **overrides: Additional kwargs merged into the client constructor

    Returns:
        boto3 client instance
    """
    import boto3

    kwargs = _build_client_kwargs()
    kwargs.update(overrides)
    return boto3.client(service, **kwargs)


@lru_cache(maxsize=1)
def get_boto3_session() -> Any:
    """Return a shared boto3 Session (cached)."""
    import boto3
    return boto3.session.Session()
