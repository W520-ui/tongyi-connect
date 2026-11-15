import asyncio
import json

import pytest
from pydantic import BaseModel, ValidationError

from app.agent.events import RunCompleted, RunFailed, TextDelta, ToolFinished, ToolStarted
from app.agent.llm.base import StreamChunk, Usage
from app.agent.runtime import RunContext
from app.agent.tools.base import FunctionTool
from app.agent.tools.catalog import QueryArgs
from app.agent.tools.outputs import output
from app.core.config import Settings
from app.domain.types import InboundMessage, Message, ToolCall
from tests.support import Decision, ScriptedProvider


async def run_events(runtime, *, streaming=False):
    return [
        event
        async for event in runtime.service.runner.run(
            RunContext(
                (Message(role="user", content="Please help."),),
                runtime.service.tool_deps,
                streaming,
            ),
        )
    ]


@pytest.mark.parametrize(
    "name,args,code",
    [
        ("missing_tool", {}, "UNKNOWN_TOOL"),
        ("catalog_quote", "{broken", "TOOL_VALIDATION_ERROR"),
        ("catalog_quote", {"product_id": 12}, "TOOL_VALIDATION_ERROR"),
        ("catalog_quote", [], "TOOL_VALIDATION_ERROR"),
        (
            "catalog_shipping",
            {"product_id": "headset-pro", "destination": "Mars"},
            "TOOL_VALIDATION_ERROR",
        ),
    ],
)
async def test_bad_tool_calls_reach_model_as_errors_and_run_continues(
    runtime_factory, name, args, code
):
    provider = ScriptedProvider(
        [Decision(tool_calls=(ToolCall("bad", name, args),)), Decision(reply="Please clarify.")]
    )
    runtime = runtime_factory(provider)
    events = await run_events(runtime)
    completed = events[-1]
    assert isinstance(completed, RunCompleted)
    assert completed.reply == "Please clarify."
    assert completed.trace.calls[0].ok is False
    tool_message = next(
        message for message in provider.calls[1]["messages"] if message.role == "tool"
    )
    error = json.loads(tool_message.content)
    assert error["ok"] is False
    assert error["error"]["code"] == code and error["error"]["message"]
    assert tool_message.tool_call_id == "bad"


async def test_tool_timeout_is_recoverable(runtime_factory):
    async def slow(_args, _deps):
        await asyncio.sleep(1)
        return output({"done": True})

    runtime = runtime_factory(
        ScriptedProvider(
            [
                Decision(tool_calls=(ToolCall("slow", "slow", {"query": "x"}),)),
                Decision(reply="Please try again."),
            ]
        )
    )
    runtime.service.runner.registry.register(
        FunctionTool("slow", "Slow tool", QueryArgs, slow, 0.01)
    )
    events = await run_events(runtime)
    assert isinstance(events[-1], RunCompleted)
    assert events[-1].trace.calls[0].ok is False
    result = json.loads(
        next(
            message.content
            for message in runtime.provider.calls[1]["messages"]
            if message.role == "tool"
        )
    )
    assert result["error"]["code"] == "TOOL_TIMEOUT"


async def test_tool_exception_is_logged_and_internal_details_are_hidden(runtime_factory, caplog):
    async def broken(_args, _deps):
        raise RuntimeError("INTERNAL-STACK-MARKER")

    runtime = runtime_factory(
        ScriptedProvider(
            [
                Decision(tool_calls=(ToolCall("broken", "broken", {"query": "x"}),)),
                Decision(reply="Try again."),
            ]
        )
    )
    runtime.service.runner.registry.register(
        FunctionTool("broken", "Broken tool", QueryArgs, broken)
    )
    events = await run_events(runtime)
    assert isinstance(events[-1], RunCompleted)
    tool_message = next(
        message for message in runtime.provider.calls[1]["messages"] if message.role == "tool"
    )
    assert "INTERNAL-STACK-MARKER" not in tool_message.content
    assert json.loads(tool_message.content)["error"]["code"] == "TOOL_EXECUTION_ERROR"
    assert any(
        record.exc_info and "Tool execution failed" in record.message for record in caplog.records
    )


async def test_tools_execute_concurrently_and_finish_events_follow_actual_order(runtime_factory):
    second_finished = asyncio.Event()

    async def first(_args, _deps):
        await asyncio.wait_for(second_finished.wait(), 0.5)
        return output({"tool": "first"})

    async def second(_args, _deps):
        second_finished.set()
        return output({"tool": "second"})

    runtime = runtime_factory(
        ScriptedProvider(
            [
                Decision(
                    tool_calls=(
                        ToolCall("1", "first", {"query": "x"}),
                        ToolCall("2", "second", {"query": "x"}),
                    )
                ),
                Decision(reply="Done."),
            ]
        )
    )
    registry = runtime.service.runner.registry
    registry.register(FunctionTool("first", "First tool", QueryArgs, first))
    registry.register(FunctionTool("second", "Second tool", QueryArgs, second))
    events = await run_events(runtime)
    assert [event.call_id for event in events if isinstance(event, ToolStarted)] == ["1", "2"]
    assert [event.call_id for event in events if isinstance(event, ToolFinished)] == ["2", "1"]
    assert all(entry.ok for entry in events[-1].trace.calls)
    assert [
        message.tool_call_id
        for message in runtime.provider.calls[1]["messages"]
        if message.role == "tool"
    ] == ["1", "2"]


async def test_total_run_timeout_cancels_active_tool_and_returns_code(runtime_factory):
    cancelled = asyncio.Event()

    async def never(_args, _deps):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    runtime = runtime_factory(
        ScriptedProvider([Decision(tool_calls=(ToolCall("never", "never", {"query": "x"}),))]),
        run_timeout_seconds=0.03,
    )
    runtime.service.runner.registry.register(
        FunctionTool("never", "Never-ending tool", QueryArgs, never, 2)
    )
    events = await run_events(runtime)
    assert isinstance(events[-1], RunFailed)
    assert events[-1].error_code == "AGENT_RUN_TIMEOUT"
    assert cancelled.is_set()
    assert not any(isinstance(event, RunCompleted) for event in events)


def test_api_total_timeout_counts_failure_without_saving_incomplete_history(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider([Decision(reply="Late reply")], delay=0.1), run_timeout_seconds=0.01
    )
    response = runtime.client.post(
        "/api/v1/agent/chat", json={"message": "hello", "session_id": "timeout"}
    )
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "AGENT_RUN_TIMEOUT"
    assert runtime.snapshot()["failed_requests"] == 1
    assert runtime.snapshot()["total_conversations"] == 1
    assert [(turn.role, turn.content) for turn in runtime.session("timeout").turns] == [
        ("user", "hello")
    ]
    assert runtime.recent() == []


async def test_gateway_ignoring_final_tool_choice_fails_without_another_tool_round(runtime_factory):
    provider = ScriptedProvider(
        [
            Decision(tool_calls=(ToolCall("1", "catalog_search", {"query": "headphones"}),)),
            Decision(tool_calls=(ToolCall("2", "catalog_search", {"query": "lamp"}),)),
        ]
    )
    runtime = runtime_factory(provider, max_tool_rounds=2)
    events = await run_events(runtime)
    assert isinstance(events[-1], RunFailed)
    assert events[-1].error_code == "LLM_BAD_RESPONSE"
    assert len([event for event in events if isinstance(event, ToolStarted)]) == 1
    assert provider.calls[-1]["tool_choice"] == "none"
    assert provider.calls[-1]["tools"]


async def test_truncation_and_token_usage_are_recorded(runtime_factory, caplog):
    provider = ScriptedProvider(
        [
            Decision(
                tool_calls=(ToolCall("1", "catalog_search", {"query": "headphones"}),),
                usage=Usage(10, 3),
            ),
            Decision(reply="A truncated answer", finish_reason="length", usage=Usage(15, 4)),
        ]
    )
    runtime = runtime_factory(provider)
    events = await run_events(runtime)
    assert events[-1].trace.truncated is True
    assert events[-1].usage == Usage(25, 7)
    assert "truncated" in caplog.text
    provider.decisions.append(Decision(reply="Another truncated reply", finish_reason="length"))
    await runtime.service.handle_inbound(InboundMessage("Hello.", "truncated"))
    assert json.loads(runtime.recent()[0]["tool_trace"])["truncated"] is True


async def test_streaming_accumulates_tool_fragments_by_index_before_execution(runtime_factory):
    provider = ScriptedProvider(
        streams=[
            [
                StreamChunk(content="Let me check."),
                StreamChunk(
                    tool_calls=(
                        {
                            "index": 1,
                            "id": "ship",
                            "function": {
                                "name": "catalog_ship",
                                "arguments": '{"product_id":"headset-pro",',
                            },
                        },
                        {
                            "index": 0,
                            "id": "quote",
                            "function": {"name": "catalog_", "arguments": '{"product_'},
                        },
                    )
                ),
                StreamChunk(
                    tool_calls=(
                        {
                            "index": 0,
                            "function": {"name": "quote", "arguments": 'id":"headset-pro"}'},
                        },
                        {
                            "index": 1,
                            "function": {"name": "ping", "arguments": '"destination":"ES"}'},
                        },
                    ),
                    finish_reason="tool_calls",
                    usage=Usage(12, 3),
                ),
            ],
            [
                StreamChunk(content="Final "),
                StreamChunk(content="answer.", finish_reason="stop", usage=Usage(8, 2)),
            ],
        ]
    )
    runtime = runtime_factory(provider, max_tool_rounds=2)
    events = await run_events(runtime, streaming=True)
    started = [event for event in events if isinstance(event, ToolStarted)]
    assert [event.name for event in started] == ["catalog_quote", "catalog_shipping"]
    assert started[0].args == {"product_id": "headset-pro"}
    assert started[1].args["destination"] == "ES"
    assert isinstance(events[0], TextDelta)
    assert events[-1].reply == "Final answer."
    assert events[-1].usage == Usage(20, 5)
    assert all(entry.ok for entry in events[-1].trace.calls)
    assert provider.calls[-1]["tool_choice"] == "none"
    assert (
        len([message for message in provider.calls[-1]["messages"] if message.role == "tool"]) == 2
    )


def test_tool_schema_generated_from_pydantic_and_names_are_valid(runtime_factory):
    runtime = runtime_factory()
    schemas = runtime.service.runner.registry.schemas()
    shipping = next(
        schema["function"]["parameters"]
        for schema in schemas
        if schema["function"]["name"] == "catalog_shipping"
    )
    assert "destination" in shipping["required"]
    assert shipping["properties"]["destination"]["pattern"] == "^[A-Z]{2}$"
    assert shipping["additionalProperties"] is False
    with pytest.raises(ValueError, match="underscores"):
        runtime.service.runner.registry.register(FunctionTool("bad.name", "", BaseModel, None))


def test_total_timeout_must_be_less_than_frontend_timeout():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, run_timeout_seconds=70)
