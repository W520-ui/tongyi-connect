import json

from sqlalchemy import func, select, text

from app.core.db import Database
from app.domain.types import INTENT_LABELS, LANGUAGE_LABELS
from app.repositories.models import (
    AgentRun,
    HandoffTicket,
    MetadataEntry,
    RequestFailure,
    StoredMessage,
)


class AnalyticsRepository:
    def __init__(self, database: Database, merchant_id="demo"):
        self.database, self.merchant_id = database, merchant_id

    async def snapshot(self):
        async with self.database.sessions() as session:
            total = await session.scalar(
                select(func.count())
                .select_from(StoredMessage)
                .where(StoredMessage.merchant_id == self.merchant_id, StoredMessage.role == "user")
            )
            failures = await session.scalar(
                select(func.count())
                .select_from(RequestFailure)
                .where(RequestFailure.merchant_id == self.merchant_id)
            )
            handoffs = await session.scalar(
                select(func.count())
                .select_from(HandoffTicket)
                .where(HandoffTicket.merchant_id == self.merchant_id)
            )
            pending = await session.scalar(
                select(func.count())
                .select_from(HandoffTicket)
                .where(
                    HandoffTicket.merchant_id == self.merchant_id, HandoffTicket.status == "open"
                )
            )
            labels = """
                SELECT m.id,
                    COALESCE(json_extract(r.outcome, '$.language'),
                        m.detected_language, 'zh-CN') AS language,
                    COALESCE(json_extract(r.outcome, '$.intents'), '["general"]') AS intents
                FROM messages AS m LEFT JOIN agent_runs AS r ON r.trigger_message_id=m.id
                WHERE m.merchant_id=:merchant AND m.role='user'
            """
            languages = (
                (
                    await session.execute(
                        text(
                            "SELECT language AS code, COUNT(*) AS count FROM ("
                            + labels
                            + ") GROUP BY language ORDER BY count DESC, language"
                        ),
                        {"merchant": self.merchant_id},
                    )
                )
                .mappings()
                .all()
            )
            intents = (
                (
                    await session.execute(
                        text(
                            "SELECT terms.value AS code, COUNT(DISTINCT labeled.id) AS count FROM ("
                            + labels
                            + ") AS labeled, json_each(labeled.intents) AS terms "
                            + "GROUP BY terms.value ORDER BY count DESC, terms.value"
                        ),
                        {"merchant": self.merchant_id},
                    )
                )
                .mappings()
                .all()
            )
            started = await session.get(MetadataEntry, "started_at")
        return {
            "total_conversations": total,
            "failed_requests": failures,
            "human_handoffs": handoffs,
            "pending_handoffs": pending,
            "resolution_rate": round((total - handoffs) / total * 100, 1) if total else 100.0,
            "top_intent": INTENT_LABELS.get(intents[0]["code"], "暂无数据")
            if intents
            else "暂无数据",
            "languages": [
                {"code": row["code"], "label": LANGUAGE_LABELS[row["code"]], "count": row["count"]}
                for row in languages
            ],
            "intents": [
                {"code": row["code"], "label": INTENT_LABELS[row["code"]], "count": row["count"]}
                for row in intents
            ],
            "started_at": started.value,
        }

    async def recent(self, limit=8):
        async with self.database.sessions() as session:
            rows = (
                await session.execute(
                    select(AgentRun, StoredMessage)
                    .join(StoredMessage, AgentRun.trigger_message_id == StoredMessage.id)
                    .where(AgentRun.merchant_id == self.merchant_id, AgentRun.status == "ok")
                    .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                    .limit(limit)
                )
            ).all()
            records = []
            for run, message in rows:
                result = run.workflow
                ticket = (
                    await session.get(HandoffTicket, result["handoff_id"])
                    if result.get("handoff_id")
                    else None
                )
                analysis = result["analysis"]
                records.append(
                    {
                        "id": run.id,
                        "conversation_id": run.conversation_id,
                        "session_id": run.conversation_id,
                        "created_at": run.created_at,
                        "message": message.content[:180],
                        "reply": result["reply"][:240],
                        "merchant_summary": result["merchant_summary"][:240],
                        "intent_label": INTENT_LABELS[analysis["intent"]],
                        "language_label": LANGUAGE_LABELS[analysis["language"]],
                        "needs_human": result["needs_human"],
                        "human_acknowledged": bool(ticket and ticket.acknowledged_at),
                        "handoff_reason": result["handoff_reason"],
                        "issue_summary": result.get("issue_summary"),
                        "tool_trace": json.dumps(run.tool_trace, ensure_ascii=False),
                    }
                )
            return records

    async def pending(self, limit=20):
        async with self.database.sessions() as session:
            rows = (
                await session.execute(
                    select(HandoffTicket, AgentRun)
                    .outerjoin(
                        AgentRun,
                        (AgentRun.trigger_message_id == HandoffTicket.trigger_message_id)
                        & (AgentRun.merchant_id == HandoffTicket.merchant_id)
                        & (AgentRun.status == "ok"),
                    )
                    .where(
                        HandoffTicket.merchant_id == self.merchant_id,
                        HandoffTicket.status == "open",
                    )
                    .order_by(HandoffTicket.created_at.desc(), HandoffTicket.id.desc())
                    .limit(limit)
                )
            ).all()
            return [
                {
                    "id": ticket.id,
                    "conversation_id": ticket.conversation_id,
                    "session_id": ticket.conversation_id,
                    "created_at": ticket.created_at,
                    "message": ticket.customer_message[:180],
                    "reply": run.workflow["reply"][:240] if run else "",
                    "merchant_summary": (
                        run.workflow["merchant_summary"]
                        if run
                        else ticket.issue_summary or ticket.reason_text
                    )[:240],
                    "intent_label": INTENT_LABELS[run.workflow["analysis"]["intent"]]
                    if run
                    else ticket.intent_label,
                    "language_label": LANGUAGE_LABELS[run.workflow["analysis"]["language"]]
                    if run
                    else ticket.language_label,
                    "needs_human": True,
                    "human_acknowledged": False,
                    "handoff_reason": ticket.reason_text,
                    "issue_summary": ticket.issue_summary,
                }
                for ticket, run in rows
            ]
