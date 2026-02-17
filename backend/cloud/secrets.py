"""
Secrets management abstraction.

Providers:
- aws   — AWS Secrets Manager (production)
- env   — Environment variables only, no cloud calls (development)

Selection via SECRETS_PROVIDER env var (default: "env").
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BaseSecretsBackend(ABC):
    """Abstract interface for secrets retrieval."""

    @abstractmethod
    def get_secret(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a secret by name.

        Returns:
            Parsed dict of secret key/value pairs, or None if not found.
        """
        ...


class AWSSecretsBackend(BaseSecretsBackend):
    """Fetch secrets from AWS Secrets Manager."""

    def __init__(self, region: Optional[str] = None):
        from backend.cloud.aws_helpers import get_boto3_client
        self._region = region
        self._client = get_boto3_client(
            "secretsmanager",
            **({"region_name": region} if region else {}),
        )

    def get_secret(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            response = self._client.get_secret_value(SecretId=name)
            if "SecretString" in response:
                return json.loads(response["SecretString"])
            logger.warning("Secret %s does not contain SecretString", name)
            return None
        except Exception as exc:
            error_code = getattr(
                getattr(exc, "response", {}).get("Error", {}),
                "__getitem__",
                lambda _: None,
            )
            # Handle botocore ClientError gracefully
            try:
                err = exc.response["Error"]["Code"]  # type: ignore[union-attr]
                if err == "ResourceNotFoundException":
                    logger.warning("Secret %s not found in Secrets Manager", name)
                elif err == "AccessDeniedException":
                    logger.warning("Access denied to secret %s", name)
                else:
                    logger.error("Error fetching secret %s: %s", name, exc)
            except (AttributeError, KeyError, TypeError):
                logger.error("Unexpected error fetching secret %s", name)
            return None


class EnvSecretsBackend(BaseSecretsBackend):
    """
    Read secrets from environment variables only.

    No cloud calls are made. This is the default for local development.
    """

    def get_secret(self, _name: str) -> Optional[Dict[str, Any]]:
        logger.debug("EnvSecretsBackend: skipping cloud fetch for %s", _name)
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_secrets_backend: Optional[BaseSecretsBackend] = None


def get_secrets_backend() -> BaseSecretsBackend:
    """Return singleton secrets backend based on SECRETS_PROVIDER config."""
    global _secrets_backend
    if _secrets_backend is not None:
        return _secrets_backend

    provider = os.getenv("SECRETS_PROVIDER", "env").lower()
    if provider == "aws":
        logger.info("Secrets provider: AWS Secrets Manager")
        _secrets_backend = AWSSecretsBackend()
    else:
        logger.info("Secrets provider: environment variables only")
        _secrets_backend = EnvSecretsBackend()
    return _secrets_backend
