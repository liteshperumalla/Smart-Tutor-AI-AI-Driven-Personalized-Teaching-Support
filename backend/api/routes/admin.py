"""
Admin API Routes
All endpoints require Admin role via get_admin_session dependency.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from typing import Optional

from backend.api.dependencies import get_admin_session
from backend.services.admin_service import get_admin_service
from backend.services.resource_service import get_resource_service

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Request Models ────────────────────────────────────────────────

class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(User|Admin)$")


class UpdateFeedbackStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(new|reviewed|resolved)$")


class CreateAnnouncementRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    priority: str = Field(default="info", pattern="^(info|warning|critical)$")


class UpdateAnnouncementRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None, max_length=5000)
    priority: Optional[str] = Field(default=None, pattern="^(info|warning|critical)$")
    active: Optional[bool] = None


class CreateResourceLinkRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., min_length=1)
    description: str = Field(default="", max_length=2000)
    order: int = Field(default=0, ge=0)


class UpdateResourceRequest(BaseModel):
    category: Optional[str] = Field(default=None, max_length=200)
    title: Optional[str] = Field(default=None, max_length=500)
    url: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    order: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None


# ── Dashboard ─────────────────────────────────────────────────────

@router.get("/stats")
def admin_stats(session=Depends(get_admin_session)):
    svc = get_admin_service()
    return {"stats": svc.get_admin_stats()}


# ── Quiz Metrics ─────────────────────────────────────────────────

@router.get("/quiz-metrics")
def quiz_metrics(session=Depends(get_admin_session)):
    svc = get_admin_service()
    return {"quiz_metrics": svc.get_quiz_metrics()}


# ── User Management ──────────────────────────────────────────────

@router.get("/users")
def list_users(session=Depends(get_admin_session)):
    svc = get_admin_service()
    return {"users": svc.list_users()}


@router.put("/users/{username}/role")
def update_user_role(
    username: str,
    payload: UpdateRoleRequest,
    session=Depends(get_admin_session),
):
    _, admin_user = session
    if admin_user.get("username") == username and payload.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own Admin role",
        )
    svc = get_admin_service()
    try:
        svc.update_user_role(username, payload.role)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return {"success": True, "username": username, "role": payload.role}


@router.delete("/users/{username}")
def delete_user(
    username: str,
    session=Depends(get_admin_session),
):
    _, admin_user = session
    if admin_user.get("username") == username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account from admin panel",
        )
    svc = get_admin_service()
    if not svc.delete_user(username):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return {"success": True, "username": username}


# ── Feedback ──────────────────────────────────────────────────────

@router.get("/feedback")
def list_all_feedback(
    feedback_type: Optional[str] = Query(None, pattern="^(feedback|bug)$"),
    limit: int = Query(200, ge=1, le=1000),
    session=Depends(get_admin_session),
):
    svc = get_admin_service()
    entries = svc.get_all_feedback(feedback_type=feedback_type, limit=limit)

    # Overlay statuses from the status file
    statuses = svc._load_feedback_statuses()
    for entry in entries:
        fb_id = entry.get("id")
        if fb_id and fb_id in statuses:
            entry["status"] = statuses[fb_id].get("status", "new")

    return {"feedback": entries, "total": len(entries)}


@router.put("/feedback/{feedback_id}")
def update_feedback_status(
    feedback_id: str,
    payload: UpdateFeedbackStatusRequest,
    session=Depends(get_admin_session),
):
    svc = get_admin_service()
    result = svc.update_feedback_status(feedback_id, payload.status)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback entry not found",
        )
    return {"success": True, "feedback_id": feedback_id, "status": payload.status}


# ── Announcements ─────────────────────────────────────────────────

@router.get("/announcements")
def list_announcements(session=Depends(get_admin_session)):
    svc = get_admin_service()
    return {"announcements": svc.list_announcements()}


@router.post("/announcements")
def create_announcement(
    payload: CreateAnnouncementRequest,
    session=Depends(get_admin_session),
):
    _, admin_user = session
    svc = get_admin_service()
    announcement = svc.create_announcement(
        title=payload.title,
        content=payload.content,
        priority=payload.priority,
        author=admin_user.get("username", "admin"),
    )
    return {"announcement": announcement}


@router.put("/announcements/{announcement_id}")
def update_announcement(
    announcement_id: str,
    payload: UpdateAnnouncementRequest,
    session=Depends(get_admin_session),
):
    svc = get_admin_service()
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    result = svc.update_announcement(announcement_id, updates)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found",
        )
    return {"announcement": result}


@router.delete("/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    session=Depends(get_admin_session),
):
    svc = get_admin_service()
    if not svc.delete_announcement(announcement_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found",
        )
    return {"success": True}


# ── Agent & Knowledge Graph Metrics ──────────────────────────────

@router.get("/agent-metrics")
def agent_metrics(session=Depends(get_admin_session)):
    svc = get_admin_service()
    return {"agent_metrics": svc.get_agent_metrics()}


@router.get("/knowledge-graph-metrics")
def knowledge_graph_metrics(session=Depends(get_admin_session)):
    svc = get_admin_service()
    return {"knowledge_graph_metrics": svc.get_knowledge_graph_metrics()}


# ── Resources Management ─────────────────────────────────────────

@router.get("/resources")
def list_admin_resources(session=Depends(get_admin_session)):
    svc = get_resource_service()
    resources = svc.list_resources(include_inactive=True)
    return {"resources": resources, "total": len(resources)}


@router.post("/resources")
def create_resource_link(
    payload: CreateResourceLinkRequest,
    session=Depends(get_admin_session),
):
    _, admin_user = session
    svc = get_resource_service()
    resource = svc.create_link(
        category=payload.category,
        title=payload.title,
        url=payload.url,
        description=payload.description,
        order=payload.order,
        created_by=admin_user.get("username", "admin"),
    )
    return {"resource": resource}


@router.post("/resources/upload")
async def upload_resource_file(
    file: UploadFile = File(...),
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    order: int = Form(0),
    session=Depends(get_admin_session),
):
    _, admin_user = session
    contents = await file.read()
    MAX_SIZE = 50 * 1024 * 1024  # 50 MB
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large (max 50 MB)",
        )
    svc = get_resource_service()
    resource = svc.upload_file(
        category=category,
        title=title,
        file_bytes=contents,
        file_name=file.filename or "upload",
        mime_type=file.content_type or "application/octet-stream",
        description=description,
        order=order,
        created_by=admin_user.get("username", "admin"),
    )
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create resource",
        )
    return {"resource": resource}


@router.put("/resources/{resource_id}")
def update_resource(
    resource_id: str,
    payload: UpdateResourceRequest,
    session=Depends(get_admin_session),
):
    svc = get_resource_service()
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    result = svc.update_resource(resource_id, updates)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    return {"resource": result}


@router.delete("/resources/{resource_id}")
def delete_resource(
    resource_id: str,
    session=Depends(get_admin_session),
):
    svc = get_resource_service()
    if not svc.delete_resource(resource_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    return {"success": True}


@router.get("/resources/categories")
def list_resource_categories(session=Depends(get_admin_session)):
    svc = get_resource_service()
    return {"categories": svc.get_categories()}


@router.post("/resources/migrate")
def migrate_static_resources(session=Depends(get_admin_session)):
    svc = get_resource_service()
    result = svc.migrate_from_catalog()
    return result
