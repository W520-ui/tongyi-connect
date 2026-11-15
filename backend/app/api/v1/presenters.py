from app.api.v1.schemas.agent import AgentWorkflowData, ProductSchema, ToolTraceSchema
from app.domain.types import INTENT_LABELS, LANGUAGE_LABELS, WorkflowResult


def present_workflow(result: WorkflowResult) -> AgentWorkflowData:
    analysis = result.analysis
    plan = []
    if result.products:
        plan.append("从商品资料库匹配商品")
    for intent, label in (
        ("quote", "整理价格与数量信息"),
        ("logistics", "核对目的地与配送时效"),
        ("specs", "提取产品参数"),
        ("after_sales", "记录售后诉求并检查人工接管"),
    ):
        if intent in analysis.intents:
            plan.append(label)
    if not plan:
        plan.append("澄清客户需求并推荐下一步")
    plan.append("生成对客多语言回复和商家中文摘要")
    product = result.products[0] if result.products else None
    return AgentWorkflowData(
        reply=result.reply,
        merchant_summary=result.merchant_summary,
        intent=analysis.intent,
        intent_label=INTENT_LABELS[analysis.intent],
        detected_intents=list(analysis.intents),
        detected_intent_labels=[INTENT_LABELS[intent] for intent in analysis.intents],
        task_plan=plan,
        language=analysis.language,
        language_label=LANGUAGE_LABELS[analysis.language],
        confidence=analysis.confidence,
        product_confidence=analysis.product_confidence,
        matched_product=product.name if product else "未匹配具体商品",
        product_id=product.id if product else None,
        matched_products=[ProductSchema.model_validate(item) for item in result.products],
        needs_human=result.needs_human,
        handoff_reason=result.handoff_reason,
        steps=list(result.steps),
        source=result.source,
        session_id=result.session_id,
        trace=[ToolTraceSchema.model_validate(entry) for entry in result.trace.calls],
        conversation_id=result.session_id,
        message_id=result.message_id,
        client_message_id=result.client_message_id,
        run_id=result.run_id,
        replayed=result.replayed,
        conversation_status=result.conversation_status,
        analysis_source=result.analysis_source,
    )
