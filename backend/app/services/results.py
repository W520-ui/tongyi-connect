from app.domain.types import Product, RunTrace, ToolTraceEntry, WorkflowAnalysis, WorkflowResult


def restore_result(data):
    values = dict(data)
    values["products"] = tuple(
        Product(**{**item, "aliases": tuple(item["aliases"])}) for item in data["products"]
    )
    analysis = dict(data["analysis"])
    analysis["intents"] = tuple(analysis["intents"])
    if analysis["product"]:
        analysis["product"] = Product(
            **{**analysis["product"], "aliases": tuple(analysis["product"]["aliases"])}
        )
    values["analysis"] = WorkflowAnalysis(**analysis)
    values["trace"] = RunTrace(
        tuple(ToolTraceEntry(**entry) for entry in data["trace"]["calls"]),
        data["trace"]["truncated"],
    )
    values["steps"] = tuple(data["steps"])
    return WorkflowResult(**values)
