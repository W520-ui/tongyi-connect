from app.agent.tools.deps import CatalogPort
from app.domain.types import InboundMessage, Message, Session


class ContextBuilder:
    def __init__(self, template: str, catalog: CatalogPort, max_history_turns: int = 10) -> None:
        self.template = template
        self.catalog = catalog
        self.max_history_turns = max_history_turns

    async def build(
        self, inbound: InboundMessage, session: Session, language: str
    ) -> tuple[Message, ...]:
        lines = ["Conversation state:"]
        for product_id in session.focused_product_ids:
            product = await self.catalog.get(product_id)
            if product:
                lines.append(
                    f"Focused product: {product.name} ({product.english_name}), id={product.id}"
                )
        lines.append(f"Destination country: {session.destination_country or 'unset'}")
        lines.append(f"Quantity: {session.quantity or 'unset'}")
        if session.reply_language:
            lines.append(f"Reply in {session.reply_language}.")
        else:
            lines.append("Reply in the language of the customer's latest message.")
        groups: list[list[Message]] = []
        for turn in session.turns:
            message = Message(
                turn.role, turn.content, turn.tool_calls, turn.tool_call_id, turn.name
            )
            if message.role == "tool" and groups and groups[-1][0].tool_calls:
                groups[-1].append(message)
            else:
                groups.append([message])
        history: list[Message] = []
        for group in reversed(groups):
            if len(history) + len(group) > self.max_history_turns:
                break
            history = group + history
        return (
            Message(role="system", content=self.template + "\n\n" + "\n".join(lines)),
            *history,
            Message(role="user", content=inbound.message),
        )
