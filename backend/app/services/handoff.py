from app.repositories.archive import WorkflowArchive


class HandoffService:
    def __init__(self, archive: WorkflowArchive) -> None:
        self.archive = archive

    def pending_for(self, session_id: str) -> dict | None:
        return self.archive.existing_handoff(session_id)

    def pending(self, limit: int = 20) -> list[dict]:
        return self.archive.handoffs(limit)

    def acknowledge(self, record_id: str) -> bool:
        return self.archive.acknowledge(record_id)
