import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Protocol

from app.core.errors import AppError


class ConversationLocks(Protocol):
    def hold(self, session_id: str) -> AbstractAsyncContextManager[None]: ...


@dataclass
class _Slot:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


class LocalConversationLocks:
    def __init__(self, wait_timeout: float = 30) -> None:
        self.wait_timeout = wait_timeout
        self._slots: dict[str, _Slot] = {}

    @asynccontextmanager
    async def hold(self, session_id: str) -> AsyncIterator[None]:
        slot = self._slots.setdefault(session_id, _Slot())
        slot.users += 1
        acquired = False
        try:
            try:
                async with asyncio.timeout(self.wait_timeout):
                    await slot.lock.acquire()
                acquired = True
            except TimeoutError:
                raise AppError("CONVERSATION_BUSY") from None
            yield
        finally:
            if acquired:
                slot.lock.release()
            slot.users -= 1
            if slot.users == 0:
                self._slots.pop(session_id, None)
