from typing import Protocol

from app.domain.types import WorkflowResult

HELP_TEXT = """可用指令：
/help 查看指令列表
/reset 清空当前会话
/lang <zh-CN|en-US|es-ES> 设置会话语言偏好
/product 查看当前会话记住的商品
/handoff 主动登记人工接管
其余消息会交给智能体处理。"""


class CommandServices(Protocol):
    async def command_help(self) -> WorkflowResult: ...
    async def command_reset(self) -> WorkflowResult: ...
    async def command_language(self, language: str) -> WorkflowResult: ...
    async def command_product(self) -> WorkflowResult: ...
    async def command_handoff(self) -> WorkflowResult: ...


class CommandRouter:
    @staticmethod
    def parse(message: str) -> tuple[str, str] | None:
        text = message.strip()
        if not text.startswith("/"):
            return None
        name, _, args = text[1:].partition(" ")
        return (name.lower(), args.strip()) if name else ("help", "")

    async def handle(
        self, name: str, args: str, services: CommandServices
    ) -> WorkflowResult | None:
        if name in {"help", "帮助"}:
            return await services.command_help()
        if name in {"reset", "清空"}:
            return await services.command_reset()
        if name in {"lang", "language"}:
            return await services.command_language(args)
        if name == "product":
            return await services.command_product()
        if name == "handoff":
            return await services.command_handoff()
        return await services.command_help()
