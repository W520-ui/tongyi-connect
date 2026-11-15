import json

import httpx
import pytest

from app.agent.analysis import PostAnalyzer, heuristic_outcome
from app.agent.guardrails import analyze_message
from app.agent.llm.base import Usage
from app.agent.llm.openai import OpenAICompatibleClient
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.types import InboundMessage, ToolCall
from app.repositories.models import AgentRun, HandoffTicket
from tests.support import Decision, ScriptedProvider


def outcome(**overrides):
    return {
        "intents": ["logistics"],
        "language": "es-ES",
        "product_ids": ["headset-pro"],
        "needs_human": False,
        "handoff_reason": None,
        "merchant_summary_zh": "客户咨询物流。中文译文：你好，耳机寄往墨西哥需要多长时间？",
        "confidence": 0.9,
        **overrides,
    }


async def test_post_analysis_persists_translation_schema_source_and_usage(runtime_factory):
    customer = "Hola, ¿cuánto tarda el envío de los auriculares a México?"
    provider = ScriptedProvider(
        [
            Decision(reply="El comerciante debe confirmar el envío.", usage=Usage(5, 2)),
            Decision(reply=json.dumps(outcome(), ensure_ascii=False), usage=Usage(7, 3)),
        ]
    )
    runtime = runtime_factory(provider, analysis_enabled=True)
    result = await runtime.service.handle_inbound(InboundMessage(customer, "analysis"))
    run = runtime.rows(AgentRun)[0]
    assert "你好，耳机寄往墨西哥需要多长时间？" in result.merchant_summary
    assert result.analysis_source == run.analysis_source == "llm"
    assert result.analysis.intent == "logistics" and result.analysis.language == "es-ES"
    assert run.outcome["merchant_summary_zh"] == result.merchant_summary
    assert run.prompt_tokens == 12 and run.completion_tokens == 5
    assert provider.calls[-1]["response_format"]["type"] == "json_schema"
    assert json.loads(provider.calls[-1]["messages"][-1].content)["customer_message"] == customer
    assert len(runtime.session("analysis").turns) == 2
    assert runtime.rows(HandoffTicket) == []


async def test_analysis_annotation_never_creates_handoff_or_changes_focus(runtime_factory):
    provider = ScriptedProvider(
        [
            Decision(reply="Hello"),
            Decision(
                reply=json.dumps(
                    outcome(
                        intents=["after_sales"],
                        needs_human=True,
                        handoff_reason="Analysis annotation",
                    ),
                    ensure_ascii=False,
                )
            ),
        ]
    )
    runtime = runtime_factory(provider, analysis_enabled=True)
    result = await runtime.service.handle_inbound(InboundMessage("Hello", "analysis"))
    assert result.analysis.intent == "after_sales" and result.analysis_source == "llm"
    assert not result.needs_human and result.handoff_reason is None
    assert runtime.rows(AgentRun)[0].outcome["needs_human"] is True
    assert runtime.rows(HandoffTicket) == []
    assert runtime.session("analysis").focused_product_ids == ()


async def test_analysis_cannot_cancel_actual_handoff(runtime_factory):
    provider = ScriptedProvider(
        [
            Decision(
                tool_calls=(ToolCall("after", "after_sales_record", {"issue": "ISSUE-MARKER"}),)
            ),
            Decision(reply="Recorded"),
            Decision(reply=json.dumps(outcome(needs_human=False), ensure_ascii=False)),
        ]
    )
    runtime = runtime_factory(provider, analysis_enabled=True)
    result = await runtime.service.handle_inbound(InboundMessage("Hello", "analysis"))
    assert result.needs_human and result.handoff_id
    assert runtime.rows(HandoffTicket)[0].issue_summary == "ISSUE-MARKER"
    assert runtime.rows(AgentRun)[0].outcome["needs_human"] is False


async def test_pending_queue_preserves_reply_and_translated_summary(runtime_factory):
    reply = "Hemos registrado el problema para que nuestro equipo lo revise."
    summary = "客户申请售后。中文译文：我收到的耳机屏幕碎了。"
    provider = ScriptedProvider(
        [
            Decision(
                tool_calls=(
                    ToolCall("after", "after_sales_record", {"issue": "Pantalla rota al llegar"}),
                )
            ),
            Decision(reply=reply),
            Decision(
                reply=json.dumps(
                    outcome(
                        intents=["after_sales"],
                        needs_human=True,
                        merchant_summary_zh=summary,
                    ),
                    ensure_ascii=False,
                )
            ),
        ]
    )
    runtime = runtime_factory(provider, analysis_enabled=True)
    result = await runtime.service.handle_inbound(
        InboundMessage("Los auriculares llegaron con la pantalla rota", "queue")
    )
    pending = runtime.pending()[0]
    assert pending["id"] == result.handoff_id
    assert pending["id"] != result.run_id
    assert pending["reply"] == reply
    assert pending["merchant_summary"] == summary == result.merchant_summary
    assert pending["intent_label"] == "售后服务"
    assert pending["language_label"] == "西班牙语"
    assert pending["issue_summary"] == "Pantalla rota al llegar"


@pytest.mark.parametrize(
    "response",
    [
        Decision(reply="{broken"),
        Decision(reply=json.dumps(outcome(language="fr-FR"))),
        Decision(reply=json.dumps(outcome(product_ids=["invented"]))),
        Decision(reply=json.dumps(outcome(needs_human="yes"))),
        Decision(reply=json.dumps(outcome(merchant_summary_zh="English only"))),
        AppError("LLM_TIMEOUT"),
    ],
)
async def test_analysis_failure_keeps_main_reply_and_marks_heuristic(runtime_factory, response):
    runtime = runtime_factory(
        ScriptedProvider([Decision(reply="Main answer"), response]), analysis_enabled=True
    )
    result = await runtime.service.handle_inbound(InboundMessage("Hello", "analysis"))
    assert result.reply == "Main answer" and result.analysis_source == "heuristic"
    assert runtime.rows(AgentRun)[0].analysis_source == "heuristic"
    assert runtime.snapshot()["failed_requests"] == 0
    assert runtime.rows(HandoffTicket) == []


async def test_response_format_rejection_falls_back_to_plain_json_prompt(settings_factory):
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(400, json={"error": {"message": "response_format unsupported"}})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": json.dumps(outcome(), ensure_ascii=False)},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    fallback = heuristic_outcome("Hello", analyze_message("Hello"), (), False, None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        analyzer = PostAnalyzer(OpenAICompatibleClient(settings_factory(), transport))
        result = await analyzer.analyze(
            "Hola", "Reply", fallback, ("headset-pro",), remaining_seconds=10
        )
    assert result.source == "llm" and len(requests) == 2
    assert requests[0]["response_format"]["type"] == "json_schema"
    assert "response_format" not in requests[1]
    assert "Chinese translation" in requests[1]["messages"][0]["content"]


async def test_disabled_analysis_never_calls_model(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Hello")]))
    result = await runtime.service.handle_inbound(InboundMessage("Hello", "disabled"))
    assert result.analysis_source == "heuristic" and len(runtime.provider.calls) == 1


def test_analysis_defaults_enabled_and_model_defaults_to_main(settings_factory):
    settings = Settings(_env_file=None)
    assert settings.analysis_enabled and settings.analysis_model is None
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings_factory(analysis_model="analysis-model"))) as client:
        state = client.app.state
        assert state.analyzer.client.settings.llm_model == "analysis-model"
        assert state.runner.client.settings.llm_model == "test-model"
        assert state.analyzer.client.http_client is state.runner.client.http_client


async def test_analysis_timeout_is_bounded_and_preserves_reply(runtime_factory):
    analysis_provider = ScriptedProvider([Decision(reply=json.dumps(outcome()))], delay=0.1)
    runtime = runtime_factory(
        ScriptedProvider([Decision(reply="Hello")]),
        analysis_provider=analysis_provider,
        analysis_enabled=True,
        analysis_timeout_seconds=0.01,
    )
    result = await runtime.service.handle_inbound(InboundMessage("Hello", "analysis"))
    assert result.reply == "Hello" and result.analysis_source == "heuristic"
    assert runtime.snapshot()["failed_requests"] == 0
