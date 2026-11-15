import pytest

from app.domain.types import InboundMessage, ToolCall
from tests.support import Decision, ScriptedProvider


async def test_quote_records_quantity_without_changing_unit_price(runtime_factory):
    runtime = runtime_factory(
        ScriptedProvider(
            [
                Decision(
                    tool_calls=(
                        ToolCall(
                            "quote", "catalog_quote", {"product_id": "headset-pro", "quantity": 10}
                        ),
                    )
                ),
                Decision(reply="USD 39.00 per unit; no confirmed tier discount"),
            ]
        )
    )
    result = await runtime.service.handle_inbound(InboundMessage("Quote 10 headphones", "quantity"))
    assert result.products[0].price_usd == 39
    assert runtime.session("quantity").quantity == 10
    assert runtime.session("quantity").focused_product_ids == ("headset-pro",)


@pytest.mark.parametrize("with_failed_tool", [False, True])
async def test_keywords_cannot_set_product_state_without_successful_effects(
    runtime_factory, with_failed_tool
):
    decisions = [Decision(reply="Please confirm the product")]
    if with_failed_tool:
        decisions.insert(
            0,
            Decision(tool_calls=(ToolCall("bad", "catalog_quote", {"product_id": "unknown"}),)),
        )
    runtime = runtime_factory(ScriptedProvider(decisions))
    result = await runtime.service.handle_inbound(
        InboundMessage("Please quote the headphones", "no-focus")
    )
    assert result.products == ()
    assert runtime.session("no-focus").focused_product_ids == ()
    if with_failed_tool:
        assert not result.trace.calls[0].ok


@pytest.mark.parametrize(
    "message",
    [
        "¿Envían a España?",
        "Necesito devolver mi pedido",
        "¿Tienen descuento por 10 unidades?",
    ],
)
async def test_spanish_labels_do_not_override_customer_reply_instructions(runtime_factory, message):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Respuesta")]))
    result = await runtime.service.handle_inbound(InboundMessage(message, "spanish"))
    assert result.analysis.language == "es-ES"
    prompt = runtime.provider.calls[0]["messages"][0].content
    assert "Reply in en-US" not in prompt
    assert "Reply in the language of the customer's latest message." in prompt
