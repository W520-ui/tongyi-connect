"""Desired behavior for defects 1–12; phase 0 intentionally keeps these red."""

import asyncio
import json

import pytest

from app.agent.models import AgentContext, Decision, Session, ToolCall
from app.agent.registry import create_default_registry
from app.schemas.agent import AgentChatRequest
from app.services.workflow import WorkflowMetrics, analyze_message
from tests.support import ScriptedProvider


def defect(number, *, phase=1):
    return pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=f"Defect {number}: scheduled for phase {phase}",
    )


async def send(runtime, message, session_id="regression"):
    return (await runtime.engine.chat(AgentChatRequest(message=message, session_id=session_id)))[
        "data"
    ]


@defect(1)
@pytest.mark.parametrize(
    "message,property_name,expected",
    [
        ("Can I cancel my order?", "product", None),
        ("Do you ship to France?", "product", None),
        ("I'm a returning customer, what's the price?", "intent", "quote"),
        ("I'm a returning customer, what's the price?", "needs_human", False),
        ("Is it lightweight enough for a flight?", "product", None),
        ("Is this especially good for kids?", "intent", "general"),
        ("你们客服会说英语吗？", "language", "zh-CN"),
    ],
)
def test_defect_01_substrings_do_not_change_business_classification(
    message, property_name, expected
):
    assert getattr(analyze_message(message), property_name) == expected


@pytest.mark.parametrize(
    "message,field,expected",
    [
        ("I want a refund", "intent", "after_sales"),
        ("我要退货", "intent", "after_sales"),
        ("Nebula ANC Headphones Pro", "product_id", "headset-pro"),
        ("降噪耳机", "product_id", "headset-pro"),
        ("请用英文回复：耳机多少钱？", "language", "en-US"),
    ],
)
def test_defect_01_true_positives_are_preserved(message, field, expected):
    analysis = analyze_message(message)
    actual = analysis.product["id"] if field == "product_id" else getattr(analysis, field)
    assert actual == expected


@defect(2)
async def test_defect_02_reset_clears_product_and_archive_fallback(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider([Decision(reply="Quote"), Decision(reply="Which product?")])
    )
    await send(runtime, "Please quote the headphones")
    await send(runtime, "/reset")
    product = await send(runtime, "/product")
    followup = await send(runtime, "How long is the delivery?")
    assert "headset-pro" not in product["reply"]
    assert "星云降噪耳机" not in product["reply"]
    assert followup["product_id"] is None
    assert runtime.engine.store.load("regression").last_product_id is None


@defect(3)
async def test_defect_03_explicit_language_survives_customer_language_change(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider([Decision(reply="Primera respuesta"), Decision(reply="Segunda respuesta")])
    )
    await send(runtime, "/lang es-ES")
    await send(runtime, "Hello, tell me more.")
    await send(runtime, "And what else?")
    assert runtime.engine.store.load("regression").language == "es-ES"
    assert "es-ES" in runtime.provider.calls[-1]["messages"][0].content


@defect(3)
async def test_defect_03_invalid_language_is_rejected(runtime_factory):
    runtime = runtime_factory()
    result = await send(runtime, "/lang foo")
    assert runtime.engine.store.load("regression").language != "foo"
    assert all(language in result["reply"] for language in ("zh-CN", "en-US", "es-ES"))


async def command_sequence(runtime):
    await send(runtime, "First real inquiry")
    await send(runtime, "/help")
    await send(runtime, "/product")
    await send(runtime, "/lang es-ES")
    await send(runtime, "Second real inquiry")
    await send(runtime, "Third real inquiry")


@defect(4)
async def test_defect_04_commands_do_not_increment_consultation_counts(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Answer") for _ in range(3)]))
    await command_sequence(runtime)
    assert runtime.metrics.snapshot()["total_conversations"] == 3


@defect(4)
async def test_defect_04_commands_and_their_replies_are_absent_from_model_history(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Answer") for _ in range(3)]))
    await command_sequence(runtime)
    history = [message.content for message in runtime.provider.calls[-1]["messages"][1:]]
    assert history == [
        "First real inquiry",
        "Answer",
        "Second real inquiry",
        "Answer",
        "Third real inquiry",
    ]


@defect(5)
async def test_defect_05_handoff_preserves_user_request_reason(runtime_factory):
    runtime = runtime_factory()
    await send(runtime, "/handoff")
    assert runtime.metrics.recent_handoffs()[0]["handoff_reason"] == "用户主动请求人工接管"


@defect(6)
async def test_defect_06_anonymous_requests_receive_independent_session_ids(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="One"), Decision(reply="Two")]))
    first = await send(runtime, "FIRST-ANONYMOUS-MARKER", None)
    second = await send(runtime, "SECOND-ANONYMOUS-MARKER", None)
    context = runtime.provider.calls[1]["messages"]
    assert not any("FIRST-ANONYMOUS-MARKER" in message.content for message in context)
    assert isinstance(first.get("session_id"), str) and first["session_id"]
    assert isinstance(second.get("session_id"), str) and second["session_id"]
    assert first["session_id"] != second["session_id"]


@defect(7)
async def test_defect_07_concurrent_inbound_messages_are_all_saved_in_order(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider(
            [Decision(reply="First reply"), Decision(reply="Second reply")], delay=0.05
        )
    )
    await asyncio.gather(send(runtime, "First inquiry"), send(runtime, "Second inquiry"))
    turns = runtime.engine.store.load("regression").turns
    assert [(turn.role, turn.content) for turn in turns] == [
        ("user", "First inquiry"),
        ("assistant", "First reply"),
        ("user", "Second inquiry"),
        ("assistant", "Second reply"),
    ]


@defect(8)
async def test_defect_08_statistics_are_consistent_between_instances(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Recorded your request.")]))
    second = WorkflowMetrics(runtime.metrics.db_path)
    try:
        await send(runtime, "I want a refund")
        snapshot = second.snapshot()
        assert {
            key: snapshot[key]
            for key in ("total_conversations", "human_handoffs", "pending_handoffs")
        } == {
            "total_conversations": 1,
            "human_handoffs": 1,
            "pending_handoffs": 1,
        }
    finally:
        second.close()


@defect(9)
@pytest.mark.parametrize("observable", ["database", "merchant_queue"])
async def test_defect_09_after_sales_issue_is_persisted_and_visible(runtime_factory, observable):
    issue = "ISSUE-MARKER screen cracked on arrival"
    provider = ScriptedProvider(
        [
            Decision(tool_calls=(ToolCall("issue", "after_sales_record", {"issue": issue}),)),
            Decision(reply="Recorded."),
        ]
    )
    runtime = runtime_factory(provider)
    await send(runtime, "Please ask the merchant to help.")
    assert len(provider.calls) == 2
    if observable == "database":
        row = runtime.metrics.connection.execute("SELECT * FROM workflow_conversations").fetchone()
        assert dict(row).get("issue_summary") == issue
    else:
        assert issue in json.dumps(runtime.metrics.recent_handoffs()[0], ensure_ascii=False)


@defect(10)
@pytest.mark.parametrize("observable", ["card", "steps", "session"])
async def test_defect_10_tool_results_drive_cards_and_product_memory(runtime_factory, observable):
    provider = ScriptedProvider(
        [
            Decision(tool_calls=(ToolCall("search", "catalog_search", {"query": "nebula"}),)),
            Decision(
                tool_calls=(ToolCall("quote", "catalog_quote", {"product_id": "headset-pro"}),)
            ),
            Decision(reply="The headphones cost USD 39.00."),
        ]
    )
    runtime = runtime_factory(provider)
    data = await send(runtime, "How much is the Nebula?")
    assert len(provider.calls) == 3
    if observable == "card":
        assert data["matched_product"] == "星云降噪耳机 Pro"
        assert data["product_id"] == "headset-pro"
    elif observable == "steps":
        steps = "\n".join(data["steps"])
        assert "catalog_search" in steps and "catalog_quote" in steps
        assert steps.index("catalog_search") < steps.index("catalog_quote")
    else:
        assert runtime.engine.store.load("regression").last_product_id == "headset-pro"


def shipping_context():
    return AgentContext(
        session_id="shipping", session=Session("shipping"), analysis=analyze_message("hi")
    )


async def test_defect_11_known_spain_shipping_remains_available():
    result = await create_default_registry().invoke(
        "catalog_shipping",
        {"product_id": "headset-pro", "destination": "ES"},
        shipping_context(),
    )
    payload = json.loads(result.content)
    assert result.ok
    assert payload["international_shipping"] is True
    assert payload["shipping_days"] == "5–8 个工作日"


@defect(11)
async def test_defect_11_unconfirmed_destination_does_not_claim_delivery():
    result = await create_default_registry().invoke(
        "catalog_shipping",
        {"product_id": "headset-pro", "destination": "AQ"},
        shipping_context(),
    )
    payload = json.loads(result.content)
    assert payload.get("availability") == "unconfirmed"
    assert payload.get("international_shipping") is not True


@defect(11)
async def test_defect_11_invalid_country_returns_tool_error_to_model(runtime_factory):
    provider = ScriptedProvider(
        [
            Decision(
                tool_calls=(
                    ToolCall(
                        "mars",
                        "catalog_shipping",
                        {"product_id": "headset-pro", "destination": "Mars"},
                    ),
                )
            ),
            Decision(reply="Please confirm the destination country."),
        ]
    )
    runtime = runtime_factory(provider)
    data = await send(runtime, "Can this reach my destination?")
    tool_messages = [
        message for message in provider.calls[-1]["messages"] if message.role == "tool"
    ]
    assert len(tool_messages) == 1
    assert "international_shipping" not in tool_messages[0].content
    assert data["reply"] == "Please confirm the destination country."


@defect(12, phase=2)
async def test_defect_12_scripted_post_analysis_supplies_chinese_translation(runtime_factory):
    translation = "你好，耳机寄往墨西哥需要多长时间？"
    analysis = {
        "intents": ["logistics"],
        "language": "es-ES",
        "product_ids": ["headset-pro"],
        "needs_human": False,
        "handoff_reason": None,
        "merchant_summary_zh": f"客户咨询物流。中文译文：{translation}",
    }
    provider = ScriptedProvider(
        [
            Decision(reply="Necesitamos confirmar el envío con el comerciante."),
            Decision(reply=json.dumps(analysis, ensure_ascii=False)),
        ]
    )
    runtime = runtime_factory(provider)
    data = await send(runtime, "Hola, ¿cuánto tarda el envío de los auriculares a México?")
    assert translation in data["merchant_summary"]
    assert data["intent"] == "logistics"
    assert data.get("analysis_source") == "llm"
    assert len(provider.calls) == 2
