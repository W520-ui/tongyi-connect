from dataclasses import dataclass, field
from typing import Any, Literal

Language = Literal["zh-CN", "en-US", "es-ES"]
Intent = Literal["quote", "logistics", "specs", "after_sales", "general"]
ReplySource = Literal["native", "native+human-handoff"]

INTENT_LABELS: dict[Intent, str] = {
    "quote": "询价",
    "logistics": "物流查询",
    "specs": "产品参数",
    "after_sales": "售后服务",
    "general": "综合咨询",
}
LANGUAGE_LABELS: dict[Language, str] = {"zh-CN": "中文", "en-US": "英语", "es-ES": "西班牙语"}


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    english_name: str
    category: str
    price_usd: float
    stock: int
    shipping_days: str
    aliases: tuple[str, ...]
    specs: dict[str, str]


@dataclass(frozen=True)
class ShippingRule:
    product_id: str | None
    destination_country: str
    available: bool
    days_text: str
    note: str


@dataclass(frozen=True)
class InboundMessage:
    message: str
    session_id: str | None = None
    username: str | None = None
    locale: str = "zh-CN"
    streaming: bool = False


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: Any


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    tool_call_id: str | None = None
    name: str | None = None

    def to_openai(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            payload["tool_calls"] = list(self.tool_calls)
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.name:
            payload["name"] = self.name
        return payload


@dataclass(frozen=True)
class Turn:
    role: str
    content: str
    created_at: str
    tool_calls: tuple[dict[str, Any], ...] = ()
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class Session:
    session_id: str
    turns: list[Turn] = field(default_factory=list)
    focused_product_ids: tuple[str, ...] = ()
    reply_language: Language | None = None
    detected_language: Language | None = None
    destination_country: str | None = None
    quantity: int | None = None
    updated_at: str = ""

    @property
    def last_product_id(self) -> str | None:
        return self.focused_product_ids[0] if self.focused_product_ids else None

    @property
    def language(self) -> Language | None:
        return self.reply_language


@dataclass(frozen=True)
class WorkflowAnalysis:
    language: Language
    intent: Intent
    intents: tuple[Intent, ...]
    confidence: float
    product: Product | None
    needs_human: bool
    handoff_reason: str | None
    product_confidence: float
    detected_language: Language
    requested_language: Language | None = None


@dataclass(frozen=True)
class ToolTraceEntry:
    call_id: str
    round: int
    name: str
    args: dict[str, Any]
    ok: bool
    latency_ms: float
    error: str | None = None


@dataclass(frozen=True)
class RunTrace:
    calls: tuple[ToolTraceEntry, ...] = ()
    truncated: bool = False


@dataclass(frozen=True)
class WorkflowResult:
    reply: str
    merchant_summary: str
    analysis: WorkflowAnalysis
    products: tuple[Product, ...]
    needs_human: bool
    handoff_reason: str | None
    issue_summary: str | None
    source: ReplySource
    session_id: str
    trace: RunTrace = field(default_factory=RunTrace)
    steps: tuple[str, ...] = ()
