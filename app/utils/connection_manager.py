from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import WebSocket


class ConnectionManager:
    """
    In-memory connection tracking for:
    - Presence: global presence WS connections + last_seen timestamps
    - Chat: per-thread WS connection groups

    This is intentionally process-local (no external broker).
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

        # Presence
        # user_id -> active WebSocket connections
        self.presence_connections: Dict[str, set[WebSocket]] = {}
        # user_id -> last seen timestamp (updated on heartbeat + disconnect)
        self.presence_last_seen: Dict[str, datetime] = {}

        # Chat
        # thread_id -> active WebSocket connections
        self.chat_connections: Dict[str, set[WebSocket]] = {}
        # websocket -> metadata for routing/exclusion
        self.chat_socket_user: Dict[WebSocket, str] = {}
        self.chat_socket_thread: Dict[WebSocket, str] = {}

    async def connect_presence(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self.presence_connections.setdefault(user_id, set()).add(websocket)
            self.presence_last_seen[user_id] = datetime.now(timezone.utc)

    async def disconnect_presence(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self.presence_connections.get(user_id)
            if conns and websocket in conns:
                conns.remove(websocket)
                if not conns:
                    self.presence_connections.pop(user_id, None)
            # Mark as offline at disconnect time (last_seen remains meaningful).
            self.presence_last_seen[user_id] = datetime.now(timezone.utc)

    def is_user_online(self, user_id: str) -> bool:
        conns = self.presence_connections.get(user_id)
        return bool(conns)

    def get_last_seen(self, user_id: str) -> Optional[datetime]:
        return self.presence_last_seen.get(user_id)

    async def update_last_seen(self, user_id: str) -> None:
        async with self._lock:
            self.presence_last_seen[user_id] = datetime.now(timezone.utc)

    async def broadcast_to_presence(self, payload: Dict[str, Any]) -> None:
        async with self._lock:
            websockets: list[WebSocket] = []
            for conns in self.presence_connections.values():
                websockets.extend(list(conns))

        # Send outside the lock to avoid blocking other operations.
        for ws in websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                # If a websocket is dead, presence disconnect handler will clean it up.
                pass

    async def connect_chat(self, thread_id: str, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self.chat_connections.setdefault(thread_id, set()).add(websocket)
            self.chat_socket_user[websocket] = user_id
            self.chat_socket_thread[websocket] = thread_id

    async def disconnect_chat(self, websocket: WebSocket) -> None:
        async with self._lock:
            thread_id = self.chat_socket_thread.pop(websocket, None)
            self.chat_socket_user.pop(websocket, None)

            if thread_id:
                conns = self.chat_connections.get(thread_id)
                if conns and websocket in conns:
                    conns.remove(websocket)
                    if not conns:
                        self.chat_connections.pop(thread_id, None)

    async def broadcast_to_thread(
        self,
        thread_id: str,
        payload: Dict[str, Any],
        exclude_websocket: Optional[WebSocket] = None,
    ) -> None:
        async with self._lock:
            websockets = set(self.chat_connections.get(thread_id, set()))

        for ws in websockets:
            if exclude_websocket is not None and ws is exclude_websocket:
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    async def broadcast_typing(
        self,
        thread_id: str,
        typing_payload: Dict[str, Any],
        exclude_user_id: Optional[str] = None,
    ) -> None:
        async with self._lock:
            websockets = set(self.chat_connections.get(thread_id, set()))
            socket_user_map = dict(self.chat_socket_user)

        for ws in websockets:
            if exclude_user_id is not None and socket_user_map.get(ws) == exclude_user_id:
                continue
            try:
                await ws.send_json(typing_payload)
            except Exception:
                pass


# Shared singleton used by routers.
connection_manager = ConnectionManager()

