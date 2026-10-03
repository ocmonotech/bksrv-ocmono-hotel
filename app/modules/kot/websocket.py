from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class KotConnectionManager:
    """In-memory WebSocket manager for kitchen display updates."""

    def __init__(self) -> None:
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, outlet_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[outlet_id].append(websocket)
        await self.broadcast(
            outlet_id,
            {
                "event": "connection.established",
                "outlet_id": outlet_id,
                "message": "Connected to KOT stream",
            },
        )

    def disconnect(self, outlet_id: int, websocket: WebSocket) -> None:
        connections = self.active_connections.get(outlet_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and outlet_id in self.active_connections:
            del self.active_connections[outlet_id]

    async def broadcast(self, outlet_id: int, payload: dict) -> None:
        dead: list[WebSocket] = []
        for connection in self.active_connections.get(outlet_id, []):
            try:
                await connection.send_json(payload)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(outlet_id, connection)


kot_manager = KotConnectionManager()


async def notify_kot_event(outlet_id: int, event: str, data: dict) -> None:
    await kot_manager.broadcast(outlet_id, {"event": event, "outlet_id": outlet_id, "data": data})


def schedule_kot_event(outlet_id: int, event: str, data: dict) -> None:
    """Fire-and-forget broadcast from sync service code."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_kot_event(outlet_id, event, data))
    except RuntimeError:
        asyncio.run(notify_kot_event(outlet_id, event, data))
