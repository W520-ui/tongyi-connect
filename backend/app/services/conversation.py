import asyncio
import logging
import re
from dataclasses import asdict, dataclass, replace
from time import perf_counter
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.agent.analysis import PostAnalyzer, heuristic_outcome
from app.agent.commands import HELP_TEXT, CommandRouter
from app.agent.context import ContextBuilder
from app.agent.effects import FocusProducts, RequestHandoff, UpdateSlots
from app.agent.events import RunCompleted, RunFailed, TextDelta, ToolFinished, ToolStarted
from app.agent.guardrails import analyze_message, detect_language
from app.agent.runtime import AgentRunner, RunContext
from app.agent.tools.deps import CatalogPort
from app.core.background import BackgroundTasks
from app.core.config import Settings
from app.core.errors import AppError
from app.core.locks import ConversationLocks
from app.domain.types import InboundMessage, RunTrace, ToolTraceEntry, WorkflowResult
from app.repositories.conversations import ConversationRepository, now
from app.repositories.models import AgentRun, CommandReceipt, RequestFailure, StoredMessage
from app.services.analytics import AnalyticsService
from app.services.catalog import CatalogService
from app.services.events import AnalysisCompleted, WorkflowCompleted
from app.services.handoff import HandoffService
from app.services.results import restore_result

logger = logging.getLogger(__name__)
PAUSED_REPLIES = {
    "zh-CN": "已转人工，商家会尽快回复您。",
    "en-US": "You've been connected to our team. A staff member will reply shortly.",
    "es-ES": "Le hemos transferido a nuestro equipo. Un agente le responderá en breve.",
}


@dataclass(frozen=True)
class ServiceToolDeps:
    catalog: CatalogPort


class ConversationService:
    def __init__(
        self,
        settings: Settings,
        runner: AgentRunner,
        context: ContextBuilder,
        store: ConversationRepository,
        catalog: CatalogService,
        analytics: AnalyticsService,
        handoffs: HandoffService,
        locks: ConversationLocks,
        analyzer: PostAnalyzer,
        background: BackgroundTasks,
    ):
        self.settings, self.runner, self.context = settings, runner, context
        self.store, self.catalog, self.analytics = store, catalog, analytics
        self.database, self.handoffs, self.locks = store.database, handoffs, locks
        self.analyzer, self.background = analyzer, background
        self.commands, self.tool_deps = CommandRouter(), ServiceToolDeps(catalog)

    async def describe(self, conversation_id):
        snapshot = await self.store.get(conversation_id)
        ticket = await self.handoffs.pending_for(conversation_id)
        return {
            "id": snapshot.session_id,
            "status": snapshot.status,
            "reply_language": snapshot.reply_language,
            "state": {
                "focused_product_ids": list(snapshot.focused_product_ids),
                "destination_country": snapshot.destination_country,
                "quantity": snapshot.quantity,
            },
            "open_handoff": ticket,
            "created_at": snapshot.created_at,
            "updated_at": snapshot.updated_at,
            "last_message_at": snapshot.last_message_at,
        }

    async def create(self, reply_language=None):
        snapshot = await self.store.create(reply_language)
        return await self.describe(snapshot.session_id)

    async def update_language(self, conversation_id, language):
        async with self.locks.hold(conversation_id):
            snapshot = await self.store.get(conversation_id)
            snapshot.reply_language = language
            await self.store.save_state(snapshot)
            return await self.describe(conversation_id)

    async def history(self, conversation_id, limit=50, before_seq=None):
        await self.store.get(conversation_id)
        items, has_more = await self.store.history(conversation_id, limit, before_seq)
        for item in items:
            if item["workflow"]:
                item["workflow"] = restore_result(item["workflow"])
        return items, has_more

    async def reset(self, conversation_id):
        async with self.locks.hold(conversation_id):
            snapshot = await self.store.get(conversation_id)
            replacement = await self.handoffs.reset(snapshot)
            return await self.describe(replacement.session_id)

    async def request_handoff(self, conversation_id, reason_text):
        async with self.locks.hold(conversation_id):
            snapshot = await self.store.get(conversation_id)
            analysis = analyze_message("/handoff", await self.catalog.list_products())
            latest = next((turn for turn in reversed(snapshot.turns) if turn.role == "user"), None)
            if latest:
                analysis = analyze_message(latest.content, await self.catalog.list_products())
            async with self.database.transaction() as transaction:
                ticket = await self.handoffs.pending_for(conversation_id, transaction)
                if ticket is None:
                    await self.store.update(transaction, snapshot, status="pending_human")
                    ticket = await self.handoffs.request(
                        transaction,
                        snapshot,
                        RequestHandoff("user_request", reason_text),
                        latest.id if latest else None,
                        latest.content if latest else "",
                        analysis,
                    )
            return await self.describe(conversation_id), ticket

    async def change_handoff(self, ticket_id, *, resolve=False):
        ticket = await self.handoffs.get(ticket_id)
        async with self.locks.hold(ticket.conversation_id):
            return await self.handoffs.change(ticket_id, resolve=resolve)

    async def handle_inbound(
        self, inbound: InboundMessage, *, emit=None, ready=None
    ) -> WorkflowResult:
        key = inbound.session_id or str(uuid4())
        if inbound.legacy_session:
            key = key[:120]
        try:
            async with self.locks.hold(key):
                resolved = (
                    await self.store.resolve(key)
                    if inbound.legacy_session
                    else await self.store.get(key)
                )
                async with (
                    self.locks.hold(resolved.session_id)
                    if key != resolved.session_id
                    else _Unlocked()
                ):
                    snapshot = await self.store.get(resolved.session_id)
                    replay = await self._replay(snapshot, inbound)
                    if replay is not None:
                        if ready:
                            ready()
                        if emit:
                            await emit(WorkflowCompleted(replay))
                        return replay
                    parsed = self.commands.parse(inbound.message)
                    if not inbound.legacy_session and not parsed:
                        if (
                            snapshot.status != "human_active"
                            and not self.runner.client.is_configured
                        ):
                            raise AppError("LLM_NOT_CONFIGURED")
                    if ready:
                        ready()
                    if parsed:
                        async with self.database.transaction() as transaction:
                            result = await self.commands.handle(
                                *parsed, _CommandActions(self, inbound, snapshot, transaction)
                            )
                            if result is not None and inbound.client_message_id:
                                transaction.add(
                                    CommandReceipt(
                                        merchant_id=self.settings.merchant_id,
                                        conversation_id=resolved.session_id,
                                        client_message_id=inbound.client_message_id,
                                        workflow=asdict(result),
                                        created_at=now(),
                                    )
                                )
                        if result is not None:
                            if emit:
                                await emit(WorkflowCompleted(result))
                            return result
                    if snapshot.status == "human_active":
                        result = await self._paused(snapshot, inbound)
                        if emit:
                            await emit(WorkflowCompleted(result))
                        return result
                    return await self._run(snapshot, inbound, emit=emit)
        except AppError as error:
            if not error.recorded:
                await self.analytics.record_failed_request(error.code)
            raise
        except OperationalError:
            await self.analytics.record_failed_request("CONVERSATION_BUSY")
            raise AppError("CONVERSATION_BUSY") from None
        except Exception:
            logger.exception("Unexpected conversation failure")
            await self.analytics.record_failed_request("INTERNAL_ERROR")
            raise AppError("INTERNAL_ERROR") from None

    async def _replay(self, snapshot, inbound):
        if not inbound.client_message_id:
            return None
        async with self.database.sessions() as transaction:
            receipt = await transaction.get(
                CommandReceipt, (snapshot.session_id, inbound.client_message_id)
            )
            if receipt and receipt.merchant_id == self.settings.merchant_id:
                return replace(restore_result(receipt.workflow), replayed=True)
            user = await transaction.scalar(
                select(StoredMessage).where(
                    StoredMessage.conversation_id == snapshot.session_id,
                    StoredMessage.client_message_id == inbound.client_message_id,
                    StoredMessage.merchant_id == self.settings.merchant_id,
                    StoredMessage.role == "user",
                )
            )
            if not user:
                return None
            if user.workflow:
                return replace(restore_result(user.workflow), replayed=True)
            run = await transaction.scalar(
                select(AgentRun).where(AgentRun.trigger_message_id == user.id)
            )
            if run and run.status == "error":
                error = AppError(run.error_code)
                error.recorded = True
                raise error
            return (
                replace(restore_result(run.workflow), replayed=True)
                if run and run.workflow
                else None
            )

    async def _products(self, snapshot):
        products = []
        for product_id in snapshot.focused_product_ids:
            product = await self.catalog.get(product_id)
            if product is not None:
                products.append(product)
        return tuple(products)

    async def _base_result(
        self,
        snapshot,
        inbound,
        reply,
        *,
        source="native",
        needs_human=False,
        reason=None,
        issue=None,
        handoff_id=None,
    ):
        products = await self._products(snapshot)
        analysis = analyze_message(
            inbound.message, await self.catalog.list_products(), snapshot.last_product_id
        )
        fallback = heuristic_outcome(inbound.message, analysis, products, needs_human, reason)
        return WorkflowResult(
            reply,
            fallback["merchant_summary_zh"],
            analysis,
            products,
            needs_human,
            reason,
            issue,
            source,
            snapshot.session_id,
            RunTrace(),
            ("处理本地指令",),
            snapshot.status,
            message_id=str(uuid4()),
            client_message_id=inbound.client_message_id,
            handoff_id=handoff_id,
        )

    async def _paused(self, snapshot, inbound, *, persist=True):
        language = snapshot.reply_language
        if not language:
            language = (
                detect_language(inbound.message)
                if re.search(r"[a-zA-Z\u4e00-\u9fff¿¡]", inbound.message)
                else "zh-CN"
            )
        ticket = await self.handoffs.pending_for(snapshot.session_id)
        result = await self._base_result(
            snapshot,
            inbound,
            PAUSED_REPLIES[language],
            source="paused-for-human",
            needs_human=True,
            reason=ticket.reason_text if ticket else None,
            issue=ticket.issue_summary if ticket else None,
            handoff_id=ticket.id if ticket else None,
        )
        if persist:
            message_id = str(uuid4())
            result = replace(result, message_id=message_id, steps=("保存客户消息，等待人工回复",))
            async with self.database.transaction() as transaction:
                await self.store.update(transaction, snapshot, last_message_at=now())
                await self.store.append(
                    transaction,
                    snapshot,
                    [self._user_message(inbound, result, None, workflow=asdict(result))],
                )
        return result

    def _user_message(self, inbound, result, run_id, *, workflow=None):
        return {
            "id": result.message_id,
            "role": "user",
            "content": inbound.message,
            "run_id": run_id,
            "created_at": now(),
            "client_message_id": inbound.client_message_id,
            "detected_language": result.analysis.detected_language,
            "workflow": workflow,
        }

    async def _run(self, snapshot, inbound, *, emit=None):
        started = perf_counter()
        analysis = analyze_message(
            inbound.message, await self.catalog.list_products(), snapshot.last_product_id
        )
        built = await self.context.build_details(inbound, snapshot)
        completed, observed = None, {}
        failure = None
        steps = ["加载会话上下文"]
        try:
            async for event in self.runner.run(
                RunContext(built.messages, self.tool_deps, inbound.streaming)
            ):
                if emit and isinstance(event, (ToolStarted, ToolFinished, TextDelta)):
                    await emit(event)
                if isinstance(event, ToolStarted):
                    steps.append(f"调用工具：{event.name}")
                    observed[(event.round, event.call_id)] = (event, None)
                elif isinstance(event, ToolFinished):
                    steps.append(f"工具{'完成' if event.ok else '失败'}：{event.name}")
                    previous = observed.get((event.round, event.call_id))
                    if previous:
                        observed[(event.round, event.call_id)] = (previous[0], event)
                elif isinstance(event, RunFailed):
                    failure = event
                    raise AppError(event.error_code, event.message)
                elif isinstance(event, RunCompleted):
                    completed = event
            if completed is None:
                raise AppError("INTERNAL_ERROR")
        except AppError as error:
            await self._save_failure(snapshot, inbound, analysis, error, observed, started, failure)
            error.recorded = True
            raise
        effects = list(completed.effects)
        if analysis.needs_human and not any(
            isinstance(effect, RequestHandoff) for effect in effects
        ):
            effects.append(
                RequestHandoff("guardrail", analysis.handoff_reason or "退款或投诉需要人工确认")
            )
        focus = [effect for effect in effects if isinstance(effect, FocusProducts)]
        if focus:
            snapshot.focused_product_ids = tuple(
                dict.fromkeys(product_id for effect in focus for product_id in effect.product_ids)
            )
        for effect in effects:
            if isinstance(effect, UpdateSlots):
                if effect.destination_country is not None:
                    snapshot.destination_country = effect.destination_country
                if effect.quantity is not None:
                    snapshot.quantity = effect.quantity
        products = await self._products(snapshot)
        if focus and products:
            analysis = replace(analysis, product=products[0], product_confidence=0.96)
        run_id, message_id, timestamp = str(uuid4()), str(uuid4()), now()
        handoff_effect = next(
            (effect for effect in effects if isinstance(effect, RequestHandoff)), None
        )
        async with self.database.transaction() as transaction:
            await self.store.update(
                transaction,
                snapshot,
                state={
                    "focused_product_ids": list(snapshot.focused_product_ids),
                    "destination_country": snapshot.destination_country,
                    "quantity": snapshot.quantity,
                },
                status="pending_human"
                if handoff_effect or snapshot.status == "pending_human"
                else "bot_active",
                last_message_at=timestamp,
            )
            provisional = WorkflowResult(
                "",
                "",
                analysis,
                products,
                False,
                None,
                None,
                "native",
                snapshot.session_id,
                completed.trace,
                message_id=message_id,
            )
            messages = [self._user_message(inbound, provisional, run_id)]
            messages.extend(
                {
                    "id": str(uuid4()),
                    "role": message.role,
                    "content": message.content,
                    "tool_calls": list(message.tool_calls) or None,
                    "tool_call_id": message.tool_call_id,
                    "name": message.name,
                    "run_id": run_id,
                    "created_at": timestamp,
                }
                for message in completed.messages
            )
            await self.store.append(transaction, snapshot, messages)
            ticket = (
                await self.handoffs.request(
                    transaction, snapshot, handoff_effect, message_id, inbound.message, analysis
                )
                if handoff_effect
                else await self.handoffs.pending_for(snapshot.session_id, transaction)
            )
            needs_human = ticket is not None
            reason, issue = (ticket.reason_text, ticket.issue_summary) if ticket else (None, None)
            fallback = heuristic_outcome(inbound.message, analysis, products, needs_human, reason)
            steps.extend(("生成对客回复", "生成商家摘要", "保存会话与咨询归档"))
            if handoff_effect and snapshot.status != "pending_human":
                steps.append("登记人工接管")
            result = WorkflowResult(
                completed.reply,
                fallback["merchant_summary_zh"],
                analysis,
                products,
                needs_human,
                reason,
                issue,
                "native+human-handoff" if needs_human else "native",
                snapshot.session_id,
                completed.trace,
                tuple(steps),
                "pending_human" if ticket else "bot_active",
                message_id,
                inbound.client_message_id,
                run_id,
                handoff_id=ticket.id if ticket else None,
            )
            transaction.add(
                AgentRun(
                    id=run_id,
                    merchant_id=self.settings.merchant_id,
                    conversation_id=snapshot.session_id,
                    trigger_message_id=message_id,
                    model=self.settings.llm_model,
                    status="ok",
                    rounds=completed.rounds,
                    tool_trace=asdict(completed.trace),
                    prompt_tokens=completed.usage.prompt_tokens if completed.usage else 0,
                    completion_tokens=completed.usage.completion_tokens if completed.usage else 0,
                    latency_ms=(perf_counter() - started) * 1000,
                    outcome=fallback,
                    analysis_source="heuristic",
                    workflow=asdict(result),
                    created_at=timestamp,
                )
            )
        if emit:
            await emit(WorkflowCompleted(replace(result, analysis_source="pending")))
        try:
            final, outcome = await self._analyze(result, fallback, started, inbound.message)
        except Exception:
            logger.exception("Post-analysis failed; using the saved heuristic result")
            final, outcome = result, fallback
        if emit:
            await emit(AnalysisCompleted(final, outcome))
        if self.settings.summary_enabled and built.omitted:
            earlier = built.omitted
            if snapshot.summary:
                from app.domain.types import Message

                earlier = (Message("system", snapshot.summary), *earlier)
            self.background.schedule(
                self._summarize(snapshot.session_id, snapshot.version + 1, earlier)
            )
        logger.info(
            "Agent run model=%s rounds=%s latency_ms=%.1f",
            self.settings.llm_model,
            completed.rounds,
            (perf_counter() - started) * 1000,
        )
        return final

    async def _analyze(self, result, fallback, started, customer_message):
        known_ids = tuple(product.id for product in await self.catalog.list_products())
        remaining = self.settings.run_timeout_seconds - (perf_counter() - started)
        analyzed = await self.analyzer.analyze(
            customer_message, result.reply, fallback, known_ids, remaining_seconds=remaining
        )
        outcome = analyzed.outcome
        analysis = replace(
            result.analysis,
            intent=outcome["intents"][0],
            intents=tuple(outcome["intents"]),
            language=outcome["language"],
            detected_language=outcome["language"],
            confidence=outcome["confidence"],
        )
        final = replace(
            result,
            merchant_summary=outcome["merchant_summary_zh"],
            analysis=analysis,
            analysis_source=analyzed.source,
        )
        try:
            async with self.database.transaction() as transaction:
                run = await transaction.get(AgentRun, result.run_id)
                run.outcome, run.analysis_source, run.workflow = (
                    outcome,
                    analyzed.source,
                    asdict(final),
                )
                run.latency_ms = (perf_counter() - started) * 1000
                if analyzed.usage:
                    run.prompt_tokens += analyzed.usage.prompt_tokens
                    run.completion_tokens += analyzed.usage.completion_tokens
        except Exception:
            logger.exception("Unable to persist post-analysis; returning saved heuristic result")
            return result, fallback
        return final, outcome

    async def _save_failure(self, snapshot, inbound, analysis, error, observed, started, failure):
        message_id, run_id = str(uuid4()), str(uuid4())
        result = WorkflowResult(
            "",
            "",
            analysis,
            (),
            False,
            None,
            None,
            "native",
            snapshot.session_id,
            RunTrace(),
            message_id=message_id,
        )
        trace = tuple(
            ToolTraceEntry(
                start.call_id,
                start.round,
                start.name,
                start.args,
                finished.ok if finished else False,
                finished.latency_ms if finished else 0,
                finished.error if finished else error.message,
            )
            for start, finished in observed.values()
        )
        async with self.database.transaction() as transaction:
            await self.store.update(
                transaction,
                snapshot,
                status="bot_active" if snapshot.status == "resolved" else snapshot.status,
                last_message_at=now(),
            )
            await self.store.append(
                transaction, snapshot, [self._user_message(inbound, result, run_id)]
            )
            transaction.add(
                AgentRun(
                    id=run_id,
                    merchant_id=self.settings.merchant_id,
                    conversation_id=snapshot.session_id,
                    trigger_message_id=message_id,
                    model=self.settings.llm_model,
                    status="error",
                    error_code=error.code,
                    rounds=failure.rounds if failure else 0,
                    tool_trace=asdict(
                        RunTrace(trace, failure.trace.truncated if failure else False)
                    ),
                    prompt_tokens=failure.usage.prompt_tokens if failure and failure.usage else 0,
                    completion_tokens=failure.usage.completion_tokens
                    if failure and failure.usage
                    else 0,
                    latency_ms=(perf_counter() - started) * 1000,
                    outcome=heuristic_outcome(inbound.message, analysis, (), False, None),
                    analysis_source="heuristic",
                    workflow=None,
                    created_at=now(),
                )
            )
            transaction.add(
                RequestFailure(
                    id=str(uuid4()),
                    merchant_id=self.settings.merchant_id,
                    conversation_id=snapshot.session_id,
                    error_code=error.code,
                    created_at=now(),
                )
            )

    async def _summarize(self, conversation_id, version, messages):
        try:
            async with asyncio.timeout(self.settings.analysis_timeout_seconds):
                summary = await self.analyzer.summarize(messages)
                await self.store.update_summary(conversation_id, version, summary)
        except Exception as error:
            logger.warning("Conversation summary unavailable: %s", type(error).__name__)


class _Unlocked:
    async def __aenter__(self):
        pass

    async def __aexit__(self, *_args):
        pass


class _CommandActions:
    def __init__(self, service, inbound, snapshot, transaction):
        self.service, self.inbound, self.snapshot = service, inbound, snapshot
        self.transaction = transaction

    async def result(self, text):
        ticket = await self.service.handoffs.pending_for(self.snapshot.session_id, self.transaction)
        return await self.service._base_result(
            self.snapshot,
            self.inbound,
            text,
            source="native+human-handoff" if ticket else "native",
            needs_human=bool(ticket),
            reason=ticket.reason_text if ticket else None,
            issue=ticket.issue_summary if ticket else None,
            handoff_id=ticket.id if ticket else None,
        )

    async def command_help(self):
        return await self.result(HELP_TEXT)

    async def command_product(self):
        product = (
            await self.service.catalog.get(self.snapshot.last_product_id)
            if self.snapshot.last_product_id
            else None
        )
        return await self.result(
            f"当前商品：{product.name}（{product.id}）"
            if product
            else "当前会话还没有匹配到商品，可以直接告诉我商品名称。"
        )

    async def command_language(self, language):
        if language not in PAUSED_REPLIES:
            return await self.result(
                "用法：/lang zh-CN、/lang en-US 或 /lang es-ES；请选择有效的语言。"
            )
        self.snapshot.reply_language = language
        await self.service.store.update(self.transaction, self.snapshot, reply_language=language)
        return await self.result(f"会话语言偏好已设置为 {language}。")

    async def command_reset(self):
        self.snapshot = await self.service.handoffs.reset(self.snapshot, self.transaction)
        return await self.result("当前会话已关闭，已新建会话，可以重新开始咨询。")

    async def command_handoff(self):
        analysis = analyze_message(self.inbound.message, await self.service.catalog.list_products())
        existing = await self.service.handoffs.pending_for(
            self.snapshot.session_id, self.transaction
        )
        if not existing:
            await self.service.store.update(self.transaction, self.snapshot, status="pending_human")
            await self.service.handoffs.request(
                self.transaction,
                self.snapshot,
                RequestHandoff("user_request", "用户主动请求人工接管"),
                None,
                self.inbound.message,
                analysis,
            )
            self.snapshot.status = "pending_human"
        return await self.result("已登记人工接管请求，商家会在看板的接管队列中看到这条咨询。")
