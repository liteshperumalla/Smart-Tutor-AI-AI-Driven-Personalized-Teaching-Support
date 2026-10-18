from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_current_session
from backend.resources_catalog import RESOURCES


router = APIRouter(prefix="/resources", tags=["resources"])


def get_resource_service():
    from backend.services.resource_service import get_resource_service as _get_resource_service

    return _get_resource_service()


@router.get("")
def list_resources(session=Depends(get_current_session)):
    """Return active resources grouped by category.
    Falls back to static catalog when the dynamic store is empty."""
    _, user = session
    svc = get_resource_service()
    resources = svc.list_resources(include_inactive=False)
    from backend.services.learning_service import get_learning_service
    learning = get_learning_service()
    visible = []
    for resource in resources:
        # Untagged entries are legacy INFO 5731 content. New records must be
        # explicitly visible through the caller's course membership.
        resource_course = resource.get("course_id") or "info-5731"
        try:
            learning.require_access(user["username"], user, resource_course)
            visible.append(resource)
        except HTTPException:
            continue
    grouped: dict = {}
    for resource in visible:
        grouped.setdefault(resource.get("category", "Uncategorized"), []).append(resource)

    if not grouped:
        # Fallback: serve static catalog in the original format
        return {"categories": RESOURCES}

    # Build both the legacy format (for backward-compat) and the full resources list
    categories: dict = {}
    all_resources: list = []
    for cat, items in grouped.items():
        cat_links = []
        for r in items:
            all_resources.append(r)
            if r.get("type") == "link" and r.get("url"):
                cat_links.append({"title": r["title"], "url": r["url"]})
        if cat_links:
            categories[cat] = cat_links

    return {
        "categories": categories,
        "resources": all_resources,
    }


@router.get("/download/{resource_id}")
def download_resource(resource_id: str, session=Depends(get_current_session)):
    """Return a presigned S3 URL for a file-type resource."""
    svc = get_resource_service()
    resource = svc.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not resource.get("active", True):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not available")
    _, user = session
    from backend.services.learning_service import get_learning_service
    get_learning_service().require_access(user["username"], user, resource.get("course_id") or "info-5731")
    if resource.get("type") != "file" or not resource.get("s3_key"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resource is not a downloadable file")

    url = svc.get_presigned_url(resource["s3_key"])
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Download temporarily unavailable",
        )
    return {"download_url": url, "file_name": resource.get("file_name", "download")}
