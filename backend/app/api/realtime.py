import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.config import Settings, get_settings
from app.core.demo_access import has_demo_access
from app.services.realtime import manager

router = APIRouter()


@router.websocket('/ws/work-orders')
async def work_order_events(socket: WebSocket, settings: Settings = Depends(get_settings)):
    authenticated = False
    if settings.solvo_demo_access_enabled:
        await socket.accept()
        try:
            submitted_key = await asyncio.wait_for(socket.receive_text(), timeout=5)
        except (TimeoutError, WebSocketDisconnect):
            await socket.close(code=1008)
            return
        if not has_demo_access(submitted_key, settings):
            await socket.close(code=1008)
            return
        authenticated = True
        await socket.send_text('authorized')
    await manager.connect(socket, accepted=authenticated)
    try:
        while True:
            # This is a server-to-client feed, not a client command channel.
            await socket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        manager.disconnect(socket)
