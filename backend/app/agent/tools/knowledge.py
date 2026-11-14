from __future__ import annotations

import json
from typing import Any

from app.agent.models import ToolResult
from app.agent.registry import ToolRegistry


def register(registry: ToolRegistry) -> None:
    @registry.tool(
        name="knowledge_search",
        description="检索商家知识库（预留接口，尚未接入数据源）",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "检索问题"}},
            "required": ["query"],
        },
        scopes=("knowledge",),
    )
    async def search(args: dict[str, Any], ctx: Any) -> ToolResult:
        query = str(args.get("query") or "").strip()
        payload = {
            "status": "not_configured",
            "query": query,
            "results": [],
            "note": "知识库尚未接入，请先使用商品资料工具",
        }
        return ToolResult(ok=True, content=json.dumps(payload, ensure_ascii=False))
