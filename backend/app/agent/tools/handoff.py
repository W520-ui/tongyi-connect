from pydantic import BaseModel, ConfigDict, Field

from app.agent.effects import Effect, FocusProducts, RequestHandoff
from app.agent.tools.base import FunctionTool, ToolOutput
from app.agent.tools.deps import ToolDeps
from app.agent.tools.outputs import output


class HandoffArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    issue: str = Field(min_length=1)
    product_id: str | None = None


async def record(args: HandoffArgs, deps: ToolDeps) -> ToolOutput:
    effects: tuple[Effect, ...] = (
        RequestHandoff("after_sales", "售后、退款或质量问题需要人工核实", args.issue),
    )
    if args.product_id and await deps.catalog.get(args.product_id):
        effects += (FocusProducts((args.product_id,)),)
    return output(
        {
            "registered": True,
            "issue": args.issue,
            "product_id": args.product_id,
            "next_step": "商家在工作台的人工接管队列中确认",
        },
        effects=effects,
    )


def handoff_tool(timeout: float) -> FunctionTool:
    return FunctionTool(
        "after_sales_record",
        "Record an after-sales issue and request merchant handoff",
        HandoffArgs,
        record,
        timeout,
    )
