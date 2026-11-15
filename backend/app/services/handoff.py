from contextlib import nullcontext
from uuid import uuid4

from sqlalchemy import select, update

from app.agent.effects import RequestHandoff
from app.core.db import Database
from app.core.errors import AppError
from app.domain.types import INTENT_LABELS, LANGUAGE_LABELS
from app.repositories.analytics import AnalyticsRepository
from app.repositories.conversations import (
    ConversationRepository,
    empty_state,
    new_conversation,
    now,
    session_value,
)
from app.repositories.models import Conversation, ConversationAlias, HandoffTicket


class HandoffService:
    def __init__(
        self, database: Database, conversations: ConversationRepository, merchant_id="demo"
    ):
        self.database, self.conversations, self.merchant_id = database, conversations, merchant_id

    async def pending(self, limit=20):
        return await AnalyticsRepository(self.database, self.merchant_id).pending(limit)

    async def get(self, ticket_id):
        async with self.database.sessions() as transaction:
            ticket = await transaction.get(HandoffTicket, ticket_id)
            if ticket is None or ticket.merchant_id != self.merchant_id:
                raise AppError("HANDOFF_NOT_FOUND")
            return ticket

    async def list_tickets(self, statuses, limit=20):
        async with self.database.sessions() as transaction:
            return (
                await transaction.scalars(
                    select(HandoffTicket)
                    .where(
                        HandoffTicket.merchant_id == self.merchant_id,
                        HandoffTicket.status.in_(statuses),
                    )
                    .order_by(HandoffTicket.created_at.desc(), HandoffTicket.id.desc())
                    .limit(limit)
                )
            ).all()

    async def pending_for(self, conversation_id, transaction=None):
        if transaction is None:
            async with self.database.sessions() as transaction:
                return await self.pending_for(conversation_id, transaction)
        return await transaction.scalar(
            select(HandoffTicket).where(
                HandoffTicket.conversation_id == conversation_id,
                HandoffTicket.merchant_id == self.merchant_id,
                HandoffTicket.status.in_(("open", "acknowledged")),
            )
        )

    async def request(
        self, transaction, snapshot, effect: RequestHandoff, trigger_id, message, analysis
    ):
        existing = await self.pending_for(snapshot.session_id, transaction)
        if existing:
            return existing
        ticket = HandoffTicket(
            id=str(uuid4()),
            merchant_id=self.merchant_id,
            conversation_id=snapshot.session_id,
            trigger_message_id=trigger_id,
            reason_code=effect.reason_code,
            reason_text=effect.reason_text,
            issue_summary=effect.issue_summary,
            status="open",
            created_at=now(),
            customer_message=message[:500],
            language_label=LANGUAGE_LABELS[analysis.language],
            intent_label=INTENT_LABELS[analysis.intent],
        )
        transaction.add(ticket)
        await transaction.flush()
        return ticket

    async def change(self, ticket_id, *, resolve=False):
        async with self.database.transaction() as transaction:
            ticket = await transaction.get(HandoffTicket, ticket_id)
            if ticket is None or ticket.merchant_id != self.merchant_id:
                raise AppError("HANDOFF_NOT_FOUND")
            if ticket.status not in (("open", "acknowledged") if resolve else ("open",)):
                raise AppError("INVALID_STATE")
            row = await transaction.get(Conversation, ticket.conversation_id)
            snapshot = session_value(row)
            await self.conversations.update(
                transaction, snapshot, status="resolved" if resolve else "human_active"
            )
            if resolve:
                ticket.status, ticket.resolved_at = "resolved", now()
            else:
                ticket.status, ticket.acknowledged_at = "acknowledged", now()
            await transaction.flush()
            return ticket

    async def acknowledge(self, ticket_id):
        try:
            await self.change(ticket_id)
            return True
        except AppError as error:
            if error.code in ("HANDOFF_NOT_FOUND", "INVALID_STATE"):
                return False
            raise

    async def resolve(self, ticket_id):
        return await self.change(ticket_id, resolve=True)

    async def reset(self, snapshot, transaction=None):
        replacement = new_conversation(self.merchant_id)
        async with (
            self.database.transaction()
            if transaction is None
            else nullcontext(transaction) as transaction
        ):
            await self.conversations.update(
                transaction, snapshot, status="resolved", state=empty_state(), reply_language=None
            )
            await transaction.execute(
                update(HandoffTicket)
                .where(
                    HandoffTicket.conversation_id == snapshot.session_id,
                    HandoffTicket.merchant_id == self.merchant_id,
                    HandoffTicket.status.in_(("open", "acknowledged")),
                )
                .values(status="resolved", resolved_at=now())
            )
            transaction.add(replacement)
            await transaction.flush()
            await transaction.execute(
                update(ConversationAlias)
                .where(
                    ConversationAlias.conversation_id == snapshot.session_id,
                    ConversationAlias.merchant_id == self.merchant_id,
                )
                .values(conversation_id=replacement.id)
            )
            alias = await transaction.get(
                ConversationAlias, (self.merchant_id, snapshot.session_id)
            )
            if alias is None:
                transaction.add(
                    ConversationAlias(
                        merchant_id=self.merchant_id,
                        alias=snapshot.session_id,
                        conversation_id=replacement.id,
                    )
                )
            else:
                alias.conversation_id = replacement.id
        return session_value(replacement)
