"""SSE subscribes to an independently owned service task."""

import asyncio
import logging
from dataclasses import asdict

from app.api.v1.presenters import present_public_workflow
from app.api.v1.schemas.stream import (
    AnalysisUpdate,
    CompletedData,
    DeltaData,
    StreamErrorData,
    ToolFinishedData,
    ToolStartedData,
)
from app.core.errors import AppError
from app.domain.types import INTENT_LABELS, LANGUAGE_LABELS
from app.services.events import (
    AnalysisCompleted,
    TextDelta,
    ToolFinished,
    ToolStarted,
    WorkflowCompleted,
)

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 15


def encode_event(event):
    if isinstance(event, (ToolStarted, ToolFinished, TextDelta)):
        name, schema = {
            ToolStarted: ("tool_started", ToolStartedData),
            ToolFinished: ("tool_finished", ToolFinishedData),
            TextDelta: ("delta", DeltaData),
        }[type(event)]
        payload = schema(**asdict(event))
    elif isinstance(event, WorkflowCompleted):
        name, payload = "completed", CompletedData(data=present_public_workflow(event.result))
    elif isinstance(event, AnalysisCompleted):
        name, outcome = "analysis", event.outcome
        workflow = present_public_workflow(event.result)
        payload = AnalysisUpdate(
            analysis_source=event.result.analysis_source,
            intent=outcome["intents"][0],
            intent_label=INTENT_LABELS[outcome["intents"][0]],
            detected_intents=outcome["intents"],
            detected_intent_labels=[INTENT_LABELS[item] for item in outcome["intents"]],
            language=outcome["language"],
            language_label=LANGUAGE_LABELS[outcome["language"]],
            task_plan=workflow.task_plan,
            merchant_summary=outcome["merchant_summary_zh"],
            product_ids=outcome["product_ids"],
            needs_human=outcome["needs_human"],
            confidence=outcome["confidence"],
        )
    elif isinstance(event, AppError):
        name, payload = "error", StreamErrorData(code=event.code, message=event.message)
    else:
        raise TypeError("Unsupported stream event")
    return f"event: {name}\ndata: {payload.model_dump_json()}\n\n"


async def subscribe(service, inbound):
    queue = asyncio.Queue()
    ready = asyncio.get_running_loop().create_future()
    subscribed = True

    async def emit(event):
        if subscribed:
            queue.put_nowait(encode_event(event))

    async def produce():
        try:
            await service.handle_inbound(inbound, emit=emit, ready=lambda: ready.set_result(None))
        except Exception as error:
            if not isinstance(error, AppError):
                logger.exception("Unexpected stream failure")
                error = AppError("INTERNAL_ERROR")
            if not ready.done():
                ready.set_exception(error)
            else:
                await emit(error)
        finally:
            queue.put_nowait(None)

    service.background.schedule(produce())
    try:
        await asyncio.shield(ready)
    except BaseException:
        subscribed = False
        # Consume errors if the HTTP request disconnects during preflight waiting.
        ready.add_done_callback(
            lambda future: future.exception() if not future.cancelled() else None
        )
        raise

    async def events():
        nonlocal subscribed
        try:
            while True:
                try:
                    async with asyncio.timeout(HEARTBEAT_SECONDS):
                        item = await queue.get()
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                if item is None:
                    break
                yield item
        finally:
            subscribed = False
            while not queue.empty():
                queue.get_nowait()

    return events()
