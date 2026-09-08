"""Best-effort, single-process invalidation events; never part of a DB transaction."""
import asyncio
from datetime import datetime, timezone
import logging
from typing import Literal

from fastapi import WebSocket
from pydantic import BaseModel

logger = logging.getLogger(__name__)
EventType = Literal[
    'work_order.created', 'work_order.updated', 'work_order.deleted',
    'work_order.status_changed', 'reminder.created', 'assignment.created',
    'assignment.accepted', 'assignment.rejected', 'assignment.no_response',
    'assignment.escalated', 'assignment.notification_sent',
]


class RealtimeEvent(BaseModel):
    type: EventType
    work_order_id: int
    timestamp: datetime


class ConnectionManager:
    def __init__(self):
        self.clients: dict[WebSocket, asyncio.Lock] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, socket: WebSocket):
        await socket.accept()
        self.loop = asyncio.get_running_loop()
        self.clients[socket] = asyncio.Lock()

    def disconnect(self, socket: WebSocket):
        self.clients.pop(socket, None)

    async def _send(self, socket: WebSocket, lock: asyncio.Lock, event: dict):
        try:
            # Bound both waiting for an earlier send and slow network writes.
            async with asyncio.timeout(2):
                async with lock:
                    if socket in self.clients:
                        await socket.send_json(event)
        except Exception:
            self.disconnect(socket)
            logger.warning('Realtime client disconnected during broadcast')
            try:
                await asyncio.wait_for(socket.close(code=1013), timeout=1)
            except Exception:
                pass

    async def broadcast(self, event: dict):
        await asyncio.gather(*(self._send(socket, lock, event) for socket, lock in list(self.clients.items())))

    def submit(self, event: dict):
        if not self.clients or self.loop is None:
            return
        # Services run in FastAPI's synchronous worker threads. Send on the socket loop.
        future = asyncio.run_coroutine_threadsafe(self.broadcast(event), self.loop)
        def completed(result):
            try:
                result.result()
            except Exception:
                logger.warning('Realtime broadcast failed; committed data remains unchanged')
        future.add_done_callback(completed)


manager = ConnectionManager()


def publish(event_type: EventType, work_order_id: int):
    try:
        event = RealtimeEvent(type=event_type, work_order_id=work_order_id, timestamp=datetime.now(timezone.utc))
        manager.submit(event.model_dump(mode='json'))
    except Exception:
        logger.warning('Realtime publication failed; committed data remains unchanged')
