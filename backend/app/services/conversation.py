import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.agent.commands import HELP_TEXT, CommandRouter
from app.agent.context import ContextBuilder
from app.agent.effects import FocusProducts, RequestHandoff, UpdateSlots
from app.agent.events import RunCompleted, RunFailed, ToolFinished, ToolStarted
from app.agent.guardrails import analyze_message
from app.agent.runtime import AgentRunner, RunContext
from app.agent.tools.deps import CatalogPort
from app.core.config import Settings
from app.core.errors import AppError
from app.core.locks import ConversationLocks
from app.domain.types import (
    INTENT_LABELS,
    LANGUAGE_LABELS,
    InboundMessage,
    RunTrace,
    Session,
    Turn,
    WorkflowResult,
)
from app.repositories.archive import WorkflowArchive
from app.repositories.session import SessionStore
from app.services.analytics import AnalyticsService
from app.services.catalog import CatalogService
from app.services.handoff import HandoffService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceToolDeps:
    catalog: CatalogPort


def merchant_summary(message, analysis, needs_human, product):
    return (
        f"客户语言：{LANGUAGE_LABELS[analysis.language]}；意图：{INTENT_LABELS[analysis.intent]}；"
        f"商品：{product.name if product else '未识别商品'}；"
        f"处理建议：{'需要人工接管' if needs_human else '可由智能体继续处理'}。"
        f"原始咨询：{message.strip()}"
    )


class ConversationService:
    def __init__(
        self,
        settings: Settings,
        runner: AgentRunner,
        context: ContextBuilder,
        store: SessionStore,
        archive: WorkflowArchive,
        catalog: CatalogService,
        analytics: AnalyticsService,
        handoffs: HandoffService,
        locks: ConversationLocks,
    ) -> None:
        self.settings, self.runner, self.context = settings, runner, context
        self.store, self.archive, self.catalog = store, archive, catalog
        self.analytics, self.handoffs, self.locks = analytics, handoffs, locks
        self.commands = CommandRouter()
        self.tool_deps = ServiceToolDeps(catalog)

    async def handle_inbound(self, inbound: InboundMessage) -> WorkflowResult:
        session_id = (inbound.session_id or str(uuid4()))[:120]
        try:
            async with self.locks.hold(session_id):
                session = self.store.load(session_id, self.settings.session_ttl_hours)
                analysis = analyze_message(
                    inbound.message, self.catalog.products, session.last_product_id
                )
                parsed = self.commands.parse(inbound.message)
                if parsed:
                    result = await self.commands.handle(
                        *parsed, _CommandActions(self, inbound, session)
                    )
                    if result is not None:
                        return result
                started = perf_counter()
                messages = await self.context.build(inbound, session, analysis.language)
                completed = None
                steps = ["加载会话上下文"]
                async for event in self.runner.run(
                    RunContext(messages, self.tool_deps, inbound.streaming)
                ):
                    if isinstance(event, ToolStarted):
                        steps.append(f"调用工具：{event.name}")
                    elif isinstance(event, ToolFinished):
                        steps.append(f"工具{'完成' if event.ok else '失败'}：{event.name}")
                    elif isinstance(event, RunFailed):
                        raise AppError(event.error_code, event.message)
                    elif isinstance(event, RunCompleted):
                        completed = event
                if completed is None:
                    raise AppError("INTERNAL_ERROR")
                effects = list(completed.effects)
                if analysis.needs_human and not any(
                    isinstance(effect, RequestHandoff) for effect in effects
                ):
                    effects.append(
                        RequestHandoff(
                            "guardrail", analysis.handoff_reason or "退款或投诉需要人工确认"
                        )
                    )
                focus = tuple(
                    dict.fromkeys(
                        product_id
                        for effect in effects
                        if isinstance(effect, FocusProducts)
                        for product_id in effect.product_ids
                    )
                )
                if focus:
                    session.focused_product_ids = focus
                elif analysis.product:
                    session.focused_product_ids = (analysis.product.id,)
                products = tuple(
                    [
                        product
                        for product_id in session.focused_product_ids
                        if (product := await self.catalog.get(product_id)) is not None
                    ]
                )
                if focus and products:
                    analysis = replace(analysis, product=products[0], product_confidence=0.96)
                for effect in effects:
                    if isinstance(effect, UpdateSlots):
                        if effect.destination_country is not None:
                            session.destination_country = effect.destination_country
                        if effect.quantity is not None:
                            session.quantity = effect.quantity
                existing = self.handoffs.pending_for(session_id)
                handoff = next(
                    (effect for effect in effects if isinstance(effect, RequestHandoff)), None
                )
                needs_human = existing is not None or handoff is not None
                reason = (
                    existing["handoff_reason"]
                    if existing
                    else handoff.reason_text
                    if handoff
                    else None
                )
                issue = (
                    existing["issue_summary"]
                    if existing
                    else handoff.issue_summary
                    if handoff
                    else None
                )
                session.detected_language = analysis.detected_language
                now = datetime.now(UTC).isoformat()
                session.turns.append(Turn("user", inbound.message, now))
                session.turns.extend(
                    Turn(
                        message.role,
                        message.content,
                        now,
                        message.tool_calls,
                        message.tool_call_id,
                        message.name,
                    )
                    for message in completed.messages
                )
                self.store.save(session)
                steps.extend(("生成对客回复", "生成商家摘要", "保存会话与咨询归档"))
                if needs_human and not existing:
                    steps.append("登记人工接管")
                result = WorkflowResult(
                    reply=completed.reply,
                    merchant_summary=merchant_summary(
                        inbound.message, analysis, needs_human, products[0] if products else None
                    ),
                    analysis=analysis,
                    products=products,
                    needs_human=needs_human,
                    handoff_reason=reason,
                    issue_summary=issue,
                    source="native+human-handoff" if needs_human else "native",
                    session_id=session_id,
                    trace=completed.trace,
                    steps=tuple(steps),
                )
                self.archive.append(inbound.message, result)
                logger.info(
                    "Agent run model=%s rounds=%s prompt_tokens=%s "
                    "completion_tokens=%s latency_ms=%.1f",
                    self.settings.llm_model,
                    completed.rounds,
                    completed.usage.prompt_tokens if completed.usage else None,
                    completed.usage.completion_tokens if completed.usage else None,
                    (perf_counter() - started) * 1000,
                )
                return result
        except AppError as error:
            self.analytics.record_failed_request(error.code)
            raise
        except Exception:
            logger.exception("Unexpected conversation failure")
            self.analytics.record_failed_request("INTERNAL_ERROR")
            raise AppError("INTERNAL_ERROR") from None


class _CommandActions:
    def __init__(
        self, service: ConversationService, inbound: InboundMessage, session: Session
    ) -> None:
        self.service, self.inbound, self.session = service, inbound, session

    async def _result(self, reply: str, *, handoff: bool = False) -> WorkflowResult:
        products = tuple(
            [
                product
                for product_id in self.session.focused_product_ids
                if (product := await self.service.catalog.get(product_id)) is not None
            ]
        )
        analysis = analyze_message(self.inbound.message, self.service.catalog.products)
        reason = "用户主动请求人工接管" if handoff else None
        return WorkflowResult(
            reply=reply,
            merchant_summary=merchant_summary(
                self.inbound.message, analysis, handoff, products[0] if products else None
            ),
            analysis=analysis,
            products=products,
            needs_human=handoff,
            handoff_reason=reason,
            issue_summary=None,
            source="native+human-handoff" if handoff else "native",
            session_id=self.session.session_id,
            trace=RunTrace(),
            steps=("处理本地指令",),
        )

    async def command_help(self) -> WorkflowResult:
        return await self._result(HELP_TEXT)

    async def command_reset(self) -> WorkflowResult:
        self.service.store.clear(self.session.session_id)
        self.session = Session(self.session.session_id)
        return await self._result("当前会话已清空，可以重新开始咨询。")

    async def command_language(self, language: str) -> WorkflowResult:
        if language not in LANGUAGE_LABELS:
            return await self._result(
                "用法：/lang zh-CN、/lang en-US 或 /lang es-ES；请选择有效的语言。"
            )
        self.session.reply_language = language
        self.service.store.save(self.session)
        return await self._result(f"会话语言偏好已设置为 {language}。")

    async def command_product(self) -> WorkflowResult:
        product = (
            await self.service.catalog.get(self.session.last_product_id)
            if self.session.last_product_id
            else None
        )
        return await self._result(
            f"当前商品：{product.name}（{product.id}）"
            if product
            else "当前会话还没有匹配到商品，可以直接告诉我商品名称。"
        )

    async def command_handoff(self) -> WorkflowResult:
        result = await self._result(
            "已登记人工接管请求，商家会在看板的接管队列中看到这条咨询。", handoff=True
        )
        if self.service.handoffs.pending_for(self.session.session_id) is None:
            self.service.archive.append(self.inbound.message, result, is_command=True)
        return result
