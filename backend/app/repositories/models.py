"""SQLAlchemy models for the single source of conversation truth."""

from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)


class MetadataEntry(Base):
    __tablename__ = "app_metadata"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    channel: Mapped[str] = mapped_column(default="web_demo")
    customer_ref: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="bot_active")
    reply_language: Mapped[str | None]
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    summary: Mapped[str | None]
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    last_message_at: Mapped[str | None]
    __table_args__ = (
        CheckConstraint("status IN ('bot_active','pending_human','human_active','resolved')"),
        CheckConstraint("reply_language IS NULL OR reply_language IN ('zh-CN','en-US','es-ES')"),
        CheckConstraint("version >= 1"),
        Index("idx_conversation_merchant_last_message", "merchant_id", "last_message_at"),
    )


class ConversationAlias(Base):
    __tablename__ = "conversation_aliases"
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), primary_key=True)
    alias: Mapped[str] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)


class RequestFailure(Base):
    __tablename__ = "request_failures"
    id: Mapped[str] = mapped_column(primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"))
    error_code: Mapped[str]
    created_at: Mapped[str]


class StoredMessage(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    seq: Mapped[int]
    role: Mapped[str]
    content: Mapped[str]
    tool_calls: Mapped[list | None] = mapped_column(JSON)
    tool_call_id: Mapped[str | None]
    name: Mapped[str | None]
    run_id: Mapped[str | None] = mapped_column(index=True)
    client_message_id: Mapped[str | None]
    created_at: Mapped[str]
    detected_language: Mapped[str | None]
    workflow: Mapped[dict | None] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_message_sequence"),
        CheckConstraint("role IN ('user','assistant','tool','human_agent')"),
        CheckConstraint("seq >= 1"),
        Index(
            "uq_message_client_id",
            "conversation_id",
            "client_message_id",
            unique=True,
            sqlite_where=text("client_message_id IS NOT NULL AND role='user'"),
        ),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    trigger_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"))
    model: Mapped[str]
    status: Mapped[str]
    error_code: Mapped[str | None]
    rounds: Mapped[int]
    tool_trace: Mapped[dict] = mapped_column(JSON)
    prompt_tokens: Mapped[int]
    completion_tokens: Mapped[int]
    latency_ms: Mapped[float]
    outcome: Mapped[dict] = mapped_column(JSON)
    analysis_source: Mapped[str]
    workflow: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str]
    __table_args__ = (
        CheckConstraint("status IN ('ok','error')"),
        Index("idx_run_merchant_created", "merchant_id", "created_at"),
    )


class HandoffTicket(Base):
    __tablename__ = "handoff_tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    trigger_message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"))
    reason_code: Mapped[str]
    reason_text: Mapped[str]
    issue_summary: Mapped[str | None]
    status: Mapped[str]
    created_at: Mapped[str]
    acknowledged_at: Mapped[str | None]
    resolved_at: Mapped[str | None]
    customer_message: Mapped[str]
    language_label: Mapped[str]
    intent_label: Mapped[str]
    __table_args__ = (
        CheckConstraint("status IN ('open','acknowledged','resolved')"),
        CheckConstraint("reason_code IN ('after_sales','user_request','guardrail')"),
        Index(
            "uq_handoff_unclosed",
            "conversation_id",
            unique=True,
            sqlite_where=text("status IN ('open','acknowledged')"),
        ),
        Index("idx_handoff_merchant_status_created", "merchant_id", "status", "created_at"),
    )


class StoredProduct(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), primary_key=True)
    name: Mapped[str]
    english_name: Mapped[str]
    category: Mapped[str]
    price_usd: Mapped[float]
    stock: Mapped[int]
    shipping_days: Mapped[str]
    aliases: Mapped[list] = mapped_column(JSON)
    specs: Mapped[dict] = mapped_column(JSON)


class StoredShippingRule(Base):
    __tablename__ = "shipping_rules"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    product_id: Mapped[str | None]
    destination_country: Mapped[str]
    available: Mapped[bool]
    days_text: Mapped[str]
    note: Mapped[str]
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "merchant_id"], ["products.id", "products.merchant_id"]
        ),
        Index("idx_shipping_destination", "merchant_id", "destination_country", "product_id"),
    )
