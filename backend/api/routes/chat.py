import asyncio
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request, status
from fastapi.responses import StreamingResponse
from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session, get_rate_limiter_dep
from backend import posthog_tracker
from backend.csrf_protection import csrf_protect
from backend.rate_limiter import PerUserRateLimiter
from backend.services.models import ChatMessage
from backend.validators import FileValidator
from backend.exceptions import InvalidFileError

if TYPE_CHECKING:
    from backend.services.chat_service import ChatService
    from backend.services.message_feedback_service import MessageFeedbackService
    from backend.services.research_service import ResearchService

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service():
    from backend.services.chat_service import get_chat_service as _get_chat_service

    return _get_chat_service()


def get_llm_semaphore():
    from backend.services.chat_service import get_llm_semaphore as _get_llm_semaphore

    return _get_llm_semaphore()


def get_research_service():
    from backend.services.research_service import get_research_service as _get_research_service

    return _get_research_service()


def get_share_service():
    from backend.services.share_service import get_share_service as _get_share_service

    return _get_share_service()


def get_feedback_service():
    from backend.services.message_feedback_service import (
        get_feedback_service as _get_feedback_service,
    )

    return _get_feedback_service()


class ShareRequest(BaseModel):
    expires_in_hours: int = Field(default=168, ge=1, le=8760)  # 1 hour to 1 year


class ShareResponse(BaseModel):
    share_id: str
    share_url: str
    expires_at: str


class SharedSessionResponse(BaseModel):
    session: dict
    expires_at: str


class SharedSessionInfoResponse(BaseModel):
    title: str
    message_count: int
    created_at: Optional[str] = None
    expires_at: str


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=80)
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None


class AttachmentInfo(BaseModel):
    """Metadata for a file attached to a chat message."""
    name: str = Field(..., max_length=255)
    ext: str = Field(..., max_length=20)
    isImage: bool = False


class SendMessageRequest(BaseModel):
    """Request body for sending a chat message."""
    query: str = Field(..., min_length=1, max_length=10000)
    model_id: Optional[str] = Field(None, description="AWS Bedrock model ID to use")
    web_search_enabled: bool = Field(default=True)
    response_style: Optional[str] = Field(default=None)
    uploaded_only: bool = Field(default=False)
    uploaded_file_ids: Optional[List[str]] = None
    attachments: Optional[List[AttachmentInfo]] = None


class MessageFeedbackRequest(BaseModel):
    """Request body for submitting message feedback."""
    type: str = Field(..., pattern="^(thumbs_up|thumbs_down|report)$")
    reason: Optional[str] = Field(None, max_length=1000)


class MessageFeedbackResponse(BaseModel):
    """Response for feedback operations."""
    success: bool
    feedback_type: Optional[str] = None
    message: Optional[str] = None


class ShareActionRequest(BaseModel):
    channel: str = Field(
        ...,
        pattern="^(copy_link|x|linkedin|reddit|whatsapp|email|native_share)$",
    )
    share_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


@router.post("/uploads")
async def upload_chat_file(
    session_data=Depends(get_current_session),
    file: UploadFile = File(...),
):
    content = await file.read()
    try:
        if len(content) == 0:
            raise ValueError("File is empty")

        sanitized_name = FileValidator.validate_file(
            file.filename or "uploaded-file", len(content)
        )
        if os.getenv("ENVIRONMENT") == "test":
            return {
                "preview": {
                    "filename": sanitized_name,
                    "content_type": file.content_type,
                    "size_bytes": len(content),
                }
            }

        research_service = get_research_service()
        preview = research_service.preview_file(content, sanitized_name)
    except (ValueError, InvalidFileError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        # Catch file-parsing errors (e.g. pymupdf FileDataError, EmptyFileError)
        # and return 400 — malformed/empty files are a client error, not a server error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File could not be processed: {exc}"
        )
    return {"preview": preview}


@router.post("/sessions")
def create_session(
    title: Optional[str] = None,
    session_data=Depends(get_current_session),
    chat_service: "ChatService" = Depends(get_chat_service),
):
    _, user = session_data
    session = chat_service.create_session(user["username"], title)
    return {"session": session.to_dict()}


@router.get("/sessions")
def list_sessions(
    session_data=Depends(get_current_session),
    chat_service: "ChatService" = Depends(get_chat_service),
):
    _, user = session_data
    sessions = chat_service.list_sessions(user["username"])
    return {"sessions": [s.to_dict() for s in sessions]}


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    payload: SendMessageRequest,
    request: Request,
    session_data=Depends(get_current_session),
    chat_service: "ChatService" = Depends(get_chat_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    _, user = session_data
    session = chat_service.load_session(user["username"], session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    query = payload.query
    model_id = payload.model_id

    posthog_tracker.capture(
        distinct_id=user["username"],
        event="chat_message_sent",
        properties={
            "session_id":      session_id,
            "message_length":  len(query),
            "model_requested": model_id or "auto",
            "response_style":  payload.response_style,
            "uploaded_only":   payload.uploaded_only,
            "has_file_ids":    bool(payload.uploaded_file_ids),
        },
    )
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
            research_service = get_research_service()
            # When specific file IDs are provided, fetch all their chunks directly
            if payload.uploaded_file_ids:
                uploaded_results = research_service.get_chunks_by_file_ids(
                    payload.uploaded_file_ids
                )
            else:
                uploaded_results = research_service.query(
                    query, uploaded_only=True
                ).get("results", [])
            if uploaded_results:
                context_snippets = "\n\n".join(
                    [r.get("text", "") for r in uploaded_results[:10] if r.get("text")]
                ).strip()
                if context_snippets:
                    effective_query = (
                        "Use the following uploaded document excerpts as context. "
                        "Base your answer on this content:\n"
                        f"{context_snippets}\n\nUser question: {query}"
                    )
        except Exception as _exc:  # context fetch failure is non-fatal; log and continue
            _logger.debug("Uploaded-only context lookup failed: %s", _exc)

    if payload.web_search_enabled is False:
        effective_query = (
            "Do not use web search. Answer only from available context.\n\n"
            f"{effective_query}"
        )
    attachment_dicts = (
        [a.model_dump() for a in payload.attachments] if payload.attachments else None
    )
    user_message = ChatMessage(role="user", content=query, attachments=attachment_dicts)

    # Pre-check: resolve model for rate limiting without triggering the full pipeline
    from backend.config import config as app_config
    if model_id:
        effective_model = model_id
    elif app_config.LLM_ROUTING_ENABLED:
        from backend.llm_router import classify_query_complexity, select_model_for_complexity
        tier, _ = classify_query_complexity(effective_query)
        effective_model = select_model_for_complexity(tier)
    else:
        effective_model = app_config.BEDROCK_MODEL_ID
    await rate_limiter.check_model_rate_limit(request, effective_model)

    # Resolve the generator before opening the stream — this lets FastAPI return
    # a proper 503 JSON body if the circuit is open or the LLM is unavailable,
    # rather than sending a partial streamed response then aborting.
    from backend.circuit_breaker import CircuitBreakerOpenError, bedrock_circuit_breaker
    try:
        generator, sources, resolved_model_id = chat_service.stream_response(
            effective_query,
            user_id=user["username"],
            session_id=session_id,
            model_id=model_id,
        )
    except CircuitBreakerOpenError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "LLM service temporarily unavailable", "retry_after": int(e.retry_after)},
        )

    # Save user message only after all pre-flight checks pass — avoids orphaned
    # messages in session history when the request is rejected by rate-limiter
    # or circuit-breaker.
    chat_service.append_message(session, user_message)
    chat_service.save_session(user["username"], session)

    # Acquire a concurrency slot — awaited via asyncio.to_thread so the event
    # loop is not blocked while waiting for a slot (up to 5 s).
    sem = get_llm_semaphore()
    acquired = await asyncio.to_thread(sem.acquire, True, 5)
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail={"error": "Server busy — too many concurrent requests", "retry_after": 5},
        )

    def stream():
        import time as _time
        from backend.llmops import record_llm_call
        _stream_start = _time.time()
        _stream_failed = False
        collected = ""
        try:
            # Emit auto-routed model info when user didn't specify a model
            if not model_id and resolved_model_id:
                import json
                meta = json.dumps({"model_used": resolved_model_id})
                yield f"__AGENT_META__{meta}\n"
            for chunk in generator:
                collected += chunk
                yield chunk
            bedrock_circuit_breaker._on_success()
        except Exception:
            _stream_failed = True
            bedrock_circuit_breaker._on_failure()
            raise
        finally:
            sem.release()
            _latency_ms = (_time.time() - _stream_start) * 1000
            _model = resolved_model_id or "unknown"
            _output_tokens = max(1, len(collected) // 4)
            _input_tokens = max(1, len(query) // 4)

            # Approximate cost in USD based on model pricing (per 1K tokens)
            _PRICING = {
                "meta.llama3-70b-instruct-v1:0":          (0.00265, 0.00350),
                "us.meta.llama3-1-70b-instruct-v1:0":     (0.00265, 0.00350),
                "us.anthropic.claude-3-5-sonnet-20241022-v2:0": (0.00300, 0.01500),
                "us.anthropic.claude-3-haiku-20240307-v1:0":    (0.00025, 0.00125),
                "amazon.titan-embed-text-v2:0":            (0.00020, 0.00000),
            }
            _in_price, _out_price = _PRICING.get(_model, (0.00265, 0.00350))
            _cost_usd = round(
                (_input_tokens / 1000 * _in_price) + (_output_tokens / 1000 * _out_price), 6
            )

            # LLMOps: record call telemetry (fire-and-forget, never raises)
            record_llm_call(
                model=_model,
                latency_ms=_latency_ms,
                output_chars=len(collected),
                success=not _stream_failed,
                user_id=user["username"],
                session_id=session_id,
                input_text=query,
                output_text=collected,
                input_tokens=_input_tokens,
                output_tokens=_output_tokens,
                cost_usd=_cost_usd,
            )

            # PostHog $ai_generation — powers the LLM Analytics dashboard
            try:
                posthog_tracker.capture(
                    distinct_id=user["username"],
                    event="$ai_generation",
                    properties={
                        "$ai_model":           _model,
                        "$ai_provider":        "aws_bedrock",
                        "$ai_input_tokens":    _input_tokens,
                        "$ai_output_tokens":   _output_tokens,
                        "$ai_latency":         round(_latency_ms / 1000, 3),
                        "$ai_total_cost_usd":  _cost_usd,
                        "$ai_trace_id":        session_id,
                        "$ai_http_status":     200 if not _stream_failed else 500,
                        # extra context
                        "session_id":          session_id,
                        "success":             not _stream_failed,
                        "response_style":      payload.response_style,
                    },
                )
            except Exception:
                pass
            # Save even when the client disconnects mid-stream (GeneratorExit).
            # No yield allowed inside finally — that would raise RuntimeError.
            if collected:
                clean_content = collected
                if clean_content.startswith("__AGENT_META__"):
                    newline_idx = clean_content.find("\n")
                    if newline_idx != -1:
                        clean_content = clean_content[newline_idx + 1:]
                assistant_message = ChatMessage(
                    role="assistant", content=clean_content, sources=sources
                )
                chat_service.append_message(session, assistant_message)
                chat_service.save_session(user["username"], session)

    return StreamingResponse(stream(), media_type="text/plain")


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    session_data=Depends(get_current_session),
    chat_service: "ChatService" = Depends(get_chat_service),
):
    _, user = session_data
    session = chat_service.get_session(user["username"], session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session.to_dict()}


@router.patch("/sessions/{session_id}", dependencies=[Depends(csrf_protect)])
def update_session(
    session_id: str,
    payload: SessionUpdate,
    session_data=Depends(get_current_session),
    chat_service: "ChatService" = Depends(get_chat_service),
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


@router.delete("/sessions/{session_id}", dependencies=[Depends(csrf_protect)])
def delete_session(
    session_id: str,
    session_data=Depends(get_current_session),
    chat_service: "ChatService" = Depends(get_chat_service),
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


@router.get("/share/{share_id}/info", response_model=SharedSessionInfoResponse)
def get_shared_session_info(
    share_id: str,
    share_service=Depends(get_share_service),
):
    share_info = share_service.get_shared_session_info(share_id)
    if share_info is None:
        raise HTTPException(
            status_code=404, detail="Shared session not found or expired"
        )
    return SharedSessionInfoResponse(**share_info)


@router.delete("/share/{share_id}", dependencies=[Depends(csrf_protect)])
def revoke_share(
    share_id: str,
    session_data=Depends(get_current_session),
    share_service=Depends(get_share_service),
):
    """Revoke a share link. The requesting user must own the share."""
    _, user = session_data
    success = share_service.revoke_share(share_id, user["username"])
    if not success:
        raise HTTPException(status_code=404, detail="Share link not found")
    return {"success": True}


@router.post("/sessions/{session_id}/share-events", dependencies=[Depends(csrf_protect)])
def track_share_event(
    session_id: str,
    request: ShareActionRequest,
    session_data=Depends(get_current_session),
    chat_service: "ChatService" = Depends(get_chat_service),
    share_service=Depends(get_share_service),
):
    _, user = session_data
    session = chat_service.get_session(user["username"], session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    share_service.log_share_action(
        username=user["username"],
        session_id=session_id,
        channel=request.channel,
        share_id=request.share_id,
    )
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
    chat_service: "ChatService" = Depends(get_chat_service),
    feedback_service: "MessageFeedbackService" = Depends(get_feedback_service),
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

    from backend.services.message_feedback_service import MessageFeedback

    feedback_type = request.type

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

    # LLMOps: track satisfaction signal in Prometheus
    if feedback_type in ("thumbs_up", "thumbs_down"):
        try:
            from backend.metrics import track_llm_satisfaction
            track_llm_satisfaction(vote=feedback_type)
        except Exception:
            pass

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
    feedback_service: "MessageFeedbackService" = Depends(get_feedback_service),
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
    feedback_service: "MessageFeedbackService" = Depends(get_feedback_service),
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


@router.get("/model-limits")
async def get_model_limits(
    request: Request,
    session_data=Depends(get_current_session),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Get per-model rate limit status for the current user."""
    return await rate_limiter.get_all_model_limits(request)
