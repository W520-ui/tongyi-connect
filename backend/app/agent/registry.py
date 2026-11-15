import asyncio
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.agent.tools.base import Tool, ToolOutput
from app.agent.tools.deps import ToolDeps
from app.agent.tools.outputs import error_output

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]+", tool.name):
            raise ValueError("Tool names must contain only letters, numbers and underscores")
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_model.model_json_schema(),
                },
            }
            for tool in self._tools.values()
        ]

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    async def invoke(self, name: str, arguments: Any, deps: ToolDeps) -> ToolOutput:
        tool = self._tools.get(name)
        if tool is None:
            return error_output("UNKNOWN_TOOL", f"Unknown tool: {name}")
        try:
            raw = json.loads(arguments) if isinstance(arguments, str) else arguments
            args = tool.args_model.model_validate(raw, strict=True)
        except (ValueError, TypeError) as exc:
            if isinstance(exc, ValidationError):
                details = "; ".join(
                    f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                    for item in exc.errors(include_input=False, include_url=False)
                )
            else:
                details = "Arguments must be a valid JSON object"
            return error_output("TOOL_VALIDATION_ERROR", details)
        try:
            async with asyncio.timeout(tool.timeout_seconds):
                result = await tool.run(args, deps)
                if not isinstance(result, ToolOutput):
                    raise TypeError("Tool must return ToolOutput")
                return result
        except TimeoutError:
            return error_output("TOOL_TIMEOUT", "Tool execution timed out")
        except Exception:
            logger.exception("Tool execution failed: %s", name)
            return error_output("TOOL_EXECUTION_ERROR", "Tool execution failed; please try again")


def create_default_registry(timeout_seconds: float = 10) -> ToolRegistry:
    from app.agent.tools.catalog import catalog_tools
    from app.agent.tools.handoff import handoff_tool

    registry = ToolRegistry()
    for tool in (*catalog_tools(timeout_seconds), handoff_tool(timeout_seconds)):
        registry.register(tool)
    return registry
