from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.realtime import manager

router = APIRouter()


@router.websocket('/ws/work-orders')
async def work_order_events(socket: WebSocket):
    await manager.connect(socket)
    try:
        while True:
            # This is a server-to-client feed, not a client command channel.
            await socket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        manager.disconnect(socket)
