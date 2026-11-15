from pydantic import BaseModel, ConfigDict, Field

from app.domain.types import Intent, Language, ReplySource


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    english_name: str
    category: str
    price_usd: float
    stock: int
    shipping_days: str
    specs: dict[str, str]


class ToolTraceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    call_id: str
    round: int
    name: str
    args: dict
    ok: bool
    latency_ms: float
    error: str | None


class AgentFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enable_streaming: bool = False


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=20_000)
    session_id: str | None = None
    username: str | None = None
    locale: str = "zh-CN"
    flags: AgentFlags = Field(default_factory=AgentFlags)


class AgentWorkflowData(BaseModel):
    reply: str
    merchant_summary: str
    intent: Intent
    intent_label: str
    detected_intents: list[Intent]
    detected_intent_labels: list[str]
    task_plan: list[str]
    language: Language
    language_label: str
    confidence: float
    product_confidence: float
    matched_product: str
    product_id: str | None
    matched_products: list[ProductSchema]
    needs_human: bool
    handoff_reason: str | None
    steps: list[str]
    source: ReplySource
    session_id: str
    trace: list[ToolTraceSchema]


class AgentChatResponse(BaseModel):
    status: str
    data: AgentWorkflowData
    message: str | None = None
