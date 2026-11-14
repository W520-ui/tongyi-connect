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
        astrbot_error: str | None = None
        source = "astrbot"
        model_reply: str | None = None

        # A demo with the local fallback enabled should be usable immediately
        # when no AstrBot key has been configured. Skipping the network call
        # also avoids a connection timeout on the first message.
        if not getattr(self.client, "is_configured", True):
            astrbot_error = "AstrBot 尚未配置 API Key"
            if not self._fallback_enabled:
                raise AstrBotError(astrbot_error)
        else:
            try:
                result = await self.client.send_chat(payload)
                if result.get("status") == "error":
                    astrbot_error = str(result.get("message") or "AstrBot 返回错误")
                else:
                    model_reply = _extract_reply(result)
                if _is_provider_unavailable(model_reply):
                    astrbot_error = model_reply
                    model_reply = None
                if model_reply is None and astrbot_error and not self._fallback_enabled:
                    raise AstrBotError(astrbot_error)
            except AstrBotError as exc:
                is_client_error = exc.status_code is not None and 400 <= exc.status_code < 500
                if not self._fallback_enabled or is_client_error:
                    raise
                astrbot_error = str(exc)

        if model_reply is None:
            source = "local-demo"
        elif analysis.needs_human:
            source = "astrbot+human-handoff"

        workflow = build_workflow_answer(
            request.message,
            analysis,
            reply=model_reply,
            source=source,
            astrbot_error=astrbot_error,
        )
        metrics.archive(
            session_id=session_id,
            message=request.message,
            answer=workflow,
        )
        return {
            "status": "ok",
            "data": workflow,
            "message": None,
        }

    @property
    def _fallback_enabled(self) -> bool:
        # The client keeps the Settings-derived URL/key; this flag is attached
        # by the endpoint factory for backwards compatibility with the small
        # original adapter.
        return getattr(self.client, "local_fallback_enabled", True)


def _extract_reply(result: dict[str, Any]) -> str | None:
    if result.get("status") == "error":
        return str(result.get("message") or "AstrBot 返回错误")

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


def _is_provider_unavailable(reply: str | None) -> bool:
    if not reply:
        return False
    lowered = reply.lower()
    return any(marker.lower() in lowered for marker in _NO_PROVIDER_MARKERS)
