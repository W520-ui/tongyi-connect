import pytest

from app.domain.types import InboundMessage
from tests.support import Decision, ScriptedProvider


@pytest.mark.parametrize(
    "message",
    [
        "¿Envían a España?",
        "Necesito devolver mi pedido",
        "¿Tienen descuento por 10 unidades?",
    ],
)
async def test_latest_customer_language_is_not_overridden_by_keyword_guess(
    runtime_factory, message
):
    provider = ScriptedProvider([Decision(reply="Respuesta en español.")])
    runtime = runtime_factory(provider)
    await runtime.service.handle_inbound(InboundMessage(message, "language-regression"))
    prompt = provider.calls[0]["messages"][0].content
    assert "Reply in en-US" not in prompt
    assert "reply in the language of the customer's latest message" in prompt.lower()
    assert provider.calls[0]["messages"][-1].content == message


async def test_explicit_language_preference_still_controls_reply(runtime_factory):
    provider = ScriptedProvider([Decision(reply="Respuesta en español.")])
    runtime = runtime_factory(provider)
    await runtime.service.handle_inbound(InboundMessage("/lang es-ES", "language-regression"))
    await runtime.service.handle_inbound(InboundMessage("Hello", "language-regression"))
    assert "Reply in es-ES." in provider.calls[0]["messages"][0].content
    assert "Reply in en-US" not in provider.calls[0]["messages"][0].content
