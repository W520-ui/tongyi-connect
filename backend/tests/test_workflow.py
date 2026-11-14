import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.clients.astrbot import AstrBotError, _parse_sse_response
from app.schemas.agent import AgentChatRequest
from app.services.agent import AgentService
from app.services.workflow import WorkflowMetrics, analyze_message, build_workflow_answer


MODEL_REPLY = "The Nebula ANC Headphones Pro ships to Spain in 5-8 business days."


def run_chat(client, message="Please quote the Nebula headphones"):
    """Run AgentService against a throwaway metrics database."""

    with tempfile.TemporaryDirectory() as temp_dir:
        isolated_metrics = WorkflowMetrics(Path(temp_dir) / "agent-test.db")
        try:
            with patch("app.services.agent.metrics", isolated_metrics):
                result = asyncio.run(
                    AgentService(client).chat(AgentChatRequest(message=message))
                )
            return result, isolated_metrics.snapshot()
        finally:
            isolated_metrics.close()


class WorkflowAnalysisTests(unittest.TestCase):
    def test_detects_multiple_intents_and_uses_catalog(self):
        message = "Please quote the headphones and tell me the shipping time to Spain."
        analysis = analyze_message(message)
        result = build_workflow_answer(message, analysis, reply=MODEL_REPLY)

        self.assertEqual(analysis.language, "en-US")
        self.assertEqual(set(result["detected_intents"]), {"quote", "logistics"})
        self.assertEqual(result["matched_product"], "星云降噪耳机 Pro")
        self.assertEqual(result["reply"], MODEL_REPLY)
        self.assertEqual(result["source"], "astrbot")
        self.assertNotIn("aliases", result["matched_products"][0])
        self.assertNotIn("fallback_notice", result)

    def test_chinese_destination_does_not_change_reply_language(self):
        analysis = analyze_message("耳机可以发往西班牙吗？")
        self.assertEqual(analysis.language, "zh-CN")

    def test_follow_up_message_reuses_last_matched_product(self):
        message = "And how long is the delivery time?"
        analysis = analyze_message(message, product_hint="headset-pro")
        result = build_workflow_answer(message, analysis, reply=MODEL_REPLY)
        self.assertEqual(result["matched_product"], "星云降噪耳机 Pro")
        self.assertEqual(result["product_id"], "headset-pro")
        self.assertEqual(result["product_confidence"], 0.72)

    def test_after_sales_requests_human_handoff(self):
        message = "The headset arrived damaged. I want a refund."
        analysis = analyze_message(message)
        result = build_workflow_answer(
            message, analysis, reply=MODEL_REPLY, source="astrbot+human-handoff"
        )
        self.assertTrue(result["needs_human"])
        self.assertEqual(result["source"], "astrbot+human-handoff")
        self.assertIn("人工接管", result["steps"][-1])


class WorkflowArchiveTests(unittest.TestCase):
    def test_archive_and_aggregate_survive_restart(self):
        message = "耳机坏了，申请退款。"
        analysis = analyze_message(message)
        result = build_workflow_answer(message, analysis, reply="已记录售后诉求，等待商家接管。")

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "workflow.db"
            first_run = WorkflowMetrics(db_path)
            first_run.archive(session_id="test-session", message=message, answer=result)
            self.assertEqual(first_run.snapshot()["total_conversations"], 1)
            self.assertEqual(first_run.recent()[0]["intent_label"], "售后服务")
            handoff_id = first_run.recent()[0]["id"]

            after_restart = WorkflowMetrics(db_path)
            snapshot = after_restart.snapshot()
            self.assertEqual(snapshot["total_conversations"], 1)
            self.assertEqual(snapshot["human_handoffs"], 1)
            self.assertEqual(after_restart.recent()[0]["message"], message)
            self.assertEqual(snapshot["pending_handoffs"], 1)
            self.assertTrue(after_restart.acknowledge_handoff(handoff_id))
            self.assertFalse(after_restart.acknowledge_handoff(handoff_id))
            self.assertEqual(after_restart.snapshot()["pending_handoffs"], 0)
            self.assertTrue(after_restart.recent()[0]["human_acknowledged"])
            first_run.close()
            after_restart.close()


class AstrBotIntegrationTests(unittest.TestCase):
    def test_sse_plain_and_complete_events_are_aggregated_once(self):
        body = (
            'data: {"type":"plain","data":"hello ","streaming":true}\n\n'
            'data: {"type":"plain","data":"world","streaming":true}\n\n'
            'data: {"type":"complete","data":"hello world","streaming":true}\n\n'
        )
        self.assertEqual(_parse_sse_response(body)["data"], "hello world")

    def test_model_reply_is_used_and_archived(self):
        class ConfiguredAstrBot:
            is_configured = True

            async def send_chat(self, _payload):
                return {"status": "ok", "data": MODEL_REPLY, "message": None}

        result, snapshot = run_chat(ConfiguredAstrBot())
        self.assertEqual(result["data"]["reply"], MODEL_REPLY)
        self.assertEqual(result["data"]["source"], "astrbot")
        self.assertEqual(snapshot["total_conversations"], 1)

    def test_missing_api_key_raises_error(self):
        class UnconfiguredAstrBot:
            is_configured = False

            async def send_chat(self, _payload):
                raise AssertionError("send_chat must not be called without a key")

        with self.assertRaises(AstrBotError) as context:
            run_chat(UnconfiguredAstrBot())
        self.assertIn("API Key", str(context.exception))

    def test_provider_unavailable_raises_error(self):
        class NoProviderAstrBot:
            is_configured = True

            async def send_chat(self, _payload):
                return {
                    "status": "ok",
                    "data": "未找到任何可用的对话模型，请先配置模型提供商",
                    "message": None,
                }

        with self.assertRaises(AstrBotError) as context:
            run_chat(NoProviderAstrBot())
        self.assertIn("对话模型", str(context.exception))

    def test_transport_error_is_not_masked(self):
        class BrokenAstrBot:
            is_configured = True

            async def send_chat(self, _payload):
                raise AstrBotError("无法连接 AstrBot 服务")

        with self.assertRaises(AstrBotError) as context:
            run_chat(BrokenAstrBot())
        self.assertIn("无法连接", str(context.exception))

    def test_error_envelope_raises_error(self):
        class ErrorAstrBot:
            is_configured = True

            async def send_chat(self, _payload):
                return {"status": "error", "data": None, "message": "模型调用失败"}

        with self.assertRaises(AstrBotError) as context:
            run_chat(ErrorAstrBot())
        self.assertIn("模型调用失败", str(context.exception))


if __name__ == "__main__":
    unittest.main()
