from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.domain.types import Message, ToolCall


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class ModelResponse:
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None
    usage: Usage | None = None


@dataclass(frozen=True)
class StreamChunk:
    content: str | None = None
    tool_calls: tuple[dict[str, Any], ...] = ()
    finish_reason: str | None = None
    usage: Usage | None = None


class LLMClient(Protocol):
    @property
    def is_configured(self) -> bool: ...

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, Any]] = (),
        tool_choice: Literal["auto", "none"] = "auto",
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse: ...

    def stream(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, Any]] = (),
        tool_choice: Literal["auto", "none"] = "auto",
    ) -> AsyncIterator[StreamChunk]: ...
