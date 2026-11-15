from app.agent.llm.base import LLMClient
from app.core.config import Settings
from app.core.db import Database


class StatusService:
    def __init__(self, settings: Settings, llm: LLMClient, database: Database):
        self.settings, self.llm, self.database = settings, llm, database

    async def snapshot(self):
        configured = self.llm.is_configured
        return {
            "version": self.settings.app_version,
            "llm_configured": configured,
            "model": self.settings.llm_model if configured else None,
            "db_ok": await self.database.ping(),
        }
