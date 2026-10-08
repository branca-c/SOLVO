import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.demo_access import has_demo_access
from app.db.session import get_db
from app.services import demo_sessions
from app.services.realtime import manager

router = APIRouter()


@router.websocket('/ws/work-orders')
async def work_order_events(
    socket: WebSocket,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    authenticated = False
    authenticated_generation = None
    if settings.solvo_demo_access_enabled or settings.solvo_demo_session_enabled:
        await socket.accept()
        try:
            submitted_key = await asyncio.wait_for(socket.receive_text(), timeout=5)
        except WebSocketDisconnect:
            return
        except TimeoutError:
            await socket.close(code=1008)
            return
        if not has_demo_access(submitted_key, settings):
            await socket.close(code=1008)
            return
        if settings.solvo_demo_session_enabled:
            await socket.send_text('demo-key-authorized')
            try:
                session_token = await asyncio.wait_for(socket.receive_text(), timeout=5)
                active_session = demo_sessions.require_active(db, session_token, settings)
                authenticated_generation = active_session.generation
                # Authentication is complete; do not retain a database read
                # transaction for the lifetime of this long-lived socket.
                db.rollback()
            except WebSocketDisconnect:
                return
            except (TimeoutError, demo_sessions.DemoSessionUnauthorizedError):
                db.rollback()
                await socket.close(code=1008)
                return
        authenticated = True
        await socket.send_text('authorized')
    await manager.connect(
        socket, accepted=authenticated, generation=authenticated_generation
    )
    try:
        while True:
            # This is a server-to-client feed, not a client command channel.
            await socket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        manager.disconnect(socket)
