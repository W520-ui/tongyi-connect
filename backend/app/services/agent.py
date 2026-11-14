from typing import Any

from app.agent.engine import AgentEngine
from app.schemas.agent import AgentChatRequest


class AgentService:
    """Thin adapter between the HTTP layer and the in-process agent runtime."""

    def __init__(self, engine: AgentEngine) -> None:
        self.engine = engine

    async def chat(self, request: AgentChatRequest) -> dict[str, Any]:
        return await self.engine.chat(request)
