from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.schemas.agent import AgentWorkflowData
from app.domain.types import ConversationStatus, Language


class CreateConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply_language: Language | None = None


class UpdateConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply_language: Language | None


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=20_000)
    client_message_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value):
        return value.strip() if isinstance(value, str) else value


class RequestHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason_text: str = Field(default="用户主动请求人工接管", min_length=1)


class ConversationState(BaseModel):
    focused_product_ids: list[str]
    destination_country: str | None
    quantity: int | None


class HandoffTicket(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    conversation_id: str
    status: Literal["open", "acknowledged", "resolved"]
    reason_code: Literal["after_sales", "user_request", "guardrail"]
    reason_text: str
    issue_summary: str | None
    customer_message: str
    language_label: str
    intent_label: str
    created_at: str
    acknowledged_at: str | None
    resolved_at: str | None


class Conversation(BaseModel):
    id: str
    status: ConversationStatus
    reply_language: Language | None
    state: ConversationState
    open_handoff: HandoffTicket | None
    created_at: str
    updated_at: str
    last_message_at: str | None


class HistoryMessage(BaseModel):
    id: str
    seq: int
    role: Literal["user", "assistant", "human_agent"]
    content: str
    created_at: str
    client_message_id: str | None
    workflow: AgentWorkflowData | None


class MessagePage(BaseModel):
    items: list[HistoryMessage]
    has_more: bool


class ResetConversation(BaseModel):
    previous_conversation_id: str
    conversation: Conversation


class HandoffResult(BaseModel):
    conversation: Conversation
    ticket: HandoffTicket


class HandoffList(BaseModel):
    items: list[HandoffTicket]
