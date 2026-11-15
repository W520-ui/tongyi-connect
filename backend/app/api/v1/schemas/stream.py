from typing import Literal

from pydantic import BaseModel

from app.api.v1.schemas.agent import AgentWorkflowData
from app.domain.types import Intent, Language


class ToolStartedData(BaseModel):
    call_id: str
    round: int
    name: str
    args: dict


class ToolFinishedData(BaseModel):
    call_id: str
    round: int
    name: str
    ok: bool
    latency_ms: float
    error: str | None


class DeltaData(BaseModel):
    round: int
    text: str


class CompletedData(BaseModel):
    data: AgentWorkflowData


class AnalysisUpdate(BaseModel):
    analysis_source: Literal["llm", "heuristic"]
    intent: Intent
    intent_label: str
    detected_intents: list[Intent]
    detected_intent_labels: list[str]
    language: Language
    language_label: str
    task_plan: list[str]
    merchant_summary: str
    product_ids: list[str]
    needs_human: bool
    confidence: float


class StreamErrorData(BaseModel):
    code: str
    message: str


STREAM_SCHEMAS = {
    "tool_started": ToolStartedData,
    "tool_finished": ToolFinishedData,
    "delta": DeltaData,
    "completed": CompletedData,
    "analysis": AnalysisUpdate,
    "error": StreamErrorData,
}
