import json
import math
from dataclasses import dataclass

from app.agent.tools.deps import CatalogPort
from app.domain.types import InboundMessage, Message, Session


def estimate_tokens(message: Message) -> int:
    text = message.content + json.dumps(message.tool_calls, ensure_ascii=False)
    return math.ceil(len(text.encode("utf-8")) / 4) + 4


def history_groups(turns, tool_result_max_chars):
    groups = []
    for turn in turns:
        role = "assistant" if turn.role == "human_agent" else turn.role
        content = turn.content
        if role == "tool" and len(content) > tool_result_max_chars:
            marker = "\n[tool result truncated]"
            content = content[: max(0, tool_result_max_chars - len(marker))] + marker
        message = Message(role, content, turn.tool_calls, turn.tool_call_id, turn.name)
        if role == "tool":
            if groups and groups[-1][0].tool_calls:
                groups[-1].append(message)
        else:
            groups.append([message])
    return [
        group
        for group in groups
        if not group[0].tool_calls
        or (
            {call["id"] for call in group[0].tool_calls}
            == {message.tool_call_id for message in group[1:]}
            and len(group[0].tool_calls) == len(group) - 1
        )
    ]


@dataclass(frozen=True)
class BuiltContext:
    messages: tuple[Message, ...]
    omitted: tuple[Message, ...]


class ContextBuilder:
    def __init__(
        self,
        template: str,
        catalog: CatalogPort,
        token_budget: int = 8192,
        tool_result_max_chars: int = 2000,
    ) -> None:
        self.template, self.catalog = template, catalog
        self.token_budget, self.tool_result_max_chars = token_budget, tool_result_max_chars

    async def build_details(self, inbound: InboundMessage, session: Session) -> BuiltContext:
        products = []
        for product_id in session.focused_product_ids:
            product = await self.catalog.get(product_id)
            if product:
                products.append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "english_name": product.english_name,
                        "price_usd": product.price_usd,
                        "stock": product.stock,
                        "shipping_days": product.shipping_days,
                        "specs": product.specs,
                    }
                )
        state = {
            "focused_products": products,
            "destination_country": session.destination_country,
            "quantity": session.quantity,
            "reply_language": session.reply_language,
            "handoff_status": session.status,
        }
        instruction = (
            f"Reply in {session.reply_language}."
            if session.reply_language
            else "Reply in the language of the customer's latest message."
        )
        system = (
            self.template
            + "\n\nConversation state:\n"
            + json.dumps(state, ensure_ascii=False)
            + "\n"
            + instruction
        )
        if session.summary:
            system += "\n\nEarlier conversation summary:\n" + session.summary
        system_message = Message("system", system)
        latest = Message("user", inbound.message)
        remaining = self.token_budget - estimate_tokens(system_message) - estimate_tokens(latest)
        groups = history_groups(session.turns, self.tool_result_max_chars)
        retained = []
        first = len(groups)
        for index in range(len(groups) - 1, -1, -1):
            cost = sum(estimate_tokens(message) for message in groups[index])
            if cost > remaining:
                break
            remaining -= cost
            retained = groups[index] + retained
            first = index
        return BuiltContext(
            (system_message, *retained, latest),
            tuple(message for group in groups[:first] for message in group),
        )

    async def build(
        self, inbound: InboundMessage, session: Session, language=None
    ) -> tuple[Message, ...]:
        return (await self.build_details(inbound, session)).messages
