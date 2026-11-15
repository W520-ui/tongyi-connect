import pytest

from app.agent.llm.base import Usage
from app.core.errors import AppError
from app.domain.types import InboundMessage, ToolCall
from app.repositories.models import AgentRun
from tests.support import Decision, ScriptedProvider


async def test_failed_run_preserves_observed_usage_rounds_trace_and_truncation(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider(
            [
                Decision(
                    tool_calls=(ToolCall("quote", "catalog_quote", {"product_id": "headset-pro"}),),
                    finish_reason="length",
                    usage=Usage(9, 3),
                ),
                AppError("LLM_TIMEOUT"),
            ]
        )
    )
    with pytest.raises(AppError) as error:
        await runtime.service.handle_inbound(InboundMessage("Hello", "failed"))
    assert error.value.code == "LLM_TIMEOUT"
    run = runtime.rows(AgentRun)[0]
    assert run.status == "error" and run.error_code == "LLM_TIMEOUT"
    assert run.rounds == 2 and (run.prompt_tokens, run.completion_tokens) == (9, 3)
    assert run.tool_trace["truncated"] is True and run.tool_trace["calls"][0]["ok"] is True
    assert run.tool_trace["calls"][0]["name"] == "catalog_quote"
    assert runtime.session("failed").focused_product_ids == ()
    assert [(turn.role, turn.content) for turn in runtime.session("failed").turns] == [
        ("user", "Hello")
    ]
