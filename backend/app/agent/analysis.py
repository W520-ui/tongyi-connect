import asyncio
import json
import logging
import re
from dataclasses import dataclass

from app.agent.llm.base import LLMClient, Usage
from app.core.errors import UnsupportedResponseFormat
from app.domain.types import Message, WorkflowAnalysis

logger = logging.getLogger(__name__)
INTENTS = ("quote", "logistics", "specs", "after_sales", "general")
LANGUAGES = ("zh-CN", "en-US", "es-ES")
OUTCOME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intents": {"type": "array", "items": {"type": "string", "enum": list(INTENTS)}},
        "language": {"type": "string", "enum": list(LANGUAGES)},
        "product_ids": {"type": "array", "items": {"type": "string"}},
        "needs_human": {"type": "boolean"},
        "handoff_reason": {"type": ["string", "null"]},
        "merchant_summary_zh": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}
OUTCOME_SCHEMA["required"] = list(OUTCOME_SCHEMA["properties"])


@dataclass(frozen=True)
class AnalysisResult:
    outcome: dict
    source: str
    usage: Usage | None = None


def heuristic_outcome(message: str, analysis: WorkflowAnalysis, products, needs_human, reason):
    names = "、".join(product.name for product in products) or "未识别商品"
    return {
        "intents": list(analysis.intents),
        "language": analysis.language,
        "product_ids": [product.id for product in products],
        "needs_human": needs_human,
        "handoff_reason": reason,
        "confidence": analysis.confidence,
        "merchant_summary_zh": (
            f"商品：{names}；处理建议：{'需要人工接管' if needs_human else '继续咨询'}。"
            f"原始咨询：{message.strip()}"
        ),
    }


def parse_outcome(content, known_ids):
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Analysis must be an object")
    required = set(OUTCOME_SCHEMA["properties"]) - {"confidence"}
    if not required <= data.keys() or not data.keys() <= OUTCOME_SCHEMA["properties"].keys():
        raise ValueError("Analysis fields do not match the schema")
    intents = data.get("intents")
    product_ids = data.get("product_ids")
    summary = data.get("merchant_summary_zh")
    confidence = data.get("confidence", 0.8)
    if (
        not isinstance(intents, list)
        or not intents
        or any(intent not in INTENTS for intent in intents)
        or data.get("language") not in LANGUAGES
        or not isinstance(product_ids, list)
        or any(not isinstance(item, str) or item not in known_ids for item in product_ids)
        or type(data.get("needs_human")) is not bool
        or data.get("handoff_reason") is not None
        and not isinstance(data["handoff_reason"], str)
        or not isinstance(summary, str)
        or not summary.strip()
        or not re.search(r"[\u4e00-\u9fff]", summary)
        or type(confidence) not in (int, float)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Invalid structured analysis")
    return {
        "intents": list(dict.fromkeys(intents)),
        "language": data["language"],
        "product_ids": list(dict.fromkeys(product_ids)),
        "needs_human": data["needs_human"],
        "handoff_reason": data.get("handoff_reason"),
        "merchant_summary_zh": summary.strip(),
        "confidence": confidence,
    }


class PostAnalyzer:
    def __init__(self, client: LLMClient, enabled=True, timeout_seconds=10):
        self.client, self.enabled, self.timeout_seconds = client, enabled, timeout_seconds

    async def analyze(self, message, reply, fallback, known_ids, *, remaining_seconds):
        if not self.enabled or not self.client.is_configured or remaining_seconds <= 0:
            return AnalysisResult(fallback, "heuristic")
        messages = (
            Message(
                "system",
                "Annotate this completed customer-support exchange. Output only JSON matching "
                "the supplied schema. merchant_summary_zh must be Chinese and must include "
                "a Chinese translation of the customer's original inquiry when it is not Chinese. "
                "Use only known product_ids. "
                "needs_human is an annotation; never call tools or create tickets.",
            ),
            Message(
                "user",
                json.dumps(
                    {
                        "customer_message": message,
                        "assistant_reply": reply,
                        "known_product_ids": list(known_ids),
                        "schema": OUTCOME_SCHEMA,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        try:
            async with asyncio.timeout(min(self.timeout_seconds, remaining_seconds)):
                try:
                    response = await self.client.complete(
                        messages,
                        tool_choice="none",
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "conversation_outcome",
                                "strict": True,
                                "schema": OUTCOME_SCHEMA,
                            },
                        },
                    )
                except UnsupportedResponseFormat:
                    response = await self.client.complete(messages, tool_choice="none")
                return AnalysisResult(
                    parse_outcome(response.content, known_ids), "llm", response.usage
                )
        except Exception as error:
            logger.warning("Post-analysis fell back to heuristic: %s", type(error).__name__)
            return AnalysisResult(fallback, "heuristic")

    async def summarize(self, messages):
        response = await self.client.complete(
            (
                Message(
                    "system",
                    "Summarize earlier customer conversation for future context. Keep product IDs, "
                    "confirmed facts, unresolved issues and explicit preferences. "
                    "Do not invent policies.",
                ),
                Message(
                    "user",
                    json.dumps([message.to_openai() for message in messages], ensure_ascii=False),
                ),
            ),
            tool_choice="none",
        )
        if not response.content or not response.content.strip():
            raise ValueError("Empty conversation summary")
        return response.content.strip()[:4000]
