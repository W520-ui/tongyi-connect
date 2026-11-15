from app.agent.guardrails import analyze_message
from app.api.v1.presenters import present_workflow
from app.domain.types import InboundMessage
from app.repositories.archive import WorkflowArchive
from app.services.analytics import AnalyticsService
from tests.support import Decision, ScriptedProvider

MODEL_REPLY = "The Nebula ANC Headphones Pro ships to Spain in 5-8 business days."


async def test_detects_multiple_intents_and_uses_catalog(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply=MODEL_REPLY)]))
    message = "Please quote the headphones and tell me the shipping time to Spain."
    analysis = analyze_message(message, runtime.service.catalog.products)
    result = present_workflow(
        await runtime.service.handle_inbound(InboundMessage(message))
    ).model_dump()
    assert analysis.language == "en-US"
    assert set(result["detected_intents"]) == {"quote", "logistics"}
    assert result["matched_product"] == "星云降噪耳机 Pro"
    assert result["reply"] == MODEL_REPLY
    assert result["source"] == "native"
    assert "aliases" not in result["matched_products"][0]
    assert "fallback_notice" not in result


def test_chinese_destination_does_not_change_reply_language():
    assert analyze_message("耳机可以发往西班牙吗？").language == "zh-CN"


async def test_follow_up_message_reuses_last_matched_product(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply=MODEL_REPLY)]))
    session = runtime.service.store.load("followup")
    session.focused_product_ids = ("headset-pro",)
    runtime.service.store.save(session)
    data = present_workflow(
        await runtime.service.handle_inbound(
            InboundMessage("And how long is the delivery time?", "followup")
        )
    )
    assert data.matched_product == "星云降噪耳机 Pro"
    assert data.product_id == "headset-pro"
    assert data.product_confidence == 0.72


async def test_after_sales_requests_human_handoff(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply=MODEL_REPLY)]))
    data = present_workflow(
        await runtime.service.handle_inbound(
            InboundMessage("The headset arrived damaged. I want a refund.")
        )
    )
    assert data.needs_human
    assert data.source == "native+human-handoff"
    assert "人工接管" in data.steps[-1]


async def test_archive_and_aggregate_survive_restart(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="已记录售后诉求，等待商家接管。")]))
    message = "耳机坏了，申请退款。"
    await runtime.service.handle_inbound(InboundMessage(message, "test-session"))
    assert runtime.metrics.snapshot()["total_conversations"] == 1
    assert runtime.archive.recent()[0]["intent_label"] == "售后服务"
    handoff_id = runtime.handoffs.pending()[0]["id"]
    runtime.metrics.record_failed_request("LLM_TIMEOUT")
    restarted_archive = WorkflowArchive(runtime.archive.db_path)
    restarted = AnalyticsService(restarted_archive)
    try:
        snapshot = restarted.snapshot()
        assert (
            snapshot["total_conversations"]
            == snapshot["human_handoffs"]
            == snapshot["pending_handoffs"]
            == 1
        )
        assert snapshot["failed_requests"] == 1
        assert restarted_archive.recent()[0]["message"] == message
        assert restarted_archive.acknowledge(handoff_id)
        assert not restarted_archive.acknowledge(handoff_id)
        assert restarted.snapshot()["pending_handoffs"] == 0
        assert restarted_archive.recent()[0]["human_acknowledged"] == 1
    finally:
        restarted_archive.close()
