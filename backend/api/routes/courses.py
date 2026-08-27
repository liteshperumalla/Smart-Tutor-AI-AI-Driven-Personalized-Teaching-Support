"""Course workspaces and aggregate instructor learning analytics."""

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_admin_session, get_current_session
from backend.csrf_protection import csrf_protect

router = APIRouter(prefix="/courses", tags=["courses"], dependencies=[Depends(csrf_protect)])


def get_learning_service():
    from backend.services.learning_service import get_learning_service as factory
    return factory()


class CourseCreateRequest(BaseModel):
    id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    code: str = Field(min_length=2, max_length=32)
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=1000)
    open_enrollment: bool = False
    resource_prefixes: list[str] = Field(default_factory=list)
    modules: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationCaseCreateRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    category: str = Field(default="course")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    expected_topics: list[str] = Field(default_factory=list, max_length=20)
    objective_ids: list[str] = Field(default_factory=list, max_length=10)


class MembershipRequest(BaseModel):
    username: str = Field(min_length=2, max_length=128)
    role: str = Field(pattern="^(student|instructor)$")


@router.post("/{course_id}/resources/upload", status_code=201)
async def upload_course_resource(
    course_id: str,
    file: UploadFile = File(...),
    category: str = Form("Course materials"),
    title: str = Form(""),
    description: str = Form(""),
    session=Depends(get_current_session),
    service=Depends(get_learning_service),
):
    """Allow the owning instructor to add a course-scoped, indexed source."""
    _, user = session
    service.require_access(user["username"], user, course_id, roles=("instructor",))
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="File is empty")
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 50 MB)")
    from backend.services.resource_service import get_resource_service
    resource = get_resource_service().upload_file(
        category=category,
        title=title or file.filename or "Course file",
        file_bytes=contents,
        file_name=file.filename or "upload",
        mime_type=file.content_type or "application/octet-stream",
        description=description,
        created_by=user["username"],
        course_id=course_id,
    )
    if not resource:
        raise HTTPException(status_code=500, detail="Could not create course resource")
    from pathlib import Path
    if Path(resource["file_name"]).suffix.lower() in {".pdf", ".pptx", ".docx", ".txt", ".md", ".ipynb"}:
        try:
            from backend.services.indexing_service import get_indexing_service
            get_indexing_service().start_indexing(resource["id"], resource["s3_key"], resource["file_name"], resource.get("mime_type", "application/octet-stream"))
        except Exception:
            pass
    return {"resource": resource}


@router.get("")
def list_courses(session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return {"courses": service.list_courses(user["username"], user)}


@router.get("/catalog")
def course_catalog(session=Depends(get_current_session), service=Depends(get_learning_service)):
    """Public course metadata for explicit open-enrollment decisions."""
    _, user = session
    return {"courses": service.list_enrollable_courses(user["username"], user)}


@router.post("")
def create_course(payload: CourseCreateRequest, session=Depends(get_admin_session), service=Depends(get_learning_service)):
    _, user = session
    return {"course": service.create_course(user["username"], payload.model_dump())}


@router.post("/{course_id}/enroll")
def enroll(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return {"membership": service.enroll(user["username"], user, course_id)}


@router.get("/{course_id}/memberships")
def list_memberships(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return {"memberships": service.memberships(user["username"], user, course_id)}


@router.put("/{course_id}/memberships")
def set_membership(course_id: str, payload: MembershipRequest, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return {"membership": service.set_membership(user["username"], user, course_id, payload.username, payload.role)}


@router.delete("/{course_id}/memberships/{username}")
def remove_membership(course_id: str, username: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    service.remove_membership(user["username"], user, course_id, username)
    return {"success": True}


@router.get("/{course_id}/objectives")
def course_objectives(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return {"objectives": service.objectives(user["username"], user, course_id)}


@router.get("/{course_id}/instructor-summary")
def instructor_summary(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return service.instructor_summary(user["username"], user, course_id)


@router.get("/{course_id}/content-ingestion")
def content_ingestion(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return service.content_ingestion_status(user["username"], user, course_id)


@router.post("/{course_id}/resources/{resource_id}/reindex")
def reindex_course_resource(course_id: str, resource_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    """Let a course instructor retry an indexing job without global admin access."""
    _, user = session
    service.require_access(user["username"], user, course_id, roles=("instructor",))
    from backend.services.resource_service import get_resource_service
    resource = get_resource_service().get_resource(resource_id)
    if not resource or resource.get("course_id") != course_id:
        raise HTTPException(status_code=404, detail="Course resource not found")
    if resource.get("type") != "file" or not resource.get("s3_key"):
        raise HTTPException(status_code=400, detail="Only stored file resources can be indexed")
    from pathlib import Path
    if Path(resource.get("file_name", "")).suffix.lower() not in {".pdf", ".pptx", ".docx", ".txt", ".md", ".ipynb"}:
        raise HTTPException(status_code=400, detail="This file type cannot be indexed")
    from backend.services.indexing_service import get_indexing_service
    get_indexing_service().start_indexing(resource["id"], resource["s3_key"], resource["file_name"], resource.get("mime_type", "application/octet-stream"))
    return {"started": True, "resource_id": resource_id}


@router.get("/{course_id}/objective-coverage")
def objective_coverage(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return service.objective_coverage(user["username"], user, course_id)


@router.get("/{course_id}/evaluation/cases")
def course_evaluation_cases(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    service.require_access(user["username"], user, course_id, roles=("instructor",))
    from backend.services.evaluation_service import get_evaluation_service
    return {"cases": get_evaluation_service().list_cases(course_id=course_id), "course_id": course_id}


@router.post("/{course_id}/evaluation/cases", status_code=201)
def create_course_evaluation_case(course_id: str, payload: EvaluationCaseCreateRequest, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    service.require_access(user["username"], user, course_id, roles=("instructor",))
    service.validate_objectives(user["username"], user, course_id, payload.objective_ids)
    from backend.services.evaluation_service import get_evaluation_service
    return {"case": get_evaluation_service().create_course_case(course_id, payload.model_dump())}


@router.post("/{course_id}/evaluation/run")
def run_course_evaluations(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    service.require_access(user["username"], user, course_id, roles=("instructor",))
    from backend.services.evaluation_service import get_evaluation_service
    return get_evaluation_service().run_tests(course_id=course_id, source_prefixes=service.course_prefixes(user["username"], user, course_id))
