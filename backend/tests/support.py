"""Scripted model and runtime fixtures shared by regression tests."""

import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.agent.engine import AgentEngine
from app.agent.models import AgentError, Decision, Message
from app.services.workflow import WorkflowMetrics


class ScriptedProvider:
    def __init__(self, decisions=(), *, delay: float = 0.0) -> None:
        self.decisions = deque(decisions)
        self.calls: list[dict[str, Any]] = []
        self.delay = delay
        self.is_configured = True

    async def decide(self, messages: list[Message], tools: list[dict[str, Any]]) -> Decision:
        self.calls.append({"messages": deepcopy(messages), "tools": deepcopy(tools)})
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.decisions:
            raise RuntimeError("Scripted model responses exhausted")
        decision = self.decisions.popleft()
        if isinstance(decision, AgentError):
            raise decision
        return decision


@dataclass
class Runtime:
    engine: AgentEngine
    metrics: WorkflowMetrics
    provider: ScriptedProvider
