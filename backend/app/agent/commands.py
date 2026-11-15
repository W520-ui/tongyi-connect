from __future__ import annotations

from app.agent.models import AgentContext, CommandResult
from app.agent.session import SessionStore

HELP_TEXT = """可用指令：
/help 查看指令列表
/reset 清空当前会话
/lang <zh-CN|en-US|es-ES> 设置会话语言偏好
/product 查看当前会话记住的商品
/handoff 主动登记人工接管
其余消息会交给智能体处理。"""


class CommandRouter:
    """Slash commands are handled locally before any model call."""

    def __init__(self, store: SessionStore) -> None:
        self.store = store

    @staticmethod
    def parse(message: str) -> tuple[str, str] | None:
        text = message.strip()
        if not text.startswith("/"):
            return None
        name, _, args = text[1:].partition(" ")
        name = name.lower()
        if not name:
            return None
        return name, args.strip()

    async def handle(
        self, name: str, args: str, ctx: AgentContext
    ) -> CommandResult | None:
        if name in {"help", "帮助"}:
            return CommandResult(reply=HELP_TEXT)
        if name in {"reset", "清空"}:
            self.store.clear(ctx.session_id)
            ctx.session.turns.clear()
            ctx.session.last_product_id = None
            ctx.session.language = None
            return CommandResult(
                reply="当前会话已清空，可以重新开始咨询。", persist=False
            )
        if name in {"lang", "language"}:
            if not args:
                return CommandResult(reply="用法：/lang zh-CN、/lang en-US 或 /lang es-ES")
            ctx.language_override = args
            return CommandResult(reply=f"会话语言偏好已设置为 {args}。")
        if name == "product":
            product = ctx.analysis.product
            if product:
                return CommandResult(reply=f"当前商品：{product['name']}（{product['id']}）")
            if ctx.session.last_product_id:
                return CommandResult(reply=f"上一轮商品 ID：{ctx.session.last_product_id}")
            return CommandResult(reply="当前会话还没有匹配到商品，可以直接告诉我商品名称。")
        if name == "handoff":
            return CommandResult(
                reply="已登记人工接管请求，商家会在看板的接管队列中看到这条咨询。",
                needs_human=True,
                handoff_reason="用户主动请求人工接管",
            )
        return None
