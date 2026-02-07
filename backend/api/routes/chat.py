from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, status
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session
from backend.services.chat_service import get_chat_service, ChatService
from backend.services.research_service import get_research_service, ResearchService
from backend.services.share_service import get_share_service
from backend.services.message_feedback_service import (
    get_feedback_service,
    MessageFeedback,
    MessageFeedbackService,
    FeedbackType,
)
from backend.services.models import ChatMessage
from backend.validators import FileValidator
from backend.exceptions import InvalidFileError

router = APIRouter(prefix="/chat", tags=["chat"])


class ShareRequest(BaseModel):
    expires_in_hours: int = Field(default=168, ge=1, le=8760)  # 1 hour to 1 year


class ShareResponse(BaseModel):
    share_id: str
    share_url: str
    expires_at: str


class SharedSessionResponse(BaseModel):
    session: dict
    expires_at: str


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=80)
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None


class SendMessageRequest(BaseModel):
    """Request body for sending a chat message."""
    query: str = Field(..., min_length=1, max_length=10000)
    model_id: Optional[str] = Field(None, description="AWS Bedrock model ID to use")
    web_search_enabled: bool = Field(default=True)
    response_style: Optional[str] = Field(default=None)
    uploaded_only: bool = Field(default=False)
    uploaded_file_ids: Optional[List[str]] = None


class MessageFeedbackRequest(BaseModel):
    """Request body for submitting message feedback."""
    type: str = Field(..., pattern="^(thumbs_up|thumbs_down|report)$")
    reason: Optional[str] = Field(None, max_length=1000)


class MessageFeedbackResponse(BaseModel):
    """Response for feedback operations."""
    success: bool
    feedback_type: Optional[str] = None
    message: Optional[str] = None


@router.post("/uploads")
async def upload_chat_file(
    session_data=Depends(get_current_session),
    research_service: ResearchService = Depends(get_research_service),
    file: UploadFile = File(...),
):
    content = await file.read()
    try:
        sanitized_name = FileValidator.validate_file(
            file.filename or "uploaded-file", len(content)
        )
        preview = research_service.preview_file(content, sanitized_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InvalidFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"preview": preview}


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
    payload: SendMessageRequest,
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
    research_service: ResearchService = Depends(get_research_service),
):
    _, user = session_data
    session = chat_service.load_session(user["username"], session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    query = payload.query
    model_id = payload.model_id
    effective_query = query

    style_instructions = {
        "learning": "Respond with step-by-step explanations and short examples.",
        "concise": "Keep the response brief and to the point.",
        "explanatory": "Provide a detailed explanation with context and definitions.",
        "formal": "Use an academic, formal tone.",
    }
    if payload.response_style and payload.response_style in style_instructions:
        effective_query = (
            f"{style_instructions[payload.response_style]}\n\nUser question: {effective_query}"
        )

    if payload.uploaded_only:
        try:
            uploaded_results = research_service.query(
                query, uploaded_only=True
            ).get("results", [])
            if uploaded_results:
                context_snippets = "\n\n".join(
                    [r.get("text", "") for r in uploaded_results[:3] if r.get("text")]
                ).strip()
                if context_snippets:
                    effective_query = (
                        "Use the following uploaded document excerpts as context:\n"
                        f"{context_snippets}\n\nUser question: {query}"
                    )
        except Exception:
            pass

    if payload.web_search_enabled is False:
        effective_query = (
            "Do not use web search. Answer only from available context.\n\n"
            f"{effective_query}"
        )
    user_message = ChatMessage(role="user", content=query)
    chat_service.append_message(session, user_message)
    chat_service.save_session(user["username"], session)

    def stream():
        generator, sources = chat_service.stream_response(
            effective_query,
            user_id=user["username"],
            session_id=session_id,
            model_id=model_id,
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

    # Build update dict with only provided fields
    updates = {}
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.is_pinned is not None:
        updates["is_pinned"] = payload.is_pinned
    if payload.is_archived is not None:
        updates["is_archived"] = payload.is_archived

    if not updates:
        raise HTTPException(status_code=400, detail="No update fields provided")

    session = chat_service.update_session(user["username"], session_id, updates)
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


@router.post("/sessions/{session_id}/share", response_model=ShareResponse)
def share_session(
    session_id: str,
    request: ShareRequest,
    session_data=Depends(get_current_session),
    share_service=Depends(get_share_service),
):
    """Create a share link for a chat session."""
    _, user = session_data
    try:
        share_data = share_service.create_share_link(
            username=user["username"],
            session_id=session_id,
            expires_in_hours=request.expires_in_hours,
        )
        return ShareResponse(**share_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/share/{share_id}", response_model=SharedSessionResponse)
def get_shared_session(
    share_id: str,
    share_service=Depends(get_share_service),
):
    """Get a shared session by share ID."""
    share_data = share_service.get_shared_session(share_id)
    if share_data is None:
        raise HTTPException(
            status_code=404, detail="Shared session not found or expired"
        )
    return SharedSessionResponse(
        session=share_data["session_data"],
        expires_at=share_data["expires_at"],
    )


@router.delete("/share/{share_id}")
def revoke_share(
    share_id: str,
    session_data=Depends(get_current_session),
    share_service=Depends(get_share_service),
):
    """Revoke a share link."""
    success = share_service.revoke_share(share_id)
    if not success:
        raise HTTPException(status_code=404, detail="Share link not found")
    return {"success": True}


@router.post(
    "/sessions/{session_id}/messages/{message_index}/feedback",
    response_model=MessageFeedbackResponse,
)
def submit_message_feedback(
    session_id: str,
    message_index: int,
    request: MessageFeedbackRequest,
    session_data=Depends(get_current_session),
    chat_service: ChatService = Depends(get_chat_service),
    feedback_service: MessageFeedbackService = Depends(get_feedback_service),
):
    """
    Submit feedback for a specific message in a chat session.

    Supports thumbs_up, thumbs_down, and report types.
    For thumbs_up/thumbs_down, submitting the same type again will toggle it off.
    """
    _, user = session_data
    username = user["username"]

    # Validate session exists and message index is valid
    session = chat_service.get_session(username, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if message_index < 0 or message_index >= len(session.messages):
        raise HTTPException(status_code=400, detail="Invalid message index")

    # Check if the message is an assistant message (only assistant messages can receive feedback)
    message = session.messages[message_index]
    if message.role != "assistant":
        raise HTTPException(
            status_code=400,
            detail="Feedback can only be submitted for assistant messages"
        )

    feedback_type: FeedbackType = request.type  # type: ignore

    # For thumbs up/down, check if the same type already exists (toggle behavior)
    if feedback_type in ("thumbs_up", "thumbs_down"):
        existing = feedback_service.get_feedback_for_message(
            username, session_id, message_index
        )
        if existing and existing.feedback_type == feedback_type:
            # Same feedback exists, remove it (toggle off)
            feedback_service.remove_feedback(
                username, session_id, message_index, feedback_type
            )
            return MessageFeedbackResponse(
                success=True,
                feedback_type=None,
                message=f"Removed {feedback_type} feedback"
            )

    # Save the new feedback
    feedback = MessageFeedback(
        session_id=session_id,
        message_index=message_index,
        feedback_type=feedback_type,
        reason=request.reason,
    )
    feedback_service.save_feedback(username, feedback)

    return MessageFeedbackResponse(
        success=True,
        feedback_type=feedback_type,
        message=f"Feedback recorded: {feedback_type}"
    )


@router.get("/sessions/{session_id}/messages/{message_index}/feedback")
def get_message_feedback(
    session_id: str,
    message_index: int,
    session_data=Depends(get_current_session),
    feedback_service: MessageFeedbackService = Depends(get_feedback_service),
):
    """Get the current feedback for a specific message."""
    _, user = session_data
    username = user["username"]

    feedback = feedback_service.get_feedback_for_message(
        username, session_id, message_index
    )

    if feedback:
        return {"feedback_type": feedback.feedback_type}
    return {"feedback_type": None}


@router.get("/sessions/{session_id}/feedback")
def get_session_feedback(
    session_id: str,
    session_data=Depends(get_current_session),
    feedback_service: MessageFeedbackService = Depends(get_feedback_service),
):
    """Get all feedback for a session (for restoring UI state)."""
    _, user = session_data
    username = user["username"]

    feedback_list = feedback_service.get_feedback_for_session(username, session_id)

    # Return as a dict mapping message_index to feedback_type for easy lookup
    feedback_map = {}
    for fb in feedback_list:
        if fb.feedback_type in ("thumbs_up", "thumbs_down"):
            feedback_map[fb.message_index] = fb.feedback_type

    return {"feedback": feedback_map}
