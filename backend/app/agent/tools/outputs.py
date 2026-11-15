import json
from dataclasses import asdict
from typing import Any

from app.agent.effects import Effect
from app.agent.tools.base import ToolOutput
from app.domain.types import Product


def product_data(product: Product) -> dict[str, Any]:
    data = asdict(product)
    data.pop("aliases")
    return data


def output(data: dict[str, Any], *, effects: tuple[Effect, ...] = ()) -> ToolOutput:
    return ToolOutput(json.dumps(data, ensure_ascii=False), effects=effects)


def error_output(code: str, message: str) -> ToolOutput:
    return ToolOutput(
        json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False),
        ok=False,
    )
