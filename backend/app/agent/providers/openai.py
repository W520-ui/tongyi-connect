from __future__ import annotations

import json
from typing import Any

import httpx

from app.agent.config import AgentSettings
from app.agent.models import AgentError, Decision, Message, ToolCall


class OpenAICompatibleProvider:
    """Call any OpenAI-compatible /chat/completions endpoint with httpx."""

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.timeout = httpx.Timeout(
            settings.llm_timeout_seconds,
            connect=min(settings.llm_timeout_seconds, 5.0),
        )

    @property
    def is_configured(self) -> bool:
        return self.settings.is_configured

    async def decide(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Decision:
        if not self.is_configured:
            raise AgentError("尚未配置 AGENT_LLM_API_KEY，无法生成回复")

        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [message.to_openai() for message in messages],
            "temperature": 0.3,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AgentError("模型请求超时") from exc
        except httpx.HTTPError as exc:
            raise AgentError("无法连接模型服务") from exc

        if response.status_code >= 400:
            raise AgentError(
                f"模型返回错误：{_response_detail(response)}", status_code=502
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AgentError("模型返回了无法解析的响应") from exc
        if not isinstance(body, dict):
            raise AgentError("模型返回格式不正确")
        return _parse_decision(body)


def _response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text
    if isinstance(body, dict):
        for key in ("message", "error", "detail"):
            value = body.get(key)
            if value:
                return str(value)[:300]
    return str(body)[:300] or response.reason_phrase


def _parse_decision(body: dict[str, Any]) -> Decision:
    choices = body.get("choices") or []
    if not choices:
        raise AgentError("模型返回了空结果")
    message = choices[0].get("message") or {}

    calls: list[ToolCall] = []
    for index, raw_call in enumerate(message.get("tool_calls") or []):
        function = raw_call.get("function") or {}
        raw_args = function.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except (ValueError, TypeError):
            args = {}
        calls.append(
            ToolCall(
                id=str(raw_call.get("id") or f"call_{index}"),
                name=str(function.get("name") or ""),
                arguments=args,
            )
        )
    if calls:
        return Decision(tool_calls=tuple(calls))

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return Decision(reply=content.strip())
    if isinstance(content, list):
        text = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
        if text.strip():
            return Decision(reply=text.strip())
    raise AgentError("模型返回了空回复")
