import asyncio
import json
import logging
from uuid import UUID

import httpx
import pytest

from app.core.errors import AppError
from app.core.logging import RedactingFormatter
from app.domain.types import ToolCall
from app.repositories.models import (
    AgentRun,
    CommandReceipt,
    Conversation,
    HandoffTicket,
    StoredMessage,
)
from tests.support import Decision, ScriptedProvider
from tests.test_api import WORKFLOW_FIELDS, assert_workflow_contract

PREFIX = "/api/v1"
PUBLIC_WORKFLOW_FIELDS = WORKFLOW_FIELDS | {
    "conversation_id",
    "message_id",
    "client_message_id",
    "run_id",
    "replayed",
    "conversation_status",
    "analysis_source",
    "trace",
}
CONVERSATION_FIELDS = {
    "id",
    "status",
    "reply_language",
    "state",
    "open_handoff",
    "created_at",
    "updated_at",
    "last_message_at",
}
TICKET_FIELDS = {
    "id",
    "conversation_id",
    "status",
    "reason_code",
    "reason_text",
    "issue_summary",
    "customer_message",
    "language_label",
    "intent_label",
    "created_at",
    "acknowledged_at",
    "resolved_at",
}


def create(client, **values):
    response = client.post(f"{PREFIX}/conversations", json=values)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "ok"
    return response.json()["data"]["id"]


def path(conversation_id, suffix=""):
    return f"{PREFIX}/conversations/{conversation_id}{suffix}"


def assert_error(response, status_code, code):
    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"status", "error", "detail"}
    assert body["status"] == "error"
    assert body["error"]["code"] == code
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["detail"] == body["error"]["message"]
    assert "test-key" not in response.text
    if code != "VALIDATION_ERROR":
        assert body["error"]["details"] is None
    else:
        assert body["error"]["details"]
        assert all(set(item) == {"loc", "msg"} for item in body["error"]["details"])


def test_create_read_update_reset_and_old_history(api_client):
    client, runtime = api_client
    conversation_id = create(client, reply_language="es-ES")
    assert UUID(conversation_id)
    current = client.get(path(conversation_id)).json()["data"]
    assert set(current) == CONVERSATION_FIELDS
    assert current["reply_language"] == "es-ES"
    assert current["open_handoff"] is current["last_message_at"] is None
    assert current["state"] == {
        "focused_product_ids": [],
        "destination_country": None,
        "quantity": None,
    }
    assert current["created_at"].endswith("+00:00")
    runtime.provider.decisions.append(Decision(reply="Hello"))
    sent = client.post(path(conversation_id, "/messages"), json={"content": "  hello  "}).json()[
        "data"
    ]
    assert set(sent) == PUBLIC_WORKFLOW_FIELDS
    assert_workflow_contract(sent)
    assert UUID(sent["message_id"]) and UUID(sent["run_id"])
    assert sent["analysis_source"] == "heuristic"
    assert sent["client_message_id"] is None
    for language in ("zh-CN", "en-US", None):
        changed = client.patch(path(conversation_id), json={"reply_language": language})
        assert changed.status_code == 200
        assert changed.json()["data"]["reply_language"] == language
    ticket = client.post(path(conversation_id, "/handoff"), json={}).json()["data"]["ticket"]
    reset = client.post(path(conversation_id, "/reset"))
    assert reset.status_code == 201
    replacement = reset.json()["data"]
    assert replacement["previous_conversation_id"] == conversation_id
    new_id = replacement["conversation"]["id"]
    assert new_id != conversation_id and UUID(new_id)
    assert replacement["conversation"]["reply_language"] is None
    assert client.get(path(conversation_id)).json()["data"]["status"] == "resolved"
    assert client.get(path(new_id, "/messages")).json()["data"] == {"items": [], "has_more": False}
    old = client.get(path(conversation_id, "/messages")).json()["data"]["items"]
    assert [item["content"] for item in old] == ["hello", "Hello"]
    assert old[1]["workflow"] == sent
    assert runtime.rows(HandoffTicket)[0].id == ticket["id"]
    assert runtime.rows(HandoffTicket)[0].status == "resolved"


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("GET", "", None),
        ("PATCH", "", {"reply_language": None}),
        ("GET", "/messages", None),
        ("POST", "/messages", {"content": "hi"}),
        ("POST", "/messages/stream", {"content": "hi"}),
        ("POST", "/reset", None),
        ("POST", "/handoff", {}),
    ],
)
def test_unknown_conversations_never_create_an_alias(api_client, method, suffix, body):
    client, runtime = api_client
    response = client.request(method, path("unknown", suffix), json=body)
    assert_error(response, 404, "CONVERSATION_NOT_FOUND")
    assert runtime.rows(Conversation) == []
    assert runtime.provider.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"content": ""},
        {"content": " \n\t "},
        {"content": "x" * 20001},
        {"content": 2},
        {"content": "hello", "client_message_id": ""},
        {"content": "hello", "client_message_id": "a" * 65},
        {"content": "hello", "client_message_id": "id has-space"},
        {"content": "hello", "client_message_id": " id"},
        {"content": "hello", "client_message_id": "中文"},
        {"content": "hello", "client_message_id": "bad\n"},
        {"content": "hello", "unknown": True},
        {},
    ],
)
@pytest.mark.parametrize("stream", [False, True])
def test_message_validation_uses_safe_envelope(api_client, payload, stream):
    client, runtime = api_client
    conversation_id = create(client)
    response = client.post(
        path(conversation_id, "/messages" + ("/stream" if stream else "")), json=payload
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert runtime.provider.calls == [] and runtime.rows(StoredMessage) == []
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("PATCH", "", {}),
        ("PATCH", "", {"reply_language": "fr-FR"}),
        ("GET", "/messages?limit=0", None),
        ("GET", "/messages?limit=201", None),
        ("GET", "/messages?before_seq=0", None),
        ("GET", "/messages?before_seq=text", None),
    ],
)
def test_conversation_query_and_language_validation(api_client, method, suffix, body):
    client, _ = api_client
    assert_error(
        client.request(method, path(create(client), suffix), json=body), 422, "VALIDATION_ERROR"
    )


def test_history_pages_exclude_tool_calls_and_restore_saved_cards(api_client):
    from app.domain.types import ToolCall

    client, runtime = api_client
    conversation_id = create(client)
    runtime.provider.decisions.extend(
        [
            Decision(tool_calls=[ToolCall("search", "catalog_search", {"query": "nebula"})]),
            Decision(reply="First answer"),
            Decision(reply="Second answer"),
        ]
    )
    first = client.post(
        path(conversation_id, "/messages"), json={"content": "Hello", "client_message_id": "a_1-"}
    ).json()["data"]
    client.post(path(conversation_id, "/messages"), json={"content": "/help"})
    second = client.post(path(conversation_id, "/messages"), json={"content": "Again"}).json()[
        "data"
    ]
    latest = client.get(path(conversation_id, "/messages?limit=2")).json()["data"]
    assert latest["has_more"] is True
    assert [item["content"] for item in latest["items"]] == ["Again", "Second answer"]
    assert latest["items"][1]["workflow"] == second
    previous = client.get(
        path(conversation_id, f"/messages?limit=2&before_seq={latest['items'][0]['seq']}")
    ).json()["data"]
    assert previous["has_more"] is False
    assert [item["content"] for item in previous["items"]] == ["Hello", "First answer"]
    assert previous["items"][0]["client_message_id"] == "a_1-"
    assert previous["items"][0]["workflow"] is None
    assert previous["items"][1]["client_message_id"] is None
    assert previous["items"][1]["workflow"] == first
    assert first["matched_products"][0]["id"] == "headset-pro"
    assert [item["seq"] for item in previous["items"]] == [1, 4]
    assert len(runtime.rows(StoredMessage)) == 6
    assert runtime.snapshot()["total_conversations"] == 2


def test_handoff_lifecycle_and_paused_replay(api_client):
    client, runtime = api_client
    conversation_id = create(client, reply_language="en-US")
    runtime.provider.decisions.extend([Decision(reply="Initial"), Decision(reply="Resumed")])
    message = "Customer question " + "x" * 600
    client.post(path(conversation_id, "/messages"), json={"content": message})
    result = client.post(
        path(conversation_id, "/handoff"), json={"reason_text": "Please review"}
    ).json()["data"]
    ticket = result["ticket"]
    assert set(ticket) == TICKET_FIELDS
    assert ticket["reason_code"] == "user_request" and ticket["reason_text"] == "Please review"
    assert ticket["customer_message"] == message[:500]
    assert ticket["acknowledged_at"] is ticket["resolved_at"] is ticket["issue_summary"] is None
    assert result["conversation"]["status"] == "pending_human"
    assert result["conversation"]["open_handoff"] == ticket
    repeated = client.post(path(conversation_id, "/handoff"), json={}).json()["data"]
    assert repeated["ticket"] == ticket
    ticket_path = f"{PREFIX}/handoffs/{ticket['id']}"
    ack = client.post(ticket_path + "/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["data"]["status"] == "acknowledged"
    assert ack.json()["data"]["acknowledged_at"].endswith("+00:00")
    assert_error(client.post(ticket_path + "/acknowledge"), 409, "INVALID_STATE")
    request = {"content": "你好", "client_message_id": "paused"}
    paused = client.post(path(conversation_id, "/messages"), json=request).json()["data"]
    replay = client.post(path(conversation_id, "/messages"), json=request).json()["data"]
    assert paused["source"] == "paused-for-human" and paused["run_id"] is None
    assert paused["reply"].startswith("You've been connected")
    assert replay == {**paused, "replayed": True}
    assert client.get(f"{PREFIX}/handoffs?status=open").json()["data"]["items"] == []
    assert client.get(f"{PREFIX}/handoffs").json()["data"]["items"][0]["status"] == "acknowledged"
    resolved = client.post(ticket_path + "/resolve").json()["data"]
    assert resolved["status"] == "resolved" and resolved["resolved_at"].endswith("+00:00")
    assert_error(client.post(ticket_path + "/resolve"), 409, "INVALID_STATE")
    assert client.get(path(conversation_id)).json()["data"]["open_handoff"] is None
    resumed = client.post(
        path(conversation_id, "/messages"), json={"content": "Hello again"}
    ).json()["data"]
    assert resumed["conversation_status"] == "bot_active" and not resumed["needs_human"]
    assert len(runtime.provider.calls) == 2
    assert runtime.snapshot()["total_conversations"] == 3


def test_open_ticket_resolve_sorting_and_filter_validation(api_client):
    client, _ = api_client
    tickets = []
    for _ in range(3):
        tickets.append(
            client.post(path(create(client), "/handoff"), json={}).json()["data"]["ticket"]
        )
    assert (
        client.get(f"{PREFIX}/handoffs?limit=2").json()["data"]["items"]
        == list(reversed(tickets))[0:2]
    )
    ticket = tickets[0]
    assert (
        client.post(f"{PREFIX}/handoffs/{ticket['id']}/resolve").json()["data"]["status"]
        == "resolved"
    )
    assert (
        client.get(f"{PREFIX}/handoffs?status=resolved").json()["data"]["items"][0]["id"]
        == ticket["id"]
    )
    for query in (
        "status=",
        "status=unknown",
        "status=open,",
        "status=open, resolved",
        "limit=0",
        "limit=51",
    ):
        assert_error(client.get(f"{PREFIX}/handoffs?{query}"), 422, "VALIDATION_ERROR")
    for action in ("acknowledge", "resolve"):
        assert_error(client.post(f"{PREFIX}/handoffs/missing/{action}"), 404, "HANDOFF_NOT_FOUND")


@pytest.mark.parametrize(
    "command", ["/help", "/product", "/lang es-ES", "/handoff", "/reset", "/unknown"]
)
def test_commands_replay_atomically_without_history(api_client, command):
    client, runtime = api_client
    conversation_id = create(client)
    request = {"content": command, "client_message_id": "command"}
    first = client.post(path(conversation_id, "/messages"), json=request)
    assert first.status_code == 200, first.text
    first = first.json()["data"]
    replay = client.post(path(conversation_id, "/messages"), json=request).json()["data"]
    assert UUID(first["message_id"])
    assert first["run_id"] is None and first["trace"] == []
    assert replay == {**first, "replayed": True}
    assert runtime.rows(StoredMessage) == runtime.rows(AgentRun) == []
    assert runtime.snapshot()["total_conversations"] == 0
    assert len(runtime.rows(CommandReceipt)) == 1
    assert len(runtime.rows(Conversation)) == (2 if command == "/reset" else 1)


async def test_http_concurrent_duplicate_waits_and_different_messages_keep_order(runtime_factory):
    provider = ScriptedProvider([Decision(reply="One"), Decision(reply="Two")], delay=0.03)
    runtime = runtime_factory(provider)
    conversation_id = create(runtime.client)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=runtime.app), base_url="http://test"
        ) as client:
            first, duplicate, second = await asyncio.gather(
                *[
                    client.post(
                        path(conversation_id, "/messages"),
                        json={"content": text, "client_message_id": key},
                    )
                    for text, key in (
                        ("First", "one"),
                        ("Changed duplicate", "one"),
                        ("Second", "two"),
                    )
                ]
            )
            assert first.status_code == duplicate.status_code == second.status_code == 200
            assert duplicate.json()["data"] == {**first.json()["data"], "replayed": True}

    await asyncio.wrap_future(runtime.client.portal.start_task_soon(exercise))
    assert len(provider.calls) == 2
    history = runtime.client.get(path(conversation_id, "/messages")).json()["data"]["items"]
    assert [item["content"] for item in history] == ["First", "One", "Second", "Two"]
    assert [item["seq"] for item in history] == [1, 2, 3, 4]


def test_failed_message_id_replays_error_without_another_run(api_client):
    client, runtime = api_client
    conversation_id = create(client)
    runtime.provider.decisions.append(AppError("LLM_TIMEOUT"))
    for _ in range(2):
        response = client.post(
            path(conversation_id, "/messages"),
            json={"content": "Hello", "client_message_id": "failure"},
        )
        assert_error(response, 504, "LLM_TIMEOUT")
    assert len(runtime.provider.calls) == len(runtime.rows(AgentRun)) == 1
    assert runtime.snapshot()["failed_requests"] == runtime.snapshot()["total_conversations"] == 1


@pytest.mark.parametrize("secret", [None, "merchant-secret"])
def test_merchant_key_applies_only_when_configured(runtime_factory, secret):
    runtime = runtime_factory(merchant_api_key=secret)
    client = runtime.client
    conversation_id = create(client)
    ticket = client.post(path(conversation_id, "/handoff"), json={}).json()["data"]["ticket"]
    merchant_paths = [
        ("GET", "/handoffs"),
        ("GET", "/dashboard/overview"),
        ("GET", "/dashboard/recent"),
        ("POST", f"/handoffs/{ticket['id']}/acknowledge"),
        ("POST", f"/handoffs/{ticket['id']}/resolve"),
    ]
    for method, endpoint in merchant_paths:
        if secret:
            for headers in ({}, {"X-Merchant-Key": "wrong"}):
                assert_error(
                    client.request(method, PREFIX + endpoint, headers=headers), 401, "UNAUTHORIZED"
                )
        response = client.request(
            method, PREFIX + endpoint, headers={"X-Merchant-Key": secret or "ignored"}
        )
        assert response.status_code == 200, response.text
    for endpoint in ("/catalog/products", "/status", "/health"):
        assert client.get(PREFIX + endpoint).status_code == 200
    assert client.get(f"{PREFIX}/dashboard/handoffs").status_code == 200
    legacy_ack = f"{PREFIX}/dashboard/handoffs/{ticket['id']}/acknowledge"
    if secret:
        assert client.post(legacy_ack).status_code != 401
    assert client.get(path(conversation_id)).status_code == 200


def test_unexpected_http_exception_is_safe_even_in_debug(runtime_factory, monkeypatch):
    runtime = runtime_factory(debug=True)

    async def fail():
        raise RuntimeError("INTERNAL-PRIVATE-STACK test-key")

    monkeypatch.setattr(runtime.service.catalog, "list_products", fail)
    response = runtime.client.get(f"{PREFIX}/catalog/products")
    assert_error(response, 500, "INTERNAL_ERROR")
    assert "INTERNAL-PRIVATE-STACK" not in response.text


def test_malformed_json_is_validation_envelope(api_client):
    client, _ = api_client
    assert_error(
        client.post(
            f"{PREFIX}/conversations", content="{", headers={"Content-Type": "application/json"}
        ),
        422,
        "VALIDATION_ERROR",
    )


def test_merchant_key_environment_value_is_redacted_from_logs(runtime_factory, monkeypatch):
    merchant_key = "merchant-env-test-secret"
    monkeypatch.setenv("MERCHANT_API_KEY", merchant_key)
    runtime = runtime_factory()
    formatters = [handler.formatter for handler in logging.getLogger().handlers]
    formatter = next(item for item in formatters if isinstance(item, RedactingFormatter))
    assert merchant_key in formatter.secrets
    assert "test-key" in formatter.secrets
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 0, "credentials %s %s", ("test-key", merchant_key), None
    )
    formatted = formatter.format(record)
    assert "test-key" not in formatted and merchant_key not in formatted
    assert formatted.count("[REDACTED]") == 2
    assert_error(runtime.client.get(f"{PREFIX}/dashboard/overview"), 401, "UNAUTHORIZED")


def test_openapi_lists_all_contract_paths_and_stream_events(api_client):
    client, _runtime = api_client
    schema = client.app.openapi()
    paths = schema["paths"]
    expected = {
        f"{PREFIX}/status",
        f"{PREFIX}/conversations",
        f"{PREFIX}/conversations/{{conversation_id}}",
        f"{PREFIX}/conversations/{{conversation_id}}/messages",
        f"{PREFIX}/conversations/{{conversation_id}}/messages/stream",
        f"{PREFIX}/conversations/{{conversation_id}}/reset",
        f"{PREFIX}/conversations/{{conversation_id}}/handoff",
        f"{PREFIX}/handoffs",
        f"{PREFIX}/handoffs/{{ticket_id}}/acknowledge",
        f"{PREFIX}/handoffs/{{ticket_id}}/resolve",
        f"{PREFIX}/dashboard/overview",
        f"{PREFIX}/dashboard/recent",
        f"{PREFIX}/catalog/products",
        f"{PREFIX}/health",
        f"{PREFIX}/agent/chat",
        f"{PREFIX}/dashboard/handoffs",
        f"{PREFIX}/dashboard/handoffs/{{record_id}}/acknowledge",
    }
    assert expected <= paths.keys()
    operation = paths[f"{PREFIX}/conversations/{{conversation_id}}/messages/stream"]["post"]
    assert operation["responses"]["200"]["content"]["text/event-stream"]
    assert set(operation["x-sse-events"]) == {
        "tool_started",
        "tool_finished",
        "delta",
        "completed",
        "analysis",
        "error",
    }
    schemas = schema["components"]["schemas"]
    assert "ErrorEnvelope" in schemas and "ValidationDetail" in schemas
    assert "LegacyAgentWorkflowData" in schemas
    assert "session_id" not in schemas["AgentWorkflowData"]["properties"]
    assert "session_id" in schemas["LegacyAgentWorkflowData"]["properties"]
    assert "issue_summary" in schemas["RecentInquiry"]["properties"]
    assert "422" in operation["responses"]


def test_phase3_demo_smoke_uses_new_conversation_and_merchant_apis(api_client):
    client, runtime = api_client
    runtime.provider.decisions.extend(
        [
            Decision(tool_calls=(ToolCall("search", "catalog_search", {"query": "headphones"}),)),
            Decision(
                tool_calls=(
                    ToolCall(
                        "shipping",
                        "catalog_shipping",
                        {"product_id": "headset-pro", "destination": "ES"},
                    ),
                )
            ),
            Decision(reply="The headphones ship to Spain in 5-8 business days."),
            Decision(reply="It takes 5-8 business days."),
            Decision(
                tool_calls=(
                    ToolCall(
                        "after-sales",
                        "after_sales_record",
                        {"issue": "Headphones will not turn on", "product_id": "headset-pro"},
                    ),
                )
            ),
            Decision(reply="Your issue is recorded for merchant review."),
        ]
    )
    conversation_id = create(client, reply_language="en-US")

    def send(content, client_message_id):
        response = client.post(
            path(conversation_id, "/messages"),
            json={"content": content, "client_message_id": client_message_id},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert set(data) == PUBLIC_WORKFLOW_FIELDS
        return data

    first = send("Do the headphones ship to Spain?", "demo-1")
    followup = send("How long is delivery?", "demo-2")
    after_sales = send("Please register this issue", "demo-3")
    assert first["matched_product"] == "星云降噪耳机 Pro"
    assert first["trace"][-1]["name"] == "catalog_shipping"
    assert followup["product_id"] == "headset-pro"
    assert after_sales["needs_human"] is True
    assert after_sales["source"] == "native+human-handoff"
    ticket = client.get(f"{PREFIX}/handoffs").json()["data"]["items"][0]
    assert ticket["conversation_id"] == after_sales["conversation_id"]
    assert ticket["reason_code"] == "after_sales"
    assert ticket["customer_message"] == "Please register this issue"
    acknowledged = client.post(f"{PREFIX}/handoffs/{ticket['id']}/acknowledge")
    assert acknowledged.status_code == 200
    assert acknowledged.json()["data"]["status"] == "acknowledged"

    paused = send("Can you help me?", "demo-4")
    assert paused["source"] == "paused-for-human"
    assert paused["run_id"] is None
    conversation = client.get(path(conversation_id)).json()["data"]
    assert conversation["status"] == "human_active"
    assert conversation["open_handoff"]["id"] == ticket["id"]
    assert client.get(path(conversation_id, "/messages")).json()["data"]["has_more"] is False
    overview = client.get(f"{PREFIX}/dashboard/overview").json()["data"]
    assert overview["total_conversations"] == 4
    assert overview["human_handoffs"] == 1
    assert overview["pending_handoffs"] == 0
    recent = client.get(f"{PREFIX}/dashboard/recent").json()["data"]
    assert len(recent) == 3
    assert all(item["conversation_id"] == conversation_id for item in recent)
    assert "issue_summary" in recent[0]
    assert client.get(f"{PREFIX}/handoffs").json()["data"]["items"][0]["status"] == "acknowledged"
    assert runtime.snapshot()["total_conversations"] == 4
    assert len(runtime.rows(AgentRun)) == 3
    assert len(runtime.provider.calls) == 6


def test_completed_analysis_is_restored_after_application_restart(runtime_factory):
    from tests.test_phase2_analysis import outcome

    provider = ScriptedProvider([Decision(reply="Hello")])
    analysis = ScriptedProvider([Decision(reply=json.dumps(outcome()))])
    first = runtime_factory(provider, analysis_provider=analysis, analysis_enabled=True)
    conversation_id = create(first.client)
    saved = first.client.post(
        path(conversation_id, "/messages"), json={"content": "Hola", "client_message_id": "restart"}
    ).json()["data"]
    second = runtime_factory(database_url=first.database.url)
    replay = second.client.post(
        path(conversation_id, "/messages"), json={"content": "Hola", "client_message_id": "restart"}
    ).json()["data"]
    assert saved["analysis_source"] == "llm"
    assert replay == {**saved, "replayed": True}
    assert (
        second.client.get(path(conversation_id, "/messages")).json()["data"]["items"][1]["workflow"]
        == saved
    )
    assert second.provider.calls == []
