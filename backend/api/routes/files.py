from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path

from backend.api.dependencies import get_current_session
from backend.validators import PathValidator
from backend.exceptions import InvalidInputError
from backend.config import config

try:
    from botocore.exceptions import ClientError
except ImportError:
    ClientError = Exception  # fallback if boto3 not installed


router = APIRouter(prefix="/files", tags=["files"])

# S3 Configuration - use config value with fallback
S3_DOCUMENTS_BUCKET = config.S3_DOCUMENTS_BUCKET
S3_DOCUMENTS_PREFIX = "modules/"


def _get_s3_client():
    """Get S3 client with signature v4 for presigned URL generation."""
    from backend.cloud.aws_helpers import get_boto3_client
    from botocore.config import Config as BotoConfig
    return get_boto3_client(
        "s3", config=BotoConfig(signature_version="s3v4")
    )


# Lazy-initialized S3 client (replaces module-level boto3.client)
_s3_client = None


def _get_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = _get_s3_client()
    return _s3_client


def _resolve_path(raw_path: str) -> Path:
    try:
        project_root = Path.cwd().resolve()
        allowed_roots = [
            project_root / config.USER_DATA_ROOT,
            project_root / "data",
            project_root / "Modules",
            project_root / "Assets",
            project_root / "docs",
            project_root / "Evaluation_files",
        ]

        resolved = Path(raw_path).expanduser().resolve()
        for root in allowed_roots:
            try:
                resolved.relative_to(root.resolve())
                resolved_path = PathValidator.validate_path(
                    str(resolved), base_dir=str(root.resolve())
                )
                break
            except ValueError:
                continue
        else:
            raise InvalidInputError("path", "Path is outside allowed directories")
    except InvalidInputError:
        raise HTTPException(status_code=403, detail="Access denied")

    resolved = Path(resolved_path)
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return resolved


@router.get("/view")
def view_file(
    request: Request,
    path: str = Query(...),
    session=Depends(get_current_session),
):
    """
    View a file. Supports both local files and S3 documents.
    If file doesn't exist locally, redirects to S3 presigned URL.
    Requires authentication. Local files are validated against the allowlist.
    """
    import os
    import logging

    logger = logging.getLogger(__name__)

    # Validate local path against the allowlist (prevents path traversal)
    try:
        resolved = _resolve_path(path)
        return FileResponse(
            resolved,
            filename=resolved.name,
            media_type="application/octet-stream",
        )
    except HTTPException:
        # File not in allowed dirs or doesn't exist locally — fall through to S3
        pass

    # File doesn't exist locally - redirect to S3
    filename = os.path.basename(path)
    logger.info(f"File not found locally ({path}), redirecting to S3 for: {filename}")

    # Check if request came through frontend proxy (port 4000) vs direct backend access (port 8010)
    host = request.headers.get("host", "")
    is_via_proxy = (
        "4000" in host
        or "localhost:4000" in host
        or "127.0.0.1:4000" in host
    )

    # Check X-Forwarded-Proto to detect if request came through proxy
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    is_https = forwarded_proto == "https" or request.url.scheme == "https"

    if is_via_proxy:
        # Request came through frontend proxy, return redirect through proxy
        scheme = "https" if is_https else "http"
        base_url = f"{scheme}://{host}"
        redirect_url = (
            f"{base_url}/api/backend/files/s3-document?source_file={filename}"
        )
        logger.info(f"Via proxy, redirecting to: {redirect_url}")
    else:
        # Direct backend access or internal Docker request
        redirect_url = f"/files/s3-document?source_file={filename}"
        logger.info(f"Direct access, redirecting to: {redirect_url}")

    return RedirectResponse(url=redirect_url, status_code=307)


@router.get("/download")
def download_file(
    path: str = Query(...),
    session=Depends(get_current_session),
):
    file_path = _resolve_path(path)
    return FileResponse(
        file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/s3-document")
def get_s3_document(
    source_file: str = Query(..., description="Source file name from RAG metadata"),
    session=Depends(get_current_session),
):
    """
    Generate presigned S3 URL for course documents.
    Redirects user to the document in S3 for viewing.

    Note: This endpoint does not require authentication because:
    1. It only provides access to public course materials
    2. The presigned S3 URL is temporary (1 hour expiry)
    3. Browser navigation requests don't reliably pass auth cookies

    Args:
        source_file: File name from RAG source metadata (e.g., "Module 1/Lesson 1...")

    Returns:
        Redirect to presigned S3 URL (valid for 1 hour)
    """
    import re
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"S3 document request for: {source_file}")

    def normalize_filename(name: str) -> str:
        """Normalize filename for fuzzy matching"""
        name_no_ext = re.sub(
            r"\.(pptx?|pdf|docx?|ipynb)$", "", name, flags=re.IGNORECASE
        )
        normalized = re.sub(r"[\s\-_]+", "", name_no_ext.lower())
        return normalized

    source_normalized = normalize_filename(source_file)
    logger.debug(f"Normalized query: '{source_normalized}'")

    matching_key = None
    best_match_score = 0

    try:
        paginator = _get_client().get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=S3_DOCUMENTS_BUCKET, Prefix=S3_DOCUMENTS_PREFIX
        )

        for page in pages:
            if "Contents" not in page:
                continue
            for obj in page["Contents"]:
                key = obj["Key"]
                filename = key.split("/")[-1]
                file_path_with_prefix = key.replace(S3_DOCUMENTS_PREFIX, "", 1)

                if filename == source_file:
                    matching_key = key
                    logger.info(f"Exact filename match: {key}")
                    break

                if key.endswith(source_file) or file_path_with_prefix == source_file:
                    matching_key = key
                    logger.info(f"Exact path match: {key}")
                    break

                key_normalized = normalize_filename(filename)
                key_path_normalized = normalize_filename(file_path_with_prefix)

                if (
                    source_normalized in key_normalized
                    or source_normalized in key_path_normalized
                    or key_normalized in source_normalized
                    or key_path_normalized in source_normalized
                ):
                    score = min(len(source_normalized), len(key_normalized))
                    if score > best_match_score:
                        best_match_score = score
                        matching_key = key
                        logger.debug(f"Better match: {key} (score: {score})")

            if matching_key and best_match_score == len(source_normalized):
                break

        if not matching_key:
            logger.warning(f"File not found in S3: {source_file}")
            raise HTTPException(
                status_code=404, detail=f"Document not found: {source_file}"
            )

        logger.info(f"Found S3 document: {matching_key}")

        # Get the filename from the key for content disposition
        filename = matching_key.split("/")[-1]

        # File types that should be viewed inline in browser
        inline_types = {
            ".pdf",
            ".pptx",
            ".docx",
            ".txt",
            ".ipynb",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".html",
        }
        ext = Path(filename).suffix.lower()

        if ext in inline_types:
            # Use inline content disposition for viewable files
            response_content_disposition = f'inline; filename="{filename}"'
        else:
            # Default to attachment for other files
            response_content_disposition = f'attachment; filename="{filename}"'

        presigned_url = _get_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_DOCUMENTS_BUCKET,
                "Key": matching_key,
                "ResponseContentDisposition": response_content_disposition,
            },
            ExpiresIn=3600,
        )

        return RedirectResponse(url=presigned_url, status_code=302)

    except ClientError as e:
        logger.error(f"S3 error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")


@router.get("/s3-url")
def get_s3_url(
    source_file: str = Query(..., description="Source file name from RAG metadata"),
    session=Depends(get_current_session),
):
    """
    Get the S3 presigned URL for a document.
    Returns JSON with the presigned URL instead of redirecting.
    Useful for external viewers that need the direct S3 URL.
    """
    import re
    import logging
    from pathlib import Path

    logger = logging.getLogger(__name__)
    logger.info(f"S3 URL request for: {source_file}")

    def normalize_filename(name: str) -> str:
        """Normalize filename for fuzzy matching"""
        name_no_ext = re.sub(
            r"\.(pptx?|pdf|docx?|ipynb)$", "", name, flags=re.IGNORECASE
        )
        normalized = re.sub(r"[\s\-_]+", "", name_no_ext.lower())
        return normalized

    source_normalized = normalize_filename(source_file)
    matching_key = None
    best_match_score = 0

    try:
        paginator = _get_client().get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=S3_DOCUMENTS_BUCKET, Prefix=S3_DOCUMENTS_PREFIX
        )

        for page in pages:
            if "Contents" not in page:
                continue
            for obj in page["Contents"]:
                key = obj["Key"]
                filename = key.split("/")[-1]
                file_path_with_prefix = key.replace(S3_DOCUMENTS_PREFIX, "", 1)

                if filename == source_file:
                    matching_key = key
                    logger.info(f"Exact filename match: {key}")
                    break

                if key.endswith(source_file) or file_path_with_prefix == source_file:
                    matching_key = key
                    logger.info(f"Exact path match: {key}")
                    break

                key_normalized = normalize_filename(filename)
                key_path_normalized = normalize_filename(file_path_with_prefix)

                if (
                    source_normalized in key_normalized
                    or source_normalized in key_path_normalized
                    or key_normalized in source_normalized
                    or key_path_normalized in source_normalized
                ):
                    score = min(len(source_normalized), len(key_normalized))
                    if score > best_match_score:
                        best_match_score = score
                        matching_key = key
                        logger.debug(f"Better match: {key} (score: {score})")

            if matching_key and best_match_score == len(source_normalized):
                break

        if not matching_key:
            logger.warning(f"File not found in S3: {source_file}")
            raise HTTPException(
                status_code=404, detail=f"Document not found: {source_file}"
            )

        logger.info(f"Found S3 document: {matching_key}")

        filename = matching_key.split("/")[-1]
        inline_types = {
            ".pdf",
            ".pptx",
            ".docx",
            ".txt",
            ".ipynb",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".html",
        }
        ext = Path(filename).suffix.lower()

        if ext in inline_types:
            response_content_disposition = f'inline; filename="{filename}"'
        else:
            response_content_disposition = f'attachment; filename="{filename}"'

        presigned_url = _get_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_DOCUMENTS_BUCKET,
                "Key": matching_key,
                "ResponseContentDisposition": response_content_disposition,
            },
            ExpiresIn=3600,
        )

        return {"url": presigned_url, "filename": filename, "content_type": ext}

    except ClientError as e:
        logger.error(f"S3 error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")
