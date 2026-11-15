from app.agent.llm.base import LLMClient
from app.core.config import Settings
from app.repositories.archive import WorkflowArchive


class StatusService:
    def __init__(self, settings: Settings, client: LLMClient, archive: WorkflowArchive) -> None:
        self.settings, self.client, self.archive = settings, client, archive

    def snapshot(self) -> dict:
        configured = self.client.is_configured
        return {
            "version": self.settings.app_version,
            "llm_configured": configured,
            "model": self.settings.llm_model if configured else None,
            "db_ok": self.archive.ping(),
        }
