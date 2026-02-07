from fastapi import APIRouter

from backend.content.home_content import (
    ANNOUNCEMENTS,
    COURSE_TOPICS,
    PROFESSOR,
    QUICK_ACTIONS,
)
from backend.services.status_service import get_system_status
from backend.services.admin_service import get_admin_service


router = APIRouter(prefix="/home", tags=["home"])


@router.get("/overview")
def home_overview():
    """Provide hero widgets for the Next.js landing page."""
    system_status = get_system_status()

    # Merge static announcements with admin-created active announcements
    admin_svc = get_admin_service()
    dynamic_announcements = [
        {
            "id": a["id"],
            "title": a["title"],
            "body": a["content"],
            "accent": {
                "info": "border-blue-500",
                "warning": "border-yellow-500",
                "critical": "border-red-500",
            }.get(a.get("priority", "info"), "border-blue-500"),
        }
        for a in admin_svc.list_active_announcements()
    ]

    return {
        "announcements": dynamic_announcements + ANNOUNCEMENTS,
        "professor": PROFESSOR,
        "course_topics": COURSE_TOPICS,
        "quick_actions": QUICK_ACTIONS,
        "system_status": system_status,
    }


@router.get("/announcements")
def public_announcements():
    """Public endpoint returning active announcements."""
    admin_svc = get_admin_service()
    return {"announcements": admin_svc.list_active_announcements()}
