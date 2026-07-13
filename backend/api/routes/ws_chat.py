"""
WebSocket Chat Route
Real-time chat using WebSocket for instant message streaming
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from backend.websocket.manager import manager
from backend.services.models import ChatMessage
from backend.logger import get_logger
from backend.rate_limiter import get_rate_limiter
import json
import asyncio

router = APIRouter(tags=["websocket"])
logger = get_logger(__name__)


def get_auth_service():
    from backend.auth_service import get_auth_service as _get_auth_service

    return _get_auth_service()


def get_chat_service():
    from backend.services.chat_service import get_chat_service as _get_chat_service

    return _get_chat_service()


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for real-time chat

    Authentication: HttpOnly cookie (access_token) only.
    SECURITY: Query param tokens are NOT supported — they leak into server logs,
    browser history, and HTTP Referer headers.

    Message Format:
        Client -> Server:
        {
            "type": "message",
            "content": "user message here"
        }

        Server -> Client:
        {
            "type": "chunk",
            "content": "response chunk"
        }
        OR
        {
            "type": "complete",
            "sources": [...]
        }
        OR
        {
            "type": "error",
            "message": "error message"
        }
    """

    # SECURITY: Only accept authentication via HttpOnly cookie
    effective_token = websocket.cookies.get("access_token")
    if not effective_token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    try:
        auth_service = get_auth_service()
        user = auth_service.validate_session(effective_token)
        user_id = user["username"]
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Invalid authentication token")
        return

    # Connect WebSocket
    await manager.connect(websocket, user_id)

    try:
        # Load chat session
        chat_service = get_chat_service()
        session = chat_service.load_session(user_id, session_id)

        # SECURITY: verify the session belongs to the authenticated user
        if not session or getattr(session, "owner", user_id) != user_id:
            await websocket.send_json({
                "type": "error",
                "message": f"Chat session {session_id} not found"
            })
            await websocket.close(code=1003, reason="Session not found")
            return

        logger.info(f"WebSocket chat started: user={user_id}, session={session_id}")

        # Main message loop
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)

                if message_data.get("type") == "message":
                    query = message_data.get("content", "").strip()

                    if not query:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Empty message"
                        })
                        continue

                    # Rate limit each message the same way the HTTP /chat
                    # route does -- an open WebSocket has no per-request
                    # gate otherwise, so a tight client loop could fire
                    # unlimited Bedrock calls for the life of the connection.
                    try:
                        rate_limiter = get_rate_limiter()
                        await rate_limiter.check_rate_limit(
                            websocket, limit=60, window=3600, scope="ws_chat_message"
                        )
                        from backend.config import config as app_config
                        if app_config.LLM_ROUTING_ENABLED:
                            from backend.llm_router import (
                                classify_query_complexity,
                                select_model_for_complexity,
                            )
                            tier, _ = classify_query_complexity(query)
                            effective_model = select_model_for_complexity(tier)
                        else:
                            effective_model = app_config.BEDROCK_MODEL_ID
                        await rate_limiter.check_model_rate_limit(websocket, effective_model)
                        await rate_limiter.check_cost_budget(websocket, effective_model)
                    except HTTPException as exc:
                        await websocket.send_json({
                            "type": "error",
                            "message": exc.detail.get("message", "Rate limit exceeded")
                            if isinstance(exc.detail, dict) else str(exc.detail),
                            "retry_after": exc.detail.get("retry_after") if isinstance(exc.detail, dict) else None,
                        })
                        continue

                    # Add user message to session
                    user_message = ChatMessage(role="user", content=query)
                    chat_service.append_message(session, user_message)
                    chat_service.save_session(user_id, session)

                    # Stream response
                    try:
                        # stream_response() itself does real blocking work before
                        # it returns a generator (profile lookup incl. a Neo4j
                        # call that can trip an Aura auto-resume attempt, RAG
                        # retrieval, agent routing) -- offload the call itself,
                        # not just the generator iteration below, or a slow or
                        # paused-Neo4j request blocks the whole event loop for
                        # every other connection this worker is serving.
                        generator, sources, _ = await asyncio.to_thread(
                            chat_service.stream_response,
                            query,
                            user_id=user_id,
                            session_id=session_id,
                        )

                        # Collect chunks in a thread-pool worker so the sync generator
                        # does not block the asyncio event loop, then stream to client.
                        chunks: list[str] = await asyncio.to_thread(list, generator)
                        full_response = ""
                        for chunk in chunks:
                            full_response += chunk
                            await websocket.send_json({
                                "type": "chunk",
                                "content": chunk
                            })

                        # Send completion message with sources
                        await websocket.send_json({
                            "type": "complete",
                            "sources": sources,
                            "full_response": full_response
                        })

                        # Save assistant message
                        assistant_message = ChatMessage(
                            role="assistant",
                            content=full_response,
                            sources=sources
                        )
                        chat_service.append_message(session, assistant_message)
                        chat_service.save_session(user_id, session)

                    except Exception as e:
                        logger.error(f"Error generating response: {e}", exc_info=True)
                        await websocket.send_json({
                            "type": "error",
                            "message": "An error occurred while generating the response"
                        })

                elif message_data.get("type") == "ping":
                    # Heartbeat/keepalive
                    await websocket.send_json({"type": "pong"})

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_data.get('type')}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": "An error occurred while processing the message"
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={user_id}, session={session_id}")
        manager.disconnect(websocket)

    except Exception as e:
        logger.error(f"Unexpected error in WebSocket: {e}", exc_info=True)
        manager.disconnect(websocket)


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket connection status (counts only, no user list)"""
    return {
        "total_connections": manager.get_total_connections(),
        "connected_users": len(manager.get_connected_users()),
    }
