from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    status: Literal["ok"] = "ok"
    data: T


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class SystemStatus(BaseModel):
    version: str
    llm_configured: bool
    model: str | None
    db_ok: bool


class CountItem(BaseModel):
    code: str
    label: str
    count: int


class DashboardOverview(BaseModel):
    total_conversations: int
    failed_requests: int
    human_handoffs: int
    pending_handoffs: int
    resolution_rate: float
    top_intent: str
    languages: list[CountItem]
    intents: list[CountItem]
    started_at: str


class RecentInquiry(BaseModel):
    id: str
    created_at: str
    session_id: str
    conversation_id: str
    message: str
    reply: str
    merchant_summary: str
    intent_label: str
    language_label: str
    needs_human: bool
    human_acknowledged: bool
    handoff_reason: str | None
    issue_summary: str | None


class Acknowledgment(BaseModel):
    record_id: str
