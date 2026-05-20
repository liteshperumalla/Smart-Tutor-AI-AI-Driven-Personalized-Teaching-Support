"""
WebSocket Connection Manager
Manages WebSocket connections for real-time features
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for users"""

    def __init__(self):
        # user_id -> list of websocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # websocket -> user_id mapping for quick lookup
        self.connection_users: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = []

        self.active_connections[user_id].append(websocket)
        self.connection_users[websocket] = user_id

        logger.info(f"WebSocket connected: user={user_id}, total_connections={len(self.active_connections[user_id])}")

        # Send connection confirmation
        await self.send_personal_message(
            json.dumps({
                "type": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "WebSocket connection established"
            }),
            user_id
        )

    def disconnect(self, websocket: WebSocket):
        """Disconnect and unregister a WebSocket connection"""
        user_id = self.connection_users.get(websocket)

        if user_id and user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)

            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

            del self.connection_users[websocket]

            logger.info(f"WebSocket disconnected: user={user_id}")

    async def send_personal_message(self, message: str, user_id: str):
        """Send message to all connections of a specific user"""
        if user_id in self.active_connections:
            disconnected = []

            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
                    disconnected.append(connection)

            # Clean up failed connections
            for conn in disconnected:
                self.disconnect(conn)

    async def send_json(self, data: dict, user_id: str):
        """Send JSON data to a specific user"""
        await self.send_personal_message(json.dumps(data), user_id)

    async def broadcast(self, message: str, exclude_user: Optional[str] = None):
        """Broadcast message to all connected users"""
        for user_id in list(self.active_connections.keys()):
            if exclude_user and user_id == exclude_user:
                continue

            await self.send_personal_message(message, user_id)

    async def broadcast_json(self, data: dict, exclude_user: Optional[str] = None):
        """Broadcast JSON data to all connected users"""
        await self.broadcast(json.dumps(data), exclude_user)

    def is_connected(self, user_id: str) -> bool:
        """Check if user has active connections"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def get_connection_count(self, user_id: str) -> int:
        """Get number of active connections for a user"""
        return len(self.active_connections.get(user_id, []))

    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())

    def get_connected_users(self) -> List[str]:
        """Get list of users with active connections"""
        return list(self.active_connections.keys())


# Global connection manager instance
manager = ConnectionManager()
