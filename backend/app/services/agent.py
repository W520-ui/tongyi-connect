from typing import Any

from app.clients.astrbot import AstrBotClient, AstrBotError
from app.schemas.agent import AgentChatRequest
from app.services.workflow import analyze_message, build_workflow_answer, metrics


_NO_PROVIDER_MARKERS = (
    "未找到任何可用的对话模型",
    "没有任何可用的对话模型",
    "no available chat model",
    "no available provider",
)


class AgentService:
    def __init__(self, client: AstrBotClient) -> None:
        self.client = client

    async def chat(self, request: AgentChatRequest) -> dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        payload["flags"] = request.flags.model_dump(exclude_none=True)
        payload.setdefault("username", "web-user")

        session_id = request.session_id or "未命名会话"
        analysis = analyze_message(
            request.message,
            product_hint=metrics.last_product_id(session_id) if request.session_id else None,
        )

        # A live AstrBot model is required. Any configuration or transport
        # problem is surfaced to the caller instead of being masked.
        if not self.client.is_configured:
            raise AstrBotError("AstrBot 尚未配置 API Key")

        result = await self.client.send_chat(payload)
        if result.get("status") == "error":
            raise AstrBotError(str(result.get("message") or "AstrBot 返回错误"))

        reply = _extract_reply(result)
        if reply is None:
            raise AstrBotError("AstrBot 返回了空回复")
        if _is_provider_unavailable(reply):
            raise AstrBotError(reply)

        source = "astrbot+human-handoff" if analysis.needs_human else "astrbot"
        workflow = build_workflow_answer(
            request.message,
            analysis,
            reply=reply,
            source=source,
        )
        metrics.archive(session_id=session_id, message=request.message, answer=workflow)
        return {
            "status": "ok",
            "data": workflow,
            "message": None,
        }


def _extract_reply(result: dict[str, Any]) -> str | None:
    data = result.get("data")
    if isinstance(data, str):
        return data.strip() or None
    if isinstance(data, dict):
        for key in ("reply", "response", "message", "content", "text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("reply", "response", "message", "content", "text"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_provider_unavailable(reply: str) -> bool:
    lowered = reply.lower()
    return any(marker.lower() in lowered for marker in _NO_PROVIDER_MARKERS)
