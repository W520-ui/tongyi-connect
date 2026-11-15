"""Run the source-controlled evaluation cases against the configured real model."""

import argparse
import asyncio
import json
import re
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError
from app.domain.countries import COUNTRY_CODES
from app.domain.types import InboundMessage
from app.main import create_app

EVAL_ROOT = Path(__file__).absolute().parents[2] / "evals"


def load_cases(path=EVAL_ROOT / "cases.json"):
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not 20 <= len(cases) <= 50 or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Expected 20-50 uniquely identified evaluation cases")
    for case in cases:
        if not case["messages"] or not all(
            isinstance(message, str) and message.strip() for message in case["messages"]
        ):
            raise ValueError("Each case requires nonempty messages")
        for pattern in (*case["reply_patterns"], *case["forbidden_patterns"]):
            re.compile(pattern)
    return cases


def score_case(case, results, snapshot):
    final = results[-1]
    trace = [entry for result in results for entry in result.trace.calls]
    checks = []

    def check(name, condition):
        checks.append({"name": name, "ok": bool(condition)})

    for name in case["required_tools"]:
        check("tool:" + name, any(entry.name == name and entry.ok for entry in trace))
    for expected in case["expected_arguments"]:
        check(
            "arguments:" + json.dumps(expected, ensure_ascii=False),
            any(
                entry.ok
                and entry.name == expected["name"]
                and all(
                    entry.args.get(key) == value for key, value in expected.items() if key != "name"
                )
                for entry in trace
            ),
        )
    for pattern in case["reply_patterns"]:
        check("reply:" + pattern, re.search(pattern, final.reply, re.IGNORECASE) is not None)
    for pattern in case["forbidden_patterns"]:
        check("forbidden:" + pattern, re.search(pattern, final.reply, re.IGNORECASE) is None)
    if case["expected_handoff"] is not None:
        check("handoff", final.needs_human is case["expected_handoff"])
    for name, value in case["expected_slots"].items():
        check("slot:" + name, getattr(snapshot, name) == value)
    for entry in trace:
        if entry.name == "catalog_shipping" and entry.args.get("destination") not in COUNTRY_CODES:
            check("invalid_country_is_a_tool_failure", not entry.ok and bool(entry.error))
    return checks


async def evaluate(settings, cases):
    if not settings.is_configured:
        raise AppError("LLM_NOT_CONFIGURED")
    records = []
    with tempfile.TemporaryDirectory(prefix="tongyi-real-model-eval-") as temporary:
        isolated = settings.model_copy(
            update={
                "database_url": "sqlite+aiosqlite:///" + str(Path(temporary) / "eval.db"),
                "summary_enabled": False,
            }
        )
        app = create_app(isolated)
        async with app.router.lifespan_context(app):
            for case in cases:
                results = []
                try:
                    for message in case["messages"]:
                        results.append(
                            await app.state.conversation_service.handle_inbound(
                                InboundMessage(message, "eval-" + case["id"])
                            )
                        )
                    snapshot = await app.state.conversations.get(results[-1].session_id)
                    checks = score_case(case, results, snapshot)
                    records.append(
                        {
                            "id": case["id"],
                            "passed": all(check["ok"] for check in checks),
                            "checks": checks,
                            "reply": results[-1].reply,
                            "merchant_summary": results[-1].merchant_summary,
                            "analysis_source": results[-1].analysis_source,
                            "trace": [
                                asdict(entry) for result in results for entry in result.trace.calls
                            ],
                        }
                    )
                except AppError as error:
                    records.append({"id": case["id"], "passed": False, "error_code": error.code})
    passed = sum(record["passed"] for record in records)
    return {
        "model": settings.llm_model,
        "analysis_enabled": settings.analysis_enabled,
        "passed": passed,
        "total": len(records),
        "pass_rate": round(passed / len(records) * 100, 1),
        "cases": records,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the configured real model without touching demo data"
    )
    parser.add_argument(
        "--case", action="append", dest="case_ids", help="Run only a selected case ID; repeatable"
    )
    parser.add_argument(
        "--list", action="store_true", help="List cases without constructing application resources"
    )
    parser.add_argument("--output", type=Path, default=EVAL_ROOT / "results" / "latest.json")
    args = parser.parse_args()
    cases = load_cases()
    if args.list:
        for case in cases:
            print(case["id"])
        return
    if args.case_ids:
        available = {case["id"] for case in cases}
        if unknown := set(args.case_ids) - available:
            parser.error("Unknown case IDs: " + ", ".join(sorted(unknown)))
        cases = [case for case in cases if case["id"] in args.case_ids]
    try:
        report = asyncio.run(evaluate(Settings(), cases))
    except AppError as error:
        parser.exit(2, error.message + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{report['passed']}/{report['total']} passed ({report['pass_rate']}%): {args.output}")


if __name__ == "__main__":
    main()
