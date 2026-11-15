from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from app.agent.effects import Effect
from app.agent.tools.deps import ToolDeps


@dataclass(frozen=True)
class ToolOutput:
    content: str
    ok: bool = True
    effects: tuple[Effect, ...] = ()


class Tool(Protocol):
    name: str
    description: str
    args_model: type[BaseModel]
    timeout_seconds: float

    async def run(self, args: BaseModel, deps: ToolDeps) -> ToolOutput: ...


@dataclass(frozen=True)
class FunctionTool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel, ToolDeps], Awaitable[ToolOutput]]
    timeout_seconds: float = 10

    async def run(self, args: BaseModel, deps: ToolDeps) -> ToolOutput:
        return await self.handler(args, deps)
