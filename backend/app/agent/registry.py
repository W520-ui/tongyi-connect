from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.models import AgentContext, AgentError, ToolResult, ToolSpec


class ToolRegistry:
    """Registry of callable tools exposed to the model as JSON schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec
        return spec

    def tool(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        scopes: tuple[str, ...] = (),
    ) -> Callable[[Callable[..., Awaitable[ToolResult]]], Callable[..., Awaitable[ToolResult]]]:
        def decorator(
            handler: Callable[..., Awaitable[ToolResult]],
        ) -> Callable[..., Awaitable[ToolResult]]:
            self.register(
                ToolSpec(
                    name=name,
                    description=description,
                    parameters=parameters,
                    handler=handler,
                    scopes=scopes,
                )
            )
            return handler

        return decorator

    def schemas(self) -> list[dict[str, Any]]:
        return [spec.schema() for spec in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    async def invoke(self, name: str, args: dict[str, Any], ctx: AgentContext) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            raise AgentError(f"模型调用了未注册的工具：{name}")
        try:
            return await spec.handler(args, ctx)
        except AgentError:
            raise
        except Exception as exc:
            return ToolResult(ok=False, content=f"工具执行失败：{exc}")


def create_default_registry() -> ToolRegistry:
    from app.agent.tools import catalog, handoff, knowledge

    registry = ToolRegistry()
    for module in (catalog, handoff, knowledge):
        module.register(registry)
    return registry
