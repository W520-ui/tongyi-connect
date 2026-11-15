import asyncio
import json
from uuid import UUID

import pytest
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse

from app.agent.llm.base import StreamChunk
from app.api.v1.streaming import subscribe
from app.core.errors import AppError
from app.domain.types import InboundMessage
from app.repositories.models import AgentRun, StoredMessage
from tests.support import Decision, ScriptedProvider
from tests.test_phase2_analysis import outcome
from tests.test_phase3_api import PREFIX, create, path


def parse_events(body):
    events = []
    for frame in body.split("\n\n"):
        if not frame or frame.startswith(":"):
            continue
        name, data = frame.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def test_stream_returns_complete_typed_event_sequence(api_client):
    client, runtime = api_client
    conversation_id = create(client)
    runtime.provider.streams.extend(
        [
            [
                StreamChunk(
                    tool_calls=(
                        {
                            "index": 0,
                            "id": "search",
                            "function": {
                                "name": "catalog_search",
                                "arguments": '{"query":"nebula"}',
                            },
                        },
                    )
                ),
            ],
            [StreamChunk(content="Hello "), StreamChunk(content="there.")],
        ]
    )
    analysis = ScriptedProvider([Decision(reply=json.dumps(outcome(), ensure_ascii=False))])
    runtime.app.state.conversation_service.analyzer.client = analysis
    runtime.app.state.conversation_service.analyzer.enabled = True
    response = client.post(
        path(conversation_id, "/messages/stream"),
        headers={"Accept": "text/event-stream"},
        json={"content": "Please quote the Nebula", "client_message_id": "stream-1"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    events = parse_events(response.text)
    names = [name for name, _data in events]
    assert names == ["tool_started", "tool_finished", "delta", "delta", "completed", "analysis"]
    assert events[0][1] == {
        "call_id": "search",
        "round": 0,
        "name": "catalog_search",
        "args": {"query": "nebula"},
    }
    assert events[1][1]["ok"] is True and events[1][1]["error"] is None
    assert events[2][1] == {"round": 1, "text": "Hello "}
    assert events[3][1] == {"round": 1, "text": "there."}
    completed = events[4][1]["data"]
    assert completed["reply"] == "Hello there." and completed["analysis_source"] == "pending"
    assert completed["replayed"] is False and UUID(completed["message_id"])
    assert events[5][1]["analysis_source"] == "llm"
    assert events[5][1]["intent"] == "logistics"
    assert events[5][1]["merchant_summary"].startswith("客户咨询")
    assert len(runtime.rows(AgentRun)) == 1 and len(runtime.rows(StoredMessage)) == 4


@pytest.mark.parametrize(
    "setup,expected_code,status_code",
    [("missing", "CONVERSATION_NOT_FOUND", 404), ("unconfigured", "LLM_NOT_CONFIGURED", 503)],
)
def test_stream_preflight_errors_stay_json(api_client, setup, expected_code, status_code):
    client, runtime = api_client
    if setup == "unconfigured":
        conversation_id = create(client)
        runtime.provider.is_configured = False
    else:
        conversation_id = "missing"
    response = client.post(path(conversation_id, "/messages/stream"), json={"content": "Hello"})
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["status"] == "error"
    assert response.json()["error"]["code"] == expected_code
    assert "event:" not in response.text
    assert runtime.provider.calls == []


def test_stream_run_failures_are_error_events_without_completed(api_client):
    client, runtime = api_client
    conversation_id = create(client)
    runtime.provider.streams.append([AppError("LLM_TIMEOUT")])
    response = client.post(path(conversation_id, "/messages/stream"), json={"content": "Hello"})
    assert response.status_code == 200
    events = parse_events(response.text)
    assert [name for name, _data in events] == ["error"]
    assert events[0][1]["code"] == "LLM_TIMEOUT"
    assert len(runtime.rows(AgentRun)) == 1
    assert [(turn.role, turn.content) for turn in runtime.session(conversation_id).turns] == [
        ("user", "Hello")
    ]


def test_stream_replay_commands_and_human_pause_complete_once(api_client):
    client, runtime = api_client
    conversation_id = create(client)
    request = {"content": "/help", "client_message_id": "cmd"}
    for _ in range(2):
        response = client.post(path(conversation_id, "/messages/stream"), json=request)
        events = parse_events(response.text)
        assert [name for name, _data in events] == ["completed"]
        assert events[0][1]["data"]["run_id"] is None
        assert events[0][1]["data"]["analysis_source"] == "heuristic"
    handoff = client.post(path(conversation_id, "/handoff"), json={})
    ticket_id = handoff.json()["data"]["ticket"]["id"]
    client.post(f"{PREFIX}/handoffs/{ticket_id}/acknowledge")
    runtime.provider.is_configured = False
    paused = client.post(
        path(conversation_id, "/messages/stream"),
        json={"content": "Hola", "client_message_id": "paused"},
    )
    events = parse_events(paused.text)
    assert [name for name, _data in events] == ["completed"]
    assert events[0][1]["data"]["source"] == "paused-for-human"
    assert runtime.rows(AgentRun) == [] and runtime.provider.calls == []


def test_client_disconnect_stops_subscription_but_run_keeps_persisting(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider(
            streams=[[StreamChunk(content="Part one."), StreamChunk(content="Part two.")]],
            delay=0.03,
        )
    )
    conversation_id = create(runtime.client)

    async def disconnect():
        body = await subscribe(
            runtime.service,
            InboundMessage(
                "Hello after disconnect", conversation_id, streaming=True, legacy_session=False
            ),
        )
        response = StreamingResponse(
            body, media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )
        scope = {
            "type": "http",
            "asgi": {"spec_version": "2.4"},
            "method": "POST",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("test", 80),
            "client": ("test", 1),
            "root_path": "",
            "http_version": "1.1",
        }
        frames = []

        async def receive():
            raise AssertionError("ASGI 2.4 must not poll disconnect separately")

        async def send(message):
            frames.append(message)
            if message["type"] == "http.response.body" and message.get("body"):
                raise OSError("simulated client disconnect")

        with pytest.raises(ClientDisconnect):
            await response(scope, receive, send)
        await response.body_iterator.aclose()
        tasks = tuple(runtime.service.background.tasks)
        assert tasks
        await asyncio.gather(*tasks)
        assert any(message.get("type") == "http.response.start" for message in frames)

    runtime.client.portal.call(disconnect)
    assert len(runtime.provider.calls) == 1
    assert [turn.content for turn in runtime.session(conversation_id).turns] == [
        "Hello after disconnect",
        "Part one.Part two.",
    ]
    assert len(runtime.rows(AgentRun)) == 1
