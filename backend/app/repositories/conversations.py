from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.db import Database
from app.core.errors import AppError
from app.domain.types import Session, Turn
from app.repositories.models import Conversation, ConversationAlias, StoredMessage


def now():
    return datetime.now(UTC).isoformat()


def empty_state():
    return {"focused_product_ids": [], "destination_country": None, "quantity": None}


def new_conversation(merchant_id, reply_language=None):
    timestamp = now()
    return Conversation(
        id=str(uuid4()),
        merchant_id=merchant_id,
        channel="web_demo",
        status="bot_active",
        state=empty_state(),
        reply_language=reply_language,
        version=1,
        created_at=timestamp,
        updated_at=timestamp,
    )


def session_value(row, turns=()):
    return Session(
        session_id=row.id,
        turns=list(turns),
        focused_product_ids=tuple(row.state.get("focused_product_ids", ())),
        destination_country=row.state.get("destination_country"),
        quantity=row.state.get("quantity"),
        reply_language=row.reply_language,
        status=row.status,
        summary=row.summary,
        version=row.version,
        merchant_id=row.merchant_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_message_at=row.last_message_at,
    )


class ConversationRepository:
    def __init__(self, database: Database, merchant_id="demo"):
        self.database, self.merchant_id = database, merchant_id

    async def create(self, reply_language=None):
        row = new_conversation(self.merchant_id, reply_language)
        async with self.database.transaction() as transaction:
            transaction.add(row)
        return session_value(row)

    async def resolve(self, key=None, *, create=True):
        if not key:
            return await self.create()
        key = key[:120]
        async with self.database.sessions() as transaction:
            alias = await transaction.get(ConversationAlias, (self.merchant_id, key))
            row = await transaction.get(Conversation, alias.conversation_id if alias else key)
            if row and row.merchant_id == self.merchant_id:
                return session_value(row)
        if not create:
            raise AppError("CONVERSATION_NOT_FOUND")
        row = new_conversation(self.merchant_id)
        try:
            async with self.database.transaction() as transaction:
                transaction.add(row)
                await transaction.flush()
                transaction.add(
                    ConversationAlias(
                        merchant_id=self.merchant_id, alias=key, conversation_id=row.id
                    )
                )
        except IntegrityError:
            return await self.resolve(key, create=False)
        return session_value(row)

    async def get(self, conversation_id):
        async with self.database.sessions() as transaction:
            row = await transaction.get(Conversation, conversation_id)
            if row is None or row.merchant_id != self.merchant_id:
                raise AppError("CONVERSATION_NOT_FOUND")
            messages = (
                await transaction.scalars(
                    select(StoredMessage)
                    .where(
                        StoredMessage.conversation_id == row.id,
                        StoredMessage.merchant_id == self.merchant_id,
                    )
                    .order_by(StoredMessage.seq)
                )
            ).all()
            turns = tuple(
                Turn(
                    item.role,
                    item.content,
                    item.created_at,
                    tuple(item.tool_calls or ()),
                    item.tool_call_id,
                    item.name,
                    item.id,
                    item.seq,
                    item.run_id,
                    item.client_message_id,
                )
                for item in messages
            )
            return session_value(row, turns)

    async def load(self, key):
        resolved = await self.resolve(key)
        return await self.get(resolved.session_id)

    async def update(self, transaction, snapshot, **values):
        result = await transaction.execute(
            update(Conversation)
            .where(
                Conversation.id == snapshot.session_id,
                Conversation.merchant_id == self.merchant_id,
                Conversation.version == snapshot.version,
            )
            .values(**values, version=snapshot.version + 1, updated_at=now())
        )
        if result.rowcount != 1:
            raise AppError("CONVERSATION_BUSY")

    async def save_state(self, snapshot):
        async with self.database.transaction() as transaction:
            await self.update(
                transaction,
                snapshot,
                state={
                    "focused_product_ids": list(snapshot.focused_product_ids),
                    "destination_country": snapshot.destination_country,
                    "quantity": snapshot.quantity,
                },
                reply_language=snapshot.reply_language,
            )
        return await self.get(snapshot.session_id)

    async def append(self, transaction, snapshot, messages):
        sequence = await transaction.scalar(
            select(func.coalesce(func.max(StoredMessage.seq), 0)).where(
                StoredMessage.conversation_id == snapshot.session_id
            )
        )
        for offset, message in enumerate(messages, 1):
            transaction.add(
                StoredMessage(
                    merchant_id=self.merchant_id,
                    conversation_id=snapshot.session_id,
                    seq=sequence + offset,
                    **message,
                )
            )
        await transaction.flush()

    async def update_summary(self, conversation_id, version, summary):
        async with self.database.transaction() as transaction:
            result = await transaction.execute(
                update(Conversation)
                .where(
                    Conversation.id == conversation_id,
                    Conversation.merchant_id == self.merchant_id,
                    Conversation.version == version,
                )
                .values(summary=summary)
            )
            return result.rowcount == 1
