import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.agent.llm.base import ModelResponse
from app.core.errors import AppError
from app.repositories.archive import WorkflowArchive
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
    archive: WorkflowArchive
    handoffs: HandoffService
    provider: ScriptedProvider
