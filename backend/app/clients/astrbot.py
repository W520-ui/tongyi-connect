import json
from typing import Any

import httpx

from app.core.config import Settings


class AstrBotError(Exception):
    """AstrBot 请求失败。"""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AstrBotClient:
    """AstrBot HTTP API v1 客户端。

    当前只封装 WebChat 的同步 HTTP 入口。API Key 只在服务端使用，
    不会返回给浏览器。
    """

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.astrbot_base_url.rstrip("/")
        self.api_key = settings.astrbot_api_key
        # Keep model generation time generous while failing fast when the
        # AstrBot service is unreachable.
        self.timeout = httpx.Timeout(
            settings.astrbot_timeout_seconds,
            connect=min(settings.astrbot_timeout_seconds, 5.0),
        )

    @property
    def is_configured(self) -> bool:
        """Whether the server has credentials required by AstrBot WebChat."""

        return bool(self.api_key)

    async def send_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post("/api/v1/chat", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AstrBotError("AstrBot 请求超时") from exc
        except httpx.HTTPError as exc:
            raise AstrBotError("无法连接 AstrBot 服务") from exc

        if response.status_code >= 400:
            detail = _response_detail(response)
            raise AstrBotError(
                f"AstrBot 返回错误：{detail}",
                status_code=response.status_code,
            )

        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            return _parse_sse_response(response.text)

        try:
            body = response.json()
        except ValueError as exc:
            raise AstrBotError("AstrBot 返回了无法解析的响应") from exc

        if not isinstance(body, dict):
            raise AstrBotError("AstrBot 返回格式不正确")

        return body


def _response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text

    if isinstance(body, dict):
        for key in ("message", "detail", "error"):
            value = body.get(key)
            if value:
                return str(value)

    return str(body)[:300] or response.reason_phrase


def _parse_sse_response(raw_body: str) -> dict[str, Any]:
    """把 AstrBot 的 WebChat SSE 事件聚合为项目统一的响应信封。

    AstrBot 即使在非流式模式下也会返回 ``text/event-stream``，其中最终文本
    位于一个或多个 ``type=plain`` 事件的 ``data`` 字段。这里只向上层暴露
    聚合后的回答，避免浏览器和项目 API 直接处理 AstrBot 的内部事件流。
    """

    events: list[dict[str, Any]] = []
    for line in raw_body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue

        encoded = line.removeprefix("data:").strip()
        if not encoded or encoded == "[DONE]":
            continue

        try:
            event = json.loads(encoded)
        except json.JSONDecodeError:
            # 忽略 SSE 注释/心跳或未来版本的非 JSON 数据行。
            continue
        if isinstance(event, dict):
            events.append(event)

    if not events:
        raise AstrBotError("AstrBot 返回了空的 SSE 响应")

    text_parts: list[str] = []
    completed_text: str | None = None
    error_parts: list[str] = []
    for event in events:
        event_type = event.get("type")
        data = event.get("data")
        if event_type in {"plain", "text"}:
            if isinstance(data, str):
                text_parts.append(data)
        elif event_type == "complete":
            # 流式模式会先发送增量 plain 事件，再用 complete 携带完整文本；
            # 使用完整文本可避免把回答拼接两次。
            if isinstance(data, str):
                completed_text = data
        elif event_type == "error" and data:
            error_parts.append(str(data))

    if error_parts and not text_parts:
        return {
            "status": "error",
            "data": None,
            "message": "；".join(error_parts),
        }

    return {
        "status": "ok",
        "data": completed_text if completed_text is not None else "".join(text_parts),
        "message": None,
    }
