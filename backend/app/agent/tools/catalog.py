from __future__ import annotations

import json
from typing import Any

from app.agent.models import ToolResult
from app.agent.registry import ToolRegistry
from app.services.workflow import PRODUCTS


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _public(product: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in product.items() if key != "aliases"}


def _find(product_id: str) -> dict[str, Any] | None:
    return next((item for item in PRODUCTS if item["id"] == product_id), None)


def register(registry: ToolRegistry) -> None:
    @registry.tool(
        name="catalog_search",
        description="按商品名称或关键词检索商品资料库，返回命中的商品列表与 ID",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "商品名称或关键词"}},
            "required": ["query"],
        },
        scopes=("catalog",),
    )
    async def search(args: dict[str, Any], ctx: Any) -> ToolResult:
        query = str(args.get("query") or "").strip().lower()
        if not query:
            return ToolResult(ok=False, content="缺少 query 参数")
        matched: list[dict[str, Any]] = []
        for product in PRODUCTS:
            haystack = (
                product["name"].lower(),
                product["english_name"].lower(),
                *product["aliases"],
            )
            if any(query in token for token in haystack):
                matched.append(_public(product))
        return ToolResult(
            ok=bool(matched),
            content=_json({"count": len(matched), "products": matched}),
            data={"matched_products": matched},
        )

    @registry.tool(
        name="catalog_quote",
        description="查询指定商品的参考价格、库存与币种",
        parameters={
            "type": "object",
            "properties": {"product_id": {"type": "string", "description": "商品 ID"}},
            "required": ["product_id"],
        },
        scopes=("catalog",),
    )
    async def quote(args: dict[str, Any], ctx: Any) -> ToolResult:
        product = _find(str(args.get("product_id") or ""))
        if product is None:
            return ToolResult(ok=False, content="未找到该商品，请先用 catalog_search 检索")
        payload = {
            "product_id": product["id"],
            "name": product["name"],
            "price_usd": product["price_usd"],
            "currency": "USD",
            "stock": product["stock"],
        }
        return ToolResult(ok=True, content=_json(payload), data=payload)

    @registry.tool(
        name="catalog_shipping",
        description="查询指定商品发往目的地的常规配送时效",
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "商品 ID"},
                "destination": {"type": "string", "description": "目的国家或地区"},
            },
            "required": ["product_id"],
        },
        scopes=("catalog",),
    )
    async def shipping(args: dict[str, Any], ctx: Any) -> ToolResult:
        product = _find(str(args.get("product_id") or ""))
        if product is None:
            return ToolResult(ok=False, content="未找到该商品，请先用 catalog_search 检索")
        destination = str(args.get("destination") or "")
        payload = {
            "product_id": product["id"],
            "destination": destination or "未提供",
            "shipping_days": product["shipping_days"],
            "international_shipping": True,
        }
        return ToolResult(ok=True, content=_json(payload), data=payload)

    @registry.tool(
        name="catalog_specs",
        description="查询指定商品的参数与规格",
        parameters={
            "type": "object",
            "properties": {"product_id": {"type": "string", "description": "商品 ID"}},
            "required": ["product_id"],
        },
        scopes=("catalog",),
    )
    async def specs(args: dict[str, Any], ctx: Any) -> ToolResult:
        product = _find(str(args.get("product_id") or ""))
        if product is None:
            return ToolResult(ok=False, content="未找到该商品，请先用 catalog_search 检索")
        payload = {
            "product_id": product["id"],
            "name": product["name"],
            "specs": product["specs"],
        }
        return ToolResult(ok=True, content=_json(payload), data=payload)
