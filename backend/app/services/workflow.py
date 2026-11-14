"""Cross-border service workflow primitives used by the agent.

The project keeps the business workflow separate from the AstrBot transport:
every request requires a live model reply, while this module supplies intent
analysis, catalog matching, merchant summaries and archive metrics.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Literal
from uuid import uuid4


Intent = Literal["quote", "logistics", "specs", "after_sales", "general"]


PRODUCTS: list[dict[str, Any]] = [
    {
        "id": "headset-pro",
        "name": "星云降噪耳机 Pro",
        "english_name": "Nebula ANC Headphones Pro",
        "category": "3C 数码",
        "price_usd": 39.0,
        "stock": 268,
        "shipping_days": "5–8 个工作日",
        "aliases": ["耳机", "降噪", "headphone", "headphones", "anc"],
        "specs": {
            "续航": "40 小时",
            "蓝牙": "5.3",
            "重量": "248g",
            "颜色": "曜石黑、云雾白",
        },
    },
    {
        "id": "lamp-mini",
        "name": "光屿便携氛围灯",
        "english_name": "Luma Portable Ambient Lamp",
        "category": "家居用品",
        "price_usd": 24.0,
        "stock": 154,
        "shipping_days": "6–10 个工作日",
        "aliases": ["氛围灯", "灯", "lamp", "light"],
        "specs": {
            "续航": "18 小时",
            "充电": "USB-C",
            "重量": "390g",
            "防护": "IPX4",
        },
    },
    {
        "id": "bottle-lite",
        "name": "澄野保温杯 Lite",
        "english_name": "Clearfield Insulated Bottle Lite",
        "category": "生活方式",
        "price_usd": 18.0,
        "stock": 412,
        "shipping_days": "7–12 个工作日",
        "aliases": ["保温杯", "水杯", "bottle", "mug"],
        "specs": {
            "容量": "500ml",
            "材质": "304 不锈钢",
            "保温": "12 小时",
            "重量": "285g",
        },
    },
]

INTENT_LABELS: dict[Intent, str] = {
    "quote": "询价",
    "logistics": "物流查询",
    "specs": "产品参数",
    "after_sales": "售后服务",
    "general": "综合咨询",
}

LANGUAGE_LABELS = {
    "zh-CN": "中文",
    "en-US": "英语",
    "es-ES": "西班牙语",
}


@dataclass(frozen=True)
class WorkflowAnalysis:
    language: str
    intent: Intent
    intents: tuple[Intent, ...]
    confidence: float
    product: dict[str, Any] | None
    needs_human: bool
    handoff_reason: str | None
    product_confidence: float


class WorkflowMetrics:
    """Persist recent demo conversations and aggregate dashboard counters."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(__file__).resolve().parents[2] / "data" / "workflow.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_conversations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                message TEXT NOT NULL,
                reply TEXT NOT NULL,
                merchant_summary TEXT NOT NULL,
                intent TEXT NOT NULL,
                intent_label TEXT NOT NULL,
                detected_intents TEXT NOT NULL,
                product_id TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL,
                language_label TEXT NOT NULL,
                needs_human INTEGER NOT NULL,
                human_acknowledged INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_created_at "
            "ON workflow_conversations(created_at DESC)"
        )
        self._ensure_column("product_id", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("human_acknowledged", "INTEGER NOT NULL DEFAULT 0")
        self.connection.commit()
        self.failed_requests = 0
        self.started_at = datetime.now(timezone.utc)
        self.total = 0
        self.handoffs = 0
        self.intents: Counter[str] = Counter()
        self.languages: Counter[str] = Counter()
        self.records: list[dict[str, Any]] = []
        self._load_existing_metrics()

    def _load_existing_metrics(self) -> None:
        row = self.connection.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(needs_human), 0) AS handoffs "
            "FROM workflow_conversations"
        ).fetchone()
        self.total = int(row["total"])
        self.handoffs = int(row["handoffs"])
        self.intents.clear()
        self.languages.clear()
        for row in self.connection.execute(
            "SELECT intent, detected_intents, language FROM workflow_conversations"
        ):
            try:
                intents = json.loads(row["detected_intents"])
            except (TypeError, json.JSONDecodeError):
                intents = [row["intent"]]
            for intent in set(intents):
                self.intents[str(intent)] += 1
            self.languages[str(row["language"])] += 1
        self.records = self.recent(50)

    def _ensure_column(self, name: str, declaration: str) -> None:
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(workflow_conversations)")}
        if name not in columns:
            self.connection.execute(f"ALTER TABLE workflow_conversations ADD COLUMN {name} {declaration}")
            self.connection.commit()

    def archive(self, *, session_id: str, message: str, answer: dict[str, Any]) -> None:
        """Persist a compact recent-conversation record and update counters."""

        created_at = datetime.now(timezone.utc).isoformat()
        record = {
            "id": str(uuid4()),
            "created_at": created_at,
            "session_id": session_id[:120],
            "message": message.strip()[:180],
            "reply": str(answer.get("reply", ""))[:240],
            "merchant_summary": str(answer.get("merchant_summary", ""))[:240],
            "intent": str(answer.get("intent", "general")),
            "intent_label": str(answer.get("intent_label", "综合咨询")),
            "detected_intents": list(answer.get("detected_intents", [])),
            # Keep the stable catalog id in the archive so a follow-up such as
            # “what is its delivery time?” can reuse the product from the
            # previous turn. Older records may not have this field, so the
            # archive remains backwards compatible with an empty value.
            "product_id": str(
                answer.get("product_id")
                or (
                    answer.get("matched_products", [{}])[0].get("id", "")
                    if answer.get("matched_products")
                    else ""
                )
                or ""
            ),
            "language": str(answer.get("language", "zh-CN")),
            "language_label": str(answer.get("language_label", "中文")),
            "needs_human": bool(answer.get("needs_human")),
            "human_acknowledged": False,
        }
        self.connection.execute(
            """
            INSERT INTO workflow_conversations (
                id, created_at, session_id, message, reply, merchant_summary,
                intent, intent_label, detected_intents, product_id, language,
                language_label, needs_human, human_acknowledged
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"], record["created_at"], record["session_id"],
                record["message"], record["reply"], record["merchant_summary"],
                record["intent"], record["intent_label"],
                json.dumps(record["detected_intents"], ensure_ascii=False),
                record["product_id"],
                record["language"], record["language_label"],
                int(record["needs_human"]),
                int(record["human_acknowledged"]),
            ),
        )
        self.connection.commit()
        self.records.insert(0, self._public_record(record))
        del self.records[50:]
        self._load_existing_metrics()

    @staticmethod
    def _public_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            **{
                key: record[key]
                for key in (
                "id", "created_at", "session_id", "message", "reply",
                "merchant_summary", "intent_label", "language_label", "needs_human",
                "human_acknowledged",
                )
            },
            "needs_human": bool(record["needs_human"]),
            "human_acknowledged": bool(record.get("human_acknowledged", 0)),
        }

    @classmethod
    def _row_to_record(cls, row: sqlite3.Row) -> dict[str, Any]:
        record = cls._public_record(dict(row))
        record["human_acknowledged"] = bool(record.get("human_acknowledged", False))
        return record

    def recent(self, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM workflow_conversations ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 20)),),
        )
        return [self._row_to_record(row) for row in rows]

    def recent_archive(self, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM workflow_conversations ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 20)),),
        )
        return [
            {
                **self._row_to_record(row),
                "handoff_reason": "售后、退款或质量问题需要人工核实"
                if row["needs_human"]
                else None,
            }
            for row in rows
        ]

    def recent_handoffs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM workflow_conversations "
            "WHERE needs_human = 1 AND human_acknowledged = 0 "
            "ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 50)),),
        )
        return [
            {
                **self._row_to_record(row),
                "handoff_reason": "售后、退款或质量问题需要人工核实",
            }
            for row in rows
        ]

    def last_product_id(self, session_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT product_id FROM workflow_conversations "
            "WHERE session_id = ? AND product_id != '' ORDER BY created_at DESC LIMIT 1",
            (session_id[:120],),
        ).fetchone()
        return str(row["product_id"]) if row else None

    def acknowledge_handoff(self, record_id: str) -> bool:
        cursor = self.connection.execute(
            "UPDATE workflow_conversations SET human_acknowledged = 1 "
            "WHERE id = ? AND needs_human = 1 AND human_acknowledged = 0",
            (record_id,),
        )
        self.connection.commit()
        if cursor.rowcount:
            self._load_existing_metrics()
            return True
        return False

    def record_failed_request(self) -> None:
        self.failed_requests += 1

    def close(self) -> None:
        self.connection.close()

    def snapshot(self) -> dict[str, Any]:
        resolved = max(self.total - self.handoffs, 0)
        return {
            "total_conversations": self.total,
            "failed_requests": self.failed_requests,
            "human_handoffs": self.handoffs,
            "pending_handoffs": int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM workflow_conversations "
                    "WHERE needs_human = 1 AND human_acknowledged = 0"
                ).fetchone()[0]
            ),
            "resolution_rate": round(resolved / self.total * 100, 1) if self.total else 100.0,
            "top_intent": (
                INTENT_LABELS.get(self.intents.most_common(1)[0][0], "综合咨询")
                if self.intents
                else "暂无数据"
            ),
            "languages": [
                {"code": code, "label": LANGUAGE_LABELS.get(code, code), "count": count}
                for code, count in self.languages.most_common()
            ],
            "intents": [
                {
                    "code": code,
                    "label": INTENT_LABELS.get(code, code),
                    "count": count,
                }
                for code, count in self.intents.most_common()
            ],
            "started_at": self.started_at.isoformat(),
        }


metrics = WorkflowMetrics()


def list_products() -> list[dict[str, Any]]:
    """Return catalog data safe for the browser and model context."""

    return [
        {
            key: value
            for key, value in product.items()
            if key not in {"aliases"}
        }
        for product in PRODUCTS
    ]


def analyze_message(message: str, product_hint: str | None = None) -> WorkflowAnalysis:
    normalized = message.strip().lower()
    language = _detect_language(message)
    intent, confidence = _detect_intent(normalized)
    intents = tuple(_detect_all_intents(normalized))
    product = _match_product(normalized)
    product_confidence = 0.96 if product else 0.0
    if product is None and product_hint:
        product = next((item for item in PRODUCTS if item["id"] == product_hint), None)
        if product:
            product_confidence = 0.72

    needs_human = intent == "after_sales"
    handoff_reason = "涉及退款、退货或质量问题，建议人工确认" if needs_human else None
    if intent == "general" and not product:
        confidence = min(confidence, 0.65)

    return WorkflowAnalysis(
        language=language,
        intent=intent,
        intents=intents or (intent,),
        confidence=confidence,
        product=product,
        needs_human=needs_human,
        handoff_reason=handoff_reason,
        product_confidence=product_confidence,
    )


def build_workflow_answer(
    message: str,
    analysis: WorkflowAnalysis,
    *,
    reply: str,
    source: Literal["astrbot", "astrbot+human-handoff"] = "astrbot",
) -> dict[str, Any]:
    final_reply = reply.strip()
    product_name = analysis.product["name"] if analysis.product else "未匹配具体商品"
    summary = _merchant_summary(message, analysis)
    intent_labels = [INTENT_LABELS[item] for item in analysis.intents]
    steps = [
        f"识别语言：{LANGUAGE_LABELS.get(analysis.language, analysis.language)}",
        f"识别意图：{'、'.join(intent_labels)}",
        "检索商品资料" if analysis.product else "等待商家补充商品信息",
        "生成对客回复",
        "推送商家摘要并归档",
    ]
    if analysis.needs_human:
        steps.append("触发人工接管提醒")

    answer: dict[str, Any] = {
        "reply": final_reply,
        "merchant_summary": summary,
        "intent": analysis.intent,
        "intent_label": INTENT_LABELS[analysis.intent],
        "detected_intents": list(analysis.intents),
        "detected_intent_labels": intent_labels,
        "task_plan": _task_plan(analysis),
        "language": analysis.language,
        "language_label": LANGUAGE_LABELS.get(analysis.language, analysis.language),
        "confidence": analysis.confidence,
        "product_confidence": analysis.product_confidence,
        "matched_product": product_name,
        "product_id": analysis.product["id"] if analysis.product else None,
        "matched_products": [
            {key: value for key, value in analysis.product.items() if key != "aliases"}
        ] if analysis.product else [],
        "needs_human": analysis.needs_human,
        "handoff_reason": analysis.handoff_reason,
        "steps": steps,
        "source": source,
    }
    return answer


def _detect_language(message: str) -> str:
    lower = message.lower()
    if any(token in lower for token in ("用英文", "英语", "english", "in english")):
        return "en-US"
    if any(token in lower for token in ("西班牙语", "español", "in spanish", "en español")):
        return "es-ES"
    if re.search(r"[\u4e00-\u9fff]", message):
        return "zh-CN"
    if any(
        token in lower
        for token in (
            "qué ", "precio", "cuánto", "cuanto", "envío", "entrega",
            "hola", "por favor", "gracias", "puede enviar",
        )
    ):
        return "es-ES"
    return "en-US"


def _detect_intent(message: str) -> tuple[Intent, float]:
    rules: list[tuple[Intent, tuple[str, ...], float]] = [
        ("after_sales", ("售后", "退款", "退货", "换货", "投诉", "坏了", "refund", "return", "warranty", "damaged", "complaint"), 0.97),
        ("logistics", ("物流", "快递", "运费", "发货", "发往", "寄到", "寄往", "送到", "配送", "邮寄", "到货", "shipping", "delivery", "tracking", "ship to", "arrive", "enviar"), 0.94),
        ("quote", ("价格", "多少钱", "报价", "批发", "折扣", "price", "cost", "quote", "discount", "how much"), 0.93),
        ("specs", ("参数", "规格", "尺寸", "重量", "材质", "续航", "spec", "size", "weight", "material", "battery"), 0.9),
    ]
    for intent, keywords, confidence in rules:
        if any(keyword in message for keyword in keywords):
            return intent, confidence
    return "general", 0.72


def _detect_all_intents(message: str) -> list[Intent]:
    rules: list[tuple[Intent, tuple[str, ...]]] = [
        ("after_sales", ("售后", "退款", "退货", "换货", "投诉", "坏了", "refund", "return", "warranty", "damaged", "complaint")),
        ("logistics", ("物流", "快递", "运费", "发货", "发往", "寄到", "寄往", "送到", "配送", "邮寄", "到货", "shipping", "delivery", "tracking", "ship to", "arrive", "enviar")),
        ("quote", ("价格", "多少钱", "报价", "批发", "折扣", "price", "cost", "quote", "discount", "how much")),
        ("specs", ("参数", "规格", "尺寸", "重量", "材质", "续航", "spec", "size", "weight", "material", "battery")),
    ]
    detected = [intent for intent, keywords in rules if any(keyword in message for keyword in keywords)]
    return detected or ["general"]


def _task_plan(analysis: WorkflowAnalysis) -> list[str]:
    plan: list[str] = []
    if analysis.product:
        plan.append("从商品资料库匹配商品")
    if "quote" in analysis.intents:
        plan.append("整理价格与数量信息")
    if "logistics" in analysis.intents:
        plan.append("核对目的地与配送时效")
    if "specs" in analysis.intents:
        plan.append("提取产品参数")
    if "after_sales" in analysis.intents:
        plan.append("记录售后诉求并检查人工接管")
    if not plan:
        plan.append("澄清客户需求并推荐下一步")
    plan.append("生成对客多语言回复和商家中文摘要")
    return plan


def _match_product(message: str) -> dict[str, Any] | None:
    for product in PRODUCTS:
        if product["name"].lower() in message or product["english_name"].lower() in message:
            return product
        if any(alias in message for alias in product["aliases"]):
            return product
    return None


def _merchant_summary(message: str, analysis: WorkflowAnalysis) -> str:
    product = analysis.product
    product_info = product["name"] if product else "未识别商品"
    handoff = "需要人工接管" if analysis.needs_human else "可由智能体继续处理"
    return (
        f"客户语言：{LANGUAGE_LABELS.get(analysis.language, analysis.language)}；"
        f"意图：{INTENT_LABELS[analysis.intent]}；商品：{product_info}；"
        f"处理建议：{handoff}。原始咨询：{message.strip()}"
    )
