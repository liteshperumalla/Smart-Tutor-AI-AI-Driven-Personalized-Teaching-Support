"""
Cloud provider abstraction layer.

Provides cloud-agnostic interfaces for:
- Object storage (S3, local filesystem)
- Secrets management (AWS Secrets Manager, environment variables)
- AWS client helpers

All backends are selected via configuration, following the same factory
pattern used by BaseStorageBackend and LLMFactory.
"""


def __getattr__(name: str):
    """Lazy-load cloud backends on first access."""
    if name in ("BaseObjectStorage", "S3ObjectStorage", "LocalFileStorage", "get_object_storage"):
        from .object_storage import BaseObjectStorage, S3ObjectStorage, LocalFileStorage, get_object_storage
        globals()["BaseObjectStorage"] = BaseObjectStorage
        globals()["S3ObjectStorage"] = S3ObjectStorage
        globals()["LocalFileStorage"] = LocalFileStorage
        globals()["get_object_storage"] = get_object_storage
        return globals()[name]
    if name in ("BaseSecretsBackend", "AWSSecretsBackend", "EnvSecretsBackend", "get_secrets_backend"):
        from .secrets import BaseSecretsBackend, AWSSecretsBackend, EnvSecretsBackend, get_secrets_backend
        globals()["BaseSecretsBackend"] = BaseSecretsBackend
        globals()["AWSSecretsBackend"] = AWSSecretsBackend
        globals()["EnvSecretsBackend"] = EnvSecretsBackend
        globals()["get_secrets_backend"] = get_secrets_backend
        return globals()[name]
    if name in ("get_boto3_client",):
        from .aws_helpers import get_boto3_client
        globals()["get_boto3_client"] = get_boto3_client
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseObjectStorage",
    "S3ObjectStorage",
    "LocalFileStorage",
    "get_object_storage",
    "BaseSecretsBackend",
    "AWSSecretsBackend",
    "EnvSecretsBackend",
    "get_secrets_backend",
    "get_boto3_client",
]
