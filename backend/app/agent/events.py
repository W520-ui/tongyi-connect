from dataclasses import dataclass
from typing import Any

from app.agent.effects import Effect
from app.agent.llm.base import Usage
from app.domain.types import Message, RunTrace


@dataclass(frozen=True)
class ToolStarted:
    call_id: str
    round: int
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolFinished:
    call_id: str
    round: int
    name: str
    ok: bool
    latency_ms: float
    error: str | None


@dataclass(frozen=True)
class TextDelta:
    round: int
    text: str


@dataclass(frozen=True)
class RunCompleted:
    reply: str
    effects: tuple[Effect, ...]
    trace: RunTrace
    usage: Usage | None
    messages: tuple[Message, ...]
    rounds: int


@dataclass(frozen=True)
class RunFailed:
    error_code: str
    message: str


AgentEvent = ToolStarted | ToolFinished | TextDelta | RunCompleted | RunFailed
