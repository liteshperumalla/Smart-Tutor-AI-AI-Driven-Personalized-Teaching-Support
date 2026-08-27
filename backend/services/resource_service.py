"""
Resource Service
CRUD operations for learning resources stored in data/resources.json.
Uploaded files live in S3 under the resources/ prefix.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

RESOURCES_FILE = os.path.join(
    getattr(config, "DATA_DIR", "data"), "resources.json"
)

_file_lock = threading.Lock()


def _ensure_resources_file() -> None:
    os.makedirs(os.path.dirname(RESOURCES_FILE), exist_ok=True)
    if not os.path.exists(RESOURCES_FILE):
        with open(RESOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


class ResourceService:
    """Manage learning resources (links + uploaded files)."""

    def __init__(self) -> None:
        _ensure_resources_file()
        self._s3 = None

    # ── S3 helpers ────────────────────────────────────────────────

    def _get_s3(self):
        if self._s3 is None:
            try:
                import boto3
                self._s3 = boto3.client(
                    "s3",
                    region_name=getattr(config, "AWS_REGION", "us-east-1"),
                )
            except Exception as e:
                logger.warning("S3 client init failed: %s", e)
        return self._s3

    def _upload_to_s3(self, file_bytes: bytes, s3_key: str, content_type: str) -> bool:
        s3 = self._get_s3()
        if not s3:
            return False
        bucket = getattr(config, "S3_DOCUMENTS_BUCKET", "smart-ai-tutor-docs")
        try:
            s3.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=file_bytes,
                ContentType=content_type,
            )
            logger.info("Uploaded %s to s3://%s/%s", s3_key, bucket, s3_key)
            return True
        except Exception as e:
            logger.error("S3 upload failed for %s: %s", s3_key, e)
            return False

    def _delete_from_s3(self, s3_key: str) -> bool:
        s3 = self._get_s3()
        if not s3:
            return False
        bucket = getattr(config, "S3_DOCUMENTS_BUCKET", "smart-ai-tutor-docs")
        try:
            s3.delete_object(Bucket=bucket, Key=s3_key)
            logger.info("Deleted s3://%s/%s", bucket, s3_key)
            return True
        except Exception as e:
            logger.error("S3 delete failed for %s: %s", s3_key, e)
            return False

    def get_presigned_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        s3 = self._get_s3()
        if not s3:
            return None
        bucket = getattr(config, "S3_DOCUMENTS_BUCKET", "smart-ai-tutor-docs")
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": s3_key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            logger.error("Presigned URL failed for %s: %s", s3_key, e)
            return None

    # ── JSON read / write ─────────────────────────────────────────

    def _read_resources(self) -> List[Dict[str, Any]]:
        _ensure_resources_file()
        with _file_lock:
            with open(RESOURCES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        return data if isinstance(data, list) else []

    def _write_resources(self, resources: List[Dict[str, Any]]) -> None:
        _ensure_resources_file()
        with _file_lock:
            tmp = RESOURCES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(resources, f, indent=2, ensure_ascii=False)
            os.replace(tmp, RESOURCES_FILE)

    # ── CRUD ──────────────────────────────────────────────────────

    def list_resources(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        resources = self._read_resources()
        if not include_inactive:
            resources = [r for r in resources if r.get("active", True)]
        return sorted(resources, key=lambda r: (r.get("category", ""), r.get("order", 0)))

    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        for r in self._read_resources():
            if r["id"] == resource_id:
                return r
        return None

    def create_link(
        self,
        category: str,
        title: str,
        url: str,
        description: str = "",
        order: int = 0,
        created_by: str = "admin",
        course_id: str | None = None,
    ) -> Dict[str, Any]:
        resource = {
            "id": str(uuid.uuid4()),
            "category": category,
            "title": title,
            "url": url,
            "description": description,
            "type": "link",
            "file_name": None,
            "s3_key": None,
            "file_size_bytes": None,
            "mime_type": None,
            "order": order,
            "active": True,
            "created_by": created_by,
            "course_id": course_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        resources = self._read_resources()
        resources.append(resource)
        self._write_resources(resources)
        logger.info("Created link resource: %s", resource["id"])
        return resource

    def upload_file(
        self,
        category: str,
        title: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        description: str = "",
        order: int = 0,
        created_by: str = "admin",
        course_id: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        # Sanitise filename for S3 key
        safe_name = file_name.replace(" ", "_")
        s3_key = f"resources/{uuid.uuid4().hex[:8]}_{safe_name}"

        uploaded = self._upload_to_s3(file_bytes, s3_key, mime_type)
        if not uploaded:
            logger.warning("S3 upload failed — creating resource entry anyway (download won't work until S3 is configured)")

        resource = {
            "id": str(uuid.uuid4()),
            "category": category,
            "title": title,
            "url": None,
            "description": description,
            "type": "file",
            "file_name": file_name,
            "s3_key": s3_key,
            "file_size_bytes": len(file_bytes),
            "mime_type": mime_type,
            "order": order,
            "active": True,
            "created_by": created_by,
            "course_id": course_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        resources = self._read_resources()
        resources.append(resource)
        self._write_resources(resources)
        logger.info("Created file resource: %s (%s)", resource["id"], file_name)
        return resource

    def update_resource(
        self, resource_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        resources = self._read_resources()
        allowed = {"category", "title", "url", "description", "order", "active", "course_id"}
        for res in resources:
            if res["id"] == resource_id:
                for key in allowed:
                    if key in updates:
                        res[key] = updates[key]
                res["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_resources(resources)
                logger.info("Updated resource: %s", resource_id)
                return res
        return None

    def update_indexing_status(self, resource_id: str, progress: Dict[str, Any]) -> None:
        """Persist the last known indexing outcome beyond Redis/process lifetime."""
        resources = self._read_resources()
        for resource in resources:
            if resource.get("id") == resource_id:
                resource["indexing_status"] = dict(progress)
                resource["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_resources(resources)
                return

    def assign_unscoped_resources_to_course(self, course_id: str) -> int:
        """One-time compatibility migration for the original single-course catalog."""
        resources = self._read_resources()
        changed = 0
        for resource in resources:
            if resource.get("course_id") is None:
                resource["course_id"] = course_id
                resource["updated_at"] = datetime.utcnow().isoformat()
                changed += 1
        if changed:
            self._write_resources(resources)
        return changed

    def delete_resource(self, resource_id: str) -> bool:
        resources = self._read_resources()
        target = None
        for r in resources:
            if r["id"] == resource_id:
                target = r
                break
        if not target:
            return False

        # Delete S3 file if it's an uploaded resource
        if target.get("type") == "file" and target.get("s3_key"):
            self._delete_from_s3(target["s3_key"])

        filtered = [r for r in resources if r["id"] != resource_id]
        self._write_resources(filtered)
        logger.info("Deleted resource: %s", resource_id)
        return True

    # ── Helpers ───────────────────────────────────────────────────

    def get_categories(self) -> List[str]:
        resources = self._read_resources()
        cats = sorted(set(r.get("category", "") for r in resources if r.get("active", True)))
        return [c for c in cats if c]

    def get_resources_by_category(self, active_only: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        resources = self.list_resources(include_inactive=not active_only)
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for r in resources:
            cat = r.get("category", "Uncategorized")
            grouped.setdefault(cat, []).append(r)
        return grouped

    # ── Migration from static catalog ────────────────────────────

    def migrate_from_catalog(self) -> Dict[str, Any]:
        """Import all static links from resources_catalog.py into JSON store."""
        try:
            from backend.resources_catalog import RESOURCES
        except ImportError:
            return {"success": False, "error": "resources_catalog.py not found", "imported": 0}

        existing = self._read_resources()
        existing_urls = {r.get("url") for r in existing if r.get("url")}
        imported = 0

        for category, links in RESOURCES.items():
            for idx, link in enumerate(links):
                url = link.get("url", "")
                if url in existing_urls:
                    continue  # skip duplicates
                resource = {
                    "id": str(uuid.uuid4()),
                    "category": category,
                    "title": link.get("title", "Untitled"),
                    "url": url,
                    "description": "",
                    "type": "link",
                    "file_name": None,
                    "s3_key": None,
                    "file_size_bytes": None,
                    "mime_type": None,
                    "order": idx,
                    "active": True,
                    "created_by": "migration",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                existing.append(resource)
                existing_urls.add(url)
                imported += 1

        self._write_resources(existing)
        logger.info("Migrated %d resources from static catalog", imported)
        return {"success": True, "imported": imported, "total": len(existing)}


# ── Singleton ─────────────────────────────────────────────────────

_resource_service: Optional[ResourceService] = None


def get_resource_service() -> ResourceService:
    global _resource_service
    if _resource_service is None:
        _resource_service = ResourceService()
    return _resource_service
