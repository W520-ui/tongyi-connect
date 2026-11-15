import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from app.agent.effects import Effect
from app.agent.events import (
    AgentEvent,
    RunCompleted,
    RunFailed,
    TextDelta,
    ToolFinished,
    ToolStarted,
)
from app.agent.llm.base import LLMClient, ModelResponse, Usage
from app.agent.registry import ToolRegistry
from app.agent.tools.base import ToolOutput
from app.agent.tools.deps import ToolDeps
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.types import Message, RunTrace, ToolCall, ToolTraceEntry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunContext:
    messages: tuple[Message, ...]
    deps: ToolDeps
    streaming: bool = False


def trace_args(arguments: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


@dataclass
class RunProgress:
    rounds: int = 0
    entries: list[ToolTraceEntry] = field(default_factory=list)
    usage: Usage | None = None
    truncated: bool = False


class AgentRunner:
    def __init__(self, settings: Settings, client: LLMClient, registry: ToolRegistry) -> None:
        self.settings = settings
        self.client = client
        self.registry = registry

    async def _stream_round(
        self, messages, tools, tool_choice, round_number, events
    ) -> ModelResponse:
        text: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        finish_reason = None
        usage = None
        async for chunk in self.client.stream(messages, tools=tools, tool_choice=tool_choice):
            if chunk.content:
                text.append(chunk.content)
                await events.put(TextDelta(round_number, chunk.content))
            for delta in chunk.tool_calls:
                index = delta.get("index")
                if not isinstance(index, int) or index < 0:
                    raise AppError("LLM_BAD_RESPONSE")
                call = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if delta.get("id"):
                    call["id"] += delta["id"]
                function = delta.get("function") or {}
                call["name"] += function.get("name") or ""
                call["arguments"] += function.get("arguments") or ""
            finish_reason = chunk.finish_reason or finish_reason
            usage = chunk.usage or usage
        return ModelResponse(
            "".join(text) or None,
            tuple(
                ToolCall(value["id"] or f"call_{index}", value["name"], value["arguments"] or "{}")
                for index, value in sorted(calls.items())
            ),
            finish_reason,
            usage,
        )

    async def _invoke(self, call, round_number, deps, events) -> tuple[ToolTraceEntry, ToolOutput]:
        started = perf_counter()
        result = await self.registry.invoke(call.name, call.arguments, deps)
        error = None
        if not result.ok:
            try:
                error = json.loads(result.content)["error"]["message"]
            except (ValueError, KeyError, TypeError):
                error = "Tool execution failed"
        latency = (perf_counter() - started) * 1000
        entry = ToolTraceEntry(
            call.id, round_number, call.name, trace_args(call.arguments), result.ok, latency, error
        )
        await events.put(ToolFinished(call.id, round_number, call.name, result.ok, latency, error))
        return entry, result

    async def _round_response(
        self, messages, tools, choice, index
    ) -> AsyncIterator[AgentEvent | ModelResponse]:
        events = asyncio.Queue()
        task = asyncio.create_task(self._stream_round(messages, tools, choice, index, events))
        try:
            while not task.done() or not events.empty():
                waiter = asyncio.create_task(events.get())
                try:
                    done, _ = await asyncio.wait(
                        (task, waiter), return_when=asyncio.FIRST_COMPLETED
                    )
                    if waiter in done:
                        yield waiter.result()
                    else:
                        waiter.cancel()
                        await asyncio.gather(waiter, return_exceptions=True)
                finally:
                    if not waiter.done():
                        waiter.cancel()
                        await asyncio.gather(waiter, return_exceptions=True)
            yield await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def run(self, ctx: RunContext) -> AsyncIterator[AgentEvent]:
        progress = RunProgress()

        def failed(error):
            return RunFailed(
                error.code,
                error.message,
                RunTrace(tuple(progress.entries), progress.truncated),
                progress.usage,
                progress.rounds,
            )

        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                async for event in self._run(ctx, progress):
                    yield event
        except TimeoutError:
            error = AppError("AGENT_RUN_TIMEOUT")
            yield failed(error)
        except AppError as error:
            yield failed(error)
        except Exception:
            logger.exception("Agent run failed")
            error = AppError("INTERNAL_ERROR")
            yield failed(error)

    async def _run(self, ctx: RunContext, progress: RunProgress) -> AsyncIterator[AgentEvent]:
        if not self.client.is_configured:
            raise AppError("LLM_NOT_CONFIGURED")
        messages = list(ctx.messages)
        initial_count = len(messages)
        effects: list[Effect] = []
        entries = progress.entries
        prompt_tokens = completion_tokens = 0
        has_usage = truncated = False
        tools = self.registry.schemas()

        for round_number in range(self.settings.max_tool_rounds):
            progress.rounds = round_number + 1
            final_round = round_number == self.settings.max_tool_rounds - 1
            choice = "none" if final_round else "auto"
            if ctx.streaming:
                response = None
                async for event in self._round_response(messages, tools, choice, round_number):
                    if isinstance(event, ModelResponse):
                        response = event
                    else:
                        yield event
                if response is None:
                    raise AppError("LLM_BAD_RESPONSE")
            else:
                response = await self.client.complete(messages, tools=tools, tool_choice=choice)
            if response.usage:
                has_usage = True
                prompt_tokens += response.usage.prompt_tokens
                completion_tokens += response.usage.completion_tokens
                progress.usage = Usage(prompt_tokens, completion_tokens)
            if response.finish_reason == "length":
                truncated = True
                progress.truncated = True
                logger.warning("LLM response truncated in round=%s", round_number)
            if not response.tool_calls:
                if not response.content or not response.content.strip():
                    raise AppError("LLM_BAD_RESPONSE")
                reply = response.content.strip()
                if not ctx.streaming:
                    yield TextDelta(round_number, reply)
                messages.append(Message(role="assistant", content=reply))
                yield RunCompleted(
                    reply,
                    tuple(effects),
                    RunTrace(tuple(entries), truncated),
                    Usage(prompt_tokens, completion_tokens) if has_usage else None,
                    tuple(messages[initial_count:]),
                    round_number + 1,
                )
                return
            if final_round:
                raise AppError("LLM_BAD_RESPONSE")
            assistant_calls = tuple(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments
                        if isinstance(call.arguments, str)
                        else json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in response.tool_calls
            )
            messages.append(
                Message(
                    role="assistant", content=response.content or "", tool_calls=assistant_calls
                )
            )
            if response.content and not ctx.streaming:
                yield TextDelta(round_number, response.content)
            for call in response.tool_calls:
                yield ToolStarted(call.id, round_number, call.name, trace_args(call.arguments))
            events = asyncio.Queue()

            async def execute_all(calls=response.tool_calls, index=round_number):
                return await asyncio.gather(
                    *(self._invoke(call, index, ctx.deps, events) for call in calls)
                )

            task = asyncio.create_task(execute_all())
            try:
                for _ in response.tool_calls:
                    yield await events.get()
                results = await task
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            for call, (entry, result) in zip(response.tool_calls, results, strict=True):
                entries.append(entry)
                effects.extend(result.effects)
                messages.append(
                    Message(
                        role="tool", content=result.content, tool_call_id=call.id, name=call.name
                    )
                )
        raise AppError("LLM_BAD_RESPONSE")
