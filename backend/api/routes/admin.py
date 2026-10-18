from __future__ import annotations

"""
Admin API Routes
All endpoints require Admin role via get_admin_session dependency.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.api.dependencies import get_admin_session
from backend.csrf_protection import csrf_protect

# File extensions that the indexing pipeline can process
_INDEXABLE_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md", ".ipynb"}

# Every state-changing admin route applies the CSRF double-submit check in
# addition to the existing SameSite=Lax cookies — defense-in-depth against
# state-changing actions like update_user_role / delete_user.
_CSRF = [Depends(csrf_protect)]

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service():
    from backend.services.admin_service import get_admin_service as _get_admin_service

    return _get_admin_service()


def get_resource_service():
    from backend.services.resource_service import get_resource_service as _get_resource_service

    return _get_resource_service()


def get_indexing_service():
    from backend.services.indexing_service import get_indexing_service as _get_indexing_service

    return _get_indexing_service()


# ── Request Models ────────────────────────────────────────────────

class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(User|Admin)$")


class UpdateFeedbackStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(new|reviewed|resolved)$")


class UpdateAppointmentStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|confirmed|cancelled|completed)$")


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
    course_id: Optional[str] = Field(default=None, max_length=64)


class UpdateResourceRequest(BaseModel):
    category: Optional[str] = Field(default=None, max_length=200)
    title: Optional[str] = Field(default=None, max_length=500)
    url: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    order: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None
    course_id: Optional[str] = Field(default=None, max_length=64)


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


@router.put("/users/{username}/role", dependencies=_CSRF)
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


@router.delete("/users/{username}", dependencies=_CSRF)
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

@router.get("/appointments")
def list_all_appointments(
    status: Optional[str] = Query(
        None, pattern="^(pending|confirmed|cancelled|completed)$"
    ),
    limit: int = Query(200, ge=1, le=1000),
    session=Depends(get_admin_session),
):
    svc = get_admin_service()
    entries = svc.get_all_appointments(status=status, limit=limit)
    return {"appointments": entries, "total": len(entries)}


@router.put("/appointments/{appointment_id}", dependencies=_CSRF)
def update_appointment_status(
    appointment_id: str,
    payload: UpdateAppointmentStatusRequest,
    session=Depends(get_admin_session),
):
    svc = get_admin_service()
    result = svc.update_appointment_status(appointment_id, payload.status)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return {"success": True, "appointment": result}


# ── Feedback ──────────────────────────────────────────────────────

@router.get("/feedback")
def list_all_feedback(
    feedback_type: Optional[str] = Query(None, pattern="^(feedback|bug|report)$"),
    course_id: Optional[str] = Query(None, max_length=64),
    limit: int = Query(200, ge=1, le=1000),
    session=Depends(get_admin_session),
):
    svc = get_admin_service()
    entries = svc.get_all_feedback(feedback_type=feedback_type, course_id=course_id, limit=limit)

    # Overlay statuses from the status file
    statuses = svc._load_feedback_statuses()
    for entry in entries:
        fb_id = entry.get("id")
        if fb_id and fb_id in statuses:
            entry["status"] = statuses[fb_id].get("status", "new")

    return {"feedback": entries, "total": len(entries)}


@router.put("/feedback/{feedback_id}", dependencies=_CSRF)
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


@router.post("/announcements", dependencies=_CSRF)
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


@router.put("/announcements/{announcement_id}", dependencies=_CSRF)
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


@router.delete("/announcements/{announcement_id}", dependencies=_CSRF)
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


@router.get("/tracing-health")
def tracing_health(session=Depends(get_admin_session)):
    from backend.langfuse_setup import get_langfuse_health
    return {"tracing": get_langfuse_health()}


# ── LLMOps ───────────────────────────────────────────────────────────

@router.get("/llmops")
def llmops_stats(
    last_n: int = Query(default=200, ge=10, le=1000),
    session=Depends(get_admin_session),
):
    """Aggregated LLM observability stats: latency percentiles, token usage, per-model breakdown."""
    from backend.llmops import get_llmops_logger
    return get_llmops_logger().get_stats(last_n=last_n)


# ── Prompt Registry ───────────────────────────────────────────────────

class RegisterPromptRequest(BaseModel):
    template: str = Field(..., min_length=1, max_length=10000)
    description: str = Field(default="", max_length=500)
    variables: List[str] = Field(default_factory=list)


@router.get("/prompts")
def list_prompts(session=Depends(get_admin_session)):
    """List all registered prompt templates with their latest versions."""
    from backend.prompt_registry import get_prompt_registry
    return {"prompts": get_prompt_registry().list_prompts()}


@router.get("/prompts/{name}")
def get_prompt_versions(
    name: str,
    session=Depends(get_admin_session),
):
    """List all versions of a specific prompt."""
    from backend.prompt_registry import get_prompt_registry
    versions = get_prompt_registry().list_versions(name)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return {"name": name, "versions": versions}


@router.post("/prompts/{name}", status_code=201, dependencies=_CSRF)
def register_prompt(
    name: str,
    payload: RegisterPromptRequest,
    session=Depends(get_admin_session),
):
    """Register a new version of a prompt template."""
    from backend.prompt_registry import get_prompt_registry
    entry = get_prompt_registry().register(
        name=name,
        template=payload.template,
        description=payload.description,
        variables=payload.variables,
    )
    return entry


@router.delete("/prompts/{name}", status_code=200, dependencies=_CSRF)
def delete_prompt(name: str, session=Depends(get_admin_session)):
    """Delete all versions of a prompt (irreversible)."""
    from backend.prompt_registry import get_prompt_registry
    deleted = get_prompt_registry().delete(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return {"success": True, "deleted": name}


# ── Resources Management ─────────────────────────────────────────

@router.get("/resources")
def list_admin_resources(session=Depends(get_admin_session)):
    svc = get_resource_service()
    resources = svc.list_resources(include_inactive=True)
    return {"resources": resources, "total": len(resources)}


@router.post("/resources", dependencies=_CSRF)
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
        course_id=payload.course_id,
    )
    return {"resource": resource}


@router.post("/resources/upload", dependencies=_CSRF)
async def upload_resource_file(
    file: UploadFile = File(...),
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    order: int = Form(0),
    course_id: str = Form(""),
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
        course_id=course_id or None,
    )
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create resource",
        )

    # Auto-trigger RAG indexing for supported file types
    from pathlib import Path
    ext = Path(resource.get("file_name", "")).suffix.lower()
    if ext in _INDEXABLE_EXTENSIONS and resource.get("s3_key"):
        try:
            get_indexing_service().start_indexing(
                resource_id=resource["id"],
                s3_key=resource["s3_key"],
                filename=resource["file_name"],
                mime_type=resource.get("mime_type", "application/octet-stream"),
            )
        except Exception:
            pass  # Never block the upload response

    return {"resource": resource}


@router.put("/resources/{resource_id}", dependencies=_CSRF)
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


@router.delete("/resources/{resource_id}", dependencies=_CSRF)
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


@router.post("/resources/migrate", dependencies=_CSRF)
def migrate_static_resources(session=Depends(get_admin_session)):
    svc = get_resource_service()
    result = svc.migrate_from_catalog()
    return result


# ── Indexing ──────────────────────────────────────────────────────

@router.post("/resources/{resource_id}/reindex", dependencies=_CSRF)
def reindex_resource(
    resource_id: str,
    session=Depends(get_admin_session),
):
    """Kick off (or re-run) the RAG indexing pipeline for a file resource."""
    svc = get_resource_service()
    resource = svc.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if resource.get("type") != "file":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only file resources can be indexed")
    from pathlib import Path
    ext = Path(resource.get("file_name", "")).suffix.lower()
    if ext not in _INDEXABLE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{ext}' is not supported for indexing",
        )
    if not resource.get("s3_key"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resource has no S3 key")

    get_indexing_service().start_indexing(
        resource_id=resource["id"],
        s3_key=resource["s3_key"],
        filename=resource["file_name"],
        mime_type=resource.get("mime_type", "application/octet-stream"),
    )
    return {"started": True, "resource_id": resource_id}


@router.get("/resources/{resource_id}/reindex-status")
def reindex_status(
    resource_id: str,
    session=Depends(get_admin_session),
):
    """Poll the current indexing progress for a resource."""
    data = get_indexing_service().get_status(resource_id)
    if data is None:
        return {"status": "not_started", "progress_pct": 0, "chunks_created": 0, "total_chunks": None, "error": None}
    return data
