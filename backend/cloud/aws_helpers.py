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
    """Build shared kwargs for boto3 clients from config."""
    from backend.config import config

    kwargs: dict[str, Any] = {"region_name": config.AWS_REGION}
    if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY
        if config.AWS_SESSION_TOKEN:
            kwargs["aws_session_token"] = config.AWS_SESSION_TOKEN
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
