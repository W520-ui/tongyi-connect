from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from app.agent.commands import CommandRouter
from app.agent.config import AgentSettings, get_agent_settings
from app.agent.hooks import Hooks
from app.agent.models import AgentContext, AgentError, Message, Turn
from app.agent.prompts import build_system_prompt
from app.agent.providers.base import LLMProvider
from app.agent.providers.openai import OpenAICompatibleProvider
from app.agent.registry import ToolRegistry, create_default_registry
from app.agent.session import SessionStore
from app.schemas.agent import AgentChatRequest
from app.services.workflow import analyze_message, build_workflow_answer, metrics

logger = logging.getLogger(__name__)


class AgentEngine:
    """Orchestrates commands, sessions, LLM decisions and tool execution."""

    def __init__(
        self,
        settings: AgentSettings,
        provider: LLMProvider,
        registry: ToolRegistry,
        store: SessionStore,
        commands: CommandRouter,
        hooks: Hooks,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.registry = registry
        self.store = store
        self.commands = commands
        self.hooks = hooks

    @classmethod
    def create(cls, settings: AgentSettings | None = None) -> AgentEngine:
        settings = settings or get_agent_settings()
        store = SessionStore()
        hooks = Hooks()
        hooks.on(
            "on_tool_call",
            lambda _event, payload: logger.info(
                "agent tool %s ok=%s", payload.get("name"), payload.get("ok")
            ),
        )
        return cls(
            settings=settings,
            provider=OpenAICompatibleProvider(settings),
            registry=create_default_registry(),
            store=store,
            commands=CommandRouter(store),
            hooks=hooks,
        )

    async def chat(self, request: AgentChatRequest) -> dict[str, Any]:
        session_id = (request.session_id or "未命名会话")[:120]
        session = self.store.load(session_id, self.settings.session_ttl_hours)
        hint = session.last_product_id or (
            metrics.last_product_id(session_id) if request.session_id else None
        )
        analysis = analyze_message(request.message, product_hint=hint)
        ctx = AgentContext(
            session_id=session_id,
            session=session,
            analysis=analysis,
            locale=request.locale,
        )

        parsed = self.commands.parse(request.message)
        if parsed:
            result = await self.commands.handle(parsed[0], parsed[1], ctx)
            if result is not None:
                if result.needs_human and not analysis.needs_human:
                    analysis = replace(
                        analysis,
                        needs_human=True,
                        handoff_reason=result.handoff_reason or "用户主动请求人工接管",
                    )
                    ctx.analysis = analysis
                return self._finalize(
                    request,
                    ctx,
                    result.reply,
                    needs_human_override=result.needs_human,
                    handoff_reason=result.handoff_reason,
                    persist=result.persist,
                )

        if not self.provider.is_configured:
            raise AgentError("尚未配置 AGENT_LLM_API_KEY，无法生成回复")

        messages = self._build_messages(request, ctx)
        tools = self.registry.schemas()
        reply: str | None = None
        needs_human_override = False
        handoff_reason: str | None = None

        for _round in range(self.settings.max_tool_rounds):
            decision = await self.provider.decide(messages, tools)
            if decision.reply is not None:
                reply = decision.reply
                break
            if not decision.tool_calls:
                raise AgentError("模型未返回回复或工具调用")

            assistant_calls = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in decision.tool_calls
            ]
            messages.append(
                Message(role="assistant", content="", tool_calls=tuple(assistant_calls))
            )

            for call in decision.tool_calls:
                result = await self.registry.invoke(call.name, call.arguments, ctx)
                self.hooks.emit(
                    "on_tool_call",
                    {
                        "session_id": session_id,
                        "name": call.name,
                        "ok": result.ok,
                        "round": _round,
                    },
                )
                if result.data.get("needs_human"):
                    needs_human_override = True
                    handoff_reason = result.data.get("handoff_reason")
                messages.append(
                    Message(
                        role="tool",
                        content=result.content,
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

        if reply is None:
            raise AgentError("工具调用轮次已用尽，模型仍未给出最终回复")

        return self._finalize(
            request,
            ctx,
            reply,
            needs_human_override=needs_human_override,
            handoff_reason=handoff_reason,
        )

    def _build_messages(self, request: AgentChatRequest, ctx: AgentContext) -> list[Message]:
        messages = [Message(role="system", content=build_system_prompt(ctx))]
        for turn in ctx.session.turns[-self.settings.max_history_turns :]:
            messages.append(Message(role=turn.role, content=turn.content))
        messages.append(Message(role="user", content=request.message))
        return messages

    def _finalize(
        self,
        request: AgentChatRequest,
        ctx: AgentContext,
        reply: str,
        *,
        needs_human_override: bool = False,
        handoff_reason: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        analysis = ctx.analysis
        if needs_human_override and not analysis.needs_human:
            analysis = replace(
                analysis,
                needs_human=True,
                handoff_reason=handoff_reason or "工具登记了需人工处理的诉求",
            )

        session = ctx.session
        if analysis.product:
            session.last_product_id = analysis.product["id"]
        session.language = ctx.language_override or analysis.language
        if persist:
            now = datetime.now(UTC).isoformat()
            self.store.append(session, Turn(role="user", content=request.message, created_at=now))
            self.store.append(session, Turn(role="assistant", content=reply, created_at=now))

        source = "native+human-handoff" if analysis.needs_human else "native"
        workflow = build_workflow_answer(request.message, analysis, reply=reply, source=source)
        metrics.archive(session_id=ctx.session_id, message=request.message, answer=workflow)
        self.hooks.emit("on_reply", {"session_id": ctx.session_id, "source": source})
        if analysis.needs_human:
            self.hooks.emit(
                "on_handoff",
                {"session_id": ctx.session_id, "reason": analysis.handoff_reason},
            )
        return {"status": "ok", "data": workflow, "message": None}

    def close(self) -> None:
        self.store.close()


@lru_cache
def get_agent_engine() -> AgentEngine:
    return AgentEngine.create()
