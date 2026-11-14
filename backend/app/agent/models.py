from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal


class AgentError(Exception):
    """Agent runtime failure. ``status_code`` marks an upstream HTTP error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    tool_call_id: str | None = None
    name: str | None = None

    def to_openai(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            payload["tool_calls"] = [dict(call) for call in self.tool_calls]
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.name:
            payload["name"] = self.name
        return payload


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    reply: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any], AgentContext], Awaitable[ToolResult]]
    scopes: tuple[str, ...] = ()

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class Turn:
    role: str
    content: str
    created_at: str


@dataclass
class Session:
    session_id: str
    turns: list[Turn] = field(default_factory=list)
    last_product_id: str | None = None
    language: str | None = None
    updated_at: str = ""


@dataclass
class AgentContext:
    session_id: str
    session: Session
    analysis: Any
    locale: str = "zh-CN"
    language_override: str | None = None


@dataclass(frozen=True)
class CommandResult:
    reply: str
    needs_human: bool = False
    handoff_reason: str | None = None
    persist: bool = True
