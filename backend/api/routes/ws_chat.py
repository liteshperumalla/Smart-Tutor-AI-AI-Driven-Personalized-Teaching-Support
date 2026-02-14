"""
WebSocket Chat Route
Real-time chat using WebSocket for instant message streaming
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from backend.websocket.manager import manager
from backend.auth_service import get_auth_service
from backend.services.chat_service import get_chat_service
from backend.services.models import ChatMessage
from backend.logger import get_logger
import json
from typing import Optional

router = APIRouter(tags=["websocket"])
logger = get_logger(__name__)


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time chat

    NOTE: Token is accepted via query param because WebSocket API does not
    support custom headers. This is an accepted trade-off; prefer short-lived
    tokens and ensure reverse proxies strip query strings from access logs.

    Query Parameters:
        token: JWT access token for authentication

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

    # Authenticate user
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    try:
        auth_service = get_auth_service()
        user = auth_service.validate_session(token)
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

        if not session:
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

                    # Add user message to session
                    user_message = ChatMessage(role="user", content=query)
                    chat_service.append_message(session, user_message)
                    chat_service.save_session(user_id, session)

                    # Stream response
                    try:
                        generator, sources = chat_service.stream_response(
                            query,
                            user_id=user_id,
                            session_id=session_id
                        )

                        # Stream chunks to client
                        full_response = ""
                        async for chunk in generator:
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
