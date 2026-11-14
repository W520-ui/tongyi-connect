import asyncio
from datetime import datetime, timedelta, timezone
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent.commands import CommandRouter
from app.agent.config import AgentSettings
from app.agent.engine import AgentEngine
from app.agent.hooks import Hooks
from app.agent.models import (
    AgentContext,
    AgentError,
    Decision,
    Message,
    Session,
    ToolCall,
    Turn,
)
from app.agent.providers.openai import _parse_decision
from app.agent.registry import create_default_registry
from app.agent.session import SessionStore
from app.schemas.agent import AgentChatRequest
from app.services.workflow import WorkflowMetrics, analyze_message


class ScriptedProvider:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    @property
    def is_configured(self):
        return True

    async def decide(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        if not self.decisions:
            raise AssertionError("scripted decisions exhausted")
        return self.decisions.pop(0)


class UnconfiguredProvider:
    is_configured = False

    async def decide(self, messages, tools):
        raise AssertionError("model must not be called without a key")


def make_engine(provider, temp_dir):
    settings = AgentSettings(
        llm_api_key="test-key",
        llm_base_url="https://example.test/v1",
        llm_model="test-model",
        max_tool_rounds=4,
        session_ttl_hours=24,
        max_history_turns=10,
    )
    root = Path(temp_dir)
    store = SessionStore(root / "sessions.db")
    metrics = WorkflowMetrics(root / "workflow.db")
    engine = AgentEngine(
        settings=settings,
        provider=provider,
        registry=create_default_registry(),
        store=store,
        commands=CommandRouter(store),
        hooks=Hooks(),
    )
    return engine, metrics, store


def run_engine(engine, metrics, message, session_id="test-session"):
    with patch("app.agent.engine.metrics", metrics):
        return asyncio.run(
            engine.chat(
                AgentChatRequest(
                    message=message, session_id=session_id, username="tester"
                )
            )
        )


class AgentEngineTests(unittest.TestCase):
    def test_tool_calling_loop_returns_model_reply_and_archives(self):
        provider = ScriptedProvider(
            [
                Decision(
                    tool_calls=(
                        ToolCall(
                            id="c1",
                            name="catalog_search",
                            arguments={"query": "headphones"},
                        ),
                    )
                ),
                Decision(reply="The headphones cost USD 39.00."),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(provider, temp_dir)
            result = run_engine(engine, metrics, "Please quote the headphones", "s1")
            data = result["data"]
            self.assertEqual(result["status"], "ok")
            self.assertEqual(data["reply"], "The headphones cost USD 39.00.")
            self.assertEqual(data["source"], "native")
            self.assertEqual(data["matched_product"], "星云降噪耳机 Pro")
            self.assertEqual(len(provider.calls), 2)
            tool_names = [
                item["function"]["name"] for item in provider.calls[0]["tools"]
            ]
            self.assertIn("catalog_search", tool_names)
            self.assertTrue(
                any(message.role == "tool" for message in provider.calls[1]["messages"])
            )
            self.assertEqual(metrics.snapshot()["total_conversations"], 1)
            session = store.load("s1")
            self.assertEqual(len(session.turns), 2)
            self.assertEqual(session.last_product_id, "headset-pro")
            store.close()
            metrics.close()

    def test_after_sales_tool_triggers_human_handoff(self):
        provider = ScriptedProvider(
            [
                Decision(
                    tool_calls=(
                        ToolCall(
                            id="c1",
                            name="after_sales_record",
                            arguments={"issue": "arrived damaged"},
                        ),
                    )
                ),
                Decision(reply="I have recorded your request."),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(provider, temp_dir)
            result = run_engine(engine, metrics, "The headset arrived damaged.", "s2")
            self.assertTrue(result["data"]["needs_human"])
            self.assertEqual(result["data"]["source"], "native+human-handoff")
            self.assertEqual(metrics.snapshot()["human_handoffs"], 1)
            store.close()
            metrics.close()

    def test_follow_up_reuses_session_product(self):
        provider = ScriptedProvider(
            [Decision(reply="First reply."), Decision(reply="Second reply.")]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(provider, temp_dir)
            run_engine(engine, metrics, "Please quote the headphones", "s3")
            result = run_engine(
                engine, metrics, "And how long is the delivery time?", "s3"
            )
            self.assertEqual(result["data"]["matched_product"], "星云降噪耳机 Pro")
            self.assertEqual(result["data"]["product_confidence"], 0.72)
            store.close()
            metrics.close()

    def test_missing_api_key_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(UnconfiguredProvider(), temp_dir)
            with patch("app.agent.engine.metrics", metrics):
                with self.assertRaises(AgentError) as context:
                    asyncio.run(engine.chat(AgentChatRequest(message="hello")))
            self.assertIn("AGENT_LLM_API_KEY", str(context.exception))
            self.assertEqual(metrics.snapshot()["total_conversations"], 0)
            store.close()
            metrics.close()

    def test_tool_round_limit_raises(self):
        decisions = [
            Decision(
                tool_calls=(
                    ToolCall(
                        id=f"c{index}",
                        name="knowledge_search",
                        arguments={"query": "x"},
                    ),
                )
            )
            for index in range(4)
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(ScriptedProvider(decisions), temp_dir)
            with self.assertRaises(AgentError) as context:
                run_engine(engine, metrics, "hello", "s-round")
            self.assertIn("轮次", str(context.exception))
            store.close()
            metrics.close()

    def test_help_command_bypasses_model(self):
        provider = ScriptedProvider([])
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(provider, temp_dir)
            result = run_engine(engine, metrics, "/help", "s4")
            self.assertIn("可用指令", result["data"]["reply"])
            self.assertEqual(len(provider.calls), 0)
            store.close()
            metrics.close()

    def test_reset_clears_session_history(self):
        provider = ScriptedProvider([Decision(reply="hello")])
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(provider, temp_dir)
            run_engine(engine, metrics, "Please quote the headphones", "s5")
            run_engine(engine, metrics, "/reset", "s5")
            self.assertEqual(store.load("s5").turns, [])
            store.close()
            metrics.close()

    def test_lang_command_sets_language(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(ScriptedProvider([]), temp_dir)
            run_engine(engine, metrics, "/lang es-ES", "s6")
            self.assertEqual(store.load("s6").language, "es-ES")
            store.close()
            metrics.close()

    def test_handoff_command_marks_needs_human(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine, metrics, store = make_engine(ScriptedProvider([]), temp_dir)
            result = run_engine(engine, metrics, "/handoff", "s7")
            self.assertTrue(result["data"]["needs_human"])
            self.assertEqual(result["data"]["source"], "native+human-handoff")
            store.close()
            metrics.close()


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()
        self.ctx = AgentContext(
            session_id="x",
            session=Session(session_id="x"),
            analysis=analyze_message("hi"),
        )

    def test_schemas_expose_all_builtin_tools(self):
        names = [item["function"]["name"] for item in self.registry.schemas()]
        self.assertEqual(len(names), 6)
        self.assertIn("catalog_quote", names)
        self.assertIn("after_sales_record", names)

    def test_catalog_quote_returns_price(self):
        result = asyncio.run(
            self.registry.invoke("catalog_quote", {"product_id": "headset-pro"}, self.ctx)
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data["price_usd"], 39.0)

    def test_unknown_tool_raises(self):
        with self.assertRaises(AgentError):
            asyncio.run(self.registry.invoke("missing.tool", {}, self.ctx))


class ProviderParsingTests(unittest.TestCase):
    def test_plain_content(self):
        decision = _parse_decision({"choices": [{"message": {"content": "hello"}}]})
        self.assertEqual(decision.reply, "hello")

    def test_tool_calls(self):
        args = json.dumps({"query": "lamp"})
        body = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "catalog_search",
                                    "arguments": args,
                                },
                            }
                        ]
                    }
                }
            ]
        }
        decision = _parse_decision(body)
        self.assertEqual(decision.tool_calls[0].name, "catalog_search")
        self.assertEqual(decision.tool_calls[0].arguments, {"query": "lamp"})

    def test_empty_choices_raises(self):
        with self.assertRaises(AgentError):
            _parse_decision({"choices": []})

    def test_message_serialization(self):
        assistant = Message(
            role="assistant",
            tool_calls=(
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "x", "arguments": "{}"},
                },
            ),
        )
        self.assertIn("tool_calls", assistant.to_openai())
        tool = Message(role="tool", content="{}", tool_call_id="c1", name="x")
        self.assertEqual(tool.to_openai()["tool_call_id"], "c1")


class SessionStoreTests(unittest.TestCase):
    def test_ttl_expires_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir) / "sessions.db")
            session = store.load("s", 24)
            store.append(
                session,
                Turn(
                    role="user",
                    content="hi",
                    created_at=datetime.now(timezone.utc).isoformat(),
                ),
            )
            expired = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
            store.connection.execute(
                "UPDATE agent_sessions SET updated_at = ? WHERE session_id = ?",
                (expired, "s"),
            )
            store.connection.commit()
            self.assertEqual(store.load("s", 24).turns, [])
            store.close()


if __name__ == "__main__":
    unittest.main()
