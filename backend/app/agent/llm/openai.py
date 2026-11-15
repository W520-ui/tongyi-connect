import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx

from app.agent.llm.base import ModelResponse, StreamChunk, Usage
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.types import Message, ToolCall

logger = logging.getLogger(__name__)


def parse_usage(body: dict[str, Any]) -> Usage | None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        return Usage(max(0, int(usage["prompt_tokens"])), max(0, int(usage["completion_tokens"])))
    except (KeyError, TypeError, ValueError):
        return None


def parse_response(body: Any) -> ModelResponse:
    try:
        message = body["choices"][0]["message"]
        finish_reason = body["choices"][0].get("finish_reason")
        if not isinstance(message, dict):
            raise ValueError("Invalid message")
        calls = tuple(
            ToolCall(
                id=str(raw.get("id") or f"call_{index}"),
                name=str(raw["function"].get("name") or ""),
                arguments=raw["function"].get("arguments", "{}"),
            )
            for index, raw in enumerate(message.get("tool_calls") or ())
        )
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if content is not None and not isinstance(content, str):
            raise ValueError("Invalid content")
        if not calls and (not content or not content.strip()):
            raise ValueError("Empty message")
        return ModelResponse(content, calls, finish_reason, parse_usage(body))
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise AppError("LLM_BAD_RESPONSE") from exc


def parse_chunk(body: Any) -> StreamChunk:
    try:
        if not isinstance(body, dict):
            raise ValueError("Invalid stream event")
        choices = body.get("choices") or []
        if not choices:
            return StreamChunk(usage=parse_usage(body))
        choice = choices[0]
        delta = choice.get("delta") or {}
        content = delta.get("content")
        calls = delta.get("tool_calls") or ()
        if content is not None and not isinstance(content, str):
            raise ValueError("Invalid content delta")
        if not isinstance(calls, (list, tuple)) or any(
            not isinstance(call, dict) for call in calls
        ):
            raise ValueError("Invalid tool-call delta")
        return StreamChunk(content, tuple(calls), choice.get("finish_reason"), parse_usage(body))
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise AppError("LLM_BAD_RESPONSE") from exc


def retry_delay(header: str | None, attempt: int) -> float:
    if header:
        try:
            return max(0, float(header))
        except ValueError:
            try:
                timestamp = parsedate_to_datetime(header)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                return max(0, (timestamp - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return 0.25 * (2**attempt)


class OpenAICompatibleClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client
        self.timeout = httpx.Timeout(
            settings.llm_timeout_seconds, connect=min(settings.llm_timeout_seconds, 5)
        )
        self.url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

    @property
    def is_configured(self) -> bool:
        return self.settings.is_configured

    def _request(self, messages, tools, tool_choice, response_format=None) -> tuple[dict, dict]:
        if not self.is_configured:
            raise AppError("LLM_NOT_CONFIGURED")
        payload = {
            "model": self.settings.llm_model,
            "messages": [message.to_openai() for message in messages],
            "temperature": self.settings.llm_temperature,
        }
        if self.settings.llm_max_tokens is not None:
            payload["max_tokens"] = self.settings.llm_max_tokens
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = response_format
        return payload, {
            "Authorization": f"Bearer {self.settings.llm_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    def _log_upstream(self, response: httpx.Response) -> None:
        detail = response.text
        if self.settings.llm_api_key:
            detail = detail.replace(self.settings.llm_api_key.get_secret_value(), "[REDACTED]")
        logger.warning(
            "LLM upstream returned status=%s detail=%s", response.status_code, detail[:300]
        )

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, Any]] = (),
        tool_choice: Literal["auto", "none"] = "auto",
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse:
        payload, headers = self._request(messages, tools, tool_choice, response_format)
        for attempt in range(3):
            try:
                response = await self.http_client.post(
                    self.url, json=payload, headers=headers, timeout=self.timeout
                )
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                if attempt == 2:
                    code = (
                        "LLM_TIMEOUT"
                        if isinstance(error, httpx.ConnectTimeout)
                        else "LLM_UPSTREAM_ERROR"
                    )
                    raise AppError(code) from None
                await asyncio.sleep(retry_delay(None, attempt))
                continue
            except httpx.TimeoutException:
                raise AppError("LLM_TIMEOUT") from None
            except httpx.HTTPError:
                raise AppError("LLM_UPSTREAM_ERROR") from None
            if response.status_code >= 400:
                self._log_upstream(response)
                if (response.status_code == 429 or response.status_code >= 500) and attempt < 2:
                    await asyncio.sleep(retry_delay(response.headers.get("Retry-After"), attempt))
                    continue
                raise AppError("LLM_UPSTREAM_ERROR")
            try:
                return parse_response(response.json())
            except ValueError:
                raise AppError("LLM_BAD_RESPONSE") from None
        raise AppError("LLM_UPSTREAM_ERROR")

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, Any]] = (),
        tool_choice: Literal["auto", "none"] = "auto",
    ) -> AsyncIterator[StreamChunk]:
        payload, headers = self._request(messages, tools, tool_choice)
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        emitted = False
        for attempt in range(3):
            try:
                async with self.http_client.stream(
                    "POST", self.url, json=payload, headers=headers, timeout=self.timeout
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        self._log_upstream(response)
                        if (
                            response.status_code == 429 or response.status_code >= 500
                        ) and attempt < 2:
                            await asyncio.sleep(
                                retry_delay(response.headers.get("Retry-After"), attempt)
                            )
                            continue
                        raise AppError("LLM_UPSTREAM_ERROR")
                    data_lines: list[str] = []
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data_lines.append(line[5:].lstrip())
                        elif not line and data_lines:
                            data = "\n".join(data_lines)
                            data_lines.clear()
                            if data == "[DONE]":
                                return
                            emitted = True
                            try:
                                yield parse_chunk(json.loads(data))
                            except ValueError:
                                raise AppError("LLM_BAD_RESPONSE") from None
                    if data_lines:
                        data = "\n".join(data_lines)
                        if data != "[DONE]":
                            try:
                                yield parse_chunk(json.loads(data))
                            except ValueError:
                                raise AppError("LLM_BAD_RESPONSE") from None
                    return
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                if emitted or attempt == 2:
                    code = (
                        "LLM_TIMEOUT"
                        if isinstance(error, httpx.ConnectTimeout)
                        else "LLM_UPSTREAM_ERROR"
                    )
                    raise AppError(code) from None
                await asyncio.sleep(retry_delay(None, attempt))
            except httpx.TimeoutException:
                raise AppError("LLM_TIMEOUT") from None
            except httpx.HTTPError:
                raise AppError("LLM_UPSTREAM_ERROR") from None
        raise AppError("LLM_UPSTREAM_ERROR")
