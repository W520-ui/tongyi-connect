from tests import isolation  # noqa: F401 -- isolate database before importing the app

# isort: split

import tempfile
import unittest
from pathlib import Path

from app.services.workflow import WorkflowMetrics, analyze_message, build_workflow_answer

MODEL_REPLY = "The Nebula ANC Headphones Pro ships to Spain in 5-8 business days."


class WorkflowAnalysisTests(unittest.TestCase):
    def test_detects_multiple_intents_and_uses_catalog(self):
        message = "Please quote the headphones and tell me the shipping time to Spain."
        analysis = analyze_message(message)
        result = build_workflow_answer(message, analysis, reply=MODEL_REPLY)

        self.assertEqual(analysis.language, "en-US")
        self.assertEqual(set(result["detected_intents"]), {"quote", "logistics"})
        self.assertEqual(result["matched_product"], "星云降噪耳机 Pro")
        self.assertEqual(result["reply"], MODEL_REPLY)
        self.assertEqual(result["source"], "native")
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
            message, analysis, reply=MODEL_REPLY, source="native+human-handoff"
        )
        self.assertTrue(result["needs_human"])
        self.assertEqual(result["source"], "native+human-handoff")
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


if __name__ == "__main__":
    unittest.main()
