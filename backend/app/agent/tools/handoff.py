from __future__ import annotations

import json
from typing import Any

from app.agent.models import ToolResult
from app.agent.registry import ToolRegistry


def register(registry: ToolRegistry) -> None:
    @registry.tool(
        name="after_sales_record",
        description="登记售后、退款、退货或质量投诉，并触发商家人工接管",
        parameters={
            "type": "object",
            "properties": {
                "issue": {"type": "string", "description": "客户诉求摘要"},
                "product_id": {"type": "string", "description": "相关商品 ID，可为空"},
            },
            "required": ["issue"],
        },
        scopes=("handoff",),
    )
    async def record(args: dict[str, Any], ctx: Any) -> ToolResult:
        issue = str(args.get("issue") or "客户提出售后诉求").strip()
        product_id = str(args.get("product_id") or ctx.session.last_product_id or "")
        payload = {
            "registered": True,
            "issue": issue,
            "product_id": product_id or None,
            "next_step": "商家在工作台的人工接管队列中确认",
        }
        return ToolResult(
            ok=True,
            content=json.dumps(payload, ensure_ascii=False),
            data={
                **payload,
                "needs_human": True,
                "handoff_reason": "售后、退款或质量问题需要人工核实",
            },
        )
