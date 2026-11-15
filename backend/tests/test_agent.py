import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agent.llm.openai import parse_response
from app.core.errors import AppError
from app.domain.types import InboundMessage, Message, ToolCall
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
    assert runtime.snapshot()["total_conversations"] == 1
    session = runtime.session("s1")
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
    assert runtime.snapshot()["human_handoffs"] == 1


async def test_follow_up_reuses_session_product(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider(
            [
                Decision(
                    tool_calls=(ToolCall("focus", "catalog_search", {"query": "headphones"}),)
                ),
                Decision(reply="First reply."),
                Decision(reply="Second reply."),
            ]
        )
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
    assert runtime.snapshot()["total_conversations"] == 1
    assert len(runtime.session("test-session").turns) == 1
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
    assert runtime.session("s5").turns == []


async def test_lang_command_sets_language(runtime_factory):
    runtime = runtime_factory()
    await send(runtime, "/lang es-ES", "s6")
    assert runtime.session("s6").reply_language == "es-ES"
    assert runtime.snapshot()["total_conversations"] == 0


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


async def test_old_timestamp_does_not_remove_append_only_history(runtime_factory):
    from sqlalchemy import update

    from app.repositories.models import Conversation

    runtime = runtime_factory(ScriptedProvider([Decision(reply="Hello")]))
    await send(runtime, "Hi", "old-conversation")
    snapshot = runtime.session("old-conversation")
    original = [(turn.id, turn.content) for turn in snapshot.turns]
    async with runtime.database.transaction() as transaction:
        await transaction.execute(
            update(Conversation)
            .where(Conversation.id == snapshot.session_id)
            .values(updated_at=(datetime.now(UTC) - timedelta(hours=48)).isoformat())
        )
    assert [
        (turn.id, turn.content) for turn in runtime.session("old-conversation").turns
    ] == original


@pytest.mark.parametrize("corrupt_turns", ["{broken", "null", "[1]", '[{"unexpected": 1}]'])
async def test_corrupt_legacy_history_is_not_imported(runtime_factory, corrupt_turns):
    from sqlalchemy import text

    runtime = runtime_factory()
    snapshot = runtime.session("legacy")
    snapshot.focused_product_ids, snapshot.reply_language = ("headset-pro",), "es-ES"
    await runtime.service.store.save_state(snapshot)
    async with runtime.database.transaction() as transaction:
        await transaction.execute(text("CREATE TABLE agent_sessions (session_id TEXT, turns TEXT)"))
        await transaction.execute(
            text("INSERT INTO agent_sessions VALUES ('legacy', :turns)"), {"turns": corrupt_turns}
        )
    loaded = runtime.session("legacy")
    assert loaded.turns == []
    assert loaded.focused_product_ids == ("headset-pro",) and loaded.reply_language == "es-ES"


@pytest.mark.parametrize("corrupt_focus", ["{broken", '"headset-pro"', "[1]"])
async def test_corrupt_legacy_focus_is_not_imported(runtime_factory, corrupt_focus):
    from sqlalchemy import text

    runtime = runtime_factory()
    snapshot = runtime.session("legacy")
    snapshot.focused_product_ids = ("headset-pro",)
    await runtime.service.store.save_state(snapshot)
    async with runtime.database.transaction() as transaction:
        await transaction.execute(
            text("CREATE TABLE agent_sessions (session_id TEXT, focused_product_ids TEXT)")
        )
        await transaction.execute(
            text("INSERT INTO agent_sessions VALUES ('legacy', :focus)"), {"focus": corrupt_focus}
        )
    assert runtime.session("legacy").focused_product_ids == ("headset-pro",)


async def test_unexpected_service_failure_is_persisted_and_redacted(runtime_factory, monkeypatch):
    runtime = runtime_factory()

    def fail(*_args):
        raise RuntimeError("PRIVATE-SERVICE-DETAIL")

    monkeypatch.setattr(runtime.service.store, "get", fail)
    with pytest.raises(AppError) as error:
        await send(runtime, "Hello")
    assert error.value.code == "INTERNAL_ERROR"
    assert "PRIVATE-SERVICE-DETAIL" not in str(error.value)
    snapshot = runtime.snapshot()
    assert snapshot["failed_requests"] == 1 and snapshot["total_conversations"] == 0
