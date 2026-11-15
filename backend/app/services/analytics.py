from app.domain.types import INTENT_LABELS, LANGUAGE_LABELS
from app.repositories.archive import WorkflowArchive


class AnalyticsService:
    def __init__(self, archive: WorkflowArchive) -> None:
        self.archive = archive

    def snapshot(self) -> dict:
        stats = self.archive.aggregates()
        total, handoffs = stats["total"], stats["handoffs"]
        return {
            "total_conversations": total,
            "human_handoffs": handoffs,
            "pending_handoffs": stats["pending"],
            "failed_requests": stats["failures"],
            "resolution_rate": round((total - handoffs) / total * 100, 1) if total else 100.0,
            "top_intent": INTENT_LABELS.get(stats["intents"][0]["code"], "综合咨询")
            if stats["intents"]
            else "暂无数据",
            "languages": [
                {**item, "label": LANGUAGE_LABELS.get(item["code"], item["code"])}
                for item in stats["languages"]
            ],
            "intents": [
                {**item, "label": INTENT_LABELS.get(item["code"], item["code"])}
                for item in stats["intents"]
            ],
            "started_at": stats["started_at"],
        }

    def record_failed_request(self, code: str) -> None:
        self.archive.record_failure(code)

    def recent(self, limit: int = 8) -> list[dict]:
        return self.archive.recent(limit)
