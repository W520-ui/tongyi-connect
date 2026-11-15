import json
from datetime import UTC, datetime

import httpx
import pytest

from app.agent.llm.base import Usage
from app.agent.llm.openai import OpenAICompatibleClient, parse_response, retry_delay
from app.core.errors import AppError
from app.domain.types import Message


def response_body():
    return {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }


async def test_shared_http_client_payload_and_usage(settings_factory):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=response_body())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        settings = settings_factory(llm_temperature=0.2, llm_max_tokens=128)
        client = OpenAICompatibleClient(settings, http_client)
        result = await client.complete(
            [Message(role="user", content="Hi")],
            tools=[{"type": "function", "function": {"name": "x"}}],
            tool_choice="none",
        )
        await client.complete(
            [Message(role="user", content="Again")], response_format={"type": "json_object"}
        )
        assert client.http_client is http_client
        assert result.usage == Usage(5, 2) and result.finish_reason == "stop"
        payload = json.loads(requests[0].content)
        assert payload["temperature"] == 0.2 and payload["max_tokens"] == 128
        assert payload["tool_choice"] == "none" and payload["tools"]
        assert requests[0].headers["Authorization"] == "Bearer test-key"
        assert json.loads(requests[1].content)["response_format"] == {"type": "json_object"}
    assert http_client.is_closed


async def test_retries_429_and_5xx_and_honors_retry_after(settings_factory, monkeypatch):
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.agent.llm.openai.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="busy")
        if len(requests) == 2:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json=response_body())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        assert (
            await OpenAICompatibleClient(settings_factory(), transport).complete([])
        ).content == "Hello"
    assert len(requests) == 3
    assert delays == [0, 0.5]


async def test_connection_errors_retry_at_most_twice(settings_factory, monkeypatch):
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.agent.llm.openai.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        raise httpx.ConnectError("sensitive connection details", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        with pytest.raises(AppError) as error:
            await OpenAICompatibleClient(settings_factory(), transport).complete([])
    assert error.value.code == "LLM_UPSTREAM_ERROR"
    assert "sensitive" not in str(error.value)
    assert len(requests) == 3 and delays == [0.25, 0.5]


@pytest.mark.parametrize("status,attempts", [(401, 1), (429, 3), (500, 3)])
async def test_upstream_errors_are_redacted_and_retries_are_bounded(
    settings_factory, monkeypatch, caplog, status, attempts
):
    requests = []

    async def sleep(_delay):
        pass

    monkeypatch.setattr("app.agent.llm.openai.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        return httpx.Response(status, text="UPSTREAM-DETAIL-MARKER key=test-key")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        with pytest.raises(AppError) as error:
            await OpenAICompatibleClient(settings_factory(), transport).complete([])
    assert error.value.code == "LLM_UPSTREAM_ERROR"
    assert "UPSTREAM-DETAIL-MARKER" not in str(error.value)
    assert "test-key" not in caplog.text
    assert "[REDACTED]" in caplog.text
    assert len(requests) == attempts


async def test_read_timeout_is_not_retried(settings_factory):
    requests = []

    def handle(request):
        requests.append(request)
        raise httpx.ReadTimeout("private details", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        with pytest.raises(AppError) as error:
            await OpenAICompatibleClient(settings_factory(), transport).complete([])
    assert error.value.code == "LLM_TIMEOUT" and len(requests) == 1
    assert "private details" not in str(error.value)


@pytest.mark.parametrize("streaming", [False, True])
async def test_connect_timeout_retries_then_returns_timeout(
    settings_factory, monkeypatch, streaming
):
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.agent.llm.openai.asyncio.sleep", sleep)

    def handle(request):
        requests.append(request)
        raise httpx.ConnectTimeout("private connection details", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        client = OpenAICompatibleClient(settings_factory(), transport)
        with pytest.raises(AppError) as error:
            if streaming:
                async for _event in client.stream([]):
                    pytest.fail("A connect timeout cannot emit a stream event")
            else:
                await client.complete([])
    assert error.value.code == "LLM_TIMEOUT"
    assert "private connection details" not in str(error.value)
    assert len(requests) == 3 and delays == [0.25, 0.5]


@pytest.mark.parametrize(
    "body", [[], {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {"content": 1}}]}]
)
async def test_bad_responses_receive_stable_code(settings_factory, body):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=body))
    ) as transport:
        with pytest.raises(AppError) as error:
            await OpenAICompatibleClient(settings_factory(), transport).complete([])
    assert error.value.code == "LLM_BAD_RESPONSE"


def test_bad_tool_json_is_preserved_for_tool_validation():
    body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "bad",
                            "function": {"name": "catalog_quote", "arguments": "{broken"},
                        },
                    ]
                }
            }
        ]
    }
    assert parse_response(body).tool_calls[0].arguments == "{broken"


async def test_real_http_sse_parser_and_stream_payload(settings_factory):
    requests = []
    chunks = [
        {"choices": [{"delta": {"content": "Hel"}}]},
        {
            "choices": [{"delta": {"content": "lo"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1},
        },
    ]

    def handle(request):
        requests.append(request)
        text = (
            ": ping\n\n"
            + "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks)
            + "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=text, headers={"Content-Type": "text/event-stream"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        events = [
            event
            async for event in OpenAICompatibleClient(settings_factory(), transport).stream(
                [Message(role="user", content="Hi")]
            )
        ]
    assert "".join(event.content or "" for event in events) == "Hello"
    assert events[-1].usage == Usage(3, 1)
    assert json.loads(requests[0].content)["stream"] is True


def test_retry_after_http_date_and_invalid_header(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2020, 1, 1, tzinfo=UTC)

    monkeypatch.setattr("app.agent.llm.openai.datetime", FixedDatetime)
    assert retry_delay("Wed, 01 Jan 2020 00:00:02 GMT", 0) == 2
    assert retry_delay("invalid", 1) == 0.5
    assert retry_delay("0", 0) == 0


async def test_unconfigured_client_never_sends_request(settings_factory):
    def handle(_request):
        raise AssertionError("No request may be sent")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        with pytest.raises(AppError) as error:
            await OpenAICompatibleClient(settings_factory(llm_api_key=None), transport).complete([])
    assert error.value.code == "LLM_NOT_CONFIGURED"
