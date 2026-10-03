from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.modules.kot.websocket import kot_manager


async def kot_websocket_endpoint(websocket: WebSocket, outlet_id: int) -> None:
    await kot_manager.connect(outlet_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"event": "pong", "outlet_id": outlet_id})
    except WebSocketDisconnect:
        kot_manager.disconnect(outlet_id, websocket)
