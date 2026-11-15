import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.agent.llm.base import ModelResponse
from app.core.db import Database
from app.core.errors import AppError
from app.services.analytics import AnalyticsService
from app.services.conversation import ConversationService
from app.services.handoff import HandoffService


def Decision(reply=None, tool_calls=(), *, finish_reason="stop", usage=None):
    return ModelResponse(reply, tuple(tool_calls), finish_reason, usage)


class ScriptedProvider:
    def __init__(self, decisions=(), *, delay: float = 0.0, streams=()) -> None:
        self.decisions = deque(decisions)
        self.streams = deque(streams)
        self.calls: list[dict[str, Any]] = []
        self.delay = delay
        self.is_configured = True

    async def complete(
        self, messages, *, tools=(), tool_choice="auto", response_format=None
    ) -> ModelResponse:
        self.calls.append(
            {
                "messages": deepcopy(list(messages)),
                "tools": deepcopy(list(tools)),
                "tool_choice": tool_choice,
                "response_format": response_format,
            }
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.decisions:
            raise RuntimeError("Scripted model responses exhausted")
        decision = self.decisions.popleft()
        if isinstance(decision, AppError):
            raise decision
        return decision

    async def stream(self, messages, *, tools=(), tool_choice="auto"):
        self.calls.append(
            {
                "messages": deepcopy(list(messages)),
                "tools": deepcopy(list(tools)),
                "tool_choice": tool_choice,
            }
        )
        if not self.streams:
            raise RuntimeError("Scripted stream responses exhausted")
        for chunk in self.streams.popleft():
            if self.delay:
                await asyncio.sleep(self.delay)
            if isinstance(chunk, AppError):
                raise chunk
            yield chunk


@dataclass
class Runtime:
    service: ConversationService
    metrics: AnalyticsService
    database: Database
    handoffs: HandoffService
    provider: ScriptedProvider
    client: Any
    app: Any

    def call(self, function, *args):
        return self.client.portal.call(function, *args)

    def snapshot(self):
        return self.call(self.metrics.snapshot)

    def recent(self, limit=8):
        return self.call(self.metrics.recent, limit)

    def pending(self, limit=20):
        return self.call(self.handoffs.pending, limit)

    def session(self, key):
        return self.call(self.service.store.load, key)

    def rows(self, model):
        from sqlalchemy import select

        async def read():
            async with self.database.sessions() as transaction:
                return (await transaction.scalars(select(model))).all()

        return self.call(read)
