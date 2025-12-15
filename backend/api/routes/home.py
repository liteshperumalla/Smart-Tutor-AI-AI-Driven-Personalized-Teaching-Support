from fastapi import APIRouter

from backend.content.home_content import (
    ANNOUNCEMENTS,
    COURSE_TOPICS,
    PROFESSOR,
    QUICK_ACTIONS,
)
from backend.services.status_service import get_system_status


router = APIRouter(prefix="/home", tags=["home"])


@router.get("/overview")
def home_overview():
    """Provide hero widgets for the Next.js landing page."""
    system_status = get_system_status()
    return {
        "announcements": ANNOUNCEMENTS,
        "professor": PROFESSOR,
        "course_topics": COURSE_TOPICS,
        "quick_actions": QUICK_ACTIONS,
        "system_status": system_status,
    }
