from dataclasses import replace

from app.domain.types import RunTrace, ToolTraceEntry
from app.scripts.eval_agent import load_cases, score_case
from tests.support import Decision, ScriptedProvider


async def test_evaluation_uses_successful_tools_and_observable_facts(runtime_factory):
    from app.domain.types import InboundMessage

    cases = load_cases()
    assert len(cases) == 30
    case = next(case for case in cases if case["id"] == "quote-headphones-en")
    runtime = runtime_factory(ScriptedProvider([Decision(reply="The price is USD 39.00.")]))
    result = await runtime.service.handle_inbound(InboundMessage("Hello", "eval"))
    snapshot = runtime.session("eval")
    failed = ToolTraceEntry(
        "quote", 0, "catalog_quote", {"product_id": "headset-pro"}, False, 1, "failure"
    )
    checks = score_case(case, [replace(result, trace=RunTrace((failed,)))], snapshot)
    assert not all(check["ok"] for check in checks)
    checks = score_case(
        case, [replace(result, trace=RunTrace((replace(failed, ok=True, error=None),)))], snapshot
    )
    assert all(check["ok"] for check in checks)
