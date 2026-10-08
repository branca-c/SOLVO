"""Best-effort, single-process invalidation events; never part of a DB transaction."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Callable, Literal

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


@dataclass
class ClientConnection:
    lock: asyncio.Lock
    generation: int | None


class ConnectionManager:
    def __init__(self):
        self.clients: dict[WebSocket, ClientConnection] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self.generation_resolver: Callable[[], tuple[bool, int | None]] | None = None

    def set_generation_resolver(
        self, resolver: Callable[[], tuple[bool, int | None]]
    ):
        self.generation_resolver = resolver

    async def connect(
        self, socket: WebSocket, *, accepted: bool = False,
        generation: int | None = None,
    ):
        if not accepted:
            await socket.accept()
        self.loop = asyncio.get_running_loop()
        self.clients[socket] = ClientConnection(asyncio.Lock(), generation)

    def disconnect(self, socket: WebSocket):
        self.clients.pop(socket, None)

    async def _close_stale(self, socket: WebSocket):
        self.disconnect(socket)
        try:
            await asyncio.wait_for(socket.close(code=1008), timeout=1)
        except Exception:
            pass

    async def _send(
        self, socket: WebSocket, client: ClientConnection, event: dict,
        *, generation_guarded: bool, active_generation: int | None,
        event_generation: int | None,
    ):
        if generation_guarded and client.generation != active_generation:
            await self._close_stale(socket)
            return
        if generation_guarded and event_generation != active_generation:
            return
        try:
            # Bound both waiting for an earlier send and slow network writes.
            async with asyncio.timeout(2):
                async with client.lock:
                    if socket in self.clients:
                        await socket.send_json(event)
        except Exception:
            self.disconnect(socket)
            logger.warning('Realtime client disconnected during broadcast')
            try:
                await asyncio.wait_for(socket.close(code=1013), timeout=1)
            except Exception:
                pass

    async def broadcast(self, event: dict, generation: int | None = None):
        generation_guarded = False
        active_generation = None
        if self.generation_resolver is not None:
            try:
                generation_guarded, active_generation = await asyncio.to_thread(
                    self.generation_resolver
                )
            except Exception:
                logger.warning('Realtime generation validation failed')
                generation_guarded = True
        await asyncio.gather(*(
            self._send(
                socket, client, event,
                generation_guarded=generation_guarded,
                active_generation=active_generation,
                event_generation=generation,
            )
            for socket, client in list(self.clients.items())
        ))

    def submit(self, event: dict, generation: int | None = None):
        if not self.clients or self.loop is None:
            return
        # Services run in FastAPI's synchronous worker threads. Send on the socket loop.
        future = asyncio.run_coroutine_threadsafe(
            self.broadcast(event, generation), self.loop
        )
        def completed(result):
            try:
                result.result()
            except Exception:
                logger.warning('Realtime broadcast failed; committed data remains unchanged')
        future.add_done_callback(completed)


manager = ConnectionManager()


def publish(
    event_type: EventType, work_order_id: int, *, generation: int | None = None,
):
    try:
        if generation is None:
            from app.core.demo_access import demo_session_generation

            generation = demo_session_generation.get()
        event = RealtimeEvent(type=event_type, work_order_id=work_order_id, timestamp=datetime.now(timezone.utc))
        manager.submit(event.model_dump(mode='json'), generation)
    except Exception:
        logger.warning('Realtime publication failed; committed data remains unchanged')
