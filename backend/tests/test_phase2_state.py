import asyncio
from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.domain.types import InboundMessage, WorkflowResult
from app.repositories.models import AgentRun, HandoffTicket, StoredMessage
from app.services.conversation import PAUSED_REPLIES
from tests.support import Decision, ScriptedProvider


async def send(runtime, message, session_id="state", **kwargs):
    return await runtime.service.handle_inbound(InboundMessage(message, session_id, **kwargs))


async def test_reset_closes_old_conversation_and_preserves_append_only_messages(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Quote")]))
    original = await send(runtime, "Please quote the headphones")
    await send(runtime, "/lang es-ES")
    await send(runtime, "/handoff")
    ticket_id = runtime.pending()[0]["id"]
    assert await runtime.handoffs.acknowledge(ticket_id)
    before = [(turn.id, turn.content) for turn in runtime.session("state").turns]
    reset = await send(runtime, "/reset")
    assert UUID(reset.session_id) and reset.session_id != original.session_id
    previous = await runtime.service.store.get(original.session_id)
    current = await runtime.service.store.get(reset.session_id)
    assert previous.status == "resolved"
    assert [(turn.id, turn.content) for turn in previous.turns] == before
    assert current.status == "bot_active" and current.turns == []
    assert current.focused_product_ids == () and current.reply_language is None
    assert runtime.session("state").session_id == reset.session_id
    assert runtime.rows(HandoffTicket)[0].status == "resolved"
    assert runtime.snapshot()["total_conversations"] == 1


@pytest.mark.parametrize(
    "preference,message,expected",
    [
        ("es-ES", "Hello", "es-ES"),
        ("en-US", "你好", "en-US"),
        (None, "¿Envían a España?", "es-ES"),
        (None, "Hello", "en-US"),
        (None, "你好", "zh-CN"),
        (None, "🙂", "zh-CN"),
    ],
)
async def test_human_active_saves_customer_only_and_uses_fixed_language(
    runtime_factory, preference, message, expected
):
    runtime = runtime_factory()
    if preference:
        await send(runtime, "/lang " + preference)
    await send(runtime, "/handoff")
    ticket = runtime.pending()[0]
    assert await runtime.handoffs.acknowledge(ticket["id"])
    result = await send(runtime, message)
    assert result.reply == PAUSED_REPLIES[expected]
    assert result.source == "paused-for-human" and result.run_id is None
    assert result.conversation_status == "human_active" and result.needs_human
    assert [(turn.role, turn.content) for turn in runtime.session("state").turns] == [
        ("user", message)
    ]
    assert runtime.provider.calls == [] and runtime.rows(AgentRun) == []
    assert runtime.snapshot()["total_conversations"] == 1


async def test_human_active_commands_execute_without_history_or_counts(runtime_factory):
    runtime = runtime_factory()
    await send(runtime, "/handoff")
    assert await runtime.handoffs.acknowledge(runtime.pending()[0]["id"])
    for command in ("/help", "/product", "/lang es-ES", "/handoff", "/unknown"):
        result = await send(runtime, command)
        assert result.reply and result.run_id is None and result.trace.calls == ()
    assert runtime.session("state").reply_language == "es-ES"
    assert runtime.session("state").status == "human_active"
    assert runtime.session("state").turns == []
    assert runtime.snapshot()["total_conversations"] == 0
    assert runtime.snapshot()["human_handoffs"] == 1
    assert runtime.provider.calls == []


async def test_pending_handoff_deduplicates_and_resolved_conversation_resumes(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider(
            [Decision(reply="First"), Decision(reply="Second"), Decision(reply="Resumed")]
        )
    )
    first = await send(runtime, "I want a refund")
    second = await send(runtime, "I still want a refund")
    assert first.handoff_id == second.handoff_id and len(runtime.rows(HandoffTicket)) == 1
    assert second.conversation_status == "pending_human"
    assert await runtime.handoffs.acknowledge(first.handoff_id)
    assert not await runtime.handoffs.acknowledge(first.handoff_id)
    await runtime.handoffs.resolve(first.handoff_id)
    with pytest.raises(AppError) as error:
        await runtime.handoffs.resolve(first.handoff_id)
    assert error.value.code == "INVALID_STATE"
    resumed = await send(runtime, "Hello again")
    assert resumed.session_id == first.session_id and resumed.conversation_status == "bot_active"
    assert not resumed.needs_human and resumed.source == "native"
    assert runtime.snapshot()["total_conversations"] == 3
    assert runtime.snapshot()["pending_handoffs"] == 0


async def test_one_transaction_rolls_back_messages_state_run_and_ticket(
    runtime_factory, monkeypatch
):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Recorded")]))
    original = runtime.session("state")

    async def fail(*_args):
        raise RuntimeError("PRIVATE-TRANSACTION-DETAIL")

    monkeypatch.setattr(runtime.handoffs, "request", fail)
    with pytest.raises(AppError) as error:
        await send(runtime, "I want a refund for the headphones")
    assert error.value.code == "INTERNAL_ERROR"
    assert "PRIVATE-TRANSACTION-DETAIL" not in str(error.value)
    current = runtime.session("state")
    assert current.version == original.version and current.status == "bot_active"
    assert current.focused_product_ids == () and current.turns == []
    assert (
        runtime.rows(StoredMessage) == runtime.rows(AgentRun) == runtime.rows(HandoffTicket) == []
    )
    assert runtime.snapshot()["failed_requests"] == 1


async def test_stale_version_cannot_overwrite_state(runtime_factory):
    runtime = runtime_factory()
    original = runtime.session("state")
    changed = replace(original, focused_product_ids=("headset-pro",))
    current = await runtime.service.store.save_state(changed)
    with pytest.raises(AppError) as error:
        await runtime.service.store.save_state(
            replace(original, focused_product_ids=("lamp-mini",))
        )
    assert error.value.code == "CONVERSATION_BUSY"
    assert runtime.session("state").version == current.version
    assert runtime.session("state").focused_product_ids == ("headset-pro",)


async def test_two_instances_reject_stale_writes_without_losing_successful_messages(
    runtime_factory,
):
    arrivals = 0
    ready = asyncio.Event()

    class BarrierProvider(ScriptedProvider):
        async def complete(self, *args, **kwargs):
            nonlocal arrivals
            arrivals += 1
            if arrivals == 2:
                ready.set()
            await ready.wait()
            return await super().complete(*args, **kwargs)

    first = runtime_factory(BarrierProvider([Decision(reply="One")]))
    first.session("shared")
    second = runtime_factory(
        BarrierProvider([Decision(reply="Two")]), database_url=first.database.url
    )
    results = await asyncio.gather(
        send(first, "One", "shared"), send(second, "Two", "shared"), return_exceptions=True
    )
    assert sum(isinstance(result, WorkflowResult) for result in results) == 1
    errors = [result for result in results if isinstance(result, AppError)]
    assert len(errors) == 1 and errors[0].code == "CONVERSATION_BUSY"
    turns = first.session("shared").turns
    assert [turn.seq for turn in turns] == [1, 2]
    assert len(first.rows(AgentRun)) == 1
    assert first.snapshot() == second.snapshot()


async def test_database_rejects_message_updates(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Original reply")]))
    result = await send(runtime, "Original inquiry")
    with pytest.raises(IntegrityError, match="append-only"):
        async with runtime.database.transaction() as transaction:
            await transaction.execute(
                text("UPDATE messages SET content='changed' WHERE id=:id"),
                {"id": result.message_id},
            )
    assert runtime.session("state").turns[0].content == "Original inquiry"


async def test_regular_and_paused_client_ids_replay_saved_results(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Once")], delay=0.01))
    first, repeated = await asyncio.gather(
        send(runtime, "Hello", client_message_id="one"),
        send(runtime, "Hello", client_message_id="one"),
    )
    assert first.reply == repeated.reply and first.message_id == repeated.message_id
    assert first.run_id == repeated.run_id and repeated.replayed
    assert len(runtime.provider.calls) == 1 and len(runtime.session("state").turns) == 2
    await send(runtime, "/handoff")
    assert await runtime.handoffs.acknowledge(runtime.pending()[0]["id"])
    paused = await send(runtime, "Waiting", client_message_id="paused")
    replay = await send(runtime, "Waiting", client_message_id="paused")
    assert paused.message_id == replay.message_id and replay.replayed
    assert len(runtime.session("state").turns) == 3
    assert runtime.snapshot()["total_conversations"] == 2


def test_recent_contract_really_contains_conversation_id(api_client):
    client, runtime = api_client
    runtime.provider.decisions.append(Decision(reply="Hello"))
    first = client.post("/api/v1/agent/chat", json={"message": "Hello"}).json()["data"]
    recent = client.get("/api/v1/dashboard/recent").json()["data"][0]
    assert recent["conversation_id"] == recent["session_id"] == first["session_id"]
    assert recent["id"] == first["run_id"]
