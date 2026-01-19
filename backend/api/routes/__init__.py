from fastapi import FastAPI

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
)


def register_routes(app: FastAPI) -> None:
    """Attach all API routers to the FastAPI application."""
    app.include_router(health.router)
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
    app.include_router(ws_chat.router)  # WebSocket endpoints
