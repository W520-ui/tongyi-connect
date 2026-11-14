from __future__ import annotations

from typing import Any, Protocol

from app.agent.models import Decision, Message


class LLMProvider(Protocol):
    """Swap model vendors by implementing this single method."""

    @property
    def is_configured(self) -> bool: ...

    async def decide(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Decision: ...
