"""Conservative keyword fallback; no model context or I/O lives here."""

import re

from app.domain.types import Intent, Language, Product, WorkflowAnalysis

# Every Latin spelling is explicit; substring stems such as "return" are forbidden.
INTENT_RULES: tuple[tuple[Intent, tuple[str, ...], float], ...] = (
    (
        "after_sales",
        (
            "售后",
            "退款",
            "退货",
            "换货",
            "投诉",
            "坏了",
            "无法开机",
            "refund",
            "refunds",
            "return",
            "returns",
            "warranty",
            "damaged",
            "complaint",
            "complaints",
        ),
        0.97,
    ),
    (
        "logistics",
        (
            "物流",
            "快递",
            "运费",
            "发货",
            "发往",
            "寄到",
            "寄往",
            "送到",
            "配送",
            "邮寄",
            "到货",
            "shipping",
            "delivery",
            "tracking",
            "ship to",
            "arrive",
            "arrives",
            "enviar",
            "envío",
            "entrega",
        ),
        0.94,
    ),
    (
        "quote",
        (
            "价格",
            "多少钱",
            "报价",
            "批发",
            "折扣",
            "price",
            "prices",
            "cost",
            "costs",
            "quote",
            "quotes",
            "discount",
            "discounts",
            "how much",
            "precio",
        ),
        0.93,
    ),
    (
        "specs",
        (
            "参数",
            "规格",
            "尺寸",
            "重量",
            "材质",
            "续航",
            "spec",
            "specs",
            "specifications",
            "size",
            "sizes",
            "weight",
            "material",
            "materials",
            "battery",
        ),
        0.9,
    ),
)
LANGUAGE_PHRASES: dict[Language, tuple[str, ...]] = {
    "en-US": ("用英文回复", "用英文回答", "用英语回复", "用英语回答", "in english"),
    "es-ES": ("用西班牙语回复", "用西班牙语回答", "in spanish", "en español"),
    "zh-CN": ("用中文回复", "用中文回答", "in chinese"),
}


def matches(text: str, keyword: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", keyword):
        return keyword in text
    return re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", text, re.IGNORECASE) is not None


def requested_language(message: str) -> Language | None:
    return next(
        (
            language
            for language, phrases in LANGUAGE_PHRASES.items()
            if any(matches(message, phrase) for phrase in phrases)
        ),
        None,
    )


def detect_language(message: str) -> Language:
    if re.search(r"[\u4e00-\u9fff]", message):
        return "zh-CN"
    if any(
        matches(message, word)
        for word in (
            "qué",
            "precio",
            "cuánto",
            "cuanto",
            "envío",
            "entrega",
            "hola",
            "por favor",
            "gracias",
            "puede enviar",
            "auriculares",
        )
    ):
        return "es-ES"
    return "en-US"


def analyze_message(
    message: str, products: tuple[Product, ...] = (), product_hint: str | None = None
) -> WorkflowAnalysis:
    text = message.strip().lower()
    requested = requested_language(text)
    detected = detect_language(message)
    hit_rules = [
        (intent, confidence)
        for intent, keywords, confidence in INTENT_RULES
        if any(matches(text, keyword) for keyword in keywords)
    ]
    intent, confidence = hit_rules[0] if hit_rules else ("general", 0.72)
    product = next(
        (
            item
            for item in products
            if any(
                matches(text, keyword)
                for keyword in (
                    item.name.lower(),
                    item.english_name.lower(),
                    *item.aliases,
                )
            )
        ),
        None,
    )
    product_confidence = 0.96 if product else 0.0
    if product is None and product_hint:
        product = next((item for item in products if item.id == product_hint), None)
        product_confidence = 0.72 if product else 0.0
    needs_human = intent == "after_sales"
    return WorkflowAnalysis(
        language=requested or detected,
        intent=intent,
        intents=tuple(item[0] for item in hit_rules) or ("general",),
        confidence=min(confidence, 0.65) if intent == "general" and not product else confidence,
        product=product,
        needs_human=needs_human,
        handoff_reason="涉及退款、退货或质量问题，建议人工确认" if needs_human else None,
        product_confidence=product_confidence,
        detected_language=detected,
        requested_language=requested,
    )
