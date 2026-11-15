import asyncio
import json
from dataclasses import replace

from app.agent.context import ContextBuilder, estimate_tokens, history_groups
from app.domain.types import InboundMessage, Session, Turn
from tests.support import Decision, ScriptedProvider


class TestCatalog:
    async def get(self, _product_id):
        return None


def tool_history():
    calls = tuple(
        {"id": name, "type": "function", "function": {"name": "catalog_specs", "arguments": "{}"}}
        for name in ("one", "two")
    )
    return [
        Turn("user", "Earlier " * 1000, ""),
        Turn("assistant", "", "", calls),
        Turn("tool", json.dumps({"text": "A" * 2000}), "", tool_call_id="one"),
        Turn("tool", json.dumps({"text": "B" * 2000}), "", tool_call_id="two"),
        Turn("assistant", "Final answer", ""),
    ]


async def test_budget_never_retains_half_a_tool_group():
    turns = tool_history()
    session = Session("context", turns=turns)
    builder = ContextBuilder("Support agent", TestCatalog(), 10000, 200)
    inbound = InboundMessage("Latest")
    full = await builder.build(inbound, session)
    groups = history_groups(turns, 200)
    base = estimate_tokens(full[0]) + estimate_tokens(full[-1])
    final_cost = sum(estimate_tokens(message) for message in groups[-1])
    bundle_cost = sum(estimate_tokens(message) for message in groups[-2])
    builder.token_budget = base + final_cost + bundle_cost - 1
    clipped = await builder.build(inbound, session)
    assert [message.role for message in clipped] == ["system", "assistant", "user"]
    assert clipped[1].content == "Final answer" and clipped[-1].content == "Latest"
    assert sum(estimate_tokens(message) for message in clipped) <= builder.token_budget

    builder.token_budget += 1
    complete = await builder.build(inbound, session)
    assert [message.role for message in complete] == [
        "system",
        "assistant",
        "tool",
        "tool",
        "assistant",
        "user",
    ]
    assert {message.tool_call_id for message in complete if message.role == "tool"} == {
        "one",
        "two",
    }
    assert all(len(message.content) <= 200 for message in complete if message.role == "tool")
    assert all(
        "[tool result truncated]" in message.content
        for message in complete
        if message.role == "tool"
    )


async def test_orphan_and_incomplete_tool_groups_are_dropped():
    session = Session(
        "context",
        turns=[
            Turn("tool", "orphan", "", tool_call_id="orphan"),
            *tool_history()[1:3],
            Turn("assistant", "Valid answer", ""),
        ],
    )
    messages = await ContextBuilder("Support", TestCatalog()).build(
        InboundMessage("Latest"), session
    )
    assert [message.role for message in messages] == ["system", "assistant", "user"]
    assert messages[1].content == "Valid answer"


async def test_context_reads_live_product_state_and_contains_summary(runtime_factory):
    from sqlalchemy import update

    from app.repositories.models import StoredProduct

    runtime = runtime_factory()
    snapshot = runtime.session("context")
    snapshot.focused_product_ids = ("headset-pro",)
    snapshot.destination_country, snapshot.quantity = "ES", 10
    snapshot.summary, snapshot.status, snapshot.reply_language = (
        "Earlier facts",
        "pending_human",
        "es-ES",
    )
    async with runtime.database.transaction() as transaction:
        await transaction.execute(
            update(StoredProduct).where(StoredProduct.id == "headset-pro").values(price_usd=41)
        )
    messages = await runtime.service.context.build(InboundMessage("Hello"), snapshot)
    assert '"price_usd": 41' in messages[0].content
    assert (
        '"destination_country": "ES"' in messages[0].content
        and '"quantity": 10' in messages[0].content
    )
    assert '"handoff_status": "pending_human"' in messages[0].content
    assert "Earlier facts" in messages[0].content and "Reply in es-ES." in messages[0].content


async def test_summary_is_optional_and_does_not_delay_reply(runtime_factory):
    started, release = asyncio.Event(), asyncio.Event()

    class SummaryProvider(ScriptedProvider):
        async def complete(self, *args, **kwargs):
            started.set()
            await release.wait()
            return Decision(reply="SUMMARY-MARKER prior confirmed facts")

    summary_provider = SummaryProvider()
    runtime = runtime_factory(
        ScriptedProvider([Decision(reply="A" * 9000), Decision(reply="Second answer")]),
        analysis_provider=summary_provider,
        summary_enabled=True,
        context_token_budget=1024,
    )
    await runtime.service.handle_inbound(InboundMessage("First question", "summary"))
    second = await runtime.service.handle_inbound(InboundMessage("Second question", "summary"))
    assert second.reply == "Second answer"
    await asyncio.wait_for(started.wait(), 1)
    assert runtime.session("summary").summary is None
    release.set()
    await asyncio.gather(*tuple(runtime.app.state.background.tasks))
    assert "SUMMARY-MARKER" in runtime.session("summary").summary
    assert len(runtime.session("summary").turns) == 4


async def test_stale_summary_cannot_replace_newer_context(runtime_factory):
    runtime = runtime_factory()
    original = runtime.session("summary")
    changed = await runtime.service.store.save_state(
        replace(original, focused_product_ids=("headset-pro",))
    )
    assert not await runtime.service.store.update_summary(
        original.session_id, original.version, "stale"
    )
    assert await runtime.service.store.update_summary(
        changed.session_id, changed.version, "current"
    )
    assert runtime.session("summary").summary == "current"
