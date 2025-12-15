from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session
from backend.services.chat_service import get_chat_service, ChatService
from backend.services.models import ChatMessage

router = APIRouter(prefix="/chat", tags=["chat"])


class SessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)


@router.post("/sessions")
def create_session(
    title: Optional[str] = None,
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    _, user = session_data
    session = chat_service.create_session(user["username"], title)
    return {"session": session.to_dict()}


@router.get("/sessions")
def list_sessions(
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    _, user = session_data
    sessions = chat_service.list_sessions(user["username"])
    return {"sessions": [s.to_dict() for s in sessions]}


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: str,
    payload: dict,
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    _, user = session_data
    session = chat_service.load_session(user["username"], session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    query = payload.get("query", "")
    user_message = ChatMessage(role="user", content=query)
    chat_service.append_message(session, user_message)
    chat_service.save_session(user["username"], session)

    def stream():
        generator, sources = chat_service.stream_response(
            query, user_id=user["username"], session_id=session_id
        )
        collected = ""
        for chunk in generator:
            collected += chunk
            yield chunk
        assistant_message = ChatMessage(
            role="assistant", content=collected, sources=sources
        )
        chat_service.append_message(session, assistant_message)
        chat_service.save_session(user["username"], session)

    return StreamingResponse(stream(), media_type="text/plain")


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    _, user = session_data
    session = chat_service.get_session(user["username"], session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session.to_dict()}


@router.patch("/sessions/{session_id}")
def update_session(
    session_id: str,
    payload: SessionUpdate,
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    _, user = session_data
    session = chat_service.rename_session(user["username"], session_id, payload.title.strip())
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session.to_dict()}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    _, user = session_data
    deleted = chat_service.delete_session(user["username"], session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
