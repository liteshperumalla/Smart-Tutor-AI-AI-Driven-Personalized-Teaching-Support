from fastapi import FastAPI, APIRouter

from . import (
    health,
    auth,
    chat,
    quiz,
    research,
    resources,
    appointments,
    feedback,
    profile,
    evaluation,
    home,
    files,
    code,
    ws_chat,  # WebSocket chat support
    admin,
    courses,
    learning,
    rag,
)


# ---------------------------------------------------------------------------
# Versioned API router — all application endpoints live under /api/v1/
# ---------------------------------------------------------------------------
_v1 = APIRouter(prefix="/api/v1")

_v1.include_router(auth.router)
_v1.include_router(chat.router)
_v1.include_router(quiz.router)
_v1.include_router(research.router)
_v1.include_router(resources.router)
_v1.include_router(appointments.router)
_v1.include_router(feedback.router)
_v1.include_router(profile.router)
_v1.include_router(evaluation.router)
_v1.include_router(home.router)
_v1.include_router(files.router)
_v1.include_router(code.router)
_v1.include_router(rag.router)
_v1.include_router(courses.router)
_v1.include_router(learning.router)
_v1.include_router(admin.router)


def register_routes(app: FastAPI) -> None:
    """
    Attach all API routers to the FastAPI application.

    Routing strategy
    ----------------
    - /health, /ready, /metrics  — bare paths (infra / load-balancer probes).
    - /api/v1/*                  — canonical versioned paths for all endpoints.
      New clients MUST use this prefix.
    - Legacy bare paths (e.g. /auth/*, /chat/*) are retained for the
      backward-compatibility window and will be removed in v2.
      Sunset date: 90 days from production launch.
    - /ws/*                      — WebSocket, unversioned (proxy WS upgrade compat).
    """
    # ── Infrastructure probes (unversioned — required by load balancers) ──
    app.include_router(health.router)

    # ── Versioned API (/api/v1/) ──────────────────────────────────────────
    app.include_router(_v1)

    # ── WebSocket (unversioned — WS upgrade proxy compatibility) ─────────
    app.include_router(ws_chat.router)

    # ── Legacy bare-path routes (backward compatibility) ──────────────────
    # TODO: Remove after all clients have migrated to /api/v1/*
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(quiz.router)
    app.include_router(research.router)
    app.include_router(resources.router)
    app.include_router(appointments.router)
    app.include_router(feedback.router)
    app.include_router(profile.router)
    app.include_router(evaluation.router)
    app.include_router(home.router)
    app.include_router(files.router)
    app.include_router(code.router)
    app.include_router(rag.router)
    app.include_router(courses.router)
    app.include_router(learning.router)
    app.include_router(admin.router)
