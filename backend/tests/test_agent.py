import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agent.llm.openai import parse_response
from app.core.errors import AppError
from app.domain.types import InboundMessage, Message, Session, ToolCall, Turn
from tests.support import Decision, ScriptedProvider


async def send(runtime, message, session_id="test-session"):
    from app.api.v1.presenters import present_workflow

    result = await runtime.service.handle_inbound(InboundMessage(message, session_id))
    return {"status": "ok", "data": present_workflow(result).model_dump(), "message": None}


async def test_tool_calling_loop_returns_model_reply_and_archives(runtime_factory):
    provider = ScriptedProvider(
        [
            Decision(tool_calls=(ToolCall("c1", "catalog_search", {"query": "headphones"}),)),
            Decision(reply="The headphones cost USD 39.00."),
        ]
    )
    runtime = runtime_factory(provider)
    result = await send(runtime, "Please quote the headphones", "s1")
    assert result["status"] == "ok"
    assert result["data"]["reply"] == "The headphones cost USD 39.00."
    assert result["data"]["source"] == "native"
    assert result["data"]["matched_product"] == "星云降噪耳机 Pro"
    assert len(provider.calls) == 2
    assert "catalog_search" in [item["function"]["name"] for item in provider.calls[0]["tools"]]
    assert any(message.role == "tool" for message in provider.calls[1]["messages"])
    assert runtime.metrics.snapshot()["total_conversations"] == 1
    session = runtime.service.store.load("s1")
    assert (
        len(
            [
                turn
                for turn in session.turns
                if turn.role == "user" or turn.role == "assistant" and not turn.tool_calls
            ]
        )
        == 2
    )
    assert any(turn.role == "tool" for turn in session.turns)
    assert session.last_product_id == "headset-pro"


async def test_after_sales_tool_triggers_human_handoff(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider(
            [
                Decision(
                    tool_calls=(ToolCall("c1", "after_sales_record", {"issue": "arrived damaged"}),)
                ),
                Decision(reply="I have recorded your request."),
            ]
        )
    )
    result = await send(runtime, "The headset arrived damaged.", "s2")
    assert result["data"]["needs_human"]
    assert result["data"]["source"] == "native+human-handoff"
    assert runtime.metrics.snapshot()["human_handoffs"] == 1


async def test_follow_up_reuses_session_product(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider([Decision(reply="First reply."), Decision(reply="Second reply.")])
    )
    await send(runtime, "Please quote the headphones", "s3")
    result = await send(runtime, "And how long is the delivery time?", "s3")
    assert result["data"]["matched_product"] == "星云降噪耳机 Pro"
    assert result["data"]["product_confidence"] == 0.72


async def test_missing_api_key_raises(runtime_factory):
    provider = ScriptedProvider()
    provider.is_configured = False
    runtime = runtime_factory(provider)
    with pytest.raises(AppError) as error:
        await send(runtime, "hello")
    assert error.value.code == "LLM_NOT_CONFIGURED"
    assert runtime.metrics.snapshot()["total_conversations"] == 0
    assert provider.calls == []


async def test_tool_round_limit_forces_final_text_reply(runtime_factory):
    provider = ScriptedProvider(
        [
            *[
                Decision(
                    tool_calls=(ToolCall(f"c{index}", "catalog_search", {"query": "headphones"}),)
                )
                for index in range(3)
            ],
            Decision(reply="Final answer using the available facts."),
        ]
    )
    runtime = runtime_factory(provider)
    result = await send(runtime, "Please quote the headphones")
    assert result["data"]["reply"] == "Final answer using the available facts."
    assert [call["tool_choice"] for call in provider.calls] == ["auto", "auto", "auto", "none"]
    assert all(call["tools"] for call in provider.calls)


async def test_help_command_bypasses_model(runtime_factory):
    runtime = runtime_factory()
    assert "可用指令" in (await send(runtime, "/help"))["data"]["reply"]
    assert not runtime.provider.calls


async def test_reset_clears_session_history(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="hello")]))
    await send(runtime, "Please quote the headphones", "s5")
    await send(runtime, "/reset", "s5")
    assert runtime.service.store.load("s5").turns == []


async def test_lang_command_sets_language(runtime_factory):
    runtime = runtime_factory()
    await send(runtime, "/lang es-ES", "s6")
    assert runtime.service.store.load("s6").reply_language == "es-ES"
    assert runtime.metrics.snapshot()["total_conversations"] == 0


async def test_handoff_command_marks_needs_human(runtime_factory):
    runtime = runtime_factory()
    result = await send(runtime, "/handoff", "s7")
    assert result["data"]["needs_human"]
    assert result["data"]["source"] == "native+human-handoff"


def test_schemas_expose_configured_builtin_tools(runtime_factory):
    runtime = runtime_factory()
    schemas = runtime.service.runner.registry.schemas()
    names = [item["function"]["name"] for item in schemas]
    assert len(names) == 5
    assert "catalog_quote" in names and "after_sales_record" in names
    assert "knowledge_search" not in names


async def test_catalog_quote_returns_price(runtime_factory):
    runtime = runtime_factory()
    result = await runtime.service.runner.registry.invoke(
        "catalog_quote", {"product_id": "headset-pro"}, runtime.service.tool_deps
    )
    assert result.ok
    assert json.loads(result.content)["price_usd"] == 39.0


async def test_unknown_tool_returns_failure(runtime_factory):
    runtime = runtime_factory()
    result = await runtime.service.runner.registry.invoke(
        "missing_tool", {}, runtime.service.tool_deps
    )
    assert not result.ok
    assert json.loads(result.content)["error"]["code"] == "UNKNOWN_TOOL"


def test_plain_content():
    assert parse_response({"choices": [{"message": {"content": "hello"}}]}).content == "hello"


def test_tool_calls():
    body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {
                                "name": "catalog_search",
                                "arguments": json.dumps({"query": "lamp"}),
                            },
                        },
                    ]
                }
            }
        ]
    }
    response = parse_response(body)
    assert response.tool_calls[0].name == "catalog_search"
    assert json.loads(response.tool_calls[0].arguments) == {"query": "lamp"}


def test_empty_choices_raises():
    with pytest.raises(AppError, match="响应无法解析"):
        parse_response({"choices": []})


def test_message_serialization():
    assistant = Message(
        role="assistant",
        tool_calls=(
            {"id": "c1", "type": "function", "function": {"name": "x", "arguments": "{}"}},
        ),
    )
    assert "tool_calls" in assistant.to_openai()
    assert (
        Message(role="tool", content="{}", tool_call_id="c1", name="x").to_openai()["tool_call_id"]
        == "c1"
    )


def test_ttl_expires_session(runtime_factory):
    runtime = runtime_factory()
    store = runtime.service.store
    session = Session("s")
    store.append(session, Turn("user", "hi", datetime.now(UTC).isoformat()))
    store.connection.execute(
        "UPDATE agent_sessions SET updated_at=? WHERE session_id=?",
        ((datetime.now(UTC) - timedelta(hours=48)).isoformat(), "s"),
    )
    store.connection.commit()
    assert store.load("s", 24).turns == []


@pytest.mark.parametrize("corrupt_turns", ["{broken", "null", "[1]", '[{"unexpected": 1}]'])
def test_corrupt_legacy_history_keeps_session_preferences(runtime_factory, corrupt_turns):
    store = runtime_factory().service.store
    store.save(Session("legacy", focused_product_ids=("headset-pro",), reply_language="es-ES"))
    store.connection.execute(
        "UPDATE agent_sessions SET turns=? WHERE session_id=?", (corrupt_turns, "legacy")
    )
    store.connection.commit()
    loaded = store.load("legacy")
    assert loaded.turns == []
    assert loaded.focused_product_ids == ("headset-pro",)
    assert loaded.reply_language == "es-ES"


@pytest.mark.parametrize("corrupt_focus", ["{broken", '"headset-pro"', "[1]"])
def test_corrupt_focus_recovers_legacy_product(runtime_factory, corrupt_focus):
    store = runtime_factory().service.store
    store.save(Session("legacy", focused_product_ids=("headset-pro",)))
    store.connection.execute(
        "UPDATE agent_sessions SET focused_product_ids=? WHERE session_id=?",
        (corrupt_focus, "legacy"),
    )
    store.connection.commit()
    assert store.load("legacy").focused_product_ids == ("headset-pro",)


async def test_unexpected_service_failure_is_persisted_and_redacted(runtime_factory, monkeypatch):
    runtime = runtime_factory()

    def fail(*_args):
        raise RuntimeError("PRIVATE-SERVICE-DETAIL")

    monkeypatch.setattr(runtime.service.store, "load", fail)
    with pytest.raises(AppError) as error:
        await send(runtime, "Hello")
    assert error.value.code == "INTERNAL_ERROR"
    assert "PRIVATE-SERVICE-DETAIL" not in str(error.value)
    snapshot = runtime.metrics.snapshot()
    assert snapshot["failed_requests"] == 1 and snapshot["total_conversations"] == 0
