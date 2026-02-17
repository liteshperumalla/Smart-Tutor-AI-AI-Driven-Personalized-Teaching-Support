"""
Object storage abstraction layer.

Providers:
- s3    — AWS S3 (production)
- local — Local filesystem (development/testing)

Selection via OBJECT_STORAGE_PROVIDER env var (default: "s3").

Usage:
    from backend.cloud.object_storage import get_object_storage
    storage = get_object_storage()
    storage.put_object("my-bucket", "path/key.json", b'{"data": 1}')
    data = storage.get_object("my-bucket", "path/key.json")
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)


class ObjectStorageObject:
    """Represents a retrieved object from storage."""

    def __init__(self, body: bytes, metadata: Optional[Dict[str, str]] = None):
        self.body = body
        self.metadata = metadata or {}

    def read(self) -> bytes:
        return self.body

    def json(self) -> Any:
        return json.loads(self.body)


class ObjectStorageListEntry:
    """Represents a single entry from a list operation."""

    def __init__(self, key: str, size: int = 0, last_modified: Optional[str] = None):
        self.key = key
        self.size = size
        self.last_modified = last_modified


class BaseObjectStorage(ABC):
    """Abstract interface for object (blob) storage."""

    @abstractmethod
    def get_object(self, bucket: str, key: str) -> ObjectStorageObject:
        """Retrieve an object by bucket + key. Raises if not found."""
        ...

    @abstractmethod
    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Store an object."""
        ...

    @abstractmethod
    def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object."""
        ...

    @abstractmethod
    def list_objects(
        self, bucket: str, prefix: str = "", max_keys: int = 1000
    ) -> List[ObjectStorageListEntry]:
        """List objects under a prefix."""
        ...

    @abstractmethod
    def generate_presigned_url(
        self, bucket: str, key: str, expires_in: int = 3600
    ) -> str:
        """Generate a time-limited URL to access an object."""
        ...

    def paginate_objects(
        self, bucket: str, prefix: str = ""
    ) -> Iterator[ObjectStorageListEntry]:
        """Iterate over all objects under a prefix (handles pagination)."""
        entries = self.list_objects(bucket, prefix, max_keys=1000)
        yield from entries


# ---------------------------------------------------------------------------
# AWS S3 Implementation
# ---------------------------------------------------------------------------


class S3ObjectStorage(BaseObjectStorage):
    """AWS S3 object storage backend."""

    def __init__(self, region: Optional[str] = None, signature_version: Optional[str] = None):
        from backend.cloud.aws_helpers import get_boto3_client

        extra: Dict[str, Any] = {}
        if region:
            extra["region_name"] = region
        if signature_version:
            from botocore.config import Config as BotoConfig
            extra["config"] = BotoConfig(signature_version=signature_version)

        self._client = get_boto3_client("s3", **extra)
        self._region = region

    def get_object(self, bucket: str, key: str) -> ObjectStorageObject:
        response = self._client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        metadata = response.get("Metadata", {})
        return ObjectStorageObject(body=body, metadata=metadata)

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        kwargs: Dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
        }
        if metadata:
            kwargs["Metadata"] = metadata
        self._client.put_object(**kwargs)

    def delete_object(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    def list_objects(
        self, bucket: str, prefix: str = "", max_keys: int = 1000
    ) -> List[ObjectStorageListEntry]:
        response = self._client.list_objects_v2(
            Bucket=bucket, Prefix=prefix, MaxKeys=max_keys
        )
        entries = []
        for obj in response.get("Contents", []):
            entries.append(
                ObjectStorageListEntry(
                    key=obj["Key"],
                    size=obj.get("Size", 0),
                    last_modified=str(obj.get("LastModified", "")),
                )
            )
        return entries

    def paginate_objects(
        self, bucket: str, prefix: str = ""
    ) -> Iterator[ObjectStorageListEntry]:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield ObjectStorageListEntry(
                    key=obj["Key"],
                    size=obj.get("Size", 0),
                    last_modified=str(obj.get("LastModified", "")),
                )

    def generate_presigned_url(
        self, bucket: str, key: str, expires_in: int = 3600
    ) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )


# ---------------------------------------------------------------------------
# Local Filesystem Implementation
# ---------------------------------------------------------------------------


class LocalFileStorage(BaseObjectStorage):
    """
    Local filesystem object storage for development/testing.

    Maps bucket/key pairs to files under a root directory:
        {root}/{bucket}/{key}
    """

    def __init__(self, root: Optional[str] = None):
        self._root = Path(root or os.getenv("LOCAL_STORAGE_ROOT", "./local_storage"))
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("LocalFileStorage initialized at %s", self._root)

    def _path(self, bucket: str, key: str) -> Path:
        return self._root / bucket / key

    def get_object(self, bucket: str, key: str) -> ObjectStorageObject:
        path = self._path(bucket, key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {bucket}/{key}")
        return ObjectStorageObject(body=path.read_bytes())

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        path = self._path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def delete_object(self, bucket: str, key: str) -> None:
        path = self._path(bucket, key)
        if path.exists():
            path.unlink()

    def list_objects(
        self, bucket: str, prefix: str = "", max_keys: int = 1000
    ) -> List[ObjectStorageListEntry]:
        bucket_dir = self._root / bucket
        if not bucket_dir.exists():
            return []
        entries = []
        for path in sorted(bucket_dir.rglob("*")):
            if path.is_file():
                relative = str(path.relative_to(bucket_dir))
                if relative.startswith(prefix):
                    entries.append(
                        ObjectStorageListEntry(
                            key=relative, size=path.stat().st_size
                        )
                    )
                    if len(entries) >= max_keys:
                        break
        return entries

    def paginate_objects(
        self, bucket: str, prefix: str = ""
    ) -> Iterator[ObjectStorageListEntry]:
        yield from self.list_objects(bucket, prefix, max_keys=999999)

    def generate_presigned_url(
        self, bucket: str, key: str, expires_in: int = 3600
    ) -> str:
        path = self._path(bucket, key)
        return f"file://{path.resolve()}"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_object_storage: Optional[BaseObjectStorage] = None


def get_object_storage() -> BaseObjectStorage:
    """Return singleton object storage backend based on config."""
    global _object_storage
    if _object_storage is not None:
        return _object_storage

    provider = os.getenv("OBJECT_STORAGE_PROVIDER", "s3").lower()
    if provider == "local":
        logger.info("Object storage provider: local filesystem")
        _object_storage = LocalFileStorage()
    else:
        logger.info("Object storage provider: AWS S3")
        _object_storage = S3ObjectStorage()
    return _object_storage
